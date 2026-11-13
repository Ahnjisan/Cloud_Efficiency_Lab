"""IoT Core message batching: metered messages, monthly cost and added latency.

Deterministic calculation. Rates are read from the Seoul (ap-northeast-2) price
snapshot in references/. No AWS API is called.
"""
from itertools import product
from pathlib import Path
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "references" / "aws-price-list-apn2-2026-11-13.json"
MONTH_SECONDS = 30 * 24 * 3600
MONTH_MINUTES = MONTH_SECONDS // 60


def load_rates(path=SNAPSHOT):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))["offers"]["AWSIoT"]["rows"]

    def flat(usagetype):
        (row,) = [r for r in rows if r["usagetype"] == usagetype]
        return float(row["usd"])

    tiers = sorted(
        ((float(r["begin"]), math.inf if r["end"] == "Inf" else float(r["end"]), float(r["usd"]))
         for r in rows if r["usagetype"] == "APN2-Messages"),
    )
    return {
        "message_tiers": tiers,
        "connection_minute": flat("APN2-ConnectionMinutes"),
        "rule": flat("APN2-RulesTriggered"),
        "action": flat("APN2-ActionsExecuted"),
    }


def units_per_message(payload_bytes, batch, kb_bytes, overhead_per_record=0):
    """Metered 5 KB units for one published message carrying `batch` readings."""
    if payload_bytes <= 0 or batch < 1 or kb_bytes not in (5000, 5120):
        raise ValueError("invalid message shape")
    size = batch * (payload_bytes + overhead_per_record)
    limit = 128 * (1024 if kb_bytes == 5120 else 1000)
    if size > limit:
        raise ValueError(f"message of {size} B exceeds the 128 KB limit")
    return math.ceil(size / kb_bytes), size


def tiered_cost(count, tiers):
    cost, remaining = 0.0, count
    for begin, end, usd in tiers:
        span = min(remaining, end - begin)
        if span <= 0:
            break
        cost += span * usd
        remaining -= span
    return cost


def scenario(sensors, period_s, payload_bytes, batch, kb_bytes, overhead=0,
             rules=1, actions=1, basic_ingest=False, rates=None):
    rates = rates or load_rates()
    if MONTH_SECONDS % period_s:
        raise ValueError("period must divide the month evenly")
    readings_per_sensor = MONTH_SECONDS // period_s
    messages = sensors * math.ceil(readings_per_sensor / batch)
    units, size = units_per_message(payload_bytes, batch, kb_bytes, overhead)
    metered = messages * units
    messaging = 0.0 if basic_ingest else tiered_cost(metered, rates["message_tiers"])
    rules_cost = metered * rules * rates["rule"]
    actions_cost = metered * rules * max(actions, 1) * rates["action"]
    connection = sensors * MONTH_MINUTES * rates["connection_minute"]
    total = messaging + rules_cost + actions_cost + connection
    return {
        "sensors": sensors, "period_s": period_s, "payload_bytes": payload_bytes,
        "batch": batch, "kb_bytes": kb_bytes, "overhead_per_record": overhead,
        "basic_ingest": basic_ingest, "message_bytes": size,
        "readings": sensors * readings_per_sensor, "published_messages": messages,
        "units_per_message": units, "metered_messages": metered,
        "messaging_usd": round(messaging, 4), "rules_usd": round(rules_cost, 4),
        "actions_usd": round(actions_cost, 4), "connection_usd": round(connection, 4),
        "total_usd": round(total, 4),
        "usd_per_1000_readings": round(total / (sensors * readings_per_sensor) * 1000, 8),
        "max_added_latency_s": (batch - 1) * period_s,
    }


def main():
    rates = load_rates()
    grid = []
    for sensors, period, payload, batch, kb, overhead in product(
        (10, 100, 1000), (1, 10, 60), (100, 200, 1000, 4000),
        (1, 5, 10, 20, 25, 26, 50), (5000, 5120), (0, 1),
    ):
        try:
            grid.append(scenario(sensors, period, payload, batch, kb, overhead, rates=rates))
        except ValueError as error:
            grid.append({"sensors": sensors, "period_s": period, "payload_bytes": payload,
                         "batch": batch, "kb_bytes": kb, "overhead_per_record": overhead,
                         "invalid": str(error)})

    base = scenario(100, 10, 200, 1, 5120, rates=rates)
    batched = scenario(100, 10, 200, 20, 5120, rates=rates)
    ingest = scenario(100, 10, 200, 20, 5120, basic_ingest=True, rates=rates)
    variable = lambda r: r["messaging_usd"] + r["rules_usd"] + r["actions_usd"]
    h1_reduction = 1 - variable(batched) / variable(base)

    boundary = {
        f"{kb}B_def_overhead{ov}": {
            n: scenario(100, 10, 200, n, kb, ov, rates=rates)["units_per_message"] for n in (25, 26)
        }
        for kb in (5000, 5120) for ov in (0, 1)
    }
    large_payload = [scenario(100, 10, 4000, n, 5120, rates=rates) for n in (1, 5, 20)]
    large_reduction = 1 - variable(large_payload[1]) / variable(large_payload[0])

    hypotheses = {
        "H1_batch20_reduces_variable_cost_ge_90pct": {
            "result": h1_reduction >= 0.90, "reduction": round(h1_reduction, 4)},
        "H2_added_latency_equals_(N-1)*period": {
            "result": all(r.get("max_added_latency_s") == (r["batch"] - 1) * r["period_s"]
                          for r in grid if "invalid" not in r)},
        "H3_step_at_5KB_boundary": {
            "result": any(v[26] > v[25] for v in boundary.values()), "units": boundary},
    }
    print(json.dumps({
        "snapshot": str(SNAPSHOT.relative_to(ROOT)).replace("\\", "/"),
        "rates": {k: v if k != "message_tiers" else [[b, str(e), u] for b, e, u in v]
                  for k, v in rates.items()},
        "headline": {"individual": base, "batch20": batched, "batch20_basic_ingest": ingest},
        "large_payload_4000B": {"rows": large_payload,
                                "batch5_variable_reduction": round(large_reduction, 4)},
        "hypotheses": hypotheses,
        "grid_size": len(grid),
        "invalid_count": sum("invalid" in r for r in grid),
        "grid": grid,
    }, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
