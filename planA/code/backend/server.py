"""
后端服务 —— 把「问题 + 已召回资料」交给装了 skill 的 Agent 生成产物，供前端 Demo 调用。

零第三方依赖：用标准库 http.server（与 llm_client 的 urllib 风格一致，不引入 fastapi）。
密钥只在后端（llm_client 从 .env 读），前端只调本服务，不接触任何 key。

接口：
  GET  /                  → 返回前端 index.html
  GET  /api/cases         → 列出可选的样例 case（前端下拉用）
  POST /api/chat          → body {mode, case} → {text, trace, degraded}
"""
import os
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agent_runtime import run_agent, run_agent_auto

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DIR = os.path.join(HERE, "..", "sample_retrieval")
WEB_DIR = os.path.join(HERE, "..", "web")

_MODE_SKILL = {
    "qa": "patsnap-tech-qa",
    "comparison": "patsnap-compare",
    "promo": "patsnap-promo",
}
_SKILL_MODE = {v: k for k, v in _MODE_SKILL.items()}


def mode_to_skill(mode: str) -> str:
    return _MODE_SKILL.get(mode, "patsnap-tech-qa")


def skill_to_mode(skill: str) -> str:
    return _SKILL_MODE.get(skill, "qa")


def _fallback(mode: str) -> dict:
    with open(os.path.join(HERE, "fallback.json"), encoding="utf-8") as f:
        data = json.load(f)
    return data.get(mode, data["qa"])


# —— 资料召回（模拟检索侧）：按问题挑最相关的已召回资料集 ——
# 真实架构里这一步是检索系统按 message 做向量召回。demo 里用字面重合度模拟。
# 注意：这里只挑「资料」，不决定「用哪个能力」——能力由 Agent 自主判断（见 run_agent_auto）。

def _char_overlap(a: str, b: str) -> int:
    """极简中文相关度：共享的 2-gram 数量。无第三方分词依赖。"""
    grams = lambda s: {s[i:i + 2] for i in range(len(s) - 1)}
    return len(grams(a) & grams(b))


def pick_case(message: str) -> str:
    """按问题与各 case 自带 question 的字面重合度挑最相关的 case；无重合则退第一个。"""
    cases = list_cases()
    if not cases:
        return ""
    best, best_score = None, 0
    for c in cases:
        score = _char_overlap(message, c["question"])
        if score > best_score:
            best, best_score = c["case"], score
    return best if best else cases[0]["case"]


def handle_chat(body: dict) -> dict:
    """召回资料(case) → Agent 自主选 skill 并执行 → 失败降级。
    mode 是 Agent 选出来的（不是后端预判），仅用于前端展示能力标签与选降级档。"""
    message = (body.get("message") or "").strip()
    explicit_case = body.get("case")
    if not message and not explicit_case:
        return {"error": "缺少 message 参数"}

    case = explicit_case or pick_case(message)
    case_dir = os.path.join(SAMPLE_DIR, case)

    # 显式指定 mode/skill 时走定 skill 通道（供测试/回归），否则 Agent 自主选
    explicit_mode = body.get("mode")
    try:
        if explicit_mode:
            skill = mode_to_skill(explicit_mode)
            text, trace = run_agent(skill, case_dir, verbose=False)
            mode = explicit_mode
        else:
            text, trace, selected = run_agent_auto(case_dir, verbose=False)
            mode = skill_to_mode(selected) if selected else "qa"
        return {"text": text, "trace": trace, "degraded": False,
                "mode": mode, "case": case}
    except Exception as e:  # noqa
        mode = explicit_mode or "qa"
        fb = _fallback(mode)
        return {"text": fb["text"], "trace": [], "degraded": True,
                "degraded_reason": str(e)[:120], "mode": mode, "case": case}


def list_cases() -> list:
    if not os.path.isdir(SAMPLE_DIR):
        return []
    out = []
    for name in sorted(os.listdir(SAMPLE_DIR)):
        d = os.path.join(SAMPLE_DIR, name)
        if os.path.isdir(d) and os.path.exists(os.path.join(d, "question.txt")):
            with open(os.path.join(d, "question.txt"), encoding="utf-8") as f:
                q = f.read().strip()
            out.append({"case": name, "question": q})
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        payload = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if "json" in ctype or "html" in ctype else ""))
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            idx = os.path.join(WEB_DIR, "index.html")
            if os.path.exists(idx):
                with open(idx, "rb") as f:
                    return self._send(200, f.read(), "text/html")
            return self._send(404, {"error": "前端未构建"})
        if self.path == "/api/cases":
            return self._send(200, {"cases": list_cases()})
        if self.path.startswith("/assets/"):
            return self._serve_asset(self.path)
        return self._send(404, {"error": "not found"})

    # 静态资源：只服务 web/assets 下的白名单类型，防目录穿越
    _ASSET_TYPES = {".png": "image/png", ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg", ".svg": "image/svg+xml",
                    ".webp": "image/webp", ".ico": "image/x-icon"}

    def _serve_asset(self, path):
        rel = path.lstrip("/")                       # assets/xxx.png
        assets_root = os.path.realpath(os.path.join(WEB_DIR, "assets"))
        target = os.path.realpath(os.path.join(WEB_DIR, rel))
        # 必须落在 assets 目录内（挡住 ../ 穿越）
        if os.path.commonpath([assets_root, target]) != assets_root:
            return self._send(403, {"error": "forbidden"})
        ext = os.path.splitext(target)[1].lower()
        if ext not in self._ASSET_TYPES or not os.path.isfile(target):
            return self._send(404, {"error": "not found"})
        with open(target, "rb") as f:
            return self._send(200, f.read(), self._ASSET_TYPES[ext])

    def do_POST(self):
        if self.path != "/api/chat":
            return self._send(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "invalid json"})
        return self._send(200, handle_chat(body))

    def log_message(self, *args):
        pass  # 静音默认日志


def main(port=8000):
    print(f"芽懂后端启动: http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
