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
SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "sample_retrieval")
SOUL_PATH = os.path.join(SKILLS_DIR, "SOUL.md")

# 所有模式共享的行为底线：不编造、只信工具返回的资料、标"待核实"。
COMMON_RULES = (
    "本次的资料已由检索系统召回好，你通过 list_materials / read_material / "
    "check_conflicts 三个工具访问它们。不要凭记忆编造知识，所有事实都必须来自"
    "工具返回的资料，并附上来源和更新时间；资料没有支撑的点，标「待核实」。"
)


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _skill_frontmatter(skill_md):
    """从 SKILL.md 抽 name 与 description（description 可能是多行折叠标量）。"""
    if not skill_md.startswith("---"):
        return "", ""
    end = skill_md.find("\n---", 3)
    fm = skill_md[3:end] if end != -1 else skill_md
    name, desc, in_desc, desc_lines = "", "", False, []
    for line in fm.splitlines():
        if in_desc:
            # 折叠标量的续行是缩进的；遇到下一个顶层 key 就停
            if line and not line[0].isspace():
                in_desc = False
            else:
                desc_lines.append(line.strip())
                continue
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("description:"):
            rest = line.split(":", 1)[1].strip()
            if rest in (">-", ">", "|", "|-", ""):
                in_desc = True          # 多行折叠，后续缩进行是内容
            else:
                desc = rest.strip('"').strip("'")
    if desc_lines:
        desc = " ".join(x for x in desc_lines if x)
    return name, desc


def list_skills():
    """扫 skills 目录，返回 [{name, description}]，供 Agent 自主判断该用哪个。"""
    out = []
    for entry in sorted(os.listdir(SKILLS_DIR)):
        skill_path = os.path.join(SKILLS_DIR, entry, "SKILL.md")
        if os.path.exists(skill_path):
            name, desc = _skill_frontmatter(_read(skill_path))
            out.append({"name": name or entry, "description": desc})
    return out


def load_skill_prompt(skill_name):
    """读 SOUL.md + SKILL.md + 其引用的 references，拼成给 Agent 的 system prompt。
    SOUL.md 是三个生成 skill 共享的恒定注入层，无条件拼入，不依赖 SKILL.md 正文有没有提到它。"""
    skill_dir = os.path.join(SKILLS_DIR, skill_name)
    skill_md = _read(os.path.join(skill_dir, "SKILL.md"))

    # 收集 SKILL.md 里引用的 references 路径（../references/x.md、./references/x.md 或 references/x.md）
    ref_paths = set(re.findall(r"`?(?:\.\.?/)?references/[^\s`）)]+\.md`?", skill_md))
    ref_blocks = []
    for rp in sorted(ref_paths):
        clean = rp.strip("`")
        abs_path = os.path.normpath(os.path.join(skill_dir, clean))
        if os.path.exists(abs_path):
            ref_blocks.append(f"\n\n===== 引用文档: {clean} =====\n" + _read(abs_path))

    soul_block = ""
    if os.path.exists(SOUL_PATH):
        soul_block = "\n\n===== SOUL.md（语言人格层，恒定注入）=====\n" + _read(SOUL_PATH)

    system = (
        "你是「芽懂」——智慧芽私域知识库的技术助手。你已加载下面这个 skill，"
        "必须严格按它的 Workflow、Output Contract 和 Boundaries 执行。\n"
        + COMMON_RULES + "\n"
        "如果 Workflow 要求'先读某些 references'，这些内容已附在下方，视为你已读。\n"
        + soul_block +
        "\n\n===== SKILL.md =====\n" + skill_md + "".join(ref_blocks)
    )
    return system


# select_skill 工具：让 Agent 自主判断该用哪个 skill。
# Agent 调用它并给出 skill_name → 后端把该 skill 的完整 SKILL.md 回给它 → 据此执行。
SELECT_SKILL_TOOL = {
    "type": "function", "function": {
        "name": "select_skill",
        "description": "根据用户问题，从可选 skill 里选一个最合适的并加载它。这是你的第一步：先想清楚这是技术问答、竞品对比、还是宣传生成，再选对应 skill。工具会返回该 skill 的完整操作说明（Workflow/Output Contract/Boundaries），你之后严格照它执行。",
        "parameters": {"type": "object", "properties": {
            "skill_name": {"type": "string", "description": "要加载的 skill 名，取自可选 skill 列表的 name 字段"},
        }, "required": ["skill_name"]}}}


