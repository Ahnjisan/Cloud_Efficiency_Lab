"""Experiment 039 local measurement: Deployment 0 -> 1 time to Ready on a dedicated Minikube profile.

No KEDA: replicas are changed with `kubectl scale`, so this measures pod start only.
Safety: dedicated profile + kubeconfig, memory guards, host container/image inventory before and after,
profile deleted at the end. Prints JSON to stdout; progress to stderr.
"""
from datetime import datetime
from pathlib import Path
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid

PROFILE = "cel039-" + uuid.uuid4().hex[:8]
NS = "cel-039"
IMAGE = "python:3.12-alpine"
PAIRS = 5
START_GIB, STOP_GIB = 4.0, 1.5
MANIFEST = f"""apiVersion: v1
kind: Namespace
metadata: {{name: {NS}}}
---
apiVersion: apps/v1
kind: Deployment
metadata: {{name: worker, namespace: {NS}}}
spec:
  replicas: 0
  selector: {{matchLabels: {{app: worker}}}}
  template:
    metadata: {{labels: {{app: worker}}}}
    spec:
      terminationGracePeriodSeconds: 1
      containers:
      - name: w
        image: {IMAGE}
        imagePullPolicy: IfNotPresent
        command: ["python", "-c", "import time\\nwhile True: time.sleep(3600)"]
        resources: {{requests: {{cpu: 100m, memory: 64Mi}}, limits: {{memory: 128Mi}}}}
        readinessProbe: {{exec: {{command: ["true"]}}, periodSeconds: 1, initialDelaySeconds: 0}}
"""


class MemoryStatus(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                ("avail", ctypes.c_ulonglong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]


def free_gib():
    s = MemoryStatus(); s.length = ctypes.sizeof(s)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
    return round(s.avail / 1024 ** 3, 2)


def log(*a):
    print(datetime.now().strftime("%H:%M:%S"), *a, file=sys.stderr, flush=True)


def run(args, env, timeout=120, check=True, input_text=None):
    p = subprocess.run(args, env=env, capture_output=True, text=True, encoding="utf-8", timeout=timeout, input=input_text)
    if check and p.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:3])} failed: {p.stderr.strip()[-300:]}")
    return p.stdout


def inventory(env):
    rows = sorted(run(["docker", "ps", "-a", "--no-trunc", "--format", "{{.ID}} {{.State}}"], env).splitlines())
    rows = [r for r in rows if PROFILE not in r]
    images = sorted(run(["docker", "images", "--no-trunc", "--format", "{{.Repository}}:{{.Tag}} {{.ID}}"], env).splitlines())
    h = lambda xs: hashlib.sha256("\n".join(xs).encode()).hexdigest()
    return {"containers": len(rows), "containers_sha256": h(rows), "images": len(images), "images_sha256": h(images), "image_list": images}


def pods(kube):
    return json.loads(kube(["get", "pods", "-n", NS, "-l", "app=worker", "-o", "json"]))["items"]


def ready(pod):
    return any(c["type"] == "Ready" and c["status"] == "True" for c in pod.get("status", {}).get("conditions", []))


def wait_gone(kube, limit=90):
    end = time.monotonic() + limit
    while time.monotonic() < end:
        if not pods(kube):
            return
        time.sleep(0.5)
    raise RuntimeError("pods did not terminate")


def measure_once(kube, mk, cache):
    if free_gib() < STOP_GIB:
        raise RuntimeError("host memory below stop guard")
    kube(["scale", "deployment/worker", "-n", NS, "--replicas=0"])
    wait_gone(kube)
    if not cache:
        mk(["image", "rm", IMAGE], check=False)
        if IMAGE.split(":")[0] in mk(["image", "ls"]) and IMAGE.split(":")[1] in mk(["image", "ls"]):
            raise RuntimeError("image still cached in node")
    t0 = time.monotonic()
    kube(["scale", "deployment/worker", "-n", NS, "--replicas=1"])
    polls = 0
    while time.monotonic() - t0 < 300:
        items = pods(kube); polls += 1
        if items and ready(items[0]):
            wall = time.monotonic() - t0
            pod = items[0]
            ts = lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
            rt = next(c["lastTransitionTime"] for c in pod["status"]["conditions"] if c["type"] == "Ready")
            return {"cache": cache, "wall_s": round(wall, 2), "polls": polls,
                    "created_to_ready_s": (ts(rt) - ts(pod["metadata"]["creationTimestamp"])).total_seconds(),
                    "free_gib": free_gib()}
    raise RuntimeError("pod not Ready within 300 s")


