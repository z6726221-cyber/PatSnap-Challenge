import os
import unittest
from unittest import mock

import external_search


class ExternalSearchMockTest(unittest.TestCase):
    def test_mock_external_endpoint_reads_fixture_materials(self):
        with mock.patch.dict(os.environ, {"EXTERNAL_SEARCH_ENDPOINT": "mock"}, clear=True):
            out = external_search.search_external_intel("Engineering 研发团队 专利检索", limit=2)
        self.assertTrue(out["available"])
        self.assertIn("mock_external", out["reason"])
        self.assertGreaterEqual(len(out["items"]), 1)
        self.assertTrue(any(item["url"].startswith("public-demo://") for item in out["items"]))

    def test_missing_endpoint_is_explicit_gap_not_mock(self):
        with mock.patch.dict(os.environ, {"EXTERNAL_SEARCH_ENDPOINT": ""}, clear=True):
            out = external_search.search_external_intel("Engineering 研发团队", limit=2)
        self.assertFalse(out["available"])
        self.assertEqual(out["items"], [])
        self.assertIn("未配置 EXTERNAL_SEARCH_ENDPOINT", out["reason"])


if __name__ == "__main__":
    unittest.main()