def run_agent_auto(case_dir, max_turns=8, verbose=True):
    """Agent 自主选 skill，case 来自假样例 case 文件夹（case-xxx/question.txt + md）。
    返回 (最终产物, 轨迹, 被选中的 skill 名)。"""
    return run_agent_auto_with_case(load_case(case_dir), max_turns=max_turns, verbose=verbose)


def run_agent_auto_with_case(case, max_turns=8, verbose=True):
    """Agent 自主选 skill：system 只给三个 skill 的 name+description，
    Agent 先 select_skill 选能力（后端回传该 skill 全文），再用 case 工具执行。
    接收一个已构建好的 Case（假样例 case 文件夹或真实检索 live 目录皆可）。
    返回 (最终产物, 轨迹, 被选中的 skill 名)。"""
    cli = LLMClient()
    tools_obj = CaseTools(case)
    tool_impl = tools_obj.impl()

    skills = list_skills()
    catalog = "\n".join(f"- {s['name']}: {s['description']}" for s in skills)
    system = (
        "你是「芽懂」——智慧芽私域知识库的技术助手。用户会用大白话提一个需求，"
        "你要先判断它属于下面哪个 skill 的场景，用 select_skill 加载那个 skill，"
        "然后严格按它返回的 Workflow / Output Contract / Boundaries 执行。\n\n"
        "可选 skill：\n" + catalog + "\n\n"
        + COMMON_RULES + "\n"
        "第一步必须是 select_skill。select_skill 返回的内容已包含 SOUL.md（语言人格层），"
        "生成产物前必须先按它统一术语和风格底线。"
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": case.question},
    ]
    all_tools = [SELECT_SKILL_TOOL] + TOOLS
    trace = []
    selected = None

    for turn in range(max_turns):
        msg, usage = cli.chat(messages, tools=all_tools)
        assistant_msg = {"role": "assistant", "content": msg.get("content") or ""}
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        messages.append(assistant_msg)

        if not tool_calls:
            if verbose:
                print(f"[turn {turn}] Agent 给出最终产物。")
            return msg.get("content", ""), trace, selected

        for tc in tool_calls:
            fname = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}

            if fname == "select_skill":
                sname = args.get("skill_name", "")
                skill_path = os.path.join(SKILLS_DIR, sname, "SKILL.md")
                if os.path.exists(skill_path):
                    selected = sname
                    result = {"skill_md": load_skill_prompt(sname)}
                    if verbose:
                        print(f"[turn {turn}] Agent 选择 skill: {sname}")
                else:
                    result = {"error": f"未知 skill: {sname}",
                              "available": [s["name"] for s in skills]}
            else:
                impl = tool_impl.get(fname)
                if impl is None:
                    result = {"error": f"unknown tool {fname}"}
                else:
                    try:
                        result = impl(**args)
                    except Exception as e:  # noqa
                        result = {"error": str(e)}
                if verbose:
                    print(f"[turn {turn}] 调用 {fname}({args})")

            trace.append({"turn": turn, "tool": fname, "args": args, "result": result})
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })

    return "(达到最大轮次，未收敛)", trace, selected


def run_agent(skill_name, case_dir, max_turns=8, verbose=True):
    """加载 skill + 假样例 case 文件夹，让 Agent 生成产物。返回 (最终产物, 轨迹)。"""
    return run_agent_with_case(skill_name, load_case(case_dir), max_turns=max_turns, verbose=verbose)


def run_agent_with_case(skill_name, case, max_turns=8, verbose=True):
    """加载 skill + 已构建好的 Case（假样例或真实检索 live 目录皆可），让 Agent 生成产物。
    返回 (最终产物, 轨迹)。"""
    cli = LLMClient()
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
