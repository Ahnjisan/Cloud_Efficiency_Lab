"""Rule semantics, event scoring and reproducibility for the spike evaluation."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from evaluate import WARMUP, alert, history, make_series, score

HERE = Path(__file__).resolve().parent


def series_from(cost, events=()):
    labels = [None] * len(cost)
    for i, e in enumerate(events):
        for d in range(e["start"], e["start"] + e["length"]):
            labels[d] = (e["type"], i)
    return {"cost": cost, "labels": labels, "events": list(events)}


class RuleTest(unittest.TestCase):
    def test_history_same_weekday(self):
        cost = list(range(30))
        self.assertEqual(history(cost, 28, set(), 4, same_weekday=True), [21, 14, 7, 0])
        self.assertEqual(history(cost, 5, {4}, 2), [3, 2])

    def test_constant_series_needs_floor(self):
        cost = [10.0] * 40
        cost.append(10.5)   # +5%: below the 10% floor even though MAD is zero
        self.assertFalse(alert("R2_median_mad28", 3.0, cost, 40, set()))
        cost[40] = 12.0     # +20%
        self.assertTrue(alert("R2_median_mad28", 3.0, cost, 40, set()))

    def test_weekday_rule_ignores_weekend_dip(self):
        week = [10, 10, 10, 10, 10, 7, 7]
        cost = week * 6
        self.assertFalse(alert("R3_weekday_median4", 0.3, cost, 35, set()))  # Monday after weekend
        cost[36] = 20
        self.assertTrue(alert("R3_weekday_median4", 0.3, cost, 36, set()))


class ScoringTest(unittest.TestCase):
    def test_event_level_recall_and_delay(self):
        cost = [10.0] * (WARMUP + 20)
        for d in (WARMUP + 5, WARMUP + 6, WARMUP + 7):
            cost[d] = 10.0 if d == WARMUP + 5 else 40.0
        s = series_from(cost, [{"type": "spike", "start": WARMUP + 5, "length": 3}])
        r = score(s, "R1_mean_sd14", 3.0, False)
        self.assertEqual(r["spike"], [1, 1])
        self.assertEqual(r["delays"], [1])
        self.assertEqual(r["fp"], 0)

    def test_excluding_alerts_runs_away_after_level_shift(self):
        cost = [10.0] * WARMUP + [20.0] * 40   # permanent legitimate level shift
        s = series_from(cost)
        kept = score(s, "R2_median_mad28", 3.0, exclude_alerts=False)["fp"]
        excluded = score(s, "R2_median_mad28", 3.0, exclude_alerts=True)["fp"]
        self.assertLess(kept, 20)
        self.assertEqual(excluded, 40)

    def test_series_are_seeded(self):
        self.assertEqual(make_series(3), make_series(3))
        self.assertNotEqual(make_series(3)["cost"], make_series(4)["cost"])


class ReproductionTest(unittest.TestCase):
    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "evaluate.py")], capture_output=True,
                             text=True, check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), json.loads((HERE / "result.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
