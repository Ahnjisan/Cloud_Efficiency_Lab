"""Checks for experiment 031."""
import json
import subprocess
import sys
import unittest
from decimal import Decimal as D
from pathlib import Path

from evaluate import eks_ec2_nodes

HERE = Path(__file__).resolve().parent
RESULT = json.loads((HERE / "result.json").read_text(encoding="utf-8"))


class PackingTest(unittest.TestCase):
    def test_one_cpu_pods_fit_one_per_node(self):
        n, info = eks_ec2_nodes(D(1), D("0.5"))
        self.assertEqual(n, 20)  # 1.78 allocatable vCPU leaves no room for a second 1-vCPU pod
        self.assertEqual(info["lower_bound_nodes"]["cpu"], 12)

    def test_small_pods_hit_slot_limit(self):
        n, info = eks_ec2_nodes(D("0.02"), D("0.1"), replicas=60)
        self.assertEqual(info["slots_per_node_for_pods"], 26)
        self.assertEqual(n, 3)
        self.assertEqual(info["binding"], "slots")

    def test_lambda_flat(self):
        for sweep in ("cpu_sweep", "mem_sweep"):
            self.assertEqual(len({r["usd"]["lambda"] for r in RESULT[sweep]["rows"]}), 1)

    def test_fargate_combo_plateau(self):
        rows = {r["cpu"]: r for r in RESULT["cpu_sweep"]["rows"]}
        self.assertEqual(rows["0.5"]["usd"]["ecs_fargate"], rows["0.4"]["usd"]["ecs_fargate"])

    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "evaluate.py")], capture_output=True,
                             check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), RESULT)


if __name__ == "__main__":
    unittest.main()
