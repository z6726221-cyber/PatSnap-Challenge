"""server.py 核心逻辑测试 —— mode→skill 映射、自动路由、降级。http 层做集成冒烟，不进单测。"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server


class TestModeToSkill(unittest.TestCase):
    def test_known_modes(self):
        self.assertEqual(server.mode_to_skill("qa"), "patsnap-tech-qa")
        self.assertEqual(server.mode_to_skill("comparison"), "patsnap-compare")
        self.assertEqual(server.mode_to_skill("promo"), "patsnap-promo")

    def test_unknown_mode_defaults_to_qa(self):
        self.assertEqual(server.mode_to_skill("nonsense"), "patsnap-tech-qa")


class TestSkillMode(unittest.TestCase):
    def test_skill_to_mode_roundtrip(self):
        self.assertEqual(server.skill_to_mode("patsnap-compare"), "comparison")
        self.assertEqual(server.skill_to_mode("patsnap-promo"), "promo")
        self.assertEqual(server.skill_to_mode("patsnap-tech-qa"), "qa")

    def test_skill_to_mode_unknown_defaults_qa(self):
        self.assertEqual(server.skill_to_mode("nope"), "qa")


class TestPickCase(unittest.TestCase):
    def test_pick_by_question_overlap(self):
        # 在真实样例目录下，问语言应命中 eureka-lang 那个 case
        cases = server.list_cases()
        if not cases:
            self.skipTest("无样例 case")
        picked = server.pick_case("Eureka 到底支持多少种语言")
        self.assertIn("eureka-lang", picked)

    def test_pick_never_empty(self):
        # 完全不相关的问题，也要给一个 case，不为空（模拟检索总会召回点东西）
        cases = server.list_cases()
        if not cases:
            self.skipTest("无样例 case")
        self.assertTrue(server.pick_case("随便问问"))


class TestHandleChat(unittest.TestCase):
    def test_auto_skill_returns_mode_from_agent(self):
        # 无 case → 走真实 live 通道；Agent 自主选了 compare → 后端把 skill 反推成 mode
        with mock.patch.object(server, "_has_live_material", return_value=True), \
             mock.patch.object(server, "load_live", return_value="fake-case"), \
             mock.patch.object(server, "run_agent_auto_with_case",
                               return_value=("对比表 📎 viking://x 🕐 2026-06",
                                             [{"tool": "select_skill", "args": {}}],
                                             "patsnap-compare")):
            out = server.handle_chat({"message": "Eureka 比竞品X强在哪"})
        self.assertIn("对比表", out["text"])
        self.assertEqual(out["degraded"], False)
        self.assertEqual(out["mode"], "comparison")   # 来自 Agent 的选择
        self.assertEqual(out["case"], "live")

    def test_explicit_mode_bypasses_auto(self):
        with mock.patch.object(server, "run_agent",
                               return_value=("x", [])) as m, \
             mock.patch.object(server, "run_agent_auto") as auto:
            out = server.handle_chat({"message": "任意", "mode": "promo", "case": "case-promo-search"})
        self.assertEqual(out["mode"], "promo")
        auto.assert_not_called()                      # 显式 mode 时不走自主选
        self.assertEqual(m.call_args[0][0], "patsnap-promo")

    def test_error_degrades(self):
        # live 通道内部出错（LLM 调用失败等）也要降级
        with mock.patch.object(server, "_has_live_material", return_value=True), \
             mock.patch.object(server, "load_live", return_value="fake-case"), \
             mock.patch.object(server, "run_agent_auto_with_case", side_effect=RuntimeError("LLM down")):
            out = server.handle_chat({"message": "Eureka 支持多少种语言"})
        self.assertEqual(out["degraded"], True)
        self.assertIn("text", out)
        self.assertNotEqual(out["text"], "")

    def test_no_live_material_degrades_without_fake_case_fallback(self):
        # live/ 里没有检索资料（检索系统还没跑过）→ 直接降级，不再退回假样例匹配
        with mock.patch.object(server, "_has_live_material", return_value=False), \
             mock.patch.object(server, "pick_case") as pick, \
             mock.patch.object(server, "run_agent_auto") as auto:
            out = server.handle_chat({"message": "随便问点什么"})
        self.assertEqual(out["degraded"], True)
        self.assertIn("live/ 暂无检索资料", out["degraded_reason"])
        pick.assert_not_called()      # 不应该退回假样例匹配
        auto.assert_not_called()

    def test_missing_message_returns_error(self):
        out = server.handle_chat({})
        self.assertIn("error", out)


if __name__ == "__main__":
    unittest.main()
