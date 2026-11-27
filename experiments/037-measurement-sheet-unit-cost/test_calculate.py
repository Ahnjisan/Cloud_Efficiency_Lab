"""Checks for experiment 037."""
import json
import subprocess
import sys
import unittest
from decimal import Decimal as D
from pathlib import Path

from calculate import per_sheet
from rates import Rates

HERE = Path(__file__).resolve().parent
R = Rates()


class UnitCostTest(unittest.TestCase):
    def test_manual_rates(self):
        self.assertEqual(R.textract["tables"], D("0.015"))
        self.assertEqual(R.textract["tables_forms"], R.textract["tables"] + D("0.05"))
        self.assertEqual(R.sqs, D("0.0000004"))

    def test_bedrock_call(self):
        self.assertEqual(R.bedrock_call("Claude Haiku 4.5", 3000, 600), D("0.006"))
        self.assertEqual(R.bedrock_call("Claude Sonnet 4.5", 3000, 600), D("0.018"))

    def test_csv_only_has_no_textract(self):
        p = per_sheet(R, "medium", "tables", "Claude Haiku 4.5", "medium", D(0))
        self.assertEqual(p["textract"], 0)

    def test_photo_pages(self):
        p = per_sheet(R, "medium", "tables", "Claude Haiku 4.5", "medium", D(1))
        self.assertEqual(p["textract"], D("1.3") * D("0.015"))

    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "calculate.py")], capture_output=True,
                             check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), json.loads((HERE / "result.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
