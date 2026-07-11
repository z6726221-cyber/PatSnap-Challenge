# 芽懂 YADO · 智慧芽私域知识协作空间

芽懂是面向智慧芽内部 **销售、售前、营销、运营、研发知识维护者** 的 AI 协作 Demo。它把企业私域知识、黑盒检索召回结果和场景化 skill 连接起来，让用户从一个入口完成可信问答、客户拜访方案、营销传播内容、产品与技术解释、营销短视频方案等工作。

当前仓库聚焦可运行 Demo：前端是单文件 Web 页面，后端是零第三方 Web 框架的标准库 HTTP 服务，Agent 通过 OpenAI-compatible LLM API 调用 skill，并通过工具读取已召回资料。

---

## 当前产品形态

### 首页

首页是通用 Agent 入口，已按当前原型对齐主要视觉结构：左侧浅色导航、首页大输入框、快捷任务按钮和“为智慧芽团队定制 AI 协作空间”提示卡。

- 用户直接输入任务或问题，也可点击快捷任务。
- 后端读取 `code/sample_retrieval/live/` 中由黑盒检索系统写入的资料。
- 首页不硬编码固定能力；无显式 `mode` 时由 Agent 自主选择 skill。
- 如果 `live/` 没有资料，首页不会退回假样例硬答，而是明确降级或提示检索资料缺失。

### 业务工作台

业务工作台是具体场景入口，会显式调用对应 skill。

| 页面 | 后端 mode | skill | 定位 |
|---|---|---|---|
| 销售与售前 | `presales` | `patsnap-presales` | 把客户背景、公开信息、企业知识和 AI 推断整理成可执行拜访方案 |
| 营销与传播 | `promo` | `patsnap-promo` | 生成传播文案、30 秒短视频方案、配图提示和示例镜头视频任务 |
| 产品与技术解释 | `tech_explain` | `patsnap-tech-explain` | 把产品能力、技术概念、方法论解释成业务听得懂、来源可查的标准口径 |

`patsnap-compare` 仍保留在代码里，用于首页自动路由或内部“市场与产品洞察”视图；它不在当前主导航中展示。

### 知识空间

知识空间用于查看和沉淀内部资料。

- 研发工作台：上传研发文件，维护待解析/待审核/已入库资料列表。
- 运营素材库：管理营销素材、活动排期和内容生产状态。
- 销售知识库：管理销售话术、FAQ、客户案例和竞品攻防资料。

左侧“知识空间”标题当前没有新增项目 `+` 入口。上传资料会写入后端本地知识库，不会写入 `code/sample_retrieval/live/`。

---

## Skill 体系

| Skill | 状态 | 说明 |
|---|---|---|
| `patsnap-tech-qa` | 保留 | 首页通用技术问答、统一口径回答 |
| `patsnap-presales` | 已强化 | 销售与售前工作台专用，强制区分公开信息、企业知识、AI 推断待验证 |
| `patsnap-promo` | 已重构 | 营销与传播专用，输出传播文案、30 秒短视频方案、发布配文和生成提示 |
| `patsnap-tech-explain` | 新增 | 产品与技术解释专用，输出一句话解释、通俗解释、核心原理、业务价值、能力边界、FAQ 等 |
| `patsnap-compare` | 保留并强化 | 首页自动路由或内部视图使用；输出核心结论、对比表、建议话术、资料缺口/待核实项 |

共享资源：

- `code/skills/SOUL.md`：统一术语和表达风格。
- `code/skills/references/资料使用SOP.md`：资料读取、来源、时效、冲突裁决规则。
- `code/skills/scripts/check_sources.py`：来源检查脚本。

---

## 检索与资料契约

检索模块本身是外部黑盒，不在本仓库内。

真实链路约定：

```text
用户问题
  -> 外部黑盒检索
  -> 黑盒把召回结果写入 code/sample_retrieval/live/*.md
  -> 芽懂后端读取 live/
  -> Agent 选择或使用指定 skill
  -> skill 通过 list_materials / read_material / check_conflicts 读资料、裁决冲突、生成产物
  -> 前端结构化展示
```

资料目录约定：

- `code/sample_retrieval/live/`：黑盒检索实时输出目录。
- `code/sample_retrieval/live/analytics-ai-mode-product.md`、`triz-method-sales-explain.md`、`engineering-customer-brief.md`：白名单提交的 demo 召回资料，用于本地默认演示。
- `code/sample_retrieval/mock_external/`：外部公开信息检索的可提交模拟 fixture。
- `code/fixtures/retrieval_cases/`：基础 demo/单测 fixture。
- `code/e2e/fixtures/`：端到端测试 fixture。

