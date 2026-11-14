"""Input-token definitions differ by source; how wrong is a cost estimate, and how to tell.

Facts (checked 2026-11-15):
  - Converse API usage.inputTokens counts only non-cached input;
    total input = inputTokens + cacheReadInputTokens + cacheWriteInputTokens.
  - Responses API (OpenAI models on Bedrock) usage.input_tokens includes cached and cache-write tokens.
  - CloudWatch AWS/Bedrock InputTokenCount is defined only as "number of tokens in the input";
    whether it includes cache tokens is not stated (unconfirmed). Cache read/write are separate metrics.
  - Billing has separate usage types for input, cache read and cache write tokens.

We generate one synthetic month of agent calls with known token parts, then
compute cost under each reading of "input tokens" and the check that reveals
which reading a metric follows.
"""
from decimal import Decimal as D
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scenarios"))
from pricebook import PriceBook, emit, load_scenario, money  # noqa: E402

SEED = 33
MODEL = "Claude Haiku 5.5"  # 512-token cache minimum, so caching is active
MIN_CACHE = 512
UT = {"in": "APN2-MP:APN2_input_tokens_global_standard-Units", "out": "APN2-MP:APN2_output_tokens_global_standard-Units",
      "read": "APN2-MP:APN2_cache_read_tokens_global_standard-Units", "write": "APN2-MP:APN2_cache_write_tokens_global_standard-Units"}
TOLERANCE = D("0.01")  # relative difference treated as noise (rounding, late records)
FAILED_BEFORE_MODEL = D("0.02")  # share of requests rejected before a model is resolved (assumed)


def calls(seed=SEED, mode="fixed_prefix"):
    """Synthetic agent calls. mode: fixed_prefix (checkpoint after system+tools), automatic (checkpoint at end of input), none."""
    a = load_scenario("iot-pipeline-agent")["agent"]
    rng = random.Random(seed)
    out = []
    for _ in range(a["requests_per_month"]):
        k = rng.choice([2, 3, 4, 4, 5, 6])
        written, ctx = 0, a["system_and_tools_tokens"] + a["question_tokens"]
        for i in range(k):
            total = ctx
            if mode == "fixed_prefix":
                p = a["system_and_tools_tokens"]
                read = p if written >= p else 0
                write = p - read
                written = max(written, p)
            elif mode == "automatic":
                read = written if written and written <= total else 0
                write = (total - read) if total >= MIN_CACHE else 0
                written = total if write else written
            else:
                read = write = 0
            o = int(a["output_tokens_per_call"] * rng.uniform(0.5, 1.5))
            out.append({"uncached": total - read - write, "read": read, "write": write, "out": o})
            ctx += int(a["tool_result_tokens"] * rng.uniform(0.5, 1.5)) + o
    return out


def totals(cs):
    t = {k: sum(c[k] for c in cs) for k in ("uncached", "read", "write", "out")}
    t["inclusive_input"] = t["uncached"] + t["read"] + t["write"]
    return t


def estimates(t, r):
    true = D(t["uncached"]) * r["in"] + D(t["read"]) * r["read"] + D(t["write"]) * r["write"] + D(t["out"]) * r["out"]
    est = {
        "E1_exclusive_input_only_ignore_cache_metrics": D(t["uncached"]) * r["in"] + D(t["out"]) * r["out"],
        "E2_inclusive_input_all_at_input_rate": D(t["inclusive_input"]) * r["in"] + D(t["out"]) * r["out"],
        "E3_inclusive_metric_plus_cache_metrics_double_count": (D(t["inclusive_input"]) * r["in"] + D(t["read"]) * r["read"]
                                                                + D(t["write"]) * r["write"] + D(t["out"]) * r["out"]),
        "E4_correct": true,
    }
    return true, {k: {"usd": money(v, "0.0001"), "error": str((v / true - 1).quantize(D("0.0001")))} for k, v in est.items()}


