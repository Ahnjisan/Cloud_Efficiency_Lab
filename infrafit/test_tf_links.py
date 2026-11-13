"""Tests for infrafit/tf_links.py with a synthetic `terraform show -json` state."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from tf_links import compare, links_from_state  # noqa: E402

STATE = HERE / "convert-examples" / "terraform-show.json"
CHANGES = HERE.parent / "experiments" / "008-evidence-reconciliation" / "changes.json"


def state():
    return json.loads(STATE.read_text(encoding="utf-8"))


class LinkTests(unittest.TestCase):
    def test_links_managed_resources_with_ids(self):
        r = links_from_state(state())
        self.assertEqual(r["source"], "state")
        self.assertEqual(r["links"], {
            "aws_instance.conflict": {"resource": "i-conflict-replaced", "type": "aws_instance"},
            "aws_instance.orders": {"resource": "i-orders", "type": "aws_instance"},
            "aws_instance.worker": {"resource": "i-worker", "type": "aws_instance"},
            "module.batch.aws_instance.job[0]": {"resource": "i-batch-0", "type": "aws_instance"}})

    def test_skips_data_sources_sensitive_and_missing_ids(self):
        r = links_from_state(state())
        self.assertNotIn("data.aws_ami.base", r["links"])
        self.assertIn({"code": "id-sensitive", "address": "aws_db_instance.main"}, r["warnings"])
        self.assertIn({"code": "id-missing", "address": "aws_ebs_volume.pending"}, r["warnings"])

    def test_no_other_state_value_is_printed(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "tf_links.py"), str(STATE), "--changes", str(CHANGES)],
                             capture_output=True, text=True, encoding="utf-8", check=True).stdout
        for secret in ("do-not-print", "db-hidden-id", "123456789012", "arn:aws", "model.large", "ami-data-source"):
            self.assertNotIn(secret, out)

    def test_compare_with_changes(self):
        links = links_from_state(state())["links"]
        rows = {r["address"]: r["status"] for r in compare(links, json.loads(CHANGES.read_text(encoding="utf-8")))}
        self.assertEqual(rows, {"aws_instance.orders": "match", "aws_instance.worker": "match",
                                "aws_instance.conflict": "mismatch", "aws_instance.missing": "address-not-in-state",
                                "aws_instance.stale": "address-not-in-state",
                                "module.batch.aws_instance.job[0]": "state-only"})

    def test_links_agree_with_hand_written_basis(self):
        basis = json.loads((HERE / "config-basis.json").read_text(encoding="utf-8"))
        links = links_from_state(state())["links"]
        for address, entry in basis.items():
            self.assertEqual(links[address]["resource"], entry["resource"])

    def test_plan_prior_state_and_bad_input(self):
        plan = {"format_version": "1.2", "prior_state": state(), "resource_changes": []}
        self.assertEqual(links_from_state(plan)["source"], "plan.prior_state")
        self.assertEqual(links_from_state({"resource_changes": []})["warnings"], [{"code": "no-state-values", "address": None}])

    def test_duplicate_address_is_dropped(self):
        doc = state()
        res = doc["values"]["root_module"]["resources"]
        res.append(dict(res[0], values={"id": "i-orders-2"}))
        r = links_from_state(doc)
        self.assertNotIn("aws_instance.orders", r["links"])
        self.assertIn({"code": "address-duplicate", "address": "aws_instance.orders"}, r["warnings"])


if __name__ == "__main__":
    unittest.main()
