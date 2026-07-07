from __future__ import annotations

import unittest

from src.korea_equity import KOREA_DASHBOARD_TOKENS, KOREA_MODULE_VISUAL_REGISTRY
from src.korea_equity.interaction import formatFactorLabel, formatMetricLabel, formatModuleLabel


class KoreaVisualTokenTests(unittest.TestCase):
    def test_required_module_registry_is_complete(self) -> None:
        required = {
            "investmentAlgorithm",
            "factorHeatmap",
            "supplyDemandRadar",
            "disclosureRadar",
            "valueUpRadar",
            "backtestAccuracy",
            "portfolioReviewQueue",
            "advancedModuleSummary",
            "fearGreedIndex",
            "candleVolumeChart",
        }
        registry_keys = {item["key"] for item in KOREA_MODULE_VISUAL_REGISTRY}
        self.assertTrue(required.issubset(registry_keys))

    def test_module_metric_and_factor_labels_are_stable_korean(self) -> None:
        self.assertEqual(formatModuleLabel("investmentAlgorithm"), "투자검토 알고리즘")
        self.assertEqual(formatModuleLabel("candleVolumeChart"), "최근 60거래일 캔들 + 거래량")
        self.assertEqual(formatMetricLabel("recommendationGrade"), "등급")
        self.assertEqual(formatMetricLabel("expectedReturn3M"), "3개월 기대수익")
        self.assertEqual(formatFactorLabel("supplyDemand"), "수급")
        self.assertEqual(formatFactorLabel("valueUp"), "밸류업")

    def test_design_tokens_include_accessible_core_colors(self) -> None:
        for key in ["surface_card", "border_selected", "text_primary", "positive", "risk", "caution", "purple"]:
            self.assertIn(key, KOREA_DASHBOARD_TOKENS)
            self.assertTrue(KOREA_DASHBOARD_TOKENS[key])


if __name__ == "__main__":
    unittest.main()
