"""Checks for experiment 026."""
import json
import random
import subprocess
import sys
import unittest
from pathlib import Path

from evaluate import billed_f, case_result, samples

HERE = Path(__file__).resolve().parent


class RoundingTest(unittest.TestCase):
    def test_formula(self):
        self.assertEqual(billed_f(200, 5120, 0), 5120)
        self.assertEqual(billed_f(5121, 5120, 0), 10240)
        self.assertEqual(billed_f(20, 1, 60), 60)
        self.assertEqual(billed_f(0, 1, 60), 0)

    def test_constant_size_has_no_mean_error(self):
        r = case_result("iot_message", 3072, 0.0, 1)
        self.assertEqual(r["mean_based_error"], 0)
        self.assertAlmostEqual(r["waste_ratio"], 0.4, places=4)

    def test_lognormal_mean(self):
        xs = samples(1000, 0.5, random.Random(7), 50_000)
        self.assertAlmostEqual(sum(xs) / len(xs), 1000, delta=10)

    def test_near_boundary_underestimates(self):
        r = case_result("iot_message", 4915, 0.5, 3)
        self.assertLess(r["mean_based_error"], -0.2)

    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "evaluate.py")], capture_output=True,
                             check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), json.loads((HERE / "result.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
