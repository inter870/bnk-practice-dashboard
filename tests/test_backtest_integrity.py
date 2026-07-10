from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
import unittest

from src.korea_equity.backtest_engine import (
    _crossSectionMetrics,
    _timestamp,
    applyPointInTimeCutoff,
    calculateRebalanceCosts,
    runChronologicalWalkForwardBacktest,
    runRollingValidation,
    runWalkForwardBacktest,
    summarizeBacktest,
)


FEATURES = [
    {
        "code": "A",
        "total_score": 90,
        "as_of_date": "2020-01-01",
        "available_at": "2020-01-01",
        "source": "feature_store",
    },
    {
        "code": "B",
        "total_score": 80,
        "as_of_date": "2020-01-01",
        "available_at": "2020-01-01",
        "source": "feature_store",
    },
    {
        "code": "B",
        "total_score": 100,
        "as_of_date": "2020-01-01",
        "available_at": "2020-01-02",
        "source": "late_filing",
    },
]

PRICES = [
    {"code": "A", "timestamp": "2020-01-01", "close": 999, "source": "decision_close_must_not_be_used"},
    {"code": "A", "timestamp": "2020-01-02", "close": 100, "source": "price_store"},
    {"code": "A", "timestamp": "2020-02-02", "close": 110, "source": "price_store"},
    {"code": "A", "timestamp": "2020-03-02", "close": 99, "source": "price_store"},
    {"code": "B", "timestamp": "2020-01-01", "close": 999, "source": "decision_close_must_not_be_used"},
    {"code": "B", "timestamp": "2020-01-02", "close": 100, "source": "price_store"},
    {"code": "B", "timestamp": "2020-02-02", "close": 100, "source": "price_store"},
    {"code": "B", "timestamp": "2020-03-02", "close": 110, "source": "price_store"},
]

HISTORICAL_UNIVERSE = [
    {"timestamp": "2020-01-01", "members": ["A", "B"], "source": "universe_archive"},
    {"timestamp": "2020-02-01", "members": ["A", "B"], "source": "universe_archive"},
    {"timestamp": "2020-03-01", "members": ["A", "B"], "source": "universe_archive"},
]

BENCHMARK_PRICES = [
    {"timestamp": "2020-01-02", "close": 100, "source": "benchmark_store"},
    {"timestamp": "2020-02-02", "close": 102, "source": "benchmark_store"},
    {"timestamp": "2020-03-02", "close": 103, "source": "benchmark_store"},
]


