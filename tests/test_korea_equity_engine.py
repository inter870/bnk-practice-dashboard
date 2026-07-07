from __future__ import annotations

import math
import unittest

from src.korea_equity import (
    candleSummaryText,
    calculateDisclosureEventScore,
    calculateFactorIC,
    calculateKoreaCompositeAlphaScore,
    calculateKoreaMaxDrawdown,
    calculateMomentumScore,
    calculateMovingAverage,
    calculatePrecisionAtK,
    calculateQualityScore,
    calculateRelativeStrength,
    calculateRiskPenalty,
    calculateSupplyDemandScore,
    calculateTransactionCosts,
    calculateValueScore,
    calculateValueUpScore,
    classifyRecommendationGrade,
    fearGreedBand,
    formatConfidence,
    formatKRW,
    formatPercent,
    formatSignedPercent,
    formatRiskBadge,
    formatTradingValue,
    formatVolume,
    getKoreaDashboardData,
    getKoreaMarketStatus,
    heatmapBucket,
    safeDisplay,
)
from src.korea_equity.factor_engine import calculateSuggestedWeight
from src.korea_equity.models import KoreaDisclosureEvent, KoreaFundamentalSnapshot, KoreaPricePoint, KoreaSupplyDemandPoint
from src.korea_equity.prediction_engine import calculatePredictionConfidence, estimateForwardReturnRange, estimateOutperformanceProbability


def price_points(values: list[float]) -> list[KoreaPricePoint]:
    return [
        KoreaPricePoint(
            date=f"2026-01-{idx + 1:02d}",
            open=value,
            high=value * 1.02,
            low=value * 0.98,
            close=value,
            volume=100_000,
            trading_value=value * 100_000,
        )
        for idx, value in enumerate(values)
    ]


