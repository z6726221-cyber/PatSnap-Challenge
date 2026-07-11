# 芽懂 YADO · 智慧芽私域知识协作空间

芽懂是面向智慧芽内部 **销售、售前、营销、运营、研发知识维护者** 的 AI 协作 Demo。它把企业私域知识、黑盒检索召回结果和场景化 skill 连接起来，让用户从一个入口完成可信问答、客户拜访方案、营销传播内容、产品与技术解释等工作。

当前仓库聚焦可运行 Demo：前端是单文件 Web 页面，后端是标准库 HTTP 服务，Agent 通过 OpenAI-compatible LLM API 调用 skill，并通过工具读取已召回资料。

---

## 当前产品形态

### 首页

首页是通用 Agent 入口。

- 用户直接输入任务或问题。
- 后端读取 `code/sample_retrieval/live/` 中由黑盒检索系统写入的资料。
- Agent 自主选择 skill，不由首页硬编码固定能力。
- 如果 `live/` 没有资料，首页不会退回假样例硬答，而是明确降级或提示检索资料缺失。

### 业务工作台

业务工作台是具体场景入口，会硬编码调用对应 skill。

| 页面 | 后端 mode | skill | 定位 |
|---|---|---|---|
| 销售与售前 | `presales` | `patsnap-presales` | 把客户背景、公开信息、企业知识和 AI 推断整理成可执行拜访方案 |
| 营销与传播 | `promo` | `patsnap-promo` | 生成传播文案或 30 秒短视频方案 |
| 产品与技术解释 | `tech_explain` | `patsnap-tech-explain` | 把产品能力、技术概念、方法论解释成业务听得懂、来源可查的标准口径 |

`patsnap-compare` 不在主导航里展示，但仍保留给首页通用 Agent 自主调用，用于市场/竞品/产品洞察类问题。

### 知识空间

知识空间用于查看和沉淀内部资料。

- 研发知识库
- 运营素材库
- 销售知识库

注意：`code/sample_retrieval/live/` 是黑盒检索系统的固定输出目录。普通上传和 E2E fixture 不应写入 `live/`，避免污染实时检索结果。

---

## Skill 体系

| Skill | 状态 | 说明 |
|---|---|---|
| `patsnap-tech-qa` | 保留 | 首页通用技术问答、统一口径回答 |
| `patsnap-presales` | 已强化 | 销售与售前工作台专用，强制区分公开信息、企业知识、AI 推断待验证 |
| `patsnap-promo` | 已重构 | 营销与传播专用，只保留传播文案和短视频；销售话术移交售前 skill |
| `patsnap-tech-explain` | 新增 | 产品与技术解释专用，输出一句话解释、通俗解释、核心原理、业务价值、能力边界、FAQ 等 |
| `patsnap-compare` | 保留并强化 | 首页自动路由使用；强制输出核心结论、对比表、建议话术、资料缺口/待核实项 |

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

测试和演示 case：

- `code/sample_retrieval/case-*`：基础样例。
- `code/sample_retrieval/e2e-*`：端到端测试 fixture。
- `code/sample_retrieval/live/`：只给黑盒检索实时写入使用。

资料格式说明见：

- `code/sample_retrieval/README-契约.md`

---

## 目录结构

```text
.
├── PRD/                         # 当前需求文档
├── demo原型/                    # 原型页面和参考图
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
│   │   └── tests/               # 单元测试
│   ├── e2e/
│   │   └── run_e2e.py           # 真实 API 端到端测试 runner
│   ├── sample_retrieval/
│   │   ├── case-*               # 基础样例
│   │   ├── e2e-*                # E2E fixture
│   │   └── live/                # 黑盒检索实时输出目录
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
│       └── assets/
└── README.md
```

---

## 环境变量

后端从 `code/backend/.env` 读取配置。可以复制示例文件：

```bash
cd code/backend
cp .env.example .env
```

常用配置：

```bash
# LLM：Agent、skill 选择和最终生成
LLM_BASE_URL=https://example-compatible-endpoint/v1
LLM_MODEL=replace-with-model
LLM_API_KEY=replace-with-key
LLM_MAX_TOKENS=6000

# 图片生成：可选
IMAGE_BASE_URL=https://example-compatible-endpoint/v1
IMAGE_MODEL=replace-with-image-model
IMAGE_API_KEY=replace-with-key

# 视频生成：可选
VIDEO_BASE_URL=https://example-compatible-endpoint/v1
VIDEO_MODEL=replace-with-video-model
VIDEO_API_KEY=replace-with-key

# 外部公开信息搜索：可选
# 未配置时，销售与售前会把外部信息标为缺口/待核实，不假装联网。
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

---

## 常用 API

| Method | Path | 说明 |
|---|---|---|
| `GET` | `/` | 前端页面 |
| `GET` | `/api/cases` | 列出样例 case |
| `POST` | `/api/chat` | 首页对话与各工作台主入口 |
| `GET` | `/api/kb` | 读取知识库、项目、上传列表 |
| `POST` | `/api/kb` | 新增知识项目或知识条目 |
| `POST` | `/api/upload` | 上传资料并写入本地知识库 |
| `POST` | `/api/image/generate` | 基于生成内容创建配图 |
| `GET` | `/api/image/file/<name>` | 读取生成图片 |
| `POST` | `/api/video/start` | 提交示例镜头视频任务 |
| `GET` | `/api/video/status/<task_id>` | 查询视频任务 |
| `POST` | `/api/export` | 导出 Markdown |
| `GET` | `/api/download/<path>` | 下载导出文件 |

---

## 测试

### 单元测试

```bash
python3 -m unittest discover code/backend/tests
```

### 静态/契约 E2E

不调用真实 LLM，只检查前端导航、页面契约和 E2E runner 基础逻辑：

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

## 视频能力边界

营销与传播 skill 会生成完整 `30 秒短视频方案`，包括分镜、字幕、发布配文和事实来源。

当前真实视频按钮只提交一个**示例镜头任务**，用于预览画面风格。它不等于完整 30 秒成片，也不自动完成多镜头剪辑、字幕烧录或旁白合成。

---

## 开发约定

1. 改页面、skill、后端 API 后，同步更新 README。
2. 不要把测试 fixture 写进 `code/sample_retrieval/live/`。
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
- 浏览器像素级 E2E 依赖本机 Playwright 浏览器或 Chrome 自动化权限；当前稳定验收以真实 API E2E + HTTP + 前端静态契约为主。
