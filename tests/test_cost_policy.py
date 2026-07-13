from __future__ import annotations

import unittest

from src.execution.cost_policy import calculate_net_expected_edge, legacy_cost_policy


class CostPolicyTests(unittest.TestCase):
    def test_legacy_defaults_preserve_existing_total_cost(self):
        policy = legacy_cost_policy(0.35, 0.15)
        self.assertEqual("legacy-dashboard-cost-v1", policy.policy_id)
        self.assertAlmostEqual(50.0, policy.total_round_trip_bps)

    def test_net_expected_edge_deducts_benchmark_and_cost(self):
        policy = legacy_cost_policy(0.35, 0.15)
        self.assertAlmostEqual(3.5, calculate_net_expected_edge(6.0, 2.0, policy))

    def test_invalid_inputs_do_not_emit_nan_or_infinity(self):
        policy = legacy_cost_policy(float("nan"), float("inf"))
        self.assertEqual(0.0, policy.total_round_trip_bps)
        self.assertIsNone(calculate_net_expected_edge(float("nan"), 0, policy))


if __name__ == "__main__":
    unittest.main()
