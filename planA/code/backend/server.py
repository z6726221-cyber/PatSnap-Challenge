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

from agent_runtime import run_agent

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DIR = os.path.join(HERE, "..", "sample_retrieval")
WEB_DIR = os.path.join(HERE, "..", "web")

_MODE_SKILL = {
    "qa": "patsnap-tech-qa",
    "comparison": "patsnap-compare",
    "promo": "patsnap-promo",
}


def mode_to_skill(mode: str) -> str:
    return _MODE_SKILL.get(mode, "patsnap-tech-qa")


def _fallback(mode: str) -> dict:
    with open(os.path.join(HERE, "fallback.json"), encoding="utf-8") as f:
        data = json.load(f)
    return data.get(mode, data["qa"])


def handle_chat(body: dict) -> dict:
    """核心逻辑：mode→skill，加载 case 跑 Agent，失败降级。"""
    case = body.get("case")
    if not case:
        return {"error": "缺少 case 参数"}
    mode = body.get("mode", "qa")
    skill = mode_to_skill(mode)
    case_dir = os.path.join(SAMPLE_DIR, case)
    try:
        text, trace = run_agent(skill, case_dir, verbose=False)
        return {"text": text, "trace": trace, "degraded": False}
    except Exception as e:  # noqa
        fb = _fallback(mode)
        return {"text": fb["text"], "trace": [], "degraded": True,
                "degraded_reason": str(e)[:120]}


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
        return self._send(404, {"error": "not found"})

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
