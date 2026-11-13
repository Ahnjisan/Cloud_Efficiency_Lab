"""Tests for infrafit/collect.py with a fake aws CLI (convert-examples/fake_aws.py). No AWS call is made."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ops_rules import assess_ops  # noqa: E402
from workload_rules import assess_workloads  # noqa: E402

EX = HERE / "convert-examples"
FAKE = json.dumps([sys.executable, "-B", str(EX / "fake_aws.py")])
THRESHOLDS = json.loads((HERE / "thresholds.json").read_text(encoding="utf-8"))
PERIOD = ["--start", "2026-01-01", "--end", "2026-01-31"]


class Run:
    def __init__(self, *extra, env=None, out_inside=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.out = out_inside or self.dir / "raw"
        self.log = self.dir / "aws.log"
        e = {**os.environ, "FAKE_AWS_LOG": str(self.log), **(env or {})}
        argv = [sys.executable, "-B", str(HERE / "collect.py"), "--out", str(self.out), "--aws-cmd", FAKE, *PERIOD, *extra]
        self.proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", env=e)

    @property
    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def ops(self):
        return [" ".join(c[:2]) for c in self.calls]

    @property
    def summary(self):
        return json.loads((self.out / "collect-summary.json").read_text(encoding="utf-8"))

    def close(self):
        self.tmp.cleanup()


class CollectTests(unittest.TestCase):
    def run_collect(self, *extra, **kw):
        r = Run(*extra, **kw)
        self.addCleanup(r.close)
        return r

    def test_dry_run_makes_no_call(self):
        r = self.run_collect("--dry-run", "--glue-databases", "sensors")
        self.assertEqual(r.proc.returncode, 0, r.proc.stderr)
        plan = json.loads(r.proc.stdout)
        self.assertEqual((r.calls, plan["aws_calls_made"]), ([], 0))
        self.assertEqual(plan["worst_case_usd"], "0.035000")  # 3 CE requests + 500 metrics
        self.assertFalse(r.out.exists())

    def test_without_yes_only_free_calls(self):
        r = self.run_collect("--glue-databases", "sensors")
        self.assertEqual(r.proc.returncode, 0, r.proc.stderr)
        self.assertEqual(r.summary["status"], "stopped-before-paid-phase")
        self.assertFalse({"ce get-cost-and-usage", "cloudwatch get-metric-data", "s3 cp"} & set(r.ops()))
        self.assertEqual(r.summary["estimated_usd"]["total_excluding_glue_free_tier"], "0.000000")

    def test_full_run_with_yes(self):
        r = self.run_collect("--glue-databases", "sensors", "--yes")
        self.assertEqual(r.proc.returncode, 0, r.proc.stderr)
        s = r.summary
        self.assertEqual(s["status"], "complete")
        self.assertEqual(s["paid_units"]["cost_explorer_requests"], 2)   # two pages, NextPageToken followed
        self.assertEqual(s["paid_units"]["get_metric_data_metrics"], 3)  # 1 stream + 2 per endpoint variant
        self.assertEqual(s["estimated_usd"]["total_excluding_glue_free_tier"], "0.020030")
        self.assertEqual(s["resource_counts"]["athena_queries_in_period"], 242)
        self.assertTrue(all(c[c.index("--profile") + 1] == "cel-readonly" for c in r.calls))
        ce = next(c for c in r.calls if c[:2] == ["ce", "get-cost-and-usage"])
        self.assertEqual(ce[ce.index("--region") + 1], "us-east-1")
        self.assertTrue((r.out / "requests.log").exists())

    def test_batches_of_50(self):
        r = self.run_collect("--services", "athena")
        sizes = [len(c) - c.index("--query-execution-ids") - 1 - 6 for c in r.calls if c[1] == "batch-get-query-execution"]
        self.assertEqual(sizes, [50, 50, 50, 50, 42])
        self.assertNotIn("aws-error", [w["code"] for w in r.summary["warnings"]])

    def test_period_filter(self):
        r = self.run_collect("--services", "athena", "--start", "2026-01-02", "--end", "2026-01-31")
        counts = r.summary["resource_counts"]
        self.assertEqual((counts["athena_queries_in_period"], counts["athena_queries_outside_period"]), (29, 213))

    def test_metric_cap_stops_before_paid_calls(self):
        r = self.run_collect("--services", "firehose,cloudwatch", "--yes", "--max-metrics", "2",
                             env={"FAKE_AWS_EXTRA_STREAMS": "2"})
        self.assertEqual(r.proc.returncode, 1)
        self.assertEqual(r.summary["status"], "stopped-cap-exceeded")
        self.assertNotIn("cloudwatch get-metric-data", r.ops())

    def test_ce_cap_truncates_pages(self):
        r = self.run_collect("--services", "cost", "--yes", "--max-ce-requests", "1")
        self.assertEqual(r.ops().count("ce get-cost-and-usage"), 1)
        self.assertIn("pages-truncated-at-cap", [w["code"] for w in r.summary["warnings"]])

    def test_out_inside_repo_refused(self):
        r = self.run_collect("--dry-run", out_inside=HERE / "should-not-exist")
        self.assertEqual(r.proc.returncode, 2)
        self.assertIn("outside the repository", r.proc.stderr)
        self.assertFalse((HERE / "should-not-exist").exists())

    def test_non_empty_out_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "old.json").write_text("{}", encoding="utf-8")
            r = self.run_collect(out_inside=Path(tmp))
            self.assertEqual(r.proc.returncode, 2)
            self.assertEqual(r.calls, [])

    def test_aws_error_is_redacted_and_isolated(self):
        r = self.run_collect("--services", "firehose,sagemaker", env={"FAKE_AWS_FAIL": "sagemaker list-endpoints"})
        text = json.dumps(r.summary)
        self.assertNotIn("123456789012", text)
        self.assertNotIn("arn:aws", text)
        self.assertIn("aws-error", [w["code"] for w in r.summary["warnings"]])
        self.assertEqual(r.summary["resource_counts"]["firehose_streams"], 1)

    def test_summary_has_no_resource_names(self):
        r = self.run_collect("--glue-databases", "sensors", "--yes")
        text = json.dumps(r.summary)
        for name in ("sensor-raw-60s", "gpu-always-on", "anomaly-scorer", "sensor_csv_dashboard", "sensors"):
            self.assertNotIn(name, text)

    def test_inventory_download(self):
        r = self.run_collect("--services", "s3-inventory", "--inventory-manifest", "s3://example-inv/a/manifest.json", "--yes")
        self.assertEqual(r.summary["paid_units"]["s3_get_requests"], 2)
        self.assertTrue((r.out / "inventory" / "data-0.csv.gz").exists())

    def test_collected_files_convert_to_same_decisions(self):
        r = self.run_collect("--services", "cost,firehose,athena,sagemaker,cloudwatch,s3-inventory", "--glue-databases",
                             "sensors", "--inventory-manifest", "s3://example-inv/a/manifest.json", "--yes")
        self.assertEqual(r.summary["status"], "complete", r.proc.stderr)
        files = sorted(r.out.glob("*.json"))
        pick = lambda prefix: [str(p) for p in files if p.name.startswith(prefix)]
        out = r.dir / "converted.json"
        subprocess.run([sys.executable, "-B", str(HERE / "convert.py"), "--data-kind", "synthetic",
                        "--cost-explorer", *pick("ce-page"), "--athena-queries", *pick("athena-queries"),
                        "--glue-table", *pick("glue-table"), "--metric-queries", *pick("metric-queries"),
                        "--metric-data", *pick("metric-data"), "--firehose-describe", *pick("firehose-"),
                        "--sagemaker-notebook", *pick("notebook-"), "--sagemaker-endpoint", *pick("endpoint-"),
                        "--s3-inventory", str(r.out / "inventory" / "manifest.json"),
                        "--ops-info", str(EX / "ops-info.json"), "--out", str(out)], check=True, capture_output=True)
        converted = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(converted["conversion"]["warnings"], [])
        original = json.loads((HERE / "workloads-ops.json").read_text(encoding="utf-8"))
        decide = lambda w: {(d["rule"], d["id"]): d for d in assess_ops(w, THRESHOLDS)[0] + assess_workloads(w, THRESHOLDS)}
        got, want = decide(converted), decide(original)
        for key in [("R-FH-2", "sensor-raw-60s"), ("R-ATH-1", "sensor_csv_dashboard"), ("R-ATH-2", "sensor_parquet_daily"),
                    ("R-SM-1", "gpu-always-on"), ("R-SM-1", "anomaly-scorer")]:
            with self.subTest(key=key):
                self.assertEqual(got[key], want[key])


if __name__ == "__main__":
    unittest.main()
