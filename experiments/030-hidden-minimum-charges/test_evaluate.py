"""Checks for experiment 030."""
import json
import subprocess
import sys
import unittest
from decimal import Decimal as D
from pathlib import Path

from evaluate import share

HERE = Path(__file__).resolve().parent
RESULT = json.loads((HERE / "result.json").read_text(encoding="utf-8"))


class MinimumTest(unittest.TestCase):
    def test_share(self):
        self.assertEqual(share(D(1), D(2)), D("0.5"))
        self.assertEqual(share(D(0), D(0)), 0)

    def test_share_is_zero_above_floor(self):
        for curve in RESULT["curves"].values():
            for row in curve:
                if D(row["minimum_share"]) == 0:
                    continue
                self.assertGreater(D(row["minimum_share"]), 0)
        rows = RESULT["curves"]["elasticache_serverless_storage"]
        self.assertEqual(next(r for r in rows if r["data_gb"] == "2" and r["engine"] == "Redis")["minimum_share"], "0.0000")

    def test_fargate_minimum(self):
        row = next(r for r in RESULT["curves"]["fargate_task_minimum"] if r["task_seconds"] == 15)
        self.assertEqual(row["billed_seconds"], 60)

    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "evaluate.py")], capture_output=True,
                             check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), RESULT)


if __name__ == "__main__":
    unittest.main()
