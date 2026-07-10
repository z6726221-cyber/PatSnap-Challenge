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
import re
import json
import cgi
import mimetypes
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agent_runtime import run_agent, run_agent_auto, run_agent_with_case, run_agent_auto_with_case
from image_client import IMAGE_DIR, ImageClient
from loader import Case, Material, load_live
from local_store import add_kb, add_project, add_upload, export_text, list_kb, list_projects, load_store
from video_client import VideoClient

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DIR = os.path.join(HERE, "..", "sample_retrieval")
LIVE_DIR = os.path.join(SAMPLE_DIR, "live")
WEB_DIR = os.path.join(HERE, "..", "web")

# patsnap-promo 视频模式产物末尾固定带的一段：
#   ## 视频生成提示词
#   ```英文场景描述```
# 提取这句场景描述交给视频服务；找不到就报错，不用兜底文案顶替（避免生成跟文案毫不相关的画面）。
_VIDEO_PROMPT_RE = re.compile(r"##\s*视频生成提示词\s*\n+```([a-zA-Z]*)\n?(.+?)```", re.DOTALL)
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_SOURCE_RE = re.compile(r"(?:来源|source)[：:]\s*`?([^`\s，,；;]+)`?", re.IGNORECASE)
_UPDATED_RE = re.compile(r"(?:更新时间|updated_at|时间)[：:]\s*([0-9]{4}-[0-9]{2}(?:-[0-9]{2})?|时间未知)", re.IGNORECASE)


def extract_video_prompt(text: str) -> str:
    """从 ```text\n...``` 或裸 ```...``` 里取场景描述；模型有时会像 GFM 代码块
    一样带语言标签（如 ```text），第一个捕获组吃掉那行，避免它混进提示词。"""
    m = _VIDEO_PROMPT_RE.search(text or "")
    if not m:
        raise ValueError("生成稿里未找到「## 视频生成提示词」分镜提示词段")
    return m.group(2).strip()


def _extract_sections(text: str) -> list:
    """把 Agent 的 markdown 二级标题切成轻量 sections，供前端稳定辅助渲染。

    这是展示增强字段，不改变 text 本身；即使模型没按格式输出，也只返回少量
    可识别段落，前端仍可回退到 markdown 渲染。
    """
    text = text or ""
    matches = list(_SECTION_RE.finditer(text))
    sections = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append({
            "title": m.group(1).strip(),
            "content": text[start:end].strip(),
        })
    return sections


def _extract_citations(text: str) -> list:
    citations = []
    for line in (text or "").splitlines():
        sm = _SOURCE_RE.search(line)
        if not sm:
            continue
        tm = _UPDATED_RE.search(line)
        citations.append({
            "source": sm.group(1).strip(),
            "updated_at": tm.group(1).strip() if tm else "",
            "line": line.strip(),
        })
    return citations[:20]


def _extract_missing_items(text: str) -> list:
    items = []
    for line in (text or "").splitlines():
        if line.lstrip().startswith("#"):
            continue
        clean = line.strip().lstrip("-*0123456789.、)） ").strip()
        if clean and ("待核实" in clean or "未找到" in clean or "未在已召回资料" in clean):
            items.append(clean)
    return items[:20]


def structure_output(text: str, mode: str) -> dict:
    structured = {
        "sections": _extract_sections(text),
        "citations": _extract_citations(text),
        "missing_items": _extract_missing_items(text),
    }
    if mode == "promo" and "## 视频生成提示词" in (text or ""):
        try:
            structured["video_prompt"] = extract_video_prompt(text)
        except ValueError:
            structured["video_prompt"] = ""
    return structured

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


def _fallback(mode: str, message: str = "") -> dict:
    with open(os.path.join(HERE, "fallback.json"), encoding="utf-8") as f:
        data = json.load(f)
    if mode == "promo" and ("内容形式：视频" in message or "视频" in message):
        return data.get("promo_video", data.get("promo", data["qa"]))
    return data.get(mode, data["qa"])


# —— 假样例回归通道：按问题挑最相关的预置 case 文件夹 ——
# 仅供测试/回归用（显式传 case 或 mode 时）。真实提问走 live 目录，见 handle_chat。

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


def _has_live_material() -> bool:
    return os.path.isdir(LIVE_DIR) and any(n.endswith(".md") for n in os.listdir(LIVE_DIR))


def _retrieval_meta(source: str, case: Case) -> dict:
    materials = getattr(case, "materials", []) or []
    return {
        "source": source,
        "count": len(materials),
        "titles": [getattr(m, "title", "") for m in materials[:5]],
    }


