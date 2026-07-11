"""跑通三个生成场景 + 一次真实检索(live)通道，输出写到 run_logs/ 并做来源校验。

用法：python3 run_all.py   （需 backend/.env 里配好可用的 LLM 端点）
"""
import os
import sys
import shutil
import subprocess
import tempfile

from agent_runtime import run_agent, run_agent_with_case
from loader import load_live

HERE = os.path.dirname(__file__)
LOG = os.path.join(HERE, "run_logs")
os.makedirs(LOG, exist_ok=True)
CHECK = os.path.join(HERE, "..", "skills", "scripts", "check_sources.py")
FIXTURES = os.path.join(HERE, "..", "fixtures", "retrieval_cases")

# (skill 名, case 文件夹) —— 资料由检索侧给定，这里用样例 case
CASES = [
    ("patsnap-tech-qa", os.path.join(FIXTURES, "case-eureka-lang")),
    ("patsnap-compare", os.path.join(FIXTURES, "case-compare-lang")),
    ("patsnap-promo", os.path.join(FIXTURES, "case-promo-search")),
]

# live 通道验证：借一份已有的 OpenViking 原始检索包样例，模拟"检索侧刚写完
# live/ 目录"的场景，跑一遍 load_live() → run_agent_with_case()，确认真实
# 检索接入链路（不是假样例 case 文件夹）本身没坏。写到临时目录，不碰真正的
# sample_retrieval/live/（那是留给真实检索系统写的，不该被本地验证脚本污染）。
LIVE_SKILL = "patsnap-tech-qa"
LIVE_SOURCE_MD = os.path.join(FIXTURES, "case-algo-q3-eng", "01-raw-retrieval.md")
LIVE_QUESTION = "算法团队2026 Q3的工作规划是什么，重点方向和风险点有哪些？"


def _check(ans_file):
    check = subprocess.run([sys.executable, CHECK, ans_file],
                           capture_output=True, text=True)
    print("\n----- check_sources.py -----\n" + check.stdout, flush=True)
    return check.returncode == 0


def run_case_scenarios(summary):
    for skill, case_dir in CASES:
        print(f"\n{'#'*70}\n# {skill}: {os.path.basename(case_dir)}\n{'#'*70}", flush=True)
        try:
            ans, trace = run_agent(skill, case_dir, verbose=True)
        except Exception as e:  # noqa
            print(f"!! 运行失败: {e}", flush=True)
            summary.append((skill, "ERROR", str(e)[:80]))
            continue

        ans_file = os.path.join(LOG, f"{skill}.answer.txt")
        with open(ans_file, "w", encoding="utf-8") as f:
            f.write(ans)
        print("\n----- 最终产物 -----\n" + ans, flush=True)
        print(f"\n----- 轨迹 {len(trace)} 步 -----", flush=True)
        for t in trace:
            print(f"  - {t['tool']}({t['args']})", flush=True)

        passed = _check(ans_file)
        summary.append((skill, f"{len(trace)}步工具", "校验:通过" if passed else "校验:告警"))


def run_live_scenario(summary):
    """验证真实检索 live 通道：临时目录模拟检索侧写好的 live/，走 load_live()
    + run_agent_with_case()，不经过假样例 case 文件夹逻辑。"""
    label = f"{LIVE_SKILL}(live)"
    print(f"\n{'#'*70}\n# {label}: 模拟检索侧写好的 live 目录\n{'#'*70}", flush=True)
    if not os.path.exists(LIVE_SOURCE_MD):
        print(f"!! 找不到样例检索包: {LIVE_SOURCE_MD}，跳过 live 通道验证", flush=True)
        summary.append((label, "SKIPPED", "缺样例检索包"))
        return

    tmp_live_dir = tempfile.mkdtemp(prefix="run_all_live_")
    try:
        shutil.copy(LIVE_SOURCE_MD, os.path.join(tmp_live_dir, "01-raw-retrieval.md"))
        case = load_live(tmp_live_dir, question=LIVE_QUESTION)
        ans, trace = run_agent_with_case(LIVE_SKILL, case, verbose=True)

        ans_file = os.path.join(LOG, f"{LIVE_SKILL}.live.answer.txt")
        with open(ans_file, "w", encoding="utf-8") as f:
            f.write(ans)
        print("\n----- 最终产物 -----\n" + ans, flush=True)
        print(f"\n----- 轨迹 {len(trace)} 步 -----", flush=True)
        for t in trace:
            print(f"  - {t['tool']}({t['args']})", flush=True)

        passed = _check(ans_file)
        summary.append((label, f"{len(trace)}步工具", "校验:通过" if passed else "校验:告警"))
    except Exception as e:  # noqa
        print(f"!! 运行失败: {e}", flush=True)
        summary.append((label, "ERROR", str(e)[:80]))
    finally:
        shutil.rmtree(tmp_live_dir, ignore_errors=True)


def main():
    summary = []
    run_case_scenarios(summary)
    run_live_scenario(summary)

    print(f"\n{'='*70}\n汇总\n{'='*70}", flush=True)
    for s, a, b in summary:
        print(f"  {s:20} {a:12} {b}", flush=True)


if __name__ == "__main__":
    main()
