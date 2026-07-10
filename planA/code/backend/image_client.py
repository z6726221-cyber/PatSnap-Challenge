"""
图片生成客户端 —— 用标准库 urllib 调 OpenAI-compatible images 接口。

默认复用视频模型配置（VIDEO_BASE_URL / VIDEO_API_KEY），模型默认 doubao-seedream-5.0-lite。
如果单独配置 IMAGE_BASE_URL / IMAGE_API_KEY / IMAGE_MODEL，则优先使用 IMAGE_*。
seedream 要求至少 1920x1920；如果默认模型不可用，可回退到 doubao-seedream-4.5。
生成结果保存到 backend/data/generated_images/，前端通过本服务读取图片文件。
"""
import base64
import json
import os
import re
import time
import uuid
import urllib.error
import urllib.request


HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
IMAGE_DIR = os.path.join(DATA_DIR, "generated_images")


def _load_env(env_path=None):
    if env_path is None:
        env_path = os.path.join(HERE, ".env")
    conf = {}
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                conf[k.strip()] = v.strip()
    for k in ("IMAGE_BASE_URL", "IMAGE_API_KEY", "IMAGE_MODEL", "IMAGE_FALLBACK_MODEL", "VIDEO_BASE_URL", "VIDEO_API_KEY"):
        if os.environ.get(k):
            conf[k] = os.environ[k]
    return conf


class ImageClient:
    def __init__(self, env_path=None):
        c = _load_env(env_path)
        self.base_url = (c.get("IMAGE_BASE_URL") or c.get("VIDEO_BASE_URL") or "").rstrip("/")
        self.model = c.get("IMAGE_MODEL", "doubao-seedream-5.0-lite")
        self.fallback_model = c.get("IMAGE_FALLBACK_MODEL", "doubao-seedream-4.5")
        self._key = c.get("IMAGE_API_KEY") or c.get("VIDEO_API_KEY")
        if not self.base_url or not self._key:
            raise RuntimeError("缺少图片生成配置：IMAGE_BASE_URL/IMAGE_API_KEY，或复用 VIDEO_BASE_URL/VIDEO_API_KEY")
        self._opener = urllib.request.build_opener()

    def generate_poster(self, source_text, instruction="", size="1024x1024"):
        prompt = build_poster_prompt(source_text, instruction)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "size": _model_size(self.model, size),
            "n": 1,
        }
        model_used = self.model
        try:
            data = self._request("POST", "/images/generations", payload, timeout=180)
        except RuntimeError as e:
            if not self.fallback_model or self.fallback_model == self.model or not _should_try_fallback(str(e)):
                raise
            model_used = self.fallback_model
            payload = dict(payload)
            payload["model"] = self.fallback_model
            payload["size"] = _model_size(self.fallback_model, size)
            data = self._request("POST", "/images/generations", payload, timeout=180)
        item = (data.get("data") or [{}])[0]
        if item.get("url"):
            return {"image_url": item["url"], "prompt": prompt, "model": model_used, "size": payload["size"]}
        if item.get("b64_json"):
            rel = _save_b64_image(item["b64_json"])
            return {"image_url": "/api/image/file/" + rel, "prompt": prompt, "model": model_used, "size": payload["size"]}
        # 兼容少数网关把图片链接塞进文本字段的情况。
        text = json.dumps(data, ensure_ascii=False)
        url = _extract_url(text)
        if url:
            return {"image_url": url, "prompt": prompt, "model": model_used, "size": payload["size"]}
        raise RuntimeError("图片模型未返回 url 或 b64_json")

    def _request(self, method, path, body=None, timeout=60):
        req = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self._key,
            },
            method=method,
        )
        try:
            resp = self._opener.open(req, timeout=timeout)
            return json.load(resp)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", "replace")
            raise RuntimeError(f"图片服务 HTTP {e.code}: {err_body[:500]}") from e


def build_poster_prompt(source_text, instruction=""):
    text = _compact(source_text, 1400)
    instruction = _compact(instruction, 320)
    extra = f"\nRefinement request: {instruction}" if instruction else ""
    return (
        "Create a polished SaaS marketing poster image for a PatSnap private knowledge assistant. "
        "Visual style: premium enterprise software, warm off-white background, deep green accents, "
        "clean product-dashboard inspired composition, subtle data cards and knowledge-flow lines, "
        "professional Chinese B2B technology marketing mood. "
        "Do not render readable text, logos, watermarks, UI screenshots, or fake brand marks. "
        "Focus on the visual metaphor and layout space where copy can be placed later.\n"
        f"Source marketing content summary:\n{text}{extra}"
    )


def _compact(text, limit):
    return " ".join((text or "").split())[:limit]


def _should_try_fallback(message):
    msg = (message or "").lower()
    return (
        "billing_hard_limit_reached" in msg
        or "billing hard limit" in msg
        or "image size must be at least" in msg
        or "invalid engine" in msg
    )


def _model_size(model, size):
    if "seedream" in (model or "").lower():
        return _large_enough_size(size)
    return size


def _large_enough_size(size):
    width, height = _parse_size(size)
    if width * height >= 3686400:
        return size
    return "1920x1920"


def _parse_size(size):
    m = re.fullmatch(r"(\d+)x(\d+)", str(size or ""))
    if not m:
        return 0, 0
    return int(m.group(1)), int(m.group(2))


def _save_b64_image(b64_json):
    raw = base64.b64decode(b64_json)
    os.makedirs(IMAGE_DIR, exist_ok=True)
    name = f"poster-{int(time.time())}-{uuid.uuid4().hex[:8]}.png"
    path = os.path.join(IMAGE_DIR, name)
    with open(path, "wb") as f:
        f.write(raw)
    return name


def _extract_url(text):
    m = re.search(r"https?://[^\s)）\"'<>]+", text or "")
    if not m:
        return None
    return m.group(0).rstrip(".,，。")
