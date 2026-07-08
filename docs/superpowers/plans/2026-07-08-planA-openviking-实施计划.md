# Plan A · 智慧芽技术知识助手（生成侧）实施计划

> **范围变更（2026-07-08）**：检索（向量库召回）由另一位同学负责，产出「已召回资料的 markdown 文件夹」。
> 我方**只做生成侧**：拿「原始问题 + 已召回资料」生成产物（技术问答/竞品分析/宣传材料）。
> **OpenViking / 建库 / 检索编排全部不做**。本文件已按新范围重写；旧的 16 任务 OpenViking 版见 git 历史。

**Goal:** 面向智慧芽运营/销售，做一个「技术知识助手」的生成侧 Demo——输入是检索系统召回好的资料（markdown + 元信息），输出是带来源、口径统一、不编造的产物。用样例资料把「加载资料 → 冲突裁决 → skill 驱动生成 → 前端展示」全链路跑通，真实检索输出到位后只需写一个格式适配器。

**Architecture:**
```
用户问题 + 已召回资料(case 文件夹)
        │
        ▼
  loader.py  ── 解析 frontmatter → Material(source/updated_at/authority/topic/score/body)
        │
        ▼
  conflict.py ── 同 topic 多来源：权威+时效裁决，选主答案 + 曝光另一说法
        │
        ▼
  case_tools.py ── 把资料暴露为 Agent 工具：list_materials / read_material / check_conflicts
        │
        ▼
  agent_runtime.py ── 真实 Agent 加载 SKILL.md，用工具挑料/裁决/组织生成
        │
        ▼
  server.py(http.server) ── mode→skill，密钥后端代理，降级档
        │
        ▼
  web/index.html ── 三能力入口，渲染答案+来源+时效+冲突提示+对比表
```

**Tech Stack:** 系统 Python 3.9.6（零第三方依赖：标准库 urllib + http.server + unittest，与内部环境一致）；内部 LLM 端点 `llm-api.patsnap.info`（gpt-5.5，OpenAI 兼容，function calling）；原生 HTML/JS 前端。

## Global Constraints

- **零第三方依赖**：不引入 fastapi/pyyaml/openai/pytest。frontmatter 手写解析，后端用 http.server，测试用 unittest。理由：与内部受限环境一致，随处可跑。
- **不做检索**：资料是上游给定的。本方案不判断「去哪找料、找得全不全」——那是检索侧职责。生成侧只对给定资料负责。
- **密钥不落前端**：LLM key 只在 `backend/.env`（已 gitignore，确认未追踪）。前端只调本后端。
- **格式契约驱动**：样例资料按「理想输入格式」造（见 `sample_retrieval/README-契约.md`），同时作为对检索侧的接口诉求。真实输出缺字段时在 loader 降级，核心逻辑不动。
- **不编造 / 溯源 / 曝光冲突**：三条产物底线，由 SKILL.md 约束 + `check_sources.py` 机械校验兜底。
- **降级档**：LLM 链路失败时后端回退 `fallback.json`，Demo 不翻车。
- **工作目录**：全部产出在 `planA/code/`。
- **提交规范**：每个任务末尾提交，`feat/refactor/test/docs(planA): ...`。

## 文件结构（现状，均已落地）

```
planA/code/
├── sample_retrieval/                    # 样例「已召回资料」+ 格式契约
│   ├── README-契约.md                   # ← 给检索侧的接口诉求
│   ├── case-eureka-lang/                # 冲突case：官网12种 vs 旧笔记9种
│   ├── case-compare-lang/               # 竞品对比case
│   └── case-promo-search/               # 宣传case（含风格样本）
├── backend/
│   ├── .env                             # LLM端点(不提交)
│   ├── llm_client.py                    # urllib直连内部端点，支持function calling
│   ├── loader.py                        # frontmatter解析→Material，话题分组，缺字段降级
│   ├── conflict.py                      # 权威+时效裁决，曝光而非静默覆盖
│   ├── case_tools.py                    # Agent工具：list/read/check_conflicts
│   ├── agent_runtime.py                 # 加载SKILL.md+case，跑function-calling循环
│   ├── server.py                        # http.server：/api/chat /api/cases，降级
│   ├── fallback.json                    # 三模式降级预置结果
│   ├── run_all.py                       # 三case端到端冒烟+来源校验
│   └── tests/                           # unittest：loader/conflict/case_tools/server
├── skills/
│   ├── references/资料使用SOP.md         # 共享用料规矩（四步）
│   ├── scripts/check_sources.py         # 产物校验（来源+时效）
│   ├── patsnap-tech-qa/SKILL.md         # 技术问答（统一口径）
│   ├── patsnap-compare/                 # 竞品对比（+references/对比维度与维度对齐.md）
│   └── patsnap-promo/SKILL.md           # 宣传生成
└── web/
    └── index.html                       # 对话网页Demo
```

**测试策略**：loader/conflict/case_tools/server 的纯逻辑用 unittest 离线测（16+条，全绿）；Agent 端到端跑真 LLM 的验证在 `run_all.py`（三 case 全通过，来源校验全通过）。

---

## 任务与状态

| # | 任务 | 状态 |
|---|---|---|
| 7 | 样例检索资料文件夹 + 格式契约 | ✅ 完成 |
| 8 | 资料加载解析层 loader.py（TDD，6测试） | ✅ 完成 |
| 9 | 冲突裁决层 conflict.py（TDD，5测试） | ✅ 完成 |
| 10 | Agent运行时脱离OpenViking，case_tools（TDD，5测试） | ✅ 完成 |
| 11 | 三个生成SKILL.md（问答/竞品/宣传）+ 删建库skill | ✅ 完成 |
| 12 | 后端服务 server.py（TDD，5测试）+ 降级档 | ✅ 完成 |
| 13 | 对话网页前端 | ✅ 完成 |
| 14 | 重写plan文档反映新范围 | ✅ 完成（本文件） |

**端到端验证结论**（`run_all.py`，真 gpt-5.5）：
- 技术问答：正确执行「list→read→check_conflicts」四步，主答案选 L1 官网(12种)，**主动曝光** L4 旧笔记(9种)并说明为何以官方为准。来源校验通过。
- 竞品对比：查询分解 + 按维度对齐成表，每格带来源+时效，标注「本次无冲突」。来源校验通过。
- 宣传生成：基于能力料+风格样本生成初稿，附来源列表+待核实项。来源校验通过。

---

## 后续（真实检索输出到位后）

1. **写格式适配器**：把检索侧的真实 markdown 输出转成 `sample_retrieval` 的 case 格式（frontmatter）。缺 `authority/topic` 时 loader 已降级；若结构差异大，只改适配器，不改 loader/conflict/agent。
2. **对齐契约**：拿 `README-契约.md` 跟检索侧确认能否附带 `source/updated_at/authority/topic`——这是「溯源 + 冲突曝光」卖点的输入前提。
3. **评估评测集**（可选）：对生成产物做质量评测（来源覆盖率、冲突曝光率、无编造率），复用 `check_sources.py` 的信号。

## 遗留清理项

- `server.py` 绑 `0.0.0.0` 且无鉴权——本地 Demo 可接受，若对外暴露需加访问控制。已在此备注。
- compare 的 reference 文件已从「实时抓取」更名为「对比维度与维度对齐」，内容不再涉及抓网页。
