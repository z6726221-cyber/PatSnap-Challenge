#!/usr/bin/env python3
"""YADO full-chain E2E runner.

This is intentionally outside normal unittest discovery because it calls the
real configured LLM API and can be slow/flaky. It exercises:

1. skill runtime with real function-calling Agent;
2. backend handle_chat contracts;
3. in-process HTTP server endpoints used by the frontend;
4. static frontend wiring/PRD checks.

Outputs are written to code/e2e/reports/<timestamp>/ for inspection.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FIXTURE = ROOT / "e2e" / "fixtures"
WEB = ROOT / "web" / "index.html"
REPORT_ROOT = ROOT / "e2e" / "reports"
sys.path.insert(0, str(BACKEND))

import server  # noqa: E402
from agent_runtime import run_agent, run_agent_auto  # noqa: E402


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: list[str]
    score: int = 0


def now_slug() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def contains_any(text: str, options: list[str]) -> bool:
    return any(x in text for x in options)


def score_text(name: str, text: str, required: list[str], forbidden: list[str] | None = None) -> CheckResult:
    details: list[str] = []
    forbidden = forbidden or []
    score = 100
    for item in required:
        if item not in text:
            details.append(f"缺少必需片段：{item}")
            score -= 12
    for item in forbidden:
        if item in text:
            details.append(f"出现禁用片段：{item}")
            score -= 15
    if "来源" not in text and "source:" not in text and "kb://" not in text and "public-demo://" not in text:
        details.append("缺少来源标注")
        score -= 18
    if "更新时间" not in text and "时间未知" not in text and re.search(r"20\d{2}-\d{2}-\d{2}", text) is None:
        details.append("缺少更新时间/时间未知标注")
        score -= 10
    if "待核实" not in text and "未找到" not in text and "缺口" not in text:
        details.append("没有显式待核实/缺口表达，需确认是否过度确定")
        score -= 8
    score = max(0, score)
    return CheckResult(name=name, ok=not details, details=details, score=score)


def write_case_report(report_dir: Path, name: str, payload: dict) -> None:
    path = report_dir / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    text = payload.get("text")
    if text:
        (report_dir / f"{name}.md").write_text(text, encoding="utf-8")


CASES = [
    {
        "name": "skill_presales",
        "case": "presales-engineering",
        "skill": "patsnap-presales",
        "mode": "presales",
        "required": ["客户背景", "潜在痛点", "沟通话术", "行动清单", "本次方案依据", "公开信息", "企业知识", "AI 推断"],
        "forbidden": ["已经同步 CRM", "已发送邮件", "确定采购"],
    },
    {
        "name": "skill_promo_video",
        "case": "promo-video-analytics",
        "skill": "patsnap-promo",
        "mode": "promo",
        "required": ["30秒", "字幕", "发布配文", "事实来源", "视频生成提示词"],
        "forbidden": ["销售话术", "5-10 秒单镜头", "5-10 秒短片", "完整成片已生成"],
    },
    {
        "name": "skill_tech_explain",
        "case": "tech-explain-triz",
        "skill": "patsnap-tech-explain",
        "mode": "tech_explain",
        "required": ["一句话解释", "通俗解释", "核心原理", "业务价值", "能力边界", "FAQ", "知识来源", "AI 类比"],
        "forbidden": ["革命性", "颠覆"],
    },
]


def run_skill_cases(report_dir: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    for cfg in CASES:
        case_dir = FIXTURE / cfg["case"]
        text, trace = run_agent(cfg["skill"], str(case_dir), verbose=False)
        check = score_text(cfg["name"], text, cfg["required"], cfg.get("forbidden"))
        results.append(check)
        write_case_report(report_dir, cfg["name"], {
            "config": cfg,
            "check": asdict(check),
            "trace_tools": [t.get("tool") for t in trace],
            "trace": trace,
            "text": text,
        })
    return results


def run_auto_skill_case(report_dir: Path) -> CheckResult:
    text, trace, selected = run_agent_auto(str(FIXTURE / "auto-compare"), verbose=False)
    check = score_text(
        "skill_auto_compare",
        text,
        ["对比", "Analytics AI Mode", "Clarivate", "来源"],
        ["销售与售前拜访报告"],
    )
    if selected != "patsnap-compare":
        check.details.append(f"自动路由错误：期望 patsnap-compare，实际 {selected}")
        check.ok = False
        check.score = max(0, check.score - 25)
    write_case_report(report_dir, "skill_auto_compare", {
        "selected": selected,
        "check": asdict(check),
        "trace_tools": [t.get("tool") for t in trace],
        "trace": trace,
        "text": text,
    })
    return check


def run_backend_contracts(report_dir: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    for cfg in CASES:
        out = server.handle_chat({"message": "", "mode": cfg["mode"], "case": cfg["case"]})
        text = out.get("text", "")
        check = score_text("backend_" + cfg["mode"], text, cfg["required"], cfg.get("forbidden"))
        if out.get("degraded"):
            check.details.append("后端返回 degraded=True：" + str(out.get("degraded_reason", "")))
            check.ok = False
            check.score = max(0, check.score - 25)
        if out.get("mode") != cfg["mode"]:
            check.details.append(f"mode 不一致：{out.get('mode')} != {cfg['mode']}")
            check.ok = False
            check.score = max(0, check.score - 10)
        if not out.get("structured", {}).get("sections"):
            check.details.append("structured.sections 为空，前端辅助渲染会退化")
            check.ok = False
            check.score = max(0, check.score - 8)
        results.append(check)
        write_case_report(report_dir, "backend_" + cfg["mode"], {
            "request": {"mode": cfg["mode"], "case": cfg["case"]},
            "check": asdict(check),
            "response_meta": {k: out.get(k) for k in ("degraded", "mode", "case", "retrieval")},
            "structured": out.get("structured"),
            "trace_tools": [t.get("tool") for t in out.get("trace", [])],
            "text": text,
        })
    return results


def http_json(url: str, payload: dict | None = None, timeout: int = 180) -> dict:
    if payload is None:
        req = urllib.request.Request(url, method="GET")
    else:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def run_http_smoke(report_dir: Path, port: int) -> list[CheckResult]:
    httpd = server.ThreadingHTTPServer(("127.0.0.1", port), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    results: list[CheckResult] = []
    try:
        cases = http_json(base + "/api/cases")
        case_names = {c["case"] for c in cases.get("cases", [])}
        missing = [c["case"] for c in CASES if c["case"] not in case_names]
        ok = not missing
        details = [f"/api/cases 缺少：{', '.join(missing)}"] if missing else []
        results.append(CheckResult("http_cases", ok, details, 100 if ok else 60))

        payload = {"message": "解释主题：TRIZ 是什么？", "mode": "tech_explain", "case": "tech-explain-triz"}
        out = http_json(base + "/api/chat", payload)
        check = score_text("http_chat_tech_explain", out.get("text", ""), CASES[2]["required"], CASES[2]["forbidden"])
        if out.get("degraded"):
            check.details.append("HTTP /api/chat degraded=True")
            check.ok = False
            check.score = max(0, check.score - 25)
        results.append(check)
        write_case_report(report_dir, "http_chat_tech_explain", {
            "request": payload,
            "check": asdict(check),
            "response_meta": {k: out.get(k) for k in ("degraded", "mode", "case")},
            "structured": out.get("structured"),
            "text": out.get("text", ""),
        })

        export = http_json(base + "/api/export", {"title": "E2E 导出", "content": out.get("text", "")})
        ok = bool(export.get("download_url"))
        results.append(CheckResult("http_export", ok, [] if ok else ["缺少 download_url"], 100 if ok else 0))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        results.append(CheckResult("http_smoke", False, [repr(exc)], 0))
    finally:
        httpd.shutdown()
        httpd.server_close()
    return results


def run_frontend_static_checks() -> list[CheckResult]:
    html = WEB.read_text(encoding="utf-8")
    aside_match = re.search(r"<aside class=\"side\">(.*?)</aside>", html, re.DOTALL)
    nav_html = aside_match.group(1) if aside_match else ""
    checks = [
        ("frontend_nav_no_market_main", "市场与产品洞察" not in nav_html, "主导航仍包含“市场与产品洞察”"),
        ("frontend_nav_has_sales", "销售与售前" in nav_html, "缺少“销售与售前”入口"),
        ("frontend_nav_knowledge_space", "知识空间" in nav_html, "侧栏仍未改成“知识空间”"),
        ("frontend_has_tech_explain_page", "产品与技术解释" in html or "tech_explain" in html, "缺少产品与技术解释工作台"),
        ("frontend_promo_30s", "30s" in html or "30 秒" in html or "30秒" in html, "营销短视频 UI 仍未体现 30 秒方案"),
        ("frontend_upload_not_live", "已同步到 live" not in html, "前端仍暗示上传同步 live"),
    ]
    return [CheckResult(name, ok, [] if ok else [detail], 100 if ok else 0) for name, ok, detail in checks]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-real-api", action="store_true", help="Only run static/frontend checks; no LLM calls.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--report-dir", default="")
    args = parser.parse_args()

    report_dir = Path(args.report_dir) if args.report_dir else REPORT_ROOT / now_slug()
    report_dir.mkdir(parents=True, exist_ok=True)

    all_results: list[CheckResult] = []
    if not args.skip_real_api:
        all_results.extend(run_skill_cases(report_dir))
        all_results.append(run_auto_skill_case(report_dir))
        all_results.extend(run_backend_contracts(report_dir))
        all_results.extend(run_http_smoke(report_dir, args.port))
    all_results.extend(run_frontend_static_checks())

    summary = {
        "ok": all(r.ok for r in all_results),
        "report_dir": str(report_dir),
        "results": [asdict(r) for r in all_results],
    }
    (report_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
