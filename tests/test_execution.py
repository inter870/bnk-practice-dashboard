import unittest

import pandas as pd

from src.execution import build_execution_plan, should_block_for_execution


def make_history(volume: int = 100_000, periods: int = 60) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=periods, freq="B")
    close = pd.Series([100 + i for i in range(periods)], index=idx)
    return pd.DataFrame(
        {
            "Open": close,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": volume,
        },
        index=idx,
    )


class ExecutionTests(unittest.TestCase):
    def test_zero_volume_blocks_execution(self):
        plan = build_execution_plan(make_history(volume=0), target_order_value=1_000_000)
        self.assertEqual(plan.execution_quality_score, 0)
        self.assertEqual(plan.recommended_order_style, "대기")

    def test_high_order_size_increases_market_impact(self):
        hist = make_history(volume=100_000)
        small = build_execution_plan(hist, target_order_value=1_000_000)
        large = build_execution_plan(hist, target_order_value=500_000_000)
        self.assertGreater(large.total_execution_cost_bps, small.total_execution_cost_bps)
        self.assertLess(large.execution_quality_score, small.execution_quality_score)

    def test_missing_order_book_uses_unavailable_fields(self):
        plan = build_execution_plan(make_history(), target_order_value=1_000_000)
        self.assertIn("bid", plan.unavailable_fields)
        self.assertIn("ask", plan.unavailable_fields)
        self.assertIsNone(plan.estimated_spread_cost_bps)

    def test_expected_edge_below_execution_cost_blocks_buy_action(self):
        plan = build_execution_plan(make_history(), target_order_value=500_000_000, expected_edge_pct=0.1)
        self.assertTrue(should_block_for_execution(plan, 0.1))


if __name__ == "__main__":
    unittest.main()

