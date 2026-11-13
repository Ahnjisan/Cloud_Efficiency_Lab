"""Pipeline cost per 1,000 sensor readings: baseline vs improved, with freshness.

Reads the stored results of experiments 016 (IoT), 017 (Firehose buffers) and
018 (scan proxy) and the Seoul price snapshot. Workload: 100 sensors, one
200 B reading every 10 s, 30 days (25.92 M readings).

Baseline : individual IoT messages, 1 Firehose record per reading, 60 s
           buffer, raw CSV (no partitions), daily Glue crawler.
Improved : 20-reading IoT batches, 1 record per batch, 300 s buffer,
           Firehose Parquet conversion under dt= prefixes, partition projection.
"""
from pathlib import Path
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "experiments"
SNAPSHOT = ROOT / "references" / "aws-price-list-apn2-2026-11-13.json"
READINGS = 100 * (30 * 86_400 // 10)
KB5 = 5 * 1024
GB = 1024 ** 3
MB = 1024 ** 2

# Assumed analysis workload (queries per day by type of 018 query). Not measured.
QUERY_MIX = {"Q1": 100, "Q2": 100, "Q3": 1, "Q4": 10, "Q5": 1}
QUERY_SCALES = (0, 0.1, 1, 10)
CRAWLER = {"dpu": 2, "minutes_per_day": 10}  # pricing-page example DPU, assumed run time


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rates():
    offers = load(SNAPSHOT)["offers"]
    ut = lambda offer, u, begin=0: next(float(r["usd"]) for r in offers[offer]["rows"]
                                        if r["usagetype"] == u and float(r.get("begin") or 0) == begin)
    return {
        "firehose_gb": ut("AmazonKinesisFirehose", "APN2-BilledBytes"),
        "conversion_gb": ut("AmazonKinesisFirehose", "APN2-DFCBilledBytes"),
        "s3_gb_month": ut("AmazonS3", "APN2-TimedStorage-ByteHrs"),
        "athena_tb": ut("AmazonAthena", "APN2-DataScannedInTB"),
        "crawler_dpu_h": ut("AWSGlue", "APN2-Crawler-DPU-Hour"),
    }


def firehose_billed_gb(records, record_bytes):
    return records * math.ceil(record_bytes / KB5) * KB5 / GB


def athena_month(per_query_bytes, scale, rate_tb):
    usd = 0.0
    for q, per_day in QUERY_MIX.items():
        billed_mb = max(10, math.ceil(per_query_bytes[q] / MB))
        usd += per_day * scale * 30 * billed_mb / (1024 * 1024) * rate_tb
    return usd


def compose():
    r = rates()
    iot = load(EXP / "016-iot-message-batching" / "result.json")["headline"]
    fh = load(EXP / "017-firehose-buffer-small-files" / "result.json")["rows"]
    scan = load(EXP / "018-format-partition-scan" / "result.json")
    seed = scan["per_seed"][0]
    row_scale = READINGS / seed["rows_in_table"]
    s3_obj = lambda interval: next(x for x in fh if (x["workload"], x["partitions"], x["size_mib"], x["interval_s"])
                                   == ("A_100x10s", 1, 5, interval))
    q_bytes = lambda layout: {q: max(s["bytes"] for s in (next(x for x in p["scans"] if x["query"] == q and x["layout"] == layout)
                                                          for p in scan["per_seed"])) * row_scale
                              for q in QUERY_MIX}
    stored_gb = lambda layout: seed["storage_bytes"][layout] * row_scale / GB

    configs = {
        "baseline": {"iot": iot["individual"], "records": READINGS, "record_bytes": 200,
                     "conversion": False, "buffer": s3_obj(60), "layout": "csv", "crawler": True,
                     "batch_wait_s": iot["individual"]["max_added_latency_s"]},
        "improved": {"iot": iot["batch20"], "records": READINGS // 20, "record_bytes": 200 * 20,
                     "conversion": True, "buffer": s3_obj(300), "layout": "parquet_dt_5min", "crawler": False,
                     "batch_wait_s": iot["batch20"]["max_added_latency_s"]},
    }
    out = {}
    for name, c in configs.items():
        billed_gb = firehose_billed_gb(c["records"], c["record_bytes"])
        parts = {
            "iot_core": c["iot"]["total_usd"],
            "firehose_ingest": billed_gb * r["firehose_gb"],
            "firehose_format_conversion": billed_gb * r["conversion_gb"] if c["conversion"] else 0.0,
            "s3_put": c["buffer"]["s3_put_usd_month"],
            "s3_storage_one_month_retained": stored_gb(c["layout"]) * r["s3_gb_month"],
            "glue_crawler": (CRAWLER["dpu"] * CRAWLER["minutes_per_day"] / 60 * 30 * r["crawler_dpu_h"]
                             if c["crawler"] else 0.0),
        }
        by_scale = {}
        for scale in QUERY_SCALES:
            p = dict(parts, athena=athena_month(q_bytes(c["layout"]), scale, r["athena_tb"]))
            total = sum(p.values())
            by_scale[str(scale)] = {
                "components_usd": {k: round(v, 4) for k, v in p.items()},
                "total_usd": round(total, 4),
                "usd_per_1000_readings": round(total / READINGS * 1000, 6),
                "largest_component": max(p, key=p.get),
                "iot_share": round(p["iot_core"] / total, 4),
            }
        out[name] = {"layout": c["layout"], "firehose_billed_gb": round(billed_gb, 3),
                     "stored_gb": round(stored_gb(c["layout"]), 3),
                     "freshness_max_s": c["batch_wait_s"] + c["buffer"]["max_record_wait_s"],
                     "freshness_mean_s": round(c["batch_wait_s"] / 2 + c["buffer"]["mean_record_wait_s"], 1),
                     "per_query_bytes_scaled": {k: round(v) for k, v in q_bytes(c["layout"]).items()},
                     "by_query_scale": by_scale}
    central = lambda name: out[name]["by_query_scale"]["1"]
    ratio = {s: round(out["improved"]["by_query_scale"][s]["total_usd"] / out["baseline"]["by_query_scale"][s]["total_usd"], 4)
             for s in map(str, QUERY_SCALES)}
    hypotheses = {
        "H1_iot_messaging_is_largest_and_gt_50pct_of_baseline": {
            "result": central("baseline")["largest_component"] == "iot_core" and central("baseline")["iot_share"] > 0.5,
            "largest": central("baseline")["largest_component"], "iot_share": central("baseline")["iot_share"],
            "by_scale": {s: (v["largest_component"], v["iot_share"]) for s, v in out["baseline"]["by_query_scale"].items()}},
        "H2_improved_le_20pct_of_baseline": {"result": ratio["1"] <= 0.20, "ratio_by_query_scale": ratio},
        "H3_freshness_max_60s_to_about_490s": {
            "result": (out["baseline"]["freshness_max_s"], out["improved"]["freshness_max_s"]) == (60, 490),
            "baseline_s": out["baseline"]["freshness_max_s"], "improved_s": out["improved"]["freshness_max_s"]},
    }
    return {"readings_per_month": READINGS, "rates": r, "query_mix_per_day": QUERY_MIX,
            "query_scales": QUERY_SCALES, "crawler_assumption": CRAWLER, "row_scale_from_018": row_scale,
            "hypotheses": hypotheses, "configs": out}


def main():
    print(json.dumps(compose(), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
