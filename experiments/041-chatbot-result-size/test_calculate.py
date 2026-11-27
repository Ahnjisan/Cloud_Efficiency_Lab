"""Checks for experiment 041."""
import json
import subprocess
import sys
import unittest
from decimal import Decimal as D
from pathlib import Path

from calculate import Rates, aggregate, call_inputs, question_cost, serialize, synth_rows, tokens

HERE = Path(__file__).resolve().parent
R = Rates()


class SizeTest(unittest.TestCase):
    def test_rows_deterministic(self):
        self.assertEqual(synth_rows(50), synth_rows(50))

    def test_aggregate_has_one_row_per_item(self):
        self.assertEqual(len(aggregate(synth_rows(1000))), 10)
        self.assertEqual(sum(a["count"] for a in aggregate(synth_rows(1000))), 1000)

    def test_tokens(self):
        self.assertEqual(tokens("abcdefg", "base"), 2)          # 7 / 3.5
        self.assertEqual(tokens("합격", "base"), 2)              # 2 x 1.0

    def test_csv_shorter_than_json(self):
        rows = synth_rows(10)
        cols = list(rows[0])
        self.assertLess(len(serialize(rows, cols, "csv")), len(serialize(rows, cols, "json")))

    def test_call_inputs(self):
        ins = call_inputs(1000, 4)
        self.assertEqual(ins, [2100, 2600, 3900, 4200])

    def test_cost_without_cache(self):
        c, mx, tot = question_cost(R, "Claude Haiku 4.5", 1000, 4, False)
        self.assertEqual(c, D(tot) / D(10 ** 6) + D(4 * 300) * 5 / D(10 ** 6))
        self.assertEqual(mx, 4200)

    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "calculate.py")], capture_output=True,
                             check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), json.loads((HERE / "result.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
