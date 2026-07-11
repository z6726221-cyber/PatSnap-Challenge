import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import image_client
from image_client import ImageClient


class TestImageFallback(unittest.TestCase):
    def make_env(self, image_model="doubao-seedream-5.0-lite", fallback_model="doubao-seedream-4.5"):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write("IMAGE_BASE_URL=https://llm-api.patsnap.info/v1\n")
            f.write(f"IMAGE_MODEL={image_model}\n")
            f.write(f"IMAGE_FALLBACK_MODEL={fallback_model}\n")
            f.write("IMAGE_API_KEY=test-key\n")
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def test_default_seedream_uses_large_size_without_first_failure(self):
        client = ImageClient(env_path=self.make_env())
        with mock.patch.object(client, "_request", return_value={
            "data": [{"url": "https://example.com/poster.jpeg"}],
        }) as req:
            out = client.generate_poster("AI Mode 推文", size="1024x1024")

        self.assertEqual(out["model"], "doubao-seedream-5.0-lite")
        self.assertEqual(out["size"], "1920x1920")
        payload = req.call_args[0][2]
        self.assertEqual(payload["model"], "doubao-seedream-5.0-lite")
        self.assertEqual(payload["size"], "1920x1920")

    def test_billing_error_falls_back_to_seedream_large_size(self):
        client = ImageClient(env_path=self.make_env("gpt-image-2", "doubao-seedream-5.0-lite"))
        err = RuntimeError("图片服务 HTTP 400: billing_hard_limit_reached")
        with mock.patch.object(client, "_request", side_effect=[
            err,
            {"data": [{"url": "https://example.com/poster.jpeg"}]},
        ]) as req:
            out = client.generate_poster("AI Mode 推文", size="1024x1024")

        self.assertEqual(out["image_url"], "https://example.com/poster.jpeg")
        self.assertEqual(out["model"], "doubao-seedream-5.0-lite")
        self.assertEqual(out["size"], "1920x1920")
        first_payload = req.call_args_list[0][0][2]
        second_payload = req.call_args_list[1][0][2]
        self.assertEqual(first_payload["model"], "gpt-image-2")
        self.assertEqual(first_payload["size"], "1024x1024")
        self.assertEqual(second_payload["model"], "doubao-seedream-5.0-lite")
        self.assertEqual(second_payload["size"], "1920x1920")

    def test_parse_size(self):
        self.assertEqual(image_client._parse_size("1920x1080"), (1920, 1080))
        self.assertEqual(image_client._parse_size("bad"), (0, 0))


if __name__ == "__main__":
    unittest.main()
