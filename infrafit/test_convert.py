"""Tests for infrafit/convert.py with synthetic AWS-shaped responses (convert-examples/)."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import convert  # noqa: E402
from ops_rules import assess_ops  # noqa: E402
from workload_rules import assess_workloads  # noqa: E402

EX = HERE / "convert-examples"
THRESHOLDS = json.loads((HERE / "thresholds.json").read_text(encoding="utf-8"))
ORIGINAL = {**json.loads((HERE / "workloads.json").read_text(encoding="utf-8"))}
for key, items in json.loads((HERE / "workloads-ops.json").read_text(encoding="utf-8")).items():
    if isinstance(items, list):
        ORIGINAL.setdefault(key, []).extend(items)


def run(argv_extra=(), root=EX):
    base = ["--data-kind", "synthetic",
            "--cost-explorer", str(root / "ce-page1.json"), str(root / "ce-page2.json"),
            "--athena-queries", str(root / "athena-queries.json"),
            "--glue-table", str(root / "glue-sensor_csv_dashboard.json"), str(root / "glue-sensor_parquet_daily.json"),
            "--metric-queries", str(root / "metric-queries.json"), "--metric-data", str(root / "metric-data.json"),
            "--firehose-describe", str(root / "firehose-sensor-raw-60s.json"),
            "--s3-inventory", str(root / "inventory" / "manifest.json"),
            "--sagemaker-notebook", str(root / "notebook-gpu-always-on.json"),
            "--sagemaker-endpoint", str(root / "endpoint-anomaly-scorer.json"), str(root / "endpoint-config-anomaly-scorer.json"),
            "--bedrock-usage", str(root / "bedrock-usage.jsonl"), "--ops-info", str(root / "ops-info.json")]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.json"
        subprocess.run([sys.executable, "-B", str(HERE / "convert.py"), *base, *argv_extra, "--out", str(out)],
                       check=True, capture_output=True)
        return json.loads(out.read_text(encoding="utf-8"))


def decide(workloads):
    ops, queue, holds = assess_ops(workloads, THRESHOLDS)
    return assess_workloads(workloads, THRESHOLDS) + ops, queue, holds


def by_id(decisions):
    return {(d["rule"], d["id"]): d for d in decisions}


def warn_codes(result):
    return [w["code"] for w in result["conversion"]["warnings"]]


class TempExamples:
    """Copy of convert-examples that a test may edit."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "ex"
        shutil.copytree(EX, self.root)
        return self

    def __exit__(self, *exc):
        self.tmp.cleanup()

    def edit(self, name, fn):
        path = self.root / name
        doc = json.loads(path.read_text(encoding="utf-8"))
        fn(doc)
        path.write_text(json.dumps(doc), encoding="utf-8")


class ParityTests(unittest.TestCase):
    """A converted item must give exactly the decision of the hand-written example it mirrors."""

    @classmethod
    def setUpClass(cls):
        cls.result = run()
        cls.converted, cls.queue, _ = decide(cls.result)
        cls.original, cls.original_queue, _ = decide(ORIGINAL)

    def test_no_warnings_on_clean_examples(self):
        self.assertEqual(self.result["conversion"]["warnings"], [])

    def test_decisions_match_original_examples(self):
        conv, orig = by_id(self.converted), by_id(self.original)
        expected = [("R-FH-2", "sensor-raw-60s"), ("R-ATH-1", "sensor_csv_dashboard"), ("R-ATH-2", "sensor_parquet_daily"),
                    ("R-SM-1", "gpu-always-on"), ("R-SM-1", "anomaly-scorer"),
                    ("R-BR-1", "Claude Haiku 5.5 | sha256:agent-planner"), ("R-BR-2", "Claude Haiku 5.5 | sha256:cached-dense")]
        for key in expected:
            with self.subTest(key=key):
                self.assertIn(key, conv)
                self.assertEqual(conv[key], orig[key])

    def test_017_and_020_numbers(self):
        conv = by_id(self.converted)
        fh = conv[("R-FH-2", "sensor-raw-60s")]
        self.assertEqual((fh["decision"], fh["evidence"]["objects_per_day_observed"], fh["evidence"]["objects_per_day_after"]),
                         ("candidate", 1440, 96.0))
        self.assertEqual(conv[("R-BR-1", "Claude Haiku 5.5 | sha256:agent-planner")]["expected_saving_usd"], "0.007350")  # 020: 0.000735 x 10 runs

    def test_daily_cost_queue_matches_021(self):
        pick = lambda q: sorted((r for r in q if r["service"] in ("AWS IoT", "Amazon Bedrock")), key=lambda r: (r["service"], r["date"]))
        self.assertEqual(pick(self.queue), pick(self.original_queue))
        self.assertEqual(sum(1 for r in self.queue if r["service"] == "AWS IoT"), 14)

    def test_usage_types_are_summed_per_service(self):
        iot = next(s for s in self.result["daily_costs"] if s["service"] == "AWS IoT")
        orig = next(s for s in ORIGINAL["daily_costs"] if s["service"] == "AWS IoT")
        self.assertEqual([r["Metrics"]["NetUnblendedCost"]["Amount"] for r in iot["ResultsByTime"]],
                         [r["Metrics"]["NetUnblendedCost"]["Amount"] for r in orig["ResultsByTime"]])


