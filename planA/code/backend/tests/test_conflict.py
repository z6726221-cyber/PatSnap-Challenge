"""conflict.py 测试 —— 权威+时效裁决、曝光而非静默覆盖。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loader import Material
from conflict import adjudicate, ConflictVerdict


def _m(source, authority, updated_at, score=0.5, topic="t", body=""):
    return Material(source=source, updated_at=updated_at, authority=authority,
                    topic=topic, score=score, title=source, body=body)


class TestAdjudicate(unittest.TestCase):
    def test_prefers_higher_authority(self):
        official = _m("official", "L1", "2026-06")
        note = _m("note", "L4", "2025-11")
        v = adjudicate([note, official])
        self.assertEqual(v.primary.source, "official")   # L1 > L4
        self.assertTrue(v.has_conflict)
        self.assertEqual(v.others[0].source, "note")

    def test_same_authority_prefers_newer(self):
        old = _m("old", "L2", "2025-03")
        new = _m("new", "L2", "2026-01")
        v = adjudicate([old, new])
        self.assertEqual(v.primary.source, "new")         # 同 L2，新的赢

    def test_single_source_no_conflict(self):
        only = _m("only", "L1", "2026-06")
        v = adjudicate([only])
        self.assertFalse(v.has_conflict)
        self.assertEqual(v.others, [])

    def test_missing_time_sorts_last_within_authority(self):
        dated = _m("dated", "L2", "2026-01")
        undated = _m("undated", "L2", "")
        v = adjudicate([undated, dated])
        self.assertEqual(v.primary.source, "dated")       # 有时间的优先于无时间

    def test_conflict_note_mentions_others(self):
        official = _m("official", "L1", "2026-06")
        note = _m("note", "L4", "2025-11")
        v = adjudicate([note, official])
        text = v.conflict_note()
        self.assertIn("note", text)                       # 曝光另一来源
        self.assertIn("2025-11", text)                    # 曝光其时效
        self.assertNotEqual(text, "")


if __name__ == "__main__":
    unittest.main()
