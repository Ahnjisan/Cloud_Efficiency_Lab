"""Billing-unit facts per service ("service pack") used by experiments 026-036.

Each entry records the metering unit and minimum that turn real usage into
billed usage. Sources and check date are in experiments/scenarios/README.md and
the study notes. Values marked "unconfirmed" are not official rules.
"""
from decimal import Decimal, ROUND_CEILING

D = Decimal

UNITS = {
    "iot_message": {"unit": D(5120), "minimum": D(0), "measure": "bytes", "basis": "official; 5 KB byte definition unconfirmed (5000 or 5120)"},
    "firehose_record": {"unit": D(5120), "minimum": D(0), "measure": "bytes", "basis": "official (5 KB increments)"},
    "websocket_message": {"unit": D(32768), "minimum": D(0), "measure": "bytes", "basis": "official (32 KB increments)"},
    "http_api_request": {"unit": D(524288), "minimum": D(0), "measure": "bytes", "basis": "pricing-page example only"},
    "guardrails_text_unit": {"unit": D(1000), "minimum": D(0), "measure": "characters", "basis": "official (up to 1,000 characters)"},
    "fargate_linux_seconds": {"unit": D(1), "minimum": D(60), "measure": "seconds", "basis": "official (per second, 1-minute minimum)"},
    "lambda_duration_ms": {"unit": D(1), "minimum": D(1), "measure": "milliseconds", "basis": "official (1 ms rounding)"},
    "node_hour": {"unit": D(3600), "minimum": D(3600), "measure": "seconds", "basis": "official for ElastiCache nodes, NAT gateway, VPC endpoint (partial hour = full hour)"},
    "athena_scan": {"unit": D(1048576), "minimum": D(10485760), "measure": "bytes", "basis": "official (MB rounding, 10 MB minimum per query)"},
    "elasticache_ecpu": {"unit": D(1024), "minimum": D(1024), "measure": "bytes", "basis": "official 1 ECPU per KB; rounding of partial KB unconfirmed"},
}


def ceil_div(x, unit):
    return (D(x) / D(unit)).to_integral_value(rounding=ROUND_CEILING)


def billed(x, unit, minimum=0):
    """Billed quantity = max(minimum, ceil(x / unit) * unit). x = 0 bills 0 (nothing happened)."""
    x = D(x)
    if x == 0:
        return D(0)
    return max(D(minimum), ceil_div(x, unit) * D(unit))


def billed_units(kind, x):
    u = UNITS[kind]
    return billed(x, u["unit"], u["minimum"]) / u["unit"]


# Fargate allowed vCPU / memory (GB) combinations.
def _r(a, b, step):
    out, v = [], D(a)
    while v <= D(b):
        out.append(v)
        v += D(step)
    return out


FARGATE_COMBOS = [
    (D("0.25"), [D("0.5"), D(1), D(2)]),
    (D("0.5"), _r(1, 4, 1)),
    (D(1), _r(2, 8, 1)),
    (D(2), _r(4, 16, 1)),
    (D(4), _r(8, 30, 1)),
    (D(8), _r(16, 60, 4)),
    (D(16), _r(32, 120, 8)),
]
ECS_ONLY_COMBOS = [(D(32), [D(60), D(120), D(244)])]
EKS_POD_OVERHEAD_GB = D("0.25")


def fargate_provision(vcpu, mem_gb, platform="ecs"):
    """Smallest allowed combination covering the request. EKS adds 256 MB first."""
    vcpu, mem = D(str(vcpu)), D(str(mem_gb))
    if platform == "eks":
        mem += EKS_POD_OVERHEAD_GB
    combos = FARGATE_COMBOS + (ECS_ONLY_COMBOS if platform == "ecs" else [])
    for cpu, mems in combos:
        if cpu < vcpu:
            continue
        for m in mems:
            if m >= mem:
                return cpu, m
    raise ValueError(f"no Fargate combination for {vcpu} vCPU / {mem} GB on {platform}")


def max_pods(enis, ips_per_eni, vcpus, mode="managed"):
    """VPC CNI default (no prefix delegation)."""
    if mode == "auto":
        return min(110, enis * (ips_per_eni - 1))
    raw = enis * (ips_per_eni - 1) + 2
    if mode == "managed":
        return min(raw, 110 if vcpus < 30 else 250)
    return raw


# Instance facts used for packing (EC2 docs, checked 2026-11-15).
INSTANCES = {
    "m7g.large": {"vcpu": D(2), "mem_gib": D(8), "enis": 3, "ips_per_eni": 10},
    "m5.large": {"vcpu": D(2), "mem_gib": D(8), "enis": 3, "ips_per_eni": 10},
}
