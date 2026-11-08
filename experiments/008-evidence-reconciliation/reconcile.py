"""Reconcile independent synthetic billing, change, and peak evidence."""
from collections import Counter, defaultdict
from decimal import Decimal
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def reconcile(billing, changes, peaks, as_of, window):
    usage = defaultdict(dict)
    conflicts = set()
    unresolved = []
    for row in billing:
        if row["arrived"] > as_of or row["window"] != window:
            continue
        key = row["line_id"]
        previous = usage[key].get("row")
        if previous:
            fields = ("resource", "amount")
            if any(previous[field] != row[field] for field in fields):
                conflicts.add(key)
                usage[key]["resources"].add(row["resource"])
        else:
            usage[key] = {"row": row, "resources": {row["resource"]}}
    totals = defaultdict(Decimal)
    blocked = set()
    for key, entry in usage.items():
        resource = entry["row"]["resource"]
        if key in conflicts or not resource:
            blocked.update(entry["resources"] - {None})
            unresolved.append(key)
        else:
            totals[resource] += Decimal(entry["row"]["amount"])

    results = {}
    addresses = Counter(change["address"] for change in changes if change["window"] == window)
    for change in changes:
        if change["window"] != window:
            continue
        resource = change["resource"]
        config = change.get("candidate_config")
        baseline = totals.get(resource)
        samples = [row for row in peaks if row["resource"] == resource
                   and row.get("config") == config
                   and row["window"] == window and row["arrived"] <= as_of]
        reason = None
        if addresses[change["address"]] != 1:
            reason = "change-address-ambiguous"
        elif resource in blocked:
            reason = "billing-conflict"
        elif baseline is None:
            reason = "billing-unmatched"
        elif not isinstance(config, str) or not config.strip():
            reason = "candidate-config-missing"
        elif len(samples) != 1:
            reason = "peak-unmatched-or-ambiguous"
        else:
            p99 = samples[0].get("p99_ms")
            if type(p99) not in (int, float) or not 0 <= p99 < math.inf:
                reason = "invalid-peak-p99"
        if reason:
            results[change["address"]] = {"decision": "hold", "reason": reason}
            continue
        candidate = Decimal(change["candidate"])
        decision = "candidate" if candidate < baseline and p99 <= 200 else "keep"
        results[change["address"]] = {
            "decision": decision, "baseline": str(baseline), "candidate": str(candidate),
            "candidate_config": config, "p99_ms": p99,
        }
    return {"unresolved_billing_lines": sorted(unresolved), "decisions": results}


def main():
    billing, changes, peaks = (
        json.loads((HERE / name).read_text(encoding="utf-8"))
        for name in ("billing.json", "changes.json", "peaks.json")
    )
    initial = reconcile(billing, changes, peaks, 1, "peak-01")
    updated = reconcile(billing, changes, peaks, 2, "peak-01")
    assert updated == reconcile(billing + billing, changes, peaks, 2, "peak-01")
    duplicate = reconcile(billing, changes + changes[:1], peaks, 2, "peak-01")
    assert duplicate["decisions"]["aws_instance.orders"]["reason"] == "change-address-ambiguous"
    before, after = initial["decisions"], updated["decisions"]
    assert before["aws_instance.orders"]["reason"] == "peak-unmatched-or-ambiguous"
    assert after["aws_instance.orders"] == {
        "decision": "candidate", "baseline": "120.00", "candidate": "100.00",
        "candidate_config": "orders-small-v1", "p99_ms": 180,
    }
    assert after["aws_instance.worker"]["decision"] == "keep"
    assert after["aws_instance.conflict"]["reason"] == "billing-conflict"
    assert after["aws_instance.missing"]["reason"] == "billing-unmatched"
    assert after["aws_instance.stale"]["reason"] == "peak-unmatched-or-ambiguous"
    assert updated["unresolved_billing_lines"] == ["c", "missing"]
    alternate = {**changes[0], "address": "aws_instance.orders_alt", "candidate_config": "orders-alt-v1"}
    other_peaks = peaks + [{**peaks[0], "config": "orders-current-v1", "p99_ms": 90}]
    comparison = reconcile(billing, changes + [alternate], other_peaks, 2, "peak-01")["decisions"]
    assert comparison[alternate["address"]]["reason"] == "peak-unmatched-or-ambiguous"
    assert comparison[changes[0]["address"]] == after[changes[0]["address"]]
    other_peaks += [{**peaks[0], "config": "orders-alt-v1", "p99_ms": 250}]
    assert reconcile(billing, [alternate], other_peaks, 2, "peak-01")["decisions"][alternate["address"]]["decision"] == "keep"
    for invalid in (-5, math.nan, math.inf, "180", True, None):
        invalid_peak = {**peaks[0], "p99_ms": invalid}
        result = reconcile(billing, changes, [invalid_peak, *peaks[1:]], 2, "peak-01")
        assert result["decisions"][changes[0]["address"]]["reason"] == "invalid-peak-p99"
    print(json.dumps({"initial": initial, "reconciled": updated}, indent=2))


if __name__ == "__main__":
    main()
