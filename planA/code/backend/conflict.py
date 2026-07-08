"""
冲突裁决层 —— 同话题多来源时，决定"信哪个" + "另一个怎么曝光"。

两层机制（对齐方案 §7之二）：
  ① 权威性 + 时效裁决："谁当主答案"——先按权威级(L1>L2>L3>L4)，同级按更新时间(新的赢)。
  ② 曝光而非静默覆盖："输家怎么处理"——不删不藏，回答里附一句"另有资料表述不同…"。

不做"两句话语义上矛不矛盾"的自动判断（业界未解决，方案明确不硬碰）——
只要同话题有多份来源，就排出主答案并把其余如实曝光。
"""
from dataclasses import dataclass, field


def _authority_rank(authority: str) -> int:
    """L1 最高。返回值越大越权威。未知格式按最低。"""
    a = (authority or "").upper().strip()
    mapping = {"L1": 4, "L2": 3, "L3": 2, "L4": 1}
    return mapping.get(a, 0)


def _time_key(updated_at: str) -> str:
    """无时间排在有时间之后：空串映射为最小值。"""
    return updated_at or ""


@dataclass
class ConflictVerdict:
    primary: object                      # 选为主答案的 Material
    others: list = field(default_factory=list)   # 未选中但要曝光的 Material 列表
    has_conflict: bool = False

    def conflict_note(self) -> str:
        """曝光提示：把未选中的来源与时效如实列出。无冲突返回空串。"""
        if not self.has_conflict or not self.others:
            return ""
        parts = [
            f"另有资料表述不同：{o.source or '来源未知'}"
            f"（更新于 {o.updated_at or '时间未知'}，权威级 {o.authority}）"
            for o in self.others
        ]
        return "；".join(parts) + "。当前以更权威/更新的来源为准。"


def adjudicate(materials: list) -> ConflictVerdict:
    """对同话题的一组 Material 裁决。传入应为同 topic 的资料（由 group_by_topic 分好）。"""
    ranked = sorted(
        materials,
        key=lambda m: (_authority_rank(m.authority), _time_key(m.updated_at)),
        reverse=True,
    )
    primary = ranked[0]
    others = ranked[1:]
    return ConflictVerdict(primary=primary, others=others,
                           has_conflict=len(materials) > 1)
