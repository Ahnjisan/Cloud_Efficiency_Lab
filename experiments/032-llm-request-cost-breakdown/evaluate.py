"""Cost of one LLM request, broken down, and how agent loops amplify it.

Part A - scenario 2 chatbot request: model tokens, Guardrails (input and output
         evaluated separately, 1,000-character text units), vector-store minimum
         spread over the month's questions, API Gateway.
Part B - scenario 1 agent request: k model calls; each call re-sends the system
         prompt + tools + question and all previous tool results and outputs.
         With and without caching of the fixed prefix (system + tools).
Part C - model mix (cost only; quality is not judged here).
"""
from decimal import Decimal as D
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scenarios"))
from pricebook import HOURS_PER_MONTH, PriceBook, emit, load_scenario, money  # noqa: E402
from service_pack import billed_units  # noqa: E402

M = D(10 ** 6)
CLAUDE45 = {"in": "APN2-MP:APN2_InputTokenCount_Global-Units", "out": "APN2-MP:APN2_OutputTokenCount_Global-Units",
            "cache_read": "APN2-MP:APN2_CacheReadInputTokenCount_Global-Units", "cache_write": "APN2-MP:APN2_CacheWriteInputTokenCount_Global-Units"}
CLAUDE55 = {"in": "APN2-MP:APN2_input_tokens_global_standard-Units", "out": "APN2-MP:APN2_output_tokens_global_standard-Units",
            "cache_read": "APN2-MP:APN2_cache_read_tokens_global_standard-Units", "cache_write": "APN2-MP:APN2_cache_write_tokens_global_standard-Units"}


def model_rates(pb, model):
    uts = CLAUDE45 if "4.5" in model else CLAUDE55
    return {k: pb.rate("AmazonBedrockFoundationModels", ut, model=model) / M for k, ut in uts.items()}


def chatbot_request(pb):
    s = load_scenario("web-llm-chatbot")
    c = s["chatbot"]
    r = model_rates(pb, c["model"])
    q_units = billed_units("guardrails_text_unit", c["question_chars"])
    a_units = billed_units("guardrails_text_unit", c["answer_chars"])
    gr = sum(pb.rate("AmazonBedrock", f"APN2-Guardrail-{p}UnitsConsumed") for p in c["guardrail_policies"]) * (q_units + a_units)
    parts = {
        "model_tokens": D(c["input_tokens"]) * r["in"] + D(c["output_tokens"]) * r["out"],
        "guardrails": gr,
        "vector_store_minimum_share": 2 * pb.rate("AmazonES", "APN2-IndexingOCU") * HOURS_PER_MONTH / D(c["questions_per_month"]),
        "api_gateway_http": pb.rate("AmazonApiGateway", "APN2-ApiGatewayHttpRequest"),
    }
    total = sum(parts.values())
    return {"per_request_usd": {k: str(v.quantize(D("0.0000001"))) for k, v in parts.items()},
            "total_usd": str(total.quantize(D("0.0000001"))),
            "share": {k: str((v / total).quantize(D("0.0001"))) for k, v in parts.items()},
            "guardrail_text_units": {"question": int(q_units), "answer": int(a_units)},
            "monthly_usd": money(total * c["questions_per_month"])}


# Minimum tokens per cache checkpoint (Bedrock prompt caching docs, checked 2026-11-15).
MIN_CACHE_TOKENS = {"Claude Haiku 4.5": 4096, "Claude Haiku 5.5": 512, "Claude Sonnet 5.5": 512}


def agent_tokens(a, k, mode, min_cache=0):
    """mode: none | fixed_prefix (checkpoint after system+tools) | automatic (checkpoint moves to end of input)."""
    prefix = a["system_and_tools_tokens"]
    tokens = {"in": 0, "out": 0, "cache_read": 0, "cache_write": 0}
    written = 0  # longest prefix currently in cache
    for i in range(k):
        total_in = prefix + a["question_tokens"] + i * (a["tool_result_tokens"] + a["output_tokens_per_call"])
        if mode == "fixed_prefix" and prefix >= min_cache:
            read = prefix if written >= prefix else 0
            write = prefix - read
            written = max(written, prefix)
        elif mode == "automatic":
            read = written if written and written <= total_in else 0
            write = (total_in - read) if total_in >= min_cache else 0
            if write:
                written = total_in
        else:
            read = write = 0
        tokens["cache_read"] += read
        tokens["cache_write"] += write
        tokens["in"] += total_in - read - write
        tokens["out"] += a["output_tokens_per_call"]
    return tokens


