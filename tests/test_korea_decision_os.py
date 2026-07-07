from __future__ import annotations

from types import SimpleNamespace
import unittest

from src.korea_equity.decision_os import (
    buildDecisionFlow,
    buildKoreaInvestmentOS,
    buildSignalConflictMatrix,
    calculatePositionSizingRiskBudget,
    calculatePredictionCalibration,
    runScenarioStressTests,
)


def _score(**overrides):
    base = {
        "code": "005930",
        "name": "삼성전자",
        "total_score": 72,
        "confidence": 0.68,
        "expected_return_3m": 0.08,
        "downside_risk": -0.09,
        "target_review_range_low": 70000,
        "stop_review_price": 66000,
        "max_suggested_weight": 0.08,
        "positive_reasons": ["상대강도 양호", "거래대금 증가"],
        "negative_reasons": ["환율 부담"],
        "risk_flags": [],
        "factor_scores": SimpleNamespace(momentum=82, value=38, quality=68, supply_demand=73),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class KoreaDecisionOSTests(unittest.TestCase):
    def test_decision_flow_handles_missing_data(self) -> None:
        stages = buildDecisionFlow([], SimpleNamespace(regime="neutral", regime_score=55, reason=[]))
        self.assertEqual(stages[0].status, "데이터 부족")
        self.assertIn("investmentAlgorithm", stages[0].related_modules)

    def test_signal_conflict_splits_positive_and_negative(self) -> None:
        conflicts = buildSignalConflictMatrix(_score())
        directions = {row.direction for row in conflicts}
        self.assertIn("positive", directions)
        self.assertIn("negative", directions)

    def test_position_sizing_handles_invalid_stop_and_risk_off_haircut(self) -> None:
        invalid = calculatePositionSizingRiskBudget(_score(target_review_range_low=65000, stop_review_price=66000))
        self.assertEqual(invalid.status, "검증 필요")

        risk_off = calculatePositionSizingRiskBudget(
            _score(),
            SimpleNamespace(regime="risk_off"),
            total_equity=100_000_000,
            risk_per_trade_pct=0.0025,
        )
        self.assertLessEqual(risk_off.max_position_weight or 0, 0.08)
        self.assertTrue(any("haircut" in warning for warning in risk_off.warnings))

    def test_scenarios_are_non_deterministic_stress_outputs(self) -> None:
        missing = runScenarioStressTests(None)
        self.assertEqual(missing[0].status, "데이터 부족")

        scenarios = runScenarioStressTests(_score())
        self.assertGreaterEqual(len(scenarios), 4)
        self.assertIn("usdkrwShock", {row.id for row in scenarios})
        self.assertTrue(all("검토" in row.candidate_action or "방어" in row.candidate_action or "축소" in row.candidate_action for row in scenarios))

    def test_calibration_falls_back_safely(self) -> None:
        missing = calculatePredictionCalibration(None)
        self.assertEqual(missing.status, "데이터 부족")
        self.assertIn("검증", missing.confidence_adjustment)

        weak = calculatePredictionCalibration(SimpleNamespace(precision_at_top10=0.4, factor_rank_ic=-0.1, hit_ratio=0.45, win_rate=0.48))
        self.assertEqual(weak.status, "검증 주의")
        self.assertTrue(weak.warnings)

    def test_build_korea_investment_os_returns_all_sections(self) -> None:
        os_data = buildKoreaInvestmentOS(
            [_score()],
            SimpleNamespace(regime="neutral", regime_score=61, reason=["시장 중립"]),
            SimpleNamespace(precision_at_top10=0.62, factor_rank_ic=0.08, hit_ratio=0.55, win_rate=0.53),
            disclosures=[],
        )
        for key in [
            "decisionFlow",
            "signalConflicts",
            "positionSizing",
            "scenarios",
            "theses",
            "catalysts",
            "calibration",
            "riskAlerts",
            "similarCases",
            "postReview",
        ]:
            self.assertIn(key, os_data)
        self.assertEqual(os_data["meta"]["mode"], "decision_support")


if __name__ == "__main__":
    unittest.main()
