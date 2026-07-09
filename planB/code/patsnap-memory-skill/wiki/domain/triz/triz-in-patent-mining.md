---
page_id: triz-in-patent-mining
title: TRIZ 与专利挖掘的结合应用
aliases:
  - TRIZ专利挖掘
  - TRIZ与专利分析
domain: triz
updated_at: 2026-07-08
related:
  - triz-overview
  - triz-40-principles
  - triz-contradiction-matrix
  - patsnap-engineering-agents
sources:
  - doc_id: triz-in-patent-mining
    doc_date: 2024-03-18
---

# TRIZ 与专利挖掘的结合应用

TRIZ 最初就是从专利文献中归纳出来的方法论——Altshuller 团队分析了数万份专利才提炼出40个发明原理和矛盾矩阵。这个"从专利数据反向挖掘发明模式"的思路，在专利分析工具中有两类典型落地方式。[来源: triz-in-patent-mining, 2024-03-18]

## 1. 发明原理自动标注

对一批专利的权利要求/技术方案描述做文本分析，自动判断该专利用到了 [[triz-40-principles]] 中的哪一条或哪几条，从而：

- 帮助研发人员快速浏览"某技术领域里大家常用哪些发明原理解决问题"。
- 辅助专利分类和技术趋势观察（例如"某领域近5年从原理15动态化转向原理35参数变化"）。

[来源: triz-in-patent-mining, 2024-03-18]

## 2. 技术矛盾聚类与空白点发现

把一个技术领域内的专利按"改善参数-恶化参数"聚类，对照 [[triz-contradiction-matrix]] 反推：

- 找出该领域已被大量专利覆盖的矛盾组合（红海区）。
- 找出矛盾矩阵理论上有解但该领域专利稀少的组合（潜在空白技术机会点）。

[来源: triz-in-patent-mining, 2024-03-18]

## 与产品能力的关系

这类"TRIZ+专利数据"的结合应用，是技术挖掘/创新分析类产品的典型能力方向之一，与智慧芽 [[patsnap-engineering-agents]] 提到的"root-cause/TRIZ-based ideation"方向一致。

## 边界

- 本页为方法论综述，不构成具体产品功能承诺；具体产品是否已实现某项能力，需以官方产品页/官网为准。[来源: triz-in-patent-mining, 2024-03-18]
