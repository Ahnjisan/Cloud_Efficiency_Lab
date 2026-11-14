"""Checks for experiment 028."""
import json
import subprocess
import sys
import unittest
from decimal import Decimal as D
from pathlib import Path

from evaluate import PriceBook, break_even_gb, rates, service_costs

HERE = Path(__file__).resolve().parent
R = rates(PriceBook())


class BreakEvenTest(unittest.TestCase):
    def test_two_az_one_endpoint(self):
        self.assertEqual(break_even_gb(R, 1, 2).quantize(D("0.1")), D("387.3"))

    def test_costs_equal_at_break_even(self):
        gb = break_even_gb(R, 2, 3)
        c = service_costs(R, gb, 2, 3, False)
        self.assertAlmostEqual(float(c["nat"]), float(c["interface_endpoint"]), places=6)

    def test_gateway_is_free(self):
        self.assertEqual(service_costs(R, 1000, 1, 2, True)["gateway_endpoint"], 0)

    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "evaluate.py")], capture_output=True,
                             check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), json.loads((HERE / "result.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
