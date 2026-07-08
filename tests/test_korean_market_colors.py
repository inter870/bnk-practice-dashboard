from __future__ import annotations

import unittest

from src.ui.korean_labels import action_label, rating_label
from src.ui.korean_market_colors import (
    MARKET_DOWN,
    MARKET_FLAT,
    MARKET_UP,
    RISK_CRITICAL,
    RISK_WARNING,
    SYSTEM_ERROR,
    getActionColorClass,
    getChartSeriesColor,
    getFlowColorClass,
    getKoreanMarketBadgeClass,
    getKoreanMarketColorClass,
    getKoreanMarketColorToken,
    getKoreanMarketDirection,
    getRatingColorClass,
    getReturnColorClass,
    getRiskSeverityColorClass,
)


class KoreanMarketColorTests(unittest.TestCase):
    def test_positive_return_uses_korean_market_red(self) -> None:
        self.assertEqual("up", getKoreanMarketDirection(0.0321))
        self.assertEqual(MARKET_UP, getKoreanMarketColorToken(0.0321))
        self.assertEqual("market-up", getReturnColorClass(0.0321))

    def test_negative_return_uses_korean_market_blue(self) -> None:
        self.assertEqual("down", getKoreanMarketDirection(-0.011))
        self.assertEqual(MARKET_DOWN, getKoreanMarketColorToken(-0.011))
        self.assertEqual("market-down", getKoreanMarketColorClass(-0.011))

    def test_zero_return_is_neutral(self) -> None:
        self.assertEqual("flat", getKoreanMarketDirection(0))
        self.assertEqual(MARKET_FLAT, getKoreanMarketColorToken(0))
        self.assertEqual("market-badge-flat", getKoreanMarketBadgeClass(0))

    def test_flow_net_buy_and_sell_follow_market_convention(self) -> None:
        self.assertEqual("market-up", getFlowColorClass(123_000_000))
        self.assertEqual("market-down", getFlowColorClass(-87_000_000))

    def test_risk_stale_and_error_do_not_use_market_down_blue(self) -> None:
        self.assertEqual("risk-critical", getRiskSeverityColorClass("critical"))
        self.assertEqual("risk-warning", getRiskSeverityColorClass("stale"))
        self.assertEqual(RISK_CRITICAL, getChartSeriesColor("critical", context="risk"))
        self.assertEqual(RISK_WARNING, getChartSeriesColor("warning", context="risk"))
        self.assertEqual(SYSTEM_ERROR, getChartSeriesColor("error", context="risk"))
        self.assertNotEqual("market-down", getRiskSeverityColorClass("critical"))

    def test_rating_and_action_classes_are_separated_from_internal_keys(self) -> None:
        self.assertEqual("강력 매수 후보", rating_label("STRONG_BUY_CANDIDATE"))
        self.assertEqual("고위험 제외", rating_label("HIGH_RISK_EXCLUDE"))
        self.assertEqual("비중 확대", action_label("ADD"))
        self.assertEqual("투자 제외", action_label("EXCLUDE"))
        self.assertEqual("market-up", getRatingColorClass("STRONG_BUY_CANDIDATE"))
        self.assertEqual("risk-critical", getRatingColorClass("HIGH_RISK_EXCLUDE"))
        self.assertEqual("market-up", getActionColorClass("ADD"))
        self.assertEqual("market-down", getActionColorClass("TRIM"))
        self.assertEqual("risk-critical", getActionColorClass("EXCLUDE"))


if __name__ == "__main__":
    unittest.main()
