"""Boundary, hold and reproduction tests for the workload rules."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from workload_rules import (assess_bedrock_group, assess_firehose_stream, assess_iot_topic, assess_workloads,
                            load_json, load_rates, required_hit_ratio)

HERE = Path(__file__).resolve().parent
THRESHOLDS = load_json(HERE / "thresholds.json")
RATES = load_rates(THRESHOLDS)
WORKLOADS = load_json(HERE / "workloads.json")


def topic(**kw):
    base = {"id": "t", "purpose": "analytics", "metered_messages": 1000, "published_messages": 1000,
            "avg_payload_bytes": 200, "period_s": 10, "max_wait_s": 190, "rules_per_message": 1}
    return {**base, **kw}


def stream(**kw):
    base = {"id": "s", "incoming_records": 1000, "incoming_bytes": 1024 ** 3, "billed_gb": "10",
            "upstream_can_combine": True, "billing_usagetypes": ["APN2-BilledBytes"]}
    return {**base, **kw}


def calls(n_runs, per_run, gap, prefix=3000, model="Claude Haiku 5.5", ttl=None, reads=False):
    out = []
    for r in range(n_runs):
        for c in range(per_run):
            cw = prefix if ttl and not reads else 0
            cr = prefix if ttl and reads else 0
            out.append({"call_id": f"c{r}-{c}", "run_id": f"r{r}", "model": model, "profile": "global",
                        "prefix_hash": "h", "prefix_tokens": prefix, "input_tokens": 500,
                        "cache_read_tokens": cr, "cache_write_tokens": cw, "cache_ttl": ttl,
                        "output_tokens": 300, "ts": r * gap + c * 5})
    return out


def judge(group, model="Claude Haiku 5.5"):
    return assess_bedrock_group(model, "h", group, THRESHOLDS, RATES)


class IotRuleTest(unittest.TestCase):
    def test_reproduces_experiment_016(self):
        row = next(d for d in assess_workloads(WORKLOADS, THRESHOLDS) if d["id"] == "sensor-telemetry")
        self.assertEqual(row["decision"], "candidate")
        self.assertEqual(row["evidence"]["max_batch"], 20)
        self.assertEqual(row["expected_saving_usd"], "38.413440")

    def test_5kb_margin_limits_batch(self):
        row = assess_iot_topic(topic(max_wait_s=10_000), THRESHOLDS, RATES)
        self.assertEqual(row["evidence"]["max_batch"], 4750 // 200)  # 23, not 26+

    def test_payload_boundary(self):
        self.assertEqual(assess_iot_topic(topic(avg_payload_bytes=1024), THRESHOLDS, RATES)["decision"], "candidate")
        self.assertEqual(assess_iot_topic(topic(avg_payload_bytes=1025), THRESHOLDS, RATES)["decision"], "keep")

    def test_metering_consistency_accepts_either_kb_definition(self):
        # 5,050 B is 2 units under 5,000 B but 1 unit under 5,120 B
        row = assess_iot_topic(topic(avg_payload_bytes=5050, metered_messages=1000), THRESHOLDS, RATES)
        self.assertNotIn("iot-metering-inconsistent", row["reasons"])
        row = assess_iot_topic(topic(metered_messages=3000), THRESHOLDS, RATES)
        self.assertEqual(row["reasons"], ["iot-metering-inconsistent"])

    def test_holds_and_keeps(self):
        self.assertEqual(assess_iot_topic(topic(max_wait_s=None), THRESHOLDS, RATES)["reasons"], ["iot-max-wait-missing"])
        self.assertEqual(assess_iot_topic(topic(max_wait_s=9), THRESHOLDS, RATES)["reasons"], ["iot-wait-too-short"])
        self.assertEqual(assess_iot_topic(topic(purpose="alert"), THRESHOLDS, RATES)["decision"], "keep")
        for bad in ({"period_s": 0}, {"avg_payload_bytes": "200"}, {"metered_messages": -1}, {"purpose": "x"}):
            with self.subTest(bad=bad):
                self.assertEqual(assess_iot_topic(topic(**bad), THRESHOLDS, RATES)["reasons"], ["input-invalid"])


class FirehoseRuleTest(unittest.TestCase):
    def test_ratio_boundaries(self):
        cases = {"1.49": "keep", "1.5": "hold", "2.99": "hold", "3": "candidate"}
        for billed, expected in cases.items():
            with self.subTest(billed=billed):
                self.assertEqual(assess_firehose_stream(stream(billed_gb=billed), THRESHOLDS, RATES)["decision"], expected)

    def test_saving_is_rounding_loss_upper_bound(self):
        row = assess_firehose_stream(stream(billed_gb="10"), THRESHOLDS, RATES)
        self.assertEqual(row["expected_saving_usd"], "0.324000")  # (10 - 1) GB x 0.036

    def test_holds(self):
        self.assertEqual(assess_firehose_stream(stream(billed_gb="0.5"), THRESHOLDS, RATES)["reasons"], ["fh-billing-below-raw"])
        self.assertEqual(assess_firehose_stream(stream(upstream_can_combine=None), THRESHOLDS, RATES)["reasons"], ["fh-upstream-unknown"])
        self.assertEqual(assess_firehose_stream(stream(upstream_can_combine=False), THRESHOLDS, RATES)["decision"], "keep")
        no_round = stream(billing_usagetypes=["APN2-DirectPUT-no-rounding-BilledBytes"])
        self.assertEqual(assess_firehose_stream(no_round, THRESHOLDS, RATES)["reasons"], ["fh-no-rounding-usage"])
        for bad in ({"billed_gb": "abc"}, {"billed_gb": "NaN"}, {"incoming_bytes": 0}):
            with self.subTest(bad=bad):
                self.assertEqual(assess_firehose_stream(stream(**bad), THRESHOLDS, RATES)["reasons"], ["input-invalid"])


class BedrockRuleTest(unittest.TestCase):
    def test_reproduces_experiment_020(self):
        row = judge(calls(1, 4, 3600))
        self.assertEqual((row["rule"], row["decision"]), ("R-BR-1", "candidate"))
        self.assertEqual(row["expected_saving_usd"], "0.000735")

    def test_cache_minimum_boundary(self):
        self.assertEqual(judge(calls(3, 4, 3600, prefix=511))["reasons"], ["br-below-cache-minimum"])
        self.assertEqual(judge(calls(3, 4, 3600, prefix=512))["decision"], "candidate")
        self.assertEqual(judge(calls(3, 4, 3600), model="Claude Sonnet 4.5")["reasons"], ["br-cache-minimum-unknown"])

    def test_single_calls_use_gap_based_reuse(self):
        self.assertEqual(judge(calls(30, 1, 600))["reasons"], ["br-reuse-below-break-even"])
        self.assertEqual(judge(calls(30, 1, 120))["reasons"], ["br-reuse-above-break-even"])

    def test_break_even_hit_ratio(self):
        rate = RATES["bedrock"]["Claude Haiku 5.5"]
        self.assertAlmostEqual(float(required_hit_ratio(rate, "5m")), 0.025 / 0.115)
        writes = calls(20, 1, 3600, ttl="5m")
        just_below = writes + calls(5, 1, 3600, ttl="5m", reads=True)   # 5 / 25 = 0.20 < 0.2174
        just_above = writes + calls(6, 1, 3600, ttl="5m", reads=True)   # 6 / 26 = 0.2308
        self.assertEqual(judge(just_below)["decision"], "candidate")
        self.assertEqual(judge(just_above)["decision"], "keep")

    def test_holds(self):
        self.assertEqual(judge(calls(19, 1, 3600, ttl="5m"))["reasons"], ["br-too-few-cache-writes"])
        self.assertEqual(judge(calls(20, 1, 3600, ttl="10m"))["reasons"], ["br-ttl-missing"])
        geo = calls(3, 4, 3600)
        geo[0]["profile"] = "geographic"
        self.assertEqual(judge(geo)["reasons"], ["br-rate-unverified"])
        mixed = calls(3, 4, 3600)
        mixed[0]["prefix_tokens"] = 2999
        self.assertEqual(judge(mixed)["reasons"], ["br-prefix-inconsistent"])
        broken = calls(3, 4, 3600)
        del broken[0]["run_id"]
        self.assertEqual(judge(broken)["reasons"], ["input-invalid"])
        self.assertEqual(judge(calls(3, 4, 3600), model="Amazon Nova Lite")["reasons"], ["br-rate-unverified"])


class WorkloadReportTest(unittest.TestCase):
    def test_every_rule_has_candidate_keep_and_hold_examples(self):
        rows = assess_workloads(WORKLOADS, THRESHOLDS)
        for prefix in ("R-IOT-1", "R-FH-1", "R-BR"):
            seen = {r["decision"] for r in rows if r["rule"].startswith(prefix)}
            self.assertEqual(seen, {"candidate", "keep", "hold"}, prefix)

    def test_one_bad_item_holds_only_itself(self):
        data = copy.deepcopy(WORKLOADS)
        data["iot_topics"][0]["avg_payload_bytes"] = None
        before = {r["id"]: r for r in assess_workloads(WORKLOADS, THRESHOLDS)}
        after = {r["id"]: r for r in assess_workloads(data, THRESHOLDS)}
        self.assertEqual(after["sensor-telemetry"]["reasons"], ["input-invalid"])
        for key in before:
            if key != "sensor-telemetry":
                self.assertEqual(before[key], after[key])

    def test_extra_sensitive_fields_are_not_echoed(self):
        data = copy.deepcopy(WORKLOADS)
        secret = "acct-123456789012-secret"
        data["iot_topics"][0]["account_id"] = secret
        data["bedrock_calls"][0]["api_key"] = secret
        self.assertNotIn(secret, json.dumps(assess_workloads(data, THRESHOLDS)))

    def test_thresholds_carry_evidence_levels(self):
        for section in ("iot", "firehose", "bedrock"):
            for key, entry in THRESHOLDS[section].items():
                with self.subTest(key=key):
                    self.assertIn(entry["evidence"], ("실험 확인", "공식 자료", "임시값"))
                    self.assertTrue(entry["source"])


class CliTest(unittest.TestCase):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    def run_cli(self, *args):
        return subprocess.check_output([sys.executable, "-B", str(HERE / "cli.py"), *args],
                                       encoding="utf-8", env=self.env)

    def test_default_report_has_no_workload_section(self):
        self.assertNotIn("workload_decisions", json.loads(self.run_cli("--json")))

    def test_workloads_option_adds_section_and_text(self):
        report = json.loads(self.run_cli("--json", "--workloads", str(HERE / "workloads.json")))
        self.assertEqual(len(report["workload_decisions"]), 17)
        text = self.run_cli("--workloads", str(HERE / "workloads.json"))
        self.assertIn("예상 절감 USD 38.413440", text)
        self.assertIn("실제 청구 대사: 미검증", text)


if __name__ == "__main__":
    unittest.main()
