"""Does lowering container requests lower the bill? Four runtimes, same service.

20 replicas of one web service. We lower the CPU request (memory fixed) and the
memory request (CPU fixed) step by step and compute the monthly cost on:
  eks_ec2     - EKS cluster + m7g.large nodes; nodes = what the requests need
                (CPU, memory and Pod slots after DaemonSets and CoreDNS)
  eks_fargate - EKS cluster + one Fargate Pod per replica (+256 MB, allowed combos);
                CoreDNS also runs as 2 Fargate Pods
  ecs_fargate - one Fargate task per replica (allowed combos)
  lambda      - same traffic as requests x duration x memory; container requests do not exist
"""
from decimal import Decimal as D
from pathlib import Path
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scenarios"))
from pricebook import HOURS_PER_MONTH, PriceBook, emit, load_scenario, money  # noqa: E402
from service_pack import INSTANCES, fargate_provision, max_pods  # noqa: E402

H = HOURS_PER_MONTH
REPLICAS = 20
NODE = "m7g.large"
# Assumptions (not verified this session): EKS AMI reservation and system Pods.
KUBE_RESERVED_CPU = D("0.07")                     # 6% of 1st core + 1% of 2nd
KUBE_RESERVED_MEM_GIB = (D(255) + D(11) * 29 + D(100)) / 1024  # 255Mi + 11Mi x maxPods + 100Mi eviction
DAEMONSETS = {"pods": 3, "cpu": D("0.15"), "mem_gib": D("0.2")}  # per node, total of 3 DaemonSet Pods
COREDNS = {"pods": 2, "cpu": D("0.1"), "mem_gib": D("0.07")}     # each
LAMBDA = {"memory_mb": 1024}

CPU_STEPS = ["1", "0.5", "0.4", "0.25", "0.2", "0.1", "0.05"]
MEM_STEPS = ["2", "1.5", "1", "0.75", "0.5", "0.25"]
SMALL_REPLICAS = 60


def eks_ec2_nodes(cpu, mem, replicas=REPLICAS):
    inst = INSTANCES[NODE]
    slots = max_pods(inst["enis"], inst["ips_per_eni"], int(inst["vcpu"])) - DAEMONSETS["pods"]
    alloc_cpu = inst["vcpu"] - KUBE_RESERVED_CPU - DAEMONSETS["cpu"]
    alloc_mem = inst["mem_gib"] - KUBE_RESERVED_MEM_GIB - DAEMONSETS["mem_gib"]
    pods = [(COREDNS["cpu"], COREDNS["mem_gib"])] * COREDNS["pods"] + [(cpu, mem)] * replicas
    nodes = []  # first-fit: [cpu_left, mem_left, slots_left]
    for c, m in pods:
        for n in nodes:
            if n[0] >= c and n[1] >= m and n[2] >= 1:
                n[0] -= c; n[1] -= m; n[2] -= 1
                break
        else:
            if c > alloc_cpu or m > alloc_mem:
                raise ValueError("pod larger than node")
            nodes.append([alloc_cpu - c, alloc_mem - m, slots - 1])
    total_cpu = sum(c for c, _ in pods)
    total_mem = sum(m for _, m in pods)
    lower = {"cpu": math.ceil(total_cpu / alloc_cpu), "mem": math.ceil(total_mem / alloc_mem), "slots": math.ceil(len(pods) / slots)}
    return len(nodes), {"slots_per_node_for_pods": slots, "alloc_cpu": str(alloc_cpu),
                        "alloc_mem_gib": str(alloc_mem.quantize(D("0.001"))), "lower_bound_nodes": lower,
                        "binding": max(lower, key=lower.get), "first_fit_nodes": len(nodes)}


def fargate_hourly(pb, vcpu, gb):
    return vcpu * pb.rate("AmazonECS", "APN2-Fargate-vCPU-Hours:perCPU") + gb * pb.rate("AmazonECS", "APN2-Fargate-GB-Hours")


