"""Boundary, hold and reproduction tests for R-FH-2, R-ATH-1/2, R-SM-1 and R-COST-1."""
import copy
from datetime import date, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from ops_rules import (assess_buffer, assess_endpoint, assess_notebook, assess_ops, assess_table, cost_series,
                       load_ops_rates)
from workload_rules import load_json

HERE = Path(__file__).resolve().parent
THRESHOLDS = load_json(HERE / "thresholds.json")
RATES = load_ops_rates(THRESHOLDS)
OPS = load_json(HERE / "workloads-ops.json")
MIB = 1024 * 1024


def by_id(rows):
    return {r["id"]: r for r in rows}


def example(section, key, name):
    return copy.deepcopy(next(x for x in OPS[section] if (x["table"]["Name"] if section == "athena_tables" else x[key]) == name))


def with_thresholds(**changes):
    t = copy.deepcopy(THRESHOLDS)
    for dotted, val in changes.items():
        section, key = dotted.split("__")
        t[section][key]["value"] = val
    return t


class BufferRuleTest(unittest.TestCase):
    def stream(self, **kw):
        s = example("firehose_buffers", "DeliveryStreamName", "sensor-raw-60s")
        s.update(kw)
        return s

    def test_reproduces_experiment_017(self):
        row = assess_buffer(self.stream(), THRESHOLDS, RATES)
        self.assertEqual(row["decision"], "candidate")
        self.assertEqual(row["evidence"]["objects_per_day_modeled"], 1440.0)
        self.assertEqual(row["evidence"]["objects_per_day_after"], 96.0)
        self.assertEqual(row["evidence"]["proposed_interval_s"], 900)

    def test_size_or_time_closes_first(self):
        # 5 MiB at 2,000 B/s fills in 2,621 s: an interval just above that is closed by size
        fill = 5 * MIB / 2000
        just_above = self.stream(BufferingHints={"SizeInMBs": 5, "IntervalInSeconds": int(fill) + 1},
                                 s3_objects_daily={"count": round(86400 / fill), "mean_size_bytes": 5 * MIB})
        self.assertEqual(assess_buffer(just_above, THRESHOLDS, RATES)["reasons"], ["fh2-size-closes-first"])
        row = assess_buffer(example("firehose_buffers", "DeliveryStreamName", "sensor-high-rate"), THRESHOLDS, RATES)
        self.assertEqual(row["reasons"], ["fh2-size-closes-first"])

    def test_small_object_boundary(self):
        at = self.stream(s3_objects_daily={"count": 1440, "mean_size_bytes": MIB})
        below = self.stream(s3_objects_daily={"count": 1440, "mean_size_bytes": MIB - 1})
        self.assertEqual(assess_buffer(at, THRESHOLDS, RATES)["reasons"], ["fh2-objects-large-enough"])
        self.assertEqual(assess_buffer(below, THRESHOLDS, RATES)["decision"], "candidate")

    def test_holds(self):
        cases = {
            "fh2-freshness-missing": {"allowed_freshness_s": None},
            "fh2-zero-buffering-not-modeled": {"BufferingHints": {"SizeInMBs": 5, "IntervalInSeconds": 0}},
            "fh2-partitions-unknown": {"dynamic_partitioning": {"enabled": True, "active_partitions": None}},
            "fh2-object-count-unexplained": {"s3_objects_daily": {"count": 5000, "mean_size_bytes": 120_000}},
            "input-invalid": {"IncomingBytes_daily_sum": "lots"},
        }
        for reason, change in cases.items():
            with self.subTest(reason=reason):
                self.assertEqual(assess_buffer(self.stream(**change), THRESHOLDS, RATES)["reasons"], [reason])
        self.assertEqual(assess_buffer(self.stream(allowed_freshness_s=60), THRESHOLDS, RATES)["decision"], "keep")


