"""Experiment 036: run the design-stage cost model on (1) the 019 pipeline and (2) both scenarios."""
from decimal import Decimal as D
from pathlib import Path
import json
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scenarios"))
from pricebook import PriceBook, emit, load_scenario  # noqa: E402
import model as m  # noqa: E402

EXP = Path(__file__).resolve().parents[1]


def load(p):
    return json.loads((EXP / p).read_text(encoding="utf-8"))


def pipeline_019(pb):
    """Rebuild 019's components from its drivers (016/017/019 results) with the 2026-11-15 rates."""
    r19 = load("019-pipeline-unit-cost/result.json")
    iot = load("016-iot-message-batching/result.json")["headline"]
    fh = load("017-firehose-buffer-small-files/result.json")["rows"]
    obj = lambda i: next(x for x in fh if (x["workload"], x["partitions"], x["size_mib"], x["interval_s"]) == ("A_100x10s", 1, 5, i))
    readings = r19["readings_per_month"]
    mix, crawler = r19["query_mix_per_day"], r19["crawler_assumption"]
    cfg = {"baseline": {"iot": iot["individual"], "records": readings, "bytes": 200, "conv": False, "obj": obj(60), "crawler": True},
           "improved": {"iot": iot["batch20"], "records": readings // 20, "bytes": 4000, "conv": True, "obj": obj(300), "crawler": False}}
    out = {}
    for name, k in cfg.items():
        i = k["iot"]
        base = (m.iot_core(pb, i["published_messages"], i["message_bytes"], devices=i["sensors"], minutes=30 * 1440)
                + m.firehose(pb, k["records"], k["bytes"], k["conv"])
                + m.s3(pb, k["obj"]["objects_per_month_mean"], D(str(r19["configs"][name]["stored_gb"])))
                + (m.glue_dpu(pb, "Glue crawler", crawler["dpu"], D(crawler["minutes_per_day"]) / 60 * 30, "APN2-Crawler-DPU-Hour") if k["crawler"] else []))
        qb = r19["configs"][name]["per_query_bytes_scaled"]
        by_scale = {}
        for scale in r19["query_scales"]:
            comps = base + m.athena(pb, [(qb[q], D(n) * D(str(scale)) * 30) for q, n in mix.items()])
            s = m.summarize(comps, readings / 1000, "1000_readings")
            ref = r19["configs"][name]["by_query_scale"][str(scale)]["usd_per_1000_readings"]
            got = D(s["usd_per_1000_readings"]).quantize(D("0.000001"))
            by_scale[str(scale)] = {"model_usd_per_1000": str(got), "019_usd_per_1000": f"{ref:.6f}",
                                    "abs_diff": str(abs(got - D(str(ref)))), "model_total_usd": s["total_usd"]}
        out[name] = by_scale
    return out


def scenario_iot(pb):
    s = load_scenario("iot-pipeline-agent")
    d, rt, b, a, o, n = s["devices"], s["realtime"], s["batch"], s["agent"], s["observability"], s["network"]
    readings = d["count"] * (s["period"]["days"] * 86400 // d["interval_s"])
    calls = a["model_calls_per_request"]
    tin = sum(a["system_and_tools_tokens"] + a["question_tokens"] + i * (a["tool_result_tokens"] + a["output_tokens_per_call"]) for i in range(calls))
    comps = (m.iot_core(pb, readings, d["reading_bytes"], rules=2, devices=d["count"], minutes=s["period"]["days"] * 1440)
             + m.firehose(pb, readings, d["reading_bytes"])
             + m.s3(pb, s["period"]["days"] * 86400 // s["ingest"]["firehose_buffer_s"], D(readings * d["reading_bytes"]) / m.GB)
             + m.lambda_fn(pb, readings // rt["sqs_batch_size"], rt["fixed_ms_per_invoke"] + rt["sqs_batch_size"] * rt["ms_per_reading"], rt["lambda_memory_mb"])
             + m.glue_dpu(pb, "Glue Spark ETL job", b["dpu"], D(b["runs_per_day"] * s["period"]["days"] * b["minutes_per_run"]) / 60)
             + m.athena(pb, [(a["scan_mb_per_query"] * 1024 * 1024, a["requests_per_month"] * a["athena_queries_per_request"])])
             + m.bedrock_tokens(pb, a["model"], {"in": tin * a["requests_per_month"], "out": calls * a["output_tokens_per_call"] * a["requests_per_month"]})
             + m.nat(pb, n["nat_gateways"], 0)
             + m.logs(pb, o["log_gb_per_month"])
             + m.metrics(pb, o["metrics_per_device"] * d["count"]))
    out = m.summarize(comps, readings / 1000, "1000_readings")
    out["excluded"] = ["SQS requests (not in the 2026-11-15 snapshot)", "Glue crawler", "S3 GET by Athena"]
    return out


def scenario_web(pb):
    s = load_scenario("web-llm-chatbot")
    w, ch, n, o = s["web"], s["chatbot"], s["network"], s["observability"]
    q = ch["questions_per_month"]
    comps = (m.api_http(pb, w["requests_per_month"] + q)
             + m.ecs_fargate(pb, w["service"]["tasks"], w["service"]["vcpu"], w["service"]["mem_gb"])
             + m.rds(pb, w["db"]["class"], w["db"]["engine"], w["db"]["storage_gb"])
             + m.cache_serverless(pb, w["cache"]["engine"], w["cache"]["data_gb"], w["cache"]["requests_per_month"])
             + m.bedrock_tokens(pb, ch["model"], {"in": ch["input_tokens"] * q, "out": ch["output_tokens"] * q})
             + m.guardrails(pb, q, ch["question_chars"], ch["answer_chars"], ch["guardrail_policies"])
             + m.opensearch_classic(pb)
             + m.nat(pb, n["nat_gateways"], sum(n["monthly_gb_via_nat"].values()))
             + m.logs(pb, o["log_gb_per_month"]))
    out = m.summarize(comps, q, "chatbot_question")
    out["note"] = "per-question figure divides the whole stack by chatbot questions; web traffic shares the stack"
    return out


def evaluate():
    pb = PriceBook()
    p19 = pipeline_019(pb)
    max_diff = max(D(v["abs_diff"]) for cfg in p19.values() for v in cfg.values())
    iot, web = scenario_iot(pb), scenario_web(pb)
    return {
        "snapshot": pb.data["retrieved"],
        "reproduce_019": p19, "reproduce_019_max_abs_diff_usd_per_1000": str(max_diff),
        "scenario_iot_pipeline_agent": iot, "scenario_web_llm_chatbot": web,
        "hypotheses": {
            "H1_reproduces_019_per_1000_within_0_000001": {"result": max_diff <= D("0.000001"), "max_abs_diff": str(max_diff)},
            "H2_flagged_components_ge_50pct_in_both_scenarios": {
                "result": D(iot["flagged_share"]) >= D("0.5") and D(web["flagged_share"]) >= D("0.5"),
                "iot_flagged_share": iot["flagged_share"], "web_flagged_share": web["flagged_share"]},
        },
    }


if __name__ == "__main__":
    emit(evaluate())
