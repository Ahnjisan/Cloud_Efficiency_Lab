"""Check a small static resource model. This script never calls kubectl."""
import json
from decimal import Decimal
from pathlib import Path

def quantity(value, suffix):
    if not isinstance(value, str) or not value.endswith(suffix) or not value[:-len(suffix)].isdigit():
        raise ValueError(f"only integer {suffix} fixtures are supported")
    return int(value[:-len(suffix)])

def resources(pod):
    containers = pod["spec"]["containers"]
    assert pod["kind"] == "Pod" and len(containers) == 1
    values = containers[0]["resources"]
    pairs = [tuple(quantity(values[side][key], unit) for key, unit in (("cpu", "m"), ("memory", "Mi"))) for side in ("requests", "limits")]
    if any(request > limit for request, limit in zip(*pairs)):
        raise ValueError("request exceeds limit")
    return pairs

def placement(requests, capacity, nodes):
    remaining = [capacity for _ in range(nodes)]

    def put(index):
        if index == len(requests):
            return []
        cpu, mem = requests[index]
        for node, (free_cpu, free_mem) in enumerate(remaining):
            if cpu <= free_cpu and mem <= free_mem:
                remaining[node] = (free_cpu - cpu, free_mem - mem)
                tail = put(index + 1)
                remaining[node] = (free_cpu, free_mem)
                if tail is not None:
                    return [node + 1, *tail]
        return None

    return put(0)

def main():
    pods = json.loads(Path(__file__).with_name("pods.json").read_text(encoding="utf-8"))["items"]
    capacities = [
        {"name": "small", "capacity": [2000, 4096], "allocatable": [1800, 3072], "usd_per_hour": "0.12"},
        {"name": "large", "capacity": [4000, 8192], "allocatable": [3600, 7168], "usd_per_hour": "0.22"},
    ]
    results = {}
    for pod in pods:
        request, limit = resources(pod)
        scenarios = {}
        for node in capacities:
            cap = tuple(node["allocatable"])
            assert all(a <= b for a, b in zip(cap, node["capacity"]))
            fits_one = placement([request] * 4, cap, 1)
            fits_two = placement([request] * 4, cap, 2)
            count = 1 if fits_one is not None else 2 if fits_two is not None else None
            scenarios[node["name"]] = {
                "fits_on_one": fits_one, "fits_on_two": fits_two, "minimum_of_tested": count,
                "estimated_usd_720h": str((Decimal(node["usd_per_hour"]) * count * 720).quantize(Decimal(".01"))) if count else None,
            }
        results[pod["metadata"]["name"]] = {"request": request, "limit": limit, "scenarios": scenarios}
    assert results["baseline"]["scenarios"]["small"]["fits_on_one"] is None
    assert results["baseline"]["scenarios"]["small"]["minimum_of_tested"] == 2
    assert results["candidate"]["scenarios"]["small"]["minimum_of_tested"] == 1
    assert results["baseline"]["scenarios"]["large"]["estimated_usd_720h"] == results["candidate"]["scenarios"]["large"]["estimated_usd_720h"] == "158.40"
    assert results["candidate"]["scenarios"] == results["candidate-cpu-cap"]["scenarios"]
    assert placement([(100, 4000)], (1800, 3072), 2) is None
    print(json.dumps({"kind": "synthetic-static", "nodes": capacities, "replicas": 4, "pods": results}, indent=2))

if __name__ == "__main__":
    main()
