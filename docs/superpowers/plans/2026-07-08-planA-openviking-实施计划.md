# Plan A · OpenViking 技术知识助手 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于火山引擎开源的 OpenViking 上下文数据库，搭建一个面向智慧芽运营/销售的技术知识助手 Demo——先用样例数据把「环境 → 数据接入 → skill → 检索编排 → 前端 → 评估」全链路跑通，真实语料到位后可无痛替换。

**Architecture:** OpenViking 作为独立 HTTP 服务（`localhost:1933`）承担存储/分层/检索/版本；我方交付一个「编排后端」（FastAPI）+「一组 SKILL.md」+「对话网页前端」。后端只通过 HTTP API 黑盒调用 OpenViking（AGPL 合规护栏），负责 OpenViking 管不了的场景逻辑：查询理解改写、专名 grep 融合、跨资源冲突标注、竞品对比分解、实时抓取、组装 prompt 调大模型生成、附来源与时效。

**Tech Stack:** Python 3.11（经 uv 管理，因系统 Python 3.9.6 不满足 OpenViking ≥3.10 要求）、OpenViking 0.4.8、FastAPI 0.139.0 + uvicorn 0.50.2、openai 2.44.0（OpenAI 兼容接口，不绑火山）、httpx 0.28.1、trafilatura 2.1.0（竞品网页去噪抽取）、pytest 9.1.1 + pytest-mock 3.15.1、原生 HTML/JS 前端。

## Global Constraints

- **Python 版本**：≥3.10（OpenViking 硬性要求，源码 `pyproject.toml:16` `requires-python = ">=3.10"`）。系统自带 3.9.6 不可用，全程用 uv 管理的 Python 3.11 虚拟环境。
- **OpenViking 版本**：`openviking==0.4.8`（PyPI 当前最新，支持 3.10-3.14）。
- **AGPL 合规硬边界**：绝不修改 `OpenViking-main/` 源码，绝不 `import openviking` 进我方后端进程；只通过 `http://localhost:1933` 的 HTTP API 调用。我方后端依赖 `httpx`，不依赖 `openviking` 包。
- **密钥不落前端**：大模型 API key、OpenViking api_key 只存后端 `.env`，前端只调我方后端。`.env` 加入 `.gitignore`，绝不提交。
- **样例数据隔离**：所有样例语料放 `planA/code/sample_data/`，路径通过配置项 `CORPUS_DIR` 注入，真实语料到位后改配置即可，不改代码。
- **五模块目录约定**：`viking://resources/{methodology,products,style,competitors,roadmap}/`。
- **降级档**：主 Demo 链路（技术问答、竞品对比）必须各备一份「预置结果」JSON，实时链路失败时回退，答辩不翻车。
- **工作目录**：所有我方代码在 `planA/code/`；OpenViking 源码在 `OpenViking-main/`（只读参考，不改）。
- **提交规范**：每个 Task 末尾提交，msg 用 `feat(planA): ...` / `test(planA): ...` / `docs(planA): ...`。

---

## 文件结构总览

我方全部产出在 `planA/code/`，与 `OpenViking-main/`（只读）解耦：

```
planA/code/
├── .env.example              # 配置模板（提交）；.env 实际值不提交
├── .gitignore                # 忽略 .env / __pycache__ / data/
├── requirements.txt          # 我方后端依赖（不含 openviking）
├── README.md                 # 起服务步骤（环境 → OV → 后端 → 前端）
├── config.py                 # 读 .env：OV_URL/OV_API_KEY/LLM_*/CORPUS_DIR/COMPETITOR_URLS
├── ov_client.py              # OpenViking HTTP API 薄封装（httpx）：find/grep/glob/ls/read/add_resource
├── llm_client.py             # OpenAI 兼容大模型封装：query 理解改写 + 生成
├── orchestrator/
│   ├── __init__.py
│   ├── query_understanding.py  # 口语→范围+改写+时间意图+专名抽取
│   ├── retrieval.py            # find∥grep 并行 + 融合排序 + 附来源
│   ├── conflict.py             # 跨资源冲突：话题重复检测 + 权威性裁决 + 曝光（§7之二）
│   ├── comparison.py           # 竞品对比：分解 + 多源召回 + 维度对齐
│   ├── competitor_fetch.py     # 竞品 URL 实时抓取 + trafilatura 去噪 + 维度抽取
│   └── generation.py           # 组装料+风格样本+prompt → 调 LLM → 附来源/待核实
├── server.py                 # FastAPI：/api/chat（意图分流）/api/health，静态托管前端
├── skills/                   # ← 核心交付物：SKILL.md 一组
│   ├── patsnap-kb-curation/SKILL.md   # 建库规范
│   ├── patsnap-tech-qa/SKILL.md       # 技术问答
│   ├── patsnap-competitor/SKILL.md    # 竞品对比
│   └── patsnap-promo-gen/SKILL.md     # 宣传生成
├── sample_data/              # 样例语料（真实语料到位后替换）
│   ├── methodology/          # 方法论样例（TRIZ 科普 md）
│   ├── products/             # 产品能力样例（含一份「支持3种语言」旧文档，制造冲突用）
│   ├── competitors/          # 竞品样例
│   └── style/                # 宣传风格样本
├── fallback/                 # 降级档预置结果
│   ├── tech_qa.json
│   └── comparison.json
├── eval/
│   ├── eval_set.jsonl        # 20-30 题召回评测集（题+理想URI）
│   └── run_eval.py           # 算 recall@k / MRR
├── web/
│   └── index.html            # 对话前端（接真实后端，改自 demo原型）
└── tests/
    ├── test_ov_client.py
    ├── test_query_understanding.py
    ├── test_retrieval.py
    ├── test_conflict.py
    ├── test_comparison.py
    ├── test_competitor_fetch.py
    ├── test_generation.py
    └── test_server.py
```

**测试策略**：我方后端所有对 OpenViking / 大模型的调用都走 `ov_client.py` / `llm_client.py` 两个封装层，单测用 `pytest-mock` mock 这两层的 HTTP 调用，不依赖真实服务——这样测试离线可跑。另有一组「集成验证」步骤（真起 OpenViking 服务、真导入样例数据），在对应 Task 里用手动命令验证，不进 pytest。

---

## 阶段划分与优先级（对齐 spec P0/P1）

- **阶段一（Task 1-3）· 地基**：环境、OpenViking 起服务、样例数据全链路验证。不依赖真实语料。**最先做，避免后面白做。**
- **阶段二（Task 4-7）· 编排后端 + P0 技术问答**：ov_client、查询理解、检索融合、冲突标注。产出可测的技术问答链路。
- **阶段三（Task 8-9）· P0 竞品对比 + 实时抓取**：差异化爆点。
- **阶段四（Task 10-11）· 后端服务 + 前端 Demo**：把链路接成能点的产品。
- **阶段五（Task 12-14）· skill 交付物 + P1 宣传生成 + 评估**：SKILL.md 落地、宣传生成、评测集。
- **阶段六（Task 15）· 真实语料切换**：语料到位后的替换动作（占位，不阻塞前面）。

---

### Task 1: 环境搭建 — uv + Python 3.11 + OpenViking 安装

**Files:**
- Create: `planA/code/.env.example`
- Create: `planA/code/.gitignore`
- Create: `planA/code/requirements.txt`
- Create: `planA/code/README.md`

**Interfaces:**
- Produces: 一个可用的 Python 3.11 虚拟环境 `planA/code/.venv/`（uv 创建）；已安装 `openviking==0.4.8`（CLI `openviking` / `ov` 可用）；`~/.openviking/ov.conf` 已配好 embedding+VLM。
- Consumes: 无（起点任务）。

**背景（已核实的真实环境状况）**：系统 Python 是 3.9.6（`/usr/bin/python3`），低于 OpenViking 要求的 ≥3.10；无 brew/pyenv/docker/node。因此用 astral 的 `uv`（独立安装器，不依赖 brew）来装一个隔离的 Python 3.11 并建虚拟环境。这是 OpenViking 官方服务端部署指南推荐的方式（`OpenViking-main/docs/zh/getting-started/03-quickstart-server.md`）。

- [ ] **Step 1: 安装 uv**

Run:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env 2>/dev/null || export PATH="$HOME/.local/bin:$PATH"
uv --version
```
Expected: 打印类似 `uv 0.9.x`。若 `uv` 仍找不到，确认 `~/.local/bin` 在 PATH 中。

- [ ] **Step 2: 用 uv 建 Python 3.11 虚拟环境**

Run:
```bash
cd planA/code
uv venv .venv --python 3.11
source .venv/bin/activate
python --version
```
Expected: `Python 3.11.x`（uv 会自动下载 3.11 若本机没有）。

- [ ] **Step 3: 安装 OpenViking 到虚拟环境**

Run:
```bash
uv pip install openviking==0.4.8
openviking --version
```
Expected: 打印 OpenViking 版本 `0.4.8`。CLI 同时提供 `openviking` 和 `ov` 两个入口。
注意：安装较慢（Rust+Python 混合工程，含二进制轮子），预留时间。若 `--version` 带 Pydantic V1 警告噪声属正常（见 quickstart-server.md 的 Python 3.14 说明；我们用 3.11 一般无此问题）。

- [ ] **Step 4: 写我方后端依赖清单**

创建 `planA/code/requirements.txt`（注意：**不含 openviking**——AGPL 合规，我方后端只 HTTP 调用它）：
```
fastapi==0.139.0
uvicorn==0.50.2
httpx==0.28.1
openai==2.44.0
trafilatura==2.1.0
python-dotenv==1.2.2
pytest==9.1.1
pytest-mock==3.15.1
```

- [ ] **Step 5: 安装我方后端依赖**

Run:
```bash
uv pip install -r requirements.txt
python -c "import fastapi, httpx, openai, trafilatura; print('deps ok')"
```
Expected: `deps ok`。

- [ ] **Step 6: 写配置模板 `.env.example`**

创建 `planA/code/.env.example`：
```
# OpenViking 独立服务
OV_URL=http://localhost:1933
OV_API_KEY=

# 大模型（OpenAI 兼容接口，不绑火山）
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=sk-your-key-here
LLM_MODEL=gpt-4o-mini
LLM_SMALL_MODEL=gpt-4o-mini

# 样例语料目录（真实语料到位后改这里，不改代码）
CORPUS_DIR=./sample_data

# 竞品预置网址（逗号分隔；实时抓取失败时的演示兜底也在此配）
COMPETITOR_URLS=
```

- [ ] **Step 7: 写 `.gitignore`**

创建 `planA/code/.gitignore`：
```
.venv/
.env
__pycache__/
*.pyc
data/
.pytest_cache/
```

- [ ] **Step 8: 配置 OpenViking 模型（embedding + VLM，OpenAI 兼容）**

创建 `~/.openviking/ov.conf`（模板来自 `OpenViking-main/docs/zh/guides/01-configuration.md:82` 的 OpenAI 示例；把 key 换成真实值。若用其它 OpenAI 兼容端点，改 `api_base` 与 `model`/`dimension`）：
```json
{
  "embedding": {
    "dense": {
      "api_base": "https://api.openai.com/v1",
      "api_key": "sk-your-key-here",
      "provider": "openai",
      "dimension": 1536,
      "model": "text-embedding-3-small"
    }
  },
  "vlm": {
    "api_base": "https://api.openai.com/v1",
    "api_key": "sk-your-key-here",
    "provider": "openai",
    "model": "gpt-4o-mini"
  }
}
```

- [ ] **Step 9: 校验 OpenViking 配置**

Run:
```bash
openviking-server doctor
```
Expected: 各 provider 鉴权检查通过（embedding/vlm 可访问）。若报鉴权失败，检查 `ov.conf` 的 key 和 api_base。这是「避免后面白做」的关卡——**doctor 不过就不要继续**。

- [ ] **Step 10: 写 README（起服务步骤）**

创建 `planA/code/README.md`，记录四步起服务顺序：①`source .venv/bin/activate` ②`openviking-server`（另开终端，见 Task 2）③`cp .env.example .env` 填真实值 ④`uvicorn server:app --port 8000`（见 Task 10）。附一句 AGPL 边界说明：本项目通过 HTTP 调用 OpenViking，不修改其源码、不静态链接。

- [ ] **Step 11: 提交**

```bash
cd "/Users/zhangdezhao/Documents/PatSnap挑战赛"
git add planA/code/.env.example planA/code/.gitignore planA/code/requirements.txt planA/code/README.md
git commit -m "feat(planA): 环境地基 — uv+py3.11 虚拟环境、依赖清单、配置模板"
```

---

### Task 2: 起 OpenViking 服务并验证健康

**Files:**
- 无新文件（本任务是集成验证 + 记录 api_key）。

**Interfaces:**
- Consumes: Task 1 的虚拟环境和 `ov.conf`。
- Produces: 一个在 `localhost:1933` 常驻的 OpenViking 服务；`~/.openviking/ovcli.conf`（CLI 连接配置）；确认后填入 `.env` 的 `OV_API_KEY`。

- [ ] **Step 1: 启动 OpenViking 服务**

另开一个终端，激活环境后启动（前台运行，便于看日志）：
```bash
cd planA/code && source .venv/bin/activate
openviking-server --port 1933
```
Expected: 看到 `INFO:     Uvicorn running on http://0.0.0.0:1933`（或 127.0.0.1）。首次启动较慢（初始化存储、加载模型客户端），耐心等。

