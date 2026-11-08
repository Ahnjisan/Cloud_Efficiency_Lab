"""Measure a CPU-cap rollback on one dedicated local Docker container."""
import json
import os
from pathlib import Path
from runpy import run_path
import subprocess
import tempfile
import time
from urllib.request import urlopen
from uuid import uuid4

HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent / "006-kubernetes-resource-efficiency"
IMAGE = "python@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7"
START_GIB = 2.25
STOP_GIB = 1.5


def main():
    helpers = run_path(str(FIXTURE / "live_safety.py"))
    memory = run_path(str(FIXTURE / "run_live.py"))["memory"]
    env = os.environ.copy()
    scope = "infrafit-rollback-" + uuid4().hex[:12]
    result = {"scope": scope, "image": IMAGE, "status": "blocked", "phases": []}
    attempted = False
    original = None

    def command(args, checked=True, monitor=True, extra_env=None):
        output = subprocess.run(args, env=extra_env or env, capture_output=True, timeout=30, check=False)
        if checked and output.returncode:
            raise RuntimeError(f"{args[0]} {args[1]} failed with exit code {output.returncode}")
        return output.stdout.decode("utf-8").strip()

    def inventory():
        return command(["docker", "ps", "-a", "--no-trunc", "--format", "{{.ID}} {{.State}}"]).splitlines()

    try:
        result["start_host_gib"] = memory()
        if result["start_host_gib"] < START_GIB:
            raise RuntimeError("host memory below 2.25 GiB start guard")
        env = helpers["pin_local_docker"](command, env)
        result["docker_endpoint"] = env["DOCKER_HOST"]
        result["docker_version"] = command(["docker", "version", "--format", "{{.Server.Version}}"])
        result["k6_version"] = command(["k6", "version"])
        command(["docker", "image", "inspect", IMAGE])
        original = set(inventory())
        attempted = True
        command(["docker", "run", "-d", "--rm", "--pull=never", "--name", scope,
                 "--label", "infrafit.run=" + scope, "--publish", "127.0.0.1::8080",
                 "--cpus", "1.0", "--memory", "384m", "--memory-swap", "384m", "--pids-limit", "32",
                 "--mount", "type=bind,src=" + str(FIXTURE / "workload.py") + ",dst=/fixture.py,readonly",
                 IMAGE, "python3", "/fixture.py"])
        port = int(command(["docker", "port", scope, "8080/tcp"]).rsplit(":", 1)[1])
        url = f"http://127.0.0.1:{port}"

        def snapshot(path):
            with urlopen(url + path, timeout=2) as response:
                return json.load(response)

        for _ in range(12):
            try:
                snapshot("/health")
                break
            except OSError:
                time.sleep(.5)
        else:
            raise RuntimeError("fixture did not become ready")

        with tempfile.TemporaryDirectory(prefix="infrafit-rollback-load-") as directory:
            for name, cpu in (("baseline", "1.0"), ("candidate", "0.25"), ("restored", "1.0")):
                available = memory()
                if available < STOP_GIB:
                    raise RuntimeError("host memory below 1.5 GiB stop guard")
                change_started = time.monotonic()
                command(["docker", "update", "--cpus", cpu, scope])
                before = snapshot("/metrics")
                summary = Path(directory) / f"{name}.json"
                args = ["k6", "run", "--summary-export", str(summary), str(HERE / "load.js")]
                with subprocess.Popen(args, env={**env, "LOCAL_URL": url},
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as process:
                    deadline = time.monotonic() + 25
                    try:
                        while process.poll() is None:
                            available = min(available, memory())
                            if available < STOP_GIB or time.monotonic() >= deadline:
                                raise RuntimeError("load stopped at host memory guard or deadline")
                            time.sleep(.5)
                    finally:
                        if process.poll() is None:
                            process.kill()
                            process.wait()
                    if process.returncode:
                        raise RuntimeError(f"k6 failed with exit code {process.returncode}")
                after = snapshot("/metrics")
                quota, period = map(int, after["cpu.max"].split())
                if before["cpu.max"] != after["cpu.max"] or quota / period != float(cpu):
                    raise RuntimeError("observed cgroup quota does not match the phase")
                metrics = json.loads(summary.read_text(encoding="utf-8"))["metrics"]
                successes = metrics["successful_requests"]["count"]
                dropped = metrics.get("dropped_iterations", {"count": 0})["count"]
                requests = metrics["http_reqs"]["count"]
                errors = metrics["http_req_failed"]
                error_rate = errors.get("rate", errors.get("value"))
                p99 = metrics["http_req_duration"]["p(99)"]
                if not (0 < successes <= requests and dropped >= 0 and requests + dropped >= 300
                        and 0 <= p99 < float("inf") and 0 <= error_rate <= (requests - successes) / requests):
                    raise ValueError("invalid or incomplete load metrics")
                coverage = successes / (requests + dropped)
                result["phases"].append({
                    "phase": name, "cpu": cpu, "before": before, "after": after, "k6_metrics": metrics,
                    "host_min_gib": available, "change_to_observation_seconds": time.monotonic() - change_started,
                    "success_fraction": coverage,
                    "quality_pass": p99 <= 200 and coverage >= .99 and error_rate <= .01,
                })
        result["status"] = "pass" if [row["quality_pass"] for row in result["phases"]] == [True, False, True] else "inconclusive"
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        result["reason"] = str(error).replace(str(HERE), "[experiment]").replace(str(FIXTURE), "[fixture]")
    finally:
        if attempted:
            try:
                result["cleanup_verified"] = helpers["cleanup_owned"](command, scope)
                result["existing_containers_unchanged"] = set(inventory()) == original
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                result["cleanup_verified"] = False
            if not result["cleanup_verified"] or not result.get("existing_containers_unchanged"):
                result["status"] = "fail"
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
