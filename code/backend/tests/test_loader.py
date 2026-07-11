"""loader.py 测试 —— 用标准库 unittest，零第三方依赖（本环境无 pytest）。"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import loader
from loader import parse_material, parse_materials_from_file, load_case, load_live, group_by_topic, Material


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


class TestParseMaterialsFromFile(unittest.TestCase):
    """OpenViking 原始检索包解析 —— 一个文件里塞多条命中，无 frontmatter。"""

    def _raw_pack(self, with_full_text=True):
        full_text_block = (
            "\n全文内容：\n\nB 完整正文。\n"
            if with_full_text else ""
        )
        return (
            "# OpenViking 检索结果包\n\n"
            "- 候选资源数：2\n\n"
            "## 命中资源明细\n\n"
            "### 1. viking://resources/a.md\n\n"
            "- 关键词匹配分：43\n"
            "- URI：`viking://resources/a.md`\n\n"
            "摘要/片段：\n\nA 摘要...(truncated for embedding)\n\n"
            "### 2. viking://resources/b.md\n\n"
            "- 关键词匹配分：40\n"
            "- URI：`viking://resources/b.md`\n\n"
            "摘要/片段：\n\nB 摘要片段。\n"
            f"{full_text_block}\n"
            "## 原始工具返回\n\n"
            "```json\n{\"resources\": []}\n```\n"
        )

    def test_splits_into_multiple_materials_by_hit_entry(self):
        mats = parse_materials_from_file(self._raw_pack(), filename="raw.md")
        self.assertEqual(len(mats), 2)
        self.assertEqual(mats[0].source, "viking://resources/a.md")
        self.assertEqual(mats[1].source, "viking://resources/b.md")
        self.assertEqual(mats[0].score, 43.0)
        self.assertEqual(mats[1].score, 40.0)

    def test_prefers_full_text_over_abstract(self):
        mats = parse_materials_from_file(self._raw_pack(with_full_text=True), filename="raw.md")
        self.assertIn("B 完整正文", mats[1].body)

    def test_falls_back_to_abstract_with_truncation_note(self):
        mats = parse_materials_from_file(self._raw_pack(), filename="raw.md")
        self.assertIn("A 摘要", mats[0].body)
        self.assertIn("可能被截断", mats[0].body)

    def test_no_hit_section_falls_back_to_single_material(self):
        # 没有"命中资源明细"小节 → 退回契约理想格式，整份文件当一条资料
        text = "---\nsource: x\n---\n纯正文\n"
        mats = parse_materials_from_file(text, filename="ideal.md")
        self.assertEqual(len(mats), 1)
        self.assertEqual(mats[0].source, "x")

    def test_hit_entry_headers_inside_body_do_not_split_further(self):
        # 命中条目正文本身含 "## N. xxx" 二级标题（原文片段），不应被误判为
        # 小节结束点或新条目，必须完整保留在同一条 Material 里。
        text = (
            "## 命中资源明细\n\n"
            "### 1. viking://resources/c.md\n\n"
            "- URI：`viking://resources/c.md`\n\n"
            "全文内容：\n\n"
            "## 7. 主线四：工程服务与交付\n\n正文内容...\n\n"
            "## 8. 交付保障\n\n更多正文...\n"
        )
        mats = parse_materials_from_file(text, filename="raw.md")
        self.assertEqual(len(mats), 1)
        self.assertIn("交付保障", mats[0].body)


class TestLoadLive(unittest.TestCase):
    """load_live() —— 真实检索场景：固定目录、每次覆盖、question 由调用方传入（不读 question.txt）。"""

    def test_reads_single_md_with_frontmatter(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "01-a.md", "---\nsource: uri-a\nupdated_at: 2026-06\ntopic: t1\nscore: 0.9\n---\nA正文\n")
            case = load_live(d, question="用户实时提的问题")
            self.assertEqual(case.question, "用户实时提的问题")
            self.assertEqual(len(case.materials), 1)
            self.assertEqual(case.materials[0].source, "uri-a")

    def test_multiple_md_files_all_parsed_and_merged(self):
        # 检索侧可能按子查询分开写多个 md；每个都要被读到，合并进同一个 Case
        with tempfile.TemporaryDirectory() as d:
            _write(d, "01-a.md", "---\nsource: uri-a\ntopic: t1\nscore: 0.9\n---\nA正文\n")
            _write(d, "02-b.md", "---\nsource: uri-b\ntopic: t2\nscore: 0.5\n---\nB正文\n")
            case = load_live(d, question="q")
            sources = {m.source for m in case.materials}
            self.assertEqual(sources, {"uri-a", "uri-b"})

    def test_single_file_with_multiple_hit_entries_all_extracted(self):
        # 一个 md 内含多条命中（OpenViking 检索包格式）也要全部拆出来
        raw_pack = (
            "## 命中资源明细\n\n"
            "### 1. viking://resources/a.md\n\n- URI：`viking://resources/a.md`\n\n全文内容：\n\nA\n\n"
            "### 2. viking://resources/b.md\n\n- URI：`viking://resources/b.md`\n\n全文内容：\n\nB\n\n"
            "## 原始工具返回\n\n```json\n{}\n```\n"
        )
        with tempfile.TemporaryDirectory() as d:
            _write(d, "search-result.md", raw_pack)
            case = load_live(d, question="q")
            self.assertEqual(len(case.materials), 2)

    def test_missing_dir_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_live("/tmp/definitely-not-a-real-live-dir-xyz", question="q")

    def test_dir_with_no_md_raises(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                load_live(d, question="q")

    def test_retries_on_concurrent_overwrite_then_succeeds(self):
        # 模拟检索侧正在覆盖目录：第一次读到的文件列表前后不一致（并发写入的
        # 典型信号），第二次读到时已经写完、前后一致 —— 应该重试后成功，不报错。
        with tempfile.TemporaryDirectory() as d:
            _write(d, "01-a.md", "---\nsource: uri-a\ntopic: t1\nscore: 0.9\n---\nA正文\n")
            call_count = {"n": 0}
            real_list_md = loader._list_md

            def flaky_list_md(live_dir):
                call_count["n"] += 1
                # 第一次 _read_live_snapshot 内的"读后"校验（第 2 次调用 _list_md）
                # 返回一个和"读前"不同的假列表，制造一次不一致；之后正常。
                if call_count["n"] == 2:
                    return ["01-a.md", "02-b.md"]
                return real_list_md(live_dir)

            with mock.patch.object(loader, "_list_md", side_effect=flaky_list_md), \
                 mock.patch.object(loader.time, "sleep"):
                case = load_live(d, question="q", retries=3, retry_delay=0)
            self.assertEqual(len(case.materials), 1)
            self.assertGreater(call_count["n"], 2)   # 确认真的重试了，不是凑巧一次过

    def test_persistent_inconsistency_raises_after_retries_exhausted(self):
        # 一直不一致（检索侧持续在写、迟迟没写完）→ 重试用尽后应该报错，而不是
        # 悄悄返回一份不完整/错乱的数据。
        with tempfile.TemporaryDirectory() as d:
            _write(d, "01-a.md", "---\nsource: uri-a\n---\nA\n")
            real_list_md = loader._list_md
            call_count = {"n": 0}

            def always_flaky(live_dir):
                call_count["n"] += 1
                # 每次"读后"校验都返回和"读前"不同的列表 —— 永远不一致
                if call_count["n"] % 2 == 0:
                    return ["01-a.md", "99-ghost.md"]
                return real_list_md(live_dir)

            with mock.patch.object(loader, "_list_md", side_effect=always_flaky), \
                 mock.patch.object(loader.time, "sleep"):
                with self.assertRaises(RuntimeError):
                    load_live(d, question="q", retries=3, retry_delay=0)

    def test_file_deleted_mid_read_retries_then_succeeds(self):
        # 单个文件在读取瞬间被删除（覆盖写入时先删旧文件）→ OSError，应重试；
        # 重试时目录已经是新内容，读成功。
        with tempfile.TemporaryDirectory() as d:
            _write(d, "01-a.md", "---\nsource: uri-a\n---\nA\n")
            call_count = {"n": 0}
            real_open = open

            def flaky_open(path, *a, **kw):
                call_count["n"] += 1
                if call_count["n"] == 1 and path.endswith("01-a.md"):
                    raise OSError("file vanished mid-read (simulated overwrite)")
                return real_open(path, *a, **kw)

            with mock.patch("builtins.open", side_effect=flaky_open), \
                 mock.patch.object(loader.time, "sleep"):
                case = load_live(d, question="q", retries=3, retry_delay=0)
            self.assertEqual(len(case.materials), 1)


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
