"""Propose Terraform address -> cloud resource ID links from `terraform show -json` (read-only).

Design: experiments/terraform-state-linking-plan.md. Reads a state representation
(`terraform show -json` after apply, or the `prior_state` of a plan JSON) and keeps
only address, mode, type and values.id of managed resources. No other attribute is
read into the output, so secrets stored in state cannot be printed. An id marked in
sensitive_values is skipped. With --changes, each change's resource ID is compared
with the state's ID for the same address.

The links are candidates for config-basis.json; they are not applied automatically.
"""
import argparse
import json
from pathlib import Path
import sys


def _state_values(doc):
    if isinstance(doc.get("values"), dict):
        return doc["values"], "state"
    prior = doc.get("prior_state")
    if isinstance(prior, dict) and isinstance(prior.get("values"), dict):
        return prior["values"], "plan.prior_state"
    return None, None


def _walk(module):
    for r in module.get("resources") or []:
        if isinstance(r, dict):
            yield r
    for child in module.get("child_modules") or []:
        if isinstance(child, dict):
            yield from _walk(child)


def links_from_state(doc):
    values, source = _state_values(doc if isinstance(doc, dict) else {})
    warnings = []
    if values is None:
        return {"source": None, "links": {}, "warnings": [{"code": "no-state-values", "address": None}]}
    links = {}
    for r in _walk(values.get("root_module") or {}):
        address = r.get("address")
        if not isinstance(address, str):
            warnings.append({"code": "address-missing", "address": None})
            continue
        if r.get("mode") != "managed":
            continue
        if (r.get("sensitive_values") or {}).get("id") is True:
            warnings.append({"code": "id-sensitive", "address": address})
            continue
        rid = (r.get("values") or {}).get("id")
        if not isinstance(rid, str) or not rid:
            warnings.append({"code": "id-missing", "address": address})
            continue
        if address in links:
            warnings.append({"code": "address-duplicate", "address": address})
            links[address] = None
            continue
        links[address] = {"resource": rid, "type": r.get("type")}
    duplicates = [a for a, v in links.items() if v is None]
    for a in duplicates:
        del links[a]
    return {"source": source, "links": dict(sorted(links.items())), "warnings": warnings}


def compare(links, changes):
    """Compare change rows (008 format) with state links by address."""
    rows, seen = [], set()
    for c in changes:
        address = c.get("address")
        seen.add(address)
        link = links.get(address)
        if link is None:
            status = "address-not-in-state"
        elif link["resource"] == c.get("resource"):
            status = "match"
        else:
            status = "mismatch"
        rows.append({"address": address, "change_resource": c.get("resource"),
                     "state_resource": link["resource"] if link else None, "status": status})
    rows += [{"address": a, "change_resource": None, "state_resource": v["resource"], "status": "state-only"}
             for a, v in links.items() if a not in seen]
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("state", type=Path, help="output of `terraform show -json` (or a plan JSON with prior_state)")
    p.add_argument("--changes", type=Path, help="008-format change rows to check against the state")
    args = p.parse_args(argv)
    try:
        doc = json.loads(args.state.read_text(encoding="utf-8"))
        changes = json.loads(args.changes.read_text(encoding="utf-8")) if args.changes else None
    except (OSError, ValueError):
        p.error("unreadable input")
    result = links_from_state(doc)
    if changes is not None:
        result["comparison"] = compare(result["links"], changes)
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
