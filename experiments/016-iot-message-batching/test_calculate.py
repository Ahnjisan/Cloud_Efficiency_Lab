"""Boundary and regression checks for the IoT batching calculation."""
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

from calculate import load_rates, scenario, tiered_cost, units_per_message

HERE = Path(__file__).resolve().parent


class UnitsTest(unittest.TestCase):
    def test_5kb_increments(self):
        self.assertEqual(units_per_message(5120, 1, 5120)[0], 1)
        self.assertEqual(units_per_message(5121, 1, 5120)[0], 2)
        self.assertEqual(units_per_message(8 * 1024, 1, 5120)[0], 2)

    def test_byte_definition_changes_boundary(self):
        self.assertEqual(units_per_message(200, 25, 5000, overhead_per_record=1)[0], 2)
        self.assertEqual(units_per_message(200, 25, 5120, overhead_per_record=1)[0], 1)

    def test_invalid_inputs(self):
        for args in ((0, 1, 5120), (200, 0, 5120), (200, 1, 4096), (4000, 50, 5120)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                units_per_message(*args)


class CostTest(unittest.TestCase):
    rates = load_rates()

    def test_tier_crossing(self):
        tiers = self.rates["message_tiers"]
        cost = tiered_cost(1_200_000_000, tiers)
        self.assertAlmostEqual(cost, 1_000_000_000 * 0.0000012 + 200_000_000 * 0.00000096, places=6)

    def test_study_note_numbers(self):
        row = scenario(100, 10, 200, 1, 5120, rates=self.rates)
        self.assertEqual(row["metered_messages"], 25_920_000)
        self.assertAlmostEqual(row["messaging_usd"], 31.104, places=3)
        batched = scenario(100, 10, 200, 20, 5120, rates=self.rates)
        self.assertEqual(batched["metered_messages"], 1_296_000)
        self.assertEqual(batched["max_added_latency_s"], 190)

    def test_basic_ingest_removes_only_messaging(self):
        a = scenario(100, 10, 200, 20, 5120, rates=self.rates)
        b = scenario(100, 10, 200, 20, 5120, basic_ingest=True, rates=self.rates)
        self.assertEqual(b["messaging_usd"], 0)
        for key in ("rules_usd", "actions_usd", "connection_usd"):
            self.assertEqual(a[key], b[key])

    def test_minimum_one_action_per_rule(self):
        zero = scenario(10, 60, 200, 1, 5120, actions=0, rates=self.rates)
        one = scenario(10, 60, 200, 1, 5120, actions=1, rates=self.rates)
        self.assertEqual(zero["actions_usd"], one["actions_usd"])


class ReproductionTest(unittest.TestCase):
    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "calculate.py")],
                             capture_output=True, text=True, check=True, encoding="utf-8").stdout
        stored = (HERE / "result.json").read_text(encoding="utf-8")
        self.assertEqual(json.loads(out), json.loads(stored))


if __name__ == "__main__":
    unittest.main()
