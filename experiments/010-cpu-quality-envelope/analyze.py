"""Compare saved local measurements against illustrative quality gates."""
from collections import defaultdict
import argparse
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def quality_row(metrics):
    try:
        successes = metrics["successful_requests"]["count"]
        requests = metrics["http_reqs"]["count"]
        dropped = metrics.get("dropped_iterations", {"count": 0})["count"]
        p99 = metrics["http_req_duration"]["p(99)"]
        errors = metrics["http_req_failed"]
        error_rate = errors.get("rate", errors.get("value"))
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("missing or malformed quality metrics") from error
    if (
        any(type(count) is not int for count in (successes, requests, dropped))
        or not 0 < successes <= requests or dropped < 0
        or type(p99) not in (int, float) or not 0 <= p99 < math.inf
        or type(error_rate) not in (int, float) or not 0 <= error_rate <= 1
    ):
        raise ValueError("invalid quality metrics")
    max_error_rate = (requests - successes) / requests
    if error_rate > max_error_rate and not math.isclose(error_rate, max_error_rate, abs_tol=1e-12):
        raise ValueError("HTTP failure rate contradicts the successful request count")
    offered = requests + dropped
    if offered < 750:
        raise ValueError("offered workload below the expected minimum")
    coverage = successes / offered
    return {
        "successes": successes, "offered": offered, "dropped": dropped, "p99_ms": p99,
        "http_error_rate": error_rate, "offered_success_fraction": coverage,
        "p99_only_pass": p99 <= 200,
        "joint_gate_pass": p99 <= 200 and error_rate <= .01 and coverage >= .99,
    }


def summarize(*paths):
    groups = defaultdict(list)
    logs = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    if any(log["status"] != "pass" or not log["cleanup_verified"] for log in logs):
        raise ValueError("each input must be a completed run with verified cleanup")
    if len({log.get("profile", log.get("scope")) for log in logs}) != len(logs):
        raise ValueError("repeated run identity")
    for run in (run for log in logs for run in log["runs"]):
        mcpu = run["limit_m"] if "limit_m" in run else int(float(run["cpu"]) * 1000)
        groups[mcpu].append(quality_row(run["k6"]["metrics"]))
    return {
        cpu: {"runs": rows, "joint_passes": sum(row["joint_gate_pass"] for row in rows),
              "observed_p99_spread_ms": max(row["p99_ms"] for row in rows) - min(row["p99_ms"] for row in rows)
              if len(rows) > 1 else None}
        for cpu, rows in sorted(groups.items())
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kubernetes", type=Path, nargs="+", help="analyze new paired-run logs separately")
    args = parser.parse_args()
    if args.kubernetes:
        for path in args.kubernetes:
            groups = summarize(path)
            if set(groups) != {500, 1000} or any(len(group["runs"]) != 1 for group in groups.values()):
                parser.error(f"expected one run for each CPU limit in {path}")
        kube = summarize(*args.kubernetes)
        print(json.dumps({"kubernetes": kube}, indent=2))
        return
    docker = summarize(HERE.parent / "005-container-resource-efficiency/live-result.json")
    kube = summarize(HERE.parent / "006-kubernetes-resource-efficiency/live-attempt-4.json")
    assert [len(docker[cpu]["runs"]) for cpu in (500, 1000)] == [2, 2]
    assert docker[1000]["joint_passes"] == 2 and docker[500]["joint_passes"] == 0
    assert kube[1000]["joint_passes"] == 1 and kube[500]["joint_passes"] == 0
    assert kube[1000]["observed_p99_spread_ms"] is None
    print(json.dumps({"docker": docker, "kubernetes": kube}, indent=2))


if __name__ == "__main__":
    main()