def main():
    rec = {"profile_prefix": "cel039-", "namespace": NS, "image": IMAGE, "pairs": PAIRS, "start_guard_gib": START_GIB,
           "stop_guard_gib": STOP_GIB, "free_gib_before": free_gib(), "runs": [], "status": "not_run"}
    if rec["free_gib_before"] < START_GIB:
        rec["reason"] = "free memory below start guard"
        return rec
    tmp = Path(tempfile.mkdtemp(prefix="cel039-"))
    env = dict(os.environ, KUBECONFIG=str(tmp / "kubeconfig"))
    kube = lambda a, **kw: run(["kubectl", "--context", PROFILE, "--request-timeout=20s", *a], env, **kw)
    mk = lambda a, **kw: run(["minikube", "-p", PROFILE, *a], env, timeout=kw.pop("timeout", 180), **kw)
    rec["versions"] = {"docker": run(["docker", "version", "--format", "{{.Server.Version}}"], env).strip(),
                       "minikube": run(["minikube", "version", "--short"], env).strip(),
                       "kubectl": json.loads(run(["kubectl", "version", "--client", "-o", "json"], env))["clientVersion"]["gitVersion"]}
    before = inventory(env)
    rec["host_before"] = {k: v for k, v in before.items() if k != "image_list"}
    started = False
    try:
        log("minikube start", PROFILE)
        started = True
        mk(["start", "--driver=docker", "--memory=2048", "--cpus=2", "--keep-context=true"], timeout=900)
        rec["node"] = {"kubernetes": json.loads(kube(["version", "-o", "json"]))["serverVersion"]["gitVersion"],
                       "runtime": kube(["get", "nodes", "-o", "jsonpath={.items[0].status.nodeInfo.containerRuntimeVersion}"]).strip()}
        rec["free_gib_after_start"] = free_gib()
        if rec["free_gib_after_start"] < STOP_GIB:
            raise RuntimeError("host memory below stop guard after start")
        kube(["apply", "-f", "-"], input_text=MANIFEST)
        for i in range(PAIRS):
            for cache in (False, True):
                r = measure_once(kube, mk, cache)
                r["pair"] = i + 1
                rec["runs"].append(r)
                log("pair", i + 1, "cache" if cache else "no-cache", r["wall_s"], r["created_to_ready_s"])
        rec["status"] = "measured"
    except Exception as exc:  # record and stop
        rec["status"] = "failed"
        rec["error"] = str(exc)[-500:]
    finally:
        if started:
            log("cleanup")
            run(["kubectl", "--context", PROFILE, "delete", "namespace", NS, "--wait=true", "--timeout=120s"], env, check=False, timeout=180)
            run(["minikube", "delete", "-p", PROFILE], env, check=False, timeout=600)
        profiles = run(["minikube", "profile", "list", "-o", "json"], env, check=False)
        after = inventory(env)
        rec["cleanup"] = {
            "profile_removed": PROFILE not in profiles,
            "containers_same": (after["containers"], after["containers_sha256"]) == (before["containers"], before["containers_sha256"]),
            "images_same": after["images_sha256"] == before["images_sha256"],
            "new_host_images": sorted(set(after["image_list"]) - set(before["image_list"])),
        }
        rec["free_gib_end"] = free_gib()
        for f in tmp.iterdir():
            f.unlink()
        tmp.rmdir()
    return rec


if __name__ == "__main__":
    out = main()
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False))
