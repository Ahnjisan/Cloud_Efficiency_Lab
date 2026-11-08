"""Exercise the read-only CLI with the existing experiment inputs."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent / "experiments"
EVIDENCE = EXPERIMENTS / "008-evidence-reconciliation"
PLAN = EXPERIMENTS / "004-terraform-evidence/plan.json"


class InfraFitCliTest(unittest.TestCase):
    def invoke(self, *args, json_output=True):
        options = ["--json"] if json_output else []
        return subprocess.check_output([sys.executable, "-B", str(HERE / "cli.py"), *options, *args],
                                       cwd=self.temp, encoding="utf-8", env=self.env)

    def setUp(self):
        import os
        self.env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.temp = Path(directory.name)

    def report(self, *args):
        report = json.loads(self.invoke(*args))
        return report, {row["address"]: row for row in report["decisions"]}

    def altered(self, path, change):
        data = json.loads(path.read_bytes())
        change(data)
        copy = self.temp / path.name
        copy.write_text(json.dumps(data), encoding="utf-8")
        return str(copy)

    def test_default_report_and_display(self):
        report, rows = self.report()
        self.assertEqual([row["decision"] for row in rows.values()], ["candidate", "keep", "hold", "hold", "hold"])
        order = rows["aws_instance.orders"]
        self.assertEqual(order["modeled_usd"], {"baseline": "120.00", "candidate": "100.00", "difference": "20.00"})
        self.assertEqual(order["plan_configuration"]["after"], {"instance_type": "model.medium"})
        self.assertEqual(rows["aws_instance.worker"]["reasons"], ["peak-limit-exceeded"])
        self.assertIn("billing-conflict", rows["aws_instance.conflict"]["reasons"])
        self.assertIn("billing-unmatched", rows["aws_instance.missing"]["reasons"])
        self.assertEqual(report["actual_billing_reconciliation"], "unverified")
        text = self.invoke(json_output=False)
        for label in ("변경 검토 후보", "유지", "판단 보류", "실제 청구 대사: 미검증"):
            self.assertIn(label, text)

    def test_late_evidence_and_duplicate_delivery(self):
        _, initial = self.report("--as-of", "1")
        self.assertEqual(initial["aws_instance.orders"]["decision"], "hold")
        self.assertIn("peak-unmatched-or-ambiguous", initial["aws_instance.orders"]["reasons"])
        duplicate = self.altered(EVIDENCE / "billing.json", lambda rows: rows.extend(rows[:]))
        before = Path(duplicate).read_bytes()
        self.assertEqual(self.report("--billing", duplicate), self.report())
        self.assertEqual(Path(duplicate).read_bytes(), before)

    def test_wrong_candidate_observation_is_held(self):
        wrong = self.altered(EVIDENCE / "peaks.json", lambda rows: rows[0].update(config="orders-current-v1"))
        _, rows = self.report("--peaks", wrong)
        self.assertEqual(rows["aws_instance.orders"]["decision"], "hold")
        self.assertEqual(rows["aws_instance.orders"]["reasons"], ["peak-unmatched-or-ambiguous"])

    def test_missing_charge_id_only_holds_its_resource(self):
        _, baseline = self.report()
        for variant in ("omitted", None, "", " "):
            def change(rows):
                charge = next(row for row in rows if row["line_id"] == "a2")
                if variant == "omitted":
                    del charge["line_id"]
                else:
                    charge["line_id"] = variant

            with self.subTest(variant=variant):
                billing = self.altered(EVIDENCE / "billing.json", change)
                _, rows = self.report("--billing", billing)
                order = rows.pop("aws_instance.orders")
                self.assertEqual(order["decision"], "hold")
                self.assertEqual(order["reasons"], ["billing-line-id-missing"])
                self.assertIsNone(order["modeled_usd"])
                self.assertEqual(rows, {key: row for key, row in baseline.items() if key != order["address"]})

    def test_missing_candidate_cost_only_holds_its_address(self):
        _, baseline = self.report()
        for variant in ("omitted", None, "", " "):
            def change(rows):
                order = next(row for row in rows if row["address"] == "aws_instance.orders")
                if variant == "omitted":
                    del order["candidate"]
                else:
                    order["candidate"] = variant

            with self.subTest(variant=variant):
                changes = self.altered(EVIDENCE / "changes.json", change)
                _, rows = self.report("--changes", changes)
                order = rows.pop("aws_instance.orders")
                self.assertEqual(order["decision"], "hold")
                self.assertEqual(order["reasons"], ["candidate-cost-missing"])
                self.assertIsNone(order["modeled_usd"])
                self.assertEqual(rows, {key: row for key, row in baseline.items() if key != order["address"]})

    def test_missing_charge_id_and_amount_only_hold_the_known_resource(self):
        _, baseline = self.report()

        def change(rows):
            charge = next(row for row in rows if row["line_id"] == "a2")
            del charge["line_id"]
            del charge["amount"]

        billing = self.altered(EVIDENCE / "billing.json", change)
        original = Path(billing).read_bytes()
        _, rows = self.report("--billing", billing)
        order = rows.pop("aws_instance.orders")
        self.assertEqual(order["decision"], "hold")
        self.assertEqual(order["reasons"], ["billing-line-id-missing"])
        self.assertEqual(rows, {key: row for key, row in baseline.items() if key != order["address"]})
        self.assertEqual(Path(billing).read_bytes(), original)

    def test_missing_charge_id_and_resource_are_reported_without_stopping(self):
        def change(rows):
            charge = next(row for row in rows if row["line_id"] == "a2")
            del charge["line_id"]
            del charge["resource"]

        billing = self.altered(EVIDENCE / "billing.json", change)
        original = Path(billing).read_bytes()
        report, rows = self.report("--billing", billing)
        _, baseline = self.report()
        self.assertEqual(report["unassigned_missing_id_rows"], 1)
        order = rows.pop("aws_instance.orders")
        self.assertEqual(order["decision"], "keep")
        self.assertEqual(order["modeled_usd"]["baseline"], "100.00")
        self.assertEqual(rows, {key: row for key, row in baseline.items() if key != order["address"]})
        self.assertEqual(Path(billing).read_bytes(), original)

    def test_unchanged_cost_configuration_is_not_a_candidate(self):
        def change(plan):
            order = next(row for row in plan["resource_changes"] if row["address"] == "aws_instance.orders")
            order["change"]["after"] = {"instance_type": "model.large", "user_data": "unpriced-change"}

        plan = self.altered(PLAN, change)
        basis = self.altered(HERE / "config-basis.json",
                             lambda rows: rows["aws_instance.orders"].update(after={"instance_type": "model.large"}))
        _, rows = self.report("--plan", plan, "--basis", basis)
        order = rows["aws_instance.orders"]
        self.assertEqual(order["decision"], "hold")
        self.assertEqual(order["reasons"], ["cost-configuration-unchanged"])
        self.assertIsNone(order["modeled_usd"])

    def test_missing_unknown_mask_reports_plan_hold(self):
        def change(plan):
            order = next(row for row in plan["resource_changes"] if row["address"] == "aws_instance.orders")
            del order["change"]["after_unknown"]

        plan = self.altered(PLAN, change)
        _, rows = self.report("--plan", plan)
        order = rows["aws_instance.orders"]
        self.assertEqual(order["decision"], "hold")
        self.assertEqual(order["plan_status"], "hold")
        self.assertEqual(order["reasons"], ["plan-evidence-unavailable"])
        self.assertIsNone(order["plan_configuration"])

    def test_wrong_plan_configuration_is_held(self):
        def change(plan):
            order = next(row for row in plan["resource_changes"] if row["address"] == "aws_instance.orders")
            order["change"]["after"]["instance_type"] = "model.other"

        plan = self.altered(PLAN, change)
        _, rows = self.report("--plan", plan)
        self.assertEqual(rows["aws_instance.orders"]["reasons"], ["configuration-mismatch"])
        self.assertIsNone(rows["aws_instance.orders"]["modeled_usd"])

    def test_sensitive_plan_value_is_not_printed(self):
        def change(plan):
            order = next(row for row in plan["resource_changes"] if row["address"] == "aws_instance.orders")
            order["change"]["after"]["instance_type"] = "sensitive-fixture-only"
            order["change"]["after_sensitive"] = {"instance_type": True}

        plan = self.altered(PLAN, change)
        output = self.invoke("--plan", plan)
        self.assertNotIn("sensitive-fixture-only", output)
        _, rows = self.report("--plan", plan)
        self.assertEqual(rows["aws_instance.orders"]["reasons"], ["plan-evidence-unavailable"])


if __name__ == "__main__":
    unittest.main()
