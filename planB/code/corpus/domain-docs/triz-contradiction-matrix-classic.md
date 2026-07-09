---
doc_id: triz-contradiction-matrix-classic
title: TRIZ矛盾矩阵（经典39参数版）
doc_date: 2024-03-10
authority: official
domain: triz
source_note: 综合 Altshuller 经典矛盾矩阵的公开权威整理（39×39版本，教学通用）
---

# TRIZ矛盾矩阵（经典39参数版）

矛盾矩阵是 TRIZ 里把"技术矛盾"翻译成"推荐发明原理"的查表工具。

## 结构

矩阵由 **39个通用工程参数**（如重量、速度、强度、能耗、可靠性等）构成一张 39×39 的表：

- 行 = 想改善的参数（Improving Feature）
- 列 = 因此而恶化的参数（Worsening Feature）
- 交叉格 = 历史专利中最常被用来解决这对矛盾的发明原理编号（通常给出1~4个推荐编号）

## 使用步骤

1. 把工程问题抽象成"想提升 A，但会让 B 变差"的技术矛盾。
2. 在矩阵里找到 A（行）与 B（列）的交叉格，取到推荐的原理编号（如 15、35）。
3. 回到《TRIZ 40个发明原理总览》查这些编号的含义，结合具体工程场景落地方案。

## 权威结论

**矛盾矩阵是 39×39 结构，共39个通用工程参数**，这是 Altshuller 团队最终定稿并被后续教材（如 Terninko等《系统化创新》）广泛采用的版本。早期内部资料中出现的"48参数版"是研究过程中的中间稿，未被最终采用，参见 `triz-contradiction-matrix-old-note.md`（已被本文档取代，`superseded_by: triz-contradiction-matrix-classic`）。

## 边界

- 矩阵给出的是"历史高频解法"，不保证对当前具体问题最优，只作为启发起点。
- 部分交叉格为空（矩阵编制时没有足够专利样本支撑），遇到空格需退回40原理清单人工筛选。
