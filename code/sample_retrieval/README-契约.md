# 检索输出格式契约（生成侧 ← 检索侧）

> 这份文档定义**检索侧同学的输出**与**我们生成侧的输入**之间的接口。
> 目的：生成侧（技术问答/竞品分析/宣传材料）先按这个理想格式跑通；
> 真实检索输出到位后，只需写一个适配器把它转成这个格式，核心逻辑不动。

## 现状：生成侧已直接支持 OpenViking 原始检索包

真实检索层（OpenViking）目前直接输出的是"检索结果包"格式（含"命中资源明细"
小节，一个文件里塞多条命中，无 YAML frontmatter），而不是下面的理想格式。

`backend/loader.py` 的 `parse_materials_from_file()` 已经能直接解析这种原始
检索包：按"命中资源明细"小节拆成多条 Material，`source` 取自每条的
`URI：\`...\`` 行，正文优先取"全文内容"，没有就退回"摘要/片段"并标注"可能
被截断"。`authority`/`topic`/`updated_at` 走本文档下面定义的降级规则
（检索包本来就不含这些元信息）。

也就是说：**检索侧不需要额外适配，可以直接把 OpenViking 的检索结果包原样
放进 case 文件夹**。解析器会先尝试识别"命中资源明细"小节；识别不到时（比如
文件本身就是下面这种带 frontmatter 的理想格式）会退回整文件单条解析。两种
格式共存不冲突——如果检索侧未来能顺手带上 authority/topic 这类元信息，仍
建议按理想格式给，可以让冲突裁决更准确。

## 真实检索：live 目录（生产链路，检索侧对接这一节）

用户在网页打字提问 → 后端把问题转给检索系统 → 检索系统跑完，把召回的 md
写进固定目录 **`sample_retrieval/live/`** → 后端读这个目录 + 用户刚打的问题
→ 交给 Agent。

```
sample_retrieval/
└── live/                      # 固定路径，每次检索整目录覆盖（不是新建/累加）
    ├── 01-xxx.md               # 可以是 1 个或多个 .md（比如按子查询分开检索）
    └── 02-xxx.md
```

约定：
- **路径固定**：永远是 `sample_retrieval/live/`，不用每次换名字。
- **每次覆盖整目录**：新一轮检索的结果替换掉上一轮的，不用手动清理旧文件，
  但检索侧自己要保证不会把上一轮的残留文件和这一轮的混在一起。
- **不需要 `question.txt`**：问题就是用户当次打的那句话，由后端直接传给
  Agent，不用检索侧另外落盘一份配对。
- **md 内容格式**：跟下面"每份资料 md 的格式"一节要求相同——理想情况带
  frontmatter（`source`/`updated_at`/`authority`/`topic`）；如果检索侧输出
  的是 OpenViking 原始检索包格式（含"命中资源明细"小节，一个文件多条命中，
  无 frontmatter），也直接支持，不需要额外转换。
- **覆盖写入尽量做到原子**：后端是多线程服务，有小概率在检索侧正在覆盖
  `live/` 目录（先删旧文件、再写新文件）的过程中恰好读到中间态。我们这边
  已经加了读取一致性校验 + 重试（`loader.load_live()`）兜底，不会因此崩溃
  或读到错乱数据，但**更稳妥的做法**是检索侧写入时先写到一个临时目录，
  写完整后用 `os.replace()`/`os.rename()` 把临时目录整体换成 `live/`——
  这样后端任何时刻看到的 `live/` 都是完整的某一版，不会有中间态。如果暂时
  做不到这一步，直接写 `live/` 也可以，靠我们这边的重试兜底。
- **`live/` 里没有 `.md` 文件时**（检索还没跑过、或者本轮没召回到任何资料）：
  后端直接给用户降级提示，不会退回假样例演示数据。
