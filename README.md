# 芽懂 · 智慧芽私域技术知识库（Plan A）

面向**销售 / 售前 / 运营 / 市场**的 AI 协作空间：上传研发资料和业务素材后，用自然语言拿到**有来源、有时效、口径统一**的技术问答、销售话术、市场与产品洞察、营销传播内容、图片海报和视频生成入口。

> 本仓库聚焦 **Plan A** 的可运行 Demo。产品定位、选型论证等完整方案见 [`planA/技术方案-OpenViking.md`](planA/技术方案-OpenViking.md)。

---

## 当前能力

### 1. 首页对话

- 支持直接输入问题，后端读取检索侧写入的资料并由 Agent 自主选择 skill。
- 首页保留快捷任务条框，当前包括「生成销售话术」「写运营推文」「解释 TRIZ 概念」「进行竞品分析」。点击条框会把文字填入输入框并追加空格，方便用户继续补充问题。
- 回答会被结构化渲染：结论、依据、冲突提示、待核实项和引用来源尽量分开展示，避免整段文字堆在一起。
- 检索资料不足或模型失败时会降级，并在前端明确提示「降级演示 / 资料不足」。

### 2. 业务工作台

当前侧边栏的业务入口包括：

- **销售与售前**：使用 `patsnap-presales` skill，面向客户拜访和售前推进，提供深度调研、痛点分析、话术脚本和行动清单四类任务。4 个模块可单独生成，也可汇总成一份完整客户拜访售前报告。
- **营销与传播**：原「内容生成」，使用 `patsnap-promo` skill，支持宣传稿、运营文案、销售话术、视频脚本 / 视频提示词等生成。
- **市场与产品洞察**：原「竞品分析」，使用 `patsnap-compare` skill，按维度组织我方与竞品差异，强调可追溯来源、攻防口径和销售可用表达。

销售与售前会合并读取 `sample_retrieval/live/`、本地销售 / 运营知识库和外部情报适配层。外部搜索服务未配置时，报告会明确标注 `external-intel/gap` 和待核实项，不会假装已经联网。营销与传播、市场与产品洞察会优先读取 `sample_retrieval/live/`；如果 live 资料不存在，会使用本地 KB 做轻量召回兜底，并在响应里标注检索来源。

### 3. 知识空间

- 支持查看「研发工作台」「运营素材库」和「销售知识库」。
- 支持新增知识项目、新增知识条目。
- 支持上传销售资料 / 运营素材，文件会同时写入本地知识库和 `sample_retrieval/live/`，模拟上游检索模块产出的资料目录。
- 支持导出生成结果为 Markdown 下载。

### 4. 图片与视频增强

- 可选图片增强：调用图片模型生成配套海报，并把图片直接展示在前端。
- 可选视频增强：从营销与传播结果里提取视频提示词，提交给视频模型生成任务；是否能返回可播放视频 URL 取决于上游网关和账号能力。

## 核心原则

- **不编造**：事实只来自召回资料；没有支撑的点标为「待核实」。
- **可溯源**：事实性陈述需要绑定来源和更新时间。
- **冲突曝光**：同一话题多来源不一致时，按权威性和时效裁决主答案，同时展示另一说法。
- **销售友好**：技术问答要清晰、通俗、专业，避免只给研发能看懂的术语堆叠。

## 系统链路

检索模块本身不在本仓库内。比赛 Demo 中，检索模块的输出被模拟为 Markdown 文件目录：

- 静态样例：`planA/code/sample_retrieval/case-*`
- 实时资料：`planA/code/sample_retrieval/live/`
- 上传文件：后端会把上传资料同步写入 `live/`

```text
用户问题
  -> 前端 planA/code/web/index.html
  -> 后端 planA/code/backend/server.py
  -> 读取 sample_retrieval/live/ 或样例 case
  -> Agent 自主选择 skill，或由业务页显式指定 skill
  -> skill 按资料使用 SOP 挑料、裁决冲突、组织答案
  -> 前端结构化展示回答 / 售前报告 / 销售话术 / 洞察报告 / 营销文案 / 图片 / 视频任务状态
```

资料契约见 [`planA/code/sample_retrieval/README-契约.md`](planA/code/sample_retrieval/README-契约.md)。

## Skill 设计

能力选择由 Agent 自主判断，不是后端关键词硬路由。后端把 skill 的 `name + description` 交给模型，模型先选择能力，再读取完整 skill 指令执行。

| Skill | 场景 | 产物 |
|---|---|---|
| `patsnap-tech-qa` | 产品 / 项目 / 技术概念问答 | 面向销售的清晰解释、标准口径、来源和待核实项 |
| `patsnap-compare` | 市场与产品洞察、竞品对比、攻防话术 | 维度化对比、我方优势 / 风险、证据和销售话术 |
| `patsnap-promo` | 营销与传播、宣传稿、运营文案、销售话术、视频脚本 | 带来源的内容初稿、视频提示词、可选图片海报 |
| `patsnap-presales` | 销售与售前、客户拜访准备、机会推进 | 客户调研、痛点分析、话术脚本、行动清单和完整拜访报告 |

共享规则：

- [`planA/code/skills/SOUL.md`](planA/code/skills/SOUL.md)：统一表达原则。
- [`planA/code/skills/references/资料使用SOP.md`](planA/code/skills/references/资料使用SOP.md)：来源、时效、冲突和边界规则。
- [`planA/code/skills/scripts/check_sources.py`](planA/code/skills/scripts/check_sources.py)：来源校验脚本。