def _retrieve_local_case(message: str, mode: str) -> tuple:
    """从本地知识库做一次轻量召回，给内容生成/竞品分析提供真实材料输入。

    这里不是让生成模型凭空写，而是把知识库条目包装成 loader.Case 的 Material，
    后续仍通过 list_materials/read_material/check_conflicts 工具读取。
    """
    data = load_store()
    query = message or ""
    kinds = ("promo", "sales") if mode == "promo" else ("sales", "promo")
    candidates = []
    for kind in kinds:
        for item in data.get("kb", {}).get(kind, []):
            hay = " ".join(str(item.get(k, "")) for k in ("title", "body", "category", "product"))
            score = _char_overlap(query, hay)
            if item.get("product") and item["product"] in query:
                score += 6
            if item.get("category") and item["category"] in query:
                score += 4
            if kind == "promo" and mode == "promo":
                score += 2
            candidates.append((score, kind, item))

    candidates.sort(key=lambda x: x[0], reverse=True)
    selected = [x for x in candidates if x[0] > 0][:8] or candidates[:6]
    materials = []
    for rank, (score, kind, item) in enumerate(selected, 1):
        title = item.get("title") or "未命名知识"
        category = item.get("category") or "知识"
        product = item.get("product") or ("运营素材库" if kind == "promo" else "销售知识库")
        body = (
            f"# {title}\n\n"
            f"知识库：{'运营素材库' if kind == 'promo' else '销售知识库'}\n"
            f"分类：{category}\n"
            f"产品线/项目：{product}\n\n"
            f"{item.get('body') or ''}"
        )
        materials.append(Material(
            source=f"kb://{kind}/{item.get('id', rank)}",
            updated_at=item.get("updated_at", ""),
            authority="L2",
            topic=f"{kind}/{product}/{category}",
            score=max(0.1, min(1.0, 0.55 + score / 40)),
            title=title,
            body=body,
        ))
    if not materials:
        raise RuntimeError("本地知识库暂无可检索资料")
    case = Case(question=message, materials=materials)
    return case, _retrieval_meta("local-kb", case)


def handle_chat(body: dict) -> dict:
    """真实提问：读检索侧写到 sample_retrieval/live/ 的实时资料 + 用户问题 → Agent
    自主选 skill 并执行。live/ 里没有资料（检索还没跑过）时直接降级，不再用假样例兜底。

    显式传 case（供测试/回归）时走假样例 case 文件夹通道，行为不变。
    mode 是 Agent 选出来的（不是后端预判），仅用于前端展示能力标签与选降级档。"""
    message = (body.get("message") or "").strip()
    explicit_case = body.get("case")
    if not message and not explicit_case:
        return {"error": "缺少 message 参数"}

    explicit_mode = body.get("mode")
    case_label = explicit_case or "live"
    retrieval = None
    try:
        if explicit_case:
            case_dir = os.path.join(SAMPLE_DIR, explicit_case)
            if explicit_mode:
                text, trace = run_agent(mode_to_skill(explicit_mode), case_dir, verbose=False)
                mode = explicit_mode
            else:
                text, trace, selected = run_agent_auto(case_dir, verbose=False)
                mode = skill_to_mode(selected) if selected else "qa"
        else:
            if explicit_mode in ("promo", "comparison"):
                if _has_live_material():
                    case = load_live(LIVE_DIR, question=message)
                    retrieval = _retrieval_meta("live", case)
                    case_label = "live"
                else:
                    case, retrieval = _retrieve_local_case(message, explicit_mode)
                    case_label = retrieval["source"]
            else:
                if not _has_live_material():
                    raise RuntimeError("live/ 暂无检索资料（检索系统还未产出结果）")
                case = load_live(LIVE_DIR, question=message)
                retrieval = _retrieval_meta("live", case)
            if explicit_mode:
                text, trace = run_agent_with_case(mode_to_skill(explicit_mode), case, verbose=False)
                mode = explicit_mode
            else:
                text, trace, selected = run_agent_auto_with_case(case, verbose=False)
                mode = skill_to_mode(selected) if selected else "qa"
        out = {"text": text, "trace": trace, "degraded": False,
               "mode": mode, "case": case_label,
               "structured": structure_output(text, mode)}
        if retrieval:
            out["retrieval"] = retrieval
        return out
    except Exception as e:  # noqa
        mode = explicit_mode or "qa"
        fb = _fallback(mode, message)
        return {"text": fb["text"], "trace": [], "degraded": True,
                "degraded_reason": str(e)[:120], "mode": mode, "case": case_label,
                "structured": structure_output(fb["text"], mode)}


def handle_video_start(body: dict) -> dict:
    """从内容生成（视频模式）产物里取出场景提示词，提交给配置的视频模型，返回 task_id。
    body: {text: 生成产物全文}"""
    text = body.get("text") or ""
    try:
        prompt = extract_video_prompt(text)
    except ValueError as e:
        return {"error": str(e)}
    try:
        task_id = VideoClient().submit_text2video(prompt)
    except Exception as e:  # noqa
        return {"error": f"提交视频生成任务失败：{e}"}
    return {"task_id": task_id, "prompt": prompt}


def handle_video_status(task_id: str) -> dict:
    try:
        return VideoClient().get_status(task_id)
    except Exception as e:  # noqa
        return {"status": "failed", "video_url": None, "message": str(e)[:200]}


