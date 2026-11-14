"""Design-stage architecture cost model (prototype).

An architecture is a list of components. Each component has a service, the
drivers (quantities) it needs, and a cost function that returns
  billed : what the bill would show (with rounding, minimums, always-on hours)
  usage  : 'rate x actual usage' with no rounding or floor (None if unknowable)
  fixed  : True when the charge accrues per hour regardless of traffic
Leak-pattern flags are derived from these three numbers, not hand-assigned.
"""
from decimal import Decimal as D
from pathlib import Path
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scenarios"))
from pricebook import HOURS_PER_MONTH as H  # noqa: E402
from service_pack import billed_units, fargate_provision  # noqa: E402

GB = D(1024 ** 3)
MB = D(1024 ** 2)
KB5 = 5120


def c(name, service, billed, usage=None, fixed=False, unit_note=""):
    return {"name": name, "service": service, "billed": D(billed), "usage": None if usage is None else D(usage),
            "fixed": fixed, "note": unit_note}


# ---- component cost functions -------------------------------------------------

def iot_core(pb, messages, message_bytes, rules=1, actions_per_rule=1, devices=0, minutes=0):
    units = math.ceil(message_bytes / KB5)
    metered = messages * units
    raw_units = D(messages * message_bytes) / KB5
    msg = pb.tiered("AWSIoT", "APN2-Messages", metered)
    msg_usage = pb.tiered("AWSIoT", "APN2-Messages", raw_units)
    ra = (D(metered) * rules * pb.rate("AWSIoT", "APN2-RulesTriggered")
          + D(metered) * rules * actions_per_rule * pb.rate("AWSIoT", "APN2-ActionsExecuted"))
    conn = D(devices * minutes) * pb.rate("AWSIoT", "APN2-ConnectionMinutes")
    return [c("IoT messages", "AWSIoT", msg, msg_usage, unit_note="5 KB metering"),
            c("IoT rules+actions", "AWSIoT", ra, ra),
            c("IoT connection", "AWSIoT", conn, conn)]


def firehose(pb, records, record_bytes, conversion=False):
    billed_gb = D(records * math.ceil(record_bytes / KB5) * KB5) / GB
    raw_gb = D(records * record_bytes) / GB
    out = [c("Firehose ingest", "AmazonKinesisFirehose", pb.tiered("AmazonKinesisFirehose", "APN2-BilledBytes", billed_gb, operation="PutRecord"),
             pb.tiered("AmazonKinesisFirehose", "APN2-BilledBytes", raw_gb, operation="PutRecord"), unit_note="5 KB per record")]
    if conversion:
        rate = pb.rate("AmazonKinesisFirehose", "APN2-DFCBilledBytes")
        out.append(c("Firehose format conversion", "AmazonKinesisFirehose", billed_gb * rate, raw_gb * rate))
    return out


def s3(pb, puts, stored_gb):
    put = D(puts) * pb.rate("AmazonS3", "APN2-Requests-Tier1")
    st = pb.tiered("AmazonS3", "APN2-TimedStorage-ByteHrs", stored_gb)
    return [c("S3 PUT", "AmazonS3", put, put), c("S3 storage (1 month)", "AmazonS3", st, st)]


def glue_dpu(pb, name, dpu, hours, usagetype="APN2-ETL-DPU-Hour"):
    v = D(dpu) * D(hours) * pb.rate("AWSGlue", usagetype)
    return [c(name, "AWSGlue", v, v)]


def athena(pb, query_bytes_counts):
    """query_bytes_counts: list of (bytes_per_query, queries)."""
    tb = pb.rate("AmazonAthena", "APN2-DataScannedInTB")
    billed = sum(billed_units("athena_scan", b) * D(n) for b, n in query_bytes_counts) / D(1024 * 1024) * tb
    usage = sum(D(b) / MB * D(n) for b, n in query_bytes_counts) / D(1024 * 1024) * tb
    return [c("Athena scans", "AmazonAthena", billed, usage, unit_note="1 MB rounding, 10 MB minimum")]


def lambda_fn(pb, invocations, ms, memory_mb):
    gb_s = D(invocations) * D(ms) / 1000 * D(memory_mb) / 1024
    v = D(invocations) * pb.rate("AWSLambda", "APN2-Request") + pb.tiered("AWSLambda", "APN2-Lambda-GB-Second", gb_s)
    return [c("Lambda", "AWSLambda", v, v)]


def bedrock_tokens(pb, model, tokens):
    """tokens: dict in/out/cache_read/cache_write per month."""
    uts = ({"in": "APN2-MP:APN2_InputTokenCount_Global-Units", "out": "APN2-MP:APN2_OutputTokenCount_Global-Units"}
           if "4.5" in model else
           {"in": "APN2-MP:APN2_input_tokens_global_standard-Units", "out": "APN2-MP:APN2_output_tokens_global_standard-Units"})
    v = sum(D(tokens[k]) * pb.rate("AmazonBedrockFoundationModels", ut, model=model) for k, ut in uts.items()) / D(10 ** 6)
    return [c(f"Bedrock {model} tokens", "AmazonBedrockFoundationModels", v, v)]


