"""Normalize a documented subset of synthetic Terraform plan JSON."""
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

FIELDS = {
    "aws_instance": ("instance_type",),
    "aws_ebs_volume": ("type", "size", "iops", "throughput"),
}
ACTIONS = {
    ("no-op",): "no-op", ("create",): "create", ("update",): "update",
    ("delete",): "delete", ("delete", "create"): "replace",
    ("create", "delete"): "replace",
}

def valid_mask(mask):
    if isinstance(mask, dict):
        return all(valid_mask(value) for value in mask.values())
    if isinstance(mask, list):
        return all(valid_mask(value) for value in mask)
    return type(mask) is bool

def fields(values, sensitive, unknown, supported):
    output, unavailable = {}, {}
    values = values if isinstance(values, dict) else {}
    if values and (not isinstance(sensitive, (dict, bool)) or not valid_mask(sensitive)):
        return {"values": {}, "unavailable": dict.fromkeys(supported, "sensitivity-unverified")}
    for key in supported:
        for mask, reason in ((sensitive, "sensitive"), (unknown, "unknown")):
            # A nonempty nested mask is treated conservatively for the selected scalar.
            if mask is True or (isinstance(mask, dict) and mask.get(key)):
                unavailable[key] = reason
                break
        else:
            value = values.get(key)
            if type(value) in (str, int) and value != "":
                output[key] = value
            else:
                unavailable[key] = "missing"
    return {"values": output, "unavailable": unavailable}

def analyze(plan):
    if plan.get("format_version") not in {"1.0", "1.1", "1.2"}:
        raise ValueError("unsupported JSON format version")
    changes = plan["resource_changes"]
    addresses = Counter(item["address"] for item in changes)
    results = []
    for item in changes:
        address, resource = item["address"], item["type"]
        change = item["change"]
        action = ACTIONS.get(tuple(change["actions"]), "unsupported")
        row = {"address": address, "type": resource, "action": action}
        if addresses[address] > 1:
            if not any(result["address"] == address for result in results):
                results.append({**row, "status": "duplicate-hold"})
            continue
        if resource not in FIELDS or item["provider_name"] != "registry.terraform.io/hashicorp/aws" or action == "unsupported" or item.get("mode") != "managed":
            results.append({**row, "status": "unsupported"})
            continue
        supported = FIELDS[resource]
        for side, inactive in (("before", action == "create"), ("after", action == "delete")):
            if not inactive:
                row[side] = fields(change.get(side), change.get(side + "_sensitive"), change.get("after_unknown") if side == "after" else None, supported)
        results.append({**row, "status": "hold" if any(row[side]["unavailable"] for side in ("before", "after") if side in row) else "extracted"})
    return results

def main():
    plan = json.loads(Path(__file__).with_name("plan.json").read_text(encoding="utf-8"))
    rows = analyze(plan)
    lookup = {row["address"]: row for row in rows}
    assert len(rows) == 10 and len(lookup) == 10
    assert lookup["aws_instance.orders"]["after"]["values"]["instance_type"] == "model.medium"
    assert lookup["aws_ebs_volume.new"]["after"]["values"]["size"] == 100
    assert lookup["aws_ebs_volume.old"]["action"] == "delete" and "after" not in lookup["aws_ebs_volume.old"]
    assert lookup["aws_instance.same"]["action"] == "no-op"
    assert lookup["aws_instance.replace"]["action"] == lookup["aws_instance.replace_first"]["action"] == "replace"
    assert lookup["aws_s3_bucket.unsupported"]["status"] == "unsupported"
    assert lookup["aws_ebs_volume.unknown"]["after"]["unavailable"]["size"] == "unknown"
    assert lookup["aws_instance.masked"]["before"]["unavailable"]["instance_type"] == "sensitive"
    assert lookup["aws_instance.masked"]["after"]["unavailable"]["instance_type"] == "sensitive"
    assert lookup["aws_ebs_volume.duplicate"]["status"] == "duplicate-hold"
    assert "fixture-mask" not in json.dumps(rows)
    for replacement in (None, {"instance_type": "false"}):
        modified = deepcopy(plan)
        masked = next(row for row in modified["resource_changes"] if row["address"] == "aws_instance.masked")
        if replacement is None:
            del masked["change"]["after_sensitive"]
        else:
            masked["change"]["after_sensitive"] = replacement
        result = next(row for row in analyze(modified) if row["address"] == "aws_instance.masked")
        assert result["status"] == "hold"
        assert result["after"] == {"values": {}, "unavailable": {"instance_type": "sensitivity-unverified"}}
        assert "fixture-mask" not in json.dumps(result)
    try:
        analyze({**plan, "format_version": "2.0"})
    except ValueError:
        pass
    else:
        raise AssertionError("unsupported version accepted")
    print(json.dumps({"rows": rows, "drift_records_not_analyzed": len(plan.get("resource_drift", []))}, indent=2))

if __name__ == "__main__":
    main()
