"""Checks for the GPU idle-cost calculation."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from calculate import load_rates, month

HERE = Path(__file__).resolve().parent


class MonthTest(unittest.TestCase):
    rates = load_rates()

    def test_study_note_numbers(self):
        r = month("gpu_notebook_always_on", 16, 20, 0, 50, "g4dn", self.rates)
        self.assertAlmostEqual(r["compute_usd"], 652.32, places=2)
        self.assertAlmostEqual(r["storage_usd"], 3.192, places=3)

    def test_training_storage_is_prorated(self):
        r = month("cpu_notebook_scheduled_plus_training_jobs", 72, 0, 0, 100, "g4dn", self.rates)
        self.assertAlmostEqual(r["storage_usd"], 100 * 0.1596 * 72 / 720, places=4)

    def test_residual_is_storage_only(self):
        r = month("gpu_notebook_scheduled", 0, 50, 20, 50, "g4dn", self.rates)
        self.assertAlmostEqual(r["residual_after_stop_usd"], 50 * 0.1596 + 20 * 0.025, places=4)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            month("gpu_notebook_scheduled", 200, 20, 0, 0, "g4dn", self.rates)
        with self.assertRaises(ValueError):
            month("unknown", 1, 20, 0, 0, "g4dn", self.rates)

    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "calculate.py")], capture_output=True,
                             text=True, check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), json.loads((HERE / "result.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
