"""Compare R-COST-1 variants on real (023) and synthetic (021-style) daily cost series.

Variants (see README, decided before running):
  V0 current rule, V1 + Tax exclusion, V2 + 0.50 USD/day minimum increase,
  V3 + calendar allowance, V4 all three.
Synthetic sets: 021 test seeds 101-120 (spikes +50..300%) and seeds 201-220
with spikes +10..30%. Real data (optional, kept outside the repository) is
summarized without amounts or dates.
"""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import argparse
import importlib.util
import json
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "infrafit"))
from ops_rules import cost_series  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXP021 = _load("exp021", ROOT / "experiments" / "021-daily-cost-spike-detection" / "evaluate.py")
EXP023 = _load("exp023", ROOT / "experiments" / "023-real-cost-spike-check" / "check.py")
BASE = json.loads((ROOT / "infrafit" / "thresholds.json").read_text(encoding="utf-8"))
START = date(2025, 1, 1)
BIG_SEEDS = EXP021.TEST_SEEDS
SMALL_SEEDS = tuple(range(201, 221))
SMALL_RANGE = (0.1, 0.3)
FIXES = {
    "excluded_services": ["Tax"],
    "min_abs_increase_usd": 0.5,
    "calendar_allowance": True,
}
VARIANTS = {
    "V0": {}, "V1": {"excluded_services": FIXES["excluded_services"]},
    "V2": {"min_abs_increase_usd": FIXES["min_abs_increase_usd"]},
    "V3": {"calendar_allowance": FIXES["calendar_allowance"]}, "V4": dict(FIXES),
}


OFF = {"excluded_services": [], "min_abs_increase_usd": 0.0, "calendar_allowance": False}


def thresholds_for(variant):
    """V0 is pinned to the pre-024 rule even after the defaults change."""
    t = deepcopy(BASE)
    for key, val in {**OFF, **VARIANTS[variant]}.items():
        t["cost"][key] = {"value": val, "evidence": "임시값", "source": "experiment 024 variant"}
    return t


def as_rule_input(name, values, estimated=None):
    return {"service": name, "metric": "NetUnblendedCost", "ResultsByTime": [
        {"TimePeriod": {"Start": (START + timedelta(days=i)).isoformat()},
         "Estimated": bool(estimated and estimated[i]),
         "Metrics": {"NetUnblendedCost": {"Amount": f"{v:.6f}"}}} for i, v in enumerate(values)]}


def score_synthetic(seeds, variant, spike_range):
    t = thresholds_for(variant)
    fp = normal = 0
    found = {"spike": [0, 0], "growth": [0, 0]}
    delays = []
    for seed in seeds:
        s = EXP021.make_series(seed, spike_range)
        queue, hold = cost_series(as_rule_input("synthetic", s["cost"]), t)
        if hold:
            raise RuntimeError(hold)
        alerts = {(date.fromisoformat(q["date"]) - START).days for q in queue}
        alerts = {d for d in alerts if d >= EXP021.WARMUP}
        for d in range(EXP021.WARMUP, len(s["cost"])):
            if s["labels"][d] is None:
                normal += 1
                fp += d in alerts
        for e in s["events"]:
            days = range(e["start"], e["start"] + e["length"])
            hit = [d for d in days if d in alerts]
            found[e["type"]][1] += 1
            if hit:
                found[e["type"]][0] += 1
                if e["type"] == "spike":
                    delays.append(hit[0] - e["start"])
    return {"spike_recall": round(found["spike"][0] / found["spike"][1], 4), "spike_events": found["spike"][1],
            "growth_recall": round(found["growth"][0] / found["growth"][1], 4),
            "fp_per_30_normal_days": round(fp / normal * 30, 4),
            "mean_delay_days": round(statistics.fmean(delays), 3) if delays else None}


def score_real(pages, variant):
    t = thresholds_for(variant)
    series, estimated = EXP023.build_series(pages)
    excluded = set(VARIANTS[variant].get("excluded_services", []))
    services = {k: v for k, v in series.items() if k != "(total)"}
    days = [d for d, _ in next(iter(services.values()))]
    total = [(d, sum((dict(v)[d] for k, v in services.items() if k not in excluded), Decimal(0))) for d in days]
    out = {}
    for name, points in list(services.items()) + [("(total)", total)]:
        queue, hold = cost_series(EXP023.to_rule_input(name, points, estimated), t)
        out[name] = {"alerts": len(queue), "hold": hold and hold["reason"],
                     "alerts_starting_on_month_first_day": sum(
                         1 for q in queue if date.fromisoformat(q["date"]).day == 1)}
    per_service = sum(v["alerts"] for k, v in out.items() if k != "(total)")
    return {"per_service_alerts": per_service, "total_series_alerts": out["(total)"]["alerts"], "series": out}


def run(real_pages=None):
    result = {"design": {"variants": VARIANTS, "big_spike_seeds": [BIG_SEEDS[0], BIG_SEEDS[-1]],
                         "small_spike_seeds": [SMALL_SEEDS[0], SMALL_SEEDS[-1]], "small_spike_range": SMALL_RANGE,
                         "synthetic_start_date": START.isoformat()},
              "synthetic_big": {v: score_synthetic(BIG_SEEDS, v, (0.5, 3.0)) for v in VARIANTS},
              "synthetic_small": {v: score_synthetic(SMALL_SEEDS, v, SMALL_RANGE) for v in VARIANTS}}
    big, small = result["synthetic_big"], result["synthetic_small"]
    hyp = {
        "H2_V4_keeps_big_spike_performance": {
            "result": big["V4"]["spike_recall"] >= big["V0"]["spike_recall"] - 0.02
            and big["V4"]["fp_per_30_normal_days"] <= big["V0"]["fp_per_30_normal_days"],
            "V0": big["V0"], "V4": big["V4"]},
        "H3_V0_small_spike_recall_below_50pct": {"result": small["V0"]["spike_recall"] < 0.5,
                                                 "V0": small["V0"]["spike_recall"], "V4": small["V4"]["spike_recall"]},
    }
    if real_pages is not None:
        result["real"] = {v: score_real(real_pages, v) for v in VARIANTS}
        hyp["H1_V4_removes_real_false_alarms"] = {"result": result["real"]["V4"]["per_service_alerts"] == 0,
                                                  "V0": result["real"]["V0"]["per_service_alerts"],
                                                  "V4": result["real"]["V4"]["per_service_alerts"]}
        hyp["adopt_V4_as_default"] = hyp["H1_V4_removes_real_false_alarms"]["result"] and hyp["H2_V4_keeps_big_spike_performance"]["result"]
    result["hypotheses"] = hyp
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", nargs="*", type=Path, default=None,
                        help="023 GetCostAndUsage pages kept outside the repository")
    args = parser.parse_args(argv)
    pages = [json.loads(p.read_text(encoding="utf-8")) for p in args.real] if args.real else None
    print(json.dumps(run(pages), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
