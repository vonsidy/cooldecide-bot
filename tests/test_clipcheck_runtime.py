import json
import os
import tempfile
import unittest
from unittest import mock

import clipcheck_runtime


class ClipCheckRuntimeTests(unittest.TestCase):
    def test_clean_vertical_video_passes(self) -> None:
        payload = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920},
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {"duration": "35.0"},
        }
        completed = mock.Mock(stdout=json.dumps(payload))

        with tempfile.NamedTemporaryFile(suffix=".mp4") as video, \
                mock.patch("clipcheck_runtime.subprocess.run", return_value=completed):
            video.write(b"video bytes")
            video.flush()
            report = clipcheck_runtime.analyze_video(video.name)

        self.assertEqual(report["decision"], "pass")
        self.assertEqual(report["score"], 100)
        self.assertEqual(report["botId"], "kids")

    def test_probe_failure_blocks(self) -> None:
        report = clipcheck_runtime.analyze_video("missing.mp4")

        self.assertEqual(report["decision"], "block")
        self.assertEqual(report["score"], 0)


if __name__ == "__main__":
    unittest.main()

