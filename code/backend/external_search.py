"""
外部情报检索适配层。

当前仓库不能内置真实搜索供应商 key，所以这里做成可插拔适配器：
- 配置 EXTERNAL_SEARCH_ENDPOINT 后，后端会把 query POST 给该服务并接收统一 items。
- 未配置时明确返回 unavailable，调用方会把"需要外部检索补充"写进材料，而不是假装已经联网。
"""
import json
import os
import urllib.error
import urllib.request


def search_external_intel(query: str, limit: int = 5) -> dict:
    endpoint = (os.getenv("EXTERNAL_SEARCH_ENDPOINT") or "").strip()
    if not endpoint:
        return {
            "available": False,
            "reason": "未配置 EXTERNAL_SEARCH_ENDPOINT，当前仅能使用内部知识库与 live 检索资料。",
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
