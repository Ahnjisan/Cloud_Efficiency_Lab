"""Checks for experiment 029."""
import json
import subprocess
import sys
import unittest
from decimal import Decimal as D
from pathlib import Path

from evaluate import H, PriceBook, components, load_scenario, month_cost

HERE = Path(__file__).resolve().parent
PB, S = PriceBook(), load_scenario("web-llm-chatbot")


class ScheduleTest(unittest.TestCase):
    def test_delete_only_items_ignore_schedule(self):
        items = components(PB, S, "classic")
        _, rows = month_cost(items, D(0))
        for r in rows:
            if r["kind"] in ("delete_only", "stays_billed"):
                self.assertNotEqual(r["usd"], "0.00")
            else:
                self.assertEqual(r["usd"], "0.00")

    def test_always_on_equals_schedule_at_730h(self):
        items = components(PB, S, "nextgen")
        self.assertEqual(month_cost(items, H)[0], month_cost(items, H, rds_hours=H)[0])

    def test_opensearch_minimum(self):
        items = components(PB, S, "classic")
        os_row = next(i for i in items if i["name"].startswith("OpenSearch"))
        self.assertEqual((os_row["hourly"] * H).quantize(D("0.01")), D("427.78"))

    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "evaluate.py")], capture_output=True,
                             check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), json.loads((HERE / "result.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
