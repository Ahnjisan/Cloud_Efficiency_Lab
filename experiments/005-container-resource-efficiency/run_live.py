"""Measure the existing bounded HTTP fixture in isolated Docker containers."""
import json
import os
from pathlib import Path
from runpy import run_path
import subprocess
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent / "006-kubernetes-resource-efficiency"
IMAGE = "python@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7"
PREFIX = "infrafit-docker-" + uuid4().hex[:10]
START_GIB = 2.25
STOP_GIB = 1.5
safety = run_path(str(FIXTURE / "live_safety.py"))
memory = run_path(str(FIXTURE / "run_live.py"))["memory"]

def main():
    record = {"scope": PREFIX, "image": IMAGE, "start_guard_gib": START_GIB,
              "stop_guard_gib": STOP_GIB, "available_before_gib": memory(), "status": "blocked",
              "commands": [], "runs": []}
    if record["available_before_gib"] < START_GIB:
        record["reason"] = "host memory below the isolated Docker start guard"
        print(json.dumps(record, indent=2))
        return 1

    temp_root = Path(tempfile.gettempdir()).resolve()
    with tempfile.TemporaryDirectory(prefix="infrafit-docker-load-", dir=temp_root) as directory:
        temp = Path(directory).resolve()
        if temp.parent != temp_root or not temp.name.startswith("infrafit-docker-load-"):
            raise RuntimeError("unexpected temporary directory")

        docker_env = os.environ.copy()

        termination_unverified = False

        def command(args, timeout=15, monitor=True, checked=True, env=None):
            nonlocal termination_unverified
            minimum = memory() if monitor else None
            if monitor and minimum < STOP_GIB:
                raise RuntimeError("host memory below the command stop guard")
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       env=docker_env if env is None else env)
            deadline = time.monotonic() + timeout
            stop_reason = None
            while True:
                try:
                    out, err = process.communicate(timeout=2)
                    break
                except subprocess.TimeoutExpired:
                    try:
                        if monitor:
                            minimum = min(minimum, memory())
                    except OSError:
                        stop_reason = "host memory reading failed"
                    if stop_reason or time.monotonic() >= deadline or (monitor and minimum < STOP_GIB):
                        stop_reason = stop_reason or "local deadline or memory guard"
                        try:
                            process.kill()
                            process.wait(timeout=5)
                        except (OSError, subprocess.TimeoutExpired) as error:
                            termination_unverified = True
                            raise RuntimeError("command termination could not be verified") from error
                        out, err = process.communicate()
                        err += f"\nStopped: {stop_reason}.".encode()
                        break
            clean = lambda text: text.replace(str(temp), "[scratch]").replace(str(FIXTURE), "[fixture]")
            stdout = clean(out.decode("utf-8", errors="replace"))
            stderr = clean(err.decode("utf-8", errors="replace"))
            record["commands"].append({
                "args": [clean(arg) for arg in args], "exit_code": process.returncode,
                "min_host_gib": minimum, "stdout": stdout, "stderr": stderr,
            })
            if checked and (stop_reason or process.returncode):
                raise RuntimeError(f"{args[0]} {args[1]} failed: {stop_reason or process.returncode}")
            return stdout

        attempted = False
        try:
            docker_env = safety["pin_local_docker"](command, docker_env)
            record["docker_endpoint"] = docker_env["DOCKER_HOST"]
            command(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"])
            attempted = True
            command(["docker", "network", "create", "--label", "infrafit.run=" + PREFIX, PREFIX])
            for index, cpu in enumerate(("1.0", "0.5", "0.5", "1.0"), 1):
                if memory() < START_GIB:
                    raise RuntimeError("memory fell below start guard before next configuration")
                name = f"{PREFIX}-{index}"
                command([
                    "docker", "run", "-d", "--rm", "--pull=never", "--name", name,
                    "--label", "infrafit.run=" + PREFIX, "--network", PREFIX, "--publish", "127.0.0.1::8080",
                    "--cpus", cpu, "--memory", "512m", "--memory-swap", "512m", "--pids-limit", "32",
                    "--mount", "type=bind,src=" + str(FIXTURE / "workload.py") + ",dst=/fixture.py,readonly",
                    IMAGE, "python3", "/fixture.py",
                ])
                port = command(["docker", "port", name, "8080/tcp"]).strip().rsplit(":", 1)[1]
                url = "http://127.0.0.1:" + str(int(port))

                def snapshot(endpoint):
                    with urlopen(url + endpoint, timeout=3) as response:
                        return json.load(response)

                for _ in range(16):
                    try:
                        snapshot("/health")
                        break
                    except (URLError, OSError):
                        time.sleep(.5)
                else:
                    raise RuntimeError("workload did not become ready")
                first = snapshot("/metrics")
                measured_at = time.monotonic()
                summary = temp / f"run-{index}.json"
                command(["k6", "run", "--summary-export", str(summary), str(FIXTURE / "load.js")],
                        timeout=45, env={**docker_env, "LOCAL_URL": url})
                last = snapshot("/metrics")
                interval = time.monotonic() - measured_at
                state = json.loads(command(["docker", "inspect", "--format", "{{json .State}}", name]))
                restart = int(command(["docker", "inspect", "--format", "{{.RestartCount}}", name]))
                run = {
                    "run": index, "cpu": cpu, "memory_limit_mib": 512,
                    "before": first, "after": last, "sample_interval_s": interval, "oom_killed": state["OOMKilled"],
                    "restart_count": restart, "k6": json.loads(summary.read_text(encoding="utf-8")),
                    "measurement_valid": False,
                }
                record["runs"].append(run)
                safety["validate_measurement"](run, 1000 if cpu == "1.0" else 500)
                record["status"] = "partial"
                command(["docker", "stop", "--time", "2", name], monitor=False)
            record["status"] = "pass"
        except (AssertionError, KeyError, OSError, RuntimeError, ValueError) as error:
            record["reason"] = str(error).replace(str(temp), "[scratch]").replace(str(FIXTURE), "[fixture]")
        finally:
            if attempted:
                record["cleanup_verified"] = not termination_unverified and safety["cleanup_owned"](command, PREFIX)
                if not record["cleanup_verified"]:
                    record["status"] = "fail"
                    record["cleanup_reason"] = (
                        "command termination could not be verified" if termination_unverified
                        else "temporary resources remain or cleanup could not be verified"
                    )
    print(json.dumps(record, indent=2))
    return 0 if record["status"] == "pass" else 1

if __name__ == "__main__":
    raise SystemExit(main())