`live/` 目录可能含内部真实召回内容，默认被 `.gitignore` 排除；只有 `.gitkeep`、`README.md` 和上述 3 个白名单 demo 资料入库。普通上传、真实临时召回和 E2E fixture 不应写入并提交 `live/`。

资料格式说明见：

- `code/sample_retrieval/README-契约.md`

---

## 目录结构

```text
.
├── code/
│   ├── backend/
│   │   ├── server.py            # HTTP 服务与 API 编排
│   │   ├── agent_runtime.py     # Agent 工具调用循环与 skill 选择
│   │   ├── case_tools.py        # list_materials/read_material/check_conflicts
│   │   ├── loader.py            # Markdown 检索资料解析
│   │   ├── conflict.py          # 权威性 + 时效冲突裁决
│   │   ├── llm_client.py        # OpenAI-compatible LLM 客户端
│   │   ├── external_search.py   # 外部情报适配层；未配置时显式返回缺口
│   │   ├── local_store.py       # 本地知识库、上传、导出
│   │   ├── image_client.py      # 图片生成客户端
│   │   ├── video_client.py      # 视频生成客户端
│   │   ├── fallback.json        # 降级结果
│   │   ├── .env.example         # 后端环境变量示例
│   │   └── tests/               # 单元测试
│   ├── fixtures/
│   │   └── retrieval_cases/     # 基础 demo/单测 fixture
│   ├── e2e/
│   │   ├── fixtures/            # E2E fixture
│   │   └── run_e2e.py           # 静态/HTTP/真实 API E2E runner
│   ├── sample_retrieval/
│   │   ├── mock_external/       # 外部公开信息模拟 fixture
│   │   └── live/                # 黑盒检索实时输出目录 + 白名单 demo 资料
│   ├── skills/
│   │   ├── patsnap-tech-qa/
│   │   ├── patsnap-presales/
│   │   ├── patsnap-promo/
│   │   ├── patsnap-tech-explain/
│   │   ├── patsnap-compare/
│   │   ├── SOUL.md
│   │   └── references/
│   └── web/
│       ├── index.html           # 单文件前端
│       └── assets/              # YADO logo、芽仔等静态资源
├── README.md
└── .gitignore
```

本地可能存在 `PRD/`、`demo原型/`、`ref/` 等参考资料目录，这些目录默认不入库。

---

## 环境变量

后端从 `code/backend/.env` 读取配置。可以复制示例文件：

```bash
cd code/backend
cp .env.example .env
```

常用配置与 `.env.example` 保持一致：

```bash
# LLM：Agent、skill 选择和最终生成
LLM_BASE_URL=https://llm-api.patsnap.info/v1
LLM_MODEL=claude-opus-4-6
LLM_API_KEY=replace-with-your-backend-llm-key

# 视频生成：可选
VIDEO_BASE_URL=https://llm-api.patsnap.info/v1
VIDEO_MODEL=doubao-seedance-2.0
VIDEO_API_KEY=replace-with-your-video-key

# 图片生成：可选；未配置 IMAGE_API_KEY 时复用 VIDEO_API_KEY
IMAGE_BASE_URL=https://llm-api.patsnap.info/v1
IMAGE_MODEL=doubao-seedream-5.0-lite
IMAGE_FALLBACK_MODEL=doubao-seedream-4.5
IMAGE_API_KEY=replace-with-your-image-key-or-video-key

# 外部公开信息搜索：可选
# 未配置时，销售与售前会把外部信息标为缺口/待核实。
# 设置 EXTERNAL_SEARCH_ENDPOINT=mock 可读取 code/sample_retrieval/mock_external/。
EXTERNAL_SEARCH_ENDPOINT=
EXTERNAL_SEARCH_API_KEY=
```

不要提交真实 `.env` 或 API key。

---

## 本地运行

从仓库根目录启动：

```bash
python3 code/backend/server.py 8000
```

浏览器打开：

```text
http://localhost:8000/
```

服务仅用于本地 Demo 或受控网络环境。对外暴露前需要补鉴权、权限控制和审计。

后端运行时会在 `code/backend/data/` 下生成本地知识库、上传文件、导出文件和生成图片等数据；这些是本地 Demo 数据，不应作为生产存储。

---

## 常用 API

