"""Checks for experiment 038."""
import json
import random
import subprocess
import sys
import unittest
from pathlib import Path

from simulate import LEVELS, run_job, simulate

HERE = Path(__file__).resolve().parent
NO_FAIL = {"dup": 0, "throttle": 0, "bad": 0, "manual": 0}


def counters():
    return {"ocr_pages": 0, "bedrock": 0, "dlq": 0, "misjudged": 0, "ocr_by_cause": {}, "bedrock_by_cause": {},
            "blocked": {k: 0 for k in ("dup", "redelivery", "retry_after_fail", "first", "manual")}}


class SimTest(unittest.TestCase):
    def test_clean_run_is_ideal(self):
        c = counters()
        run_job(random.Random(1), "A", 120, NO_FAIL, 2, "upload", {"attempts": {}, "ocr_stored": False}, c)
        self.assertEqual((c["ocr_pages"], c["bedrock"]), (2, 1))

    def test_duplicate_processed_by_A_blocked_by_B(self):
        for rule, ocr in (("A", 2), ("B", 1)):
            c = counters()
            run_job(random.Random(1), rule, 120, NO_FAIL, 1, "upload", {"attempts": {}, "ocr_stored": False}, c, dup_at=5.0)
            self.assertEqual(c["ocr_pages"], ocr, rule)

    def test_B_misjudges_and_C_reuses_ocr_for_manual(self):
        for rule, ocr, mis in (("B", 1, 1), ("C", 1, 0), ("A", 2, 0)):
            c = counters()
            st = {"attempts": {}, "ocr_stored": False}
            run_job(random.Random(1), rule, 120, NO_FAIL, 1, "upload", st, c)
            st["manual_at"] = st["done_at"] + 3600
            run_job(random.Random(2), rule, 120, NO_FAIL, 1, "manual", st, c)
            self.assertEqual((c["ocr_pages"], c["misjudged"]), (ocr, mis), rule)

    def test_same_population_across_rules(self):
        ideal = {simulate(1, r, 60, "base")["ideal_ocr"] for r in ("A", "B", "C")}
        self.assertEqual(len(ideal), 1)

    def test_levels_ordered(self):
        self.assertLess(LEVELS["low"]["dup"], LEVELS["high"]["dup"])

    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "simulate.py")], capture_output=True,
                             check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), json.loads((HERE / "result.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