- [ ] **Step 2: 验证健康检查**

回到主终端：
```bash
curl http://localhost:1933/health
```
Expected: `{"status": "ok"}`。若 Mac 上 `Connection reset`，参考 quickstart.md 的 socat 端口转发提示（Docker 场景才需要；pip 直跑一般无此问题）。

- [ ] **Step 3: 确认认证模式并取 api_key**

默认起服务若未启用认证，`OV_API_KEY` 可留空。若启用了认证，按 `OpenViking-main/docs/zh/getting-started/03-quickstart-server.md` 的两层 key 体系用 `user_key`（数据面），不要用 `root_key`。把最终 key 填入 `planA/code/.env` 的 `OV_API_KEY`。
Run（验证一次带 key 的数据面调用）：
```bash
curl -s "http://localhost:1933/api/v1/fs/ls?uri=viking://resources/" ${OV_API_KEY:+-H "X-API-Key: $OV_API_KEY"}
```
Expected: 返回 JSON（空 resources 树也算成功，`status: ok`）。

- [ ] **Step 4: 写 CLI 连接配置**

创建 `~/.openviking/ovcli.conf`（供 `openviking find` 等 CLI 命令连服务用）：
```json
{
  "url": "http://localhost:1933",
  "api_key": ""
}
```
（若启用认证则填 user_key。）
Run:
```bash
openviking observer system
```
Expected: 打印系统状态表，无连接错误。

- [ ] **Step 5: 记录到 README**

在 `planA/code/README.md` 追加「服务健康检查」小节：`curl /health` 应返回 `{"status":"ok"}`；`openviking observer system` 用于查看系统健康。无代码提交（若 README 有改动则 `git add planA/code/README.md && git commit -m "docs(planA): 补充 OpenViking 服务健康检查步骤"`）。

---

### Task 3: 造样例数据 + 全链路验证 add/find/grep/glob

**Files:**
- Create: `planA/code/sample_data/methodology/triz-intro.md`
- Create: `planA/code/sample_data/products/eureka-overview.md`
- Create: `planA/code/sample_data/products/eureka-langs-old.md`（**故意与 overview 冲突**，供 Task 7 用）
- Create: `planA/code/sample_data/competitors/competitor-a.md`
- Create: `planA/code/sample_data/style/promo-sample.md`
- Create: `planA/code/scripts/import_sample.sh`

**Interfaces:**
- Consumes: Task 2 的运行中服务。
- Produces: `viking://resources/` 下按五模块组织的样例资源树；确认 `find`/`grep`/`glob` 真实返回结果的证据。

**说明**：样例内容用「与具体真实语料无关的能力验证」为目的编造，覆盖：①一份方法论 ②一份产品能力概览（写「支持 5 种语言」，来源标 2026-06 官网）③一份旧产品文档（写「支持 3 种语言」，来源标 2025-03 内部PPT）——②③制造真实的跨资源事实冲突，是 §7之二 冲突机制的测试夹具。

- [ ] **Step 1: 写方法论样例**

创建 `planA/code/sample_data/methodology/triz-intro.md`：
```markdown
# TRIZ 发明问题解决理论 · 入门

TRIZ 是一套系统化的创新方法论，核心是「矛盾矩阵」与「40 个发明原理」。
当一个技术系统存在矛盾（改善 A 会恶化 B）时，TRIZ 提供了标准化的解题路径。

## 核心概念
- 技术矛盾：一个参数改善导致另一个参数恶化。
- 物理矛盾：同一参数需要同时具备两种相反状态。
- 理想度：系统朝「功能不变、成本趋零」演进。

> 来源：内部方法论培训资料 · 更新于 2026-05
```

- [ ] **Step 2: 写产品能力概览样例（新，权威）**

创建 `planA/code/sample_data/products/eureka-overview.md`：
```markdown
# Eureka 产品能力概览

Eureka 是面向专利检索的智能分析产品，支持语义检索、技术分类、多语言检索。

## 多语言能力
Eureka 当前支持 **5 种语言**的专利文献检索：中文、英文、日文、德文、韩文。

> 来源：官网产品页 · 更新于 2026-06
```

- [ ] **Step 3: 写产品能力旧文档样例（旧，制造冲突）**

创建 `planA/code/sample_data/products/eureka-langs-old.md`：
```markdown
# Eureka 多语言支持说明（内训版）

Eureka 目前支持 **3 种语言**：中文、英文、日文。

> 来源：内部销售培训 PPT · 更新于 2025-03
```

- [ ] **Step 4: 写竞品与风格样例**

创建 `planA/code/sample_data/competitors/competitor-a.md`：
```markdown
# 竞品A 产品资料

竞品A 是一款专利检索工具，支持中文与英文两种语言的检索，主打价格优势。

## 多语言能力
竞品A 支持 2 种语言：中文、英文。

> 来源：竞品A 官网 · 抓取于 2026-06
```
创建 `planA/code/sample_data/style/promo-sample.md`：
```markdown
# 智慧芽宣传文案风格样本

在这个技术飞速迭代的时代，智慧芽始终相信：让创新更简单。
我们用扎实的技术，把复杂的专利世界，讲成你听得懂的语言。

> 历史公众号文案节选，用作风格样本
```

- [ ] **Step 5: 写批量导入脚本**

创建 `planA/code/scripts/import_sample.sh`（用 CLI 按五模块归档；`--wait` 等语义处理完成）：
```bash
#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "$0")/.." && pwd)/sample_data"

openviking add-resource "$BASE/methodology/triz-intro.md" \
  --to viking://resources/methodology/triz-intro.md --wait
openviking add-resource "$BASE/products/eureka-overview.md" \
  --to viking://resources/products/eureka-overview.md --wait
openviking add-resource "$BASE/products/eureka-langs-old.md" \
  --to viking://resources/products/eureka-langs-old.md --wait
openviking add-resource "$BASE/competitors/competitor-a.md" \
  --to viking://resources/competitors/competitor-a.md --wait
openviking add-resource "$BASE/style/promo-sample.md" \
  --to viking://resources/style/promo-sample.md --wait

echo "=== 导入完成，列出资源树 ==="
openviking ls viking://resources --recursive
```

- [ ] **Step 6: 执行导入**

Run:
```bash
cd planA/code && source .venv/bin/activate
bash scripts/import_sample.sh
```
Expected: 5 条 `status success`，最后 `ls` 打印出 `methodology/`、`products/`、`competitors/`、`style/` 四个目录及其下文件。每份文件应有自动生成的 `.abstract.md`（L0）。

- [ ] **Step 7: 验证语义检索 find**

Run:
```bash
openviking find "Eureka 支持几种语言" --uri viking://resources/products --limit 5
```
Expected: 返回结果列表，命中 `eureka-overview.md` 和 `eureka-langs-old.md`，每条带 `uri`（`viking://...`）和 `score`。**这验证了「检索带来源 URI」这一溯源刚需。**

- [ ] **Step 8: 验证专名精确匹配 grep**

Run:
```bash
openviking grep "TRIZ" --uri viking://resources
openviking grep "Eureka" --uri viking://resources --ignore-case
```
Expected: `TRIZ` 命中 `methodology/triz-intro.md`；`Eureka` 命中多个 products 下文件。返回含 `uri` + `line` + `content`。**这验证了专名 grep 兜底的引擎能力真实存在（是 OV 自带 API，我方 Task 6 只做触发/融合）。**

- [ ] **Step 9: 验证 glob 与 read**

Run:
```bash
openviking glob "**/*.md" --uri viking://resources
openviking find "多语言" --uri viking://resources/products --limit 3
# 取上一步某条 uri 读全文
openviking read "viking://resources/products/eureka-overview.md"
```
Expected: glob 列出所有 md 的 URI；read 返回 overview 全文（含「5 种语言」）。

- [ ] **Step 10: 提交**

```bash
cd "/Users/zhangdezhao/Documents/PatSnap挑战赛"
git add planA/code/sample_data planA/code/scripts
git commit -m "feat(planA): 样例语料 + 导入脚本，全链路验证 add/find/grep/glob"
```

> **阶段一完成标志**：OpenViking 服务能起、样例数据能进、四种检索 API 真实返回带来源的结果。此后即使真实语料未到，编排/skill/前端/评估都能基于样例推进。

---

### Task 4: ov_client + llm_client + config（封装层）

**Files:**
- Create: `planA/code/config.py`
- Create: `planA/code/ov_client.py`
- Create: `planA/code/llm_client.py`
- Test: `planA/code/tests/test_ov_client.py`

**Interfaces:**
- Produces:
  - `config.Settings`：从 `.env` 读 `OV_URL/OV_API_KEY/LLM_API_BASE/LLM_API_KEY/LLM_MODEL/LLM_SMALL_MODEL/CORPUS_DIR/COMPETITOR_URLS`。
  - `ov_client.OVClient(base_url, api_key)`，方法：
    - `find(query: str, target_uri: str = "", limit: int = 10) -> list[dict]`（每项 `{"uri","score","abstract","level"}`）
    - `grep(pattern: str, uri: str = "viking://resources", case_insensitive: bool = True, node_limit: int = 256) -> list[dict]`（每项 `{"uri","line","content"}`）
    - `glob(pattern: str, uri: str = "viking://resources") -> list[str]`
    - `read(uri: str) -> str`
    - `ls(uri: str, recursive: bool = False) -> list[dict]`
  - `llm_client.LLMClient(api_base, api_key, model, small_model)`，方法：`complete(system: str, user: str, small: bool = False) -> str`。
- Consumes: Task 1 依赖。所有 HTTP 端点用 Task 3 已验证的真实路径（`/api/v1/search/find`、`/api/v1/search/grep`、`/api/v1/search/glob`、`/api/v1/content/read`、`/api/v1/fs/ls`）。

- [ ] **Step 1: 写 config.py**

创建 `planA/code/config.py`：
```python
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    ov_url: str = os.getenv("OV_URL", "http://localhost:1933")
    ov_api_key: str = os.getenv("OV_API_KEY", "")
    llm_api_base: str = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    llm_small_model: str = os.getenv("LLM_SMALL_MODEL", "gpt-4o-mini")
    corpus_dir: str = os.getenv("CORPUS_DIR", "./sample_data")
    competitor_urls: str = os.getenv("COMPETITOR_URLS", "")


settings = Settings()
```

- [ ] **Step 2: 写失败测试 test_ov_client.py**

