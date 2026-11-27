"""Experiment 039: worker always-on vs KEDA scale-to-zero — monthly cost and first-result latency.

Event model per month (30 days starting Monday, 22 weekdays). Pod uptime = union of forced-up windows
(W1: whole month, W3: weekday 08-18) and scale-from-zero sessions [scale decision, scale-down].
Pod start times come from measurement.json (local Minikube); node boot and Fargate start are assumptions.
"""
from decimal import Decimal as D
from pathlib import Path
import json
import math
import random
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "037-measurement-sheet-unit-cost"))
from rates import Rates, emit, money  # noqa: E402

sys.path.insert(0, str(HERE.parent / "scenarios"))
from service_pack import fargate_provision  # noqa: E402

DAY = 86400.0
MONTH_S = 30 * DAY
SEEDS = (1, 2, 3)
VOLUMES = {"small": 20, "medium": 100, "large": 500}
PROC_MEDIAN, PROC_SIGMA = 20.0, 0.5
POLL_COOLDOWN = {"fast": (15, 120), "base": (30, 300), "slow": (60, 600)}
NODE_BOOT = {"low": 60, "base": 120, "high": 180}
FARGATE_START = {"low": 30, "base": 60, "high": 120}
NODE_SCALE_DOWN_DELAY = {"base": 600, "none": 0}
WORKER = {"vcpu": D("0.5"), "mem_gb": D(1)}
# Shared node group (case a), assumed: other workloads' total requests on m7g.large nodes (1.78 vCPU / 7.14 GiB allocatable, 031 assumption).
SHARED = {"other_vcpu": D("2.4"), "other_mem_gib": D(5), "alloc_vcpu": D("1.78"), "alloc_mem_gib": D("7.142")}


def measured_start():
    m = json.loads((HERE / "measurement.json").read_text(encoding="utf-8"))
    runs = m.get("runs", [])
    pick = lambda cache: [r["wall_s"] for r in runs if r["cache"] is cache]
    warm, cold = pick(True), pick(False)
    if m.get("status") != "measured" or not warm or not cold:
        return {"source": "assumption (measurement not available)", "warm_s": 10.0, "cold_s": 30.0, "status": m.get("status")}
    return {"source": "measurement.json", "status": m["status"], "warm_s": round(sum(warm) / len(warm), 2), "cold_s": round(sum(cold) / len(cold), 2),
            "warm_range": [min(warm), max(warm)], "cold_range": [min(cold), max(cold)], "n": [len(warm), len(cold)]}


def arrivals(seed, per_day):
    rng = random.Random(f"039-{seed}-{per_day}")
    out = []
    for d in range(30):
        if d % 7 >= 5:
            continue
        for _ in range(per_day):
            h = rng.uniform(8, 18) if rng.random() < 0.95 else rng.uniform(18, 22)
            out.append((d * DAY + h * 3600, rng.lognormvariate(math.log(PROC_MEDIAN), PROC_SIGMA)))
    return sorted(out)


def forced_windows(mode):
    if mode == "W1":
        return [(0.0, MONTH_S)]
    if mode == "W3":
        return [(d * DAY + 8 * 3600, d * DAY + 18 * 3600) for d in range(30) if d % 7 < 5]
    return []


def union(intervals):
    out = []
    for s, e in sorted(intervals):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def total(intervals):
    return sum(e - s for s, e in intervals)