def monthly(pb, cpu, mem, web, replicas=REPLICAS):
    cpu, mem = D(cpu), D(mem)
    cluster = pb.rate("AmazonEKS", "APN2-AmazonEKS-Hours:perCluster") * H
    n, info = eks_ec2_nodes(cpu, mem, replicas)
    ec2 = cluster + n * pb.rate("AmazonEC2", f"APN2-BoxUsage:{NODE}") * H
    ev, em = fargate_provision(cpu, mem, "eks")
    dv, dm = fargate_provision(COREDNS["cpu"], COREDNS["mem_gib"], "eks")
    eks_f = cluster + (replicas * fargate_hourly(pb, ev, em) + COREDNS["pods"] * fargate_hourly(pb, dv, dm)) * H
    cv, cm = fargate_provision(cpu, mem, "ecs")
    ecs_f = replicas * fargate_hourly(pb, cv, cm) * H
    gb_s = D(web["requests_per_month"]) * D(web["avg_ms_per_request"]) / 1000 * D(LAMBDA["memory_mb"]) / 1024
    lam = D(web["requests_per_month"]) * pb.rate("AWSLambda", "APN2-Request") + pb.tiered("AWSLambda", "APN2-Lambda-GB-Second", gb_s)
    return {"eks_ec2": ec2, "eks_fargate": eks_f, "ecs_fargate": ecs_f, "lambda": lam}, {
        "eks_ec2_nodes": n, "eks_ec2_packing": info,
        "eks_fargate_provisioned": [str(ev), str(em)], "ecs_fargate_provisioned": [str(cv), str(cm)]}


def sweep(pb, web, steps, fixed, axis, replicas=REPLICAS):
    rows = []
    for v in steps:
        cpu, mem = (v, fixed) if axis == "cpu" else (fixed, v)
        cost, detail = monthly(pb, cpu, mem, web, replicas)
        rows.append({"cpu": cpu, "mem_gb": mem, "usd": {k: money(x) for k, x in cost.items()}, **detail})
    resp = {}
    for rt in ("eks_ec2", "eks_fargate", "ecs_fargate", "lambda"):
        drops = sum(1 for a, b in zip(rows, rows[1:]) if D(b["usd"][rt]) < D(a["usd"][rt]))
        first, last = D(rows[0]["usd"][rt]), D(rows[-1]["usd"][rt])
        resp[rt] = {"steps": len(rows) - 1, "steps_with_cost_drop": drops,
                    "total_reduction": str(((first - last) / first).quantize(D("0.0001")))}
    return {"axis": axis, "fixed": fixed, "replicas": replicas, "rows": rows, "response": resp}


def evaluate():
    pb = PriceBook()
    web = load_scenario("web-llm-chatbot")["web"]
    cpu = sweep(pb, web, CPU_STEPS, "0.5", "cpu")
    mem = sweep(pb, web, MEM_STEPS, "0.25", "mem")
    small = sweep(pb, web, ["0.05", "0.04", "0.03", "0.02"], "0.1", "cpu", replicas=SMALL_REPLICAS)
    r = lambda s, rt: s["response"][rt]
    fargate_every_step = all(r(s, rt)["steps_with_cost_drop"] == r(s, rt)["steps"] for s in (cpu, mem) for rt in ("eks_fargate", "ecs_fargate"))
    fargate_any = all(r(s, rt)["steps_with_cost_drop"] > 0 for s in (cpu, mem) for rt in ("eks_fargate", "ecs_fargate"))
    ec2_half = all(r(s, "eks_ec2")["steps_with_cost_drop"] < r(s, "eks_ec2")["steps"] / 2 for s in (cpu, mem))
    lam_none = all(r(s, "lambda")["steps_with_cost_drop"] == 0 for s in (cpu, mem))
    return {
        "snapshot": pb.data["retrieved"], "replicas": REPLICAS, "node": NODE,
        "assumptions": {"kube_reserved_cpu": str(KUBE_RESERVED_CPU), "kube_reserved_mem_gib": str(KUBE_RESERVED_MEM_GIB.quantize(D("0.001"))),
                        "daemonsets_per_node": {k: str(v) for k, v in DAEMONSETS.items()}, "coredns": {k: str(v) for k, v in COREDNS.items()},
                        "lambda": LAMBDA, "traffic": {"requests_per_month": web["requests_per_month"], "avg_ms": web["avg_ms_per_request"]}},
        "cpu_sweep": cpu, "mem_sweep": mem, "small_pods_cpu_sweep": small,
        "hypotheses": {
            "H0_prompt_requests_down_cost_down_only_on_fargate": {
                "result": fargate_any and lam_none and ec2_half,
                "note": "EKS+EC2 also drops whenever the node count changes; Fargate drops only at allowed-combination boundaries; Lambda never"},
            "H1_fargate_cost_drops_at_every_request_step": {"result": fargate_every_step},
            "H2_eks_ec2_cost_changes_at_fewer_than_half_of_steps": {"result": ec2_half},
            "H3_lambda_cost_never_changes": {"result": lam_none},
            "H4_small_pods_eks_ec2_bound_by_slots_no_drop": {
                "result": all(r["eks_ec2_packing"]["binding"] == "slots" for r in small["rows"]) and r(small, "eks_ec2")["steps_with_cost_drop"] == 0},
        },
    }


if __name__ == "__main__":
    emit(evaluate())
