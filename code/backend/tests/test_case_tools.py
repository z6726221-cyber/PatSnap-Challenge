"""case_tools.py 测试 —— Agent 可调用的、基于已召回资料的工具。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loader import Case, Material
from case_tools import CaseTools


def _case():
    mats = [
        Material("uri-a", "2026-06-20", "L1", "eureka-lang", 0.92, "Eureka 多语言", "支持 12 种界面语言。"),
        Material("uri-b", "2025-11-02", "L4", "eureka-lang", 0.78, "旧笔记", "大概 9 种语言。"),
        Material("uri-c", "2026-05-10", "L2", "eureka-search", 0.80, "语义检索", "基于向量模型。"),
    ]
    return Case(question="Eureka 支持多少语言？", materials=mats)


class TestCaseTools(unittest.TestCase):
    def setUp(self):
        self.tools = CaseTools(_case())

    def test_list_materials(self):
        out = self.tools.list_materials()
        self.assertEqual(len(out["materials"]), 3)
        first = out["materials"][0]
        self.assertIn("source", first)
        self.assertIn("authority", first)
        self.assertIn("updated_at", first)
        self.assertIn("title", first)

    def test_read_material_by_source(self):
        out = self.tools.read_material(source="uri-a")
        self.assertIn("12 种", out["body"])
        self.assertEqual(out["updated_at"], "2026-06-20")

    def test_read_material_not_found(self):
        out = self.tools.read_material(source="nope")
        self.assertIn("error", out)

    def test_check_conflicts_flags_multi_source(self):
        out = self.tools.check_conflicts()
        # eureka-lang 有冲突，eureka-search 无
        conflicts = {c["topic"]: c for c in out["topics"]}
        self.assertTrue(conflicts["eureka-lang"]["has_conflict"])
        self.assertEqual(conflicts["eureka-lang"]["primary"]["source"], "uri-a")  # L1 主答案
        self.assertNotEqual(conflicts["eureka-lang"]["conflict_note"], "")
        self.assertFalse(conflicts["eureka-search"]["has_conflict"])

    def test_dispatch_table_covers_all(self):
        # TOOL_IMPL 调度表应能按名字调用
        impl = self.tools.impl()
        self.assertIn("list_materials", impl)
        self.assertIn("read_material", impl)
        self.assertIn("check_conflicts", impl)
        self.assertEqual(impl["list_materials"](), self.tools.list_materials())


if __name__ == "__main__":
    unittest.main()