def run(seed, per_day, mode, poll, cooldown, startup, offset):
    tick_ceil = lambda t: offset + math.ceil((t - offset) / poll) * poll
    tick_floor = lambda t: offset + math.floor((t - offset) / poll) * poll
    windows = forced_windows(mode)
    in_window = lambda t: next(((s, e) for s, e in windows if s <= t < e), None)
    sessions, lat, cold_lat = [], [], []
    cur = None

    def down(c):
        return max(c["forced_end"], tick_ceil(tick_floor(c["last_finish"]) + cooldown))

    for a, p in arrivals(seed, per_day):
        if cur is None or a >= down(cur):
            if cur is not None:
                sessions.append((cur["decision"], down(cur)))
            w = in_window(a)
            if w:
                cur = {"decision": w[0], "ready": w[0], "forced_end": w[1], "last_finish": w[0]}
            else:
                dec = tick_ceil(a)
                cur = {"decision": dec, "ready": dec + startup, "forced_end": -math.inf, "last_finish": dec}
        start = max(a, cur["ready"], cur["last_finish"])
        cur["last_finish"] = start + p
        lat.append(start + p - a)
        if a < cur["ready"]:
            cold_lat.append(start + p - a)
    if cur is not None:
        sessions.append((cur["decision"], down(cur)))
    return {"sessions": sessions, "windows": windows, "lat": lat, "cold_lat": cold_lat}


def costs(r, res, case, node_delay):
    """Monthly worker cost for the given case from the pod sessions and forced windows."""
    pod = union([(max(0.0, s), min(MONTH_S, e)) for s, e in res["sessions"]] + res["windows"])
    if case == "b2_fargate":
        v, g = fargate_provision(WORKER["vcpu"], WORKER["mem_gb"], "eks")
        hourly = v * r.pb.rate("AmazonEKS", "APN2-Fargate-vCPU-Hours:perCPU") + g * r.pb.rate("AmazonEKS", "APN2-Fargate-GB-Hours")
        secs = sum(max(60.0, e - s) for s, e in pod)
        return D(str(secs)) / 3600 * hourly, secs / 3600
    if case == "b1_node":
        node = union([(s, min(MONTH_S, e + node_delay)) for s, e in pod])
        secs = sum(max(60.0, e - s) for s, e in node)
        return D(str(secs)) / 3600 * r.pb.rate("AmazonEC2", "APN2-BoxUsage:t4g.medium"), secs / 3600
    return D(0), total(pod) / 3600  # case a: shared nodes, billed node count unchanged


def shared_nodes():
    need = lambda cpu, mem: max(math.ceil(cpu / SHARED["alloc_vcpu"]), math.ceil(mem / SHARED["alloc_mem_gib"]))
    w = need(SHARED["other_vcpu"] + WORKER["vcpu"], SHARED["other_mem_gib"] + WORKER["mem_gb"])
    wo = need(SHARED["other_vcpu"], SHARED["other_mem_gib"])
    return {"nodes_with_worker": w, "nodes_without_worker": wo,
            "note": "saving appears only if other workloads' CPU requests fall within 0.5 vCPU below a node boundary (k x 1.78 vCPU)"}


def stats(xs):
    if not xs:
        return {"n": 0, "mean_s": None, "max_s": None}
    return {"n": len(xs), "mean_s": round(sum(xs) / len(xs), 1), "max_s": round(max(xs), 1)}


