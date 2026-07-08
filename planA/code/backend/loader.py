"""
资料加载与解析层 —— 读检索侧产出的 case 文件夹，解析成结构化 Material。

零第三方依赖（本环境无 pyyaml），手写一个极简 frontmatter 解析器，
只支持 `key: value` 单层键值（契约里的字段都是单层），够用且不引依赖。

输入格式见 sample_retrieval/README-契约.md：
  case 文件夹 = question.txt + 若干带 frontmatter 的 md 资料。
"""
import os
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
            materials.append(parse_material(f.read(), filename=name))
    # score 降序；score 都为 0 时保持文件名顺序（sorted 已按名，稳定排序保序）
    materials.sort(key=lambda m: m.score, reverse=True)
    return Case(question=question, materials=materials)


def group_by_topic(materials: list) -> dict:
    """按 topic 分组。同一 topic 下多份 = 同话题多来源（可能冲突，交给 conflict 裁决）。"""
    groups: dict = {}
    for m in materials:
        groups.setdefault(m.topic, []).append(m)
    return groups
