"""agent_runtime 的可离线测试部分：skill 清单解析、select_skill 工具、自动选 skill 循环。
真跑 LLM 的验证在 run_all.py，不进单测。"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agent_runtime as ar


class TestListSkills(unittest.TestCase):
    def test_lists_three_generation_skills(self):
        skills = ar.list_skills()
        names = {s["name"] for s in skills}
        self.assertIn("patsnap-tech-qa", names)
        self.assertIn("patsnap-compare", names)
        self.assertIn("patsnap-promo", names)
        # 每个都要有非空 description（给 Agent 判断用）
        for s in skills:
            self.assertTrue(s["description"].strip())

    def test_skill_name_matches_dir(self):
        skills = ar.list_skills()
        for s in skills:
            self.assertTrue(os.path.isdir(os.path.join(ar.SKILLS_DIR, s["name"])))


class TestAutoSkillLoop(unittest.TestCase):
    def _fake_cli(self, scripted):
        """scripted: 一列 (content, tool_calls) 供 chat 依次返回。"""
        cli = mock.MagicMock()
        cli.chat.side_effect = [({"content": c, "tool_calls": tc}, {}) for c, tc in scripted]
        return cli

    def _tc(self, tid, name, args_json):
        return {"id": tid, "function": {"name": name, "arguments": args_json}}

    def test_agent_selects_skill_then_executes(self):
        # 第1轮：Agent 调 select_skill 选竞品；第2轮：调 list_materials；第3轮：给最终答案
        scripted = [
            ("我判断这是竞品对比。", [self._tc("t1", "select_skill", '{"skill_name": "patsnap-compare"}')]),
            ("", [self._tc("t2", "list_materials", "{}")]),
            ("最终对比表。", None),
        ]
        cli = self._fake_cli(scripted)
        with mock.patch.object(ar, "LLMClient", return_value=cli):
            text, trace, selected = ar.run_agent_auto(
                os.path.join(ar.SAMPLE_DIR, "case-compare-lang"), verbose=False)
        self.assertEqual(selected, "patsnap-compare")
        self.assertIn("对比表", text)
        # trace 里第一步应是 select_skill
        self.assertEqual(trace[0]["tool"], "select_skill")
        # select_skill 的返回里应含该 skill 的 SKILL.md 全文（含 workflow 关键字）
        self.assertIn("Workflow", trace[0]["result"]["skill_md"])

    def test_unknown_skill_returns_error_result(self):
        scripted = [
            ("", [self._tc("t1", "select_skill", '{"skill_name": "nope"}')]),
            ("兜底回答。", None),
        ]
        cli = self._fake_cli(scripted)
        with mock.patch.object(ar, "LLMClient", return_value=cli):
            text, trace, selected = ar.run_agent_auto(
                os.path.join(ar.SAMPLE_DIR, "case-eureka-lang"), verbose=False)
        self.assertIn("error", trace[0]["result"])
        self.assertIsNone(selected)


if __name__ == "__main__":
    unittest.main()
