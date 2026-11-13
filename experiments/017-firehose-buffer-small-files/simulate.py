"""Firehose buffer hints vs S3 object count, object size and data freshness.

Discrete one-second simulation of one day. Each sensor emits one record per
period as an independent Bernoulli trial per second (seeded). A buffer opens
at its first record and flushes when the buffered bytes reach the size hint or
the interval has elapsed since it opened. Firehose treats hints as hints, so
this is a model of the documented trigger rule, not of the service internals.
"""
from itertools import product
from pathlib import Path
import json
import math
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "references" / "aws-price-list-apn2-2026-11-13.json"
DAY = 86_400
MIB = 1024 * 1024
TAIL = 1_000  # seconds of extra arrivals after the counted day (> max interval)
WORKLOADS = {
    "A_100x10s": {"sensors": 100, "period_s": 10, "record_bytes": 200},
    "B_1000x1s": {"sensors": 1000, "period_s": 1, "record_bytes": 200},
}


def load_s3_rates(path=SNAPSHOT):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))["offers"]["AmazonS3"]["rows"]
    pick = lambda ut: float(next(r["usd"] for r in rows if r["usagetype"] == ut))
    return {"put": pick("APN2-Requests-Tier1"), "get": pick("APN2-Requests-Tier2")}


def arrivals(sensors, period_s, seed, seconds=DAY):
    """Records arriving in each second."""
    rng = random.Random(seed)
    p = 1 / period_s
    if p == 1:
        return [sensors] * seconds
    return [rng.binomialvariate(sensors, p) for _ in range(seconds)]


def run_buffer(counts, record_bytes, size_mib, interval_s, horizon=DAY):
    """Return flushes [(time, bytes, records, trigger)] and record-weighted waits.

    Arrivals continue past `horizon` so the last buffers close the way they
    would in steady state; only buffers opened before `horizon` are counted.
    """
    limit = size_mib * MIB
    flushes, wait_sum, wait_max = [], 0, 0
    opened, buf_bytes, buf_records, buf_time_sum = None, 0, 0, 0

    def close(t, trigger):
        nonlocal wait_sum, wait_max
        if opened < horizon:
            flushes.append((t, buf_bytes, buf_records, trigger))
            wait_sum += t * buf_records - buf_time_sum
            wait_max = max(wait_max, t - opened)

    for t, n in enumerate(counts):
        if opened is not None and t - opened >= interval_s:
            close(t, "interval")
            opened, buf_bytes, buf_records, buf_time_sum = None, 0, 0, 0
        if n:
            if opened is None:
                if t >= horizon:
                    break
                opened = t
            buf_bytes += n * record_bytes
            buf_records += n
            buf_time_sum += n * t
            if buf_bytes >= limit:
                close(t, "size")
                opened, buf_bytes, buf_records, buf_time_sum = None, 0, 0, 0
    if opened is not None and opened < horizon:
        raise RuntimeError("tail too short to close the last buffer")
    records = sum(f[2] for f in flushes)
    return flushes, (wait_sum / records if records else 0.0), wait_max


def summarize(workload, partitions, size_mib, interval_s, seeds, rates):
    w = WORKLOADS[workload]
    if w["sensors"] % partitions:
        raise ValueError("sensors must split evenly across partitions")
    per_seed = []
    for seed in seeds:
        counts = arrivals(w["sensors"] // partitions, w["period_s"], seed, DAY + TAIL)
        flushes, mean_wait, max_wait = run_buffer(counts, w["record_bytes"], size_mib, interval_s)
        objects_day = len(flushes) * partitions
        total_bytes = sum(f[1] for f in flushes) * partitions
        per_seed.append({
            "seed": seed,
            "objects_per_day": objects_day,
            "size_triggered_share": round(sum(f[3] == "size" for f in flushes) / len(flushes), 4),
            "mean_object_kib": round(total_bytes / objects_day / 1024, 2),
            "mean_record_wait_s": round(mean_wait, 2),
            "max_record_wait_s": max_wait,
        })
    objects_month = [r["objects_per_day"] * 30 for r in per_seed]
    mean = lambda key: sum(r[key] for r in per_seed) / len(per_seed)
    return {
        "workload": workload, "partitions": partitions,
        "size_mib": size_mib, "interval_s": interval_s,
        "objects_per_day_range": [min(r["objects_per_day"] for r in per_seed),
                                  max(r["objects_per_day"] for r in per_seed)],
        "objects_per_month_mean": round(sum(objects_month) / len(objects_month)),
        "mean_object_kib": round(mean("mean_object_kib"), 2),
        "size_triggered_share": round(mean("size_triggered_share"), 4),
        "mean_record_wait_s": round(mean("mean_record_wait_s"), 2),
        "max_record_wait_s": max(r["max_record_wait_s"] for r in per_seed),
        "s3_put_usd_month": round(sum(objects_month) / len(objects_month) * rates["put"], 4),
        "get_requests_to_read_one_day": round(mean("objects_per_day")),
        "get_usd_per_one_day_query": round(mean("objects_per_day") * rates["get"], 7),
        "seeds": per_seed,
    }


def main():
    rates = load_s3_rates()
    seeds = (1, 2, 3)
    rows = [summarize(wl, parts, size, interval, seeds, rates)
            for wl, parts, size, interval in product(
                WORKLOADS, (1, 10), (1, 5, 64, 128), (60, 300, 900))]
    get = lambda wl, parts, size, interval: next(
        r for r in rows if (r["workload"], r["partitions"], r["size_mib"], r["interval_s"])
        == (wl, parts, size, interval))
    a_default = [get("A_100x10s", 1, s, i) for s in (5, 64, 128) for i in (60, 300, 900)]
    a60, a900 = get("A_100x10s", 1, 5, 60), get("A_100x10s", 1, 5, 900)
    b = [get("B_1000x1s", 1, 5, i) for i in (60, 300, 900)]
    hypotheses = {
        "H1_A_interval_always_triggers_first": {
            "result": all(r["size_triggered_share"] == 0 for r in rows
                          if r["workload"] == "A_100x10s" and r["partitions"] == 1),
            "exceptions": [{k: r[k] for k in ("size_mib", "interval_s", "size_triggered_share")}
                           for r in rows if r["workload"] == "A_100x10s"
                           and r["partitions"] == 1 and r["size_triggered_share"] > 0],
            "holds_for_size_ge_5mib": all(r["size_triggered_share"] == 0 for r in a_default),
        },
        "H2_A_put_cost_gap_60_vs_900_lt_1usd": {
            "result": a60["s3_put_usd_month"] - a900["s3_put_usd_month"] < 1,
            "gap_usd": round(a60["s3_put_usd_month"] - a900["s3_put_usd_month"], 4)},
        "H3_A_day_query_objects_ratio_60_vs_900_is_15": {
            "result": a60["get_requests_to_read_one_day"] == 15 * a900["get_requests_to_read_one_day"],
            "ratio": round(a60["get_requests_to_read_one_day"] / a900["get_requests_to_read_one_day"], 3)},
        "H4_B_size_triggers_first_at_5mib": {
            "result": all(r["size_triggered_share"] > 0.99 for r in b),
            "objects_per_day": [r["objects_per_day_range"] for r in b]},
    }
    print(json.dumps({
        "model": "1-second Bernoulli arrivals; buffers opened during one simulated day are counted and scaled x30; arrivals continue for a tail so the last buffers close normally; each partition is simulated with the same seed and multiplied by the partition count",
        "s3_rates": rates, "seeds": seeds, "workloads": WORKLOADS,
        "hypotheses": hypotheses, "rows": rows,
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
