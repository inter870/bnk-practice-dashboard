from __future__ import annotations

import unittest

from src.korea_equity.formatting import formatSignedPercent, safeDisplay
from src.korea_equity.interaction import (
    MODULE_IDS,
    MODULE_LABELS,
    SelectedContext,
    formatFactorLabel,
    formatMetricLabel,
    formatModuleLabel,
    parse_query_context,
    related_modules_for_metric,
    safe_external_url,
    serialize_query_context,
)


class KoreaInteractionTests(unittest.TestCase):
    def test_label_mappings_are_available(self) -> None:
        self.assertEqual(formatModuleLabel("factorHeatmap"), "팩터 히트맵")
        self.assertEqual(formatMetricLabel("confidence"), "신뢰도")
        self.assertEqual(formatFactorLabel("supplyDemand"), "수급")
        self.assertEqual(formatModuleLabel("unknown"), "-")

    def test_query_state_round_trip(self) -> None:
        context = SelectedContext(
            selectedStockCode="005930",
            selectedModule="factorHeatmap",
            selectedMetric="valueScore",
            selectedFactor="value",
            selectedDateRange="60D",
        )
        query = serialize_query_context(context)
        self.assertEqual(query["stock"], "005930")
        self.assertEqual(query["module"], "factorHeatmap")
        parsed = parse_query_context(query)
        self.assertEqual(parsed.selectedStockCode, "005930")
        self.assertEqual(parsed.selectedModule, "factorHeatmap")
        self.assertEqual(parsed.selectedMetric, "valueScore")
        self.assertEqual(parsed.selectedFactor, "value")

    def test_invalid_query_params_are_ignored_safely(self) -> None:
        parsed = parse_query_context({"stock": "abc", "module": "bad", "metric": "bad", "factor": "bad"})
        self.assertIsNone(parsed.selectedStockCode)
        self.assertIsNone(parsed.selectedModule)
        self.assertIsNone(parsed.selectedMetric)
        self.assertIsNone(parsed.selectedFactor)

    def test_preserved_module_ids_exist(self) -> None:
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
        self.assertTrue(required.issubset(MODULE_LABELS))
        self.assertTrue(required.issubset(MODULE_IDS))

    def test_related_module_mapping(self) -> None:
        self.assertIn("factorHeatmap", related_modules_for_metric("totalScore"))
        self.assertIn("backtestAccuracy", related_modules_for_metric("totalScore"))
        self.assertIn("candleVolumeChart", related_modules_for_metric("downsideRisk"))
        self.assertIn("portfolioReviewQueue", related_modules_for_metric("downsideRisk"))
        self.assertIn("valueUpRadar", related_modules_for_metric("valueUpScore"))
        self.assertIn("supplyDemandRadar", related_modules_for_metric("supplyDemandScore"))

    def test_safe_formatting_and_external_links(self) -> None:
        self.assertEqual(safeDisplay(None), "-")
        self.assertEqual(safeDisplay(float("nan")), "-")
        self.assertEqual(safeDisplay(float("inf")), "-")
        self.assertEqual(formatSignedPercent(0.017), "+1.7%")
        self.assertEqual(formatSignedPercent(-0.075), "-7.5%")
        self.assertIsNone(safe_external_url(""))
        self.assertIsNone(safe_external_url("javascript:alert(1)"))
        self.assertEqual(safe_external_url("https://dart.fss.or.kr"), "https://dart.fss.or.kr")


if __name__ == "__main__":
    unittest.main()

