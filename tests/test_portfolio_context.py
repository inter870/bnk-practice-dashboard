from __future__ import annotations

from datetime import date, timedelta
import math
import unittest

from src.institutional.models import DataSourceMeta, ProviderResult
from src.portfolio.context import (
    PortfolioContext,
    PortfolioContextValidationError,
    adapt_legacy_csv_rows,
    calculate_date_aligned_covariance_risk_contributions,
    calculate_portfolio_risk_contributions,
    parse_legacy_portfolio_csv,
    reconstruct_portfolio_value_history,
)
from src.portfolio.models import Holding
from src.portfolio.service import rowsToHoldings


def source_meta() -> DataSourceMeta:
    return DataSourceMeta(
        source="UnitTest",
        provider="UnitTest",
        source_url=None,
        as_of_date="2026-07-10",
        available_at="2026-07-10T09:00:00+09:00",
        fetched_at="2026-07-10T09:01:00+09:00",
        frequency="snapshot",
        unit="KRW",
        quality_score=90,
        is_fallback=False,
        stale_data_flag=False,
    )


def holding(
    symbol: str,
    quantity: float,
    current_price: float,
    *,
    average_cost: float | None = None,
    asset_class: str = "stocks",
    currency: str = "KRW",
) -> Holding:
    return Holding(
        id=f"test-{symbol}",
        symbol=symbol,
        name=symbol,
        asset_class=asset_class,  # type: ignore[arg-type]
        quantity=quantity,
        average_cost=current_price if average_cost is None else average_cost,
        current_price=current_price,
        currency=currency,
    )


def iso_dates(count: int) -> list[str]:
    start = date(2026, 1, 1)
    return [(start + timedelta(days=index)).isoformat() for index in range(count)]


class DataContractTests(unittest.TestCase):
    def test_data_source_meta_new_fields_are_backward_compatible_defaults(self) -> None:
        meta = source_meta()
        self.assertIsNone(meta.published_at)
        self.assertIsNone(meta.timezone)
        self.assertIsNone(meta.currency)
        self.assertEqual(meta.data_mode, "unavailable")
        self.assertEqual(meta.quality_flags, ())
        self.assertIsNone(meta.provider_version)
        self.assertIsNone(meta.error_code)

        result: ProviderResult[list[int]] = ProviderResult(data=[1, 2], meta=meta)
        self.assertTrue(result.ok)
        self.assertEqual(result.value, [1, 2])
        self.assertEqual(result.metadata, meta)

    def test_computed_total_is_authoritative_and_discrepancy_is_diagnostic(self) -> None:
        context = PortfolioContext(
            holdings=(holding("AAA", 10, 100), holding("BBB", 2, 200)),
            cash=600,
            declared_total=2_100,
            meta=source_meta(),
        )
        self.assertEqual(context.holdings_market_value, 1_400)
        self.assertEqual(context.computed_total, 2_000)
        self.assertEqual(context.total_value, 2_000)
        self.assertEqual(context.declared_total_discrepancy, 100)
        self.assertAlmostEqual(context.declared_total_discrepancy_ratio or 0.0, 0.05)

    def test_negative_values_and_duplicate_cash_are_rejected(self) -> None:
        with self.assertRaises(PortfolioContextValidationError):
            PortfolioContext((holding("AAA", 1, 100),), cash=-1)
        with self.assertRaises(PortfolioContextValidationError):
            PortfolioContext((holding("AAA", -1, 100),), cash=0)
        with self.assertRaises(PortfolioContextValidationError):
            PortfolioContext((holding("CASH", 1, 100, asset_class="cash"),), cash=100)

    def test_cash_above_declared_total_is_rejected(self) -> None:
        with self.assertRaises(PortfolioContextValidationError) as error:
            PortfolioContext((holding("AAA", 1, 100),), cash=1_100, declared_total=1_000)
        self.assertTrue(
            any(issue.code == "cash_exceeds_declared_total" for issue in error.exception.issues)
        )

    def test_mixed_currency_is_rejected_without_timestamped_fx_conversion(self) -> None:
        with self.assertRaises(PortfolioContextValidationError) as error:
            PortfolioContext(
                (
                    holding("005930", 1, 100_000, currency="KRW"),
                    holding("AAPL", 1, 100, currency="USD"),
                ),
                cash=0,
                currency="KRW",
            )
        self.assertTrue(
            any(issue.code == "mixed_currency_requires_fx" for issue in error.exception.issues)
        )