## 目录结构

```text
planA/code/
├── backend/
│   ├── server.py              # HTTP 服务和 API 编排
│   ├── agent_runtime.py       # Agent 工具调用循环和 skill 选择
│   ├── case_tools.py          # list_materials/read_material/check_conflicts
│   ├── loader.py              # 读取检索输出 Markdown
│   ├── conflict.py            # 权威 + 时效裁决
│   ├── llm_client.py          # OpenAI-compatible LLM 客户端
│   ├── video_client.py        # 视频生成客户端，支持任务持久化
│   ├── image_client.py        # 图片生成客户端，保存并回显图片
│   ├── external_search.py     # 外部情报检索适配器，未配置时显式返回检索缺口
│   ├── local_store.py         # 本地知识库、上传、导出
│   ├── fallback.json          # 降级演示结果
│   └── tests/
├── sample_retrieval/
│   ├── case-*                 # 静态样例 case
│   └── live/                  # 模拟检索黑盒实时产出的 Markdown 资料
├── skills/
│   ├── patsnap-tech-qa/
│   ├── patsnap-compare/
│   ├── patsnap-promo/
│   ├── patsnap-presales/
│   ├── SOUL.md
│   └── references/资料使用SOP.md
└── web/
    ├── index.html             # 单文件前端 Demo
    └── assets/                # YADO logo、芽仔头像等静态资源
```

## 环境变量

后端从 `planA/code/backend/.env` 读取配置。可以复制 `.env.example` 后填写真实值：

```bash
cd planA/code/backend
cp .env.example .env
```

```bash
# LLM：用于对话、skill 选择和最终生成
LLM_BASE_URL=https://llm-api.patsnap.info/v1
LLM_MODEL=claude-opus-4-6
LLM_API_KEY=replace-with-your-backend-llm-key

# 视频：默认走 OpenAI-compatible 网关的 doubao-seedance-2.0
VIDEO_BASE_URL=https://llm-api.patsnap.info/v1
VIDEO_MODEL=doubao-seedance-2.0
VIDEO_API_KEY=replace-with-your-video-key

# 图片：默认 doubao-seedream-5.0-lite；不可用时可回退 doubao-seedream-4.5
IMAGE_BASE_URL=https://llm-api.patsnap.info/v1
IMAGE_MODEL=doubao-seedream-5.0-lite
IMAGE_FALLBACK_MODEL=doubao-seedream-4.5
IMAGE_API_KEY=replace-with-your-image-key-or-video-key

# 销售与售前外部情报搜索：可选
# 未配置时仍可生成报告，但外部客户事实会被标为待核实 / 需补充搜索。
EXTERNAL_SEARCH_ENDPOINT=
EXTERNAL_SEARCH_API_KEY=
```

注意：

- `.env` 已被 gitignore，不要提交真实 key。
- 前端不保存 key，只请求本地后端。
- `doubao-seedream-*` 要求图片至少 `1920x1920`，后端会自动调整过小尺寸。
- 视频模型如果只返回文本、不返回 URL，前端会展示错误或任务信息；这通常是网关能力或账号权限问题，不是前端渲染问题。

## 运行

默认端口是 `8000`，也可以传端口，例如当前调试常用 `8001`：

```bash
cd planA/code/backend
python3 server.py 8001
```

浏览器打开：

```text
http://localhost:8001/
```

该服务默认监听 `0.0.0.0` 且无鉴权，仅用于本地 Demo 或受控网络环境。对外暴露前需要补访问控制。

## 常用 API

| Method | Path | 说明 |
|---|---|---|
| `GET` | `/` | 前端页面 |
| `GET` | `/api/cases` | 列出静态样例 case |
| `POST` | `/api/chat` | 首页对话 / 销售与售前 / 市场与产品洞察 / 营销与传播主入口 |
| `GET` | `/api/kb` | 读取知识库、知识项目、上传列表 |
| `POST` | `/api/kb` | 新增知识项目或知识条目 |
| `POST` | `/api/upload` | 上传资料，并同步到本地 KB 与 `sample_retrieval/live/` |
| `POST` | `/api/image/generate` | 基于生成文案创建海报图片 |
| `GET` | `/api/image/file/<name>` | 读取后端保存的生成图片 |
| `POST` | `/api/video/start` | 从营销与传播结果中提取视频提示词并提交任务 |
| `GET` | `/api/video/status/<task_id>` | 查询视频任务状态 |
| `POST` | `/api/export` | 导出 Markdown |
| `GET` | `/api/download/<path>` | 下载导出文件 |

## 测试

```bash
cd planA/code/backend
python3 -m unittest discover -s tests

cd ../skills/scripts
python3 -m unittest discover
```

也可以从仓库根目录运行：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/codex_pycache python3 -m unittest discover -s planA/code/backend/tests
PYTHONPYCACHEPREFIX=/private/tmp/codex_pycache python3 -m unittest discover -s planA/code/skills/scripts
```

## 已知边界

- 上游真实检索服务未在仓库内实现；本 Demo 通过 `sample_retrieval/live/` 文件夹承接检索结果。
- 上传文件当前做轻量文本解码，PDF / Word / PPT 的专用解析器还未接入。
- 视频生成依赖外部模型网关；当前后端已做任务持久化和可灵配置兜底，但最终是否产出视频 URL 由上游决定。
- 本地知识库适合 Demo 和轻量验证，生产环境应替换为带权限、审计和索引能力的存储服务。