def guardrails(pb, requests, chars_in, chars_out, policies):
    units = billed_units("guardrails_text_unit", chars_in) + billed_units("guardrails_text_unit", chars_out)
    raw = D(chars_in + chars_out) / 1000
    rate = sum(pb.rate("AmazonBedrock", f"APN2-Guardrail-{p}UnitsConsumed") for p in policies)
    return [c("Bedrock Guardrails", "AmazonBedrock", units * rate * requests, raw * rate * requests, unit_note="1,000-char units")]


def opensearch_classic(pb, needed_ocu=None):
    ocu = pb.rate("AmazonES", "APN2-IndexingOCU") * H
    return [c("OpenSearch Serverless Classic (min 2 OCU)", "AmazonES", 2 * ocu,
              None if needed_ocu is None else D(needed_ocu) * ocu, fixed=True)]


def nat(pb, gateways, gb):
    fixed = D(gateways) * pb.rate("AmazonEC2", "APN2-NatGateway-Hours") * H
    proc = D(gb) * pb.rate("AmazonEC2", "APN2-NatGateway-Bytes")
    return [c("NAT gateway hours", "AmazonEC2", fixed, fixed, fixed=True), c("NAT processing", "AmazonEC2", proc, proc)]


def logs(pb, gb):
    v = D(gb) * pb.rate("AmazonCloudWatch", "APN2-DataProcessing-Bytes")
    s = D(gb) * pb.rate("AmazonCloudWatch", "APN2-TimedStorage-ByteHrs")
    return [c("CloudWatch Logs ingest", "AmazonCloudWatch", v, v), c("CloudWatch Logs storage (month 1)", "AmazonCloudWatch", s, s)]


def metrics(pb, n):
    v = pb.tiered("AmazonCloudWatch", "APN2-CW:MetricMonitorUsage", n)
    return [c("CloudWatch custom metrics", "AmazonCloudWatch", v, v, fixed=True)]


def api_http(pb, requests):
    v = pb.tiered("AmazonApiGateway", "APN2-ApiGatewayHttpRequest", requests)
    return [c("API Gateway HTTP", "AmazonApiGateway", v, v)]


def ecs_fargate(pb, tasks, vcpu, mem_gb):
    pv, pm = fargate_provision(vcpu, mem_gb, "ecs")
    rate = lambda v, m: (v * pb.rate("AmazonECS", "APN2-Fargate-vCPU-Hours:perCPU") + m * pb.rate("AmazonECS", "APN2-Fargate-GB-Hours")) * H * tasks
    return [c("ECS Fargate tasks", "AmazonECS", rate(pv, pm), rate(D(str(vcpu)), D(str(mem_gb))), fixed=True)]


def rds(pb, cls, engine, storage_gb):
    inst = pb.rate("AmazonRDS", f"APN2-InstanceUsage:{cls}", databaseEngine=engine) * H
    st = D(storage_gb) * pb.rate("AmazonRDS", "APN2-RDS:GP3-Storage", databaseEngine=engine)
    return [c("RDS instance", "AmazonRDS", inst, inst, fixed=True), c("RDS storage", "AmazonRDS", st, st, fixed=True)]


def cache_serverless(pb, engine, data_gb, requests, kb_per_request=1):
    floor = D("0.1") if engine == "Valkey" else D(1)
    rate = pb.rate("AmazonElastiCache", f"APN2-CachedData:{engine}") * H
    ecpu = D(requests * kb_per_request) * pb.rate("AmazonElastiCache", f"APN2-ElastiCacheProcessingUnits:{engine}")
    return [c(f"ElastiCache serverless {engine} storage", "AmazonElastiCache", max(D(str(data_gb)), floor) * rate, D(str(data_gb)) * rate, fixed=True),
            c(f"ElastiCache serverless {engine} ECPU", "AmazonElastiCache", ecpu, ecpu)]


# ---- evaluation ---------------------------------------------------------------

def flags(comp):
    f = []
    if comp["usage"] is None:
        f.append("usage_unknown")
    elif comp["billed"] > 0:
        excess = (comp["billed"] - comp["usage"]) / comp["billed"]
        if excess >= D("0.5"):
            f.append("minimum_or_rounding_ge_50pct")
    if comp["fixed"]:
        f.append("always_on")
    return f


def summarize(components, units=None, unit_label=None):
    total = sum(x["billed"] for x in components)
    rows = []
    for x in components:
        rows.append({"name": x["name"], "service": x["service"], "billed_usd": str(x["billed"].quantize(D("0.0001"))),
                     "usage_usd": None if x["usage"] is None else str(x["usage"].quantize(D("0.0001"))),
                     "share": str((x["billed"] / total).quantize(D("0.0001"))) if total else "0", "flags": flags(x)})
    flagged = sum(x["billed"] for x in components if flags(x))
    out = {"total_usd": str(total.quantize(D("0.01"))), "components": rows,
           "flagged_share": str((flagged / total).quantize(D("0.0001"))) if total else "0"}
    if units:
        out[f"usd_per_{unit_label}"] = str((total / D(units)).quantize(D("0.000001")))
    return out
