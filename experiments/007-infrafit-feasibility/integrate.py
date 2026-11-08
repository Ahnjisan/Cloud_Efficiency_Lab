"""Join synthetic fixtures with reproducible results from 003, 004 and 006."""
import json
from copy import deepcopy
from decimal import Decimal
from math import isfinite
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
COST = "003-aws-cost-simulation"
PLAN = "004-terraform-evidence"
KUBE = "006-kubernetes-resource-efficiency"
METRICS = ("cpu_m", "memory_mib", "io_mib_s", "p95_ms", "p99_ms", "throughput_rps", "error_pct")

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def result(folder):
    return read(HERE.parent / folder / "result.json")

def valid_metric(key, value):
    return (
        type(value) in (int, float) and value >= 0
        and (type(value) is int or isfinite(value))
        and (key != "error_pct" or value <= 100)
    )

def analyze(case, fixture, cost, plans, nodes, total):
    plan = plans[case["resource"]]
    base_pod, candidate_pod = (nodes["pods"][name] for name in ("baseline", "candidate"))
    comparison = cost["scenarios"]["E-quality-unknown"]
    before_lines, after_lines = (comparison[key] for key in ("before_lines", "after_lines"))
    metrics = case["metrics"]
    missing = [key for key in METRICS if metrics.get(key) is None]
    invalid = [key for key in METRICS if metrics.get(key) is not None and not valid_metric(key, metrics[key])]
    if plan["status"] != "extracted":
        missing.extend(
            f"terraform.{side}.{key}"
            for side in ("before", "after")
            for key in plan.get(side, {}).get("unavailable", {})
        )
        if not any(key.startswith("terraform.") for key in missing):
            missing.append("terraform.supported_change")

    cost_reference = COST + "/result.json"
    if case["cost"] == "node":
        cost_reference = KUBE + "/result.json"
        before_lines, after_lines = (
            [{"id": "nodes", "usd": pod["scenarios"]["large"]["estimated_usd_720h"]}]
            for pod in (base_pod, candidate_pod)
        )
    elif case["cost"] == "duplicate":
        # Sources differ, but both rows refer to the same underlying charge.
        after_lines = [
            *after_lines,
            {**after_lines[1], "source": "second-synthetic-export"},
        ]

    reasons = []
    if case["cost"] != "node":
        basis = comparison.get("cost_basis", {})
        if basis.get("resource_id") != case["resource"] or any(
            not basis.get(side) or basis[side] != plan.get(side, {}).get("values")
            for side in ("before", "after")
        ):
            missing.append("cost.matching_configuration")
            reasons.append("no price evidence for this Terraform address and before/after configuration")

    before, after = None, None
    if "cost.matching_configuration" not in missing:
        before = total(before_lines)
        try:
            if not any(key.startswith("terraform.") for key in missing):
                after = total(after_lines)
        except ValueError as error:
            if str(error) != "duplicate cost line":
                raise
            missing.append("cost.unique_charge_ids")
            reasons.append("duplicate charge key; cost total withheld")

    goal = fixture["quality"]
    if all(valid_metric(key, metrics.get(key)) for key in ("p99_ms", "error_pct", "throughput_rps")):
        quality = (
            metrics["p99_ms"] <= goal["p99_ms"] and metrics["error_pct"] <= goal["error_pct"]
            and metrics["throughput_rps"] >= goal["min_rps"]
        )
    else:
        quality = None
    if quality is False:
        decision = "retain"
        reasons.append("candidate violates synthetic quality constraints")
    elif missing or invalid or quality is None or after is None:
        decision = "hold"
        reasons.append("required evidence is missing or inconsistent")
    elif after < before:
        decision = "candidate"
        reasons.append("lower modeled cost with synthetic quality gates met")
    else:
        decision = "retain"
        reasons.append("no modeled cost reduction")

    return {
        "experiment_id": "007", "scenario": case["id"],
        "environment_id": fixture["environment_id"], "workload_id": fixture["workload_id"],
        "resource_id": case["resource"], "time_range": fixture["time_range"],
        "measured_or_synthetic": "synthetic",
        "sources": {
            "terraform": PLAN + "/result.json", "cost": cost_reference,
            "kubernetes": KUBE + "/result.json", "container_and_quality": "cases.json",
        },
        "node_model": {
            "node": "large", "capacity": nodes["nodes"][1]["capacity"],
            "allocatable": nodes["nodes"][1]["allocatable"], "replicas": nodes["replicas"],
        } if case["cost"] == "node" else None,
        "current": {"terraform": plan.get("before"), "request_limit": [base_pod["request"], base_pod["limit"]], "metrics": fixture["baseline_metrics"]},
        "candidate": {"terraform": plan.get("after"), "request_limit": [candidate_pod["request"], candidate_pod["limit"]], "metrics": metrics},
        "cloud_price_reference": "synthetic USD, 720-hour model",
        "estimated_cost": {
            "before": str(before) if before is not None else None,
            "after": str(after) if after is not None else None,
            "difference": str(before - after) if before is not None and after is not None else None,
        },
        "quality_pass": quality, "missing_fields": missing, "invalid_fields": invalid, "decision": decision,
        "evidence": reasons,
        "next_check": "join same-scope measured resource and workload evidence; reconcile charge IDs",
    }

