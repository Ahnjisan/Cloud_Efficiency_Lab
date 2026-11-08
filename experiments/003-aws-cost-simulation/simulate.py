"""Small EC2/EBS model using synthetic monthly rates and Decimal arithmetic."""
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

def amount(value):
    try:
        number = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("missing or invalid number") from error
    if not number.is_finite() or number < 0:
        raise ValueError("number must be finite and non-negative")
    return number

def total(lines):
    ids = [line["id"] for line in lines]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate cost line")
    return sum((amount(line["usd"]) for line in lines), Decimal(0))

def money(value):
    return str(value.quantize(Decimal("0.01")))

def estimate(config, rates):
    ec2 = config["compute"]
    month = amount(rates["month_hours"])
    hours = amount(ec2["hours"])
    od, sp, commitment = (amount(v) for v in (ec2["od"], ec2["sp"], config["commit"]))
    if not month or hours > month or not sp or sp > od:
        raise ValueError("unsupported time or rate")
    # shortcut: one instance and one plan; a real portfolio needs hourly eligible usage and priority.
    covered_fraction = min(commitment / sp, Decimal(1))
    ebs = Decimal(0)
    volume_ids = set()
    for volume in config["ebs"]:
        resource_id = volume.get("resource_id")
        if not isinstance(resource_id, str) or not resource_id.strip():
            raise ValueError("missing EBS resource ID")
        resource_id = resource_id.strip()
        if resource_id in volume_ids:
            raise ValueError("duplicate EBS resource ID")
        volume_ids.add(resource_id)
        if volume["type"] not in {"gp2", "gp3"}:
            raise ValueError("unsupported EBS type")
        iops, throughput = amount(volume["extra_iops"]), amount(volume["extra_mib_s"])
        if volume["type"] == "gp2" and (iops or throughput):
            raise ValueError("gp2 extras are unsupported")
        ebs += amount(volume["gib"]) * amount(volume["rate"])
        ebs += iops * amount(rates["extra_iops_rate"]) + throughput * amount(rates["extra_mib_s_rate"])
    amounts = {"commitment": month * commitment, "uncovered_ec2": hours * od * (1 - covered_fraction), "ebs": ebs}
    lines = [{"id": key, "usd": money(value)} for key, value in amounts.items()]
    return lines, total(lines)

def compare(before, after, rates):
    try:
        base_lines, base = estimate(before, rates)
    except (KeyError, ValueError) as error:
        return {"before": None, "after": None, "decision": "hold", "missing": str(error)}
    try:
        candidate_lines, candidate = estimate(after, rates)
    except (KeyError, ValueError) as error:
        return {"before": money(base), "after": None, "decision": "hold", "missing": str(error)}
    try:
        jobs = [amount(config["jobs"]) for config in (before, after)]
    except (KeyError, ValueError):
        return {"before": money(base), "after": money(candidate), "decision": "hold", "missing": "invalid workload quantity"}
    comparable = jobs[0] == jobs[1] and jobs[0] > 0
    savings = base - candidate
    return {
        "before": money(base), "after": money(candidate),
        "before_lines": base_lines, "after_lines": candidate_lines,
        "difference": money(savings),
        "savings_rate": str((savings / base).quantize(Decimal("0.0001"))) if base and comparable else None,
        "usd_per_1000_jobs": [money(cost * 1000 / job) if job else None for cost, job in zip((base, candidate), jobs)],
        "same_work": comparable,
        "decision": "hold" if not comparable or after.get("quality") != "pass" else ("candidate" if savings > 0 else "retain"),
    }

def main():
    data = json.loads(Path(__file__).with_name("scenarios.json").read_text(encoding="utf-8"))
    results = {}
    for case in data["cases"]:
        result = compare(case["before"], case["after"], data)
        assert {key: result[key] for key in case["expected"]} == case["expected"], result
        if "terraform_address" in case:
            result["cost_basis"] = {
                "resource_id": case["terraform_address"],
                "before": {"instance_type": case["before"]["compute"]["type"]},
                "after": {"instance_type": case["after"]["compute"]["type"]},
            }
        results[case["id"]] = result
    assert results["D-different-work"]["usd_per_1000_jobs"] == ["152.00", "76.00"]
    assert results["A-compute"]["savings_rate"] == "0.5000"
    assert results["B-ebs-retained"]["after_lines"][-1]["usd"] == "8.00"
    baseline = data["cases"][0]["before"]
    with_ebs = data["cases"][1]["before"]
    volume = with_ebs["ebs"][0]
    repeated = compare(with_ebs, {**with_ebs, "ebs": [volume, volume]}, data)
    assert repeated == {"before": "152.00", "after": None, "decision": "hold", "missing": "duplicate EBS resource ID"}
    unidentified = compare(with_ebs, {**with_ebs, "ebs": [{**volume, "resource_id": None}]}, data)
    assert unidentified["after"] is None and unidentified["missing"] == "missing EBS resource ID"
    distinct = {**with_ebs, "ebs": [volume, {**volume, "resource_id": "vol-other"}]}
    assert estimate(distinct, data)[1] == Decimal("160.00")
    assert estimate({**baseline, "commit": "0.06"}, data)[1] == Decimal("115.20")
    assert compare(baseline, {**baseline, "jobs": None}, data)["decision"] == "hold"
    assert compare({**baseline, "compute": {**baseline["compute"], "hours": -1}}, baseline, data)["before"] is None
    for invalid in (-1, None, "NaN"):
        try:
            amount(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid number accepted")
    try:
        total([{"id": "ec2", "usd": "1"}] * 2)
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate counted")
    print(json.dumps({"scenarios": results, "checks": "invalid numbers, missing or duplicate EBS IDs, and duplicate cost rows rejected"}, indent=2))

if __name__ == "__main__":
    main()
