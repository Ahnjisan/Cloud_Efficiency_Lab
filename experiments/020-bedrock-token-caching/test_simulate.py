"""Token accounting and cache-model checks for the Bedrock caching simulation."""
import unittest

from simulate import (cache_events, dynamic_tokens, evaluate, load_rates, required_hit_ratio,
                      run_times)


class RatesTest(unittest.TestCase):
    def test_snapshot_rates(self):
        r = load_rates()["Claude Haiku 5.5"]
        self.assertAlmostEqual(r["input"] * 1e6, 0.10)
        self.assertAlmostEqual(r["write_5m"] * 1e6, 0.125)
        self.assertAlmostEqual(r["read"] * 1e6, 0.01)

    def test_required_hit_ratio(self):
        r = load_rates()["Claude Haiku 5.5"]
        self.assertAlmostEqual(required_hit_ratio(r, "write_5m"), 0.025 / 0.115)


class ModelTest(unittest.TestCase):
    def test_study_note_example(self):
        dyn, out = dynamic_tokens(4)
        self.assertEqual(dyn + 4 * 3000, 18_800)
        self.assertEqual(out, 1_200)

    def test_cache_ttl_and_reset(self):
        # three runs of one call: gaps 200 s (hit) then 400 s (> 300 s TTL, write)
        self.assertEqual(cache_events([0, 200, 600], 1, 300, 0.0, 1), (2, 1))
        # gaps of 250 s keep refreshing a 300 s TTL
        self.assertEqual(cache_events([0, 250, 500, 750], 1, 300, 0.0, 1), (1, 3))
        # calls inside one run are 5 s apart, so only the first writes
        self.assertEqual(cache_events([0], 4, 300, 0.0, 1), (1, 3))

    def test_misses_turn_reads_into_writes(self):
        writes, reads = cache_events([0], 1000, 300, 1.0, 1)
        self.assertEqual((writes, reads), (1000, 0))

    def test_prefix_below_minimum_equals_no_cache(self):
        rates = load_rates()["Claude Sonnet 5.5"]
        a = evaluate("m", rates, 4, 500, 100, "cache_5m", 0.0, (1,))
        b = evaluate("m", rates, 4, 500, 100, "none", 0.0, (1,))
        self.assertEqual(a["usd_per_run"], b["usd_per_run"])

    def test_single_call_with_long_gaps_costs_more_with_cache(self):
        rates = load_rates()["Claude Haiku 5.5"]
        a = evaluate("m", rates, 1, 3000, 10, "cache_5m", 0.0, (1, 2))
        b = evaluate("m", rates, 1, 3000, 10, "none", 0.0, (1, 2))
        self.assertGreater(a["usd_per_run"], b["usd_per_run"])

    def test_run_times_are_seeded_and_inside_active_hours(self):
        t = run_times(50, 3, days=2)
        self.assertEqual(t, run_times(50, 3, days=2))
        self.assertTrue(all(x % 86_400 < 12 * 3600 for x in t))


if __name__ == "__main__":
    unittest.main()