class KoreaEquityEngineTests(unittest.TestCase):
    def test_moving_average_calculation(self) -> None:
        self.assertEqual(calculateMovingAverage([1, 2, 3, 4, 5], 3), 4)

    def test_momentum_and_relative_strength(self) -> None:
        stock = price_points([100 + i for i in range(80)])
        benchmark = price_points([100 + i * 0.2 for i in range(80)])
        self.assertGreater(calculateRelativeStrength(stock, benchmark, 20), 0)
        score = calculateMomentumScore(stock, benchmark)
        self.assertTrue(0 <= score <= 100)

    def test_value_and_quality_handle_missing_fundamentals(self) -> None:
        self.assertTrue(0 <= calculateValueScore(None, []) <= 100)
        self.assertTrue(0 <= calculateQualityScore(None, []) <= 100)

    def test_supply_demand_score_improves_with_buying(self) -> None:
        buying = [KoreaSupplyDemandPoint("2026-01-01", "005930", foreign_net_buy=1_000_000_000, institution_net_buy=800_000_000, pension_net_buy=300_000_000) for _ in range(30)]
        selling = [KoreaSupplyDemandPoint("2026-01-01", "005930", foreign_net_buy=-1_000_000_000, institution_net_buy=-800_000_000, pension_net_buy=-300_000_000) for _ in range(30)]
        self.assertGreater(calculateSupplyDemandScore(buying), calculateSupplyDemandScore(selling))

    def test_disclosure_event_score_positive_and_negative(self) -> None:
        positive = [KoreaDisclosureEvent("1", "005930", "2026-01-01", "자사주", "buyback", "positive", 80, "manual_mock")]
        negative = [KoreaDisclosureEvent("2", "005930", "2026-01-01", "CB", "convertible_bond", "negative", 80, "manual_mock")]
        self.assertGreater(calculateDisclosureEventScore(positive), calculateDisclosureEventScore(negative))

    def test_value_up_score_rewards_low_pbr_and_shareholder_return(self) -> None:
        fundamental = KoreaFundamentalSnapshot("105560", "2026-01-01", pbr=0.5, roe=0.1, dividend_yield=0.05)
        event = KoreaDisclosureEvent("1", "105560", "2026-01-01", "기업가치 제고", "value_up", "positive", 90, "manual_mock")
        self.assertGreater(calculateValueUpScore(fundamental, [event]), 70)

    def test_risk_penalty_increases_with_volatility_drawdown_and_flags(self) -> None:
        smooth = price_points([100 + i * 0.1 for i in range(80)])
        volatile = price_points([100, 130, 70, 140, 65] * 16)
        self.assertGreater(calculateRiskPenalty(volatile, None, ["negative_disclosure"]), calculateRiskPenalty(smooth, None, []))

    def test_composite_score_clamped_and_grade_downgrades_severe_flags(self) -> None:
        status = getKoreaMarketStatus()
        result = calculateKoreaCompositeAlphaScore({"price_series": [], "benchmark_series": [], "fundamentals": None, "events": []}, status)
        self.assertTrue(0 <= result["total_score"] <= 100)
        self.assertEqual(classifyRecommendationGrade(90, 0.9, ["trading_halt"]), "CAUTION")
        self.assertEqual(classifyRecommendationGrade(40, 0.9, ["trading_halt"]), "EXCLUDE")

    def test_expected_return_probability_and_confidence_are_safe(self) -> None:
        forecast = estimateForwardReturnRange(75, 0.25, "neutral")
        self.assertFalse(any(math.isnan(value) or math.isinf(value) for value in forecast.values()))
        prob = estimateOutperformanceProbability(75, 0.7, "neutral")["probability_outperform_1m"]
        self.assertTrue(0 <= prob <= 1)
        good = calculatePredictionConfidence([], [], {"momentum": 70, "quality": 72, "value": 68}, "neutral", 240)
        poor = calculatePredictionConfidence(["stale"], ["high_volatility"], {"momentum": 90, "quality": 20, "value": 30}, "panic", 40)
        self.assertGreater(good, poor)

    def test_suggested_weight_respects_caps_and_liquidity(self) -> None:
        capped = calculateSuggestedWeight(95, 90, 95, {"max_single_stock_weight": 0.03})
        illiquid = calculateSuggestedWeight(95, 90, 20, {"max_single_stock_weight": 0.08})
        self.assertLessEqual(capped, 0.03)
        self.assertLess(illiquid, 0.08)

    def test_backtest_transaction_cost_and_drawdown(self) -> None:
        self.assertGreater(calculateTransactionCosts(0.5, 20), 0)
        self.assertEqual(calculateKoreaMaxDrawdown([1, 2, 3]), 0)
        self.assertLess(calculateKoreaMaxDrawdown([3, 2, 1]), 0)
        self.assertLess(calculateKoreaMaxDrawdown([1, 3, 2, 4]), 0)

    def test_factor_ic_precision_formatter_and_dashboard_data(self) -> None:
        self.assertIsNone(calculateFactorIC([1, None], [None, 0.1]))
        self.assertIsNotNone(calculatePrecisionAtK([80, 70], [0.1, -0.1], 10))
        self.assertEqual(safeDisplay(float("nan")), "-")
        data = getKoreaDashboardData({"limit": 5})
        self.assertTrue(data["topCandidates"])
        self.assertTrue(data["backtest"])

    def test_formatting_helpers_never_render_invalid_numbers(self) -> None:
        self.assertEqual(safeDisplay(float("inf")), "-")
        self.assertEqual(safeDisplay(""), "-")
        self.assertEqual(formatPercent(float("nan")), "-")
        self.assertEqual(formatKRW(None), "-")
        self.assertEqual(formatVolume(12_300), "1.2만주")
        self.assertEqual(formatTradingValue(250_000_000), "2.5억원")
        self.assertEqual(formatConfidence(0.67), "67%")
        self.assertEqual(formatSignedPercent(0.017), "+1.7%")
        self.assertEqual(formatSignedPercent(-0.075), "-7.5%")
        self.assertEqual(formatRiskBadge("high"), "높음")

    def test_visual_bucket_helpers_are_stable(self) -> None:
        self.assertEqual(fearGreedBand(10)["label"], "극단 공포")
        self.assertEqual(fearGreedBand(20)["label"], "극단 공포")
        self.assertEqual(fearGreedBand(21)["label"], "공포")
        self.assertEqual(fearGreedBand(40)["label"], "공포")
        self.assertEqual(fearGreedBand(41)["label"], "중립")
        self.assertEqual(fearGreedBand(50)["label"], "중립")
        self.assertEqual(fearGreedBand(61)["label"], "탐욕")
        self.assertEqual(fearGreedBand(81)["label"], "극단 탐욕")
        self.assertEqual(fearGreedBand(90)["label"], "극단 탐욕")
        self.assertEqual(fearGreedBand(None)["label"], "N/A")
        self.assertEqual(heatmapBucket(80)["label"], "강함")
        self.assertEqual(heatmapBucket(62)["label"], "양호")
        self.assertEqual(heatmapBucket(45)["label"], "보통")
        self.assertEqual(heatmapBucket(25)["label"], "취약")
        self.assertEqual(heatmapBucket(float("nan"))["label"], "N/A")

    def test_candle_summary_text_uses_safe_placeholders(self) -> None:
        text = candleSummaryText(72_000, 0.0123, -0.0456, 1.42)
        self.assertIn("7.2만원", text)
        self.assertIn("+1.2%", text)
        self.assertIn("-4.6%", text)
        self.assertIn("1.42x", text)
        self.assertIn("-", candleSummaryText(None, None, None, None))


if __name__ == "__main__":
    unittest.main()
