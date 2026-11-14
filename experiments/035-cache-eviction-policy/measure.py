"""Measure Redis hit ratio and evictions under three maxmemory policies.

One local Redis container (memory limit 64 MiB, maxmemory 10 MB), cache-aside
workload with Zipf-distributed key popularity. Same seed, 3 runs per policy.
The container and image are removed at the end and the removal is checked.

Usage:
  py -3 -B measure.py            # needs Docker; prints result JSON
  py -3 -B measure.py --resummarize  # recompute summary from stored runs (no Docker)
"""
from pathlib import Path
import bisect
import json
import random
import socket
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
IMAGE = "redis:7.4-alpine"
NAME = "cel-035-redis"
PORT = 6390
CONTAINER_MEMORY = "64m"
MAXMEMORY = "10mb"
POLICIES = ("allkeys-lru", "volatile-lru", "volatile-ttl")
RUNS = 3
SEED = 35
KEYS = 60_000
VALUE_BYTES = 512
OPS = 150_000
ZIPF_S = 1.0
TTL_SHARE = 0.5          # share of keys written with a TTL (only these are evictable under volatile-*)
TTL_RANGE_S = (600, 3600)  # long enough that nothing expires during a run
CHUNK = 50


def workload(seed=SEED):
    """Deterministic key sequence and per-key TTL (None = no TTL)."""
    rng = random.Random(seed)
    weights = [1 / (i + 1) ** ZIPF_S for i in range(KEYS)]
    cum, acc = [], 0.0
    for w in weights:
        acc += w
        cum.append(acc)
    order = list(range(KEYS))
    rng.shuffle(order)  # popularity rank -> key id
    seq = [order[bisect.bisect_left(cum, rng.random() * acc)] for _ in range(OPS)]
    ttl = [rng.randint(*TTL_RANGE_S) if rng.random() < TTL_SHARE else None for _ in range(KEYS)]
    return seq, ttl


class Resp:
    def __init__(self, port):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=10)
        self.f = self.s.makefile("rb")

    def send(self, cmds):
        buf = bytearray()
        for c in cmds:
            buf += b"*%d\r\n" % len(c)
            for a in c:
                a = a if isinstance(a, bytes) else str(a).encode()
                buf += b"$%d\r\n%s\r\n" % (len(a), a)
        self.s.sendall(buf)
        return [self._read() for _ in cmds]

    def _read(self):
        line = self.f.readline()
        t, rest = line[:1], line[1:-2]
        if t == b"+":
            return rest.decode()
        if t == b"-":
            return RuntimeError(rest.decode())
        if t == b":":
            return int(rest)
        if t == b"$":
            n = int(rest)
            if n < 0:
                return None
            data = self.f.read(n + 2)[:-2]
            return data
        if t == b"*":
            return [self._read() for _ in range(int(rest))]
        raise IOError(f"bad reply {line!r}")


def info(r, section):
    text = r.send([["INFO", section]])[0].decode()
    return {k: v for k, v in (l.split(":", 1) for l in text.splitlines() if ":" in l)}


def run_once(r, policy, seq, ttl):
    r.send([["FLUSHALL"], ["CONFIG", "SET", "maxmemory-policy", policy], ["CONFIG", "RESETSTAT"]])
    value = b"x" * VALUE_BYTES
    hits = misses = oom = 0
    start = time.perf_counter()
    half = len(seq) // 2
    hits_second_half = 0
    for i in range(0, len(seq), CHUNK):
        keys = seq[i:i + CHUNK]
        got = r.send([["GET", f"k{k}"] for k in keys])
        sets = []
        for j, (k, v) in enumerate(zip(keys, got)):
            if v is None:
                misses += 1
                sets.append(["SET", f"k{k}", value] + (["EX", ttl[k]] if ttl[k] else []))
            else:
                hits += 1
                if i + j >= half:
                    hits_second_half += 1
        if sets:
            oom += sum(1 for x in r.send(sets) if isinstance(x, RuntimeError))
    stats, mem, ks = info(r, "stats"), info(r, "memory"), info(r, "keyspace")
    return {"policy": policy, "ops": len(seq), "hits": hits, "misses": misses,
            "hit_ratio": round(hits / len(seq), 4),
            "hit_ratio_second_half": round(hits_second_half / (len(seq) - half), 4),
            "set_errors_oom": oom, "evicted_keys": int(stats["evicted_keys"]),
            "used_memory_bytes": int(mem["used_memory"]), "maxmemory_bytes": int(mem["maxmemory"]),
            "keys_at_end": ks.get("db0", "keys=0").split(",")[0].split("=")[1],
            "seconds": round(time.perf_counter() - start, 1)}


