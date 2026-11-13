"""Scan-proxy logic checks on a tiny dataset (the full run takes minutes)."""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from measure import billed, queries, run, scan_bytes, stats_exclude, summarize


class BilledTest(unittest.TestCase):
    def test_minimum_and_rounding(self):
        self.assertEqual(billed(4 * 1024 * 1024, 5.0)[0], 10)
        self.assertEqual(billed(int(10.5 * 1024 * 1024), 5.0)[0], 11)
        self.assertAlmostEqual(billed(0, 5.0)[1], 10 / 1024 / 1024 * 5.0)


class StatsTest(unittest.TestCase):
    def test_row_group_skipping(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.parquet"
            table = pa.table({"zone": ["z01", "z02"] * 5, "v": list(range(10))})
            pq.write_table(table.slice(0, 4), path)
            rg = pq.ParquetFile(path).metadata.row_group(0)
            self.assertTrue(stats_exclude(rg, 0, "eq", "z09"))
            self.assertFalse(stats_exclude(rg, 0, "eq", "z02"))
            self.assertTrue(stats_exclude(rg, 1, "ge", 4))
            self.assertTrue(stats_exclude(rg, 1, "lt", 0))
            self.assertFalse(stats_exclude(rg, 1, "lt", 1))


class SmallRunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run(sensors=8, zones=4, days=2, period_s=300, seeds=(5,))
        cls.result.update(summarize(cls.result))

    def scan(self, q, layout):
        seed = self.result["per_seed"][0]
        return next(r for r in seed["scans"] if r["query"] == q and r["layout"] == layout)

    def test_answers_match_full_table(self):
        self.assertTrue(all(self.result["per_seed"][0]["answers"].values()))

    def test_csv_scans_every_file(self):
        seed = self.result["per_seed"][0]
        for q in ("Q1", "Q3", "Q4"):
            self.assertEqual(self.scan(q, "csv")["bytes"], seed["storage_bytes"]["csv"])

    def test_partition_pruning_opens_one_file_for_q1(self):
        self.assertEqual(self.scan("Q1", "parquet_dt_zone")["files_opened"], 1)
        self.assertEqual(self.scan("Q3", "parquet_dt_zone")["files_opened"], 2 * 4)

    def test_parquet_reads_less_than_csv(self):
        for q in ("Q1", "Q2", "Q3", "Q5"):
            self.assertLess(self.scan(q, "parquet")["bytes"], self.scan(q, "csv")["bytes"])

    def test_deterministic(self):
        again = run(sensors=8, zones=4, days=2, period_s=300, seeds=(5,))
        self.assertEqual(again["per_seed"][0]["scans"], self.result["per_seed"][0]["scans"])

    def test_queries_cover_last_hour(self):
        q2 = queries(2)[1]
        self.assertEqual(q2["ts_min"], datetime(2026, 1, 2, 23, 0))


if __name__ == "__main__":
    unittest.main()
