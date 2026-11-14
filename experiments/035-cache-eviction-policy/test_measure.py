"""Checks for experiment 035 (no Docker needed)."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from measure import KEYS, OPS, POLICIES, RUNS, summarize, workload

HERE = Path(__file__).resolve().parent
RESULT = json.loads((HERE / "result.json").read_text(encoding="utf-8"))


class WorkloadTest(unittest.TestCase):
    def test_deterministic(self):
        a, ta = workload()
        b, tb = workload()
        self.assertEqual(a, b)
        self.assertEqual(ta, tb)
        self.assertEqual(len(a), OPS)
        self.assertEqual(len(ta), KEYS)

    def test_zipf_head_is_hot(self):
        seq, _ = workload()
        counts = {}
        for k in seq:
            counts[k] = counts.get(k, 0) + 1
        top = sorted(counts.values(), reverse=True)
        self.assertGreater(sum(top[:100]) / OPS, 0.3)


class ResultTest(unittest.TestCase):
    def test_all_runs_present(self):
        self.assertEqual(len(RESULT["runs"]), len(POLICIES) * RUNS)
        for r in RESULT["runs"]:
            self.assertEqual(r["hits"] + r["misses"], r["ops"])

    def test_memory_cap_respected(self):
        for r in RESULT["runs"]:
            self.assertLessEqual(r["maxmemory_bytes"], 64 * 1024 * 1024)
        self.assertTrue(RESULT["environment"]["cleanup"]["container_removed"])
        self.assertTrue(RESULT["environment"]["cleanup"]["image_removed"])

    def test_summary_matches_runs(self):
        self.assertEqual(json.loads(json.dumps(summarize(RESULT["runs"]))), RESULT["summary"])

    def test_resummarize_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "measure.py"), "--resummarize"],
                             capture_output=True, check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), RESULT)


if __name__ == "__main__":
    unittest.main()
