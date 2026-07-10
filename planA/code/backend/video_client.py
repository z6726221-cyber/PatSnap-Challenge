"""
文生视频客户端 —— 用标准库 urllib 直连，风格与 llm_client 一致。
优先使用 OpenAI-compatible 视频配置（VIDEO_*），默认模型为 doubao-seedance-2.0；
未配置 VIDEO 时才回退到可灵 Kling（KLING_*）；如确需复用 LLM_*，必须显式设置 ALLOW_LLM_VIDEO_FALLBACK=1。

接口：
  OpenAI-compatible: POST /chat/completions
  Kling: POST /v1/videos/text2video，GET /v1/videos/text2video/{task_id}

单次调用只出一个 5-10 秒的短镜头，不做多镜头拼接（见 patsnap-promo 视频模式的范围约束）。
"""
import os
import json
import re
import time
import uuid
import urllib.request
import urllib.error


TASKS = {}
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
VIDEO_TASKS_PATH = os.path.join(DATA_DIR, "video_tasks.json")


def _load_env(env_path=None):
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
    for k in ("KLING_BASE_URL", "KLING_API_KEY", "VIDEO_BASE_URL", "VIDEO_API_KEY", "VIDEO_MODEL", "LLM_BASE_URL", "LLM_API_KEY", "ALLOW_LLM_VIDEO_FALLBACK"):
        if os.environ.get(k):
            conf[k] = os.environ[k]
    return conf


def _load_saved_tasks():
    if not os.path.exists(VIDEO_TASKS_PATH):
        return {}
    try:
        with open(VIDEO_TASKS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa
        return {}


def _save_task(task_id, task):
    TASKS[task_id] = task
    os.makedirs(DATA_DIR, exist_ok=True)
    data = _load_saved_tasks()
    data[task_id] = task
    tmp = VIDEO_TASKS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, VIDEO_TASKS_PATH)


def _get_saved_task(task_id):
    task = TASKS.get(task_id)
    if task:
        return task
    task = _load_saved_tasks().get(task_id)
    if task:
        TASKS[task_id] = task
    return task


