"""
Case 工具 —— Agent 通过这些工具访问"检索侧已召回的资料"。

新架构下，检索由另一位同学完成，资料已 markdown 化放进 case 文件夹。
所以 Agent 不再"自己检索"，它的工具是"读已给定的料 + 看冲突裁决"：
  - list_materials()          列出本 case 所有资料的元信息（不含正文，省 token）
  - read_material(source)     读某份资料全文
  - check_conflicts()         按 topic 分组做权威+时效裁决，返回主答案与曝光提示

这样 Agent 的职责纯化为：理解问题 → 挑料 → 处理冲突 → 组织生成，全程不编造。
"""
from loader import group_by_topic
from conflict import adjudicate


class CaseTools:
    def __init__(self, case):
        self.case = case
        self._by_source = {m.source: m for m in case.materials}

    # ---- 工具实现 ----
    def list_materials(self):
        return {"materials": [
            {"source": m.source, "title": m.title, "authority": m.authority,
             "updated_at": m.updated_at, "topic": m.topic, "score": m.score}
            for m in self.case.materials
        ]}

    def read_material(self, source):
        m = self._by_source.get(source)
        if m is None:
            return {"error": f"未找到来源 {source}",
                    "available": list(self._by_source.keys())}
        return {"source": m.source, "title": m.title, "authority": m.authority,
                "updated_at": m.updated_at, "topic": m.topic, "body": m.body}

    def check_conflicts(self):
        topics = []
        for topic, mats in group_by_topic(self.case.materials).items():
            v = adjudicate(mats)
            topics.append({
                "topic": topic,
                "has_conflict": v.has_conflict,
                "primary": {"source": v.primary.source, "title": v.primary.title,
                            "authority": v.primary.authority, "updated_at": v.primary.updated_at},
                "others": [{"source": o.source, "authority": o.authority,
                            "updated_at": o.updated_at} for o in v.others],
                "conflict_note": v.conflict_note(),
            })
        return {"topics": topics}

    # ---- 调度表：供 Agent 运行时按工具名调用 ----
    def impl(self):
        return {
            "list_materials": self.list_materials,
            "read_material": self.read_material,
            "check_conflicts": self.check_conflicts,
        }


# ---- function-calling schema（供 agent_runtime 注册给 LLM）----
TOOLS = [
    {"type": "function", "function": {
        "name": "list_materials",
        "description": "列出本次检索已召回的所有资料的元信息（来源、标题、权威级、更新时间、话题、相关度），不含正文。先调它了解有哪些料。",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "read_material",
        "description": "按来源(source)读取某份资料的完整正文。事实必须来自这里，不得凭记忆编造。",
        "parameters": {"type": "object", "properties": {
            "source": {"type": "string", "description": "资料的 source 字段（来源 URI/URL）"},
        }, "required": ["source"]}}},
    {"type": "function", "function": {
        "name": "check_conflicts",
        "description": "按话题(topic)分组检测同话题多来源，并做权威+时效裁决。返回每个话题的主答案与'另有资料表述不同'的曝光提示。组织答案前应调它，避免口径分裂。",
        "parameters": {"type": "object", "properties": {}}}},
]