class AthenaRuleTest(unittest.TestCase):
    def test_reproduces_experiment_018_billing(self):
        rows = by_id(assess_ops(OPS, THRESHOLDS)[0])
        self.assertEqual(rows["sensor_csv_dashboard"]["evidence"]["median_billed_mb"], 250)
        self.assertEqual(rows["sensor_csv_dashboard"]["decision"], "candidate")
        self.assertEqual(rows["sensor_parquet_daily"]["evidence"]["median_billed_mb"], 10)
        self.assertEqual(rows["sensor_parquet_daily"]["reasons"], ["ath-all-at-minimum"])

    def test_10mb_minimum_boundary(self):
        t = example("athena_tables", None, "device_registry_csv")
        for q in t["query_executions"]:
            q["Statistics"]["DataScannedInBytes"] = 10 * MIB
        self.assertEqual(assess_table(t, THRESHOLDS, RATES)["reasons"], ["ath-mostly-minimum"])
        for q in t["query_executions"]:
            q["Statistics"]["DataScannedInBytes"] = 10 * MIB + 1
        self.assertNotIn("ath-mostly-minimum", assess_table(t, THRESHOLDS, RATES)["reasons"])

    def test_only_succeeded_dml_counts(self):
        t = example("athena_tables", None, "sensor_csv_archive")
        for q in t["query_executions"][:25]:
            q["Status"]["State"] = "FAILED"
        self.assertEqual(assess_table(t, THRESHOLDS, RATES)["reasons"], ["ath-too-few-queries"])

    def test_conversion_cost_can_outweigh_saving(self):
        rows = by_id(assess_ops(OPS, THRESHOLDS)[0])
        self.assertEqual(rows["sensor_csv_archive"]["reasons"], ["ath-conversion-not-worth"])

    def test_small_file_boundary_and_compaction(self):
        t = example("athena_tables", None, "sensor_parquet_5min")
        t["files"]["mean_size_bytes"] = MIB
        self.assertEqual(assess_table(t, THRESHOLDS, RATES)["reasons"], ["ath-files-large-enough"])
        rows = by_id(assess_ops(OPS, THRESHOLDS)[0])
        self.assertEqual(rows["sensor_parquet_5min"]["decision"], "candidate")
        self.assertEqual(rows["sensor_parquet_5min_costly_compaction"]["reasons"], ["ath-compaction-not-worth"])
        self.assertEqual(rows["sensor_parquet_5min_no_compaction"]["reasons"], ["ath-compaction-cost-missing"])

    def test_format_detection_holds_unknown(self):
        rows = by_id(assess_ops(OPS, THRESHOLDS)[0])
        self.assertEqual(rows["legacy_custom"]["reasons"], ["ath-format-unknown"])
        broken = example("athena_tables", None, "sensor_csv_archive")
        del broken["query_executions"][0]["Statistics"]
        self.assertEqual(assess_table(broken, THRESHOLDS, RATES)["reasons"], ["input-invalid"])


class SageMakerRuleTest(unittest.TestCase):
    def nb(self, **kw):
        n = example("sagemaker_notebooks", "NotebookInstanceName", "gpu-always-on")
        n.update(kw)
        return n

    def test_reproduces_experiment_022(self):
        row = assess_notebook(self.nb(), THRESHOLDS, RATES)
        self.assertEqual(row["decision"], "candidate")
        self.assertEqual(row["evidence"]["current_to_alternative_ratio"], "19.40")
        self.assertEqual(row["evidence"]["current_usd"], "660.8000")

    def test_busy_share_boundary(self):
        self.assertEqual(assess_notebook(self.nb(activity={"gpu_busy_hours": 72}), THRESHOLDS, RATES)["decision"], "keep")
        self.assertEqual(assess_notebook(self.nb(activity={"gpu_busy_hours": 71.9}), THRESHOLDS, RATES)["decision"], "candidate")

    def test_kernel_hours_used_as_upper_bound(self):
        row = assess_notebook(self.nb(activity={"gpu_busy_hours": None, "kernel_busy_hours": 30}), THRESHOLDS, RATES)
        self.assertTrue(row["evidence"]["busy_basis"].startswith("kernel_busy_hours"))

    def test_notebook_holds(self):
        cases = {"sm-activity-missing": {"activity": {}}, "sm-long-running-unknown": {"long_running_in_notebook": None},
                 "sm-rate-unverified": {"InstanceType": "ml.g5.xlarge"},
                 "input-invalid": {"activity": {"gpu_busy_hours": 800}}}
        for reason, change in cases.items():
            with self.subTest(reason=reason):
                self.assertEqual(assess_notebook(self.nb(**change), THRESHOLDS, RATES)["reasons"], [reason])
        self.assertEqual(assess_notebook(self.nb(long_running_in_notebook=True), THRESHOLDS, RATES)["decision"], "keep")

    def test_endpoint_serverless_comparison(self):
        rows = by_id(assess_ops(OPS, THRESHOLDS)[0])
        self.assertEqual(rows["anomaly-scorer"]["evidence"]["serverless_usd"], "0.8000")
        self.assertEqual(rows["anomaly-scorer"]["decision"], "candidate")
        self.assertEqual(rows["busy-scorer"]["reasons"], ["sm-serverless-not-cheaper"])
        self.assertEqual(rows["gpu-scorer"]["reasons"], ["sm-gpu-serverless-unverified"])
        self.assertEqual(rows["batch-scorer"]["reasons"], ["sm-cold-start-unknown"])
        e = example("sagemaker_endpoints", "EndpointName", "anomaly-scorer")
        e["serverless_memory_gb"] = 3
        self.assertEqual(assess_endpoint(e, THRESHOLDS, RATES)["reasons"], ["sm-rate-unverified"])


