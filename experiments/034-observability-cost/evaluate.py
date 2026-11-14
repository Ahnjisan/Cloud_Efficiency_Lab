"""The cost of measuring: metric dimensions, EMF log events, and log retention.

CloudWatch counts every unique combination of metric name and dimension values
as a separate custom metric, prorated by the hour it receives data. EMF writes a
log event per record (log ingest + storage) and the metrics it declares.
"""
from decimal import Decimal as D
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scenarios"))
from pricebook import PriceBook, emit, load_scenario, money  # noqa: E402

GB = D(1024 ** 3)
EMF_BYTES_PER_RECORD = 300   # assumed JSON size of one EMF event incl. _aws metadata
STORAGE_COMPRESSION = D(1)   # stored GB / ingested GB; compression of stored logs not confirmed -> upper bound


def metric_designs(s):
    dev = s["devices"]["count"]
    per = s["observability"]["metrics_per_device"]
    return {
        "A_aggregate_plus_group": {"desc": "3 metrics without dimensions + 3 metrics x DeviceGroup(5)",
                                   "metric_hours_share": [(per, 1), (per * 5, 1)]},
        "B_per_device": {"desc": "3 metrics x DeviceId(100)", "metric_hours_share": [(per * dev, 1)]},
        "C_high_cardinality_agent": {"desc": "agent: 2 metrics x Tool(10) x Model(2) x User(500), each user active 2 h/day",
                                     "metric_hours_share": [(2 * 10 * 2 * 500, D(2) / D(24))]},
    }


def metric_cost(pb, design):
    billed = sum(D(n) * D(share) for n, share in design["metric_hours_share"])
    return billed, pb.tiered("AmazonCloudWatch", "APN2-CW:MetricMonitorUsage", billed)


def emf_cost(pb, s):
    dev = s["devices"]
    records = dev["count"] * (s["period"]["days"] * 86400 // dev["interval_s"])
    gb = D(records * EMF_BYTES_PER_RECORD) / GB
    ingest = gb * pb.rate("AmazonCloudWatch", "APN2-DataProcessing-Bytes")
    store = gb * STORAGE_COMPRESSION * pb.rate("AmazonCloudWatch", "APN2-TimedStorage-ByteHrs")
    return {"records": records, "ingest_gb": str(gb.quantize(D("0.01"))), "ingest_usd": money(ingest),
            "storage_first_month_usd": money(store)}


def retention(pb, gb_per_month, months=36):
    ing = pb.rate("AmazonCloudWatch", "APN2-DataProcessing-Bytes")
    st = pb.rate("AmazonCloudWatch", "APN2-TimedStorage-ByteHrs")
    rows, cum_inf, cum_30 = [], D(0), D(0)
    cross = None
    for m in range(1, months + 1):
        stored_inf = D(gb_per_month) * m * STORAGE_COMPRESSION
        stored_30 = D(gb_per_month) * STORAGE_COMPRESSION
        cum_inf += stored_inf * st
        cum_30 += stored_30 * st
        if cross is None and stored_inf * st > D(gb_per_month) * ing:
            cross = m
        if m in (1, 6, 12, 24, 36):
            rows.append({"month": m, "ingest_usd": money(D(gb_per_month) * ing),
                         "storage_usd_infinite": money(stored_inf * st), "storage_usd_30d": money(stored_30 * st),
                         "cumulative_storage_usd_infinite": money(cum_inf), "cumulative_storage_usd_30d": money(cum_30)})
    return rows, cross


def evaluate():
    pb = PriceBook()
    s = load_scenario("iot-pipeline-agent")
    designs = {}
    for name, d in metric_designs(s).items():
        n, c = metric_cost(pb, d)
        designs[name] = {"desc": d["desc"], "billed_metric_months": str(n.quantize(D("0.01"))), "usd": money(c)}
    emf = emf_cost(pb, s)
    rows, cross = retention(pb, s["observability"]["log_gb_per_month"])
    a, b, c = (D(designs[k]["usd"]) for k in ("A_aggregate_plus_group", "B_per_device", "C_high_cardinality_agent"))
    return {
        "snapshot": pb.data["retrieved"],
        "assumptions": {"emf_bytes_per_record": EMF_BYTES_PER_RECORD, "stored_to_ingested_ratio": str(STORAGE_COMPRESSION),
                        "log_gb_per_month": s["observability"]["log_gb_per_month"]},
        "metric_designs": designs, "emf_per_reading": emf,
        "retention": rows, "storage_exceeds_ingest_from_month": cross,
        "hypotheses": {
            "H1_high_cardinality_ge_10x_aggregate": {"result": c >= 10 * a, "ratio": str((c / a).quantize(D("0.1")))},
            "H2_infinite_retention_storage_exceeds_ingest_within_12_months": {"result": cross is not None and cross <= 12,
                                                                              "crossover_month": cross},
            "H3_per_device_metric_charge_exceeds_emf_ingest": {"result": b > D(emf["ingest_usd"]),
                                                               "per_device_metrics_usd": str(b), "emf_ingest_usd": emf["ingest_usd"]},
        },
    }


if __name__ == "__main__":
    emit(evaluate())
