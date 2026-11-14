"""Checks for experiment 032."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from evaluate import agent_tokens, load_scenario

HERE = Path(__file__).resolve().parent
A = load_scenario("iot-pipeline-agent")["agent"]


class AgentTokenTest(unittest.TestCase):
    def test_quadratic_context_growth(self):
        t = agent_tokens(A, 4, "none")
        self.assertEqual(t["in"], 4 * 2100 + 1100 * (0 + 1 + 2 + 3))
        self.assertEqual(t["out"], 1200)

    def test_prefix_below_minimum_is_not_cached(self):
        t = agent_tokens(A, 4, "fixed_prefix", 4096)
        self.assertEqual(t["cache_read"] + t["cache_write"], 0)

    def test_tokens_are_conserved(self):
        base = agent_tokens(A, 6, "none")["in"]
        for mode, mn in (("fixed_prefix", 512), ("automatic", 512), ("automatic", 4096)):
            t = agent_tokens(A, 6, mode, mn)
            self.assertEqual(t["in"] + t["cache_read"] + t["cache_write"], base)

    def test_automatic_starts_when_prefix_reaches_minimum(self):
        t3 = agent_tokens(A, 3, "automatic", 4096)
        self.assertEqual((t3["cache_read"], t3["cache_write"]), (0, 4300))

    def test_result_json_is_reproducible(self):
        out = subprocess.run([sys.executable, "-B", str(HERE / "evaluate.py")], capture_output=True,
                             check=True, encoding="utf-8").stdout
        self.assertEqual(json.loads(out), json.loads((HERE / "result.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
