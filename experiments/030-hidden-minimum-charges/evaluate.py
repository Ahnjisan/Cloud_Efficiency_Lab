"""Hidden minimum charges: where billed cost is set by a floor, not by usage.

For each service: usage-based cost (what a linear 'rate x usage' estimate gives)
vs billed cost with the official minimum. minimum_share = 1 - usage / billed.
Then scenario 2: which monthly components are floor-driven, compared with the
chatbot's model token cost.
"""
from decimal import Decimal as D
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scenarios"))
from pricebook import HOURS_PER_MONTH, PriceBook, emit, load_scenario, money  # noqa: E402
from service_pack import billed_units  # noqa: E402

H = HOURS_PER_MONTH


def share(usage, billed):
    return D(0) if billed == 0 else (1 - usage / billed).quantize(D("0.0001"))


def curves(pb):
    out = {}
    # ElastiCache serverless storage minimum (Valkey 100 MB, Redis OSS 1 GB)
    rows = []
    for gb in ("0.01", "0.05", "0.1", "0.5", "1", "2"):
        g = D(gb)
        for eng, floor in (("Valkey", D("0.1")), ("Redis", D(1))):
            rate = pb.rate("AmazonElastiCache", f"APN2-CachedData:{eng}") * H
            usage, billed = g * rate, max(g, floor) * rate
            rows.append({"data_gb": gb, "engine": eng, "usage_usd": money(usage), "billed_usd": money(billed),
                         "minimum_share": str(share(usage, billed))})
    out["elasticache_serverless_storage"] = rows
    # OpenSearch Serverless Classic: minimum 2 OCU (dev/test 1 OCU) vs needed average OCU
    ocu = pb.rate("AmazonES", "APN2-IndexingOCU") * H
    out["opensearch_classic_ocu"] = [
        {"needed_avg_ocu": n, "usage_usd": money(D(n) * ocu), "billed_usd": money(max(D(n), D(2)) * ocu),
         "minimum_share": str(share(D(n) * ocu, max(D(n), D(2)) * ocu))} for n in ("0.1", "0.5", "1", "2", "4")]
    # Fargate Linux 1-minute minimum per task (0.25 vCPU / 0.5 GB)
    per_s = (D("0.25") * pb.rate("AmazonECS", "APN2-Fargate-vCPU-Hours:perCPU")
             + D("0.5") * pb.rate("AmazonECS", "APN2-Fargate-GB-Hours")) / 3600
    out["fargate_task_minimum"] = [
        {"task_seconds": t, "billed_seconds": int(billed_units("fargate_linux_seconds", t)),
         "usage_usd_per_10k_tasks": money(per_s * t * 10000, "0.0001"),
         "billed_usd_per_10k_tasks": money(per_s * billed_units("fargate_linux_seconds", t) * 10000, "0.0001"),
         "minimum_share": str(share(D(t), billed_units("fargate_linux_seconds", t)))} for t in (5, 15, 30, 60, 120)]
    # Athena 10 MB minimum per query
    tb = pb.rate("AmazonAthena", "APN2-DataScannedInTB")
    out["athena_query_minimum"] = [
        {"scan_mb": mb, "billed_mb": int(billed_units("athena_scan", mb * 1048576)),
         "usage_usd_per_100k_queries": money(D(mb) / D(1048576) * tb * 100000),
         "billed_usd_per_100k_queries": money(billed_units("athena_scan", mb * 1048576) / D(1048576) * tb * 100000),
         "minimum_share": str(share(D(mb), billed_units("athena_scan", mb * 1048576)))} for mb in (0.1, 1, 5, 10, 50)]
    # Guardrails: a 30-character question still costs one text unit
    unit = pb.rate("AmazonBedrock", "APN2-Guardrail-ContentPolicyUnitsConsumed")
    out["guardrails_text_unit"] = [
        {"chars": n, "units": int(billed_units("guardrails_text_unit", n)), "usd_per_100k": money(billed_units("guardrails_text_unit", n) * unit * 100000),
         "minimum_share": str(share(D(n), billed_units("guardrails_text_unit", n) * 1000))} for n in (30, 200, 1000, 1500)]
    return out


def scenario(pb):
    s = load_scenario("web-llm-chatbot")
    c, w = s["chatbot"], s["web"]
    fm = lambda ut: pb.rate("AmazonBedrockFoundationModels", ut, model=c["model"])
    tokens = (D(c["input_tokens"]) * fm("APN2-MP:APN2_InputTokenCount_Global-Units")
              + D(c["output_tokens"]) * fm("APN2-MP:APN2_OutputTokenCount_Global-Units")) / D(10**6) * c["questions_per_month"]
    ocu = pb.rate("AmazonES", "APN2-IndexingOCU") * H
    cache_rate = pb.rate("AmazonElastiCache", f"APN2-CachedData:{w['cache']['engine']}") * H
    cache_data = D(str(w["cache"]["data_gb"]))
    comps = {
        "vector_store_opensearch_classic": {"billed": 2 * ocu, "usage": None,
                                            "note": "minimum 2 OCU; actual OCU need unknown for 2 GB of source data"},
        "cache_serverless_storage": {"billed": max(cache_data, D("0.1")) * cache_rate, "usage": cache_data * cache_rate},
        "chatbot_model_tokens": {"billed": tokens, "usage": tokens},
    }
    floor_total = comps["vector_store_opensearch_classic"]["billed"] + comps["cache_serverless_storage"]["billed"] - comps["cache_serverless_storage"]["usage"]
    return {
        "components_usd": {k: {"billed": money(v["billed"]), "usage_based": money(v["usage"]) if v["usage"] is not None else None,
                               **({"note": v["note"]} if "note" in v else {})} for k, v in comps.items()},
        "excluded": "Knowledge Base managed index storage (5 USD per source GB on pricing page) is in the snapshot's missing list",
        "floor_driven_usd": money(floor_total), "model_tokens_usd": money(tokens),
        "redis_instead_of_valkey_usd": money(max(cache_data, D(1)) * pb.rate("AmazonElastiCache", "APN2-CachedData:Redis") * H),
    }


def evaluate():
    pb = PriceBook()
    sc = scenario(pb)
    cv = curves(pb)
    valkey = D(sc["components_usd"]["cache_serverless_storage"]["billed"])
    redis = D(sc["redis_instead_of_valkey_usd"])
    return {
        "snapshot": pb.data["retrieved"], "curves": cv, "scenario_web_llm_chatbot": sc,
        "hypotheses": {
            "H1_floor_driven_cost_exceeds_model_tokens_in_scenario2": {
                "result": D(sc["floor_driven_usd"]) > D(sc["model_tokens_usd"]),
                "floor_driven_usd": sc["floor_driven_usd"], "model_tokens_usd": sc["model_tokens_usd"]},
            "H2_valkey_cuts_small_cache_storage_cost_ge_90pct_vs_redis": {
                "result": (1 - valkey / redis) >= D("0.9"), "valkey_usd": str(valkey), "redis_usd": str(redis),
                "reduction": str((1 - valkey / redis).quantize(D("0.0001")))},
        },
    }


if __name__ == "__main__":
    emit(evaluate())
