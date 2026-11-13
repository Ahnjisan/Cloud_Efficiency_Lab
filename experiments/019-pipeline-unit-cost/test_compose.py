"""Composition checks for the pipeline unit-cost experiment."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from compose import QUERY_MIX, READINGS, athena_month, compose, firehose_billed_gb

HERE = Path(__file__).resolve().parent


class PartsTest(unittest.TestCase):
    def test_firehose_rounding(self):
        self.assertAlmostEqual(firehose_billed_gb(READINGS, 200), 123.596, places=3)
        self.assertAlmostEqual(firehose_billed_gb(READINGS // 20, 4000), 6.180, places=3)

    def test_athena_minimum(self):
        tiny = {q: 1 for q in QUERY_MIX}
        per_month = sum(QUERY_MIX.values()) * 30 * 10 / (1024 * 1024) * 5.0
        self.assertAlmostEqual(athena_month(tiny, 1, 5.0), per_month)
        self.assertEqual(athena_month(tiny, 0, 5.0), 0)

    def test_totals_add_up(self):
        result = compose()
        for config in result["configs"].values():
            for row in config["by_query_scale"].values():
                self.assertAlmostEqual(sum(row["components_usd"].values()), row["total_usd"], places=3)
                self.assertAlmostEqual(row["usd_per_1000_readings"], row["total_usd"] / READINGS * 1000, places=6)

    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "compose.py")], capture_output=True,
                             text=True, check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), json.loads((HERE / "result.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
