"""Read-only InfraFit assessment of local synthetic inputs."""
import argparse
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent / "experiments"
RECONCILIATION = EXPERIMENTS / "008-evidence-reconciliation"
PLAN_EXPERIMENT = EXPERIMENTS / "004-terraform-evidence"
LABELS = {"candidate": "변경 검토 후보", "keep": "유지", "hold": "판단 보류"}
REASONS = {
    "change-address-ambiguous": "같은 Terraform 주소에 변경 기록이 여러 건 있습니다.",
    "billing-conflict": "같은 청구 행 ID의 내용이 충돌합니다.",
    "billing-line-id-missing": "해당 자원의 청구 행 ID가 누락되거나 유효하지 않습니다.",
    "billing-unmatched": "해당 자원과 기간의 청구 행이 없습니다.",
    "candidate-config-missing": "후보 구성 ID가 없습니다.",
    "candidate-cost-missing": "후보의 가상 비용 근거가 없습니다.",
    "peak-unmatched-or-ambiguous": "후보 구성과 기간에 일치하는 피크 관측이 하나로 확정되지 않았습니다.",
    "invalid-peak-p99": "피크 p99 값이 유효하지 않습니다.",
    "plan-missing": "일치하는 Terraform Plan 주소가 없습니다.",
    "plan-ambiguous": "Terraform Plan 주소가 중복됩니다.",
    "plan-not-supported": "지원 범위에 해당하는 EC2·EBS 갱신 계획이 아닙니다.",
    "plan-evidence-unavailable": "Plan의 비용 관련 구성 값이 미확정·민감 또는 누락 상태입니다.",
    "configuration-mismatch": "청구·관측의 후보 구성과 Plan의 변경 전후 구성을 연결할 근거가 없습니다.",
    "cost-configuration-unchanged": "Plan의 비용 관련 구성이 변경 전후 동일합니다.",
    "lower-cost-within-peak-limit": "가상 비용이 감소하고 피크 p99 기준을 충족합니다.",
    "peak-limit-exceeded": "피크 p99가 기준을 초과했습니다.",
    "no-modeled-cost-reduction": "가상 비용이 줄지 않습니다.",
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def assess(billing, changes, peaks, plans, basis, as_of, window):
    parser = run_path(str(PLAN_EXPERIMENT / "analyze.py"))
    engine = run_path(str(RECONCILIATION / "reconcile.py"))
    plan_rows = {}
    duplicate_addresses = set()
    unverified_unknown_masks = set()
    for plan in plans:
        for item in plan["resource_changes"]:
            mask = item["change"].get("after_unknown")
            if not isinstance(mask, (dict, bool)) or not parser["valid_mask"](mask):
                unverified_unknown_masks.add(item["address"])
        for row in parser["analyze"](plan):
            address = row["address"]
            if address in plan_rows or row["status"] == "duplicate-hold":
                duplicate_addresses.add(address)
            plan_rows[address] = row

    scoped = [change for change in changes if change["window"] == window]
    changes_by_address = defaultdict(list)
    for change in scoped:
        changes_by_address[change["address"]].append(change)
        value = change.get("candidate")
        if engine["missing_candidate_cost"](value):
            continue
        if not isinstance(value, str) or not Decimal(value).is_finite() or Decimal(value) < 0:
            raise ValueError("candidate amounts must be finite nonnegative decimal strings")
    for row in billing:
        if row["window"] != window or row["arrived"] > as_of:
            continue
        if not engine["valid_billing_line_id"](row.get("line_id")):
            continue
        if not isinstance(row["amount"], str) or not Decimal(row["amount"]).is_finite():
            raise ValueError("amounts must be finite decimal strings")

    joined = engine["reconcile"](billing, scoped, peaks, as_of, window)
    decisions = []
    for address, evidence in joined["decisions"].items():
        changes_for_address = changes_by_address[address]
        change = changes_for_address[0] if len(changes_for_address) == 1 else {}
        plan = plan_rows.get(address)
        plan_status = plan["status"] if plan else None
        plan_reason = None
        configurations = None
        if address in duplicate_addresses:
            plan_reason = "plan-ambiguous"
        elif plan is None:
            plan_reason = "plan-missing"
        elif plan["action"] != "update" or plan_status == "unsupported":
            plan_reason = "plan-not-supported"
        elif plan_status != "extracted" or address in unverified_unknown_masks:
            plan_status = "hold"
            plan_reason = "plan-evidence-unavailable"
        else:
            configurations = {side: plan[side]["values"] for side in ("before", "after")}
            expected_basis = {key: change.get(key) for key in ("resource", "window", "candidate_config")}
            if basis.get(address) != {**expected_basis, **configurations}:
                plan_reason = "configuration-mismatch"
            elif configurations["before"] == configurations["after"]:
                plan_reason = "cost-configuration-unchanged"

        status = "hold" if plan_reason else evidence["decision"]
        reasons = [reason for reason in (evidence.get("reason"), plan_reason) if reason]
        if status != "hold":
            if evidence["p99_ms"] > engine["PEAK_P99_LIMIT_MS"]:
                reasons.append("peak-limit-exceeded")
            elif status == "candidate":
                reasons.append("lower-cost-within-peak-limit")
            else:
                reasons.append("no-modeled-cost-reduction")
        costs = None
        if status != "hold":
            costs = {key: evidence[key] for key in ("baseline", "candidate")}
            costs["difference"] = str(Decimal(costs["baseline"]) - Decimal(costs["candidate"]))
        decisions.append({
            "address": address, "resource": change.get("resource"), "candidate_config": change.get("candidate_config"),
            "decision": status, "label": LABELS[status], "reasons": reasons,
            "plan_status": plan_status, "plan_configuration": configurations if not plan_reason else None,
            "modeled_usd": costs, "peak_p99_ms": evidence.get("p99_ms") if not plan_reason else None,
        })
    return {"data_kind": "synthetic", "actual_billing_reconciliation": "unverified",
            "window": window, "as_of": as_of, "peak_p99_limit_ms": engine["PEAK_P99_LIMIT_MS"],
            "unresolved_billing_lines": joined["unresolved_billing_lines"],
            "unassigned_missing_id_rows": joined.get("unassigned_missing_id_rows", 0), "decisions": decisions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("billing", "changes", "peaks"):
        parser.add_argument(f"--{name}", type=Path, default=RECONCILIATION / f"{name}.json")
    parser.add_argument("--plan", nargs="+", type=Path,
                        default=[PLAN_EXPERIMENT / "plan.json", HERE / "worker-plan.json"])
    parser.add_argument("--basis", type=Path, default=HERE / "config-basis.json")
    parser.add_argument("--window", default="peak-01")
    parser.add_argument("--as-of", type=int, default=2)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        report = assess(read(args.billing), read(args.changes), read(args.peaks), [read(p) for p in args.plan],
                        read(args.basis), args.as_of, args.window)
    except (OSError, ValueError, InvalidOperation, KeyError, TypeError):
        parser.error("invalid or unreadable input; see the InfraFit input contract")
    if args.as_json:
        print(json.dumps(report, indent=2))
        return
    print(f"InfraFit | 가상 입력 | {args.window} / 평가 시점 {args.as_of}")
    for row in report["decisions"]:
        print(f"{row['address']} | {row['label']}")
        for reason in row["reasons"]:
            print(f"  - {REASONS[reason]}")
        if row["modeled_usd"]:
            costs = row["modeled_usd"]
            print(f"  - 가상 USD {costs['baseline']} → {costs['candidate']} | p99 {row['peak_p99_ms']} ms")
    if report["unassigned_missing_id_rows"]:
        print(f"행 ID와 자원 ID를 확인할 수 없는 청구 행: {report['unassigned_missing_id_rows']}건 (비용 집계 제외)")
    print("실제 청구 대사: 미검증")


if __name__ == "__main__":
    main()
