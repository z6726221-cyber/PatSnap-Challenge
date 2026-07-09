# Plan B · Wiki-Compiled RAG 实施计划（P0 保底）

> **范围**：本计划只覆盖 spec §7 的 **P0 保底**——Raw→Wiki→SOUL(术语)→检索→**技术问答主Demo真跑通** + **竞品URL临场抓取真跑通**。
> 宣传材料生成、技术路线判断、四方评估、产品原型 Web 页面均为 P1，**不在本计划范围**，完成 P0 后另开计划。
> Spec 见 `planB/2026-07-07-课题3执行方案-design.md`（下称"设计规格"），任务编号引用其章节。

**Goal**：面向"运营小明"，交付一个能真跑的 Wiki-Compiled RAG 后端管道——手工编译的 TRIZ 领域 Wiki（互链 Markdown 整页）+ 混合检索（精确定位/关系跳转/BM25+向量模糊召回）+ 竞品 URL 真实抓取对比 + 术语与事实自检。用真实 LLM 网关和真实网络请求跑通，验收标准是"同一问题 3 种问法核心结论一致"和"抓取失败时清晰提示不编造"。

**Architecture**：
```
corpus/（Claude 手写编造的 TRIZ 领域语料，充当 raw/ 事实底座——P0 跳过 Smart-Doc）
        │  Claude 认知工作：编译
        ▼
patsnap-memory-skill/wiki/  （互链 Markdown 整页，index.md + graph.json，SOUL.md 术语表）
        │  确定性脚本：build_index.py（整页embedding→chromadb + BM25） / build_graph.py
        ▼
backend/retrieval.py  ── 意图路由：精确(index.md别名) → 关系(graph.json一两跳) → 模糊(BM25+向量RRF)
        │                 命中后永远整页返回 + sources
        ▼
backend/wiki_tools.py ── 把检索/读页/竞品抓取暴露为 function-calling 工具
        │
        ▼
backend/agent_runtime.py ── 真实 gpt-5.5 function-calling 循环，system prompt = SKILL.md
        │
        ▼
backend/run_all.py ── 端到端验收：技术问答口径一致性测试 + 竞品真实URL抓取测试
```

**Tech Stack**（本次会话已在沙盒逐一验证可安装、可导入、可运行）：
- Python 3.9（系统自带）
- `chromadb==0.5.23` + `sentence-transformers==2.7.0`（`transformers==4.44.2` / `tokenizers==0.19.1` 锁定版本避免与 chromadb 冲突）+ 本地多语 embedding 模型 `paraphrase-multilingual-MiniLM-L12-v2`（384维，中英双语，已验证真实下载编码成功；spec 提到的"BGE-M3类"为同类可替换选项）
- `rank-bm25==0.2.2` + `jieba==0.42.1`（中文分词后喂给 BM25）
- `openai==1.40.0` + `httpx==0.27.2`（httpx 锁定 0.27.2，因 1.40.0 与 httpx≥0.28 的 `proxies` 参数不兼容，已验证）
- `trafilatura==1.9.0`（竞品 URL 抓取解析，已验证真实抓取 Wikipedia 页面成功）
- `python-frontmatter==1.1.0` + `pyyaml==6.0.2`（Wiki 页面 frontmatter 解析）
- `pytest==8.3.3` + `python-dotenv==1.0.1`
- LLM 网关：`base_url=https://llm-api.patsnap.info/v1`，`model=gpt-5.5`，OpenAI 兼容协议，已用真实 key 验证连通（key 存于 `planB/code/backend/.env`，已在 `.gitignore` 排除，绝不提交）

## Global Constraints

