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
        self.assertEqual(server.mode_to_skill("presales"), "patsnap-presales")

    def test_unknown_mode_defaults_to_qa(self):
        self.assertEqual(server.mode_to_skill("nonsense"), "patsnap-tech-qa")


class TestSkillMode(unittest.TestCase):
    def test_skill_to_mode_roundtrip(self):
        self.assertEqual(server.skill_to_mode("patsnap-compare"), "comparison")
        self.assertEqual(server.skill_to_mode("patsnap-promo"), "promo")
        self.assertEqual(server.skill_to_mode("patsnap-tech-qa"), "qa")
        self.assertEqual(server.skill_to_mode("patsnap-presales"), "presales")

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

    def test_video_promo_degrades_to_video_contract(self):
        with mock.patch.object(server, "_retrieve_local_case", side_effect=RuntimeError("no kb")), \
             mock.patch.object(server, "_has_live_material", return_value=False):
            out = server.handle_chat({"message": "内容形式：视频。生成一条活动预热视频", "mode": "promo"})
        self.assertEqual(out["degraded"], True)
        self.assertIn("## 视频生成提示词", out["text"])

    def test_promo_uses_local_retrieval_before_generation(self):
        case = server.Case(question="内容形式：文案。写 Analytics AI Mode 推文", materials=[
            server.Material(
                source="kb://promo/promo-1",
                updated_at="2026-07-10",
                authority="L2",
                topic="promo/IP Search",
                score=0.9,
                title="Analytics AI Mode 公众号首图",
                body="用于专利检索、专利解读相关传播。",
            )
        ])
        with mock.patch.object(server, "_has_live_material", return_value=False), \
             mock.patch.object(server, "_retrieve_local_case",
                               return_value=(case, {"source": "local-kb", "count": 1, "titles": ["Analytics AI Mode 公众号首图"]})), \
             mock.patch.object(server, "run_agent_with_case",
                               return_value=("基于检索资料生成的文案", [{"tool": "list_materials"}])) as run:
            out = server.handle_chat({"message": "内容形式：文案。写 Analytics AI Mode 推文", "mode": "promo"})
        self.assertEqual(out["degraded"], False)
        self.assertEqual(out["case"], "local-kb")
        self.assertEqual(out["retrieval"]["count"], 1)
        run.assert_called_once()

    def test_presales_combines_local_and_external_gap(self):
        case = server.Case(question="任务模块：完整报告；目标客户：制造业客户", materials=[
            server.Material(
                source="kb://sales/sales-1",
                updated_at="2026-07-10",
                authority="L2",
                topic="sales/数据库/销售话术",
                score=0.9,
                title="Analytics AI Mode 开场介绍",
                body="适用于首次拜访企业 IP 负责人。",
            )
        ])
        with mock.patch.object(server, "_has_live_material", return_value=False), \
             mock.patch.object(server, "_retrieve_local_case",
                               return_value=(case, {"source": "local-kb", "count": 1, "titles": ["Analytics AI Mode 开场介绍"]})), \
             mock.patch.object(server, "search_external_intel",
                               return_value={"available": False, "reason": "not configured", "items": []}), \
             mock.patch.object(server, "run_agent_with_case",
                               return_value=("## 客户拜访售前报告\n来源：`kb://sales/sales-1` 更新时间：2026-07-10", [{"tool": "list_materials"}])) as run:
            out = server.handle_chat({"message": "任务模块：完整报告；目标客户：制造业客户", "mode": "presales"})
        self.assertEqual(out["degraded"], False)
        self.assertEqual(out["mode"], "presales")
        self.assertIn("local-kb", out["case"])
        self.assertIn("external-intel-gap", out["case"])
        self.assertEqual(out["retrieval"]["external"]["available"], False)
        passed_case = run.call_args[0][1]
        self.assertIn("external-intel/gap", [m.source for m in passed_case.materials])

    def test_explicit_promo_prefers_live_retrieval_when_available(self):
        case = server.Case(question="内容形式：文案。写推文", materials=[
            server.Material(
                source="viking://live/a.md",
                updated_at="2026-07-10",
                authority="L1",
                topic="live",
                score=0.95,
                title="真实检索结果",
                body="真实检索正文",
            )
        ])
        with mock.patch.object(server, "_has_live_material", return_value=True), \
             mock.patch.object(server, "load_live", return_value=case) as load_live, \
             mock.patch.object(server, "_retrieve_local_case") as local, \
             mock.patch.object(server, "run_agent_with_case",
                               return_value=("基于 live 生成", [{"tool": "list_materials"}])):
            out = server.handle_chat({"message": "内容形式：文案。写推文", "mode": "promo"})
        self.assertEqual(out["degraded"], False)
        self.assertEqual(out["case"], "live")
        self.assertEqual(out["retrieval"]["source"], "live")
        self.assertEqual(out["retrieval"]["titles"], ["真实检索结果"])
        load_live.assert_called_once()
        local.assert_not_called()

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