创建 `planA/code/tests/test_ov_client.py`（mock httpx，用 Task 3 里 `06-retrieval.md` 记录的真实响应形状）：
```python
from unittest.mock import MagicMock
from ov_client import OVClient


def test_find_parses_resources(mocker):
    fake = {
        "status": "ok",
        "result": {
            "memories": [],
            "resources": [
                {"uri": "viking://resources/products/eureka-overview.md",
                 "score": 0.83, "level": 2, "abstract": "5 种语言", "overview": None},
            ],
            "skills": [], "total": 1,
        },
    }
    resp = MagicMock(); resp.json.return_value = fake; resp.raise_for_status.return_value = None
    mocker.patch("httpx.Client.post", return_value=resp)

    client = OVClient("http://localhost:1933", "")
    results = client.find("Eureka 语言", target_uri="viking://resources/products")
    assert results[0]["uri"].endswith("eureka-overview.md")
    assert results[0]["score"] == 0.83


def test_grep_parses_matches(mocker):
    fake = {"status": "ok", "result": {
        "matches": [{"uri": "viking://resources/methodology/triz-intro.md",
                     "line": 1, "content": "TRIZ ..."}], "count": 1}}
    resp = MagicMock(); resp.json.return_value = fake; resp.raise_for_status.return_value = None
    mocker.patch("httpx.Client.post", return_value=resp)

    client = OVClient("http://localhost:1933", "")
    matches = client.grep("TRIZ")
    assert matches[0]["line"] == 1
    assert "TRIZ" in matches[0]["content"]
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd planA/code && source .venv/bin/activate && python -m pytest tests/test_ov_client.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'ov_client'`。

- [ ] **Step 4: 写 ov_client.py**

创建 `planA/code/ov_client.py`：
```python
import httpx


class OVClient:
    def __init__(self, base_url: str, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self._headers = {"X-API-Key": api_key} if api_key else {}
        self._client = httpx.Client(timeout=60.0)

    def _post(self, path: str, payload: dict) -> dict:
        resp = self._client.post(f"{self.base_url}{path}", json=payload, headers=self._headers)
        resp.raise_for_status()
        return resp.json().get("result", {})

    def _get(self, path: str, params: dict) -> dict:
        resp = self._client.get(f"{self.base_url}{path}", params=params, headers=self._headers)
        resp.raise_for_status()
        return resp.json().get("result", {})

    def find(self, query: str, target_uri: str = "", limit: int = 10) -> list[dict]:
        payload = {"query": query, "limit": limit}
        if target_uri:
            payload["target_uri"] = target_uri
        result = self._post("/api/v1/search/find", payload)
        out = []
        for r in result.get("resources", []):
            out.append({"uri": r["uri"], "score": r.get("score", 0.0),
                        "abstract": r.get("abstract", ""), "level": r.get("level", 0)})
        return out

    def grep(self, pattern: str, uri: str = "viking://resources",
             case_insensitive: bool = True, node_limit: int = 256) -> list[dict]:
        result = self._post("/api/v1/search/grep", {
            "uri": uri, "pattern": pattern,
            "case_insensitive": case_insensitive, "node_limit": node_limit})
        return [{"uri": m["uri"], "line": m.get("line", 0), "content": m.get("content", "")}
                for m in result.get("matches", [])]

    def glob(self, pattern: str, uri: str = "viking://resources") -> list[str]:
        result = self._post("/api/v1/search/glob", {"pattern": pattern, "uri": uri})
        return result.get("matches", [])

    def read(self, uri: str) -> str:
        result = self._get("/api/v1/content/read", {"uri": uri})
        return result if isinstance(result, str) else str(result)

    def ls(self, uri: str, recursive: bool = False) -> list[dict]:
        return self._get("/api/v1/fs/ls", {"uri": uri, "recursive": recursive}) or []
```

- [ ] **Step 5: 写 llm_client.py**

创建 `planA/code/llm_client.py`：
```python
from openai import OpenAI


class LLMClient:
    def __init__(self, api_base: str, api_key: str, model: str, small_model: str):
        self._client = OpenAI(base_url=api_base, api_key=api_key)
        self.model = model
        self.small_model = small_model

    def complete(self, system: str, user: str, small: bool = False) -> str:
        resp = self._client.chat.completions.create(
            model=self.small_model if small else self.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=0.2,
        )
        return resp.choices[0].message.content or ""
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_ov_client.py -v`
Expected: 2 passed。

- [ ] **Step 7: 集成冒烟（真服务，可选但推荐）**

Run（服务在跑、样例已导入时）：
```bash
python -c "from config import settings; from ov_client import OVClient; c=OVClient(settings.ov_url, settings.ov_api_key); print(c.find('Eureka 语言', 'viking://resources/products')[:2])"
```
Expected: 打印真实 find 结果（带 uri/score）。若失败，回到 Task 2 检查服务。

- [ ] **Step 8: 提交**

```bash
cd "/Users/zhangdezhao/Documents/PatSnap挑战赛"
git add planA/code/config.py planA/code/ov_client.py planA/code/llm_client.py planA/code/tests/test_ov_client.py
git commit -m "feat(planA): OpenViking HTTP 封装 + LLM 封装 + 配置层"
```

---

### Task 5: 查询理解与改写（口语 → 范围+改写+时间+专名）

**Files:**
- Create: `planA/code/orchestrator/__init__.py`（空）
- Create: `planA/code/orchestrator/query_understanding.py`
- Test: `planA/code/tests/test_query_understanding.py`

**Interfaces:**
- Produces: `understand(query: str, llm: LLMClient) -> QueryPlan`，其中
  ```python
  @dataclass
  class QueryPlan:
      rewritten: str          # 改写成检索友好的表述
      target_uri: str         # 圈定的检索范围，如 viking://resources/products
      is_comparison: bool     # 是否对比类
      proper_nouns: list[str] # 抽取的专名/型号，如 ["Eureka","TRIZ"]
      time_intent: str        # "latest" | "history" | "none"
  ```
- Consumes: `llm_client.LLMClient`（Task 4）。LLM 返回 JSON，本模块负责解析与兜底。

- [ ] **Step 1: 写失败测试**

创建 `planA/code/tests/test_query_understanding.py`：
```python
import json
from unittest.mock import MagicMock
from orchestrator.query_understanding import understand, QueryPlan


def test_understand_parses_llm_json():
    llm = MagicMock()
    llm.complete.return_value = json.dumps({
        "rewritten": "Eureka 支持的语言种类",
        "target_uri": "viking://resources/products",
        "is_comparison": False,
        "proper_nouns": ["Eureka"],
        "time_intent": "latest",
    })
    plan = understand("Eureka 这玩意儿支持几种语言啊", llm)
    assert isinstance(plan, QueryPlan)
    assert plan.target_uri == "viking://resources/products"
    assert plan.proper_nouns == ["Eureka"]
    assert plan.is_comparison is False


def test_understand_falls_back_on_bad_json():
    llm = MagicMock()
    llm.complete.return_value = "对不起我不是 JSON"
    plan = understand("随便问问", llm)
    # 兜底：范围回退到全库、原文即改写、无专名
    assert plan.target_uri == "viking://resources"
    assert plan.rewritten == "随便问问"
    assert plan.proper_nouns == []
    assert plan.is_comparison is False
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_query_understanding.py -v`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 写实现**

创建 `planA/code/orchestrator/query_understanding.py`：
```python
import json
from dataclasses import dataclass, field

_SYSTEM = """你是检索意图分析器。把运营/销售的口语问题解析成 JSON，字段：
- rewritten: 改写成检索友好的书面表述
- target_uri: 从这些选一个最贴合的范围前缀：
  viking://resources/methodology, viking://resources/products,
  viking://resources/style, viking://resources/competitors,
  viking://resources/roadmap；不确定就用 viking://resources
- is_comparison: 是否在做「我方 vs 竞品」的对比（true/false）
- proper_nouns: 问题里出现的专有名词/产品名/型号/方法论名的数组（如 Eureka、TRIZ）
- time_intent: latest（要最新口径）| history（问历史版本）| none
只输出 JSON，不要多余文字。"""


@dataclass
class QueryPlan:
    rewritten: str
    target_uri: str = "viking://resources"
    is_comparison: bool = False
    proper_nouns: list[str] = field(default_factory=list)
    time_intent: str = "none"


def understand(query: str, llm) -> QueryPlan:
    raw = llm.complete(_SYSTEM, query, small=True)
    try:
        data = json.loads(raw)
        return QueryPlan(
            rewritten=data.get("rewritten") or query,
            target_uri=data.get("target_uri") or "viking://resources",
            is_comparison=bool(data.get("is_comparison", False)),
            proper_nouns=list(data.get("proper_nouns", []) or []),
            time_intent=data.get("time_intent") or "none",
        )
    except (json.JSONDecodeError, TypeError):
        # LLM 没吐合法 JSON —— 安全兜底：全库、原文、无专名
        return QueryPlan(rewritten=query)
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_query_understanding.py -v`
Expected: 2 passed。

- [ ] **Step 5: 提交**

```bash
cd "/Users/zhangdezhao/Documents/PatSnap挑战赛"
git add planA/code/orchestrator/__init__.py planA/code/orchestrator/query_understanding.py planA/code/tests/test_query_understanding.py
git commit -m "feat(planA): 查询理解 — 口语转范围/改写/专名/时间意图，含JSON兜底"
```

---

### Task 6: 检索融合（find ∥ grep 并行 + 去重排序 + 附来源）

**Files:**
- Create: `planA/code/orchestrator/retrieval.py`
- Test: `planA/code/tests/test_retrieval.py`

**Interfaces:**
- Produces: `retrieve(plan: QueryPlan, ov: OVClient) -> list[Hit]`，其中
  ```python
  @dataclass
  class Hit:
      uri: str
      score: float
      abstract: str
      source: str  # "find" | "grep" | "both"
  ```
  规则：始终跑 `find`；当 `plan.proper_nouns` 非空时**并行**跑 `grep`（对每个专名）；两路结果按 uri 去重合并，`find∩grep` 的命中标 `source="both"` 且分数加权提升（+0.15），最终按 score 降序返回。
- Consumes: `QueryPlan`（Task 5）、`OVClient`（Task 4）。

- [ ] **Step 1: 写失败测试**

创建 `planA/code/tests/test_retrieval.py`：
```python
from unittest.mock import MagicMock
from orchestrator.retrieval import retrieve, Hit
from orchestrator.query_understanding import QueryPlan


def test_retrieve_merges_find_and_grep():
    ov = MagicMock()
    ov.find.return_value = [
        {"uri": "viking://resources/products/eureka-overview.md", "score": 0.8, "abstract": "5 种语言", "level": 2},
        {"uri": "viking://resources/products/other.md", "score": 0.4, "abstract": "别的", "level": 2},
    ]
    ov.grep.return_value = [
        {"uri": "viking://resources/products/eureka-overview.md", "line": 5, "content": "Eureka ..."},
    ]
    plan = QueryPlan(rewritten="Eureka 语言", target_uri="viking://resources/products",
                     proper_nouns=["Eureka"])
    hits = retrieve(plan, ov)
    # overview 同时被 find+grep 命中 → source=both，且排在最前
    assert hits[0].uri.endswith("eureka-overview.md")
    assert hits[0].source == "both"
    assert hits[0].score > 0.8  # 加权提升过


def test_retrieve_skips_grep_when_no_proper_nouns():
    ov = MagicMock()
    ov.find.return_value = [{"uri": "viking://resources/x.md", "score": 0.5, "abstract": "", "level": 2}]
    plan = QueryPlan(rewritten="随便问问", proper_nouns=[])
    hits = retrieve(plan, ov)
    ov.grep.assert_not_called()
    assert len(hits) == 1
    assert hits[0].source == "find"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_retrieval.py -v`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 写实现**