- **跳过 Smart-Doc**：P0 语料是 Claude 手写的 Markdown（占位 TRIZ 领域，非扫描件/PDF），不实现 `tools/parse_docs.py` 的真实 API 调用。`corpus/` 内容即视为 Raw Sources 事实底座，直接编译进 `wiki/`。若后续接入真实 PDF/Smart-Doc，是独立的 P1+ 任务。
- **不做 Web UI**：本计划只做后端管道，用 CLI 脚本（`run_all.py`）和 pytest 验证跑通。技术问答页/竞品分析页的 FastAPI+前端留给下一份计划。
- **密钥不入库**：`planB/code/backend/.env` 已创建并写入真实网关配置，`.gitignore` 已加 `.env` / `*.env` / `!.env.example` 规则并验证 `git check-ignore` 生效。仓库里只提交 `.env.example`（占位）。
- **窄而深**：知识库范围锁定 TRIZ 一个技术领域（spec §0.4），不铺开多领域。
- **术语表逐条核实**：SOUL.md 的术语表每条标注真实核实来源（官网/产品页），不凭印象编——用 WebFetch 核对 patsnap.com 官网术语后落笔。
- **不编造**：Wiki 页面每个事实点绑 `[来源: doc_id, doc_date]`；无来源的进"待核实"段和 error-book，不写成事实。故意在语料里制造 1-2 处新旧冲突（如"矛盾矩阵有几种解法"两种说法），用于验证 §1.6 权威性裁决 + `superseded_by` 链条真的工作。
- **竞品抓取失败不能静默假装成功**：`fetch_competitor.py` 遇到超时/404/反爬要给清晰错误信息，run_all.py 用一个必然失败的 URL 验证这条路径。
- **整页加载**：检索命中后返回整页 Markdown（含 frontmatter），不返回碎片。
- **提交规范**：每个任务末尾提交，`feat/refactor/test/docs(planB): ...`；不用 `git add .`，只加相关文件。

## 文件结构（目标形态）

```
planB/code/
├── requirements.txt                     # 已验证的锁定版本
├── corpus_manifest.json                 # 语料登记：来源/类型/领域/更新时间
├── corpus/
│   ├── domain-docs/                     # TRIZ 手写语料（含故意冲突点）
│   ├── open-source/openviking/          # 基于 OpenViking-main/README.md 的开源项目素材
│   └── official/                        # 智慧芽产品能力占位素材
├── tools/
│   ├── build_index.py                   # 整页embedding→chromadb + BM25索引
│   ├── build_graph.py                   # 扫描frontmatter.related + [[wikilink]] → graph.json
│   ├── fetch_competitor.py              # 竞品URL临场抓取（trafilatura，真实网络）
│   └── lint_wiki.py                     # 断链/孤儿页/无源结论/过期未标注扫描
├── patsnap-memory-skill/
│   ├── SKILL.md                         # 顶层说明书
│   ├── SOUL.md                          # 术语表（逐条核实）
│   ├── raw/                             # 原始证据层（=corpus/ 内容整理落地，只读）
│   ├── wiki/
│   │   ├── domain/triz/                 # TRIZ 知识页（主体，5+页）
│   │   ├── product-capability/          # 智慧芽产品能力页
│   │   ├── open-source-project/         # OpenViking 项目页
│   │   ├── competitors/                 # 竞品页（含临场抓取沉淀）
│   │   ├── index.md                     # 全局目录+aliases
│   │   └── graph.json                   # 脚本生成
│   ├── workflows/
│   │   ├── tech-qa.md
│   │   └── competitor-analysis.md
│   └── error-book.md
├── backend/
│   ├── .env                             # 真实网关配置（已创建，gitignored）
│   ├── .env.example
│   ├── llm_client.py                    # openai SDK 封装，指向内部网关
│   ├── retrieval.py                     # 意图路由 + 混合检索 + 整页返回
│   ├── wiki_tools.py                    # function-calling 工具封装
│   ├── agent_runtime.py                 # 真实 gpt-5.5 function-calling 循环
│   ├── run_all.py                       # 端到端验收（口径一致性 + 竞品抓取）
│   └── tests/                           # pytest：retrieval/build_index/build_graph/fetch_competitor/lint
```

---

## 任务与状态