class TestVideoPrompt(unittest.TestCase):
    def test_extract_video_prompt_from_text_block(self):
        text = "## 视频生成提示词\n```text\nA clean dashboard, slow zoom\n```"
        self.assertEqual(server.extract_video_prompt(text), "A clean dashboard, slow zoom")

    def test_extract_video_prompt_requires_section(self):
        with self.assertRaises(ValueError):
            server.extract_video_prompt("no prompt here")


class TestStructuredOutput(unittest.TestCase):
    def test_structure_output_extracts_sections_sources_and_missing_items(self):
        text = (
            "## 核心结论\n"
            "- 核心差异：我方支持可追溯回答。来源：`viking://a` 更新时间：2026-07-10\n\n"
            "## 待核实项清单\n"
            "1. 待核实：竞品是否支持跨语言检索。\n"
        )
        out = server.structure_output(text, "comparison")
        self.assertEqual([s["title"] for s in out["sections"]], ["核心结论", "待核实项清单"])
        self.assertEqual(out["citations"][0]["source"], "viking://a")
        self.assertEqual(out["citations"][0]["updated_at"], "2026-07-10")
        self.assertIn("竞品是否支持跨语言检索", out["missing_items"][0])

    def test_handle_chat_includes_structured_on_success(self):
        with mock.patch.object(server, "_has_live_material", return_value=True), \
             mock.patch.object(server, "load_live", return_value="fake-case"), \
             mock.patch.object(server, "run_agent_auto_with_case",
                               return_value=("## 回答\n来源：`viking://x` 更新时间：2026-07-10",
                                             [{"tool": "list_materials", "args": {}}],
                                             "patsnap-tech-qa")):
            out = server.handle_chat({"message": "Eureka 是什么"})
        self.assertIn("structured", out)
        self.assertEqual(out["structured"]["sections"][0]["title"], "回答")
        self.assertEqual(out["structured"]["citations"][0]["source"], "viking://x")


class TestImageGenerate(unittest.TestCase):
    def test_handle_image_generate_requires_text(self):
        out = server.handle_image_generate({})
        self.assertIn("error", out)
        self.assertIn("缺少 text", out["error"])

    def test_handle_image_generate_uses_image_client(self):
        fake = mock.MagicMock()
        fake.generate_poster.return_value = {
            "image_url": "/api/image/file/poster-test.png",
            "prompt": "poster prompt",
            "model": "gpt-image-2",
        }
        with mock.patch.object(server, "ImageClient", return_value=fake):
            out = server.handle_image_generate({"text": "写一条 AI Mode 推文", "instruction": "更科技感"})
        self.assertEqual(out["image_url"], "/api/image/file/poster-test.png")
        fake.generate_poster.assert_called_once_with("写一条 AI Mode 推文", instruction="更科技感")


if __name__ == "__main__":
    unittest.main()
