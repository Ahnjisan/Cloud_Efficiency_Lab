"""Run InfraFit R-COST-1 on real daily Cost Explorer data and print an anonymized summary.

Input: one or more GetCostAndUsage response files (DAILY, GroupBy SERVICE,
NetUnblendedCost) kept OUTSIDE the repository. Output: per-series day counts,
alert counts and, for each alert, its relative day index, whether it falls on
the first or last day of a month, whether the day was Estimated, and the
ratio observed / baseline median. No amounts, dates or account identifiers
are printed.
"""
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "infrafit"))
from ops_rules import cost_series  # noqa: E402

METRIC = "NetUnblendedCost"


def build_series(pages):
    """Turn GetCostAndUsage pages into gap-free per-service daily series (+ a total)."""
    days, per_service, estimated = [], {}, {}
    for page in pages:
        for row in page["ResultsByTime"]:
            day = date.fromisoformat(row["TimePeriod"]["Start"])
            days.append(day)
            estimated[day] = bool(row.get("Estimated", False))
            for group in row.get("Groups", []):
                amount = Decimal(group["Metrics"][METRIC]["Amount"])
                per_service.setdefault(group["Keys"][0], {})[day] = amount
    days = sorted(set(days))
    if any(b - a != timedelta(days=1) for a, b in zip(days, days[1:])):
        raise ValueError("Cost Explorer pages leave a gap in the days")
    series = {}
    for name, values in sorted(per_service.items()):
        series[name] = [(d, values.get(d, Decimal(0))) for d in days]
    series["(total)"] = [(d, sum((v.get(d, Decimal(0)) for v in per_service.values()), Decimal(0))) for d in days]
    return series, estimated


def to_rule_input(name, points, estimated):
    return {"service": name, "metric": METRIC, "ResultsByTime": [
        {"TimePeriod": {"Start": d.isoformat()}, "Estimated": estimated[d],
         "Metrics": {METRIC: {"Amount": str(v)}}} for d, v in points]}


def summarize(series, estimated, thresholds):
    start = min(d for pts in series.values() for d, _ in pts)
    out = {}
    for name, points in series.items():
        queue, hold = cost_series(to_rule_input(name, points, estimated), thresholds)
        nonzero = sum(1 for _, v in points if v != 0)
        alerts = []
        for item in queue:
            d = date.fromisoformat(item["date"])
            median = Decimal(item["baseline_median_usd"])
            alerts.append({
                "day_index": (d - start).days,
                "month_first_day": d.day == 1,
                "month_last_day": (d + timedelta(days=1)).day == 1,
                "estimated": item["estimated"],
                "observed_to_median": None if median == 0 else round(float(Decimal(item["observed_usd"]) / median), 2),
                "median_is_zero": median == 0,
                "consecutive_alert_days": item["consecutive_alert_days"],
            })
        out[name] = {"days": len(points), "nonzero_days": nonzero, "hold": hold and hold["reason"],
                     "alerts": len(alerts), "alert_details": alerts}
    return {"series_days": len(next(iter(series.values()))),
            "estimated_days": sum(estimated.values()), "series": out}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("pages", nargs="+", type=Path, help="GetCostAndUsage JSON files (outside the repository)")
    parser.add_argument("--thresholds", type=Path, default=ROOT / "infrafit" / "thresholds.json")
    args = parser.parse_args(argv)
    pages = [json.loads(p.read_text(encoding="utf-8")) for p in args.pages]
    thresholds = json.loads(args.thresholds.read_text(encoding="utf-8"))
    series, estimated = build_series(pages)
    print(json.dumps(summarize(series, estimated, thresholds), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
