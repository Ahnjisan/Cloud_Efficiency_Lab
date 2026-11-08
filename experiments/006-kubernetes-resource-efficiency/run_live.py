"""Run an isolated Minikube experiment on Windows and print the raw record."""
import argparse
import ctypes
import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path
from runpy import run_path
import re
import shutil
import subprocess
import tempfile
import time
from urllib.request import urlopen
from uuid import uuid4

HERE = Path(__file__).resolve().parent
safety = run_path(str(HERE / "live_safety.py"))
IMAGE = "finguardops-python:k8s-371-395200c3"
PROFILE = "infrafit-" + uuid4().hex[:10]
# The dedicated node is capped at 2 GiB, leaving 1.5 GiB plus bootstrap headroom.
START_GIB = 3.75
STOP_GIB = 1.5

class MemoryStatus(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
        (name, ctypes.c_ulonglong)
        for name in ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")
    ]

def memory():
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError("Windows memory reading failed")
    return status.available / 2**30

def pod(name, cpu, limit, workload=False):
    container = {
        "name": "fixture", "image": IMAGE, "imagePullPolicy": "Never",
        "command": ["python3", "/fixture/workload.py"] if workload else ["python3", "-c", "import time; time.sleep(240)"],
        "resources": {"requests": {"cpu": f"{cpu}m", "memory": "64Mi"}, "limits": {"cpu": f"{limit}m", "memory": "128Mi"}},
    }
    spec = {"restartPolicy": "Never", "terminationGracePeriodSeconds": 1, "containers": [container]}
    if workload:
        container["volumeMounts"] = [{"name": "fixture", "mountPath": "/fixture", "readOnly": True}]
        container["startupProbe"] = {
            "httpGet": {"path": "/health", "port": 8080}, "periodSeconds": 1, "failureThreshold": 15,
        }
        spec["volumes"] = [{"name": "fixture", "configMap": {"name": "fixture"}}]
    return {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": name}, "spec": spec}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--low-memory", action="store_true", help="use a 1800 MiB node and a 3.25 GiB host start guard")
    parser.add_argument("--rollback-repetitions", type=int, choices=(1, 2, 3), help="measure Deployment rollback sequences")
    parser.add_argument("--bounded-rollback-memory", action="store_true", help="permit rollback mode to start at 2.65 GiB")
    args = parser.parse_args()
    if args.bounded_rollback_memory and not (args.low_memory and args.rollback_repetitions):
        parser.error("--bounded-rollback-memory requires --low-memory and --rollback-repetitions")
    start_guard = 3.25 if args.low_memory else START_GIB
    if args.bounded_rollback_memory:
        start_guard = 2.65
    node_memory = 1800 if args.low_memory else 2048
    original_env = os.environ.copy()
    before = memory()
    record = {"profile": PROFILE, "available_before_gib": before, "start_guard_gib": start_guard, "node_memory_mib": node_memory,
              "stop_guard_gib": STOP_GIB, "commands": [], "scheduling": {}, "runs": [], "status": "blocked"}
    if args.rollback_repetitions:
        record["requested_repetitions"] = args.rollback_repetitions
    if before < start_guard:
        record["reason"] = "host memory below isolated cluster start guard"
        print(json.dumps(record, indent=2))
        return 1
    temp_base = Path(tempfile.gettempdir()).resolve()
    with tempfile.TemporaryDirectory(prefix="infrafit-kube-", dir=temp_base) as directory:
        scratch = Path(directory).resolve()
        if scratch.parent != temp_base or not scratch.name.startswith("infrafit-kube-"):
            raise RuntimeError("unexpected temporary directory")
        env = {**original_env, "MINIKUBE_HOME": str(scratch), "KUBECONFIG": str(scratch / "kubeconfig"), "MINIKUBE_IN_STYLE": "false"}
        termination_unverified = False

        def command(args, timeout=30, payload=None, checked=True, monitor=True, process_env=env, log_stdout=True):
            nonlocal termination_unverified
            minimum = memory() if monitor else None
            if monitor and minimum < STOP_GIB:
                raise RuntimeError("host memory below the command stop guard")
            proc = subprocess.Popen(args, stdin=subprocess.PIPE if payload else None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=process_env)
            deadline = time.monotonic() + timeout
            stop_reason = None
            data = payload.encode() if payload else None
            while True:
                try:
                    out, err = proc.communicate(input=data, timeout=2)
                    break
                except subprocess.TimeoutExpired:
                    data = None
                    try:
                        if monitor:
                            minimum = min(minimum, memory())
                    except OSError:
                        stop_reason = "host memory reading failed"
                    if stop_reason or time.monotonic() >= deadline or (monitor and minimum < STOP_GIB):
                        stop_reason = stop_reason or "local deadline or memory guard"
                        if args[0] == "minikube" and proc.poll() is None:
                            # Minikube can leave a Docker CLI child running after its parent stops.
                            try:
                                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                                               capture_output=True, timeout=5, check=True)
                            except (OSError, subprocess.SubprocessError):
                                termination_unverified = True
                        try:
                            proc.kill()
                            proc.wait(timeout=5)
                        except (OSError, subprocess.TimeoutExpired) as error:
                            termination_unverified = True
                            raise RuntimeError("command termination could not be verified") from error
                        try:
                            out, err = proc.communicate(timeout=5)
                        except subprocess.TimeoutExpired as error:
                            out, err = error.output or b"", error.stderr or b""
                        err += f"\nStopped: {stop_reason}.".encode()
                        break
            clean = lambda raw: (raw.decode("utf-8", errors="replace")
                                 .replace(str(scratch), "[scratch]").replace(str(HERE), "[experiment]")
                                 .replace(str(HERE.parent), "[experiments]")
                                 .replace(original_env["USERPROFILE"], "[user-profile]"))
            stdout, stderr = clean(out), clean(err)
            record["commands"].append({"args": [clean(arg.encode()) for arg in args], "exit_code": proc.returncode, "min_host_gib": minimum, "stdout": stdout if log_stdout else "[omitted]", "stderr": stderr})
            if checked and (stop_reason or proc.returncode):
                raise RuntimeError(f"{args[0]} {args[1]} failed: {stop_reason or proc.returncode}")
            return stdout

        kube = lambda *args, **kw: command(["kubectl", "--context", PROFILE, "--request-timeout=12s", *args], **kw)

        def container_inventory():
            rows = sorted(command(["docker", "ps", "-a", "--no-trunc", "--format",
                                   "{{.ID}} {{.State}}"], monitor=False, log_stdout=False).splitlines())
            return {"count": len(rows), "sha256": hashlib.sha256("\n".join(rows).encode()).hexdigest()}

        attempted = False
        profile_attempted = False
        try:
            pinned = safety["pin_local_docker"](command, env)
            env.clear()
            env.update(pinned)
            record["docker_endpoint"] = env["DOCKER_HOST"]
            command(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"])
            if memory() < start_guard:
                raise RuntimeError("memory fell below the start guard")
            original_context = command(["kubectl", "config", "current-context"], process_env=original_env).strip()
            cache = Path(original_env["USERPROFILE"]) / ".minikube" / "cache"
            for path in sorted(cache.rglob("*")):
                if path.is_file() and ("v1.37.0-containerd" in path.name or "kicbase_v0.0.51" in path.name):
                    dest = scratch / ".minikube" / "cache" / path.relative_to(cache)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, dest)
            if args.rollback_repetitions:
                record["container_inventory"] = {"before": container_inventory()}
            attempted = True
            command(["docker", "network", "create", "--label", "infrafit.run=" + PROFILE, PROFILE])
            profile_attempted = True
            command(["minikube", "start", "-p", PROFILE, "--driver=docker", "--container-runtime=containerd",
                     "--kubernetes-version=v1.37.0", "--cpus=2", "--memory=" + str(node_memory), "--disk-size=8g",
                     "--network=" + PROFILE, "--listen-address=127.0.0.1", "--install-addons=false",
                     "--auto-update-drivers=false", "--interactive=false", "--wait=apiserver",
                     "--wait-timeout=90s"], timeout=150)
            command(["minikube", "image", "load", IMAGE, "--daemon", "-p", PROFILE], timeout=70)
            nodes = json.loads(kube("get", "nodes", "-o", "json"))["items"]
            if len(nodes) != 1:
                raise RuntimeError("expected exactly one isolated node")
            node = nodes[0]["status"]
            record["node"] = {key: node[key] for key in ("capacity", "allocatable")}
            cpu = node["allocatable"]["cpu"]
            alloc = int(cpu[:-1]) if cpu.endswith("m") else int(cpu) * 1000
            large, small = alloc // 2 + 50, alloc // 3
            scheduling_cases = () if args.rollback_repetitions else (("small", small, 2), ("large", large, 1))
            for mode, request, expected in scheduling_cases:
                manifests = [pod(mode + str(i), request, alloc) for i in (1, 2)]
                kube("apply", "-f", "-", payload=json.dumps({"apiVersion": "v1", "kind": "List", "items": manifests}))
                for _ in range(12):
                    data = json.loads(kube("get", "pods", "-o", "json"))["items"]
                    scheduled = sum(bool(p["spec"].get("nodeName")) for p in data)
                    pending = any(c.get("reason") == "Unschedulable" for p in data for c in p["status"].get("conditions", []))
                    if scheduled == expected and (mode == "small" or pending):
                        break
                    time.sleep(1)
                record["scheduling"][mode] = {"request_m": request, "scheduled": scheduled, "unschedulable": pending}
                if scheduled != expected or (mode == "large" and not pending):
                    raise RuntimeError("unexpected scheduling result: " + mode)
                record["status"] = "partial"
                kube("delete", "pod", mode + "1", mode + "2", "--wait=true", "--timeout=20s")
            kube("create", "configmap", "fixture", "--from-file=workload.py=" + str(HERE / "workload.py"))
            load_script = HERE / "load.js"
            phases = [(None, None, limit) for limit in (1000, 500)]
            if args.rollback_repetitions:
                phases = [(rep, phase, limit) for rep in range(1, args.rollback_repetitions + 1)
                          for phase, limit in (("baseline", 1000), ("candidate", 500), ("restored", 1000))]
                load_script = HERE.parent / "013-peak-rollback/load.js"
            for repetition, phase, limit in phases:
                phase_started = time.monotonic()
                if phase is None:
                    name = "load-" + str(limit)
                    kube("apply", "-f", "-", payload=json.dumps(pod(name, 100, limit, True)))
                    kube("wait", "--for=condition=Ready", "pod/" + name, "--timeout=25s")
                else:
                    if phase == "baseline" and repetition == 1:
                        spec = pod("rollback", 100, limit, True)["spec"]
                        spec["restartPolicy"] = "Always"
                        selector = {"app": "infrafit-rollback"}
                        deployment = {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "rollback"},
                                      "spec": {"replicas": 1, "strategy": {"type": "Recreate"},
                                               "selector": {"matchLabels": selector},
                                               "template": {"metadata": {"labels": selector}, "spec": spec}}}
                        kube("apply", "-f", "-", payload=json.dumps(deployment))
                    elif phase == "candidate":
                        kube("set", "resources", "deployment/rollback", "-c", "fixture", "--limits=cpu=500m,memory=128Mi")
                    elif phase == "restored":
                        kube("rollout", "undo", "deployment/rollback")
                    kube("rollout", "status", "deployment/rollback", "--timeout=30s", timeout=35)
                    pods = json.loads(kube("get", "pods", "-l", "app=infrafit-rollback", "-o", "json"))["items"]
                    ready = [item for item in pods if not item["metadata"].get("deletionTimestamp")
                             and any(c["type"] == "Ready" and c["status"] == "True"
                                     for c in item["status"].get("conditions", []))]
                    if len(ready) != 1:
                        raise RuntimeError("expected one ready rollback pod")
                    name = ready[0]["metadata"]["name"]
                sample_name = name if phase is None else f"{repetition}-{phase}"
                forward_log = scratch / "forward.txt"
                with forward_log.open("w+b") as stream:
                    forward = subprocess.Popen(["kubectl", "--context", PROFILE, "port-forward", "--address=127.0.0.1", "pod/" + name, ":8080"], env=env, stdout=stream, stderr=stream)
                    try:
                        for _ in range(30):
                            match = re.search(r"127\.0\.0\.1:(\d+)", forward_log.read_text(errors="replace"))
                            if match:
                                break
                            time.sleep(.25)
                        if not match:
                            raise RuntimeError("port forwarding did not start")
                        url = "http://127.0.0.1:" + match[1]
                        def snapshot():
                            for attempt in range(8):
                                try:
                                    with urlopen(url + "/metrics", timeout=2) as response:
                                        return json.load(response)
                                except (OSError, HTTPException):
                                    if attempt == 7 or forward.poll() is not None:
                                        raise
                                    time.sleep(.4)
                        first = snapshot()
                        measured_at = time.monotonic()
                        summary = scratch / (sample_name + ".json")
                        command(["k6", "run", "--summary-export", str(summary), str(load_script)], timeout=45, process_env={**env, "LOCAL_URL": url})
                        last = snapshot()
                        interval = time.monotonic() - measured_at
                        state = json.loads(kube("get", "pod", name, "-o", "json"))["status"]
                        run = {"limit_m": limit, "before": first, "after": last, "sample_interval_s": interval,
                               "container_statuses": state["containerStatuses"], "k6": json.loads(summary.read_text()),
                               "measurement_valid": False}
                        record["runs"].append(run)
                        safety["validate_measurement"](run, limit, target_requests=300 if phase else 750)
                        if phase:
                            metrics = run["k6"]["metrics"]
                            errors = metrics["http_req_failed"]
                            offered = metrics["http_reqs"]["count"] + metrics.get("dropped_iterations", {"count": 0})["count"]
                            coverage = metrics["successful_requests"]["count"] / offered
                            run.update(repetition=repetition, phase=phase, pod_uid=ready[0]["metadata"]["uid"],
                                       offered=offered, success_fraction=coverage,
                                       quality_pass=(offered >= 300 and coverage >= .99
                                                     and errors.get("rate", errors.get("value")) <= .01
                                                     and metrics["http_req_duration"]["p(99)"] <= 200),
                                       phase_to_observation_s=time.monotonic() - phase_started)
                            record["status"] = "partial"
                    finally:
                        forward.terminate()
                        try:
                            forward.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            forward.kill()
                            forward.wait(timeout=5)
                        record.setdefault("port_forward_logs", {})[sample_name] = forward_log.read_text(errors="replace")
                if phase is None:
                    kube("delete", "pod", name, "--wait=true", "--timeout=20s")
            record["status"] = "pass"
        except (AssertionError, HTTPException, KeyError, OSError, RuntimeError, ValueError) as error:
            record["reason"] = str(error).replace(str(scratch), "[scratch]") or type(error).__name__
        finally:
            if profile_attempted and not termination_unverified:
                try:
                    command(["minikube", "delete", "-p", PROFILE], timeout=65, checked=False, monitor=False)
                except (OSError, RuntimeError) as error:
                    record["profile_delete_error"] = type(error).__name__
            if attempted:
                record["cleanup_verified"] = not termination_unverified and safety["cleanup_owned"](command, PROFILE, minikube=True)
                if "container_inventory" in record:
                    evidence = record["container_inventory"]
                    try:
                        evidence["after"] = container_inventory()
                        evidence["matches"] = evidence["before"] == evidence["after"]
                    except (OSError, RuntimeError) as error:
                        evidence["comparison_error"] = type(error).__name__
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