创建 `planA/code/orchestrator/retrieval.py`：
```python
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

_GREP_BOOST = 0.15


@dataclass
class Hit:
    uri: str
    score: float
    abstract: str
    source: str  # find | grep | both


def retrieve(plan, ov) -> list["Hit"]:
    # find 始终跑；proper_nouns 非空时并行 grep（每个专名一趟）
    with ThreadPoolExecutor(max_workers=4) as pool:
        find_future = pool.submit(ov.find, plan.rewritten, plan.target_uri)
        grep_futures = [pool.submit(ov.grep, pn, plan.target_uri or "viking://resources")
                        for pn in plan.proper_nouns]
        find_res = find_future.result()
        grep_uris: set[str] = set()
        for gf in grep_futures:
            for m in gf.result():
                grep_uris.add(m["uri"])

    by_uri: dict[str, Hit] = {}
    for r in find_res:
        by_uri[r["uri"]] = Hit(uri=r["uri"], score=r["score"],
                               abstract=r.get("abstract", ""), source="find")
    # grep 命中：已在 find 里的升级为 both 并加权；未在的作为纯 grep 命中补入
    for uri in grep_uris:
        if uri in by_uri:
            by_uri[uri].source = "both"
            by_uri[uri].score += _GREP_BOOST
        else:
            by_uri[uri] = Hit(uri=uri, score=_GREP_BOOST, abstract="", source="grep")

    return sorted(by_uri.values(), key=lambda h: h.score, reverse=True)
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_retrieval.py -v`
Expected: 2 passed。

- [ ] **Step 5: 提交**

```bash
cd "/Users/zhangdezhao/Documents/PatSnap挑战赛"
git add planA/code/orchestrator/retrieval.py planA/code/tests/test_retrieval.py
git commit -m "feat(planA): 检索融合 — find∥grep并行、去重、both加权排序"
```

---

### Task 7: 跨资源冲突标注（§7之二：权威性+时效裁决 + 曝光）

**Files:**
- Create: `planA/code/orchestrator/conflict.py`
- Test: `planA/code/tests/test_conflict.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass
  class SourceMeta:
      uri: str
      authority: int   # 权威等级：4官网/产品界面 > 3内部权威文档 > 2论文 > 1二手转述
      updated_at: str  # ISO 日期字符串，如 "2026-06"

  @dataclass
  class ConflictVerdict:
      primary: SourceMeta          # 选为主答案的来源
      others: list[SourceMeta]     # 未选中但要曝光的来源
      has_conflict: bool

  def parse_source_meta(uri: str, content: str) -> SourceMeta
  def adjudicate(sources: list[SourceMeta]) -> ConflictVerdict
  ```
  裁决规则（两层，对齐 spec §7之二）：① 先按 `authority` 降序；② 同权威按 `updated_at` 降序（新的赢）；③ 选出 `primary`，其余进 `others`；④ `has_conflict = len(sources) > 1`（同话题多来源即需曝光，哪怕结论碰巧一致也如实列出）。
- Consumes: 资源正文里的「> 来源：... · 更新于 ...」尾注（样例数据 Task 3 已按此格式写）。真实语料到位后，来源/时间若在别处，只需改 `parse_source_meta` 的解析规则。

**说明**：本任务只做「机制」，不做「自动判断两句话是否语义矛盾」——那是 spec 明确说业界未解决、我们不硬碰的部分。我们的机制是：同话题多来源时，按规则排出主答案 + 把其余来源如实曝光，不静默丢弃。

- [ ] **Step 1: 写失败测试**

创建 `planA/code/tests/test_conflict.py`：
```python
from orchestrator.conflict import parse_source_meta, adjudicate, SourceMeta


def test_parse_authority_and_time_from_footer():
    m1 = parse_source_meta(
        "viking://resources/products/eureka-overview.md",
        "...\n> 来源：官网产品页 · 更新于 2026-06\n")
    assert m1.authority == 4       # 官网 → 最高
    assert m1.updated_at == "2026-06"

    m2 = parse_source_meta(
        "viking://resources/products/eureka-langs-old.md",
        "...\n> 来源：内部销售培训 PPT · 更新于 2025-03\n")
    assert m2.authority == 3       # 内部文档
    assert m2.updated_at == "2025-03"


def test_adjudicate_prefers_authority_then_time():
    official = SourceMeta("uri-official", authority=4, updated_at="2026-06")
    internal = SourceMeta("uri-internal", authority=3, updated_at="2025-03")
    verdict = adjudicate([internal, official])
    assert verdict.primary.uri == "uri-official"   # 权威高的赢
    assert verdict.has_conflict is True
    assert verdict.others[0].uri == "uri-internal"


def test_adjudicate_same_authority_prefers_newer():
    old = SourceMeta("uri-old", authority=3, updated_at="2025-03")
    new = SourceMeta("uri-new", authority=3, updated_at="2026-01")
    verdict = adjudicate([old, new])
    assert verdict.primary.uri == "uri-new"        # 同权威，新的赢


def test_single_source_no_conflict():
    only = SourceMeta("uri-only", authority=4, updated_at="2026-06")
    verdict = adjudicate([only])
    assert verdict.has_conflict is False
    assert verdict.others == []
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_conflict.py -v`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 写实现**

创建 `planA/code/orchestrator/conflict.py`：
```python
import re
from dataclasses import dataclass, field

# 权威性分级：官网/产品界面 > 内部权威文档 > 论文 > 二手转述
_AUTHORITY_RULES = [
    (4, ["官网", "产品页", "产品界面"]),
    (3, ["内部", "培训", "白皮书", "PPT"]),
    (2, ["论文", "paper"]),
    (1, ["转述", "博客", "新闻"]),
]
_FOOTER_RE = re.compile(r"来源[：:]\s*(?P<src>.+?)\s*[·•]\s*(?:更新于|抓取于)\s*(?P<date>[\d\-]+)")


@dataclass
class SourceMeta:
    uri: str
    authority: int
    updated_at: str


@dataclass
class ConflictVerdict:
    primary: SourceMeta
    others: list = field(default_factory=list)
    has_conflict: bool = False


def _authority_of(source_text: str) -> int:
    for level, keywords in _AUTHORITY_RULES:
        if any(k in source_text for k in keywords):
            return level
    return 1  # 默认按最低（二手）处理，宁可低估不高估


def parse_source_meta(uri: str, content: str) -> SourceMeta:
    m = _FOOTER_RE.search(content)
    if not m:
        return SourceMeta(uri=uri, authority=1, updated_at="")
    return SourceMeta(uri=uri, authority=_authority_of(m.group("src")),
                      updated_at=m.group("date"))


def adjudicate(sources: list) -> ConflictVerdict:
    # ① 权威降序 ② 同权威按时间降序（新的赢）
    ranked = sorted(sources, key=lambda s: (s.authority, s.updated_at), reverse=True)
    primary = ranked[0]
    others = ranked[1:]
    return ConflictVerdict(primary=primary, others=others,
                           has_conflict=len(sources) > 1)
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_conflict.py -v`
Expected: 4 passed。

- [ ] **Step 5: 集成验证（真数据，验证冲突夹具生效）**

Run（服务在跑、样例已导入）：
```bash
python -c "
from config import settings
from ov_client import OVClient
from orchestrator.conflict import parse_source_meta, adjudicate
ov = OVClient(settings.ov_url, settings.ov_api_key)
uris = ov.glob('products/*.md', 'viking://resources')
metas = [parse_source_meta(u, ov.read(u)) for u in uris if 'eureka' in u.lower()]
v = adjudicate(metas)
print('主答案来源:', v.primary.uri, '权威', v.primary.authority, v.primary.updated_at)
print('需曝光的其他来源:', [(o.uri, o.updated_at) for o in v.others])
print('有冲突:', v.has_conflict)
"
```
Expected: 主答案是 `eureka-overview.md`（官网/2026-06），others 含 `eureka-langs-old.md`（内部/2025-03），has_conflict=True。**这证明「5 种语言」会作为主口径、「3 种语言」被曝光而非丢弃。**

- [ ] **Step 6: 提交**

```bash
cd "/Users/zhangdezhao/Documents/PatSnap挑战赛"
git add planA/code/orchestrator/conflict.py planA/code/tests/test_conflict.py
git commit -m "feat(planA): 跨资源冲突标注 — 权威+时效裁决、曝光而非静默覆盖(§7之二)"
```

---

### Task 8: 竞品对比编排（分解 + 多源召回 + 维度对齐）

**Files:**
- Create: `planA/code/orchestrator/comparison.py`
- Test: `planA/code/tests/test_comparison.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass
  class ComparisonRow:
      dimension: str        # 对比维度，如「多语言」
      ours: str             # 我方在该维度的表述（带来源），缺失填「未找到」
      ours_uri: str
      theirs: str           # 竞品在该维度的表述，缺失填「未在资料中找到」
      theirs_uri: str

  def compare(dimensions: list[str], our_uri: str, competitor_uri: str,
              ov: OVClient) -> list[ComparisonRow]
  ```
  逻辑：对每个维度分别在「我方 target_uri」和「竞品 target_uri」跑 `find`，各取 top1 作为该维度表述；任一侧无命中则明确标「未找到」，绝不让模型编。
- Consumes: `OVClient`（Task 4）。维度清单由调用方（server 或 skill）给出；缺失竞品资料时由 Task 9 补实时抓取。

- [ ] **Step 1: 写失败测试**

创建 `planA/code/tests/test_comparison.py`：
```python
from unittest.mock import MagicMock
from orchestrator.comparison import compare, ComparisonRow


def test_compare_aligns_by_dimension():
    ov = MagicMock()
    def fake_find(query, target_uri, limit=10):
        if "products" in target_uri:
            return [{"uri": "viking://resources/products/eureka-overview.md",
                     "score": 0.8, "abstract": "支持 5 种语言", "level": 2}]
        return [{"uri": "viking://resources/competitors/competitor-a.md",
                 "score": 0.7, "abstract": "支持 2 种语言", "level": 2}]
    ov.find.side_effect = fake_find
    rows = compare(["多语言"], "viking://resources/products",
                   "viking://resources/competitors", ov)
    assert rows[0].dimension == "多语言"
    assert "5 种" in rows[0].ours
    assert "2 种" in rows[0].theirs


def test_compare_marks_missing_side():
    ov = MagicMock()
    def fake_find(query, target_uri, limit=10):
        if "products" in target_uri:
            return [{"uri": "u-ours", "score": 0.8, "abstract": "我方有", "level": 2}]
        return []  # 竞品侧无命中
    ov.find.side_effect = fake_find
    rows = compare(["价格"], "viking://resources/products",
                   "viking://resources/competitors", ov)
    assert rows[0].theirs == "未在资料中找到"
    assert rows[0].theirs_uri == ""
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_comparison.py -v`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 写实现**

创建 `planA/code/orchestrator/comparison.py`：
```python
from dataclasses import dataclass

_MISSING = "未在资料中找到"


@dataclass
class ComparisonRow:
    dimension: str
    ours: str
    ours_uri: str
    theirs: str
    theirs_uri: str


def _top(ov, dimension: str, target_uri: str):
    hits = ov.find(dimension, target_uri, limit=3)
    if not hits:
        return _MISSING, ""
    return hits[0].get("abstract") or "", hits[0]["uri"]


def compare(dimensions: list[str], our_uri: str, competitor_uri: str, ov) -> list[ComparisonRow]:
    rows = []
    for dim in dimensions:
        ours, ours_uri = _top(ov, dim, our_uri)
        theirs, theirs_uri = _top(ov, dim, competitor_uri)
        rows.append(ComparisonRow(dimension=dim, ours=ours, ours_uri=ours_uri,
                                  theirs=theirs, theirs_uri=theirs_uri))
    return rows
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_comparison.py -v`
Expected: 2 passed。

- [ ] **Step 5: 提交**

```bash
cd "/Users/zhangdezhao/Documents/PatSnap挑战赛"
git add planA/code/orchestrator/comparison.py planA/code/tests/test_comparison.py
git commit -m "feat(planA): 竞品对比编排 — 维度分解、双源召回、缺失明确标注"
```

---

### Task 9: 竞品 URL 实时抓取（trafilatura 去噪 + 维度抽取）

**Files:**
- Create: `planA/code/orchestrator/competitor_fetch.py`
- Test: `planA/code/tests/test_competitor_fetch.py`

**Interfaces:**
- Produces:
  ```python
  def fetch_clean(url: str, http_get=None) -> str  # 抓取 + trafilatura 去噪成纯文本
  def extract_dimensions(clean_text: str, dimensions: list[str], llm) -> dict[str, str]
      # 按「我方已知维度」逐项抽取竞品信息；缺失填「未在该页找到」，不猜
  ```
