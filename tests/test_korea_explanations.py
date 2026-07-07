from __future__ import annotations

import unittest

from src.korea_equity.explanations import METRIC_EXPLANATIONS, get_metric_explanation


class KoreaExplanationTests(unittest.TestCase):
    def test_required_metric_explanations_exist(self) -> None:
        for key in ["totalScore", "recommendationGrade", "confidence", "expectedReturn3M", "downsideRisk", "fearGreed"]:
            with self.subTest(key=key):
                explanation = get_metric_explanation(key)
                self.assertIsNotNone(explanation)
                self.assertTrue(explanation.definition)
                self.assertTrue(explanation.interpretation)

    def test_total_score_links_to_factor_and_backtest(self) -> None:
        related = METRIC_EXPLANATIONS["totalScore"].relatedModules
        self.assertIn("factorHeatmap", related)
        self.assertIn("backtestAccuracy", related)

    def test_downside_risk_links_to_chart_and_portfolio_queue(self) -> None:
        related = METRIC_EXPLANATIONS["downsideRisk"].relatedModules
        self.assertIn("candleVolumeChart", related)
        self.assertIn("portfolioReviewQueue", related)

    def test_value_up_and_supply_demand_links(self) -> None:
        self.assertIn("valueUpRadar", METRIC_EXPLANATIONS["valueUpScore"].relatedModules)
        self.assertIn("supplyDemandRadar", METRIC_EXPLANATIONS["supplyDemandScore"].relatedModules)

    def test_backtest_metrics_include_formula_and_assumptions_text(self) -> None:
        for key in ["cagr", "excessReturn", "mdd", "sharpe", "precisionAt10", "rankIC"]:
            with self.subTest(key=key):
                explanation = METRIC_EXPLANATIONS[key]
                self.assertTrue(explanation.formula)
                self.assertIn("backtestAccuracy", explanation.relatedModules)


if __name__ == "__main__":
    unittest.main()

