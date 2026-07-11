"""
极简 LLM 客户端 —— 用标准库 urllib 直连内部 OpenAI 兼容端点。
不依赖 openai 库（本环境 PyPI 不可达），出网走系统 http_proxy 代理。
支持 function calling（工具调用），供 Agent 运行时使用。
"""

import os
import json
import urllib.request
import urllib.error


def _load_env(env_path=None):
    """从 backend/.env 读配置（不硬编码 key）。"""
    if env_path is None:
        env_path = os.path.join(os.path.dirname(__file__), ".env")
    conf = {}
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                conf[k.strip()] = v.strip()
    # 环境变量优先（便于覆盖）
    for k in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"):
        if os.environ.get(k):
            conf[k] = os.environ[k]
    return conf


class LLMClient:
    def __init__(self, env_path=None):
        c = _load_env(env_path)
        self.base_url = c["LLM_BASE_URL"].rstrip("/")
        self.model = c.get("LLM_MODEL", "claude-opus-4-6")
        self._key = c["LLM_API_KEY"]
        # urllib 默认 opener 会读 https_proxy 环境变量；显式构造以确保走代理
        self._opener = urllib.request.build_opener()

    def chat(self, messages, tools=None, tool_choice=None, temperature=None, timeout=90):
        """发一次 chat.completions 请求，返回原始 message dict（含可能的 tool_calls）。"""
        payload = {"model": self.model, "messages": messages}
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice
        if temperature is not None:
            payload["temperature"] = temperature

        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self._key,
            },
            method="POST",
        )
        try:
            resp = self._opener.open(req, timeout=timeout)
            data = json.load(resp)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            raise RuntimeError(f"LLM HTTP {e.code}: {body[:500]}") from e
        return data["choices"][0]["message"], data.get("usage", {})


if __name__ == "__main__":
    # 自检
    cli = LLMClient()
    msg, usage = cli.chat([{"role": "user", "content": "只回复三个字:自检通过"}])
    print("模型回复:", msg.get("content"))
    print("tokens:", usage.get("total_tokens"))