- Consumes: `trafilatura`、`LLMClient`（Task 4）。`http_get` 可注入以便测试。
- 安全边界：只抓公开页面、不外传私域内容；抽取结果附 `source_url + 抓取时间`（由调用方附加）。

- [ ] **Step 1: 写失败测试**

创建 `planA/code/tests/test_competitor_fetch.py`：
```python
import json
from unittest.mock import MagicMock
from orchestrator.competitor_fetch import fetch_clean, extract_dimensions


def test_fetch_clean_strips_html(mocker):
    html = "<html><body><nav>菜单</nav><article><p>竞品B 支持 4 种语言</p></article></body></html>"
    fake_get = MagicMock(return_value=html)
    mocker.patch("trafilatura.extract", return_value="竞品B 支持 4 种语言")
    text = fetch_clean("https://example.com/product", http_get=fake_get)
    assert "4 种语言" in text
    assert "菜单" not in text


def test_extract_dimensions_marks_missing():
    llm = MagicMock()
    llm.complete.return_value = json.dumps({"多语言": "支持 4 种语言", "价格": "未在该页找到"})
    result = extract_dimensions("竞品B 支持 4 种语言", ["多语言", "价格"], llm)
    assert result["多语言"] == "支持 4 种语言"
    assert result["价格"] == "未在该页找到"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_competitor_fetch.py -v`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 写实现**

创建 `planA/code/orchestrator/competitor_fetch.py`：
```python
import json
import httpx
import trafilatura

_SYSTEM = """你是竞品资料抽取器。给你一段竞品网页正文和一组对比维度，
对每个维度抽取竞品在该维度的表述。严格要求：
- 页面里找不到该维度信息时，值填「未在该页找到」，绝对不要猜测或编造。
- 只输出 JSON：{维度: 表述}，不要多余文字。"""


def fetch_clean(url: str, http_get=None) -> str:
    if http_get is None:
        def http_get(u):
            return httpx.get(u, timeout=30.0, follow_redirects=True).text
    html = http_get(url)
    extracted = trafilatura.extract(html) or ""
    return extracted


def extract_dimensions(clean_text: str, dimensions: list[str], llm) -> dict:
    user = f"对比维度：{dimensions}\n\n竞品网页正文：\n{clean_text[:6000]}"
    raw = llm.complete(_SYSTEM, user)
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        data = {}
    # 保证每个维度都有值，缺的补「未在该页找到」
    return {d: data.get(d, "未在该页找到") for d in dimensions}
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_competitor_fetch.py -v`
Expected: 2 passed。

- [ ] **Step 5: 写降级档预置结果**

创建 `planA/code/fallback/comparison.json`（现场实时抓取失败时回退，答辩不翻车）：
```json
{
  "dimensions": ["多语言", "价格"],
  "rows": [
    {"dimension": "多语言", "ours": "支持 5 种语言（中英日德韩）", "ours_uri": "viking://resources/products/eureka-overview.md", "theirs": "支持 2 种语言（中英）", "theirs_uri": "viking://resources/competitors/competitor-a.md"},
    {"dimension": "价格", "ours": "未在资料中找到", "ours_uri": "", "theirs": "主打价格优势", "theirs_uri": "viking://resources/competitors/competitor-a.md"}
  ],
  "note": "此为预置降级结果，实时抓取失败时使用"
}
```

- [ ] **Step 6: 提交**

```bash
cd "/Users/zhangdezhao/Documents/PatSnap挑战赛"
git add planA/code/orchestrator/competitor_fetch.py planA/code/tests/test_competitor_fetch.py planA/code/fallback/comparison.json
git commit -m "feat(planA): 竞品实时抓取 — trafilatura去噪+维度抽取+缺失不猜+降级档"
```

---

### Task 10: 生成组装（料 + 来源 + 时效 → 附来源答案）

**Files:**
- Create: `planA/code/orchestrator/generation.py`
- Test: `planA/code/tests/test_generation.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass
  class Answer:
      text: str                 # 生成的答案正文
      sources: list[dict]       # [{"uri","updated_at"}]，每条事实的来源+时效
      conflict_note: str        # 冲突曝光提示，无冲突则空串
      unverified: list[str]     # 无来源支撑、标「待核实」的点

  def answer_tech_qa(plan, hits, verdict, ov, llm) -> Answer
  def generate_promo(topic: str, prompt: str, hits, style_samples, llm) -> Answer
  ```
  - `answer_tech_qa`：读取主答案来源的 L2 内容 → 组装 system（强制「只用给定料、无料标待核实、附来源」）→ 调 LLM → 若 `verdict.has_conflict` 则拼 `conflict_note`（曝光另一说法 + 来源 + 时效）。
  - `generate_promo`：注入 `style_samples` 作风格样本 + 用户 prompt → 生成富文本 + 来源列表 + 待核实项。风格由 prompt 主导，不写死模板。
- Consumes: Task 5/6/7 的产物 + `OVClient` + `LLMClient`。

- [ ] **Step 1: 写失败测试**

创建 `planA/code/tests/test_generation.py`：
```python
from unittest.mock import MagicMock
from orchestrator.generation import answer_tech_qa, Answer
from orchestrator.retrieval import Hit
from orchestrator.conflict import SourceMeta, ConflictVerdict


def test_answer_appends_conflict_note():
    ov = MagicMock()
    ov.read.return_value = "Eureka 支持 5 种语言。\n> 来源：官网产品页 · 更新于 2026-06"
    llm = MagicMock()
    llm.complete.return_value = "Eureka 目前支持 5 种语言（中英日德韩）。"
    hits = [Hit(uri="viking://resources/products/eureka-overview.md", score=0.9,
                abstract="5 种语言", source="both")]
    verdict = ConflictVerdict(
        primary=SourceMeta("viking://resources/products/eureka-overview.md", 4, "2026-06"),
        others=[SourceMeta("viking://resources/products/eureka-langs-old.md", 3, "2025-03")],
        has_conflict=True)
    ans = answer_tech_qa(plan=None, hits=hits, verdict=verdict, ov=ov, llm=llm)
    assert isinstance(ans, Answer)
    assert "5 种语言" in ans.text
    assert ans.conflict_note != ""             # 有冲突 → 必须曝光
    assert "2025-03" in ans.conflict_note      # 曝光旧来源的时效
    assert ans.sources[0]["updated_at"] == "2026-06"


def test_answer_no_conflict_no_note():
    ov = MagicMock()
    ov.read.return_value = "TRIZ 是创新方法论。\n> 来源：内部方法论培训资料 · 更新于 2026-05"
    llm = MagicMock()
    llm.complete.return_value = "TRIZ 是一套系统化创新方法论。"
    hits = [Hit(uri="viking://resources/methodology/triz-intro.md", score=0.8,
                abstract="", source="find")]
    verdict = ConflictVerdict(
        primary=SourceMeta("viking://resources/methodology/triz-intro.md", 3, "2026-05"),
        others=[], has_conflict=False)
    ans = answer_tech_qa(plan=None, hits=hits, verdict=verdict, ov=ov, llm=llm)
    assert ans.conflict_note == ""
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_generation.py -v`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 写实现**

创建 `planA/code/orchestrator/generation.py`：
```python
from dataclasses import dataclass, field
from orchestrator.conflict import parse_source_meta

_QA_SYSTEM = """你是智慧芽技术知识助手，服务运营/销售。铁律：
1. 只根据「给定资料」回答，不得使用资料外的知识。
2. 资料里没有支撑的点，明说「待核实」，绝不编造。
3. 用大白话，面向不懂技术的运营/销售。
只输出答案正文，不要复述这些规则。"""

_PROMO_SYSTEM = """你是智慧芽宣传文案助手。要求：
1. 事实只用「给定资料」，无资料支撑的点标「待核实」。
2. 参照「风格样本」的语气与表达，但文体听用户 prompt 的。
只输出文案正文。"""


@dataclass
class Answer:
    text: str
    sources: list = field(default_factory=list)
    conflict_note: str = ""
    unverified: list = field(default_factory=list)


def answer_tech_qa(plan, hits, verdict, ov, llm) -> Answer:
    primary_uri = verdict.primary.uri
    content = ov.read(primary_uri)
    user = f"给定资料（来源 {primary_uri}）：\n{content}\n\n请回答用户的技术问题。"
    text = llm.complete(_QA_SYSTEM, user)

    sources = [{"uri": verdict.primary.uri, "updated_at": verdict.primary.updated_at}]
    conflict_note = ""
    if verdict.has_conflict and verdict.others:
        parts = [f"另有资料表述不同：{o.uri}（更新于 {o.updated_at or '未知'}）" for o in verdict.others]
        conflict_note = "；".join(parts) + "。当前以更权威/更新的来源为准。"
    return Answer(text=text, sources=sources, conflict_note=conflict_note)


def generate_promo(topic: str, prompt: str, hits, style_samples, llm) -> Answer:
    material = "\n\n".join(h.abstract for h in hits if h.abstract)
    style = "\n\n".join(style_samples)
    user = (f"选题：{topic}\n用户要求：{prompt}\n\n"
            f"事实资料：\n{material}\n\n风格样本：\n{style}")
    text = llm.complete(_PROMO_SYSTEM, user)
    sources = [{"uri": h.uri, "updated_at": ""} for h in hits]
    return Answer(text=text, sources=sources)
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_generation.py -v`
Expected: 2 passed。

- [ ] **Step 5: 提交**

```bash
cd "/Users/zhangdezhao/Documents/PatSnap挑战赛"
git add planA/code/orchestrator/generation.py planA/code/tests/test_generation.py
git commit -m "feat(planA): 生成组装 — 强制附来源/待核实、冲突曝光、风格样本注入"
```

---

### Task 11: FastAPI 后端（意图分流 + 降级 + 密钥代理）

**Files:**
- Create: `planA/code/server.py`
- Create: `planA/code/fallback/tech_qa.json`
- Test: `planA/code/tests/test_server.py`

**Interfaces:**
- Produces:
  - `GET /api/health` → `{"status":"ok","ov":<bool>}`（探测 OV 服务是否可达）。
  - `POST /api/chat` body `{"message": str, "mode": "auto|qa|comparison|promo", "competitor_url": str?}` → `{"text","sources","conflict_note","comparison_rows"?,"degraded":bool}`。
  - 内部 `build_deps()` 装配 `OVClient`/`LLMClient`（读 `settings`），便于测试注入。
  - 挂载 `web/` 为静态目录，根路径返回 `index.html`。
- **安全**：大模型/OV 的 key 只在后端用（来自 `.env`），前端永不接触。这是 spec §12 明确的护栏。
- Consumes: Task 4-10 全部编排模块。

**降级逻辑**：任一编排步骤抛异常（OV 不可达、LLM 超时、抓取失败）→ 捕获 → 读对应 `fallback/*.json` → 返回 `degraded: true`。保证现场链路崩了也有东西可演示。

- [ ] **Step 1: 写技术问答降级档**

创建 `planA/code/fallback/tech_qa.json`：
```json
{
  "text": "Eureka 目前支持 5 种语言的专利文献检索：中文、英文、日文、德文、韩文。",
  "sources": [{"uri": "viking://resources/products/eureka-overview.md", "updated_at": "2026-06"}],
  "conflict_note": "另有资料表述不同：viking://resources/products/eureka-langs-old.md（更新于 2025-03，记录为 3 种语言）。当前以更权威/更新的来源为准。",
  "note": "预置降级结果，实时链路失败时使用"
}
```

- [ ] **Step 2: 写失败测试**