| # | 任务 | 状态 |
|---|---|---|
| 1 | 脚手架：目录结构 + requirements.txt + backend/.env（真实网关，已验证连通）+ .env.example + .gitignore 规则 | ✅ 完成 |
| 2 | TRIZ 语料编造（corpus/domain-docs + open-source + official）+ corpus_manifest.json，含故意冲突点 | ✅ 完成 |
| 3 | Wiki 编译（Claude 认知工作）：wiki/domain/triz/*.md（5+页）+ product-capability/*.md + open-source-project/openviking.md + 1个初始竞品页 + index.md + SOUL.md（术语表逐条核实）+ error-book.md 初始记录 | ✅ 完成 |
| 4 | tools/build_index.py（TDD）：整页embedding入chromadb + jieba分词BM25索引 | ✅ 完成 |
| 5 | tools/build_graph.py（TDD）：扫描related+wikilink→graph.json | ✅ 完成 |
| 6 | tools/fetch_competitor.py（TDD + 真实网络验证）：trafilatura抓取解析，失败清晰提示 | ✅ 完成 |
| 7 | tools/lint_wiki.py（TDD）：断链/孤儿页/无源结论/过期未标注 | ✅ 完成 |
| 8 | backend/llm_client.py：openai SDK封装内部网关（复用已验证配置） | ✅ 完成 |
| 9 | backend/retrieval.py（TDD）：精确/关系/模糊三路由，整页返回+溯源 | ✅ 完成 |
| 10 | backend/wiki_tools.py + agent_runtime.py（TDD，mock测工具+真实e2e测完整链路）：function-calling循环 | ✅ 完成 |
| 11 | patsnap-memory-skill/workflows/tech-qa.md + competitor-analysis.md + SKILL.md | ✅ 完成 |
| 12 | backend/run_all.py 端到端验收：3种问法口径一致性 + 真实竞品URL抓取（成功+故意失败两种场景） | ✅ 完成 |
| 13 | pytest 全量跑绿 + 更新本计划文档反映落地状态 | ✅ 完成 |

**落地状态**（2026-07-09）：全部 13 项任务完成。`pytest` 52 项全绿（含真实网络测试，标记 `network`）。`backend/run_all.py` 用真实 `gpt-5.5` + 真实网关跑通：3 种问法核心结论一致（矛盾矩阵 39 参数）、竞品 URL 临场抓取成功场景（真实抓取 PatentSight+ 官网）与故意失败场景（不可达域名，清晰提示未编造）均通过。过程中发现并修复一处真实 bug：`retrieval.load_page` 未把 YAML frontmatter 里形如 `2026-07-08` 的日期标量转回字符串，会在 `agent_runtime.py` 的 `json.dumps(result)`（工具结果回传给 LLM）处抛出 `TypeError: Object of type date is not JSON serializable`——只有在竞品页面（`sources` 用 `fetched_at` 而非 `doc_date` 字段）触发真实 e2e 测试时才暴露，已在 `retrieval._normalize_sources` 里改为通用日期类型转换修复。

---

## 验收标准（对齐 spec §8.1 相关条目）

- [x] 技术问答：同一问题 3 种不同问法，答案核心结论一致（口径统一，主验收指标）——`run_all.py` 验证 3 种问法均含"39"（矛盾矩阵参数数）
- [x] 竞品对比：真实 URL 临场抓取可用；用一个故意失败的 URL 验证失败提示清晰、不编造——成功场景抓取 PatentSight+ 官网，失败场景对不可达域名给出"抓取失败"提示
- [x] 每个生成结果带"来源列表 + 待核实清单"——`workflows/tech-qa.md`、`workflows/competitor-analysis.md` 的 Output Contract 均强制要求
- [x] Wiki 每个结论可回查 corpus/（raw/），带 doc_date——`lint_wiki.py` 校验通过，无 unsourced_conclusion
- [x] 存在至少一处版本冲突，`superseded_by` 链条正确，error-book 记录裁决依据——`triz-contradiction-matrix.md`（39参数 vs 旧笔记48参数）
- [x] 术语表每条经过真实核实（WebFetch 核对官网）——`SOUL.md` 每条术语标注核实来源
- [x] 无 API key 泄露在 git 历史（`.env` 已确认 gitignore 生效）——`backend/.env` 已在 `.gitignore`，仓库只提交 `.env.example`
- [x] pytest 全绿；`run_all.py` 用真实 gpt-5.5 跑通不降级——52 项测试全通过（含 `network` 标记的真实网络测试），`run_all.py` 端到端全部通过
