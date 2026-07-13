from __future__ import annotations

from datetime import datetime
import math
import unittest
from zoneinfo import ZoneInfo

from src.kr_alpha.backtest import next_tradable_bar, simulate_long_trade, summarize_backtest
from src.kr_alpha.compounding import CompoundingAssumptions, analyze_compounding, required_monthly_return
from src.kr_alpha.config import KRAlphaConfig
from src.kr_alpha.fixtures import FixtureKRAlphaProvider


KST = ZoneInfo("Asia/Seoul")
DECISION = datetime(2026, 6, 18, 16, 0, tzinfo=KST)


class KRAlphaBacktestCompoundingTests(unittest.TestCase):
    def setUp(self):
        self.config = KRAlphaConfig()
        self.stocks = FixtureKRAlphaProvider().snapshot(DECISION)

    def test_entry_is_strictly_after_decision_and_tradable(self):
        entry = next_tradable_bar(self.stocks[0].bars, DECISION)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertGreater(entry.bar_start, DECISION)
        self.assertFalse(entry.is_suspended)
        self.assertFalse(entry.is_vi)
        self.assertNotEqual("UP", entry.limit_state)

    def test_costs_reduce_return_and_liquidity_causes_partial_fill(self):
        normal = simulate_long_trade(self.stocks[0], DECISION, self.config)
        self.assertIsNotNone(normal.gross_return)
        self.assertIsNotNone(normal.net_return)
        self.assertLess(normal.net_return, normal.gross_return)
        illiquid = next(stock for stock in self.stocks if "illiquid" in stock.event_flags)
        partial = simulate_long_trade(illiquid, DECISION, self.config)
        self.assertLess(partial.fill_ratio, 1.0)
        self.assertIn(partial.status, {"PARTIAL", "PENDING"})

    def test_delisting_is_not_removed_from_fixture_universe(self):
        delisting = next(stock for stock in self.stocks if "delisting" in stock.event_flags)
        self.assertFalse(delisting.security.is_active)
        self.assertIsNotNone(delisting.security.delisted_at)
        self.assertIn(delisting, self.stocks)

    def test_backtest_separates_gross_and_net(self):
        trades = tuple(simulate_long_trade(stock, DECISION, self.config) for stock in self.stocks)
        summary = summarize_backtest(trades)
        self.assertEqual("FIXTURE_ONLY", summary.data_quality_status)
        self.assertIsNotNone(summary.gross_return)
        self.assertIsNotNone(summary.net_return)
        self.assertLess(summary.net_return, summary.gross_return)

    def test_required_compounding_formula(self):
        self.assertAlmostEqual(1.0, required_monthly_return(100.0, 800.0, 3))
        with self.assertRaises(ValueError):
            required_monthly_return(0.0, 100.0, 12)

    def test_monte_carlo_is_seeded_and_extreme_goal_warns(self):
        assumptions = CompoundingAssumptions(10_000_000, 1_000_000_000_000, 12, 0.02, 0.08, simulations=1000, seed=7)
        first = analyze_compounding(assumptions)
        second = analyze_compounding(assumptions)
        self.assertEqual(first.terminal_percentiles, second.terminal_percentiles)
        self.assertEqual(first.target_probability, second.target_probability)
        self.assertTrue(any("100%" in warning for warning in first.warnings))
        self.assertTrue(math.isfinite(first.expected_max_drawdown))


if __name__ == "__main__":
    unittest.main()