- `live/` 目录结构进 git，但真实召回 `.md` 不进 git：仓库只提交
  `live/.gitkeep` 和 `live/README.md`，用于保留目录和说明；检索系统运行时
  生成的 `.md` 仍被 `.gitignore` 排除。

以下的 `case-xxx/` 假样例目录结构和 `question.txt`，只用于本地测试/回归
（`run_all.py`、单测），跟 live 真实链路无关，检索侧不需要管这部分。

## 外部公开信息模拟：mock_external 目录

销售与售前会尝试合并三类资料：`live/` 黑盒召回、内部知识库、外部公开信息。
真实外部搜索由 `backend/external_search.py` 通过 `EXTERNAL_SEARCH_ENDPOINT`
接入；未配置时会返回 `external-intel/gap`，要求报告把外部客户事实标为待核实。

为了让仓库里能看见“外部检索模拟资料”的形态，`sample_retrieval/mock_external/`
提交了可公开的 demo fixture：

```
sample_retrieval/
└── mock_external/
    ├── README.md
    ├── engineering-public-intel.md
    └── clarivate-like-ip-intel.md
```

这些资料使用 `public-demo://...` source，用于 Demo、E2E 和评审说明；不要把真实
客户外部搜索结果直接提交到这里。

## 假样例回归目录结构（仅供本地测试，非生产链路）

```
sample_retrieval/
├── case-eureka-lang/          # 一次检索 = 一个 case 文件夹
│   ├── question.txt           # 用户的原始问题（一行）
│   ├── 01-xxx.md              # 召回的资料 1（带 frontmatter）
│   ├── 02-xxx.md              # 召回的资料 2
│   └── ...                    # 按相关度排序，序号越小越相关
├── case-compare-lang/
│   └── ...
└── case-semantic-search/
    └── ...
```

## 每份资料 md 的格式

正文前带 YAML frontmatter，记录溯源与裁决所需的元信息：

```markdown
---
source: viking://resources/products/eureka/lang-support.md   # 来源 URI 或 http(s) URL
updated_at: 2026-06-20        # 资料更新日期（YYYY-MM-DD 或 YYYY-MM）
authority: L1                 # 权威级：L1官网/产品界面 > L2内部权威文档 > L3论文 > L4二手转述
topic: eureka-lang            # 话题标识；同 topic 的多份资料 = 同话题多来源（可能冲突）
score: 0.92                   # 检索相关度 0-1（可选，检索侧给则用于排序）
title: Eureka 多语言支持       # 资料标题（可选）
---

（这里是资料正文，markdown。检索召回的原文片段。）
```

## 字段说明与降级

| 字段 | 必填 | 缺失时的降级 |
|---|---|---|
| `source` | 强烈建议 | 缺 → 标「来源未知」，该资料的事实点标「待核实」 |
| `updated_at` | 强烈建议 | 缺 → 标「时间未知」 |
| `authority` | 建议 | 缺 → 按最低 L4 处理（宁可低估不高估） |
| `topic` | 建议 | 缺 → 用文件名兜底；同话题多来源检测会失效（退化为不检测冲突） |
| `score` | 可选 | 缺 → 按文件序号顺序（01 最相关） |
| `title` | 可选 | 缺 → 用文件名 |

## 为什么需要这些元信息

- `source` + `updated_at` → 支撑「溯源」和「统一口径 = 统一内容 + 统一时效」。
- `authority` + `topic` → 支撑「同话题多来源冲突曝光」：同 topic 有多份且说法不同时，
  按权威+时效选主答案，并把另一说法**曝光而非静默丢弃**。
- 这些元数据检索时本来就在向量库里，附带输出成本很低。**这是对检索侧的明确诉求。**

## 给检索侧的最小要求

如果暂时只能给 `source` + `updated_at`，生成侧仍可跑（溯源可用，冲突曝光退化）。
但强烈建议连 `authority` + `topic` 一起给，这是我们方案区别于「普通 RAG」的核心卖点。