class SafetyTests(unittest.TestCase):
    def test_sensitive_values_never_copied(self):
        text = json.dumps(run())
        for secret in ("123456789012", "arn:aws", "example-sensor-bucket", "s3://", "SELECT", "secret_table",
                       "example-firehose-delivery", "athena-results", "convert-examples"):
            self.assertNotIn(secret, text)

    def test_hash_names_hides_names_and_keeps_decisions(self):
        plain, hashed = run(), run(["--hash-names", "--hash-salt", "s1"])
        text = json.dumps(hashed)
        for name in ("sensor-raw-60s", "sensor_csv_dashboard", "gpu-always-on", "anomaly-scorer", "agent-planner"):
            self.assertNotIn(name, text)
        self.assertTrue(all("SubmissionDateTime" not in q["Status"] for t in hashed["athena_tables"] for q in t["query_executions"]))
        self.assertEqual(min(c["ts"] for c in hashed["bedrock_calls"]), 0)
        a = sorted((d["rule"], d["decision"], d["reasons"]) for d in decide(plain)[0])
        b = sorted((d["rule"], d["decision"], d["reasons"]) for d in decide(hashed)[0])
        self.assertEqual(a, b)
        self.assertIn("dates-and-amounts-kept", warn_codes(hashed))

    def test_salt_changes_hash(self):
        a = run(["--hash-names", "--hash-salt", "s1"])["firehose_buffers"][0]["DeliveryStreamName"]
        b = run(["--hash-names", "--hash-salt", "s2"])["firehose_buffers"][0]["DeliveryStreamName"]
        self.assertTrue(a.startswith("h-") and b.startswith("h-") and a != b)
        self.assertIn("salt-missing", warn_codes(run(["--hash-names"])))

    def test_prompt_fields_dropped_with_warning(self):
        with TempExamples() as t:
            path = t.root / "bedrock-usage.jsonl"
            lines = path.read_text(encoding="utf-8").splitlines()
            first = json.loads(lines[0])
            first["messages"] = [{"role": "user", "content": "PRIVATE PROMPT BODY"}]
            lines[0] = json.dumps(first)
            path.write_text("\n".join(lines), encoding="utf-8")
            result = run(root=t.root)
        self.assertNotIn("PRIVATE PROMPT BODY", json.dumps(result))
        self.assertIn("prompt-field-dropped", warn_codes(result))
        self.assertEqual(len(result["bedrock_calls"]), 140)

    def test_warning_format(self):
        with TempExamples() as t:
            t.edit("athena-queries.json", lambda d: d["UnprocessedQueryExecutionIds"].append(
                {"QueryExecutionId": "q-lost", "ErrorCode": "INTERNAL", "ErrorMessage": "synthetic"}))
            w = run(root=t.root)["conversion"]["warnings"]
        self.assertEqual(w, [{"source": "athena", "file": "athena-queries.json", "item": "q-lost",
                              "code": "unprocessed-query", "field": "UnprocessedQueryExecutionIds", "action": "skipped-item"}])