def classify(metric_total, billed_input_qty, billed_read_qty, billed_write_qty):
    """Which definition does a CloudWatch InputTokenCount total follow? Compare with billing quantities."""
    exclusive, inclusive = D(billed_input_qty), D(billed_input_qty + billed_read_qty + billed_write_qty)
    m = D(metric_total)
    near = lambda a, b: b != 0 and abs(a / b - 1) <= TOLERANCE
    ex, inc = near(m, exclusive), near(m, inclusive)
    if ex and not inc:
        return "exclusive"
    if inc and not ex:
        return "inclusive"
    return "indistinguishable" if ex and inc else "neither"


def evaluate():
    pb = PriceBook()
    r = {k: pb.rate("AmazonBedrockFoundationModels", ut, model=MODEL) / D(10 ** 6) for k, ut in UT.items()}
    modes = {}
    for mode in ("fixed_prefix", "automatic"):
        t = totals(calls(mode=mode))
        true, est = estimates(t, r)
        modes[mode] = {"token_totals": t,
                       "cache_token_share": str((D(t["read"] + t["write"]) / D(t["inclusive_input"])).quantize(D("0.0001"))),
                       "true_cost_usd": money(true, "0.0001"), "estimates": est,
                       "definition_check": {truth: classify(t["uncached"] if truth == "exclusive" else t["inclusive_input"],
                                                            t["uncached"], t["read"], t["write"]) for truth in ("exclusive", "inclusive")}}
    t = modes["fixed_prefix"]["token_totals"]
    sweep = []
    for f in ("1", "0.1", "0.05", "0.03", "0.02", "0.01", "0.005"):
        f = D(f)
        rd, wr = int(t["read"] * f), int(t["write"] * f)
        un = t["inclusive_input"] - rd - wr
        sweep.append({"cache_token_share": str((D(rd + wr) / D(t["inclusive_input"])).quantize(D("0.0001"))),
                      "exclusive_truth_classified_as": classify(un, un, rd, wr),
                      "inclusive_truth_classified_as": classify(un + rd + wr, un, rd, wr)})
    requests = load_scenario("iot-pipeline-agent")["agent"]["requests_per_month"]
    model_calls = len(calls())
    rejected = int(D(requests) * FAILED_BEFORE_MODEL)
    recon = {"model_calls_with_model_id": model_calls, "rejected_before_model_resolution": rejected,
             "invocations_aggregate_series": model_calls + rejected,
             "undercount_if_filtered_by_model_id": str((D(rejected) / D(model_calls + rejected)).quantize(D("0.0001"))),
             "note": "rejections before model resolution are published without ModelId; throttled and validation-rejected calls are not counted as Invocations at all"}
    detectable = [row for row in sweep if row["exclusive_truth_classified_as"] == "exclusive" and row["inclusive_truth_classified_as"] == "inclusive"]
    min_detectable = min(D(row["cache_token_share"]) for row in detectable) if detectable else None
    high = [m for m in modes.values() if D(m["cache_token_share"]) >= D("0.5")]
    wrong = lambda m: [abs(D(v["error"])) for k, v in m["estimates"].items() if not k.startswith("E4")]
    return {
        "snapshot": pb.data["retrieved"], "model": MODEL, "min_cache_tokens": MIN_CACHE, "seed": SEED, "tolerance": str(TOLERANCE),
        "rates_per_token": {k: str(v) for k, v in r.items()},
        "by_cache_mode": modes, "definition_check_sweep": sweep, "invocations_reconciliation": recon,
        "hypotheses": {
            "H1_wrong_definition_error_ge_30pct_when_cache_share_ge_50pct": {
                "result": bool(high) and all(min(wrong(m)) >= D("0.3") for m in high),
                "cases_with_share_ge_50pct": len(high),
                "errors_by_mode": {k: {e: v["error"] for e, v in m["estimates"].items()} for k, m in modes.items()}},
            "H2_billing_check_identifies_definition_when_cache_share_ge_2pct": {
                "result": min_detectable is not None and min_detectable <= D("0.02"),
                "smallest_detectable_cache_share": str(min_detectable) if min_detectable is not None else None},
        },
    }


if __name__ == "__main__":
    emit(evaluate())
