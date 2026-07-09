---
updated_at: 2026-07-08
---

# 术语表（SOUL）

统一口径用的关键术语表。每条标注**核实来源**——不凭印象编，凭真实抓取/公开权威资料核对后落笔。

| 术语 | 定义 | 核实来源 |
|---|---|---|
| TRIZ | 苏联发明家 Genrich Altshuller 及团队从1946年起系统整理的发明问题解决方法论，俄语缩写，中文常译"发明问题解决理论"或"萃智" | corpus/domain-docs/triz-40-principles.md（公开权威教材通用定义整理），2024-03-10 |
| 矛盾矩阵（Contradiction Matrix） | TRIZ 中把"技术矛盾"（提升A会让B变差）映射到推荐发明原理的39×39查表工具 | corpus/domain-docs/triz-contradiction-matrix-classic.md，2024-03-10；⚠️存在过期冲突版本记为48参数，已裁决取代，见 [[error-book]] |
| 40个发明原理 | 从数万份专利归纳出的通用创新解决方向清单，编号1-40 | corpus/domain-docs/triz-40-principles.md，2024-03-10 |
| 理想最终结果（IFR） | TRIZ 中"如果没有任何限制，功能理想情况下应该怎么实现"的目标导向思维工具 | corpus/domain-docs/triz-ideal-final-result.md，2024-03-12 |
| 物场分析（Su-Field Analysis） | 把技术系统抽象为 S1（对象）/S2（工具）/F（场）三元结构的问题建模工具 | corpus/domain-docs/triz-su-field-analysis.md，2024-03-15 |
| Engineering Agents（工程智能体） | 智慧芽 Patsnap Eureka 平台下面向研发问题求解的 AI Agent 产品线，含 Functional Analysis 和 Root-cause/TRIZ-based Ideation 两个能力方向 | WebFetch 核实 https://www.patsnap.com，2026-07-08 |
| Root-cause / TRIZ-based Ideation | 智慧芽官网对 Engineering Agents 能力的原文表述，指"结合根因分析方法与TRIZ方法论辅助工程师产出创新解决方向" | WebFetch 核实 https://www.patsnap.com，2026-07-08 |
| Patsnap Eureka | 智慧芽的 AI Agent 核心平台，官网将 IP Search / IP Drafting / Engineering / Life Sciences / Materials 等 Agent 归入此平台名下 | WebFetch 核实 https://www.patsnap.com，2026-07-08 |
| PatentSight+ | LexisNexis 旗下 IP 分析平台，面向专利组合估值、竞争情报和战略决策 | WebFetch 核实 https://www.lexisnexisip.com/solutions/ip-analytics-and-intelligence/patentsight/，2026-07-08 |
| Protégé | PatentSight+ 的核心 AI 助手功能，支持自然语言提问、结构化分析、可追溯推理步骤 | WebFetch 核实 https://www.lexisnexisip.com/solutions/ip-analytics-and-intelligence/patentsight/，2026-07-08 |
| Patent Asset Index | PatentSight+ 官网宣称的"全球技术实力和影响力的客观衡量指标"专有指数 | WebFetch 核实 https://www.lexisnexisip.com/solutions/ip-analytics-and-intelligence/patentsight/，2026-07-08（专有指数的计算方法未公开，标"待核实"） |
| OpenViking | 火山引擎（volcengine）开源的"面向 AI Agent 的上下文数据库"，采用文件系统范式统一管理记忆/资源/技能 | 摘录整理自 OpenViking-main/README.md（volcengine/OpenViking 官方仓库），2026-05-01 |

## 术语使用规则

- 同一术语在不同产物（技术问答/竞品对比）中必须使用本表定义，不允许各生成流程各自造词。
- 表中术语若与 Wiki 页面正文冲突，以本表为准，并回查对应 Wiki 页面更新版本冲突记录。
- 新增术语必须先核实（WebFetch 官网 / 权威公开资料）才能入表，未核实的候选术语先记入 [[error-book]] 待办区，不直接入表。
