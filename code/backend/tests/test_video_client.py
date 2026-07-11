import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import video_client
from video_client import VideoClient


class TestOpenAIVideoEndpoint(unittest.TestCase):
    def make_env(self):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write("VIDEO_BASE_URL=https://llm-api.patsnap.info/v1\n")
            f.write("VIDEO_MODEL=doubao-seedance-2.0\n")
            f.write("VIDEO_API_KEY=test-key\n")
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def test_submit_uses_videos_generations_endpoint(self):
        client = VideoClient(env_path=self.make_env())
        with mock.patch.object(client, "_request", return_value={
            "data": [{"url": "https://example.com/video.mp4"}],
            "status": "succeeded",
        }) as req, \
             mock.patch.object(video_client, "_save_task"):
            task_id = client.submit_text2video("A clean enterprise SaaS video", duration="5")

        self.assertTrue(task_id.startswith("video-"))
        method, path, payload = req.call_args[0]
        self.assertEqual(method, "POST")
        self.assertEqual(path, "/videos/generations")
        self.assertEqual(payload["model"], "doubao-seedance-2.0")
        self.assertEqual(payload["duration"], "5")
        self.assertEqual(payload["input"][0]["type"], "text")
        self.assertIn("prompt", payload["input"][0])
        self.assertNotIn("prompt", payload)

    def test_parse_immediate_video_url_response(self):
        parsed = video_client._parse_openai_video_response({
            "id": "gen-1",
            "data": [{"url": "https://example.com/video.mp4"}],
            "status": "completed",
        })
        self.assertEqual(parsed["task_id"], "gen-1")
        self.assertEqual(parsed["status"], "succeed")
        self.assertEqual(parsed["video_url"], "https://example.com/video.mp4")

    def test_parse_async_task_response(self):
        parsed = video_client._parse_openai_video_response({
            "task_id": "task-123",
            "status": "queued",
            "message": "submitted",
        })
        self.assertEqual(parsed["task_id"], "task-123")
        self.assertEqual(parsed["status"], "processing")
        self.assertIsNone(parsed["video_url"])

    def test_status_uses_task_id_query(self):
        client = VideoClient(env_path=self.make_env())
        local_task = {
            "status": "processing",
            "video_url": None,
            "message": "视频任务已提交",
            "provider": "doubao-seedance",
            "remote_task_id": "volcengine_task/with space",
        }
        with mock.patch.object(client, "_request", return_value={
            "output": [{"url": "", "task_status": "running", "error": None}]
        }) as req, \
             mock.patch.object(video_client, "_save_task"):
            out = client._get_openai_video_status("video-local", local_task)

        self.assertEqual(out["status"], "processing")
        self.assertEqual(req.call_args[0][0], "GET")
        self.assertEqual(req.call_args[0][1], "/videos/generations?task_id=volcengine_task%2Fwith%20space")


if __name__ == "__main__":
    unittest.main()
