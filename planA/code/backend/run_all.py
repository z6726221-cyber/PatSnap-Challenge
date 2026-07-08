"""跑通三个生成场景，各一个真实 case，输出写到 run_logs/ 并做来源校验。

用法：python3 run_all.py   （需 backend/.env 里配好可用的 LLM 端点）
"""
import os
import sys
import subprocess

from agent_runtime import run_agent

HERE = os.path.dirname(__file__)
LOG = os.path.join(HERE, "run_logs")
os.makedirs(LOG, exist_ok=True)
CHECK = os.path.join(HERE, "..", "skills", "scripts", "check_sources.py")
SAMPLE = os.path.join(HERE, "..", "sample_retrieval")

# (skill 名, case 文件夹) —— 资料由检索侧给定，这里用样例 case
CASES = [
    ("patsnap-tech-qa", os.path.join(SAMPLE, "case-eureka-lang")),
    ("patsnap-compare", os.path.join(SAMPLE, "case-compare-lang")),
    ("patsnap-promo", os.path.join(SAMPLE, "case-promo-search")),
]


def main():
    summary = []
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

        check = subprocess.run([sys.executable, CHECK, ans_file],
                               capture_output=True, text=True)
        print("\n----- check_sources.py -----\n" + check.stdout, flush=True)
        summary.append((skill, f"{len(trace)}步工具",
                        "校验:通过" if check.returncode == 0 else "校验:告警"))

    print(f"\n{'='*70}\n汇总\n{'='*70}", flush=True)
    for s, a, b in summary:
        print(f"  {s:20} {a:12} {b}", flush=True)


if __name__ == "__main__":
    main()
