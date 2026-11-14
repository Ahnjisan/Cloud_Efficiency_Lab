"""Checks for experiment 036."""
import json
import subprocess
import sys
import unittest
from decimal import Decimal as D
from pathlib import Path

import model as m
from evaluate import PriceBook

HERE = Path(__file__).resolve().parent
PB = PriceBook()
RESULT = json.loads((HERE / "result.json").read_text(encoding="utf-8"))


class ModelTest(unittest.TestCase):
    def test_flags(self):
        self.assertEqual(m.flags(m.c("x", "s", 10, 4)), ["minimum_or_rounding_ge_50pct"])
        self.assertEqual(m.flags(m.c("x", "s", 10, 6)), [])
        self.assertEqual(m.flags(m.c("x", "s", 10, None, fixed=True)), ["usage_unknown", "always_on"])

    def test_iot_rounding_is_flagged(self):
        comp = m.iot_core(PB, 1000, 200)[0]
        self.assertIn("minimum_or_rounding_ge_50pct", m.flags(comp))

    def test_summary_total(self):
        comps = m.nat(PB, 1, 100) + m.logs(PB, 10)
        s = m.summarize(comps)
        self.assertEqual(D(s["total_usd"]), sum(x["billed"] for x in comps).quantize(D("0.01")))

    def test_019_reproduced(self):
        for cfg in RESULT["reproduce_019"].values():
            for row in cfg.values():
                self.assertEqual(row["model_usd_per_1000"], row["019_usd_per_1000"])

    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "evaluate.py")], capture_output=True,
                             check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), RESULT)


if __name__ == "__main__":
    unittest.main()