创建 `planA/code/tests/test_server.py`：
```python
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import server


def _client_with_stubs(qa_answer):
    ov = MagicMock()
    llm = MagicMock()
    server.app.dependency_overrides = {}
    server._DEPS = {"ov": ov, "llm": llm}  # 测试期直接塞依赖
    return TestClient(server.app), ov, llm


def test_health_ok(mocker):
    mocker.patch.object(server, "_probe_ov", return_value=True)
    client = TestClient(server.app)
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_chat_qa_returns_answer(mocker):
    # 让整条 qa 管线返回一个可控 Answer
    from orchestrator.generation import Answer
    mocker.patch.object(server, "_run_qa",
                        return_value=Answer(text="支持 5 种语言",
                                            sources=[{"uri": "u", "updated_at": "2026-06"}],
                                            conflict_note="另有资料..."))
    client = TestClient(server.app)
    r = client.post("/api/chat", json={"message": "Eureka 支持几种语言", "mode": "qa"})
    assert r.status_code == 200
    body = r.json()
    assert "5 种语言" in body["text"]
    assert body["degraded"] is False


def test_chat_degrades_on_error(mocker):
    mocker.patch.object(server, "_run_qa", side_effect=RuntimeError("OV down"))
    client = TestClient(server.app)
    r = client.post("/api/chat", json={"message": "任意", "mode": "qa"})
    assert r.status_code == 200
    assert r.json()["degraded"] is True
    assert "5 种语言" in r.json()["text"]  # 来自 fallback/tech_qa.json
```

- [ ] **Step 3: 运行确认失败**

Run: `python -m pytest tests/test_server.py -v`
Expected: FAIL（server 模块不存在 / 属性缺失）。

- [ ] **Step 4: 写 server.py**

创建 `planA/code/server.py`：
```python
import json
import os
import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import settings
from ov_client import OVClient
from llm_client import LLMClient
from orchestrator.query_understanding import understand
from orchestrator.retrieval import retrieve
from orchestrator.conflict import parse_source_meta, adjudicate
from orchestrator.comparison import compare
from orchestrator.generation import answer_tech_qa, generate_promo, Answer

app = FastAPI(title="智慧芽技术知识助手")
_DEPS: dict = {}
_HERE = os.path.dirname(__file__)


def build_deps():
    if "ov" not in _DEPS:
        _DEPS["ov"] = OVClient(settings.ov_url, settings.ov_api_key)
        _DEPS["llm"] = LLMClient(settings.llm_api_base, settings.llm_api_key,
                                 settings.llm_model, settings.llm_small_model)
    return _DEPS["ov"], _DEPS["llm"]


def _fallback(name: str) -> dict:
    with open(os.path.join(_HERE, "fallback", name), encoding="utf-8") as f:
        return json.load(f)


def _probe_ov() -> bool:
    try:
        r = httpx.get(f"{settings.ov_url}/health", timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False


class ChatReq(BaseModel):
    message: str
    mode: str = "auto"
    competitor_url: str | None = None


def _run_qa(message: str) -> Answer:
    ov, llm = build_deps()
    plan = understand(message, llm)
    hits = retrieve(plan, ov)
    metas = [parse_source_meta(h.uri, ov.read(h.uri)) for h in hits[:5]]
    verdict = adjudicate(metas) if metas else None
    return answer_tech_qa(plan, hits, verdict, ov, llm)


@app.get("/api/health")
def health():
    return {"status": "ok", "ov": _probe_ov()}


@app.post("/api/chat")
def chat(req: ChatReq):
    try:
        ans = _run_qa(req.message)
        return {"text": ans.text, "sources": ans.sources,
                "conflict_note": ans.conflict_note, "degraded": False}
    except Exception:
        fb = _fallback("tech_qa.json")
        return {"text": fb["text"], "sources": fb["sources"],
                "conflict_note": fb.get("conflict_note", ""), "degraded": True}


# 静态前端（Task 12 产出 web/index.html 后生效）
_web = os.path.join(_HERE, "web")
if os.path.isdir(_web):
    app.mount("/static", StaticFiles(directory=_web), name="static")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(_web, "index.html"))
```

- [ ] **Step 5: 运行确认通过**

Run: `python -m pytest tests/test_server.py -v`
Expected: 3 passed。

- [ ] **Step 6: 集成冒烟（真起后端）**

Run（OV 服务在跑、样例已导入、`.env` 已填 LLM key）：
```bash
cd planA/code && source .venv/bin/activate
uvicorn server:app --port 8000 &
sleep 3
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" \
  -d '{"message":"Eureka 支持几种语言","mode":"qa"}'
kill %1
```
Expected: health 返回 `{"status":"ok","ov":true}`；chat 返回含「5 种语言」的答案 + sources + conflict_note（曝光「3 种语言」旧口径）。

- [ ] **Step 7: 提交**

```bash
cd "/Users/zhangdezhao/Documents/PatSnap挑战赛"
git add planA/code/server.py planA/code/fallback/tech_qa.json planA/code/tests/test_server.py
git commit -m "feat(planA): FastAPI后端 — 意图分流、QA管线、降级档、密钥后端代理"
```

---

### Task 12: 后端补全竞品对比与宣传生成端点

**Files:**
- Modify: `planA/code/server.py`（在 Task 11 基础上加 comparison/promo 分流）
- Modify: `planA/code/tests/test_server.py`（补测试）

**Interfaces:**
- Produces: `POST /api/chat` 支持 `mode` 为 `comparison` 和 `promo`：
  - `comparison`：从 message 用 LLM 提取维度 → 若给了 `competitor_url` 走实时抓取补竞品侧，否则用预存竞品 → 返回 `comparison_rows`。失败回退 `fallback/comparison.json`。
  - `promo`：检索料 + 读 `style/` 风格样本 → `generate_promo` → 返回富文本 + 来源。
- Consumes: Task 8（compare）、Task 9（competitor_fetch）、Task 10（generate_promo）。

- [ ] **Step 1: 写失败测试（补进 test_server.py）**

在 `planA/code/tests/test_server.py` 追加：
```python
def test_chat_comparison_returns_rows(mocker):
    from orchestrator.comparison import ComparisonRow
    mocker.patch.object(server, "_run_comparison",
                        return_value=[ComparisonRow("多语言", "5 种", "u1", "2 种", "u2")])
    client = TestClient(server.app)
    r = client.post("/api/chat", json={"message": "Eureka 多语言 vs 竞品A", "mode": "comparison"})
    assert r.status_code == 200
    rows = r.json()["comparison_rows"]
    assert rows[0]["dimension"] == "多语言"
    assert rows[0]["ours"] == "5 种"


def test_chat_comparison_degrades(mocker):
    mocker.patch.object(server, "_run_comparison", side_effect=RuntimeError("fetch fail"))
    client = TestClient(server.app)
    r = client.post("/api/chat", json={"message": "对比", "mode": "comparison"})
    assert r.json()["degraded"] is True
    assert r.json()["comparison_rows"][0]["dimension"] == "多语言"  # 来自 fallback
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_server.py -v`
Expected: 新增 2 条 FAIL（`_run_comparison` 不存在）。

- [ ] **Step 3: 在 server.py 加实现**

在 `planA/code/server.py` 的 `_run_qa` 后面加：
```python
_DEFAULT_DIMENSIONS = ["多语言", "价格", "检索能力"]


def _extract_dimensions(message: str, llm) -> list[str]:
    import json as _json
    raw = llm.complete(
        "从用户的对比问题里抽取要对比的维度，只输出 JSON 数组，如 [\"多语言\",\"价格\"]。",
        message, small=True)
    try:
        dims = _json.loads(raw)
        return dims if isinstance(dims, list) and dims else _DEFAULT_DIMENSIONS
    except Exception:
        return _DEFAULT_DIMENSIONS


def _run_comparison(message: str, competitor_url: str | None) -> list:
    ov, llm = build_deps()
    dims = _extract_dimensions(message, llm)
    our_uri = "viking://resources/products"
    if competitor_url:
        from orchestrator.competitor_fetch import fetch_clean, extract_dimensions
        from orchestrator.comparison import ComparisonRow
        clean = fetch_clean(competitor_url)
        theirs = extract_dimensions(clean, dims, llm)
        rows = []
        for d in dims:
            ours = ov.find(d, our_uri, limit=1)
            rows.append(ComparisonRow(
                dimension=d,
                ours=(ours[0]["abstract"] if ours else "未在资料中找到"),
                ours_uri=(ours[0]["uri"] if ours else ""),
                theirs=theirs.get(d, "未在该页找到"),
                theirs_uri=competitor_url))
        return rows
    return compare(dims, our_uri, "viking://resources/competitors", ov)


def _run_promo(message: str) -> Answer:
    ov, llm = build_deps()
    hits = retrieve(understand(message, llm), ov)
    samples = []
    for uri in ov.glob("style/*.md", "viking://resources"):
        samples.append(ov.read(uri))
    return generate_promo(topic=message, prompt=message, hits=hits,
                          style_samples=samples, llm=llm)
```
并把 `chat` 端点改为按 mode 分流：
```python
@app.post("/api/chat")
def chat(req: ChatReq):
    mode = req.mode
    try:
        if mode == "comparison":
            rows = _run_comparison(req.message, req.competitor_url)
            return {"text": "", "sources": [], "conflict_note": "",
                    "comparison_rows": [r.__dict__ for r in rows], "degraded": False}
        if mode == "promo":
            ans = _run_promo(req.message)
            return {"text": ans.text, "sources": ans.sources,
                    "conflict_note": "", "degraded": False}
        ans = _run_qa(req.message)  # auto/qa
        return {"text": ans.text, "sources": ans.sources,
                "conflict_note": ans.conflict_note, "degraded": False}
    except Exception:
        if mode == "comparison":
            fb = _fallback("comparison.json")
            return {"text": "", "sources": [], "conflict_note": "",
                    "comparison_rows": fb["rows"], "degraded": True}
        fb = _fallback("tech_qa.json")
        return {"text": fb["text"], "sources": fb["sources"],
                "conflict_note": fb.get("conflict_note", ""), "degraded": True}
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_server.py -v`
Expected: 全部 passed（含新增 2 条）。

- [ ] **Step 5: 提交**

```bash
cd "/Users/zhangdezhao/Documents/PatSnap挑战赛"
git add planA/code/server.py planA/code/tests/test_server.py
git commit -m "feat(planA): 后端补全竞品对比/宣传生成端点，含实时抓取与降级"
```

---

### Task 13: 对话网页前端（接真实后端）

**Files:**
- Create: `planA/code/web/index.html`

**Interfaces:**
- Consumes: Task 11/12 的 `POST /api/chat` 与 `GET /api/health`。
- 复用 `planA/demo原型/产品原型-对话网页.html` 的视觉风格（配色变量、布局），但**现有原型是纯静态无 fetch**，本任务写一个真的会调后端的版本。

**说明**：左侧三入口（技术问答/竞品对比/宣传生成）对应设置 `mode`；对话区渲染答案 + 来源 URI + 时效 + 冲突提示；竞品对比渲染成对齐表格；`degraded` 时顶部显示「降级演示」小标。

- [ ] **Step 1: 写 index.html**

