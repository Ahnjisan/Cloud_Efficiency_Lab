"""Synthetic checks for the real-data R-COST-1 summary (no real billing data in the repository)."""
from datetime import date, timedelta
import json
import unittest
from pathlib import Path

from check import build_series, pre_024, summarize

ROOT = Path(__file__).resolve().parents[2]
CURRENT = json.loads((ROOT / "infrafit" / "thresholds.json").read_text(encoding="utf-8"))
THRESHOLDS = pre_024(CURRENT)  # the rule 023 evaluated


def page(start, days, fee_per_month=None, tax_on_first=None):
    rows = []
    for i in range(days):
        d = start + timedelta(days=i)
        month_days = ((d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).day
        groups = []
        if fee_per_month is not None:
            groups.append({"Keys": ["Fixed Fee Service"],
                           "Metrics": {"NetUnblendedCost": {"Amount": f"{fee_per_month / month_days:.10f}"}}})
        if tax_on_first is not None and d.day == 1:
            groups.append({"Keys": ["Tax"], "Metrics": {"NetUnblendedCost": {"Amount": str(tax_on_first)}}})
        rows.append({"TimePeriod": {"Start": d.isoformat()}, "Estimated": False, "Groups": groups})
    return {"ResultsByTime": rows}


class CheckTest(unittest.TestCase):
    def test_february_proration_triggers_the_10pct_floor(self):
        series, est = build_series([page(date(2025, 10, 1), 200, fee_per_month=0.40)])
        out = summarize(series, est, THRESHOLDS)["series"]["Fixed Fee Service"]
        firsts = [a for a in out["alert_details"] if a["month_first_day"]]
        self.assertEqual(len(firsts), 1)                    # only 1 Feb starts an alert run
        self.assertEqual(firsts[0]["day_index"], (date(2026, 2, 1) - date(2025, 10, 1)).days)
        self.assertEqual(out["alerts"], 14)                 # until the 28-day median flips

    def test_monthly_tax_with_zero_median_alerts_every_month(self):
        series, est = build_series([page(date(2025, 10, 1), 200, fee_per_month=0.40, tax_on_first=0.04)])
        tax = summarize(series, est, THRESHOLDS)["series"]["Tax"]
        self.assertTrue(all(a["median_is_zero"] and a["month_first_day"] for a in tax["alert_details"]))
        self.assertEqual(tax["alerts"], 6)                  # Nov..Apr after 28 days of history

    def test_gap_is_rejected(self):
        p = page(date(2025, 10, 1), 40, fee_per_month=0.40)
        del p["ResultsByTime"][10]
        with self.assertRaises(ValueError):
            build_series([p])

    def test_summary_has_no_amounts_or_dates(self):
        series, est = build_series([page(date(2025, 10, 1), 120, fee_per_month=0.40, tax_on_first=0.04)])
        text = json.dumps(summarize(series, est, THRESHOLDS))
        self.assertNotIn("2025-", text)
        self.assertNotIn("2026-", text)
        self.assertNotIn("0.04", text)
        self.assertNotIn("_usd", text)


class CurrentRuleTest(unittest.TestCase):
    def test_024_defaults_remove_both_false_alarm_patterns(self):
        series, est = build_series([page(date(2025, 10, 1), 200, fee_per_month=0.40, tax_on_first=0.04)])
        out = summarize(series, est, CURRENT)["series"]
        self.assertEqual(out["Fixed Fee Service"]["alerts"], 0)
        self.assertEqual(out["Tax"]["hold"], "cost-service-excluded")


if __name__ == "__main__":
    unittest.main()