def evaluate():
    r = Rates()
    start = measured_start()
    nodes = shared_nodes()
    m4 = lambda v: round(v, 4)
    results = {}
    for vol, per_day in VOLUMES.items():
        for pc_name, (poll, cooldown) in POLL_COOLDOWN.items():
            for case, startups in (("a_shared", {"base": start["warm_s"]}),
                                   ("b1_node", {k: v + start["cold_s"] for k, v in NODE_BOOT.items()}),
                                   ("b2_fargate", dict(FARGATE_START))):
                if pc_name != "base" and case != "b2_fargate" and case != "b1_node" and case != "a_shared":
                    continue
                for st_name, startup in startups.items():
                    if pc_name != "base" and st_name != "base":
                        continue
                    for mode in ("W1", "W2", "W3"):
                        per_seed = []
                        for seed in SEEDS:
                            offset = random.Random(f"off-{seed}").uniform(0, poll)
                            res = run(seed, per_day, mode, poll, cooldown, startup, offset)
                            delays = NODE_SCALE_DOWN_DELAY if case == "b1_node" else {"base": 0}
                            c = {dn: costs(r, res, case, dv) for dn, dv in delays.items()}
                            per_seed.append({"cost": c, "lat": stats(res["lat"]), "cold": stats(res["cold_lat"]),
                                             "sessions": len(res["sessions"])})
                        key = f"{vol}|{pc_name}|{case}|{st_name}|{mode}"
                        dn_keys = per_seed[0]["cost"].keys()
                        results[key] = {
                            "volume": vol, "poll_cooldown": [poll, cooldown], "case": case, "startup_s": startup, "mode": mode,
                            "monthly_usd": {dn: money(sum(p["cost"][dn][0] for p in per_seed) / len(per_seed)) for dn in dn_keys},
                            "monthly_usd_range": {dn: [money(min(p["cost"][dn][0] for p in per_seed)), money(max(p["cost"][dn][0] for p in per_seed))] for dn in dn_keys},
                            "billed_hours": {dn: m4(sum(p["cost"][dn][1] for p in per_seed) / len(per_seed)) for dn in dn_keys},
                            "latency_mean_s": round(sum(p["lat"]["mean_s"] for p in per_seed) / len(per_seed), 1),
                            "latency_max_s": max(p["lat"]["max_s"] for p in per_seed),
                            "cold_sheets": sum(p["cold"]["n"] for p in per_seed),
                            "cold_latency_mean_s": (round(sum(p["cold"]["mean_s"] * p["cold"]["n"] for p in per_seed if p["cold"]["n"]) /
                                                          max(1, sum(p["cold"]["n"] for p in per_seed)), 1) if any(p["cold"]["n"] for p in per_seed) else None),
                            "cold_latency_max_s": max((p["cold"]["max_s"] for p in per_seed if p["cold"]["n"]), default=None),
                            "scale_up_sessions_mean": round(sum(p["sessions"] for p in per_seed) / len(per_seed), 1),
                        }
    g = lambda vol, case, mode, st="base", pc="base": results[f"{vol}|{pc}|{case}|{st}|{mode}"]
    h2 = {vol: 1 - D(g(vol, "b2_fargate", "W2")["monthly_usd"]["base"]) / D(g(vol, "b2_fargate", "W1")["monthly_usd"]["base"]) for vol in VOLUMES}
    h3 = {vol: (g(vol, "b1_node", "W2")["cold_latency_mean_s"] or 0) / g(vol, "b1_node", "W1")["latency_mean_s"] for vol in VOLUMES}
    return {
        "pod_start": start, "shared_nodes": nodes, "worker": {k: str(v) for k, v in WORKER.items()},
        "assumptions": {"node_boot_s": NODE_BOOT, "fargate_start_s": FARGATE_START, "node_scale_down_delay_s": NODE_SCALE_DOWN_DELAY,
                        "processing": [PROC_MEDIAN, PROC_SIGMA], "poll_cooldown": POLL_COOLDOWN, "seeds": SEEDS},
        "results": results,
        "hypotheses": {
            "H1_shared_saving_zero": {"result": nodes["nodes_with_worker"] == nodes["nodes_without_worker"]
                                      and all(D(g(v, "a_shared", m)["monthly_usd"]["base"]) == 0 for v in VOLUMES for m in ("W2", "W3")),
                                      "nodes": [nodes["nodes_with_worker"], nodes["nodes_without_worker"]]},
            "H2_fargate_W2_saves_ge_50pct_small_medium": {"result": all(h2[v] >= D("0.5") for v in ("small", "medium")),
                                                          "saving_by_volume": {k: str(v.quantize(D("0.0001"))) for k, v in h2.items()}},
            "H3_node_W2_cold_latency_ge_3x_W1": {"result": all(v >= 3 for v in h3.values()),
                                                 "ratio_by_volume": {k: round(v, 2) for k, v in h3.items()}},
        },
    }


if __name__ == "__main__":
    emit(evaluate())
