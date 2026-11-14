"""Checks for experiment 033."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from evaluate import calls, classify, totals

HERE = Path(__file__).resolve().parent


class DefinitionTest(unittest.TestCase):
    def test_parts_add_up(self):
        for mode in ("fixed_prefix", "automatic", "none"):
            t = totals(calls(mode=mode))
            self.assertEqual(t["uncached"] + t["read"] + t["write"], t["inclusive_input"])

    def test_same_traffic_across_modes(self):
        self.assertEqual(totals(calls(mode="none"))["inclusive_input"], totals(calls(mode="fixed_prefix"))["inclusive_input"])

    def test_classify(self):
        self.assertEqual(classify(1000, 1000, 500, 100), "exclusive")
        self.assertEqual(classify(1600, 1000, 500, 100), "inclusive")
        self.assertEqual(classify(1000, 1000, 1, 1), "indistinguishable")
        self.assertEqual(classify(1300, 1000, 500, 100), "neither")

    def test_deterministic(self):
        self.assertEqual(calls(), calls())

    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "evaluate.py")], capture_output=True,
                             check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), json.loads((HERE / "result.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
