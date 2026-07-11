#!/usr/bin/env python3
"""
check_sources.py — 芽懂 skill 共享的产物校验脚本

作用：把"检索四步 SOP"里机械、确定的第④步（附来源 + 时效）从"靠 agent 自觉"
变成"脚本卡死"。四个 skill 的 Verification 都调它，保证输出口径不漂移。

它不判断答案对不对（那要人/评测集），只检查**可机械验证的产物契约**：
  1. 是否出现了来源 URI（viking:// 或 http(s) source_url）
  2. 是否带了更新/抓取时间，或明确标注了"时间未知"
  3. 若正文含"待核实/未找到"这类诚实标注，视为合规的缺失处理

用法：
  python3 check_sources.py <文件路径>
  echo "答案文本" | python3 check_sources.py -
退出码：0 = 通过；1 = 有告警（不阻断，供人判断）；2 = 用法错误
"""

import re
import sys

# --- 匹配规则（宽松，面向中文答案文本） ---
URI_PAT = re.compile(r"viking://[^\s，。）)\]】]+")
URL_PAT = re.compile(r"https?://[^\s，。）)\]】]+")
# presales 场景的本地/外部情报来源 scheme（非黑盒检索的 viking://，但同样可溯源）：
# kb://<kind>/<id> 内部知识库、external-intel/<n> 或 external-intel/gap 外部情报（含缺口标注）、
# uploads/<filename> 当前任务附件、public-demo://... 情报适配层兜底占位。
OTHER_SOURCE_PAT = re.compile(
    r"(?:kb://|external-intel/|uploads/|public-demo://)[^\s，。）)\]】]*"
)
# 时间：2026-06、2026-06-01、2026/6、"截至 2026"、ISO 等
TIME_PAT = re.compile(r"(20\d{2}[-/年.]\s?\d{1,2}([-/月.]\s?\d{1,2})?|截至\s*20\d{2}|时间未知|日期未知)")
# 诚实缺失标注
HONEST_PAT = re.compile(r"(待核实|未找到|未在.*找到|无(来源|资料)|时间未知|日期未知)")
# 事实性陈述的粗略信号（数字、"支持N种"、"率""倍"等），用于估计"该有来源的地方"
FACT_HINT_PAT = re.compile(r"(\d+\s*(种|个|倍|%|％|项|款|年)|支持|兼容|领先|首个|唯一|准确率|召回)")

# "来源：..." 整个来源子句，取到下一个"更新时间"标注或句末标点为止（不能只
# 取第一个 token —— 多来源常写成 "来源：`A`、`B`、`C`，更新时间：..."，只看
# 第一个会漏掉后面几个）。
SOURCE_CLAUSE_RE = re.compile(r"来源[：:]\s*(.+?)(?:，?\s*更新时间|[。；\n]|$)")
# 来源子句内，多个来源之间的分隔符：、，, 都算
_SOURCE_ITEM_SPLIT_RE = re.compile(r"[、，,]")
# 允许的非 URI 标注：诚实缺失标注本身、以及 CaseTools 的工具调用引用
# （check_conflicts() 这类是真实发生的工具调用，不是编造，应放行）
_ALLOWED_NON_URI_LABEL = re.compile(
    r"^(未知|待核实|未找到|无来源|无资料|"
    r"list_materials\(\)|read_material\(.*\)?|check_conflicts\(\)?)$"
)


def _find_fake_source_labels(text: str):
    """返回"来源：..."子句里，每个来源既不是真实 URI/URL、也不是允许的诚实
    标注/工具引用的那些 token。子句可能包含多个用"、"分隔的来源，逐个检查。"""
    fakes = []
    for clause_m in SOURCE_CLAUSE_RE.finditer(text):
        clause = clause_m.group(1)
        for item in _SOURCE_ITEM_SPLIT_RE.split(clause):
            token = item.strip().strip("`").strip("《》（）").strip()
            if not token:
                continue
            if token.startswith("viking://") or token.startswith("http://") or token.startswith("https://"):
                continue
            if token.startswith("kb://") or token.startswith("external-intel/") \
                    or token.startswith("uploads/") or token.startswith("public-demo://"):
                continue
            if _ALLOWED_NON_URI_LABEL.match(token):
                continue
            fakes.append(token)
    return fakes


def read_input(arg: str) -> str:
    if arg == "-":
        return sys.stdin.read()
    try:
        with open(arg, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        print(f"[错误] 无法读取输入：{e}", file=sys.stderr)
        sys.exit(2)


def check(text: str) -> int:
    warnings = []

    uris = URI_PAT.findall(text)
    urls = URL_PAT.findall(text)
    others = OTHER_SOURCE_PAT.findall(text)
    times = TIME_PAT.findall(text)
    honest = HONEST_PAT.findall(text)
    fact_hints = FACT_HINT_PAT.findall(text)

    n_sources = len(uris) + len(urls) + len(others)

    # 规则1：有事实信号却完全没有来源 → 告警
    if fact_hints and n_sources == 0:
        warnings.append(
            f"检测到 {len(fact_hints)} 处事实性表述，但未发现任何来源"
            "（viking://、http 链接，或 kb:// / external-intel/ / uploads/ / public-demo:// 等本地来源）。"
            "按检索四步 SOP 第④步，事实点应绑来源。"
        )

    # 规则2：有来源但完全没有时间标注 → 告警
    if n_sources > 0 and not times:
        warnings.append(
            "发现来源但未发现任何更新/抓取时间或\"时间未知\"标注。"
            "统一口径 = 统一内容 + 统一时效，请补时间或标注\"时间未知\"。"
        )

    # 规则3：既无来源也无诚实缺失标注，且有事实信号 → 更强告警
    if fact_hints and n_sources == 0 and not honest:
        warnings.append(
            "既无来源也无\"待核实/未找到\"等诚实标注 —— 有编造风险，请核对。"
        )

    # 规则4：出现"来源：X"标注，但 X 不是真实可溯源的 URI/URL（比如缩写成 "S1"
    # 这种编号）→ 告警。契约要求来源必须可点回原文，缩写编号做不到这一点。
    fake_labels = _find_fake_source_labels(text)
    if fake_labels:
        sample = "、".join(sorted(set(fake_labels))[:5])
        warnings.append(
            f"发现 {len(fake_labels)} 处「来源：」标注不是真实 URI/URL（如 {sample}）——"
            "来源必须是可溯源的完整地址，不能用编号/缩写代替。"
        )

    # --- 报告 ---
    print("=== check_sources.py 产物校验 ===")
    print(f"来源(viking://): {len(uris)}  外部链接(http): {len(urls)}  本地来源(kb/external-intel/uploads): {len(others)}  "
          f"时间标注: {len(times)}  诚实缺失标注: {len(honest)}  事实信号: {len(fact_hints)}  "
          f"疑似虚假来源标注: {len(fake_labels)}")

    if not warnings:
        print("✓ 通过：来源与时效标注符合产物契约。")
        return 0

    print(f"⚠ {len(warnings)} 条告警（不阻断，供人判断）：")
    for i, w in enumerate(warnings, 1):
        print(f"  {i}. {w}")
    return 1


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    text = read_input(sys.argv[1])
    if not text.strip():
        print("[错误] 输入为空。", file=sys.stderr)
        sys.exit(2)
    sys.exit(check(text))


if __name__ == "__main__":
    main()
