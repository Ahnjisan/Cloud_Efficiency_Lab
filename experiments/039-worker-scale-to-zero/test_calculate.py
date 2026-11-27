"""Checks for experiment 039 (calculation; uses the stored measurement.json, no Docker)."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from calculate import DAY, MONTH_S, arrivals, forced_windows, measured_start, run, shared_nodes, union

HERE = Path(__file__).resolve().parent
MEAS = json.loads((HERE / "measurement.json").read_text(encoding="utf-8"))


class ModelTest(unittest.TestCase):
    def test_arrivals_weekdays_only(self):
        a = arrivals(1, 20)
        self.assertEqual(len(a), 22 * 20)
        self.assertTrue(all(int(t // DAY) % 7 < 5 for t, _ in a))

    def test_union(self):
        self.assertEqual(union([(0, 5), (3, 8), (10, 12)]), [[0, 8], [10, 12]])

    def test_w1_has_no_cold_sheets(self):
        r = run(1, 20, "W1", 30, 300, 100.0, 5.0)
        self.assertEqual(r["cold_lat"], [])
        self.assertEqual(r["windows"], [(0.0, MONTH_S)])

    def test_w2_first_sheet_waits_for_startup(self):
        r = run(1, 20, "W2", 30, 300, 100.0, 5.0)
        self.assertGreaterEqual(r["lat"][0], 100.0)       # first sheet of the month finds the pod off
        self.assertGreater(min(r["cold_lat"]), 0)         # later arrivals during start-up wait only the remainder

    def test_w3_windows(self):
        self.assertEqual(len(forced_windows("W3")), 22)

    def test_shared_nodes_unchanged(self):
        n = shared_nodes()
        self.assertEqual(n["nodes_with_worker"], n["nodes_without_worker"])

    def test_measurement_recorded_and_cleaned(self):
        self.assertIn(MEAS["status"], ("measured", "failed", "not_run"))
        if MEAS["status"] == "measured":
            self.assertEqual(len(MEAS["runs"]), 10)
            self.assertTrue(MEAS["cleanup"]["profile_removed"])
            self.assertTrue(MEAS["cleanup"]["containers_same"])
        self.assertIn("source", measured_start())

    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "calculate.py")], capture_output=True,
                             check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), json.loads((HERE / "result.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