def level_shift_series(days_before=28, days_after=40):
    rows = []
    for i in range(days_before + days_after):
        day = (date(2026, 1, 1) + timedelta(days=i)).isoformat()
        rows.append({"TimePeriod": {"Start": day}, "Metrics": {"NetUnblendedCost": {"Amount": "10" if i < days_before else "20"}}})
    return {"service": "shift", "ResultsByTime": rows}


class CostQueueTest(unittest.TestCase):
    def test_history_boundary(self):
        series = level_shift_series(28, 0)
        self.assertEqual(cost_series(series, THRESHOLDS)[1]["reason"], "cost-history-short")
        series["ResultsByTime"].append({"TimePeriod": {"Start": "2026-01-29"}, "Metrics": {"NetUnblendedCost": {"Amount": "30"}}})
        queue, hold = cost_series(series, THRESHOLDS)
        self.assertIsNone(hold)
        self.assertEqual(len(queue), 1)

    def test_reproduces_experiment_021_runaway_and_cap(self):
        kept, _ = cost_series(level_shift_series(), THRESHOLDS)
        self.assertLess(len(kept), 20)
        no_cap = with_thresholds(cost__exclude_alerts=True)
        self.assertEqual(cost_series(level_shift_series(), no_cap)[1]["reason"], "cost-exclusion-without-cap")
        runaway = with_thresholds(cost__exclude_alerts=True, cost__consecutive_cap_days=10 ** 6)
        self.assertEqual(len(cost_series(level_shift_series(), runaway)[0]), 40)
        capped = with_thresholds(cost__exclude_alerts=True, cost__consecutive_cap_days=3)
        self.assertLess(len(cost_series(level_shift_series(), capped)[0]), 40)

    def test_example_queue_and_holds(self):
        _, queue, holds = assess_ops(OPS, THRESHOLDS)
        bedrock = [q for q in queue if q["service"] == "Amazon Bedrock"]
        self.assertEqual([q["date"] for q in bedrock], ["2026-02-20", "2026-03-01"])
        self.assertEqual([q["estimated"] for q in bedrock], [False, True])
        self.assertEqual({h["reason"] for h in holds}, {"cost-history-short", "cost-series-gap"})

    def test_no_daily_costs_means_no_queue(self):
        self.assertEqual(assess_ops({"firehose_buffers": []}, THRESHOLDS)[1:], (None, None))


class ReportTest(unittest.TestCase):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    def run_cli(self, *args):
        return subprocess.check_output([sys.executable, "-B", str(HERE / "cli.py"), *args], encoding="utf-8", env=self.env)

    def test_every_rule_has_candidate_keep_and_hold(self):
        rows = assess_ops(OPS, THRESHOLDS)[0]
        for prefix in ("R-FH-2", "R-ATH", "R-SM-1"):
            seen = {r["decision"] for r in rows if r["rule"].startswith(prefix)}
            self.assertEqual(seen, {"candidate", "keep", "hold"}, prefix)

    def test_one_bad_item_holds_only_itself(self):
        data = copy.deepcopy(OPS)
        data["sagemaker_endpoints"][0]["Invocations_sum"] = -1
        before, after = by_id(assess_ops(OPS, THRESHOLDS)[0]), by_id(assess_ops(data, THRESHOLDS)[0])
        self.assertEqual(after["anomaly-scorer"]["reasons"], ["input-invalid"])
        self.assertEqual({k: v for k, v in before.items() if k != "anomaly-scorer"},
                         {k: v for k, v in after.items() if k != "anomaly-scorer"})

    def test_extra_fields_are_not_echoed(self):
        data = copy.deepcopy(OPS)
        secret = "arn:aws:iam::123456789012:role/secret"
        data["sagemaker_notebooks"][0]["RoleArn"] = secret
        data["athena_tables"][0]["query_executions"][0]["Query"] = f"SELECT '{secret}'"
        self.assertNotIn(secret, json.dumps(assess_ops(data, THRESHOLDS)))

    def test_new_thresholds_carry_evidence(self):
        for section in ("firehose_buffer", "athena", "sagemaker", "cost"):
            for key, entry in THRESHOLDS[section].items():
                with self.subTest(key=key):
                    self.assertIn(entry["evidence"], ("실험 확인", "공식 자료", "임시값"))
                    self.assertTrue(entry["source"])

    def test_cli_combines_workload_files(self):
        both = json.loads(self.run_cli("--json", "--workloads", str(HERE / "workloads.json"), str(HERE / "workloads-ops.json")))
        self.assertEqual(len(both["workload_decisions"]), 17 + 28)
        self.assertIn("investigation_queue", both)
        only_old = json.loads(self.run_cli("--json", "--workloads", str(HERE / "workloads.json")))
        self.assertNotIn("investigation_queue", only_old)
        text = self.run_cli("--workloads", str(HERE / "workloads-ops.json"))
        self.assertIn("비용 급증 조사 대기열", text)
        self.assertIn("(잠정)", text)


if __name__ == "__main__":
    unittest.main()
