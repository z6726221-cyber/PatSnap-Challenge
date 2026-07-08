---
name: patsnap-tech-qa
description: >-
  当运营/销售/市场用大白话问智慧芽技术问题（产品能力、方法论、技术口径），
  需要有来源、口径统一的标准答案时加载。
  Load when a non-technical user asks about product capabilities, methodology,
  or technical facts and needs a sourced, consistent answer. 涉及"这东西是什么/
  怎么用/比别人强在哪（单问不对比）/口径统一/带出处的技术问答"时触发。
  纯竞品横向对比交给 patsnap-compare；写宣传稿交给 patsnap-promo。
compatibility: >-
  资料由上游检索系统召回，通过 list_materials / read_material / check_conflicts
  三个工具访问。本 skill 只管"拿到料之后怎么组织成统一口径的答案"。
version: 0.2.0
allowed-tools:
  - list_materials
  - read_material
  - check_conflicts
tags:
  - patsnap
  - qa
  - retrieval-augmented
---

# 芽懂 · 技术问答（统一口径）

把运营的口语技术问题，基于**已召回的资料**，变成**有来源、有时效、口径统一**的标准答案。这是产品的头号价值——同一问题谁问都是同一个可追溯的答案。

## Goal

口语问题 + 已召回资料 → 挑出相关料 → 组织成结论清晰、每个事实绑来源、带更新时间的答案；命中同话题多来源时曝光分歧而非装懂。

## Load When

- 运营/销售/市场用大白话问技术问题（产品能力、方法论概念、技术口径）。
- 需要"带出处、经得起客户追问"的答案。
- 单一对象的"强在哪/怎么样"也算问答；**多个竞品横向对比**才交给 patsnap-compare。
- 不在范围：竞品对比（patsnap-compare）、宣传写作（patsnap-promo）。

## Inputs

| 名称 | 必填 | 说明 |
|---|---|---|
| 用户问题 | 是 | 运营的口语提问（本次 case 的 question） |
| 已召回资料 | 是 | 由检索系统给定，经 list_materials/read_material 访问 |

## 先读（Workflow 依赖，必读）

进入 Workflow 前**必须先读**：
1. `../SOUL.md` —— 语言人格层：术语规范（生成前强制校准命名）+ 风格底线。恒定注入，每次都读。
2. `../references/资料使用SOP.md` —— 用料的统一规矩（看料→读料→处理多来源→附来源时效）。

## Workflow

严格按《资料使用 SOP》执行，命名一律对照 `../SOUL.md` 术语表：

1. **看清有哪些料**：`list_materials()`，按标题/话题/相关度判断哪些与问题相关。
2. **读相关料**：对相关的调 `read_material(source)` 取正文。事实只来自这里，不凭记忆。
3. **处理多来源**：`check_conflicts()`。若相关话题 `has_conflict=true`，以 `primary` 为主答案，并把 `conflict_note` 附进回答（曝光另一说法+来源+时效）。
4. **术语校准**：对照 `../SOUL.md` 术语节统一命名，改正误用写法；命名与召回资料正文冲突时以 SOUL 术语表为准；表中列为"待核实候选"的词不当正确答案用，标"待核实"。
5. **组织答案**：先给结论、再给依据；每个事实点后附来源 + 更新时间。
6. **自检**：见 Verification。

## Output Contract

- 结论明确，不含糊。
- **每个事实性陈述都绑来源**；带更新时间，或明确标"时间未知"。
- 无资料支撑的内容标"待核实"，不编造。
- 若有同话题多来源分歧，主答案之外附另一说法及其来源/时间。

## Verification

```bash
python3 ../scripts/check_sources.py <本次答案文件或文本>
```
- 每个事实点有来源；
- 有更新时间或"时间未知"标注；
- 无来源的话都标了"待核实"。

## Boundaries

- **不编造**：资料里没有就说没有/待核实，绝不脑补。
- **不凭记忆**：不用模型自带的"常识"替代资料——它可能过时或不合智慧芽私域口径。
- **不做检索**：资料是上游给定的；本 skill 不负责去哪找料、找得全不全。
- **口径以本地权威版为准**：同话题多来源冲突时，按权威性+时效裁决并标注，不静默覆盖。
- 单对象问答不做多竞品横向拉表（那是 patsnap-compare）。

## Runtime Resources

- `../SOUL.md` —— 语言人格层：术语规范 + 风格底线（必读，恒定注入）。
- `../references/资料使用SOP.md` —— 用料统一规矩（必读）。
- `../scripts/check_sources.py` —— 产物校验（来源+时效）。
