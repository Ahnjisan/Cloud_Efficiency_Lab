"""Synthetic-only checks for experiment 024 (real billing data stays outside the repository)."""
import json
import unittest
from pathlib import Path

from evaluate import BASE, run, thresholds_for

HERE = Path(__file__).resolve().parent


class EvaluateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run()

    def test_v0_is_pinned_to_the_pre_024_rule(self):
        cost = thresholds_for("V0")["cost"]
        self.assertEqual(cost["excluded_services"]["value"], [])
        self.assertEqual(cost["min_abs_increase_usd"]["value"], 0.0)
        self.assertFalse(cost["calendar_allowance"]["value"])
        self.assertTrue(BASE["cost"]["calendar_allowance"]["value"])  # current default is V4

    def test_hypotheses_on_synthetic_data(self):
        self.assertTrue(self.result["hypotheses"]["H2_V4_keeps_big_spike_performance"]["result"])
        self.assertTrue(self.result["hypotheses"]["H3_V0_small_spike_recall_below_50pct"]["result"])

    def test_synthetic_part_of_result_json_is_reproducible(self):
        stored = json.loads((HERE / "result.json").read_text(encoding="utf-8"))
        for key in ("design", "synthetic_big", "synthetic_small"):
            self.assertEqual(json.loads(json.dumps(self.result[key])), stored[key])


if __name__ == "__main__":
    unittest.main()
