"""Scanned-bytes proxy for CSV, CSV.gz, Parquet and partitioned Parquet.

The same synthetic sensor table is written in four layouts to a temporary
directory. For five representative queries the script computes the bytes an
engine like Athena would have to read:

* CSV / CSV.gz: every file the query cannot prune by partition (no column
  pruning; compressed bytes for gzip).
* Parquet: for each file not pruned by partition, each row group whose
  min/max statistics do not exclude the filter, the compressed size of the
  column chunks the query references. Footers and page indexes are ignored.

This is a proxy, not an Athena measurement. Billed bytes apply Athena's
rounding to the next MB with a 10 MB minimum per query.
"""
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import gzip
import json
import math
import random
import sys
import tempfile

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.dataset as ds
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "references" / "aws-price-list-apn2-2026-11-13.json"
START = datetime(2026, 1, 1)  # synthetic calendar (naive, treated as UTC), not a real project date
MB = 1024 * 1024
TB_MB = 1024 * 1024
LAYOUTS = ("csv", "csv_gz", "parquet", "parquet_dt_5min", "parquet_dt_zone")
PARTITION_KEYS = {"parquet_dt_5min": ("dt",), "parquet_dt_zone": ("dt", "zone")}
BUCKET_S = 300  # Firehose-like 300 s buffer objects


def athena_rate(path=SNAPSHOT):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))["offers"]["AmazonAthena"]["rows"]
    return float(next(r["usd"] for r in rows if r["usagetype"] == "APN2-DataScannedInTB"))


def generate(sensors, zones, days, period_s, seed):
    """Synthetic readings sorted by time, as Firehose would deliver them."""
    rng = random.Random(seed)
    steps = days * 86_400 // period_s
    sensor_zone = [i % zones for i in range(sensors)]
    zone_offset = [rng.uniform(-3, 3) for _ in range(zones)]
    battery = [rng.uniform(80, 100) for _ in range(sensors)]
    ts, sid, zone, temp, hum, vib, bat, status = ([] for _ in range(8))
    for step in range(steps):
        t = START + timedelta(seconds=step * period_s)
        daily = math.sin(2 * math.pi * (step * period_s % 86_400) / 86_400)
        for s in range(sensors):
            z = sensor_zone[s]
            v = rng.lognormvariate(0, 0.4)
            battery[s] = max(0.0, battery[s] - rng.uniform(0, 0.0006))
            ts.append(t)
            sid.append(f"s{s:03d}")
            zone.append(f"z{z:02d}")
            temp.append(round(21 + zone_offset[z] + 3 * daily + rng.gauss(0, 0.5), 2))
            hum.append(round(55 - 8 * daily + rng.gauss(0, 2), 1))
            vib.append(round(v, 3))
            bat.append(round(battery[s], 2))
            status.append("warn" if v > 2.5 else "ok")
    return pa.table({
        "ts": pa.array(ts, pa.timestamp("s")), "sensor_id": sid, "zone": zone,
        "temperature": temp, "humidity": hum, "vibration": vib, "battery": bat, "status": status,
    })


def day_of(table):
    return pc.strftime(table["ts"], format="%Y-%m-%d")


def write_layouts(table, base, rows_per_bucket):
    base = Path(base)
    days = sorted(set(day_of(table).to_pylist()))
    files = {layout: [] for layout in LAYOUTS}
    dcol = day_of(table)
    for d in days:
        part = table.filter(pc.equal(dcol, d))
        buf = pa.BufferOutputStream()
        pacsv.write_csv(part, buf)
        raw = buf.getvalue().to_pybytes()
        for layout, data, name in (("csv", raw, f"{d}.csv"), ("csv_gz", gzip.compress(raw, 6, mtime=0), f"{d}.csv.gz")):
            path = base / layout / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            files[layout].append({"path": path, "dt": d, "zone": None})
        path = base / "parquet" / f"{d}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(part, path, compression="snappy")
        files["parquet"].append({"path": path, "dt": d, "zone": None})
        if part.num_rows % rows_per_bucket:
            raise ValueError("readings must fill 300 s buckets evenly")
        for i, off in enumerate(range(0, part.num_rows, rows_per_bucket)):
            path = base / "parquet_dt_5min" / f"dt={d}" / f"part-{i:03d}.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(part.slice(off, rows_per_bucket), path, compression="snappy")
            files["parquet_dt_5min"].append({"path": path, "dt": d, "zone": None})
        zcol = part["zone"]
        for z in sorted(set(zcol.to_pylist())):
            zpart = part.filter(pc.equal(zcol, z)).drop_columns(["zone"])
            path = base / "parquet_dt_zone" / f"dt={d}" / f"zone={z}" / "part-0.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(zpart, path, compression="snappy")
            files["parquet_dt_zone"].append({"path": path, "dt": d, "zone": z})
    return files


