---
page_id: triz-contradiction-matrix
title: TRIZ 矛盾矩阵
aliases:
  - 矛盾矩阵
  - contradiction matrix
  - 矛盾矩阵有几个参数
domain: triz
updated_at: 2026-07-08
related:
  - triz-overview
  - triz-40-principles
  - triz-in-patent-mining
sources:
  - doc_id: triz-contradiction-matrix-classic
    doc_date: 2024-03-10
    authority: official
  - doc_id: triz-contradiction-matrix-old-note
    doc_date: 2021-06-01
    authority: internal_note
    superseded_by: triz-contradiction-matrix-classic
---

# TRIZ 矛盾矩阵

矛盾矩阵是 TRIZ 里把"技术矛盾"翻译成"推荐发明原理"的查表工具。[来源: triz-contradiction-matrix-classic, 2024-03-10]

## 结构（权威结论）

矩阵由 **39个通用工程参数**（如重量、速度、强度、能耗、可靠性等）构成一张 **39×39** 的表：行是想改善的参数，列是因此恶化的参数，交叉格给出历史专利中最常用来解决这对矛盾的发明原理编号（通常1~4个）。[来源: triz-contradiction-matrix-classic, 2024-03-10]

这是 Altshuller 团队最终定稿、被后续教材广泛采用的版本。

## ⚠️ 版本冲突提示

存在一份更早的内部培训笔记（2021-06-01）记录为"48个参数、48×48矩阵"，与上述官方权威版本（39参数，2024-03-10整理）不一致。经核对：

- **权威性**：官方权威版标注 `authority: official`，内部笔记标注 `authority: internal_note`，按权威性应以官方版为准。
- **时效性**：官方权威版整理时间（2024-03-10）晚于内部笔记（2021-06-01）。
- **裁决结论**：**采用39参数版为准确结论**；48参数说法疑似把"48个改善方向候选"和"39个参数"两个概念搞混，未能找到可验证的原始出处。

裁决过程记录见 [[error-book]]。原始冲突文档见 raw/ 层的 `triz-contradiction-matrix-old-note.md`（已标注 `superseded_by: triz-contradiction-matrix-classic`，不作为当前结论使用）。

## 使用步骤

1. 把工程问题抽象成"想提升A，但会让B变差"的技术矛盾。
2. 在矩阵中找到A（行）与B（列）的交叉格，取推荐的原理编号。
3. 回到 [[triz-40-principles]] 查这些编号的含义，结合具体场景落地方案。

[来源: triz-contradiction-matrix-classic, 2024-03-10]

## 边界

- 矩阵给出的是"历史高频解法"，不保证对当前具体问题最优，只作为启发起点。
- 部分交叉格为空（专利样本不足），遇到空格需退回40原理清单人工筛选。

[来源: triz-contradiction-matrix-classic, 2024-03-10]
