"""NAT gateway vs VPC endpoints: break-even traffic and scenario 2 decision.

Per service the choice is: keep traffic on NAT (per-GB processing), add interface
endpoints (hourly per endpoint per AZ + per-GB), or use a gateway endpoint
(S3/DynamoDB, no charge). The NAT gateway's own hourly charge stays while any
internet traffic remains, so it is compared separately.
"""
from decimal import Decimal as D
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scenarios"))
from pricebook import HOURS_PER_MONTH, PriceBook, emit, load_scenario, money  # noqa: E402

# Interface endpoints a service needs (assumption from service docs; ECR modelled as api + dkr).
ENDPOINTS = {"ecr": 2, "cloudwatch_logs": 1, "bedrock_runtime": 1, "s3": 1}
GATEWAY_CAPABLE = {"s3"}


def rates(pb):
    return {"nat_hour": pb.rate("AmazonEC2", "APN2-NatGateway-Hours"),
            "nat_gb": pb.rate("AmazonEC2", "APN2-NatGateway-Bytes"),
            "ep_hour": pb.rate("AmazonVPC", "APN2-VpcEndpoint-Hours"),
            "ep_gb": pb.rate("AmazonVPC", "APN2-VpcEndpoint-Bytes")}


def break_even_gb(r, endpoints=1, azs=2):
    fixed = r["ep_hour"] * endpoints * azs * HOURS_PER_MONTH
    return fixed / (r["nat_gb"] - r["ep_gb"])


def service_costs(r, gb, endpoints, azs, gateway):
    gb = D(gb)
    out = {"nat": gb * r["nat_gb"],
           "interface_endpoint": r["ep_hour"] * endpoints * azs * HOURS_PER_MONTH + gb * r["ep_gb"]}
    if gateway:
        out["gateway_endpoint"] = D(0)
    return out


def evaluate():
    pb = PriceBook()
    r = rates(pb)
    s = load_scenario("web-llm-chatbot")["network"]
    azs = s["azs"]
    table = {}
    for n_ep in (1, 2, 3):
        table[f"{n_ep}_endpoints"] = {f"{a}_az": str(break_even_gb(r, n_ep, a).quantize(D("0.1"))) for a in (1, 2, 3)}
    per_service, best_total, nat_only, all_interface = {}, D(0), D(0), D(0)
    for svc, gb in s["monthly_gb_via_nat"].items():
        if svc == "internet_other":
            continue
        c = service_costs(r, gb, ENDPOINTS[svc], azs, svc in GATEWAY_CAPABLE)
        best = min(c, key=c.get)
        per_service[svc] = {"gb": gb, "endpoints": ENDPOINTS[svc],
                            "break_even_gb": str(break_even_gb(r, ENDPOINTS[svc], azs).quantize(D("0.1"))),
                            "usd": {k: money(v) for k, v in c.items()}, "cheapest": best}
        best_total += c[best]
        nat_only += c["nat"]
        all_interface += c["interface_endpoint"]
    other = D(s["monthly_gb_via_nat"]["internet_other"]) * r["nat_gb"]
    nat_fixed = r["nat_hour"] * s["nat_gateways"] * HOURS_PER_MONTH
    totals = {"nat_only": nat_fixed + other + nat_only,
              "all_interface_endpoints": nat_fixed + other + all_interface,
              "cheapest_per_service": nat_fixed + other + best_total}
    s3_saving = per_service["s3"]["gb"] * r["nat_gb"]
    savings = {k: (c["nat"] - min(c.values())) for k, c in
               ((k, service_costs(r, v["gb"], v["endpoints"], azs, k in GATEWAY_CAPABLE)) for k, v in per_service.items())}
    small = [k for k, v in per_service.items() if D(v["gb"]) < D(v["break_even_gb"]) and k not in GATEWAY_CAPABLE]
    return {
        "snapshot": pb.data["retrieved"], "rates": {k: str(v) for k, v in r.items()},
        "break_even_gb_per_month": table,
        "scenario": {"azs": azs, "nat_gateways": s["nat_gateways"], "per_service": per_service,
                     "nat_fixed_usd": money(nat_fixed), "internet_other_usd": money(other),
                     "totals_usd": {k: money(v) for k, v in totals.items()}},
        "hypotheses": {
            "H1_interface_endpoints_below_break_even_cost_more": {
                "result": all(per_service[k]["cheapest"] == "nat" for k in small), "services_below_break_even": small},
            "H2_s3_gateway_endpoint_is_largest_single_saving": {
                "result": max(savings, key=savings.get) == "s3", "saving_usd": {k: money(v) for k, v in savings.items()},
                "s3_saving_usd": money(s3_saving)},
            "H3_all_interface_endpoints_cost_more_than_nat_only": {
                "result": totals["all_interface_endpoints"] > totals["nat_only"]},
        },
        "variant_no_internet_traffic": no_internet_variant(r, s, per_service),
    }


def no_internet_variant(r, s, per_service):
    """If nothing needs the internet, the NAT gateway can be deleted only when every service has an endpoint."""
    azs = s["azs"]
    nat_keep = r["nat_hour"] * s["nat_gateways"] * HOURS_PER_MONTH + sum(D(v["gb"]) for v in per_service.values()) * r["nat_gb"]
    s3_gw = D(per_service["s3"]["gb"])
    nat_keep_s3_gw = nat_keep - s3_gw * r["nat_gb"]
    eps = sum(v["endpoints"] for k, v in per_service.items() if k not in GATEWAY_CAPABLE)
    ep_gb = sum(D(v["gb"]) for k, v in per_service.items() if k not in GATEWAY_CAPABLE)
    no_nat = r["ep_hour"] * eps * azs * HOURS_PER_MONTH + ep_gb * r["ep_gb"]
    return {"nat_plus_s3_gateway_usd": money(nat_keep_s3_gw), "endpoints_only_no_nat_usd": money(no_nat),
            "interface_endpoints": eps, "cheaper": "endpoints_only" if no_nat < nat_keep_s3_gw else "nat_plus_s3_gateway",
            "nat_removal_needs_interface_gb_at_least": str(((no_nat - r["nat_hour"] * s["nat_gateways"] * HOURS_PER_MONTH) / r["nat_gb"]).quantize(D("0.1")))}


if __name__ == "__main__":
    emit(evaluate())
