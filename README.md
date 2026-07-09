# 芽懂 · 智慧芽私域技术知识库（Plan A）

面向**运营 / 销售 / 市场**的私域技术知识库：用大白话提问，拿到**有来源、有时效、口径统一**的技术问答、竞品对比和宣传初稿。

> 本仓库聚焦 **Plan A** 的可运行实现。产品定位、选型论证等完整方案见 [`planA/技术方案-OpenViking.md`](planA/技术方案-OpenViking.md)。

---

## 它解决什么

运营销售遇到技术问题时，问研发慢、研发讲不明白，且不同人对同一能力的说法不一致，客户面前容易露馅。这个系统的头号价值是**统一口径**——同一个问题，谁问都得到同一个可追溯的标准答案。

三条核心原则贯穿实现：

- **不编造**：所有事实都来自召回的资料，没有支撑的点标「待核实」。
- **可溯源**：每个事实性陈述绑来源 + 更新时间。
- **冲突曝光而非静默覆盖**：同话题多来源分歧时，按权威性 + 时效裁决出主答案，同时把另一说法如实曝光。

## 职责边界

**检索侧不在本仓库**——资料的召回与存储由上游检索系统负责（方案里对应 OpenViking 底座）。本仓库是**生成侧**：拿到已召回的资料后，负责「挑料 → 裁决冲突 → 组织成带来源的产物」。两侧通过一份格式契约解耦，见 [`planA/code/sample_retrieval/README-契约.md`](planA/code/sample_retrieval/README-契约.md)。

```
用户问题
  → 前端（web/index.html）
  → 编排后端（backend/）
      → 召回资料（本仓库用样例 case 模拟检索侧输出）
      → Agent 自主选 skill → 按 skill 的 SOP 读料/裁决/组织
  → 带来源的产物（问答 / 竞品对比 / 宣传初稿）
```

## 三个 Skill（能力）

能力选择**由 Agent 自主判断**，不是后端关键词路由：后端只把三个 skill 的 `name + description` 交给模型，模型先调 `select_skill` 选中场景、后端再回传该 skill 全文，之后严格照它的 Workflow / Output Contract / Boundaries 执行（渐进式披露）。

| Skill | 场景 | 产物 |
|---|---|---|
| `patsnap-tech-qa` | 单对象技术问答（能力 / 方法论 / 口径） | 结论清晰、每个事实绑来源的标准答案 |
| `patsnap-compare` | 我方 vs 一个或多个竞品 | 按维度对齐的可溯源对比表 |
| `patsnap-promo` | 宣传稿 / 推文 / 产品介绍 / 销售话术 | 贴官宣风格、带来源的富文本初稿 |

三个 skill 共享一份用料规矩 [`skills/references/资料使用SOP.md`](planA/code/skills/references/资料使用SOP.md)，并共用校验脚本 `skills/scripts/check_sources.py` 把「附来源 + 时效」从"靠 Agent 自觉"变成"脚本卡死"。

## 目录结构

```
planA/code/
├── backend/                 # 编排后端（Python 标准库，零第三方依赖）
│   ├── server.py            # http.server 服务：GET / · GET /api/cases · POST /api/chat
│   ├── agent_runtime.py     # Agent 工具调用循环 + select_skill 自主选能力
│   ├── case_tools.py        # 暴露给 Agent 的三个工具
│   ├── loader.py            # 读 case 文件夹、解析 frontmatter → Material
│   ├── conflict.py          # 权威 + 时效裁决，冲突曝光
│   ├── llm_client.py        # urllib 直连 OpenAI 兼容端点（支持 function calling）
│   ├── fallback.json        # LLM 不可用时的降级预置结果
│   ├── run_all.py           # 三场景各跑一个 case 并做来源校验
│   └── tests/               # 30 个单元测试
├── skills/                  # 三个生成类 skill（本课题头号交付物）
│   ├── patsnap-tech-qa/ · patsnap-compare/ · patsnap-promo/
│   ├── references/资料使用SOP.md
│   └── scripts/check_sources.py
├── sample_retrieval/        # 模拟检索侧输出的样例 case（含冲突设计）
└── web/index.html           # 前端 Demo（单文件，无构建）
```

## Agent 访问资料的三个工具

Agent 不自己检索，只操作已召回的料：

- `list_materials()` — 列出所有资料的元信息（来源 / 权威级 / 更新时间 / 话题 / 相关度），不含正文，省 token。
- `read_material(source)` — 按来源读某份资料全文；事实只能来自这里。
- `check_conflicts()` — 按话题分组做权威 + 时效裁决，返回主答案与「另有资料表述不同」的曝光提示。

## 冲突裁决机制

同话题多来源时（例：官网说 Eureka 支持 12 种语言、旧笔记说 9 种）：

1. **选主答案**：先按权威级 `L1（官网/产品界面）> L2（内部权威文档）> L3（论文）> L4（二手转述）`，同级再按更新时间取新。
2. **曝光另一说法**：不删不藏，回答里附一句「另有资料表述不同：…（更新于 …，权威级 …）」。

不做「两句话语义上矛不矛盾」的自动判断（业界未解决）——只要同话题有多份来源，就排出主答案并如实曝光其余。

## 运行

### 1. 配置后端密钥

后端从 `planA/code/backend/.env` 读取 LLM 配置（`.env` 已被 gitignore，不入库）。新建该文件：

```bash
# planA/code/backend/.env
LLM_BASE_URL=<你的 OpenAI 兼容端点，如 https://.../v1>
LLM_MODEL=<模型名>
LLM_API_KEY=<你的 key>
```

密钥只在后端，前端只调本服务、不接触任何 key。

### 2. 启动服务

```bash
cd planA/code/backend
python3 server.py           # 默认 0.0.0.0:8000，可传端口：python3 server.py 8080
```

浏览器打开 http://localhost:8000 即可使用。

> ⚠️ 该服务默认监听 `0.0.0.0` 且**无鉴权**，仅供本地 Demo。若需对外暴露，请自行加访问控制。

### 3. 命令行跑三个场景（可选）

```bash
cd planA/code/backend
python3 run_all.py          # 三场景各跑一个样例 case，产物写入 run_logs/ 并做来源校验
```

## 测试

```bash
cd planA/code/backend
python3 -m unittest discover tests     # 30 个测试，覆盖 loader / conflict / case_tools / agent_runtime / server
```

## 技术选择说明

- **零第三方依赖**：后端全用 Python 标准库（`http.server` + `urllib`），本环境 PyPI 不可达、无 pyyaml，因此手写了极简 frontmatter 解析器和 LLM 客户端。开箱即跑，无需 `pip install`。
- **LLM 不可用时降级**：`/api/chat` 捕获异常后回退到 `fallback.json` 的预置结果，前端标「降级演示」，保证 Demo 不白屏。
