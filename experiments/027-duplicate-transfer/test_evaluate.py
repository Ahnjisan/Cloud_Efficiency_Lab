"""Checks for experiment 027."""
import json
import subprocess
import sys
import unittest
from decimal import Decimal as D
from pathlib import Path

from evaluate import DESIGNS, load_scenario, volumes

HERE = Path(__file__).resolve().parent
S = load_scenario("iot-pipeline-agent")


class VolumeTest(unittest.TestCase):
    def test_raw_volume(self):
        v = volumes(S, DESIGNS["D0_duplicated"])
        self.assertEqual(v["readings"], 25_920_000)
        self.assertEqual(v["raw_gb"] * 1024 ** 3, D(25_920_000 * 200))

    def test_rule_counts(self):
        d0, d1 = volumes(S, DESIGNS["D0_duplicated"]), volumes(S, DESIGNS["D1_deduplicated"])
        self.assertEqual(d0["rules_triggered"], 2 * d1["rules_triggered"])
        self.assertEqual(d0["actions_executed"], d1["actions_executed"])

    def test_firehose_rounds_each_record_to_5kb(self):
        v = volumes(S, DESIGNS["D1_deduplicated"])
        self.assertAlmostEqual(float(v["firehose_billed_gb"] / v["raw_gb"]), 25.6, places=6)

    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "evaluate.py")], capture_output=True,
                             check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), json.loads((HERE / "result.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
