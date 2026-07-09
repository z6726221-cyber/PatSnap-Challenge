---
updated_at: 2026-07-08
---

# 错题本 / 裁决记录

记录版本冲突裁决过程和已知的知识缺口，供后续核实/复查。

## 裁决记录

### 1. 矛盾矩阵参数数量：39 vs 48

- **冲突**：`triz-contradiction-matrix-classic.md`（官方权威整理，2024-03-10）记为 39个参数、39×39矩阵；`triz-contradiction-matrix-old-note.md`（内部培训笔记，2021-06-01）记为 48个参数、48×48矩阵。
- **裁决**：采用 **39参数版**为准确结论。
- **依据**：
  1. 权威性：前者 `authority: official`，后者 `authority: internal_note`。
  2. 时效性：前者整理时间（2024-03-10）晚于后者（2021-06-01）。
  3. 交叉验证：39参数版是被后续教材（如 Terninko等《系统化创新》）广泛采用的公开权威版本；48参数说法未能找到可验证原始出处，疑似混淆了"48个改善方向候选"与"39个参数"两个不同概念。
- **处理**：`triz-contradiction-matrix-old-note.md` 标注 `superseded_by: triz-contradiction-matrix-classic`，Wiki 页面 [[triz-contradiction-matrix]] 正文中主动曝光此冲突及裁决依据，不静默覆盖。

## 已知缺口 / 待核实候选术语

- Engineering Agents 的"root-cause/TRIZ-based ideation"具体覆盖哪些 TRIZ 子工具（矛盾矩阵/物场分析/IFR），官网首页未给出细节，需要产品文档进一步核实。
- PatentSight+ 的 Patent Asset Index 计算方法未公开，暂标"待核实"，不在生成产物中作为可验证事实引用。
- PatentSight+ 定价与部署方式（SaaS/本地）未在已抓取内容中出现，如需回答相关问题需重新临场抓取或标"待核实"。