| Method | Path | 说明 |
|---|---|---|
| `GET` | `/`、`/index.html` | 前端页面 |
| `GET` | `/assets/<name>` | 前端静态资源 |
| `GET` | `/api/cases` | 列出样例 case |
| `POST` | `/api/chat` | 首页对话与各工作台主入口 |
| `GET` | `/api/kb` | 读取知识库、项目、上传列表 |
| `POST` | `/api/kb` | 新增知识项目或知识条目 |
| `POST` | `/api/upload` | 上传资料并写入本地知识库 |
| `POST` | `/api/image/generate` | 基于生成内容创建配图 |
| `GET` | `/api/image/file/<name>` | 读取生成图片 |
| `POST` | `/api/video/start` | 从生成稿提取视频提示词并提交示例镜头任务 |
| `GET` | `/api/video/status/<task_id>` | 查询视频任务 |
| `POST` | `/api/export` | 导出 Markdown |
| `GET` | `/api/download/<path>` | 下载导出文件 |

`/api/chat` 常用 body：

```json
{
  "message": "把 Analytics AI Mode 转成销售拜访话术",
  "mode": "presales"
}
```

`mode` 可省略；可选值包括 `promo`、`comparison`、`presales`、`tech_explain`。测试回归可额外传 `case`，从 `code/fixtures/retrieval_cases/` 或 `code/e2e/fixtures/` 读取 fixture。

---

## 测试

### 单元测试

```bash
python3 -m unittest discover code/backend/tests
```

### 静态/契约 E2E

不调用真实 LLM，只检查前端导航、页面契约和 HTTP 基础逻辑：

```bash
python3 code/e2e/run_e2e.py --skip-real-api
```

### 真实 API 全链路 E2E

会调用真实 LLM API，耗时较长，用于验证 skill、后端 HTTP、前端契约是否整体跑通：

```bash
python3 code/e2e/run_e2e.py
```

测试报告输出到：

```text
code/e2e/reports/<timestamp>/
```

报告目录已被 `.gitignore` 忽略，不提交。

当前 E2E 覆盖：

- `patsnap-presales`：销售与售前拜访方案。
- `patsnap-promo`：30 秒短视频方案。
- `patsnap-tech-explain`：产品与技术解释。
- `patsnap-compare`：首页自动路由到竞品对比。
- 后端 `handle_chat` contract。
- HTTP `/api/cases`、`/api/chat`、`/api/export`。
- 前端静态契约：主导航、知识空间、30 秒视频口径、上传不污染 `live/`。

---

## 视频与图片能力边界

营销与传播 skill 会生成完整 `30 秒短视频方案`，包括分镜、字幕、发布配文和事实来源。

当前真实视频按钮只提交一个**示例镜头任务**，用于预览画面风格。它不等于完整 30 秒成片，也不自动完成多镜头剪辑、字幕烧录或旁白合成。

图片生成用于 Demo 配图/海报预览，生成结果保存在后端本地数据目录。未配置图片服务时会显式返回错误，不会在前端暴露密钥。

---

## 开发约定

1. 改页面、skill、后端 API 后，同步更新 README。
2. 不要把测试 fixture 写进 `code/sample_retrieval/live/`；内部检索 demo fixture 放进 `code/fixtures/retrieval_cases/`，E2E fixture 放进 `code/e2e/fixtures/`，外部公开信息模拟资料放进 `code/sample_retrieval/mock_external/`。
3. 新增工作台时，需要同时补：
   - 前端页面入口。
   - 后端 `mode -> skill` 映射。
   - skill `SKILL.md`。
   - E2E fixture。
   - `code/e2e/run_e2e.py` 验收项。
4. 首页是通用入口，由 Agent 自主选择 skill；业务工作台是具体场景，直接调用对应 skill。
5. 事实性输出必须有来源和更新时间；没有资料支撑的内容标 `待核实` 或 `资料缺口`。

---

## 已知边界

- 真实检索系统是外部黑盒，本仓库只消费其写入的 `code/sample_retrieval/live/`。
- 本地知识库适合 Demo，不是生产级权限/审计/索引系统。
- 外部公开信息搜索未配置时，系统会显式输出缺口，不会假装已经联网。
- 后端 HTTP 服务未内置鉴权、租户隔离、审计和生产级文件解析。
- 浏览器像素级 E2E 依赖本机 Playwright 浏览器或 Chrome 自动化权限；当前稳定验收以真实 API E2E + HTTP + 前端静态契约为主。