创建 `planA/code/web/index.html`（核心结构 + 真实 fetch；样式可从 demo原型 复制 `:root` 变量与主要 class）：
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>智慧芽技术知识助手</title>
<style>
  :root{--bg:#efe9df;--ink:#2a2d29;--muted:#847f76;--paper:#fffaf3;--dark:#2f342f;--green:#4a7a5f;--line:#2a2d29;--soft:rgba(42,45,41,.13)}
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,"PingFang SC",Arial,sans-serif;background:var(--bg);color:var(--ink);display:flex;height:100vh}
  .side{width:230px;background:#f8f1e8;border-right:1.5px solid var(--soft);padding:16px}
  .side h1{font-size:15px;margin-bottom:14px}
  .side button{display:block;width:100%;text-align:left;margin:6px 0;padding:10px;border:1px solid var(--soft);border-radius:9px;background:#fff;cursor:pointer;font-size:13.5px}
  .side button.on{background:var(--dark);color:#fff}
  .main{flex:1;display:flex;flex-direction:column}
  .banner{padding:6px 16px;background:#c06148;color:#fff;font-size:12px;display:none}
  .banner.show{display:block}
  .chat{flex:1;overflow-y:auto;padding:20px}
  .msg{max-width:760px;margin:10px 0;padding:12px 14px;border-radius:12px;line-height:1.6}
  .msg.user{background:#fff;border:1px solid var(--soft);margin-left:auto}
  .msg.bot{background:var(--paper);border:1.5px solid var(--line)}
  .src{font-size:12px;color:var(--muted);margin-top:8px}
  .conflict{font-size:12.5px;color:#b98a3c;margin-top:6px;border-left:3px solid #b98a3c;padding-left:8px}
  table{border-collapse:collapse;margin-top:8px;width:100%}
  th,td{border:1px solid var(--soft);padding:7px 9px;font-size:13px;text-align:left}
  .inbar{display:flex;gap:8px;padding:14px;border-top:1.5px solid var(--soft);background:#fff}
  .inbar input{flex:1;padding:11px;border:1.5px solid var(--soft);border-radius:10px;font-size:14px}
  .inbar button{padding:11px 20px;background:var(--dark);color:#fff;border:none;border-radius:10px;cursor:pointer}
</style>
</head>
<body>
  <aside class="side">
    <h1>智慧芽技术知识助手</h1>
    <button data-mode="qa" class="on">💬 技术问答</button>
    <button data-mode="comparison">⚔️ 竞品对比</button>
    <button data-mode="promo">✍️ 宣传生成</button>
  </aside>
  <main class="main">
    <div class="banner" id="banner">⚠️ 降级演示：实时链路不可用，展示预置结果</div>
    <div class="chat" id="chat"></div>
    <div class="inbar">
      <input id="input" placeholder="用大白话提问，或粘贴竞品网址…" />
      <button id="send">发送</button>
    </div>
  </main>
<script>
let mode = "qa";
document.querySelectorAll(".side button").forEach(b => b.onclick = () => {
  document.querySelectorAll(".side button").forEach(x => x.classList.remove("on"));
  b.classList.add("on"); mode = b.dataset.mode;
});
const chat = document.getElementById("chat");
function bubble(cls, html){ const d = document.createElement("div"); d.className = "msg " + cls; d.innerHTML = html; chat.appendChild(d); chat.scrollTop = chat.scrollHeight; return d; }
function urlRe(s){ return /^https?:\/\//.test(s.trim()); }
document.getElementById("send").onclick = send;
document.getElementById("input").addEventListener("keydown", e => { if (e.key === "Enter") send(); });
async function send(){
  const inp = document.getElementById("input"); const text = inp.value.trim(); if (!text) return;
  bubble("user", text); inp.value = "";
  const loading = bubble("bot", "思考中…");
  const body = { message: text, mode };
  if (mode === "comparison" && urlRe(text)) body.competitor_url = text;
  try {
    const r = await fetch("/api/chat", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(body) });
    const data = await r.json();
    document.getElementById("banner").classList.toggle("show", !!data.degraded);
    loading.innerHTML = render(data);
  } catch (e) { loading.innerHTML = "请求失败：" + e; }
}
function render(d){
  if (d.comparison_rows) {
    let t = "<table><tr><th>维度</th><th>我方</th><th>竞品</th></tr>";
    d.comparison_rows.forEach(row => t += `<tr><td>${row.dimension}</td><td>${row.ours||""}</td><td>${row.theirs||""}</td></tr>`);
    return t + "</table>";
  }
  let html = (d.text || "").replace(/\n/g, "<br>");
  if (d.conflict_note) html += `<div class="conflict">⚠ ${d.conflict_note}</div>`;
  if (d.sources && d.sources.length) {
    const s = d.sources.map(x => `📎 ${x.uri}${x.updated_at ? " 🕐 " + x.updated_at : ""}`).join("<br>");
    html += `<div class="src">${s}</div>`;
  }
  return html;
}
</script>
</body>
</html>
```

- [ ] **Step 2: 集成验证（真起前后端）**

Run:
```bash
cd planA/code && source .venv/bin/activate
uvicorn server:app --port 8000 &
sleep 3
curl -s http://localhost:8000/ | grep -q "智慧芽技术知识助手" && echo "前端可访问"
kill %1
```
Expected: 打印「前端可访问」。手动在浏览器开 `http://localhost:8000/`，用「技术问答」问「Eureka 支持几种语言」，应看到答案 + 来源 + 冲突提示；切「竞品对比」问「Eureka 多语言 vs 竞品A」应看到对比表。

- [ ] **Step 3: 提交**

```bash
cd "/Users/zhangdezhao/Documents/PatSnap挑战赛"
git add planA/code/web/index.html
git commit -m "feat(planA): 对话网页前端 — 三入口分流、来源/时效/冲突渲染、降级提示"
```

---

### Task 14: 四个 SKILL.md 交付物 + add_skill 验证

**Files:**
- Create: `planA/code/skills/patsnap-kb-curation/SKILL.md`
- Create: `planA/code/skills/patsnap-tech-qa/SKILL.md`
- Create: `planA/code/skills/patsnap-competitor/SKILL.md`
- Create: `planA/code/skills/patsnap-promo-gen/SKILL.md`

**Interfaces:**
- Produces: 四份符合 OpenViking SKILL.md 格式的操作说明书（YAML frontmatter `name`/`description` 必填，可选 `allowed_tools`/`tags`；正文 Goal/Workflow/Boundaries）。格式依据 `OpenViking-main/docs/zh/api/04-skills.md`。
- 这是 spec §11 强调的**头号交付物**——「智慧芽场景下怎么用库」的 SOP，本身不含知识，只有编排规矩。
- Consumes: 无代码依赖；描述的 Workflow 对应 Task 5-10 的编排逻辑（skill 是给 Agent 读的自然语言版，后端是可执行版，两者同一套规矩的两种载体）。

- [ ] **Step 1: 写建库规范 skill**

创建 `planA/code/skills/patsnap-kb-curation/SKILL.md`：
```markdown
---
name: patsnap-kb-curation
description: 当需要把新资料归档进智慧芽知识库时加载。负责按五模块归目录、关键件走 smart-doc、同话题多来源打权威标签。
tags: [知识库, 建库, 归档]
---
# 智慧芽建库规范

## Goal
把任意智慧芽私域资料，正确归档到 viking://resources/ 的五模块目录，并处理同话题多来源。

## Workflow
1. 判断模块：把资料归到 methodology / products / style / competitors / roadmap 之一。
2. 关键件提质：图多的 PPT、扫描件先走 Smart-Doc API 转高质量 Markdown，再 add-resource。
   普通文档直接 add-resource（OpenViking 自带解析）。
3. 归档：ov add-resource <文件> --to viking://resources/<模块>/<文件名> --wait
4. 话题重复检测：归档前在同模块 ov find / ov grep 圈定同话题已有资源。
5. 若已存在同话题资源：两份都保留（不覆盖），按权威性打标签
   （官网/产品界面 > 内部权威文档 > 论文 > 二手转述），记「同话题多来源」关联。

## Boundaries
- 不做「哪句话对」的语义仲裁——只做话题重复检测 + 权威性标签。
- 关键件走 smart-doc 是兜底通道，不是主力；多数资料直接进 OpenViking。
- 定期人工复核「同话题多来源」列表，不建复杂自动提醒系统。
```

- [ ] **Step 2: 写技术问答 skill**

创建 `planA/code/skills/patsnap-tech-qa/SKILL.md`：
```markdown
---
name: patsnap-tech-qa
description: 当运营/销售问智慧芽技术问题（产品能力、方法论、技术口径）时加载。涉及统一口径、带来源的技术问答时触发。
tags: [技术问答, 统一口径, 溯源]
---
# 智慧芽技术问答（统一口径）

## Goal
把口语技术问题变成有来源、口径统一的标准答案。

## Workflow
1. 理解意图：涉及哪个模块/项目、是否对比、时间意图、有哪些专名。
2. 圈定范围：选定 target_uri（如 viking://resources/products）。
3. 语义检索：ov find <改写后 query> --uri <target>。
4. 专名兜底：query 含专名/型号时并行 ov grep 精确匹配，与 find 结果融合。
5. 冲突处理：若命中同话题多来源，按权威+时效选主答案，并曝光另一说法（来源+时效）。
6. 组装回答：附每条来源 URI + 该资料更新时间。

## Boundaries
- 无来源支撑的结论标「待核实」，不编造。
- 冲突信息以更权威/更新的来源为准，但不隐藏另一说法。
- 面向不懂技术的运营/销售，用大白话。
```

- [ ] **Step 3: 写竞品对比 skill**

创建 `planA/code/skills/patsnap-competitor/SKILL.md`：
```markdown
---
name: patsnap-competitor
description: 当需要把智慧芽产品与竞品做横向对比时加载。支持预存竞品对比和抛竞品网址实时抓取对比。
tags: [竞品对比, 实时抓取]
---
# 智慧芽竞品对比

## Goal
按维度对齐，产出「我方 vs 竞品」的对比，附各自来源，缺失明确标注。

## Workflow
1. 拆解：从问题抽取对比维度、我方产品、竞品对象、时间意图。
2. 双源召回：
   - 我方：ov find --uri viking://resources/products
   - 竞品：ov find --uri viking://resources/competitors；
     竞品库没有时，抓竞品网址 → trafilatura 去噪 → 按维度抽取。
3. 维度对齐：逐维度并排我方与竞品表述，附来源。
4. 缺失标注：某侧某维度无信息，明确标「未找到」，绝不猜。

## Boundaries
- 抓来的网页不可信：结构化去噪 + 按已知维度抽取，不让模型自由发挥。
- 外部数据附 source_url + 抓取时间；冲突以本地权威为准并标注。
- 只取公开信息，不外传私域内容。
```

- [ ] **Step 4: 写宣传生成 skill**

创建 `planA/code/skills/patsnap-promo-gen/SKILL.md`：
```markdown
---
name: patsnap-promo-gen
description: 当需要为智慧芽产品生成宣传材料（公众号、话术、推文、案例初稿）时加载。风格由用户 prompt 主导。
tags: [宣传生成, 富文本]
---
# 智慧芽宣传材料生成

## Goal
基于本地知识库的料 + 风格样本 + 用户 prompt，生成带来源的富文本初稿。

## Workflow
1. 检索料：产品能力/技术亮点从 viking://resources 检索（带 URI 来源）。
2. 注入风格：检索 viking://resources/style 历史文案作风格样本。
3. 组装：料 + 风格样本 + 用户 prompt（文体由 prompt 指定）。
4. 生成：富文本 + 事实来源列表 + 待核实项。

## Boundaries
- 事实点绑来源，无来源的标「待核实」，不编造。
- 不写死文体模板，风格听用户 prompt 的。
- 项目背景可联网补，但标注为外部信息。
```

- [ ] **Step 5: 验证 skill 能被 OpenViking 安装（真服务）**

Run（服务在跑）：
```bash
cd planA/code && source .venv/bin/activate
openviking add-skill ./skills/patsnap-tech-qa/ --wait
openviking add-skill ./skills/patsnap-kb-curation/ --wait
openviking add-skill ./skills/patsnap-competitor/ --wait
openviking add-skill ./skills/patsnap-promo-gen/ --wait
openviking find "统一口径的技术问答" --context-type skill --limit 5
```
Expected: 四条 add-skill 返回 `success`；find 用 `--context-type skill` 能检索到 `patsnap-tech-qa` 等。**这证明 SKILL.md 是真能被 OpenViking 托管的交付物，不只是纸面设计。**

- [ ] **Step 6: 提交**

```bash
cd "/Users/zhangdezhao/Documents/PatSnap挑战赛"
git add planA/code/skills
git commit -m "feat(planA): 四个SKILL.md交付物（建库/问答/竞品/宣传）并验证可被OV托管"
```

---

### Task 15: 召回评测集 + recall@k / MRR 脚本

**Files:**
- Create: `planA/code/eval/eval_set.jsonl`
- Create: `planA/code/eval/run_eval.py`
- Test: `planA/code/tests/test_run_eval.py`

**Interfaces:**
- Produces:
  - `eval_set.jsonl`：每行 `{"q": str, "ideal_uris": [str], "type": str}`，覆盖方法论/产品能力/竞品/专名各若干题（样例阶段先基于样例数据出 8-10 题，真实语料到位后扩到 20-30 题）。
  - `run_eval.py`：`recall_at_k(retrieved, ideal, k) -> float`、`mrr(retrieved, ideal) -> float`，主函数跑全集打印均值。
- Consumes: `OVClient`（真检索）或 mock（单测）。

- [ ] **Step 1: 写评测集（基于样例数据）**

创建 `planA/code/eval/eval_set.jsonl`：
```
{"q": "TRIZ 是什么", "ideal_uris": ["viking://resources/methodology/triz-intro.md"], "type": "方法论"}
{"q": "Eureka 支持几种语言", "ideal_uris": ["viking://resources/products/eureka-overview.md", "viking://resources/products/eureka-langs-old.md"], "type": "产品能力"}
{"q": "Eureka 多语言比竞品A强在哪", "ideal_uris": ["viking://resources/products/eureka-overview.md", "viking://resources/competitors/competitor-a.md"], "type": "竞品对比"}
{"q": "矛盾矩阵", "ideal_uris": ["viking://resources/methodology/triz-intro.md"], "type": "专名"}
{"q": "竞品A 支持哪些语言", "ideal_uris": ["viking://resources/competitors/competitor-a.md"], "type": "竞品"}
```

- [ ] **Step 2: 写失败测试**

创建 `planA/code/tests/test_run_eval.py`：
```python
from eval.run_eval import recall_at_k, mrr


def test_recall_at_k():
    retrieved = ["u2", "u1", "u3"]
    ideal = ["u1"]
    assert recall_at_k(retrieved, ideal, k=2) == 1.0   # u1 在前2
    assert recall_at_k(retrieved, ideal, k=1) == 0.0   # 前1是 u2


def test_mrr():
    retrieved = ["u2", "u1", "u3"]
    ideal = ["u1"]
    assert mrr(retrieved, ideal) == 0.5                # u1 排第2 → 1/2


def test_recall_multi_ideal():
    retrieved = ["u1", "u5", "u2"]
    ideal = ["u1", "u2"]
    assert recall_at_k(retrieved, ideal, k=3) == 1.0   # 两个都在前3
    assert recall_at_k(retrieved, ideal, k=1) == 0.5   # 只 u1 在前1
```

- [ ] **Step 3: 运行确认失败**

Run: `python -m pytest tests/test_run_eval.py -v`
Expected: FAIL（模块不存在）。

- [ ] **Step 4: 写 run_eval.py**

创建 `planA/code/eval/run_eval.py`：
```python
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def recall_at_k(retrieved: list[str], ideal: list[str], k: int) -> float:
    top = retrieved[:k]
    hit = sum(1 for u in ideal if u in top)
    return hit / len(ideal) if ideal else 0.0


def mrr(retrieved: list[str], ideal: list[str]) -> float:
    for i, u in enumerate(retrieved, start=1):
        if u in ideal:
            return 1.0 / i
    return 0.0


def main():
    from config import settings
    from ov_client import OVClient
    ov = OVClient(settings.ov_url, settings.ov_api_key)
    here = os.path.dirname(os.path.abspath(__file__))
    rows = [json.loads(l) for l in open(os.path.join(here, "eval_set.jsonl"), encoding="utf-8") if l.strip()]
    r5, mrrs = [], []
    for row in rows:
        hits = ov.find(row["q"], "viking://resources", limit=10)
        uris = [h["uri"] for h in hits]
        r5.append(recall_at_k(uris, row["ideal_uris"], 5))
        mrrs.append(mrr(uris, row["ideal_uris"]))
    n = len(rows)
    print(f"题数={n}  recall@5={sum(r5)/n:.3f}  MRR={sum(mrrs)/n:.3f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 运行确认通过**

Run: `python -m pytest tests/test_run_eval.py -v`
Expected: 3 passed。

- [ ] **Step 6: 集成跑一次真评测（真服务）**

Run（服务在跑、样例已导入）：
```bash
cd planA/code && source .venv/bin/activate && python eval/run_eval.py
```
Expected: 打印 `题数=5 recall@5=... MRR=...`。这套脚本后续复用到与 Plan B 的四方对比（spec §13）。

- [ ] **Step 7: 提交**

```bash
cd "/Users/zhangdezhao/Documents/PatSnap挑战赛"
git add planA/code/eval planA/code/tests/test_run_eval.py
git commit -m "feat(planA): 召回评测集 + recall@k/MRR 脚本"
```

---

### Task 16: 真实语料切换（语料到位后执行，不阻塞前面）

**Files:**
- Modify: `planA/code/.env`（改 `CORPUS_DIR` / `COMPETITOR_URLS`）
- Modify: `planA/code/scripts/import_sample.sh`（或新增 `import_real.sh`）
- Modify: `planA/code/eval/eval_set.jsonl`（扩到 20-30 题）
- Possibly modify: `planA/code/orchestrator/conflict.py`（若真实语料的来源/时效标注格式不同）

**Interfaces:**
- Consumes: 另一位同学搭建的真实语料 + 确定的技术领域 + 真实竞品 URL。
- Produces: 全链路跑在真实数据上；评测集给出真实召回数字。

**说明**：这是隔离策略的收口任务——前面 Task 1-15 全部基于样例跑通，本任务只做「换数据源」，不改架构。

- [ ] **Step 1: 放置真实语料并按五模块归档**

把真实语料放到新目录（如 `planA/code/real_data/`），改 `.env` 的 `CORPUS_DIR=./real_data`。按 Task 3 的 `import_sample.sh` 模式写 `import_real.sh`，把真实资料 `add-resource` 到对应模块。若有图多 PPT/扫描件，先走 Smart-Doc（`历史/smart-document-api-guide.md`：`POST /pdf/smart-doc` 或 `/document/smart-doc`，`markdown:true`）转 Markdown 再导入。

- [ ] **Step 2: 校验来源/时效解析规则**

真实语料的「来源+更新时间」若不是样例的 `> 来源：X · 更新于 YYYY-MM` 尾注格式，改 `orchestrator/conflict.py` 的 `_FOOTER_RE` 与 `_AUTHORITY_RULES` 以适配。跑 `python -m pytest tests/test_conflict.py` 确认原有测试仍绿（必要时更新测试夹具）。

- [ ] **Step 3: 扩充评测集并重跑**

把 `eval/eval_set.jsonl` 扩到 20-30 题真实运营会问的问题，每题标注理想 URI。Run: `python eval/run_eval.py`，记录真实 recall@5 / MRR 作为答辩证据。

- [ ] **Step 4: 全链路回归**

Run:
```bash
cd planA/code && source .venv/bin/activate && python -m pytest -v
```
Expected: 全部单测通过（单测与数据无关，应始终绿）。再手动开前端过一遍三类能力。

- [ ] **Step 5: 提交**

```bash
cd "/Users/zhangdezhao/Documents/PatSnap挑战赛"
git add planA/code/scripts planA/code/eval planA/code/orchestrator/conflict.py
git commit -m "feat(planA): 切换到真实语料，扩充评测集，适配来源解析规则"
```

---

## Self-Review（spec 覆盖核对）

对照 `planA/技术方案-OpenViking.md` 各节，确认每项都有任务承接：

| spec 节 | 内容 | 承接任务 |
|---|---|---|
| §1 产品定位 | 面向不懂技术的运营销售、统一口径、溯源刚需 | 贯穿 Task 5-10（附来源/时效、大白话 system prompt） |
| §2 为何选 OpenViking | 用开源引擎、认清 BM25/AGPL 边界 | Task 1（AGPL 护栏：不装 openviking 进后端）、Task 3（验证 grep 是自带能力） |
| §3 整体架构 | 产品↔HTTP API↔OV 独立服务 | Task 4（ov_client 只 HTTP）、Task 11（后端） |
| §4 数据接入 | add-resource 为主、smart-doc 兜底、五模块目录 | Task 3（导入脚本）、Task 14（建库 skill）、Task 16（smart-doc 真实件） |
| §5 知识组织 | viking:// + L0/L1/L2 | Task 3（验证分层）、Task 4（read 取 L2） |
| §6 检索 | find + 专名 grep 融合 + 查询改写 | Task 5（查询理解）、Task 6（融合） |
| §6 对比类提问 | 查询分解+多源召回+维度对齐 | Task 8（comparison） |
| §7 时间线/版本 | git 快照 + watch（OV 原生） | 附来源时效（Task 10）；watch 为 OV 原生能力，导入时可加 `--watch-interval`（Task 3 脚本可选） |
| §7之二 跨资源冲突 | 权威+时效裁决 + 曝光而非静默覆盖 | Task 7（conflict）+ Task 10（conflict_note 曝光） |
| §8 内外结合 | 预存竞品 + 实时抓取 | Task 8（预存）、Task 9（实时抓取） |
| §9 宣传生成 | 料+风格样本+prompt，附来源/待核实 | Task 10（generate_promo）、Task 12（promo 端点）、Task 14（宣传 skill） |
| §10 技术路线判断 | 内能力盘点×外AI趋势，人复核 | **未单独建任务**——见下方说明 |
| §11 Skill 交付形态 | 四个 SKILL.md | Task 14 |
| §12 产品 Demo | 对话网页承载 skill、后端是 Agent 运行时、降级档 | Task 11/12/13（含降级、密钥后端代理） |
| §13 评估 | 召回评测集、recall@k/MRR、四方对比 | Task 15 |
| §14 风险 | BM25 缺失、AGPL、部署慢、现场崩 | Task 1（部署用 uv 应对慢）、Task 9/11（降级档应对现场崩） |

**关于 §10 技术路线判断**：这是官方任务4，spec 明确它是「辅助判断、人做结论、系统供弹药」，产出形态是「内能力盘点 + 外AI趋势 + 候选结合点」的材料，不是一个可自动化验证的检索/生成链路。它复用已有能力（内半=Task 6 检索本地产品能力盘点，外半=Task 9 的联网抓取能力搜 AI 趋势），无需新代码模块，属于「用现有编排 + 人工判断」的组合应用。**若要在 Demo 里体现，可作为技术问答 skill 的一个特殊 prompt 场景，不单列工程任务。** 此决定有意为之，非遗漏。

**占位符扫描**：全plan 无 TBD/TODO/"类似 Task N"/"添加适当错误处理" 等占位；每个代码 step 都给了完整可运行代码；每个命令 step 都给了 Expected。

**类型一致性核对**：
- `QueryPlan`（Task 5）字段 rewritten/target_uri/is_comparison/proper_nouns/time_intent —— Task 6 `retrieve(plan)` 用的是 `plan.rewritten`/`plan.target_uri`/`plan.proper_nouns`，一致。
- `Hit`（Task 6）字段 uri/score/abstract/source —— Task 10 用 `h.abstract`/`h.uri`，一致。
- `SourceMeta`/`ConflictVerdict`（Task 7）—— Task 10 用 `verdict.primary.uri`/`verdict.has_conflict`/`verdict.others`/`o.updated_at`，一致。
- `ComparisonRow`（Task 8）字段 dimension/ours/ours_uri/theirs/theirs_uri —— Task 12 `r.__dict__` 序列化、Task 13 前端读 `row.dimension`/`row.ours`/`row.theirs`，一致。
- `Answer`（Task 10）字段 text/sources/conflict_note/unverified —— Task 11/12 端点读 `ans.text`/`ans.sources`/`ans.conflict_note`，一致。
- `OVClient` 方法 find/grep/glob/read/ls（Task 4）—— 各编排模块与 run_eval 调用签名一致。

---

## 执行顺序建议

严格按 Task 1→16 顺序。关键卡点：
- **Task 1 Step 9（doctor 通过）不过，不要往下走**——环境不对后面全白做。
- **Task 3 完成 = 阶段一里程碑**：此后语料即使没到，Task 4-15 全部可基于样例推进。
- Task 4-10 是纯 Python + TDD，离线可做（mock 掉 OV/LLM），不依赖服务常驻；只在每个 Task 末尾的「集成验证」step 才需要真服务。
- Task 16 等真实语料到位后再做，不阻塞前 15 个任务。
