---
name: patsnap-compare
description: >-
  当需要把智慧芽产品能力与一个或多个竞品做横向对比时加载。
  Load when the user wants to compare a PatSnap product/capability against
  competitor(s). 涉及"我们 vs 竞品、强在哪、对比表、竞品分析"时触发。
  单对象问答（不涉及竞品）交给 patsnap-tech-qa；写宣传稿交给 patsnap-promo。
compatibility: >-
  资料由上游检索系统召回（含我方产品料与竞品料），通过 list_materials /
  read_material / check_conflicts 三个工具访问。本 skill 只管"拿到料之后
  怎么按维度对齐成一张可溯源的对比表"，不自己检索、不自己抓网页。
version: 0.2.0
allowed-tools:
  - list_materials
  - read_material
  - check_conflicts
tags:
  - patsnap
  - competitor
  - comparison
  - retrieval-augmented
---

# 芽懂 · 竞品对比

把"我们比竞品强在哪"变成一张**按维度对齐、每格带来源与时效**的对比表。这是区别于普通聊天机器人的差异化能力。核心是查询分解 + 我方/竞品分别用料 + 维度对齐——不能把两边的料混在一起答。

## Goal

对比问题 + 已召回资料 → 拆成{维度/我方/竞品/时间} → 从已召回料里区分我方料与竞品料 → 逐维度对齐成对比表 → 缺失标"未找到"、同话题多来源曝光分歧，每格可溯源。

## Load When

- 用户要把某产品/能力与一个或多个竞品横向对比。
- 用户要系统说清我方相对竞品的优势。
- 不在范围：单对象问答（patsnap-tech-qa）、宣传写作（patsnap-promo）。

## Inputs

| 名称 | 必填 | 说明 |
|---|---|---|
| 对比问题 | 是 | 含我方对象、竞品对象（可从问题推断）（本次 case 的 question） |
| 已召回资料 | 是 | 由检索系统给定，含我方产品料与竞品料，经 list_materials/read_material 访问 |
| 对比维度 | 否 | 用户没指定则按能力维度补默认 |

## 先读（Workflow 依赖，必读）

进入 Workflow 前**必须先读**，否则不得继续：
1. `../SOUL.md` —— 语言人格层：术语规范（对齐对比表命名，我方/竞品术语都走标准叫法）+ 风格底线。恒定注入，每次都读。
2. `references/对比维度与维度对齐.md` —— 查询分解、我方/竞品分料、维度对齐、资料不足如何标注的完整规矩。
3. `../references/资料使用SOP.md` —— 用料的统一规矩（看料→读料→处理多来源→附来源时效）。

## Workflow

严格按《资料使用 SOP》+《对比维度与维度对齐》执行：

1. **查询分解**：把口语对比问题转成 {is_comparison, dimensions, our_target, competitors, time_intent}（见 references）。用户没说全维度时按能力维度补默认。
2. **看清有哪些料**：`list_materials()`，按标题/话题/来源/相关度判断哪些是我方料、哪些是竞品料。
   - **我方料**：`source` 含 `products/`（或 `topic` 指向我方对象）。
   - **竞品料**：`source` 含 `competitors/`（或 `topic` 指向竞品对象）。
3. **分别读料**：对相关的我方料、竞品料分别调 `read_material(source)` 取正文。事实只来自这里，不凭记忆。
4. **处理同话题多来源**：`check_conflicts()`。若某话题（比如我方产品有新旧两版语言数）`has_conflict=true`，以 `primary` 为主答案，并把 `conflict_note` 附进对应格子（曝光另一说法+来源+时效）。
5. **维度对齐**：逐维度把我方与竞品摆到同一行成表；某边该维度没料就标"未找到"，不猜。
6. **术语校准**：对照 `../SOUL.md` 术语节统一命名——我方产品名（如 Patsnap Eureka / Engineering Agents）、技术术语（语义检索 / 混合检索等）都走标准叫法；命名与召回资料正文冲突时以 SOUL 术语表为准；竞品专名按其官方来源写，拿不准标"待核实"。
7. **标注**：每格附来源 `source` + `updated_at`（缺则标"时间未知"）；竞品维度资料不足时标"未在已召回资料中找到该竞品的X维度信息"。
8. **自检**：见 Verification。

## Output Contract

- 一张按维度对齐的对比表，每格带来源与时间。
- 缺失维度明确标"未找到"，不脑补。
- 某竞品维度在已召回料里没有 → 标"未在已召回资料中找到该竞品的X维度信息"，并提示这需要上游检索补充，不自己去找。
- 同话题多来源分歧的格子，主答案之外附另一说法及其来源/时间。
- 对比表必须用标准 markdown 语法（`| 列 | 列 |` + 分隔行 `| --- | --- |`），不用空格/换行手工排版——前端按标准语法渲染表格，格式不对会整段显示成乱码。

## Verification

```bash
python3 ../scripts/check_sources.py <对比表文件或文本>
```
- 每格有来源；
- 有更新时间或"时间未知"标注；
- 缺失项标了"未找到"，无来源支撑的话标"待核实"。

## Boundaries

- **不编造**：资料里没有就标"未找到"/"待核实"，绝不脑补。
- **不凭记忆**：不用模型自带的"常识"替代资料——它可能过时或不合智慧芽私域口径。
- **不混料**：我方料、竞品料要分开取、按维度对齐；两边混在一起答会偏。
- **缺失不猜**：某维度没料就标"未找到"；竞品料不足属于检索侧的补料诉求，不由本 skill 自己抓网页。
- **口径以权威版为准**：同话题多来源冲突时，按权威性+时效裁决并标注，不静默覆盖。
- 不抄知识进 skill。

## Runtime Resources

- `../SOUL.md` —— 语言人格层：术语规范 + 风格底线（必读，恒定注入）。
- `references/对比维度与维度对齐.md` —— 分解/分料/对齐/资料不足处理（必读）。
- `../references/资料使用SOP.md` —— 用料统一规矩（必读）。
- `../scripts/check_sources.py` —— 产物校验（来源+时效+缺失标注）。
