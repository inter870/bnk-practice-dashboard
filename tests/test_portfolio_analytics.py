import math
import unittest

from src.portfolio.analytics import (
    calculateAllocationByAssetClass,
    calculateAllocationDrift,
    calculateAnnualizedVolatility,
    calculateBeta,
    calculateConcentrationRisk,
    calculateDrawdownSeries,
    calculateMaxDrawdown,
    calculateSharpeRatio,
    calculateTopHoldingWeight,
    format_currency,
    format_percent,
    generateRebalanceSuggestions,
)
from src.portfolio.models import Holding, PricePoint, TargetAllocation


def holdings(values):
    return [
        Holding(str(idx), f"T{idx}", f"Test {idx}", asset_class, 1, value * 0.9, value, "KRW")
        for idx, (asset_class, value) in enumerate(values)
    ]


class PortfolioAnalyticsTests(unittest.TestCase):
    def test_allocation_weights_sum_to_one(self):
        allocation = calculateAllocationByAssetClass(holdings([("stocks", 60), ("bonds", 30), ("cash", 10)]))
        self.assertAlmostEqual(sum(row["weight"] for row in allocation.values()), 1.0)

    def test_drift_identifies_overweight_and_underweight(self):
        current = calculateAllocationByAssetClass(holdings([("stocks", 70), ("bonds", 30)]))
        target = [TargetAllocation("stocks", 0.60), TargetAllocation("bonds", 0.35), TargetAllocation("cash", 0.05)]
        drift = calculateAllocationDrift(current, target)
        self.assertEqual(drift["stocks"]["status"], "Overweight")
        self.assertEqual(drift["cash"]["status"], "Underweight")

    def test_rebalance_ignores_tiny_drift_below_threshold(self):
        current = {"stocks": {"weight": 0.61, "value": 61}, "bonds": {"weight": 0.39, "value": 39}}
        target = {"stocks": 0.60, "bonds": 0.40}
        suggestions = generateRebalanceSuggestions(current, target, 100_000, {"threshold": 0.03, "minimum_trade_amount": 100})
        self.assertEqual(suggestions, [])

    def test_max_drawdown_rising_falling_and_mixed_series(self):
        rising = [PricePoint("2024-01-01", 100), PricePoint("2024-01-02", 120)]
        falling = [PricePoint("2024-01-01", 100), PricePoint("2024-01-02", 80)]
        mixed = [PricePoint("2024-01-01", 100), PricePoint("2024-01-02", 130), PricePoint("2024-01-03", 91)]
        self.assertEqual(calculateMaxDrawdown(rising), 0.0)
        self.assertAlmostEqual(calculateMaxDrawdown(falling), -0.2)
        self.assertAlmostEqual(calculateMaxDrawdown(mixed), -0.3)
        self.assertEqual(calculateDrawdownSeries(rising)[-1]["drawdown"], 0.0)

    def test_sharpe_handles_zero_volatility(self):
        self.assertIsNone(calculateSharpeRatio(0.1, 0.0, 0.02))
        self.assertEqual(calculateAnnualizedVolatility([0.01]), 0.0)

    def test_beta_handles_mismatched_and_missing_data_safely(self):
        self.assertIsNone(calculateBeta([], []))
        self.assertIsNone(calculateBeta([0.1, 0.2], [0.0, 0.0]))
        beta = calculateBeta([0.02, 0.03, -0.01], [0.01, 0.02, -0.02, 0.04])
        self.assertIsNotNone(beta)

    def test_concentration_risk_labels_low_medium_high(self):
        low = calculateConcentrationRisk(holdings([("stocks", 10), ("stocks", 10), ("bonds", 10), ("bonds", 10), ("cash", 10), ("stocks", 10), ("bonds", 10), ("cash", 10), ("stocks", 10), ("bonds", 10), ("cash", 10)]))
        medium = calculateConcentrationRisk(holdings([("stocks", 15), ("stocks", 15), ("bonds", 14), ("bonds", 14), ("cash", 14), ("stocks", 14), ("bonds", 14)]))
        high = calculateConcentrationRisk(holdings([("stocks", 25), ("stocks", 75)]))
        self.assertEqual(low["level"], "Low")
        self.assertEqual(medium["level"], "Medium")
        self.assertEqual(high["level"], "High")
        self.assertGreater(calculateTopHoldingWeight(holdings([("stocks", 25), ("stocks", 75)])), 0.2)

    def test_concentration_uses_cash_inclusive_total_when_provided(self):
        portfolio = holdings([("stocks", 70_000)])

        concentration = calculateConcentrationRisk(portfolio, total_portfolio_value=970_000)

        self.assertAlmostEqual(concentration["topHoldingWeight"], 70_000 / 970_000)
        self.assertAlmostEqual(concentration["herfindahlIndex"], (70_000 / 970_000) ** 2)
        self.assertEqual(concentration["level"], "Low")

    def test_no_nan_or_infinity_outputs(self):
        allocation = calculateAllocationByAssetClass([{"quantity": 0, "currentPrice": float("nan"), "assetClass": "stocks"}])
        for row in allocation.values():
            self.assertTrue(math.isfinite(row["weight"]))
            self.assertTrue(math.isfinite(row["value"]))

    def test_formatting_handles_null_values(self):
        self.assertEqual(format_currency(None), "N/A")
        self.assertEqual(format_percent(None), "N/A")
        self.assertEqual(format_currency(1234), "1,234원")
        self.assertEqual(format_percent(0.1234, signed=True), "+12.3%")

    def test_dashboard_metric_format_examples(self):
        self.assertEqual(format_percent(0.084), "8.4%")
        self.assertEqual(format_percent(0.976, signed=True), "+97.6%")
        self.assertEqual(format_percent(0.452), "45.2%")
        self.assertEqual(format_percent(-0.125), "-12.5%")
        self.assertEqual(format_percent(0.383, signed=True), "+38.3%")
        self.assertEqual(format_percent(0.262), "26.2%")
        self.assertEqual(format_percent(0.0, signed=True), "0.0%")
        self.assertEqual(f"{0.12:.2f}", "0.12")
        self.assertEqual(f"{1.30:.2f}", "1.30")
        self.assertEqual(f"{0.202:.3f}", "0.202")


if __name__ == "__main__":
    unittest.main()