def summarize(runs):
    out = {}
    for p in POLICIES:
        rs = [x for x in runs if x["policy"] == p]
        hr = [x["hit_ratio"] for x in rs]
        out[p] = {"runs": len(rs), "hit_ratio_mean": round(sum(hr) / len(hr), 4),
                  "hit_ratio_range": round(max(hr) - min(hr), 4),
                  "hit_ratio_second_half_mean": round(sum(x["hit_ratio_second_half"] for x in rs) / len(rs), 4),
                  "evicted_keys_mean": round(sum(x["evicted_keys"] for x in rs) / len(rs)),
                  "eviction_per_set": round(sum(x["evicted_keys"] for x in rs) / sum(x["misses"] for x in rs), 4),
                  "set_errors_oom_mean": round(sum(x["set_errors_oom"] for x in rs) / len(rs))}
    best = max(out, key=lambda p: out[p]["hit_ratio_mean"])
    return {"by_policy": out, "best_hit_ratio_policy": best,
            "max_within_policy_range": max(v["hit_ratio_range"] for v in out.values()),
            "origin_cost_per_million_requests": origin_cost(out)}


def origin_cost(by_policy):
    """Translate misses into origin calls when the origin is one LLM request (scenario 2 chatbot shape)."""
    sys.path.insert(0, str(HERE.parent / "scenarios"))
    from decimal import Decimal
    from pricebook import PriceBook, load_scenario, money
    pb, c = PriceBook(), load_scenario("web-llm-chatbot")["chatbot"]
    per_call = (Decimal(c["input_tokens"]) * pb.rate("AmazonBedrockFoundationModels", "APN2-MP:APN2_InputTokenCount_Global-Units", model=c["model"])
                + Decimal(c["output_tokens"]) * pb.rate("AmazonBedrockFoundationModels", "APN2-MP:APN2_OutputTokenCount_Global-Units", model=c["model"])) / Decimal(10**6)
    out = {"origin": f"{c['model']} {c['input_tokens']} in / {c['output_tokens']} out tokens", "usd_per_origin_call": str(per_call)}
    for p, v in by_policy.items():
        misses = (Decimal(1) - Decimal(str(v["hit_ratio_mean"]))) * Decimal(10**6)
        out[p] = {"origin_calls": int(misses), "usd": money(misses * per_call)}
    return out


def sh(*args, check=True):
    return subprocess.run(args, capture_output=True, text=True, check=check, encoding="utf-8")


def free_memory_gib():
    try:
        out = sh("powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory").stdout.strip()
        return round(int(out) / 1024 / 1024, 2)
    except Exception:
        return None


def measure():
    seq, ttl = workload()
    env = {"free_memory_gib_before": free_memory_gib(),
           "docker_server": sh("docker", "version", "--format", "{{.Server.Version}}").stdout.strip()}
    sh("docker", "rm", "-f", NAME, check=False)
    sh("docker", "pull", "-q", IMAGE)
    sh("docker", "run", "-d", "--name", NAME, "--memory", CONTAINER_MEMORY, "-p", f"127.0.0.1:{PORT}:6379",
       IMAGE, "redis-server", "--maxmemory", MAXMEMORY, "--save", "", "--appendonly", "no")
    runs = []
    try:
        for _ in range(50):
            try:
                r = Resp(PORT)
                if r.send([["PING"]])[0] == "PONG":
                    break
            except OSError:
                time.sleep(0.2)
        env["redis_version"] = info(r, "server")["redis_version"]
        for p in POLICIES:
            for n in range(RUNS):
                x = run_once(r, p, seq, ttl)
                x["run"] = n + 1
                runs.append(x)
                print(p, n + 1, x["hit_ratio"], file=sys.stderr)
        env["container_memory_peak"] = sh("docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", NAME).stdout.strip()
    finally:
        sh("docker", "rm", "-f", NAME, check=False)
        sh("docker", "rmi", IMAGE, check=False)
    left_c = sh("docker", "ps", "-a", "--filter", f"name={NAME}", "--format", "{{.Names}}").stdout.strip()
    left_i = sh("docker", "images", "-q", IMAGE).stdout.strip()
    env["cleanup"] = {"container_removed": left_c == "", "image_removed": left_i == ""}
    return {"config": config(), "environment": env, "runs": runs, "summary": summarize(runs)}


def config():
    return {"image": IMAGE, "container_memory": CONTAINER_MEMORY, "maxmemory": MAXMEMORY, "policies": POLICIES,
            "runs_per_policy": RUNS, "seed": SEED, "keys": KEYS, "value_bytes": VALUE_BYTES, "ops": OPS,
            "zipf_s": ZIPF_S, "ttl_share": TTL_SHARE, "ttl_range_s": TTL_RANGE_S, "pipeline_chunk": CHUNK}


if __name__ == "__main__":
    if "--resummarize" in sys.argv:
        d = json.loads((HERE / "result.json").read_text(encoding="utf-8"))
        d["summary"] = summarize(d["runs"])
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(d, indent=1, ensure_ascii=False))
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(measure(), indent=1, ensure_ascii=False))
