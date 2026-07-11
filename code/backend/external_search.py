"""
外部情报检索适配层。

当前仓库不能内置真实搜索供应商 key，所以这里做成可插拔适配器：
- 配置 EXTERNAL_SEARCH_ENDPOINT 后，后端会把 query POST 给该服务并接收统一 items。
- 配置 EXTERNAL_SEARCH_ENDPOINT=mock 或 EXTERNAL_SEARCH_USE_MOCK=1 时，读取
  code/sample_retrieval/mock_external/ 里的可提交模拟公开信息。
- 未配置时明确返回 unavailable，调用方会把"需要外部检索补充"写进材料，而不是假装已经联网。
"""
import json
import os
import urllib.error
import urllib.request

from loader import parse_materials_from_file


HERE = os.path.dirname(os.path.abspath(__file__))
MOCK_EXTERNAL_DIR = os.path.join(HERE, "..", "sample_retrieval", "mock_external")


def _char_overlap(a: str, b: str) -> int:
    grams = lambda s: {s[i:i + 2] for i in range(len(s) - 1)}
    return len(grams(a or "") & grams(b or ""))


def _search_mock_external(query: str, limit: int) -> dict:
    if not os.path.isdir(MOCK_EXTERNAL_DIR):
        return {
            "available": False,
            "reason": f"mock_external 目录不存在：{MOCK_EXTERNAL_DIR}",
            "items": [],
        }

    scored = []
    for name in sorted(os.listdir(MOCK_EXTERNAL_DIR)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(MOCK_EXTERNAL_DIR, name)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for material in parse_materials_from_file(text, filename=name):
            hay = " ".join([material.title, material.topic, material.body])
            score = _char_overlap(query, hay) + int((material.score or 0) * 10)
            scored.append((score, material))

    scored.sort(key=lambda x: x[0], reverse=True)
    items = []
    for _, material in scored[:limit]:
        snippet = " ".join((material.body or "").split())[:240]
        items.append({
            "title": material.title or material.source or "外部公开信息模拟资料",
            "snippet": snippet,
            "url": material.source or "public-demo://unknown",
            "updated_at": material.updated_at or "时间未知",
        })
    return {
        "available": bool(items),
        "reason": "mock_external fixture" if items else "mock_external 目录没有可用 .md 资料",
        "items": items,
    }


def search_external_intel(query: str, limit: int = 5) -> dict:
    endpoint = (os.getenv("EXTERNAL_SEARCH_ENDPOINT") or "").strip()
    use_mock = (os.getenv("EXTERNAL_SEARCH_USE_MOCK") or "").strip().lower() in ("1", "true", "yes")
    if endpoint.lower() in ("mock", "mock_external", "file://mock_external") or use_mock:
        return _search_mock_external(query, limit)

    if not endpoint:
        return {
            "available": False,
            "reason": "未配置 EXTERNAL_SEARCH_ENDPOINT，当前仅能使用内部知识库与 live 检索资料；如需 Demo 外部情报，可设置 EXTERNAL_SEARCH_ENDPOINT=mock。",
            "items": [],
        }

    payload = json.dumps({"query": query, "limit": limit}, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    api_key = (os.getenv("EXTERNAL_SEARCH_API_KEY") or "").strip()
    if api_key:
        headers["Authorization"] = "Bearer " + api_key

    req = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return {
            "available": False,
            "reason": f"外部检索服务不可用：{e}",
            "items": [],
        }

    raw_items = data.get("items") if isinstance(data, dict) else data
    items = []
    for item in (raw_items or [])[:limit]:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or item.get("name") or "").strip()
        snippet = (item.get("snippet") or item.get("summary") or item.get("content") or "").strip()
        url = (item.get("url") or item.get("source") or "").strip()
        if title or snippet:
            items.append({
                "title": title or url or "外部检索结果",
                "snippet": snippet,
                "url": url or "external://unknown",
                "updated_at": item.get("updated_at") or item.get("date") or "时间未知",
            })
    return {"available": True, "reason": "", "items": items}