def main():
    fixture = read(HERE / "cases.json")
    cost, plan, nodes = map(result, (COST, PLAN, KUBE))
    plans = {row["address"]: row for row in plan["rows"]}
    total = run_path(str(HERE.parent / COST / "simulate.py"))["total"]
    rows = [analyze(case, fixture, cost, plans, nodes, total) for case in fixture["cases"]]
    assert [row["decision"] for row in rows] == [case["expected"] for case in fixture["cases"]]
    assert Decimal(rows[0]["estimated_cost"]["difference"]) == Decimal("72")
    assert rows[1]["quality_pass"] is False
    assert set(rows[2]["missing_fields"]) == {"memory_mib", "io_mib_s"}
    assert Decimal(rows[3]["estimated_cost"]["difference"]) == 0
    assert "terraform.after.size" in rows[4]["missing_fields"]
    assert "cost.matching_configuration" in rows[4]["missing_fields"] and rows[4]["estimated_cost"]["before"] is None
    assert "cost.unique_charge_ids" in rows[5]["missing_fields"]
    assert rows[4]["estimated_cost"]["after"] is rows[5]["estimated_cost"]["after"] is None
    no_p99 = {**fixture["cases"][0], "metrics": {**fixture["cases"][0]["metrics"], "p99_ms": None}}
    assert analyze(no_p99, fixture, cost, plans, nodes, total)["decision"] == "hold"
    case = fixture["cases"][0]
    for key, value in (("p99_ms", -1), ("throughput_rps", float("inf")), ("error_pct", 101)):
        invalid = {**case, "metrics": {**case["metrics"], key: value}}
        row = analyze(invalid, fixture, cost, plans, nodes, total)
        assert row["decision"] == "hold" and row["invalid_fields"] == [key]
        assert row["quality_pass"] is None
    for side in ("before", "after"):
        unpriced = deepcopy(plans)
        unpriced[case["resource"]][side]["values"]["instance_type"] = "model.unpriced-review"
        row = analyze(case, fixture, cost, unpriced, nodes, total)
        assert row["decision"] == "hold" and row["estimated_cost"]["after"] is None
        assert "cost.matching_configuration" in row["missing_fields"]
    other_address = "aws_instance.other"
    other_plans = {**plans, other_address: {**plans[case["resource"]], "address": other_address}}
    row = analyze({**case, "resource": other_address}, fixture, cost, other_plans, nodes, total)
    assert row["decision"] == "hold" and "cost.matching_configuration" in row["missing_fields"]
    print(json.dumps(rows, indent=2))

if __name__ == "__main__":
    main()
