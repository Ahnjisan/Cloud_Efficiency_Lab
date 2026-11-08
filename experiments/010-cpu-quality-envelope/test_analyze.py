"""Quality-gate regressions without starting an experiment."""
import unittest

from analyze import quality_row


class QualityRowTest(unittest.TestCase):
    def setUp(self):
        self.metrics = {
            "successful_requests": {"count": 750},
            "http_reqs": {"count": 750},
            "http_req_duration": {"p(99)": 100},
            "http_req_failed": {"value": 0},
        }

    def test_missing_dropped_iterations_matches_explicit_zero(self):
        row = quality_row(self.metrics)
        self.assertEqual(row["dropped"], 0)
        self.assertTrue(row["joint_gate_pass"])
        self.metrics["dropped_iterations"] = {"count": 0}
        self.assertEqual(row, quality_row(self.metrics))

    def test_invalid_values_are_rejected(self):
        for key, field, value in (
            ("http_req_duration", "p(99)", -1),
            ("http_req_duration", "p(99)", float("nan")),
            ("http_req_failed", "value", -.5),
            ("http_req_failed", "value", 1.1),
            ("http_req_failed", "value", .5),
            ("dropped_iterations", "count", -1),
            ("dropped_iterations", "count", 0.5),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                quality_row({**self.metrics, key: {field: value}})


if __name__ == "__main__":
    unittest.main()
