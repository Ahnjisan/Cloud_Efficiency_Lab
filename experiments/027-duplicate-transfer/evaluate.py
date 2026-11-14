"""Same data, billed again at every hop: scenario 1 (IoT -> real-time + batch -> agent).

Raw data R = devices x readings x 200 B per month. We follow it through the hops
and add up what each hop bills, in its own unit, then compare designs:

  D0 duplicated : two IoT rules (one per destination), the real-time Lambda logs
                  every reading, the agent tool downloads the last day of raw
                  objects through NAT for every request.
  D1 de-duplicated: one rule with two actions, Lambda logs a 100 B summary per
                  invocation, the agent reads only Athena results and S3 goes
                  through a gateway endpoint (no NAT processing).
"""
from decimal import Decimal as D
from pathlib import Path
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scenarios"))
from pricebook import PriceBook, emit, load_scenario, money  # noqa: E402

GB = D(1024 ** 3)
MB = D(1024 ** 2)
KB5 = 5120

DESIGNS = {
    "D0_duplicated": {"rules": 2, "actions_per_rule": 1, "log_bytes_per_reading": 500,
                      "agent_downloads_last_day_via_nat": True},
    "D1_deduplicated": {"rules": 1, "actions_per_rule": 2, "log_bytes_per_reading": None, "log_bytes_per_invoke": 100,
                        "agent_downloads_last_day_via_nat": False},
}


def volumes(s, d):
    dev, rt, ag = s["devices"], s["realtime"], s["agent"]
    readings = dev["count"] * (s["period"]["days"] * 86400 // dev["interval_s"])
    raw = D(readings * dev["reading_bytes"])
    units = math.ceil(dev["reading_bytes"] / KB5)  # 5 KB metering per message / rule / action / record
    v = {
        "readings": readings, "raw_gb": raw / GB,
        "iot_messages": readings * units,
        "rules_triggered": readings * d["rules"] * units,
        "actions_executed": readings * d["rules"] * d["actions_per_rule"] * units,
        "firehose_billed_gb": D(readings * units * KB5) / GB,
        "lambda_invocations": readings,  # IoT rule Lambda action: one invocation per message
        "lambda_gb_s": D(readings) * D(rt["ms_per_reading"] + rt["fixed_ms_per_invoke"]) / 1000 * D(rt["lambda_memory_mb"]) / 1024,
        "log_gb": (D(readings) * (d["log_bytes_per_reading"] or d.get("log_bytes_per_invoke", 0))) / GB,
        "athena_billed_tb": D(ag["requests_per_month"] * ag["athena_queries_per_request"] * max(10, ag["scan_mb_per_query"])) * MB / D(1024 ** 4),
        "nat_gb": (raw / 30 * ag["requests_per_month"] / GB) if d["agent_downloads_last_day_via_nat"] else D(0),
    }
    return v


def costs(pb, v):
    c = {
        "iot_messages": pb.tiered("AWSIoT", "APN2-Messages", v["iot_messages"]),
        "iot_rules": D(v["rules_triggered"]) * pb.rate("AWSIoT", "APN2-RulesTriggered"),
        "iot_actions": D(v["actions_executed"]) * pb.rate("AWSIoT", "APN2-ActionsExecuted"),
        "firehose_ingest": pb.tiered("AmazonKinesisFirehose", "APN2-BilledBytes", v["firehose_billed_gb"], operation="PutRecord"),
        "lambda": D(v["lambda_invocations"]) * pb.rate("AWSLambda", "APN2-Request") + v["lambda_gb_s"] * pb.rate("AWSLambda", "APN2-Lambda-GB-Second"),
        "logs_ingest": v["log_gb"] * pb.rate("AmazonCloudWatch", "APN2-DataProcessing-Bytes"),
        "logs_storage_first_month": v["log_gb"] * pb.rate("AmazonCloudWatch", "APN2-TimedStorage-ByteHrs"),
        "athena": v["athena_billed_tb"] * pb.rate("AmazonAthena", "APN2-DataScannedInTB"),
        "nat_processing": v["nat_gb"] * pb.rate("AmazonEC2", "APN2-NatGateway-Bytes"),
    }
    return c


def evaluate():
    pb = PriceBook()
    s = load_scenario("iot-pipeline-agent")
    out = {}
    for name, d in DESIGNS.items():
        v = volumes(s, d)
        c = costs(pb, v)
        byte_billed = v["firehose_billed_gb"] + v["log_gb"] + v["athena_billed_tb"] * 1024 + v["nat_gb"]
        out[name] = {
            "design": d,
            "volumes": {k: (str(x.quantize(D("0.0001"))) if isinstance(x, D) else x) for k, x in v.items()},
            "byte_metered_gb_total": str(byte_billed.quantize(D("0.01"))),
            "byte_metered_multiple_of_raw": str((byte_billed / v["raw_gb"]).quantize(D("0.01"))),
            "per_hop_multiple_of_raw": {k: str((x / v["raw_gb"]).quantize(D("0.01"))) for k, x in
                                        (("firehose", v["firehose_billed_gb"]), ("logs", v["log_gb"]),
                                         ("athena", v["athena_billed_tb"] * 1024), ("nat", v["nat_gb"]))},
            "costs_usd": {k: money(x) for k, x in c.items()},
            "total_usd": money(sum(c.values())),
        }
    t0, t1 = D(out["D0_duplicated"]["total_usd"]), D(out["D1_deduplicated"]["total_usd"])
    return {
        "snapshot": pb.data["retrieved"], "designs": out,
        "hypotheses": {
            "H1_byte_metered_volume_ge_10x_raw_in_D0": {
                "result": D(out["D0_duplicated"]["byte_metered_multiple_of_raw"]) >= 10,
                "multiple": out["D0_duplicated"]["byte_metered_multiple_of_raw"]},
            "H2_dedup_cuts_path_cost_ge_30pct": {
                "result": (t0 - t1) / t0 >= D("0.3"), "reduction": str(((t0 - t1) / t0).quantize(D("0.0001"))),
                "d0_usd": str(t0), "d1_usd": str(t1)},
        },
    }


if __name__ == "__main__":
    emit(evaluate())
