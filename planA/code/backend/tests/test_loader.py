"""loader.py 测试 —— 用标准库 unittest，零第三方依赖（本环境无 pytest）。"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loader import parse_material, load_case, group_by_topic, Material


def _write(dir_path, name, content):
    with open(os.path.join(dir_path, name), "w", encoding="utf-8") as f:
        f.write(content)


class TestParseMaterial(unittest.TestCase):
    def test_parse_full_frontmatter(self):
        md = ("---\n"
              "source: viking://resources/products/eureka/lang-support.md\n"
              "updated_at: 2026-06-20\n"
              "authority: L1\n"
              "topic: eureka-lang\n"
              "score: 0.92\n"
              "title: Eureka 多语言支持\n"
              "---\n\n"
              "# Eureka 多语言支持\n\nEureka 支持 12 种界面语言。\n")
        m = parse_material(md, filename="01-lang-support.md")
        self.assertEqual(m.source, "viking://resources/products/eureka/lang-support.md")
        self.assertEqual(m.updated_at, "2026-06-20")
        self.assertEqual(m.authority, "L1")
        self.assertEqual(m.topic, "eureka-lang")
        self.assertEqual(m.score, 0.92)
        self.assertEqual(m.title, "Eureka 多语言支持")
        self.assertIn("12 种界面语言", m.body)

    def test_missing_fields_degrade(self):
        # 只有正文，无 frontmatter → 全部降级
        m = parse_material("# 纯正文\n没有元信息。\n", filename="raw.md")
        self.assertEqual(m.source, "")           # 缺 source
        self.assertEqual(m.updated_at, "")       # 缺时间
        self.assertEqual(m.authority, "L4")      # 缺权威 → 最低
        self.assertEqual(m.title, "raw.md")      # 缺标题 → 文件名兜底
        self.assertIn("纯正文", m.body)

    def test_missing_topic_uses_filename(self):
        md = "---\nsource: x\nupdated_at: 2026-01\n---\n正文\n"
        m = parse_material(md, filename="mydoc.md")
        self.assertEqual(m.topic, "mydoc.md")    # 缺 topic → 文件名兜底


class TestLoadCase(unittest.TestCase):
    def test_load_case_reads_question_and_materials(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "question.txt", "客户问支持多少语言？\n")
            _write(d, "01-a.md", "---\nsource: uri-a\nupdated_at: 2026-06\nauthority: L1\ntopic: t1\nscore: 0.9\n---\nA正文\n")
            _write(d, "02-b.md", "---\nsource: uri-b\nupdated_at: 2025-11\nauthority: L4\ntopic: t1\nscore: 0.7\n---\nB正文\n")
            case = load_case(d)
            self.assertEqual(case.question, "客户问支持多少语言？")
            self.assertEqual(len(case.materials), 2)
            # 按 score 降序
            self.assertEqual(case.materials[0].source, "uri-a")

    def test_load_case_missing_question_raises(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "01-a.md", "---\nsource: x\n---\n正文\n")
            with self.assertRaises(FileNotFoundError):
                load_case(d)


class TestGroupByTopic(unittest.TestCase):
    def test_group_detects_multi_source_topic(self):
        mats = [
            Material(source="a", updated_at="2026-06", authority="L1", topic="eureka-lang", score=0.9, title="A", body="12种"),
            Material(source="b", updated_at="2025-11", authority="L4", topic="eureka-lang", score=0.7, title="B", body="9种"),
            Material(source="c", updated_at="2026-05", authority="L2", topic="eureka-search", score=0.8, title="C", body="语义"),
        ]
        groups = group_by_topic(mats)
        self.assertEqual(len(groups["eureka-lang"]), 2)   # 同话题多来源
        self.assertEqual(len(groups["eureka-search"]), 1)


if __name__ == "__main__":
    unittest.main()
