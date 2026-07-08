---
name: patsnap-promo
description: >-
  当需要为智慧芽产品/开源项目生成宣传材料（公众号、产品介绍、销售话术、
  活动推文、客户案例初稿）时加载。
  Load when the user wants to generate promotional/marketing content for a
  PatSnap product or open-source project. 涉及"写宣传稿、生成推文、产品介绍、
  销售话术、贴智慧芽风格、带出处的富文本初稿"时触发。风格由用户 prompt 主导。
  技术问答交给 patsnap-tech-qa；竞品对比交给 patsnap-compare。
compatibility: >-
  资料由上游检索系统召回，通过 list_materials / read_material / check_conflicts
  三个工具访问。本 skill 只管"拿到料之后怎么组织成对齐官宣风格、带来源的富文本初稿"。
version: 0.2.0
allowed-tools:
  - list_materials
  - read_material
  - check_conflicts
tags:
  - patsnap
  - content-generation
  - marketing
  - retrieval-augmented
---

# 芽懂 · 宣传材料生成

选题 + 一句 prompt + 已召回资料 → 出**富文本初稿 + 来源列表 + 待核实项**。生成端刻意做薄：风格与文体由用户 prompt 控制、不写死模板；但守住"可信、贴官宣、带来源"三条底线。

## Goal

从已召回资料里挑出项目能力/技术亮点（带来源）+ 注入历史官宣风格样本 + 用户 prompt → 生成对齐智慧芽表达的富文本，事实点绑来源、无来源标"待核实"。

## Load When

- 用户要为某产品/开源项目写宣传材料（公众号/产品介绍/话术/推文/案例）。
- 用户给了选题和写作 prompt。
- 不在范围：技术问答（patsnap-tech-qa）、竞品对比（patsnap-compare）。

## Inputs

| 名称 | 必填 | 说明 |
|---|---|---|
| 选题 | 是 | 写哪个产品/项目、什么角度（本次 case 的 question） |
| 用户 prompt | 是 | 文体、语气、篇幅、渠道（公众号/推文/话术…） |
| 已召回资料 | 是 | 由检索系统给定，经 list_materials/read_material 访问；含产品能力料与风格样本 |

## 先读（Workflow 依赖，必读）

进入 Workflow 前**必须先读**：
1. `../SOUL.md` —— 语言人格层：术语规范（生成前强制校准命名）+ 风格底线（可信优先、贴智慧芽不贴通用 AI 腔）。恒定注入，每次都读。
2. `../references/资料使用SOP.md` —— 用料的统一规矩（看料→读料→处理多来源→附来源时效）。

## Workflow

按《资料使用 SOP》取料，再叠加"注入风格样本 + prompt 主导文体"，命名走 `../SOUL.md` 术语表：

1. **看清有哪些料**：`list_materials()`，按标题/话题/相关度分出两类——项目能力/技术亮点料，以及**风格样本**（`topic=style`，或标题含"风格/文案样本"的那份）。
2. **取能力料**：对相关的能力料调 `read_material(source)` 取正文。宣传里的产品能力、数据、卖点只来自这里，不凭记忆。
3. **取风格样本**：`read_material(source)` 读那份风格样本，作**对齐参考**——学它的语气、节奏、句式，不套死模板。
4. **处理多来源**：`check_conflicts()`。若能力话题 `has_conflict=true`，以 `primary` 为准写进正文，别把有分歧的说法当铁板卖点。
5. **结构规划**：先按用户 prompt 的文体列出稿件大纲（要点顺序 + 每段依据哪份能力料），不直接一步到位成文——大纲让生成可中途干预、也让每个卖点可追溯到料。
6. **组装生成**：按大纲用 能力料 + 风格样本 + 用户 prompt → 生成富文本。文体/语气/篇幅**由用户 prompt 决定**，风格样本只负责"像不像智慧芽"。
7. **术语校准**：对照 `../SOUL.md` 术语节统一命名，改正误用写法（如产品名全称、TRIZ 大小写等）；命名与召回资料正文冲突时以 SOUL 术语表为准；表中"待核实候选"的词标"待核实"，不当卖点硬写。
8. **附来源与待核实**：事实点绑来源；本地已召回资料没有的背景（行业语境等），标"待核实"或提示需上游补充，**不自己联网、不编造**。
9. **自检**：见 Verification。

## Output Contract

- 一篇富文本初稿（形态由用户 prompt 定：公众号/介绍/话术/推文/案例）。
- 附**事实来源列表**（每个关键事实的来源 + 更新时间，或标"时间未知"）。
- 附**待核实项清单**（无来源支撑、或需上游补充/人工确认的点）。
- 风格贴合历史官宣样本，但不套死模板。

## Verification

```bash
python3 ../scripts/check_sources.py <生成稿文件或文本>
```
- 关键事实有来源；
- 带更新时间或"时间未知"标注；
- 无来源的都进了"待核实"，未凭空捏造数据/功能。

## Boundaries

- **事实不编造**：产品能力/数据必须有已召回资料支撑，否则标"待核实"，不脑补卖点。
- **风格不写死**：文体由用户 prompt 主导，风格样本只作对齐参考，不套固定模板。
- **不凭记忆**：卖点不用模型自带"常识"替代资料——它可能过时或不合智慧芽私域口径。
- **本地没有就不硬补**：资料里缺的背景标"待核实"或提示上游补充，不自己联网、不编造。
- 生成的是**初稿**，需人复核，尤其待核实项。

## Runtime Resources

- `../SOUL.md` —— 语言人格层：术语规范 + 风格底线（必读，恒定注入）。
- `../references/资料使用SOP.md` —— 用料统一规矩（必读）。
- `../scripts/check_sources.py` —— 产物校验（来源/待核实）。