def cost(tokens, r):
    return sum(D(tokens[k]) * r[k] for k in tokens)


def agent_request(pb):
    a = load_scenario("iot-pipeline-agent")["agent"]
    out = {}
    for model in (a["model"], "Claude Haiku 5.5"):
        r, mn = model_rates(pb, model), MIN_CACHE_TOKENS[model]
        single = cost(agent_tokens(a, 1, "none"), r)
        rows = []
        for k in range(1, 9):
            t = agent_tokens(a, k, "none")
            c = cost(t, r)
            row = {"calls": k, "input_tokens": t["in"], "output_tokens": t["out"], "usd": str(c.quantize(D("0.000001"))),
                   "amplification_vs_single_call": str((c / single).quantize(D("0.01")))}
            for mode in ("fixed_prefix", "automatic"):
                tm = agent_tokens(a, k, mode, mn)
                cm = cost(tm, r)
                row[mode] = {"usd": str(cm.quantize(D("0.000001"))), "saving": str(((c - cm) / c).quantize(D("0.0001"))),
                             "cache_read": tm["cache_read"], "cache_write": tm["cache_write"]}
            rows.append(row)
        out[model] = {"min_cache_tokens": mn, "single_call_usd": str(single.quantize(D("0.000001"))), "by_calls": rows}
    athena = D(a["athena_queries_per_request"] * max(10, a["scan_mb_per_query"])) / D(1024 * 1024) * pb.rate("AmazonAthena", "APN2-DataScannedInTB")
    k = a["model_calls_per_request"]
    row = out[a["model"]]["by_calls"][k - 1]
    return {"scenario_model": a["model"], "scenario_calls": k, "by_model": out,
            "athena_per_request_usd": str(athena.quantize(D("0.000001"))),
            "monthly_usd_scenario": money((D(row["usd"]) + athena) * a["requests_per_month"]),
            "monthly_usd_scenario_automatic_cache": money((D(row["automatic"]["usd"]) + athena) * a["requests_per_month"])}


def model_mix(pb):
    c = load_scenario("web-llm-chatbot")["chatbot"]
    per = {m: D(c["input_tokens"]) * model_rates(pb, m)["in"] + D(c["output_tokens"]) * model_rates(pb, m)["out"]
           for m in ("Claude Haiku 4.5", "Claude Sonnet 4.5", "Claude Haiku 5.5", "Claude Sonnet 5.5")}
    mixes = {"100% Claude Sonnet 5.5": {"Claude Sonnet 5.5": D(1)},
             "70% Haiku 5.5 / 30% Sonnet 5.5": {"Claude Haiku 5.5": D("0.7"), "Claude Sonnet 5.5": D("0.3")},
             "100% Claude Haiku 4.5": {"Claude Haiku 4.5": D(1)}}
    return {"per_request_model_usd": {m: str(v.quantize(D("0.0000001"))) for m, v in per.items()},
            "mixes_monthly_usd": {name: money(sum(w * per[m] for m, w in mix.items()) * c["questions_per_month"]) for name, mix in mixes.items()},
            "verdict": "판단 보류 — 배분에 따른 응답 품질을 평가할 데이터가 없음"}


def evaluate():
    pb = PriceBook()
    chat, agent = chatbot_request(pb), agent_request(pb)
    k = agent["scenario_calls"]
    row = agent["by_model"][agent["scenario_model"]]["by_calls"][k - 1]
    return {
        "snapshot": pb.data["retrieved"], "chatbot_request": chat, "agent_request": agent, "model_mix": model_mix(pb),
        "hypotheses": {
            "H1_model_tokens_lt_half_of_chatbot_request": {"result": D(chat["share"]["model_tokens"]) < D("0.5"),
                                                         "model_token_share": chat["share"]["model_tokens"]},
            "H2_agent_k_calls_cost_more_than_k_times_single": {"result": D(row["amplification_vs_single_call"]) > k,
                                                              "calls": k, "amplification": row["amplification_vs_single_call"]},
            "H3_prefix_cache_saves_ge_20pct_at_scenario_calls": {
                "result": D(row["fixed_prefix"]["saving"]) >= D("0.2"), "saving_fixed_prefix": row["fixed_prefix"]["saving"],
                "saving_automatic": row["automatic"]["saving"],
                "note": "fixed 2,000-token prefix is below the 4,096-token minimum for Claude Haiku 4.5"},
        },
    }


if __name__ == "__main__":
    emit(evaluate())
