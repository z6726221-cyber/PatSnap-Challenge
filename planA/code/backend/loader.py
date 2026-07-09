"""
资料加载与解析层 —— 读检索侧产出的 case 文件夹，解析成结构化 Material。

零第三方依赖（本环境无 pyyaml），手写一个极简 frontmatter 解析器，
只支持 `key: value` 单层键值（契约里的字段都是单层），够用且不引依赖。

输入支持两种格式（见 sample_retrieval/README-契约.md）：
  1. 理想格式：带 YAML frontmatter 的单条资料 md（每个文件 = 一条 Material）。
  2. OpenViking 原始检索包：一次检索的完整返回（含"命中资源明细"小节），
     一个文件里塞了多条命中，每条自带 URI 但没有 frontmatter。
     按"命中资源明细"小节拆成多条 Material；拆不出来（小节不存在）时
     退回格式 1 的整文件单条解析，不报错、不丢数据。
"""
import os
import re
from dataclasses import dataclass, field


@dataclass
class Material:
    source: str          # 来源 URI/URL，缺失 → ""（标"来源未知"）
    updated_at: str      # 更新日期，缺失 → ""（标"时间未知"）
    authority: str       # 权威级 L1-L4，缺失 → "L4"（宁可低估）
    topic: str           # 话题标识，缺失 → 文件名
    score: float         # 检索相关度，缺失 → 0.0
    title: str           # 标题，缺失 → 文件名
    body: str            # 正文（frontmatter 之后的部分）


@dataclass
class Case:
    question: str
    materials: list = field(default_factory=list)


def _parse_frontmatter(text: str):
    """返回 (meta: dict, body: str)。无 frontmatter 时 meta={}，body=全文。"""
    if not text.startswith("---"):
        return {}, text
    # 找第二个 --- 分隔行
    lines = text.splitlines()
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    meta = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip()
    body = "\n".join(lines[end + 1:]).strip()
    return meta, body


def parse_material(text: str, filename: str) -> Material:
    meta, body = _parse_frontmatter(text)
    try:
        score = float(meta.get("score", "") or 0.0)
    except ValueError:
        score = 0.0
    return Material(
        source=meta.get("source", ""),
        updated_at=meta.get("updated_at", ""),
        authority=meta.get("authority", "") or "L4",
        topic=meta.get("topic", "") or filename,
        score=score,
        title=meta.get("title", "") or filename,
        body=body,
    )


# ---- OpenViking 原始检索包解析 ----
# 检索包格式：一个 "## 命中资源明细" 小节下，若干 "### N. <URI>" 条目，
# 每条带 "- URI：`...`"、"- 关键词匹配分：NN"，正文在 "摘要/片段：" 和/或
# "全文内容：" 之后。条目头必须是"数字. URI"且独占一行 —— 这个约束是为了不
# 误把正文里的普通小标题（如 "### 7.1 Triton serving 产线切换"）当成新条目
# 切分点：真实文档小标题后面接的是标题文字不是 URI，不会匹配。
_ENTRY_HEADER_RE = re.compile(
    r"^###\s*\d+\.\s+((?:viking|https?)://\S+)\s*$", re.MULTILINE
)


def _extract_hit_section(text: str):
    """取"## 命中资源明细"小节的正文，到"## 原始工具返回"为止（找不到就到文件尾）。

    不能用"下一个 `## ` 开头的行"当结束标记：命中条目的正文本身可能是被召回
    文档的原文片段，其中就带 "## 7. 主线四..." 这类二级标题，会被误判成小节
    结束点导致提前截断。"## 原始工具返回" 是 OpenViking 报告模板固定的下一个
    顶层小节，用它锚定更可靠。
    """
    m = re.search(r"^##\s*命中资源明细\s*$", text, re.MULTILINE)
    if m is None:
        return None
    start = m.end()
    m2 = re.search(r"^##\s*原始工具返回\s*$", text[start:], re.MULTILINE)
    end = start + m2.start() if m2 else len(text)
    return text[start:end]


def _extract_hit_body(block: str) -> str:
    """条目块内取正文：优先"全文内容"；没有则退回"摘要/片段"并标注可能被截断。"""
    full = re.search(r"全文内容[：:]\s*\n+(.*)", block, re.DOTALL)
    if full:
        return full.group(1).strip()
    abstract = re.search(r"摘要/片段[：:]\s*\n+(.*?)(?=\n全文内容[：:]|\Z)", block, re.DOTALL)
    if abstract:
        body = abstract.group(1).strip()
        if "truncated for embedding" in body:
            body += "\n\n[注：本条资料仅为检索摘要片段，可能被截断，非全文]"
        return body
    return block.strip()


def _parse_hit_entries(section_text: str, filename: str) -> list:
    """把"命中资源明细"小节拆成多条 Material。"""
    headers = list(_ENTRY_HEADER_RE.finditer(section_text))
    materials = []
    for i, h in enumerate(headers):
        block_start = h.end()
        block_end = headers[i + 1].start() if i + 1 < len(headers) else len(section_text)
        block = section_text[block_start:block_end]

        uri_line = re.search(r"URI[：:]\s*`([^`]+)`", block)
        source = uri_line.group(1).strip() if uri_line else h.group(1).strip()

        score_line = re.search(r"关键词匹配分[：:]\s*([0-9.]+)", block)
        try:
            score = float(score_line.group(1)) if score_line else 0.0
        except ValueError:
            score = 0.0

        # 检索包不带 authority/topic 元信息：authority 按契约降级取 L4；
        # topic 用 source 本身（每条命中是独立文档，不强行按文件名归并成同话题）。
        materials.append(Material(
            source=source,
            updated_at="",
            authority="L4",
            topic=source or filename,
            score=score,
            title=source.rsplit("/", 1)[-1] if source else filename,
            body=_extract_hit_body(block),
        ))
    return materials


def parse_materials_from_file(text: str, filename: str) -> list:
    """解析一个 md 文件为若干 Material。

    优先识别 OpenViking 原始检索包格式（"命中资源明细"小节），按命中条目
    拆成多条；识别不到该小节时，退回契约理想格式（单文件单条 frontmatter）。
    """
    section = _extract_hit_section(text)
    if section:
        entries = _parse_hit_entries(section, filename)
        if entries:
            return entries
    return [parse_material(text, filename)]


def load_case(case_dir: str) -> Case:
    """读一个 case 文件夹：question.txt 必需；md 资料按 score 降序（score 相同按文件名）。"""
    q_path = os.path.join(case_dir, "question.txt")
    if not os.path.exists(q_path):
        raise FileNotFoundError(f"缺少 question.txt: {case_dir}")
    with open(q_path, encoding="utf-8") as f:
        question = f.read().strip()

    materials = []
    for name in sorted(os.listdir(case_dir)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(case_dir, name), encoding="utf-8") as f:
            materials.extend(parse_materials_from_file(f.read(), filename=name))
    # score 降序；score 都为 0 时保持文件名顺序（sorted 已按名，稳定排序保序）
    materials.sort(key=lambda m: m.score, reverse=True)
    return Case(question=question, materials=materials)


def group_by_topic(materials: list) -> dict:
    """按 topic 分组。同一 topic 下多份 = 同话题多来源（可能冲突，交给 conflict 裁决）。"""
    groups: dict = {}
    for m in materials:
        groups.setdefault(m.topic, []).append(m)
    return groups