class LegacyCsvAdapterTests(unittest.TestCase):
    def test_portfolio_source_metadata_preserves_as_of_and_flags_missing_timestamp(self) -> None:
        stamped = adapt_legacy_csv_rows(
            [{"code": "005930", "qty": 1, "avg_price": 70_000}],
            current_prices={"005930": 71_000},
            as_of_date="2026-07-10T09:00:00+09:00",
        )
        self.assertTrue(stamped.ok)
        self.assertEqual(stamped.meta.as_of_date, "2026-07-10")
        self.assertEqual(stamped.meta.available_at, "2026-07-10T09:00:00+09:00")
        self.assertFalse(stamped.meta.stale_data_flag)
        self.assertFalse(stamped.meta.missing_data_flag)

        unstamped = adapt_legacy_csv_rows(
            [{"code": "005930", "qty": 1, "avg_price": 70_000}],
            current_prices={"005930": 71_000},
        )
        self.assertTrue(unstamped.ok)
        self.assertTrue(unstamped.meta.stale_data_flag)
        self.assertTrue(unstamped.meta.missing_data_flag)
        self.assertIn("timestamp_missing", unstamped.meta.quality_flags)

    def test_adapter_uses_current_price_and_preserves_declared_discrepancy(self) -> None:
        result = adapt_legacy_csv_rows(
            [{"code": "5930", "qty": "2", "avg_price": "70", "sector": "Semiconductor"}],
            cash=100,
            declared_total=350,
            current_prices={"005930": 100},
            code_to_name={"005930": "Samsung Electronics"},
        )
        self.assertTrue(result.ok)
        context = result.data
        self.assertIsNotNone(context)
        assert context is not None
        self.assertEqual(context.holdings[0].symbol, "005930")
        self.assertEqual(context.holdings[0].current_price, 100)
        self.assertEqual(context.computed_total, 300)
        self.assertEqual(context.declared_total_discrepancy, 50)

    def test_adapter_reports_row_and_cash_errors_without_partial_context(self) -> None:
        result = adapt_legacy_csv_rows(
            [{"code": "005930", "qty": -1, "avg_price": 70_000}],
            cash=-100,
        )
        self.assertFalse(result.ok)
        self.assertIsNone(result.data)
        self.assertEqual(result.status, "error")
        self.assertEqual(result.meta.error_code, "legacy_csv_validation_failed")
        self.assertTrue(any("negative_quantity" in error for error in result.errors))
        self.assertTrue(any("negative_cash" in error for error in result.errors))

    def test_text_parser_validates_required_columns(self) -> None:
        invalid = parse_legacy_portfolio_csv("code,qty\n005930,2")
        self.assertFalse(invalid.ok)
        self.assertIn("missing_required_columns:avg_price", invalid.errors)

        valid = parse_legacy_portfolio_csv(
            "code,qty,avg_price,current_price\n005930,2,70000,71000",
            cash=10,
        )
        self.assertTrue(valid.ok)
        self.assertEqual(valid.data.computed_total if valid.data else None, 142_010)
        self.assertNotIn("current_price_fallback_to_average_cost:005930", valid.warnings)

    def test_adapter_rejects_missing_current_price_instead_of_using_average_cost(self) -> None:
        result = parse_legacy_portfolio_csv("code,qty,avg_price\n005930,2,70000", cash=10)

        self.assertFalse(result.ok)
        self.assertIsNone(result.data)
        self.assertEqual(result.status, "error")
        self.assertTrue(any("current_price_missing" in error for error in result.errors))
        self.assertFalse(any("fallback_to_average_cost" in warning for warning in result.warnings))

    def test_legacy_service_never_returns_a_partially_priced_portfolio(self) -> None:
        rows = [
            {"code": "005930", "qty": 1, "avg_price": 70_000},
            {"code": "000660", "qty": 1, "avg_price": 150_000},
        ]
        snapshots = {"005930": type("Snapshot", (), {"last_close": 71_000})()}

        self.assertEqual(rowsToHoldings(rows, snapshots, {}), [])


class PortfolioHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = PortfolioContext(
            holdings=(holding("AAA", 2, 100), holding("BBB", 1, 200)),
            cash=50,
            meta=source_meta(),
        )
        self.dates = iso_dates(75)

    def test_fixed_current_quantities_pass_exact_60_day_80_percent_gate(self) -> None:
        prices = {
            "AAA": {day: 100 + index for index, day in enumerate(self.dates)},
            "BBB": {day: 200 + index for index, day in enumerate(self.dates) if index >= 15},
        }
        result = reconstruct_portfolio_value_history(self.context, prices)
        self.assertTrue(result.ok)
        history = result.data
        self.assertIsNotNone(history)
        assert history is not None
        self.assertEqual(history.coverage.aligned_days, 60)
        self.assertAlmostEqual(history.coverage.coverage_ratio, 0.8)
        self.assertTrue(history.coverage.passed)
        self.assertEqual(len(history.points), 60)
        self.assertEqual(history.quantities, {"AAA": 2.0, "BBB": 1.0})
        self.assertEqual(history.points[0].total_value, 2 * 115 + 215 + 50)
        self.assertFalse(history.supports_realized_performance)
        self.assertEqual(history.methodology, "current_holdings_fixed_quantity_risk_proxy")

    def test_history_gate_blocks_below_minimum_days_and_coverage(self) -> None:
        prices = {
            "AAA": {day: 100 + index for index, day in enumerate(self.dates)},
            "BBB": {day: 200 + index for index, day in enumerate(self.dates) if index >= 16},
        }
        result = reconstruct_portfolio_value_history(self.context, prices)
        self.assertFalse(result.ok)
        self.assertIsNotNone(result.data)
        assert result.data is not None
        self.assertEqual(result.data.coverage.aligned_days, 59)
        self.assertFalse(result.data.coverage.passed)
        self.assertTrue(any(error.startswith("insufficient_history_days") for error in result.errors))
        self.assertTrue(any(error.startswith("insufficient_history_coverage") for error in result.errors))


class CovarianceRiskContributionTests(unittest.TestCase):
    def test_pure_calculation_aligns_return_dates_and_contributions_sum_to_one(self) -> None:
        dates = iso_dates(5)
        result = calculate_date_aligned_covariance_risk_contributions(
            {"AAA": 0.6, "BBB": 0.4},
            {
                "AAA": {dates[0]: 0.01, dates[1]: 0.02, dates[2]: -0.01, dates[3]: 0.03},
                "BBB": {dates[1]: 0.00, dates[2]: 0.01, dates[3]: -0.02, dates[4]: 0.04},
            },
            minimum_observations=3,
        )
        self.assertEqual(result.aligned_dates, tuple(dates[1:4]))
        self.assertEqual(result.observations, 3)
        self.assertAlmostEqual(result.covariance_matrix["AAA"]["BBB"], result.covariance_matrix["BBB"]["AAA"])
        self.assertTrue(math.isfinite(result.annualized_volatility))
        self.assertAlmostEqual(sum(row.contribution_pct for row in result.contributions), 1.0)

    def test_portfolio_risk_uses_coverage_gate_and_current_market_value_weights(self) -> None:
        dates = iso_dates(60)
        prices = {
            "AAA": {day: 100 + index * 0.4 + (index % 3) for index, day in enumerate(dates)},
            "BBB": {day: 200 + index * 0.7 + (index % 4) * 0.5 for index, day in enumerate(dates)},
        }
        context = PortfolioContext(
            holdings=(holding("AAA", 1, 100), holding("BBB", 1, 200)),
            cash=100,
            meta=source_meta(),
        )
        result = calculate_portfolio_risk_contributions(context, prices)
        self.assertTrue(result.ok)
        risk = result.data
        self.assertIsNotNone(risk)
        assert risk is not None
        self.assertEqual(risk.coverage.aligned_days, 60)
        self.assertEqual(risk.observations, 59)
        weights = {row.symbol: row.weight for row in risk.contributions}
        self.assertAlmostEqual(weights["AAA"], 0.25)
        self.assertAlmostEqual(weights["BBB"], 0.50)
        self.assertAlmostEqual(sum(row.contribution_pct for row in risk.contributions), 1.0)


if __name__ == "__main__":
    unittest.main()