class IsolationTests(unittest.TestCase):
    """A broken field skips or empties only its own item; InfraFit then holds only that item."""

    def test_missing_scan_bytes_skips_only_that_query(self):
        with TempExamples() as t:
            t.edit("athena-queries.json", lambda d: d["QueryExecutions"][0]["Statistics"].pop("DataScannedInBytes"))
            result = run(root=t.root)
        self.assertIn("field-missing", warn_codes(result))
        csv = next(x for x in result["athena_tables"] if x["table"]["Name"] == "sensor_csv_dashboard")
        self.assertEqual(len(csv["query_executions"]), 211)
        self.assertEqual(len(result["firehose_buffers"]), 1)

    def test_partial_metric_leaves_null_and_infrafit_holds(self):
        with TempExamples() as t:
            t.edit("metric-data.json", lambda d: d["MetricDataResults"][0].update(StatusCode="PartialData"))
            result = run(root=t.root)
        self.assertIn("status-not-complete", warn_codes(result))
        self.assertIsNone(result["firehose_buffers"][0]["IncomingBytes_daily_sum"])
        decisions = by_id(decide(result)[0])
        self.assertEqual(decisions[("R-FH-2", "sensor-raw-60s")]["decision"], "hold")
        self.assertEqual(decisions[("R-SM-1", "anomaly-scorer")]["decision"], "candidate")

    def test_missing_human_value_holds_item(self):
        with TempExamples() as t:
            t.edit("ops-info.json", lambda d: d["firehose"]["sensor-raw-60s"].pop("allowed_freshness_s"))
            result = run(root=t.root)
        self.assertIn("ops-value-missing", warn_codes(result))
        d = by_id(decide(result)[0])[("R-FH-2", "sensor-raw-60s")]
        self.assertEqual((d["decision"], d["reasons"]), ("hold", ["fh2-freshness-missing"]))

    def test_unmapped_query_is_skipped(self):
        with TempExamples() as t:
            t.edit("ops-info.json", lambda d: d["athena"]["queries"].pop("sensor_parquet_daily-0000"))
            result = run(root=t.root)
        self.assertEqual(warn_codes(result).count("query-table-unknown"), 1)

    def test_cost_day_gap_passes_through_and_holds(self):
        with TempExamples() as t:
            t.edit("ce-page2.json", lambda d: d["ResultsByTime"].pop(3))
            result = run(root=t.root)
        _, queue, holds = decide(result)
        self.assertEqual({h["service"] for h in holds}, {"AWS IoT", "Amazon Bedrock"})

    def test_cost_page_without_service_grouping_skipped(self):
        with TempExamples() as t:
            t.edit("ce-page1.json", lambda d: d.update(GroupDefinitions=[{"Type": "DIMENSION", "Key": "USAGE_TYPE"}]))
            result = run(root=t.root)
        self.assertIn("group-by-without-service", warn_codes(result))

    def test_parquet_inventory_not_supported(self):
        with TempExamples() as t:
            t.edit("inventory/manifest.json", lambda d: d.update(fileFormat="Parquet"))
            result = run(root=t.root)
        codes = warn_codes(result)
        self.assertIn("format-not-supported", codes)
        self.assertIsNone(result["firehose_buffers"][0]["s3_objects_daily"])

    def test_serverless_variant_skipped(self):
        with TempExamples() as t:
            t.edit("endpoint-config-anomaly-scorer.json",
                   lambda d: d["ProductionVariants"][0].pop("InstanceType"))
            result = run(root=t.root)
        self.assertIn("variant-not-instance-based", warn_codes(result))
        self.assertNotIn("sagemaker_endpoints", result)

    def test_unreadable_file_does_not_stop(self):
        with TempExamples() as t:
            (t.root / "glue-sensor_parquet_daily.json").write_text("{not json", encoding="utf-8")
            result = run(root=t.root)
        self.assertIn("file-unreadable", warn_codes(result))
        self.assertEqual([x["table"]["Name"] for x in result["athena_tables"]], ["sensor_csv_dashboard"])


class UnitTests(unittest.TestCase):
    def test_model_and_profile(self):
        self.assertEqual(convert.model_and_profile("global.anthropic.claude-haiku-5-5", {}), ("Claude Haiku 5.5", "global"))
        self.assertEqual(convert.model_and_profile("apac.anthropic.claude-sonnet-5-5", {}), ("Claude Sonnet 5.5", "geographic"))
        self.assertEqual(convert.model_and_profile("anthropic.claude-haiku-4-5-20251001-v1:0", {}),
                         ("Claude Haiku 4.5", "in-region"))
        self.assertEqual(convert.model_and_profile("amazon.nova-lite-v1:0", {}), ("amazon.nova-lite-v1:0", "in-region"))
        self.assertEqual(convert.model_and_profile("x", {"x": {"model": "M", "profile": "global"}}), ("M", "global"))

    def test_existing_examples_unchanged(self):
        """The converter must not touch the hand-written inputs."""
        before = (HERE / "workloads-ops.json").read_bytes()
        run()
        self.assertEqual((HERE / "workloads-ops.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
