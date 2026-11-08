"""Summarize saved Kubernetes rollback sequences without a running cluster."""
import argparse
import json
from pathlib import Path
from runpy import run_path

VALIDATE = run_path(str(Path(__file__).resolve().parents[1]
                        / "006-kubernetes-resource-efficiency/live_safety.py"))["validate_measurement"]


def summarize(log):
    rows = []
    grouped = {}
    for run in log["runs"]:
        if "phase" not in run:
            continue
        expected_cpu = {"baseline": 1000, "candidate": 500, "restored": 1000}[run["phase"]]
        if run["limit_m"] != expected_cpu:
            raise ValueError("reported CPU limit does not match the rollback phase")
        VALIDATE(run.copy(), expected_cpu, target_requests=300)
        metrics = run["k6"]["metrics"]
        dropped = metrics.get("dropped_iterations", {"count": 0})["count"]
        successes = metrics["successful_requests"]["count"]
        offered = metrics["http_reqs"]["count"] + dropped
        p99 = metrics["http_req_duration"]["p(99)"]
        errors = metrics["http_req_failed"]
        rate = errors.get("rate", errors.get("value"))
        quality = offered >= 300 and successes / offered >= .99 and rate <= .01 and p99 <= 200
        if quality != run["quality_pass"] or offered != run["offered"]:
            raise ValueError("stored quality verdict does not match raw metrics")
        row = {"repetition": run["repetition"], "phase": run["phase"], "cpu_m": run["limit_m"],
               "p99_ms": p99, "successes": successes, "offered": offered, "dropped": dropped,
               "error_rate": rate, "quality_pass": quality, "pod_uid": run["pod_uid"],
               "phase_to_observation_s": run["phase_to_observation_s"]}
        rows.append(row)
        grouped.setdefault(run["repetition"], []).append(row)
    completed = {repetition: group for repetition, group in grouped.items()
                 if [row["phase"] for row in group] == ["baseline", "candidate", "restored"]}
    requested = log["requested_repetitions"]
    if log["status"] == "pass" and (
        set(completed) != set(range(1, requested + 1)) or completed.keys() != grouped.keys()
    ):
        raise ValueError("PASS log does not contain exactly the requested rollback repetitions and phases")
    for group in completed.values():
        assert [row["cpu_m"] for row in group] == [1000, 500, 1000]
        assert len({row["pod_uid"] for row in group}) == 3
    outcomes = sum([row["quality_pass"] for row in group] == [True, False, True] for group in completed.values())
    return {"execution_status": log["status"], "cleanup_verified": log.get("cleanup_verified"),
            "requested_repetitions": requested,
            "completed_repetitions": len(completed), "observed_failure_and_recovery": outcomes, "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(json.loads(args.log.read_text(encoding="utf-8"))), indent=2))


if __name__ == "__main__":
    main()