def handle_image_generate(body: dict) -> dict:
    text = (body.get("text") or "").strip()
    instruction = (body.get("instruction") or "").strip()
    if not text:
        return {"error": "缺少 text 参数，需先生成文案/话术后再生成配图"}
    try:
        return ImageClient().generate_poster(text, instruction=instruction)
    except Exception as e:  # noqa
        return {"error": f"图片生成失败：{e}"}


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
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        if path == "/" or path == "/index.html":
            idx = os.path.join(WEB_DIR, "index.html")
            if os.path.exists(idx):
                with open(idx, "rb") as f:
                    return self._send(200, f.read(), "text/html")
            return self._send(404, {"error": "前端未构建"})
        if path == "/api/cases":
            return self._send(200, {"cases": list_cases()})
        if path == "/api/kb":
            kind = query.get("kind", [None])[0]
            return self._send(200, {"kb": list_kb(kind), "projects": list_projects(), "uploads": load_store().get("uploads", [])})
        if path.startswith("/api/video/status/"):
            task_id = path[len("/api/video/status/"):]
            return self._send(200, handle_video_status(task_id))
        if path.startswith("/api/image/file/"):
            name = urllib.parse.unquote(path[len("/api/image/file/"):])
            return self._serve_generated_image(name)
        if path.startswith("/api/download/"):
            rel = urllib.parse.unquote(path[len("/api/download/"):])
            return self._serve_download(rel)
        if path.startswith("/assets/"):
            return self._serve_asset(path)
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

    def _serve_download(self, rel):
        base = os.path.realpath(os.path.join(HERE, "data"))
        target = os.path.realpath(os.path.join(base, rel))
        if os.path.commonpath([base, target]) != base or not os.path.isfile(target):
            return self._send(404, {"error": "not found"})
        ctype = mimetypes.guess_type(target)[0] or "application/octet-stream"
        with open(target, "rb") as f:
            payload = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Content-Disposition", f"attachment; filename=\"{os.path.basename(target)}\"")
        self.end_headers()
        self.wfile.write(payload)

    def _serve_generated_image(self, name):
        if "/" in name or "\\" in name:
            return self._send(404, {"error": "not found"})
        base = os.path.realpath(IMAGE_DIR)
        target = os.path.realpath(os.path.join(base, name))
        if os.path.commonpath([base, target]) != base or not os.path.isfile(target):
            return self._send(404, {"error": "not found"})
        ext = os.path.splitext(target)[1].lower()
        ctype = "image/png" if ext == ".png" else "image/jpeg" if ext in (".jpg", ".jpeg") else "application/octet-stream"
        with open(target, "rb") as f:
            return self._send(200, f.read(), ctype)

    def do_POST(self):
        if self.path not in ("/api/chat", "/api/video/start", "/api/image/generate", "/api/upload", "/api/kb", "/api/export"):
            return self._send(404, {"error": "not found"})
        if self.path == "/api/upload":
            return self._handle_upload()
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "invalid json"})
        if self.path == "/api/video/start":
            return self._send(200, handle_video_start(body))
        if self.path == "/api/image/generate":
            return self._send(200, handle_image_generate(body))
        if self.path == "/api/kb":
            try:
                if body.get("project"):
                    project = add_project(body.get("name") or body.get("item", {}).get("title"), body.get("kind") or "sales")
                    return self._send(200, {"project": project})
                item = add_kb(body.get("kind") or "sales", body.get("item") or {})
                return self._send(200, {"item": item})
            except ValueError as e:
                return self._send(400, {"error": str(e)})
        if self.path == "/api/export":
            title = body.get("title") or "芽懂导出"
            content = body.get("content") or ""
            path = export_text(title, content)
            rel = os.path.relpath(path, os.path.join(HERE, "data"))
            return self._send(200, {"download_url": "/api/download/" + urllib.parse.quote(rel)})
        return self._send(200, handle_chat(body))

    def _handle_upload(self):
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": self.headers.get("Content-Type", ""),
        })
        file_field = form["file"] if "file" in form else None
        if file_field is None or not getattr(file_field, "filename", ""):
            return self._send(400, {"error": "缺少上传文件"})
        content = file_field.file.read()
        try:
            item = add_upload(
                file_field.filename,
                content,
                description=form.getfirst("description", ""),
                visibility=form.getfirst("visibility", "销售和运营可见"),
                owner=form.getfirst("owner", "算法研发团队"),
                kind=form.getfirst("kind", "sales"),
                category=form.getfirst("category", "研发资料"),
            )
        except ValueError as e:
            return self._send(400, {"error": str(e)})
        return self._send(200, {"upload": item, "message": "上传成功，已同步到 live 检索资料与对应知识库"})

    def log_message(self, *args):
        pass  # 静音默认日志


def main(port=8000):
    print(f"芽懂后端启动: http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
