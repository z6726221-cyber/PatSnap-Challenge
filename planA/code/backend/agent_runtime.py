"""
Agent 运行时 —— 让一个真实的 Agent 加载我方生成类 skill，基于"已召回的资料"生成产物。

新架构（检索侧已由另一位同学完成）：
  用户问题 + 检索召回的资料（case 文件夹）  →  本运行时  →  生成产物（问答/竞品/宣传）

流程：
  1. 读取指定 skill 的 SKILL.md + 它引用的 references，拼成 system prompt
  2. 加载 case 文件夹（问题 + 资料），把 CaseTools 暴露为 function-calling 工具
  3. 跑工具调用循环：Agent 照 skill 的 SOP 决定读哪些料、如何裁决冲突、如何组织答案
  4. 返回最终产物 + 完整执行轨迹

验证的是：我方 skill 能不能被真实 Agent 正确理解和执行。
资料是给定的（真实/样例皆可），Agent 的挑料/裁决/组织/附来源是真的。
"""
import os
import re
import json

from llm_client import LLMClient
from loader import load_case
from case_tools import CaseTools, TOOLS

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "skills")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_skill_prompt(skill_name):
    """读 SKILL.md + 其引用的 references，拼成给 Agent 的 system prompt。"""
    skill_dir = os.path.join(SKILLS_DIR, skill_name)
    skill_md = _read(os.path.join(skill_dir, "SKILL.md"))

    # 收集 SKILL.md 里引用的 references 路径（../references/x.md 或 references/x.md）
    ref_paths = set(re.findall(r"`?\.\.?/references/[^\s`）)]+\.md`?", skill_md))
    ref_blocks = []
    for rp in sorted(ref_paths):
        clean = rp.strip("`")
        abs_path = os.path.normpath(os.path.join(skill_dir, clean))
        if os.path.exists(abs_path):
            ref_blocks.append(f"\n\n===== 引用文档: {clean} =====\n" + _read(abs_path))

    system = (
        "你是「芽懂」——智慧芽私域知识库的技术助手。你已加载下面这个 skill，"
        "必须严格按它的 Workflow、Output Contract 和 Boundaries 执行。\n"
        "本次的资料已由检索系统召回好，你通过 list_materials / read_material / "
        "check_conflicts 三个工具访问它们。不要凭记忆编造知识，所有事实都必须来自"
        "工具返回的资料，并附上来源和更新时间；资料没有支撑的点，标「待核实」。\n"
        "如果 Workflow 要求'先读某些 references'，这些内容已附在下方，视为你已读。\n\n"
        "===== SKILL.md =====\n" + skill_md + "".join(ref_blocks)
    )
    return system


def run_agent(skill_name, case_dir, max_turns=8, verbose=True):
    """加载 skill + case 文件夹，让 Agent 生成产物。返回 (最终产物, 轨迹)。"""
    cli = LLMClient()
    case = load_case(case_dir)
    tools_obj = CaseTools(case)
    tool_impl = tools_obj.impl()

    system = load_skill_prompt(skill_name)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": case.question},
    ]
    trace = []

    for turn in range(max_turns):
        msg, usage = cli.chat(messages, tools=TOOLS)
        assistant_msg = {"role": "assistant", "content": msg.get("content") or ""}
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        messages.append(assistant_msg)

        if not tool_calls:
            if verbose:
                print(f"[turn {turn}] Agent 给出最终产物。")
            return msg.get("content", ""), trace

        for tc in tool_calls:
            fname = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            impl = tool_impl.get(fname)
            if impl is None:
                result = {"error": f"unknown tool {fname}"}
            else:
                try:
                    result = impl(**args)
                except Exception as e:  # noqa
                    result = {"error": str(e)}
            trace.append({"turn": turn, "tool": fname, "args": args, "result": result})
            if verbose:
                print(f"[turn {turn}] 调用 {fname}({args})")
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })

    return "(达到最大轮次，未收敛)", trace


if __name__ == "__main__":
    import sys
    skill = sys.argv[1] if len(sys.argv) > 1 else "patsnap-tech-qa"
    case_dir = sys.argv[2] if len(sys.argv) > 2 else "../sample_retrieval/case-eureka-lang"
    print(f"=== skill: {skill} ===\n=== case: {case_dir} ===\n")
    answer, trace = run_agent(skill, case_dir)
    print("\n" + "=" * 60 + "\n最终产物:\n" + "=" * 60)
    print(answer)
    print("\n" + "=" * 60 + f"\n执行轨迹: 共 {len(trace)} 次工具调用")
    for t in trace:
        print(f"  - {t['tool']}({t['args']})")
