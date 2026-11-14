"""Always-on fixed costs in a dev environment and what a work-hours schedule can remove.

Scenario 2 (web service + internal chatbot) run as a dev environment. Each fixed
resource is classified by how it can stop billing:
  stoppable      - stop/start keeps the resource (RDS: max 7 days, then auto-start)
  scale_to_zero  - service scales capacity to 0 (ECS service desired count 0)
  delete_only    - no stop; billing ends only on delete (NAT, OpenSearch domain/Classic collection, serverless cache)
"""
from decimal import Decimal as D
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scenarios"))
from pricebook import HOURS_PER_MONTH, PriceBook, emit, load_scenario, money  # noqa: E402
from service_pack import fargate_provision  # noqa: E402

H = HOURS_PER_MONTH


def components(pb, s, opensearch="classic"):
    w, c, n = s["web"], s["chatbot"], s["network"]
    fv, fm = fargate_provision(w["service"]["vcpu"], w["service"]["mem_gb"], "ecs")
    task_hour = fv * pb.rate("AmazonECS", "APN2-Fargate-vCPU-Hours:perCPU") + fm * pb.rate("AmazonECS", "APN2-Fargate-GB-Hours")
    db = w["db"]
    inst = pb.rate("AmazonRDS", f"APN2-InstanceUsage:{db['class']}", databaseEngine=db["engine"])
    cache = w["cache"]
    min_gb = D("0.1") if cache["engine"] == "Valkey" else D(1)
    cache_gb = max(min_gb, D(str(cache["data_gb"])))
    ocu = pb.rate("AmazonES", "APN2-IndexingOCU")
    items = [
        {"name": "NAT gateway", "kind": "delete_only", "hourly": pb.rate("AmazonEC2", "APN2-NatGateway-Hours") * n["nat_gateways"], "fixed_month": D(0)},
        {"name": "ECS Fargate service", "kind": "scale_to_zero", "hourly": task_hour * w["service"]["tasks"], "fixed_month": D(0)},
        {"name": "RDS instance", "kind": "stoppable", "hourly": inst, "fixed_month": D(0)},
        {"name": "RDS gp3 storage", "kind": "stays_billed", "hourly": D(0),
         "fixed_month": D(db["storage_gb"]) * pb.rate("AmazonRDS", "APN2-RDS:GP3-Storage", databaseEngine=db["engine"])},
        {"name": f"ElastiCache serverless {cache['engine']} (minimum storage)", "kind": "delete_only",
         "hourly": cache_gb * pb.rate("AmazonElastiCache", f"APN2-CachedData:{cache['engine']}"), "fixed_month": D(0)},
    ]
    if opensearch == "classic":
        items.append({"name": "OpenSearch Serverless Classic (minimum 2 OCU)", "kind": "delete_only", "hourly": 2 * ocu, "fixed_month": D(0)})
    else:  # NextGen: scales to zero after 10 idle minutes; same OCU rate assumed (unconfirmed)
        items.append({"name": "OpenSearch Serverless NextGen (2 OCU while used)", "kind": "scale_to_zero", "hourly": 2 * ocu, "fixed_month": D(0)})
    return items


def month_cost(items, run_hours, rds_hours=None):
    total = D(0)
    rows = []
    for it in items:
        hours = H
        if it["kind"] == "scale_to_zero":
            hours = run_hours
        elif it["kind"] == "stoppable":
            hours = run_hours if rds_hours is None else rds_hours
        cost = it["hourly"] * hours + it["fixed_month"]
        rows.append({"name": it["name"], "kind": it["kind"], "hours": str(hours), "usd": money(cost)})
        total += cost
    return total, rows


def evaluate():
    pb = PriceBook()
    s = load_scenario("web-llm-chatbot")
    sch = s["schedule"]
    work = D(sch["weekday_hours"] * sch["weekdays_per_month"])
    # Stop once and forget: RDS auto-starts after 7 days and runs the rest of the month.
    forgot = H - D(7 * 24)
    out = {}
    for variant in ("classic", "nextgen"):
        items = components(pb, s, variant)
        always, rows_a = month_cost(items, H)
        sched, rows_s = month_cost(items, work)
        forget, _ = month_cost(items, work, rds_hours=forgot)
        by_kind = {}
        for it in items:
            by_kind[it["kind"]] = by_kind.get(it["kind"], D(0)) + it["hourly"] * H + it["fixed_month"]
        out[variant] = {
            "always_on_usd": money(always), "work_hours_schedule_usd": money(sched),
            "schedule_saving_ratio": str(((always - sched) / always).quantize(D("0.0001"))),
            "schedule_but_rds_stopped_once_usd": money(forget),
            "always_on_by_kind_usd": {k: money(v) for k, v in by_kind.items()},
            "rows_always_on": rows_a, "rows_schedule": rows_s}
    c = out["classic"]
    ro = rds_only(pb, s, work, forgot)
    return {
        "snapshot": pb.data["retrieved"], "work_hours_per_month": str(work), "hours_per_month": str(H),
        "variants": out,
        "hypotheses": {
            "H1_schedule_saves_less_than_40pct_with_classic_vector_store": {
                "result": D(c["schedule_saving_ratio"]) < D("0.40"), "saving_ratio": c["schedule_saving_ratio"]},
            "H2_delete_only_items_exceed_half_of_always_on": {
                "result": D(c["always_on_by_kind_usd"]["delete_only"]) > D(c["always_on_usd"]) / 2,
                "delete_only_usd": c["always_on_by_kind_usd"]["delete_only"], "always_on_usd": c["always_on_usd"]},
            "H3_forgotten_rds_stop_keeps_less_than_half_of_rds_saving": {
                "result": D(ro["saving_kept_ratio"]) < D("0.5"), "rds_only": ro},
        },
    }


def rds_only(pb, s, work, forgot):
    db = s["web"]["db"]
    inst = pb.rate("AmazonRDS", f"APN2-InstanceUsage:{db['class']}", databaseEngine=db["engine"])
    always, sched, forget = inst * H, inst * work, inst * forgot
    return {"always_usd": money(always), "schedule_usd": money(sched), "stopped_once_usd": money(forget),
            "saving_kept_ratio": str(((always - forget) / (always - sched)).quantize(D("0.0001")))}


if __name__ == "__main__":
    emit(evaluate())