def queries(days):
    first = START.date()
    mid = (first + timedelta(days=days // 2)).isoformat()
    last = (first + timedelta(days=days - 1)).isoformat()
    last_hour_start = START + timedelta(days=days) - timedelta(hours=1)
    return [
        {"id": "Q1", "sql": f"SELECT avg(temperature) FROM t WHERE dt='{mid}' AND zone='z03'",
         "columns": {"temperature"}, "dt": {mid}, "zone": {"z03"}, "ts_min": None},
        {"id": "Q2", "sql": "SELECT sensor_id, max(vibration) FROM t WHERE ts >= <last hour> GROUP BY sensor_id",
         "columns": {"sensor_id", "vibration"}, "dt": {last}, "zone": None, "ts_min": last_hour_start},
        {"id": "Q3", "sql": "SELECT dt, avg(humidity) FROM t GROUP BY dt",
         "columns": {"humidity"}, "dt": None, "zone": None, "ts_min": None},
        {"id": "Q4", "sql": f"SELECT * FROM t WHERE dt='{mid}' AND sensor_id='s013'",
         "columns": "*", "dt": {mid}, "zone": None, "ts_min": None, "sensor": "s013"},
        {"id": "Q5", "sql": "SELECT zone, count(*) FROM t WHERE status='warn' GROUP BY zone",
         "columns": {"status"}, "dt": None, "zone": None, "ts_min": None},
    ]


def stats_exclude(rg, col_index, op, value):
    st = rg.column(col_index).statistics
    if st is None or not st.has_min_max:
        return False
    if op == "eq":
        return value < st.min or value > st.max
    if op == "ge":
        return st.max < value
    if op == "lt":
        return st.min >= value
    raise ValueError(op)


def scan_bytes(query, layout, files):
    """Proxy bytes read and files opened for one query on one layout.

    Parquet bytes = footer of every file not pruned by partition (needed to read
    statistics) + compressed column chunks of row groups not excluded by stats.
    """
    keys = PARTITION_KEYS.get(layout, ())
    total, opened = 0, 0
    for f in files:
        if "dt" in keys and query["dt"] is not None and f["dt"] not in query["dt"]:
            continue
        if "zone" in keys and query["zone"] is not None and f["zone"] not in query["zone"]:
            continue
        if layout in ("csv", "csv_gz"):
            total += f["path"].stat().st_size
            opened += 1
            continue
        meta = pq.ParquetFile(f["path"]).metadata
        names = [meta.schema.column(i).name for i in range(meta.num_columns)]
        filters = []
        if "dt" not in keys and query["dt"] is not None:
            lo = min(datetime.fromisoformat(d) for d in query["dt"])
            filters += [("ts", "ge", lo), ("ts", "lt", lo + timedelta(days=1))]
        if "zone" not in keys and query["zone"] is not None:
            filters += [("zone", "eq", z) for z in query["zone"]]
        if query["ts_min"] is not None:
            filters.append(("ts", "ge", query["ts_min"]))
        if query.get("sensor"):
            filters.append(("sensor_id", "eq", query["sensor"]))
        wanted = set(names) if query["columns"] == "*" else (
            (set(query["columns"]) | {c for c, _, _ in filters}) & set(names))
        total += meta.serialized_size + 8  # footer + length + magic
        opened += 1
        for r in range(meta.num_row_groups):
            rg = meta.row_group(r)
            if any(stats_exclude(rg, names.index(c), op, v) for c, op, v in filters):
                continue
            total += sum(rg.column(names.index(c)).total_compressed_size for c in wanted)
    return total, opened


def billed(bytes_read, rate):
    mb = max(10, math.ceil(bytes_read / MB))
    return mb, mb / TB_MB * rate


def check_answers(table, base, qs):
    """The partitioned layout must give the same answers as the full table."""
    part = ds.dataset(Path(base) / "parquet_dt_zone", format="parquet", partitioning="hive")
    q1, q4 = qs[0], qs[3]
    (mid,) = q1["dt"]
    truth = table.filter(pc.and_(pc.equal(day_of(table), mid), pc.equal(table["zone"], "z03")))
    got = part.to_table(filter=(ds.field("dt") == mid) & (ds.field("zone") == "z03"), columns=["temperature"])
    t4 = table.filter(pc.and_(pc.equal(day_of(table), mid), pc.equal(table["sensor_id"], "s013")))
    g4 = part.to_table(filter=(ds.field("dt") == mid) & (ds.field("sensor_id") == "s013"))
    return {
        "Q1_rows_match": truth.num_rows == got.num_rows,
        "Q1_mean_match": abs(pc.mean(truth["temperature"]).as_py() - pc.mean(got["temperature"]).as_py()) < 1e-9,
        "Q4_rows_match": t4.num_rows == g4.num_rows,
    }


def run(sensors=100, zones=10, days=30, period_s=60, seeds=(1, 2, 3)):
    rate = athena_rate()
    per_seed = []
    for seed in seeds:
        table = generate(sensors, zones, days, period_s, seed)
        with tempfile.TemporaryDirectory() as tmp:
            files = write_layouts(table, tmp, sensors * BUCKET_S // period_s)
            qs = queries(days)
            storage = {layout: sum(f["path"].stat().st_size for f in fs) for layout, fs in files.items()}
            rows = []
            for q in qs:
                for layout in LAYOUTS:
                    b, opened = scan_bytes(q, layout, files[layout])
                    mb, usd = billed(b, rate)
                    rows.append({"query": q["id"], "layout": layout, "bytes": b, "files_opened": opened,
                                 "billed_mb": mb, "usd": usd})
            per_seed.append({"seed": seed, "rows_in_table": table.num_rows, "storage_bytes": storage,
                             "answers": check_answers(table, tmp, qs), "scans": rows,
                             "file_counts": {k: len(v) for k, v in files.items()}})
    return {"rate_usd_per_tb": rate, "queries": [{k: q[k] for k in ("id", "sql")} for q in queries(days)],
            "config": {"sensors": sensors, "zones": zones, "days": days, "period_s": period_s,
                       "seeds": list(seeds), "parquet_compression": "snappy", "gzip_level": 6},
            "per_seed": per_seed}


def summarize(result):
    seeds = result["per_seed"]
    summary = {}
    for q in (q["id"] for q in result["queries"]):
        summary[q] = {}
        for layout in LAYOUTS:
            vals = [next(r for r in s["scans"] if r["query"] == q and r["layout"] == layout) for s in seeds]
            summary[q][layout] = {
                "bytes_min": min(v["bytes"] for v in vals), "bytes_max": max(v["bytes"] for v in vals),
                "files_opened": vals[0]["files_opened"],
                "billed_mb_max": max(v["billed_mb"] for v in vals),
            }
        csv_max = summary[q]["csv"]["bytes_max"]
        for layout in LAYOUTS[1:]:
            summary[q][layout]["reduction_vs_csv_min"] = round(1 - summary[q][layout]["bytes_max"] / csv_max, 4)
    red = lambda q, layout: summary[q][layout]["reduction_vs_csv_min"]
    hypotheses = {
        "H1_Q1_partitioned_parquet_reduces_ge_90pct": {"result": red("Q1", "parquet_dt_zone") >= 0.90,
                                                       "reduction": red("Q1", "parquet_dt_zone")},
        "H2_Q4_reduction_smaller_than_Q1": {"result": red("Q4", "parquet_dt_zone") < red("Q1", "parquet_dt_zone"),
                                            "Q4": red("Q4", "parquet_dt_zone"), "Q1": red("Q1", "parquet_dt_zone")},
        "H3_all_parquet_queries_billed_at_10MB_minimum": {
            "result": all(summary[q][l]["billed_mb_max"] == 10 for q in summary for l in ("parquet", "parquet_dt_zone")),
            "above_minimum": [(q, l, summary[q][l]["billed_mb_max"]) for q in summary
                              for l in ("parquet", "parquet_dt_zone") if summary[q][l]["billed_mb_max"] > 10]},
    }
    return {"summary": summary, "hypotheses": hypotheses}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--small", action="store_true", help="tiny configuration for smoke tests")
    args = parser.parse_args(argv)
    result = run(sensors=20, zones=4, days=3, period_s=600, seeds=(1,)) if args.small else run()
    result.update(summarize(result))
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
