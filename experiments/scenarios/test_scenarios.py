"""Checks for the shared price book, service pack and scenarios."""
import unittest
from decimal import Decimal as D

from pricebook import PriceBook, load_scenario
from service_pack import billed, billed_units, fargate_provision, max_pods


class PriceBookTest(unittest.TestCase):
    pb = PriceBook()

    def test_known_rates(self):
        self.assertEqual(self.pb.rate("AmazonEC2", "APN2-NatGateway-Hours"), D("0.059"))
        self.assertEqual(self.pb.rate("AmazonVPC", "APN2-VpcEndpoint-Hours"), D("0.013"))
        self.assertEqual(self.pb.rate("AmazonElastiCache", "APN2-CachedData:Valkey"), D("0.101"))
        self.assertEqual(self.pb.rate("AmazonRDS", "APN2-InstanceUsage:db.t4g.medium"), D("0.102"))

    def test_missing_rate_raises(self):
        with self.assertRaises(KeyError):
            self.pb.rate("AWSGlue", "APN2-PythonShell-DPU-Hour")

    def test_tiered(self):
        # REST API: 333 M at 3.50/M, then 3.19/M
        cost = self.pb.tiered("AmazonApiGateway", "APN2-ApiGatewayRequest", 400_000_000)
        self.assertEqual(cost, D(333) * D("3.5") + D(67) * D("3.19"))

    def test_snapshot_has_missing_list(self):
        self.assertGreaterEqual(len(self.pb.data["missing"]), 1)
        self.assertEqual(self.pb.data["retrieved"], "2026-11-15")


class ServicePackTest(unittest.TestCase):
    def test_billed(self):
        self.assertEqual(billed(200, 5120), 5120)
        self.assertEqual(billed(0, 5120, 100), 0)
        self.assertEqual(billed(30, 1, 60), 60)
        self.assertEqual(billed_units("guardrails_text_unit", 1001), 2)

    def test_fargate(self):
        self.assertEqual(fargate_provision(1, 8, "ecs"), (D(1), D(8)))
        self.assertEqual(fargate_provision(1, 8, "eks"), (D(2), D(9)))
        self.assertEqual(fargate_provision("0.25", "0.5", "eks"), (D("0.25"), D(1)))
        self.assertEqual(fargate_provision(2, "15.9", "eks"), (D(4), D(17)))
        self.assertEqual(fargate_provision("0.3", 1, "ecs"), (D("0.5"), D(1)))

    def test_max_pods(self):
        self.assertEqual(max_pods(3, 10, 2), 29)
        self.assertEqual(max_pods(4, 15, 4), 58)
        self.assertEqual(max_pods(15, 50, 96), 250)
        self.assertEqual(max_pods(3, 10, 2, "auto"), 27)


class ScenarioTest(unittest.TestCase):
    def test_scenarios_are_synthetic_and_generic(self):
        for name in ("iot-pipeline-agent", "web-llm-chatbot"):
            s = load_scenario(name)
            self.assertTrue(s["synthetic"])
            self.assertEqual(s["period"]["hours"], 730)


if __name__ == "__main__":
    unittest.main()
