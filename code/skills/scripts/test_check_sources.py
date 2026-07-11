"""check_sources.py 测试 —— 标准库 unittest，零第三方依赖。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_sources as cs


class TestFindFakeSourceLabels(unittest.TestCase):
    def test_single_real_uri_not_flagged(self):
        t = "来源：`viking://resources/a.md`，更新时间：2026-06-20"
        self.assertEqual(cs._find_fake_source_labels(t), [])

    def test_single_real_url_not_flagged(self):
        t = "来源：https://example.com/a，更新时间：时间未知"
        self.assertEqual(cs._find_fake_source_labels(t), [])

    def test_multiple_real_uris_separated_by_dun_not_flagged(self):
        t = "来源：`viking://resources/a.md`、`viking://resources/b.md`、`viking://resources/c.md`，更新时间：时间未知"
        self.assertEqual(cs._find_fake_source_labels(t), [])

    def test_single_fake_label_flagged(self):
        t = "结论：xxx。（来源：S1，更新时间：时间未知）"
        self.assertEqual(cs._find_fake_source_labels(t), ["S1"])

    def test_multiple_fake_labels_all_flagged_not_just_first(self):
        # 回归：多来源用"、"分隔时，早期实现只抓第一个 token，这里要求全部抓到
        t = ("来源：`LS_算法团队_2026_Q3_工_2more_4208e84b.md`、"
             "`2._Q3_团队_OKR.md`、"
             "`7._主线四工程服务与交付_6more_2d5b89e6.md`，更新时间：时间未知")
        self.assertEqual(
            cs._find_fake_source_labels(t),
            ["LS_算法团队_2026_Q3_工_2more_4208e84b.md", "2._Q3_团队_OKR.md",
             "7._主线四工程服务与交付_6more_2d5b89e6.md"],
        )

    def test_mixed_real_and_fake_only_fake_flagged(self):
        t = "来源：`viking://resources/a.md`、`S2`，更新时间：2026-06"
        self.assertEqual(cs._find_fake_source_labels(t), ["S2"])

    def test_honest_missing_label_not_flagged(self):
        for label in ["来源：待核实", "来源：未找到", "来源：无来源", "来源：无资料"]:
            self.assertEqual(cs._find_fake_source_labels(label), [], label)

    def test_tool_call_reference_not_flagged(self):
        # check_conflicts() 这类是真实发生的工具调用引用，不是编造的来源
        for label in ["来源：check_conflicts()", "来源：list_materials()",
                      "来源：read_material(viking://x)"]:
            self.assertEqual(cs._find_fake_source_labels(label), [], label)

    def test_presales_local_source_schemes_not_flagged(self):
        # 回归：patsnap-presales 用 kb:// / external-intel/ / uploads/ / public-demo://
        # 这几种非 viking:// 的本地来源，之前被误判为"疑似虚假来源标注"
        for label in ["来源：kb://sales/1", "来源：external-intel/0",
                      "来源：external-intel/gap", "来源：uploads/客户会议纪要.pdf",
                      "来源：public-demo://unknown"]:
            self.assertEqual(cs._find_fake_source_labels(label), [], label)


class TestCheckReturnCode(unittest.TestCase):
    def test_fake_label_triggers_warning_exit_code(self):
        text = ("结论：xxx。（来源：S1，更新时间：时间未知）\n"
                 "| 主线 | 说明 | 来源 |\n| --- | --- | --- |\n| A | xxx | S1 |\n")
        self.assertEqual(cs.check(text), 1)

    def test_real_uri_with_time_passes(self):
        text = "结论：Eureka 支持 12 种语言。（来源：`viking://resources/a.md`，更新时间：2026-06-20）"
        self.assertEqual(cs.check(text), 0)

    def test_presales_kb_and_external_intel_source_passes(self):
        text = ("客户切换成本较高。来源：kb://sales/1，更新时间：2026-07-10\n"
                "外部新闻显示该公司扩大了研发团队规模。来源：external-intel/0，更新时间：2026-07-01")
        self.assertEqual(cs.check(text), 0)


if __name__ == "__main__":
    unittest.main()
