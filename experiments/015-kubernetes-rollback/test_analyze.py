"""Validate rollback evidence using copies of the preserved log."""
import json
from pathlib import Path
import unittest

from analyze import summarize


class RollbackEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.log = json.loads(Path(__file__).with_name("live-attempt-1.json").read_bytes())

    def test_preserved_log_has_one_recovery_in_three(self):
        result = summarize(self.log)
        self.assertEqual(result["execution_status"], "pass")
        self.assertEqual(result["completed_repetitions"], 3)
        self.assertEqual(result["observed_failure_and_recovery"], 1)

    def test_pass_log_missing_second_candidate_is_rejected(self):
        self.log["runs"] = [run for run in self.log["runs"]
                            if (run["repetition"], run["phase"]) != (2, "candidate")]
        with self.assertRaisesRegex(ValueError, "requested rollback repetitions and phases"):
            summarize(self.log)

    def test_wrong_candidate_quota_is_rejected(self):
        run = next(row for row in self.log["runs"] if row["repetition"] == 2 and row["phase"] == "candidate")
        for side in ("before", "after"):
            run[side]["cpu.max"] = "100000 100000"
        with self.assertRaisesRegex(ValueError, "quota"):
            summarize(self.log)

    def test_negative_restored_latency_is_rejected(self):
        run = next(row for row in self.log["runs"] if row["repetition"] == 2 and row["phase"] == "restored")
        run["k6"]["metrics"]["http_req_duration"]["p(99)"] = -1
        with self.assertRaisesRegex(ValueError, "invalid k6"):
            summarize(self.log)


if __name__ == "__main__":
    unittest.main()
