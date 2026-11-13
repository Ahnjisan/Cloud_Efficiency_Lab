"""Read-only workload rules: IoT batching, Firehose small records, Bedrock caching.

Rules R-IOT-1, R-FH-1, R-BR-1 and R-BR-2 from
experiments/infrafit-pipeline-ai-rules.md. Inputs are synthetic JSON; rates come
from the Seoul price snapshot. Each item is judged on its own: a missing or
contradictory input holds only that item. Savings are modeled ("expected"),
never realized billing savings.
"""
from collections import defaultdict
from decimal import Decimal
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LABELS = {"candidate": "변경 검토 후보", "keep": "유지", "hold": "판단 보류"}
GIB = 1024 ** 3
REASONS = {
    "input-invalid": "필수 입력이 없거나 형식이 잘못됐습니다.",
    "iot-max-wait-missing": "토픽의 허용 지연이 입력되지 않았습니다.",
    "iot-metering-inconsistent": "계량 메시지 수가 발행 수와 평균 페이로드로 설명되지 않습니다.",
    "iot-alert-topic": "경보·제어 토픽은 묶음 대상이 아닙니다.",
    "iot-payload-already-large": "평균 페이로드가 커서 묶어도 계량이 크게 줄지 않습니다.",
    "iot-wait-too-short": "허용 지연 안에서 2건 이상 묶을 수 없습니다.",
    "iot-batching-reduces-metering": "허용 지연 안에서 묶으면 계량 메시지가 줄어듭니다.",
    "fh-billing-below-raw": "청구 GB가 실제 수집 GB보다 작아 입력이 모순됩니다.",
    "fh-no-rounding-usage": "적용 조건을 확인하지 못한 no-rounding 수집 요율이 청구에 있습니다.",
    "fh-ratio-inconclusive": "청구 GB와 실제 수집 GB의 비율이 판정 구간 사이에 있습니다.",
    "fh-upstream-unknown": "상류에서 레코드를 합칠 수 있는지 입력되지 않았습니다.",
    "fh-upstream-cannot-combine": "상류에서 레코드를 합칠 수 없습니다.",
    "fh-small-records": "작은 레코드의 5 KB 올림으로 청구 GB가 실제보다 큽니다.",
    "fh-ratio-low": "청구 GB가 실제 수집 GB에 가깝습니다.",
    "br-rate-unverified": "이 모델·추론 프로필의 서울 리전 요율을 확인하지 못했습니다.",
    "br-prefix-inconsistent": "같은 앞부분 해시의 토큰 수가 호출마다 다릅니다.",
    "br-cache-minimum-unknown": "이 모델의 캐시 최소 토큰 수를 확인하지 못했습니다.",
    "br-below-cache-minimum": "앞부분이 캐시 최소 토큰 수보다 짧습니다.",
    "br-repeated-within-run": "같은 앞부분이 실행마다 2회 이상 반복되는데 캐싱하지 않습니다.",
    "br-reuse-above-break-even": "같은 앞부분이 TTL 안에 반복되는 비율이 손익분기보다 높습니다.",
    "br-reuse-below-break-even": "같은 앞부분이 TTL 안에 반복되는 비율이 손익분기보다 낮습니다.",
    "br-ttl-missing": "캐시를 쓰지만 TTL이 입력되지 않았거나 호출마다 다릅니다.",
    "br-too-few-cache-writes": "판정에 필요한 캐시 쓰기 관측 수가 부족합니다.",
    "br-hit-below-break-even": "캐시 적중률이 손익분기보다 낮아 캐싱이 비용을 늘립니다.",
    "br-hit-above-break-even": "캐시 적중률이 손익분기보다 높습니다.",
}
BEDROCK_USAGE = {
    "Claude Haiku 5.5": "standard", "Claude Sonnet 5.5": "standard",
    "Claude Haiku 4.5": "legacy", "Claude Sonnet 4.5": "legacy",
}
USAGE_SUFFIX = {
    "standard": {"input": "input_tokens_global_standard", "output": "output_tokens_global_standard",
                 "write_5m": "cache_write_tokens_global_standard",
                 "write_1h": "cache_write_tokens_1h_global_standard", "read": "cache_read_tokens_global_standard"},
    "legacy": {"input": "InputTokenCount_Global", "output": "OutputTokenCount_Global",
               "write_5m": "CacheWriteInputTokenCount_Global",
               "write_1h": "CacheWrite1hInputTokenCount_Global", "read": "CacheReadInputTokenCount_Global"},
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def value(thresholds, section, key):
    return thresholds[section][key]["value"]


def load_rates(thresholds):
    offers = load_json(ROOT / thresholds["rates_snapshot"])["offers"]
    iot = offers["AWSIoT"]["rows"]
    pick = lambda rows, ut: Decimal(next(r["usd"] for r in rows if r["usagetype"] == ut))
    tiers = sorted((Decimal(r["begin"]), None if r["end"] == "Inf" else Decimal(r["end"]), Decimal(r["usd"]))
                   for r in iot if r["usagetype"] == "APN2-Messages")
    firehose = next(Decimal(r["usd"]) for r in offers["AmazonKinesisFirehose"]["rows"]
                    if r["usagetype"] == "APN2-BilledBytes" and Decimal(r["begin"]) == 0)
    bedrock = {}
    rows = offers["AmazonBedrockFoundationModels"]["rows"]
    for model, scheme in BEDROCK_USAGE.items():
        bedrock[model] = {key: Decimal(next(r["usd"] for r in rows if r["model"] == model
                                            and r["usagetype"] == f"APN2-MP:APN2_{suffix}-Units")) / 1_000_000
                          for key, suffix in USAGE_SUFFIX[scheme].items()}
    return {"iot_tiers": tiers, "iot_rule": pick(iot, "APN2-RulesTriggered"),
            "iot_action": pick(iot, "APN2-ActionsExecuted"), "firehose_gb": firehose, "bedrock": bedrock}


def decision(rule, item_id, status, reasons, evidence=None, saving=None, basis=None, used=None):
    return {"rule": rule, "id": item_id, "decision": status, "label": LABELS[status], "reasons": reasons,
            "evidence": evidence or {}, "expected_saving_usd": None if saving is None else str(saving.quantize(Decimal("0.000001"))),
            "saving_basis": basis, "thresholds_used": used or []}


def is_count(x, positive=False):
    return isinstance(x, int) and not isinstance(x, bool) and (x > 0 if positive else x >= 0)


def tiered(count, tiers):
    cost, remaining = Decimal(0), Decimal(count)
    for begin, end, usd in tiers:
        span = remaining if end is None else min(remaining, end - begin)
        if span <= 0:
            break
        cost += span * usd
        remaining -= span
    return cost


# ---------------------------------------------------------------- R-IOT-1
def assess_iot_topic(t, thresholds, rates):
    item = t.get("id")
    used = ["iot.kb_definitions_bytes", "iot.payload_max_bytes", "iot.batch_size_limit_bytes", "iot.metering_tolerance"]
    if not (isinstance(item, str) and t.get("purpose") in ("analytics", "alert")
            and is_count(t.get("metered_messages")) and is_count(t.get("published_messages"))
            and is_count(t.get("avg_payload_bytes"), True) and is_count(t.get("period_s"), True)
            and is_count(t.get("rules_per_message"))):
        return decision("R-IOT-1", item, "hold", ["input-invalid"], used=used)
    if t["purpose"] == "alert":
        return decision("R-IOT-1", item, "keep", ["iot-alert-topic"], used=used)
    payload, published, metered = t["avg_payload_bytes"], t["published_messages"], t["metered_messages"]
    tol = value(thresholds, "iot", "metering_tolerance")
    if not any(abs(metered - published * math.ceil(payload / kb)) <= tol * max(1, published * math.ceil(payload / kb))
               for kb in value(thresholds, "iot", "kb_definitions_bytes")):
        return decision("R-IOT-1", item, "hold", ["iot-metering-inconsistent"],
                        {"metered_messages": metered, "published_messages": published}, used=used)
    if payload > value(thresholds, "iot", "payload_max_bytes"):
        return decision("R-IOT-1", item, "keep", ["iot-payload-already-large"], {"avg_payload_bytes": payload}, used=used)
    wait = t.get("max_wait_s")
    if wait is None:
        return decision("R-IOT-1", item, "hold", ["iot-max-wait-missing"], used=used)
    if not is_count(wait):
        return decision("R-IOT-1", item, "hold", ["input-invalid"], used=used)
    batch = min(wait // t["period_s"] + 1, value(thresholds, "iot", "batch_size_limit_bytes") // payload)
    if batch < 2:
        return decision("R-IOT-1", item, "keep", ["iot-wait-too-short"], {"max_batch": batch}, used=used)
    after = math.ceil(published / batch) * math.ceil(batch * payload / min(value(thresholds, "iot", "kb_definitions_bytes")))
    per_rules = max(t["rules_per_message"], 0) * (rates["iot_rule"] + rates["iot_action"])
    saving = (tiered(metered, rates["iot_tiers"]) - tiered(after, rates["iot_tiers"])) + (metered - after) * per_rules
    return decision("R-IOT-1", item, "candidate", ["iot-batching-reduces-metering"],
                    {"max_batch": batch, "added_max_wait_s": (batch - 1) * t["period_s"],
                     "metered_messages": metered, "metered_after_batching": after},
                    saving, "월, 5,000 B 기준(보수적), 메시지+규칙+액션", used)


# ---------------------------------------------------------------- R-FH-1
def assess_firehose_stream(s, thresholds, rates):
    item = s.get("id")
    used = ["firehose.record_unit_bytes", "firehose.ratio_keep_below", "firehose.ratio_candidate_at"]
    try:
        billed = Decimal(s["billed_gb"])
        valid = (isinstance(item, str) and billed.is_finite() and billed >= 0
                 and is_count(s.get("incoming_records")) and is_count(s.get("incoming_bytes"), True)
                 and isinstance(s.get("billing_usagetypes"), list))
    except (KeyError, TypeError, ArithmeticError):
        valid = False
    if not valid:
        return decision("R-FH-1", item, "hold", ["input-invalid"], used=used)
    if any("no-rounding" in str(u) for u in s["billing_usagetypes"]):
        return decision("R-FH-1", item, "hold", ["fh-no-rounding-usage"], used=used)
    raw = Decimal(s["incoming_bytes"]) / GIB
    if billed < raw:
        return decision("R-FH-1", item, "hold", ["fh-billing-below-raw"], used=used)
    ratio = billed / raw
    evidence = {"billed_gb": str(billed), "raw_gb": str(raw.quantize(Decimal("0.001"))),
                "billed_to_raw_ratio": str(ratio.quantize(Decimal("0.01")))}
    if s["incoming_records"]:
        evidence["mean_record_bytes"] = round(s["incoming_bytes"] / s["incoming_records"], 1)
    if ratio < Decimal(str(value(thresholds, "firehose", "ratio_keep_below"))):
        return decision("R-FH-1", item, "keep", ["fh-ratio-low"], evidence, used=used)
    if ratio < Decimal(str(value(thresholds, "firehose", "ratio_candidate_at"))):
        return decision("R-FH-1", item, "hold", ["fh-ratio-inconclusive"], evidence, used=used)
    combine = s.get("upstream_can_combine")
    if combine is None:
        return decision("R-FH-1", item, "hold", ["fh-upstream-unknown"], evidence, used=used)
    if combine is not True:
        return decision("R-FH-1", item, "keep", ["fh-upstream-cannot-combine"], evidence, used=used)
    return decision("R-FH-1", item, "candidate", ["fh-small-records"], evidence,
                    (billed - raw) * rates["firehose_gb"], "월, 올림 손실 상한(첫 구간 요율)", used)


# ---------------------------------------------------------------- R-BR-1 / R-BR-2
CALL_FIELDS = ("call_id", "run_id", "model", "profile", "prefix_hash")
COUNT_FIELDS = ("prefix_tokens", "input_tokens", "cache_read_tokens", "cache_write_tokens", "output_tokens")


def required_hit_ratio(rate, ttl):
    w = rate["write_" + ttl]
    return (w - rate["input"]) / (w - rate["read"])


def assess_bedrock_group(model, prefix_hash, calls, thresholds, rates):
    item = f"{model} | {prefix_hash}"
    used = ["bedrock.supported_profiles", "bedrock.ttl_seconds", "bedrock.min_cache_tokens",
            "bedrock.min_observed_cache_writes"]
    if not all(all(isinstance(c.get(f), str) and c.get(f) for f in CALL_FIELDS)
               and all(is_count(c.get(f)) for f in COUNT_FIELDS)
               and isinstance(c.get("ts"), (int, float)) and not isinstance(c.get("ts"), bool) for c in calls):
        return decision("R-BR-1/2", item, "hold", ["input-invalid"], used=used)
    if model not in rates["bedrock"] or any(c["profile"] not in value(thresholds, "bedrock", "supported_profiles") for c in calls):
        return decision("R-BR-1/2", item, "hold", ["br-rate-unverified"], used=used)
    prefixes = {c["prefix_tokens"] for c in calls}
    if len(prefixes) != 1:
        return decision("R-BR-1/2", item, "hold", ["br-prefix-inconsistent"], used=used)
    (prefix,) = prefixes
    rate = rates["bedrock"][model]
    reads = sum(c["cache_read_tokens"] for c in calls)
    writes = sum(c["cache_write_tokens"] for c in calls)
    ttl_seconds = value(thresholds, "bedrock", "ttl_seconds")

    if reads == 0 and writes == 0:  # R-BR-1: caching not used
        minimum = value(thresholds, "bedrock", "min_cache_tokens").get(model)
        if minimum is None:
            return decision("R-BR-1", item, "hold", ["br-cache-minimum-unknown"], used=used)
        if prefix < minimum:
            return decision("R-BR-1", item, "keep", ["br-below-cache-minimum"],
                            {"prefix_tokens": prefix, "min_cache_tokens": minimum}, used=used)
        per_run = defaultdict(int)
        for c in calls:
            per_run[c["run_id"]] += 1
        ordered = sorted(c["ts"] for c in calls)
        hits = sum(1 for a, b in zip(ordered, ordered[1:]) if b - a < ttl_seconds["5m"])
        n_write, n_read = len(ordered) - hits, hits
        reuse = Decimal(hits) / len(ordered)
        required = required_hit_ratio(rate, "5m")
        evidence = {"calls": len(calls), "runs": len(per_run), "median_calls_per_run": statistics.median(per_run.values()),
                    "prefix_tokens": prefix, "estimated_hit_ratio_5m": str(reuse.quantize(Decimal("0.0001"))),
                    "break_even_hit_ratio_5m": str(required.quantize(Decimal("0.0001")))}
        saving = prefix * (len(ordered) * rate["input"] - n_write * rate["write_5m"] - n_read * rate["read"])
        basis = "관측 기간 전체, 5분 TTL, 앞부분만 캐싱"
        if statistics.median(per_run.values()) >= 2:
            return decision("R-BR-1", item, "candidate", ["br-repeated-within-run"], evidence, saving, basis, used)
        if reuse >= required:
            return decision("R-BR-1", item, "candidate", ["br-reuse-above-break-even"], evidence, saving, basis, used)
        return decision("R-BR-1", item, "keep", ["br-reuse-below-break-even"], evidence, used=used)

    ttls = {c.get("cache_ttl") for c in calls if c["cache_read_tokens"] or c["cache_write_tokens"]}
    if len(ttls) != 1 or next(iter(ttls)) not in ttl_seconds:
        return decision("R-BR-2", item, "hold", ["br-ttl-missing"], used=used)
    (ttl,) = ttls
    write_calls = sum(1 for c in calls if c["cache_write_tokens"])
    if write_calls < value(thresholds, "bedrock", "min_observed_cache_writes"):
        return decision("R-BR-2", item, "hold", ["br-too-few-cache-writes"], {"cache_write_calls": write_calls}, used=used)
    hit = Decimal(reads) / (reads + writes)
    required = required_hit_ratio(rate, ttl)
    evidence = {"cache_ttl": ttl, "cache_write_calls": write_calls, "hit_ratio": str(hit.quantize(Decimal("0.0001"))),
                "break_even_hit_ratio": str(required.quantize(Decimal("0.0001")))}
    if hit < required:
        extra = writes * rate["write_" + ttl] + reads * rate["read"] - (reads + writes) * rate["input"]
        return decision("R-BR-2", item, "candidate", ["br-hit-below-break-even"], evidence, extra,
                        "관측 기간 전체, 캐싱을 끄면 줄어드는 입력 비용", used)
    return decision("R-BR-2", item, "keep", ["br-hit-above-break-even"], evidence, used=used)


def assess_workloads(workloads, thresholds):
    rates = load_rates(thresholds)
    out = [assess_iot_topic(t, thresholds, rates) for t in workloads.get("iot_topics", [])]
    out += [assess_firehose_stream(s, thresholds, rates) for s in workloads.get("firehose_streams", [])]
    groups = defaultdict(list)
    for call in workloads.get("bedrock_calls", []):
        groups[(str(call.get("model")), str(call.get("prefix_hash")))].append(call)
    out += [assess_bedrock_group(m, h, calls, thresholds, rates) for (m, h), calls in sorted(groups.items())]
    return out
