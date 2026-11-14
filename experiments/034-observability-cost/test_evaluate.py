"""Checks for experiment 034."""
import json
import subprocess
import sys
import unittest
from decimal import Decimal as D
from pathlib import Path

from evaluate import PriceBook, metric_cost, retention

HERE = Path(__file__).resolve().parent
PB = PriceBook()


class ObservabilityTest(unittest.TestCase):
    def test_metric_tiers(self):
        n, c = metric_cost(PB, {"metric_hours_share": [(20000, 1)]})
        self.assertEqual(n, 20000)
        self.assertEqual(c, D(10000) * D("0.3") + D(10000) * D("0.1"))

    def test_prorated_by_hours(self):
        _, full = metric_cost(PB, {"metric_hours_share": [(240, 1)]})
        _, part = metric_cost(PB, {"metric_hours_share": [(240, D(1) / D(24))]})
        self.assertEqual(part * 24, full)

    def test_retention_crossover(self):
        rows, cross = retention(PB, 20)
        # storage(n) = 20 n x 0.0314 > 20 x 0.76  <=>  n > 24.2
        self.assertEqual(cross, 25)
        self.assertEqual(rows[0]["storage_usd_infinite"], rows[0]["storage_usd_30d"])

    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "evaluate.py")], capture_output=True,
                             check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), json.loads((HERE / "result.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
