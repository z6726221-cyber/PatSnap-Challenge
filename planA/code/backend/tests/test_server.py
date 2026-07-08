"""server.py 核心逻辑测试 —— mode→skill 映射、降级。http 层做集成冒烟，不进单测。"""
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


class TestHandleChat(unittest.TestCase):
    def test_success_returns_text_and_trace(self):
        with mock.patch.object(server, "run_agent",
                               return_value=("答案 📎 viking://x 🕐 2026-06", [{"tool": "list_materials", "args": {}}])):
            out = server.handle_chat({"mode": "qa", "case": "case-eureka-lang"})
        self.assertIn("答案", out["text"])
        self.assertEqual(out["degraded"], False)
        self.assertEqual(len(out["trace"]), 1)

    def test_error_degrades(self):
        with mock.patch.object(server, "run_agent", side_effect=RuntimeError("LLM down")):
            out = server.handle_chat({"mode": "qa", "case": "case-eureka-lang"})
        self.assertEqual(out["degraded"], True)
        self.assertIn("text", out)          # 降级也要有可展示文本
        self.assertNotEqual(out["text"], "")

    def test_missing_case_returns_error(self):
        out = server.handle_chat({"mode": "qa"})
        self.assertIn("error", out)


if __name__ == "__main__":
    unittest.main()