class BacktestIntegrityTests(unittest.TestCase):
    def test_naive_korean_date_precedes_same_day_nine_am_filing(self) -> None:
        decision = _timestamp("2020-01-01")
        filing = _timestamp("2020-01-01T09:00:00+09:00")
        self.assertIsNotNone(decision)
        self.assertIsNotNone(filing)
        self.assertIsNotNone(decision.tzinfo)
        self.assertLess(decision, filing)

    def test_constant_scores_do_not_generate_cross_section_alpha_metrics(self) -> None:
        metrics = _crossSectionMetrics([10.0, 10.0], [0.10, -0.10])
        self.assertIsNone(metrics["factor_ic"])
        self.assertIsNone(metrics["rank_ic"])
        self.assertIsNone(metrics["top_decile_spread"])

    def test_current_scores_are_never_replayed_as_operating_performance(self) -> None:
        scores = [SimpleNamespace(code="A", total_score=90), SimpleNamespace(code="B", total_score=70)]

        walk_forward = runWalkForwardBacktest(scores)
        self.assertEqual(walk_forward["status"], "validation_unavailable")
        self.assertEqual(walk_forward["data_mode"], "synthetic_demo")
        self.assertTrue(walk_forward["synthetic"])
        self.assertEqual(walk_forward["strategy_returns"], [])
        self.assertEqual(walk_forward["benchmark_returns"], [])

        validation = runRollingValidation(scores)
        self.assertFalse(validation["validation_available"])
        self.assertIsNone(validation["factor_ic"])

        summary = summarizeBacktest(scores)
        self.assertIsNone(summary.total_return)
        self.assertIsNone(summary.cagr)
        self.assertIsNone(summary.sharpe_ratio)
        self.assertIsNone(summary.precision_at_top10)
        self.assertTrue(any("synthetic_demo" in note for note in summary.notes))
        self.assertTrue(any("validation_unavailable" in note for note in summary.notes))

    def test_historical_universe_is_a_hard_validation_gate(self) -> None:
        walk_forward = runChronologicalWalkForwardBacktest(FEATURES, PRICES, None)
        self.assertEqual(walk_forward["reason"], "historical_universe_missing")
        self.assertFalse(walk_forward["validation_available"])
        self.assertEqual(walk_forward["strategy_returns"], [])

        summary = summarizeBacktest(FEATURES, PRICES, None)
        self.assertIsNone(summary.cagr)
        self.assertIsNone(summary.sharpe_ratio)
        self.assertTrue(any("역사적 유니버스" in note for note in summary.notes))

    def test_chronological_walk_forward_applies_cutoff_and_all_rebalance_costs(self) -> None:
        features_before = deepcopy(FEATURES)
        prices_before = deepcopy(PRICES)
        universe_before = deepcopy(HISTORICAL_UNIVERSE)

        result = runChronologicalWalkForwardBacktest(
            FEATURES,
            PRICES,
            HISTORICAL_UNIVERSE,
            BENCHMARK_PRICES,
            top_n=1,
            weighting="equal",
            transaction_cost_bps=10,
            slippage_bps=5,
            tax_bps=20,
        )

        self.assertEqual(result["status"], "validated")
        self.assertEqual(result["data_mode"], "historical_point_in_time")
        self.assertFalse(result["synthetic"])
        self.assertEqual(len(result["periods"]), 2)

        first, second = result["periods"]
        self.assertEqual(first["weights"], {"A": 1.0})
        self.assertNotIn("B", first["selected_features"])
        self.assertEqual(second["weights"], {"B": 1.0})

        self.assertAlmostEqual(first["gross_return"], 0.10)
        self.assertAlmostEqual(first["turnover"], 1.0)
        self.assertAlmostEqual(first["transaction_cost"], 0.001)
        self.assertAlmostEqual(first["slippage_cost"], 0.0005)
        self.assertAlmostEqual(first["tax_cost"], 0.0)
        self.assertAlmostEqual(first["net_return"], 0.0985)

        self.assertAlmostEqual(second["gross_return"], 0.10)
        self.assertAlmostEqual(second["turnover"], 1.0)
        self.assertAlmostEqual(second["sell_turnover"], 1.0)
        self.assertAlmostEqual(second["transaction_cost"], 0.001)
        self.assertAlmostEqual(second["slippage_cost"], 0.0005)
        self.assertAlmostEqual(second["tax_cost"], 0.002)
        self.assertAlmostEqual(second["net_return"], 0.0965)
        self.assertEqual(first["execution_at"][:10], "2020-01-02")
        self.assertEqual(first["exit_at"][:10], "2020-02-02")

        for period in result["periods"]:
            self.assertEqual(period["unit"], "decimal_return")
            self.assertEqual(period["quality_status"], "point_in_time_validated")
            self.assertTrue(period["source"])
            self.assertTrue(period["as_of_date"])
            self.assertTrue(period["available_at"])

        self.assertEqual(FEATURES, features_before)
        self.assertEqual(PRICES, prices_before)
        self.assertEqual(HISTORICAL_UNIVERSE, universe_before)

    def test_point_in_time_cutoff_excludes_late_features_and_future_periods(self) -> None:
        visible = applyPointInTimeCutoff(FEATURES, "2020-01-01")
        self.assertEqual({row["code"] for row in visible}, {"A", "B"})
        self.assertEqual(len(visible), 2)

        result = runChronologicalWalkForwardBacktest(
            FEATURES,
            PRICES,
            HISTORICAL_UNIVERSE,
            point_in_time_cutoff="2020-02-02",
            top_n=1,
            weighting="equal",
        )
        self.assertEqual(result["status"], "validated")
        self.assertEqual(len(result["periods"]), 1)
        self.assertEqual(result["periods"][0]["weights"], {"A": 1.0})
        self.assertEqual(result["end_date"], "2020-02-02")

    def test_same_timestamp_close_is_never_used_as_entry_price(self) -> None:
        same_close_only = [
            {"code": "A", "timestamp": "2020-01-01", "close": 100, "source": "price_store"},
            {"code": "A", "timestamp": "2020-02-01", "close": 110, "source": "price_store"},
            {"code": "B", "timestamp": "2020-01-01", "close": 100, "source": "price_store"},
            {"code": "B", "timestamp": "2020-02-01", "close": 100, "source": "price_store"},
        ]

        result = runChronologicalWalkForwardBacktest(
            FEATURES,
            same_close_only,
            HISTORICAL_UNIVERSE[:2],
            top_n=1,
            weighting="equal",
        )

        self.assertEqual(result["status"], "validation_unavailable")
        self.assertEqual(result["reason"], "selected_price_history_incomplete")

    def test_missing_selected_price_invalidates_the_whole_run(self) -> None:
        incomplete_prices = [
            row for row in PRICES if not (row["code"] == "B" and row["timestamp"] == "2020-03-02")
        ]
        incomplete_prices.append(
            {"code": "B", "timestamp": "2020-02-15", "close": 105, "source": "stale_price"}
        )
        result = runChronologicalWalkForwardBacktest(
            FEATURES,
            incomplete_prices,
            HISTORICAL_UNIVERSE,
            top_n=1,
            weighting="equal",
        )
        self.assertEqual(result["status"], "validation_unavailable")
        self.assertEqual(result["reason"], "selected_price_history_incomplete")
        self.assertEqual(result["strategy_returns"], [])
        self.assertEqual(result["periods"], [])

    def test_incomplete_nonselected_forward_prices_do_not_create_precision_metrics(self) -> None:
        partial_cross_section = [
            row for row in PRICES if not (row["code"] == "A" and row["timestamp"] == "2020-03-02")
        ]
        result = runChronologicalWalkForwardBacktest(
            FEATURES,
            partial_cross_section,
            HISTORICAL_UNIVERSE,
            top_n=1,
            weighting="equal",
        )
        self.assertEqual(result["status"], "validated")
        self.assertEqual(result["cross_section_validation_status"], "validation_unavailable")
        self.assertLess(result["validation_coverage"], 1.0)
        self.assertEqual(result["feature_scores"], [])
        self.assertEqual(result["forward_returns"], [])

        summary = summarizeBacktest(
            FEATURES,
            partial_cross_section,
            HISTORICAL_UNIVERSE,
            top_n=1,
            weighting="equal",
        )
        self.assertIsNotNone(summary.cagr)
        self.assertIsNone(summary.precision_at_top10)
        self.assertIsNone(summary.factor_ic)

    def test_cross_section_validation_requires_common_execution_and_exit_window(self) -> None:
        unequal_windows = [
            {"code": "A", "timestamp": "2020-01-02", "close": 100, "source": "price_store"},
            {"code": "A", "timestamp": "2020-02-02", "close": 110, "source": "price_store"},
            {"code": "B", "timestamp": "2020-01-15", "close": 100, "source": "price_store"},
            {"code": "B", "timestamp": "2020-02-15", "close": 120, "source": "price_store"},
        ]
        result = runChronologicalWalkForwardBacktest(
            FEATURES,
            unequal_windows,
            HISTORICAL_UNIVERSE[:2],
            top_n=1,
            weighting="equal",
        )

        self.assertEqual(result["status"], "validated")
        self.assertEqual(result["cross_section_validation_status"], "validation_unavailable")
        self.assertEqual(result["validation_periods"], [])

    def test_rebalance_cost_helper_uses_sell_notional_for_tax(self) -> None:
        initial = calculateRebalanceCosts({}, {"A": 1.0}, 10, 5, 20)
        switched = calculateRebalanceCosts({"A": 1.0}, {"B": 1.0}, 10, 5, 20)

        self.assertAlmostEqual(initial["turnover"], 1.0)
        self.assertAlmostEqual(initial["tax_cost"], 0.0)
        self.assertAlmostEqual(switched["turnover"], 1.0)
        self.assertAlmostEqual(switched["sell_turnover"], 1.0)
        self.assertAlmostEqual(switched["tax_cost"], 0.002)

    def test_summary_generates_metrics_only_for_validated_history(self) -> None:
        summary = summarizeBacktest(
            FEATURES,
            PRICES,
            HISTORICAL_UNIVERSE,
            BENCHMARK_PRICES,
            top_n=1,
            weighting="equal",
        )
        self.assertIsNotNone(summary.total_return)
        self.assertIsNotNone(summary.cagr)
        self.assertIsNotNone(summary.annualized_volatility)
        self.assertIsNotNone(summary.sharpe_ratio)
        self.assertEqual(summary.start_date, "2020-01-02")
        self.assertEqual(summary.end_date, "2020-03-02")
        self.assertTrue(any("historical_point_in_time" in note for note in summary.notes))


if __name__ == "__main__":
    unittest.main()
