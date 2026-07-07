from pathlib import Path
import unittest

from src.korea_equity import (
    KOREA_MODULE_VISUAL_REGISTRY,
    formatConfidence,
    formatDirection,
    formatRegime,
    formatSeverity,
    formatSignedPercent,
    normalizeNegativeZero,
    safeDisplay,
)


APP_TEXT = Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")


class KoreaOSReadabilityTests(unittest.TestCase):
    def test_formatters_localize_status_and_confidence(self) -> None:
        self.assertEqual(formatConfidence(0.59), "59%")
        self.assertEqual(formatSignedPercent(-0.017), "-1.7%")
        self.assertEqual(formatDirection("positive"), "긍정")
        self.assertEqual(formatDirection("neutral"), "중립")
        self.assertEqual(formatDirection("negative"), "부정")
        self.assertEqual(formatSeverity("low"), "낮음")
        self.assertEqual(formatRegime("panic"), "패닉")
        self.assertEqual(normalizeNegativeZero(-0.0), 0.0)
        self.assertEqual(safeDisplay(float("nan")), "-")
        self.assertEqual(safeDisplay(float("inf")), "-")

    def test_os_v2_visual_primitives_are_rendered(self) -> None:
        for token in [
            "korea-os-shell",
            "korea-os-hero",
            "korea-os-grid",
            "korea-os-card",
            "korea-os-step-row",
            "korea-os-metric",
            "korea-os-thesis",
            "korea-os-scenario-row",
            "korea-os-alert-row",
        ]:
            self.assertIn(token, APP_TEXT)

    def test_os_v2_header_and_module_cards_are_directly_wired(self) -> None:
        section_start = APP_TEXT.index("def render_korea_investment_os_section")
        section_end = APP_TEXT.index("def render_korea_alpha_section", section_start)
        section_text = APP_TEXT[section_start:section_end]
        self.assertIn("Korea Investment OS v2", section_text)
        self.assertIn("주문 기능 없음", section_text)
        self.assertIn("korea_decision_flow_html(os_data)", section_text)
        self.assertIn("korea_signal_conflict_matrix_html(os_data)", section_text)
        self.assertIn("korea_position_sizing_budget_html(os_data)", section_text)
        self.assertIn("korea_thesis_tracker_html(os_data)", section_text)
        self.assertIn("korea_scenario_stress_tests_html(os_data)", section_text)
        self.assertNotIn("st.columns([1, 1])", section_text)

    def test_required_os_module_labels_exist(self) -> None:
        required = {
            "decisionFlow",
            "signalConflictMatrix",
            "positionSizingRiskBudget",
            "investmentThesisTracker",
            "predictionCalibration",
            "similarCaseLibrary",
            "scenarioStressTest",
            "catalystEventCalendar",
            "riskAlertRules",
            "postReviewNotebook",
        }
        registry_keys = {item["key"] for item in KOREA_MODULE_VISUAL_REGISTRY}
        self.assertTrue(required.issubset(registry_keys))

    def test_factor_and_disclosure_blank_gap_controls_exist(self) -> None:
        self.assertIn('st.expander("팩터 설명 연결", expanded=False)', APP_TEXT)
        self.assertIn('st.expander("공시 이벤트 연결", expanded=False)', APP_TEXT)
        self.assertIn('st.expander("백테스트 지표 설명", expanded=False)', APP_TEXT)
        self.assertIn("korea-safety-callout", APP_TEXT)


if __name__ == "__main__":
    unittest.main()
