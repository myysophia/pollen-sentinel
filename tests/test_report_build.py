"""报告生成器的快照路径回归测试。"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from reporter.build_report import _load_city_snapshots  # noqa: E402


class ReportSnapshotTests(unittest.TestCase):
    def test_loads_snapshot_from_shard_directory(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "shard5"))
            with open(os.path.join(root, "shard5", "xian.json"), "w", encoding="utf-8") as f:
                json.dump({"source": "fresh"}, f)

            snapshots = _load_city_snapshots(root, ["xian"])

            self.assertEqual(snapshots["xian"]["source"], "fresh")

    def test_prefers_deeper_fresh_snapshot_over_stale_root_file(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "shard5"))
            for path, source in (
                (os.path.join(root, "xian.json"), "stale"),
                (os.path.join(root, "shard5", "xian.json"), "fresh"),
            ):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"source": source}, f)

            snapshots = _load_city_snapshots(root, ["xian"])

            self.assertEqual(snapshots["xian"]["source"], "fresh")

    def test_reports_missing_city_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(FileNotFoundError, "xian"):
                _load_city_snapshots(root, ["xian"])


if __name__ == "__main__":
    unittest.main()
