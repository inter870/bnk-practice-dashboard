from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from src.institutional import (
    apply_high_risk_override,
    build_forward_alpha_ranking_panel,
    calculate_confidence_score,
    calculate_final_alpha_score,
    forward_alpha_ranking_api_response,
    forward_alpha_ranking_panel_html,
    rating_from_score,
    validate_no_label_leakage,
)
from src.ui.korean_labels import status_label


class ForwardAlphaRankingPanelTests(unittest.TestCase):
    def test_final_alpha_score_calculation(self):
        strong = calculate_final_alpha_score(
            {
                "valuation_score": 85,
                "quality_score": 88,
                "catalyst_score": 75,
                "value_up_score": 70,
                "smart_money_score": 82,
                "short_pressure_score": 78,
                "macro_score": 68,
                "liquidity_score": 90,
                "risk_penalty": 3,
            }
        )
        weak = calculate_final_alpha_score(
            {
                "valuation_score": 25,
                "quality_score": 35,
                "catalyst_score": 10,
                "smart_money_score": 20,
                "short_pressure_score": 30,
                "macro_score": 42,
                "liquidity_score": 25,
                "risk_penalty": 18,
            }
        )
        self.assertGreater(strong, 75)
        self.assertLess(weak, 35)

    def test_confidence_score_calculation(self):
        high_confidence = calculate_confidence_score(
            {
                "expected_feature_count": 8,
                "available_feature_count": 8,
                "meta_confidence": 90,
                "stale_count": 0,
                "fallback_count": 0,
            }
        )
        low_confidence = calculate_confidence_score(
            {
                "expected_feature_count": 8,
                "available_feature_count": 3,
                "meta_confidence": 45,
                "stale_count": 2,
                "fallback_count": 4,
            }
        )
        self.assertGreater(high_confidence, 80)
        self.assertLess(low_confidence, 40)

    def test_severe_risk_override_prevents_buy_rating(self):
        base_rating = rating_from_score(90, 85)
        self.assertEqual(base_rating, "STRONG_BUY_CANDIDATE")
        self.assertEqual(apply_high_risk_override(base_rating, ["severe_dilution_risk"]), "HIGH_RISK_EXCLUDE")
        self.assertEqual(apply_high_risk_override("BUY_CANDIDATE", ["liquidity_risk"]), "HIGH_RISK_EXCLUDE")
        self.assertEqual(apply_high_risk_override("BUY_CANDIDATE", ["minor_warning"]), "BUY_CANDIDATE")

    def test_no_label_leakage_validation(self):
        prediction_as_of = datetime(2026, 7, 8, tzinfo=timezone.utc)
        self.assertTrue(
            validate_no_label_leakage(
                feature_available_at=datetime(2026, 7, 7, tzinfo=timezone.utc),
                prediction_as_of=prediction_as_of,
                label_start_at=prediction_as_of + timedelta(days=1),
            )
        )
        self.assertFalse(
            validate_no_label_leakage(
                feature_available_at=datetime(2026, 7, 9, tzinfo=timezone.utc),
                prediction_as_of=prediction_as_of,
                label_start_at=prediction_as_of + timedelta(days=1),
            )
        )

    def test_deterministic_output_with_mock_features(self):
        now = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
        first = build_forward_alpha_ranking_panel(now=now, allow_mock=True)
        second = build_forward_alpha_ranking_panel(now=now, allow_mock=True)
        first_rows = [(row.code, row.final_alpha_score, row.confidence_score, row.rating, row.feature_snapshot_id) for row in first.ranking_rows]
        second_rows = [(row.code, row.final_alpha_score, row.confidence_score, row.rating, row.feature_snapshot_id) for row in second.ranking_rows]
        self.assertEqual(first_rows, second_rows)
        self.assertTrue(first.ranking_rows)
        self.assertTrue(all(row.positive_drivers or row.negative_drivers or row.risk_flags for row in first.ranking_rows))

    def test_panel_renders_loading_empty_error_and_stale_states(self):
        now = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
        empty_state = build_forward_alpha_ranking_panel(allow_mock=False, now=now)
        self.assertEqual(empty_state.status, "empty")
        self.assertIn("미래 알파 랭킹 없음", forward_alpha_ranking_panel_html(empty_state))
        self.assertIn("Loading", forward_alpha_ranking_panel_html(replace(empty_state, status="loading", summary="Loading.")))
        self.assertIn("Error", forward_alpha_ranking_panel_html(replace(empty_state, status="error", summary="Error.")))

        stale_state = build_forward_alpha_ranking_panel(now=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc), allow_mock=True)
        self.assertEqual(stale_state.status, "stale")
        self.assertIn(status_label("stale"), forward_alpha_ranking_panel_html(stale_state))

    def test_api_response_shape_and_explanations(self):
        now = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
        state = build_forward_alpha_ranking_panel(now=now, allow_mock=True)
        payload = forward_alpha_ranking_api_response(state)

        self.assertEqual(payload["moduleId"], "ForwardAlphaRankingPanel")
        self.assertEqual(payload["apiPath"], "/api/dashboard/forward-alpha-ranking")
        self.assertEqual(payload["scoreVersion"], "baseline_rule_score_v1")
        self.assertIn("featureSnapshotId", payload)
        self.assertIn("rankingRows", payload)
        self.assertIn("strongBuyCandidates", payload)
        self.assertIn("buyCandidates", payload)
        self.assertIn("highRiskExclusions", payload)
        self.assertTrue(payload["rankingRows"])
        row = payload["rankingRows"][0]
        self.assertIn("final_alpha_score", row)
        self.assertIn("confidence_score", row)
        self.assertIn("positive_drivers", row)
        self.assertIn("negative_drivers", row)
        self.assertIn("risk_flags", row)
        self.assertIn("score_version", row)
        self.assertIn("feature_snapshot_id", row)
        self.assertIn("meta", row)


if __name__ == "__main__":
    unittest.main()
