"""Buffer trigger semantics and reproducibility for the Firehose simulation."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from simulate import MIB, arrivals, run_buffer

HERE = Path(__file__).resolve().parent


class BufferTest(unittest.TestCase):
    def test_interval_trigger_with_steady_trickle(self):
        counts = [1] * 400  # 1 record of 100 B per second
        flushes, mean_wait, max_wait = run_buffer(counts, 100, 5, 60, horizon=300)
        self.assertEqual([f[0] for f in flushes], [60, 120, 180, 240, 300])
        self.assertTrue(all(f[3] == "interval" for f in flushes))
        self.assertEqual(max_wait, 60)
        self.assertAlmostEqual(mean_wait, 30.5)

    def test_size_trigger_before_interval(self):
        counts = [MIB // 2 // 1000] * 50  # about half a MiB per second
        flushes, _, max_wait = run_buffer(counts, 1000, 1, 900, horizon=10)
        self.assertTrue(all(f[3] == "size" for f in flushes))
        self.assertLessEqual(max_wait, 2)

    def test_only_buffers_opened_inside_horizon_count(self):
        counts = [1] * 200
        flushes, _, _ = run_buffer(counts, 10, 5, 50, horizon=100)
        self.assertEqual(len(flushes), 2)

    def test_short_tail_is_rejected(self):
        with self.assertRaises(RuntimeError):
            run_buffer([1] * 120, 10, 5, 50, horizon=110)

    def test_arrivals_are_seeded(self):
        self.assertEqual(arrivals(10, 10, 7, 500), arrivals(10, 10, 7, 500))
        self.assertNotEqual(arrivals(10, 10, 7, 500), arrivals(10, 10, 8, 500))
        self.assertEqual(arrivals(5, 1, 1, 3), [5, 5, 5])


class ReproductionTest(unittest.TestCase):
    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "simulate.py")], capture_output=True,
                             text=True, check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), json.loads((HERE / "result.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
