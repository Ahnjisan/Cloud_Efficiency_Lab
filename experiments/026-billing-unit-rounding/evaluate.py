"""Billing-unit rounding and minimum charges: general formula vs mean-based estimate.

billed(x) = max(min, ceil(x / u) * u). For a size/duration distribution we compare
  - distribution-based billed units: mean of billed(x_i) / u over samples
  - mean-based estimate: billed(mean) / u  (what a spreadsheet using averages gives)
Samples are lognormal with a given mean and coefficient of variation (CV), seeded.
"""
from decimal import Decimal
from pathlib import Path
import json
import math
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scenarios"))
from pricebook import PriceBook, emit, load_scenario, money  # noqa: E402
from service_pack import UNITS  # noqa: E402

SEED = 26
N = 200_000
CVS = (0.0, 0.5, 1.0)
CASES = [
    # (unit kind, label, mean in the unit's measure)
    ("iot_message", "IoT 메시지 200 B", 200),
    ("iot_message", "IoT 메시지 3 KB", 3072),
    ("iot_message", "IoT 메시지 4.8 KB", 4915),
    ("iot_message", "IoT 메시지 6 KB", 6144),
    ("websocket_message", "WebSocket 4 KB", 4096),
    ("websocket_message", "WebSocket 30 KB", 30720),
    ("guardrails_text_unit", "Guardrails 응답 800자", 800),
    ("guardrails_text_unit", "Guardrails 응답 1,500자", 1500),
    ("fargate_linux_seconds", "Fargate 작업 20초", 20),
    ("fargate_linux_seconds", "Fargate 작업 45초", 45),
    ("fargate_linux_seconds", "Fargate 작업 300초", 300),
    ("athena_scan", "Athena 질의 2 MB 스캔", 2 * 1048576),
    ("athena_scan", "Athena 질의 50 MB 스캔", 50 * 1048576),
]


def samples(mean, cv, rng, n=N):
    if cv == 0:
        return [float(mean)] * n
    s2 = math.log(1 + cv * cv)
    mu = math.log(mean) - s2 / 2
    return [rng.lognormvariate(mu, math.sqrt(s2)) for _ in range(n)]


def billed_f(x, unit, minimum):
    return max(minimum, math.ceil(x / unit) * unit) if x > 0 else 0


def case_result(kind, mean, cv, seed):
    u = UNITS[kind]
    unit, minimum = float(u["unit"]), float(u["minimum"])
    xs = samples(mean, cv, random.Random(seed))
    billed_sum = sum(billed_f(x, unit, minimum) for x in xs)
    used_sum = sum(xs)
    dist_units = billed_sum / unit / len(xs)
    mean_units = billed_f(sum(xs) / len(xs), unit, minimum) / unit
    return {"cv": cv, "billed_units_per_item": round(dist_units, 4),
            "mean_based_units_per_item": round(mean_units, 4),
            "mean_based_error": round(mean_units / dist_units - 1, 4),
            "waste_ratio": round(1 - used_sum / billed_sum, 4)}


def scenario_iot(pb):
    """Scenario 1: bytes-based estimate vs per-message metering for IoT Core."""
    s = load_scenario("iot-pipeline-agent")
    d = s["devices"]
    readings = d["count"] * (s["period"]["days"] * 86400 // d["interval_s"])
    out = {}
    for per_msg in (1, 20, 26):
        msgs = readings // per_msg
        size = d["reading_bytes"] * per_msg
        billed_msgs = msgs * math.ceil(size / 5120)
        naive_msgs = math.ceil(readings * d["reading_bytes"] / 5120)
        out[f"{per_msg}_readings_per_message"] = {
            "message_bytes": size, "billed_messages": billed_msgs, "bytes_based_estimate": naive_msgs,
            "underestimate_factor": round(billed_msgs / naive_msgs, 3),
            "billed_usd": money(pb.tiered("AWSIoT", "APN2-Messages", billed_msgs)),
            "bytes_based_usd": money(pb.tiered("AWSIoT", "APN2-Messages", naive_msgs))}
    return out


def evaluate():
    pb = PriceBook()
    rows = []
    for i, (kind, label, mean) in enumerate(CASES):
        rows.append({"case": label, "kind": kind, "unit": str(UNITS[kind]["unit"]), "minimum": str(UNITS[kind]["minimum"]),
                     "mean": mean, "by_cv": [case_result(kind, mean, cv, SEED + i) for cv in CVS]})
    cv_rows = [(r, c) for r in rows for c in r["by_cv"] if c["cv"] >= 0.5]
    under10 = [r["case"] + f" cv={c['cv']}" for r, c in cv_rows if c["mean_based_error"] <= -0.10]
    small = [(r, c) for r in rows for c in r["by_cv"]
             if r["mean"] < 0.5 * float(UNITS[r["kind"]]["unit"]) and UNITS[r["kind"]]["minimum"] <= UNITS[r["kind"]]["unit"]]
    h2_fail = [r["case"] + f" cv={c['cv']}" for r, c in small if c["waste_ratio"] <= 0.5]
    return {
        "snapshot": pb.data["retrieved"], "seed": SEED, "samples_per_case": N,
        "hypotheses": {
            "H1_mean_based_underestimates_ge_10pct_in_half_of_cv_cases": {
                "result": len(under10) >= len(cv_rows) / 2, "cases_ge_10pct": len(under10),
                "cases_total": len(cv_rows), "which": under10},
            "H2_waste_gt_50pct_when_mean_lt_half_unit": {
                "result": not h2_fail, "cases_checked": len(small), "exceptions": h2_fail},
        },
        "cases": rows,
        "scenario_iot_messages": scenario_iot(pb),
        "rates_used": pb.used,
    }


if __name__ == "__main__":
    emit(evaluate())
