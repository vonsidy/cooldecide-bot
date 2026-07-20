import json
import tempfile
import unittest
from unittest import mock

import dashboard


class DashboardClipCheckTests(unittest.TestCase):
    def test_record_attaches_report_to_video_and_summary(self) -> None:
        report = {
            "reportId": "report-1",
            "botId": "kids",
            "assetId": "asset-1",
            "decision": "review",
            "score": 80,
            "findings": [],
        }

        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as data_file, \
                mock.patch.object(dashboard, "DATA_FILE", data_file.name):
            json.dump({}, data_file)
            data_file.flush()
            dashboard.record(
                "video-1", "Title", "wyr", 3,
                privacy="public", clipcheck_report=report,
            )
            data_file.seek(0)
            saved = json.load(data_file)

        self.assertEqual(saved["videos"][0]["clipcheck"]["reportId"], "report-1")
        self.assertEqual(saved["clipcheck"]["latest"]["score"], 80)
        self.assertEqual(saved["clipcheck"]["mode"], "observation")


if __name__ == "__main__":
    unittest.main()