class VideoClient:
    def __init__(self, env_path=None):
        c = _load_env(env_path)
        self._conf = c
        self.provider = "openai" if (
            c.get("VIDEO_BASE_URL") or c.get("VIDEO_API_KEY") or c.get("VIDEO_MODEL") or
            (c.get("ALLOW_LLM_VIDEO_FALLBACK") == "1" and c.get("LLM_BASE_URL") and c.get("LLM_API_KEY"))
        ) else "kling"
        if self.provider == "openai":
            if c.get("ALLOW_LLM_VIDEO_FALLBACK") == "1":
                c.setdefault("VIDEO_BASE_URL", c.get("LLM_BASE_URL", ""))
                c.setdefault("VIDEO_API_KEY", c.get("LLM_API_KEY", ""))
            c.setdefault("VIDEO_MODEL", "doubao-seedance-2.0")
            missing = [k for k in ("VIDEO_BASE_URL", "VIDEO_API_KEY") if not c.get(k)]
            if missing:
                raise RuntimeError("缺少视频生成配置：" + "、".join(missing))
            self.base_url = c["VIDEO_BASE_URL"].rstrip("/")
            self.model = c.get("VIDEO_MODEL", "doubao-seedance-2.0")
            self._key = c["VIDEO_API_KEY"]
        else:
            missing = [k for k in ("KLING_BASE_URL", "KLING_API_KEY") if not c.get(k)]
            if missing:
                raise RuntimeError("缺少视频生成配置：VIDEO_BASE_URL、VIDEO_API_KEY、VIDEO_MODEL（或 KLING_BASE_URL、KLING_API_KEY）")
            self.base_url = c["KLING_BASE_URL"].rstrip("/")
            self.model = c.get("KLING_MODEL", "kling-v1")
            self._key = c["KLING_API_KEY"]
        self._opener = urllib.request.build_opener()

    def _request(self, method, path, body=None, timeout=30):
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
            raise RuntimeError(_friendly_http_error(e.code, err_body)) from e

    def submit_text2video(self, prompt, duration="5", mode="std", model_name="kling-v1"):
        """提交文生视频任务，返回 task_id。prompt 建议英文，场景/镜头描述越具体越好。"""
        if self.provider == "openai":
            try:
                return self._submit_openai_compatible(prompt)
            except Exception as e:  # noqa
                if not _has_kling_config(self._conf):
                    raise
                task_id = self._submit_kling(prompt, duration=duration, mode=mode, model_name=model_name)
                _save_task(task_id, {
                    "status": "submitted",
                    "video_url": None,
                    "message": "豆包 Seedance 暂不可用，已自动回退可灵生成。",
                    "provider": "kling",
                    "fallback_reason": str(e)[:240],
                    "created_at": time.time(),
                })
                return task_id
        task_id = self._submit_kling(prompt, duration=duration, mode=mode, model_name=model_name)
        _save_task(task_id, {
            "status": "submitted",
            "video_url": None,
            "message": "",
            "provider": "kling",
            "created_at": time.time(),
        })
        return task_id

    def _submit_kling(self, prompt, duration="5", mode="std", model_name="kling-v1"):
        c = self._conf
        old_base, old_model, old_key = self.base_url, self.model, self._key
        self.base_url = c.get("KLING_BASE_URL", self.base_url).rstrip("/")
        self.model = c.get("KLING_MODEL", "kling-v1")
        self._key = c.get("KLING_API_KEY", self._key)
        try:
            data = self._request("POST", "/v1/videos/text2video", {
                "model_name": model_name or self.model,
                "prompt": prompt[:2500],   # Kling 有 prompt 长度上限，截断防报错
                "mode": mode,
                "duration": str(duration),
            })
        finally:
            self.base_url, self.model, self._key = old_base, old_model, old_key
        if data.get("code") != 0:
            raise RuntimeError(f"Kling 提交失败: {data.get('message')}")
        return data["data"]["task_id"]

    def _submit_openai_compatible(self, prompt):
        task_id = "video-" + uuid.uuid4().hex[:10]
        compact_prompt = _compact_video_prompt(prompt)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": compact_prompt},
            ],
        }
        data = self._request("POST", "/chat/completions", payload, timeout=120)
        content = data["choices"][0]["message"].get("content", "")
        url = _extract_url(content)
        _save_task(task_id, {
            "status": "succeed",
            "video_url": url,
            "message": content or "视频任务已完成",
            "provider": "doubao-seedance",
            "created_at": time.time(),
        })
        return task_id

    def get_status(self, task_id):
        """返回 {status, video_url, message}。status: submitted/processing/succeed/failed。"""
        local_task = _get_saved_task(task_id)
        if local_task and local_task.get("provider") != "kling":
            return {k: local_task.get(k) for k in ("status", "video_url", "message")}
        if local_task and local_task.get("provider") == "kling":
            c = self._conf
            old_base, old_key = self.base_url, self._key
            self.base_url = c.get("KLING_BASE_URL", self.base_url).rstrip("/")
            self._key = c.get("KLING_API_KEY", self._key)
            try:
                return self._get_kling_status(task_id, local_task)
            finally:
                self.base_url, self._key = old_base, old_key
        if _looks_like_kling_task(task_id) and _has_kling_config(self._conf):
            c = self._conf
            old_base, old_key = self.base_url, self._key
            self.base_url = c.get("KLING_BASE_URL", self.base_url).rstrip("/")
            self._key = c.get("KLING_API_KEY", self._key)
            try:
                return self._get_kling_status(task_id, local_task)
            finally:
                self.base_url, self._key = old_base, old_key
        return self._get_kling_status(task_id, local_task)

    def _get_kling_status(self, task_id, local_task=None):
        data = self._request("GET", f"/v1/videos/text2video/{task_id}")
        if data.get("code") != 0:
            return {"status": "failed", "video_url": None, "message": data.get("message", "查询失败")}
        d = data["data"]
        status = d.get("task_status", "processing")
        video_url = None
        if status == "succeed":
            videos = d.get("task_result", {}).get("videos", [])
            if videos:
                video_url = videos[0].get("url")
        message = d.get("task_status_msg", "")
        if local_task and local_task.get("message") and status in ("submitted", "processing"):
            message = local_task["message"]
        if local_task:
            next_task = dict(local_task)
            next_task.update({"status": status, "video_url": video_url, "message": message})
            _save_task(task_id, next_task)
        return {"status": status, "video_url": video_url, "message": message}


def _extract_url(text):
    m = re.search(r"https?://[^\s)）\"'<>]+", text or "")
    if not m:
        return None
    return m.group(0).rstrip(".,，。")


def _compact_video_prompt(prompt):
    text = " ".join((prompt or "").split())
    if not text:
        text = "A clean professional software dashboard, warm white interface, slow camera push-in"
    # Seedance 走 OpenAI-compatible 网关时对复杂上下文更敏感，单条 user prompt 最稳。
    return text[:1200]


def _has_kling_config(conf):
    return bool(conf.get("KLING_BASE_URL") and conf.get("KLING_API_KEY"))


def _looks_like_kling_task(task_id):
    return bool(re.fullmatch(r"\d{12,}", task_id or ""))


def _friendly_http_error(code, body):
    message = body[:500]
    try:
        data = json.loads(body)
        err = data.get("error") or {}
        message = err.get("message") or err.get("code") or message
    except Exception:  # noqa
        pass
    if code >= 500:
        return (
            f"视频服务 HTTP {code}: 上游视频模型内部错误。已使用单条 user prompt 提交；"
            "如果仍失败，通常是模型网关临时不可用、该账号未开通视频生成、或当前模型只返回文本不产出视频 URL。"
            f" 原始信息：{message[:180]}"
        )
    return f"视频服务 HTTP {code}: {message}"


if __name__ == "__main__":
    import sys
    import time
    cli = VideoClient()
    prompt = sys.argv[1] if len(sys.argv) > 1 else "a professional software dashboard showing patent search results, clean UI, camera slowly zooming in"
    task_id = cli.submit_text2video(prompt)
    print("task_id:", task_id)
    for _ in range(30):
        time.sleep(5)
        st = cli.get_status(task_id)
        print(st)
        if st["status"] in ("succeed", "failed"):
            break
