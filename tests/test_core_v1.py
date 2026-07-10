import unittest
from unittest.mock import Mock, patch

import pandas as pd

import app


class CoreV1Tests(unittest.TestCase):
    def test_all_nine_legacy_views_are_preserved_in_order(self):
        self.assertEqual(
            app.MAIN_VIEW_LABELS,
            (
                "대시보드",
                "포트폴리오",
                "종목",
                "알파 후보 탐색",
                "공시",
                "매크로",
                "브리핑",
                "신호 성과",
                "설정",
            ),
        )

    def test_integer_slider_value_is_aligned_to_step(self):
        self.assertEqual(app.align_int_step(220, 50, 1000, 50), 200)
        self.assertEqual(app.align_int_step(1050, 50, 1000, 50), 1000)
        self.assertEqual(app.align_int_step(None, 50, 1000, 50), 50)

    def test_data_quality_penalizes_missing_source(self):
        score, warnings, errors = app.assess_data_quality(
            source="unknown",
            unit="KRW",
            frequency="daily",
            updated_at=pd.Timestamp.now(),
            last_close=1000,
            prev_close=990,
            change=10,
            change_pct=1.01,
            is_fallback=False,
        )
        self.assertLess(score, 70)
        self.assertIn("source 누락", errors)

    def test_market_regime_risk_off_scenario(self):
        snapshot = {
            "KOSPI": app.make_snapshot("KOSPI", "코스피", 100, 105, -5, -4.76, source="Naver", unit="index", frequency="near_realtime"),
            "KOSDAQ": app.make_snapshot("KOSDAQ", "코스닥", 100, 106, -6, -5.66, source="Naver", unit="index", frequency="near_realtime"),
            "USD/KRW": app.make_snapshot("USD/KRW", "USD/KRW", 1400, 1380, 20, 1.45, source="Naver", unit="KRW", frequency="near_realtime"),
            "US 10Y": app.make_snapshot("US 10Y", "US 10Y", 4.6, 4.5, 0.1, 2.22, source="FDR", unit="%", frequency="daily"),
            "KR 3Y": app.make_snapshot("KR 3Y", "KR 3Y", 3.7, 3.65, 0.05, 1.37, source="FDR", unit="%", frequency="daily"),
            "FNG": app.make_snapshot("FNG", "Fear", 20, None, None, None, source="Alternative.me", unit="score", frequency="daily"),
        }
        regime = app.build_market_regime_output(snapshot)
        self.assertIn(regime.regime, {"Extreme Risk-Off", "Risk-Off"})
        self.assertLess(regime.max_new_exposure, 0.40)

    def test_ecos_latest_observation_uses_parsed_max_not_first_row(self):
        frame = pd.DataFrame(
            [
                {"TIME": "202401"},
                {"TIME": "invalid"},
                {"TIME": "2026Q2"},
                {"TIME": "20251231"},
            ]
        )

        latest = app.latest_ecos_observation_timestamp(frame)

        self.assertIsNotNone(latest)
        self.assertEqual(latest.date().isoformat(), "2026-06-30")

    def test_risk_reward_handles_valid_history(self):
        idx = pd.date_range("2024-01-01", periods=80)
        close = pd.Series(range(100, 180), index=idx)
        hist = pd.DataFrame(
            {
                "Open": close - 1,
                "High": close + 2,
                "Low": close - 3,
                "Close": close,
                "Volume": 1000,
            }
        )
        plan = app.risk_plan_for_stock("000001", "테스트", hist)
        self.assertIsNotNone(plan["rr"])
        self.assertGreater(plan["latest"], plan["stop"])

    def test_action_decision_blocks_negative_edge(self):
        regime = app.MarketRegimeOutput(20, "Extreme Risk-Off", (55, 80), 0.2, [], [], [], 70, {})
        plan = {"risk_pct": 8.0, "upside_pct": 2.0, "rr": 0.25}
        decision = app.build_action_decision(40, plan, regime, 90, {"severity": "Low", "penalty": 0})
        self.assertTrue(decision.blockers)
        self.assertEqual(decision.max_position_pct, 0.0 if "공시" in " ".join(decision.blockers) else decision.max_position_pct)
        self.assertLessEqual(decision.score, 64)

    def test_expected_edge_requires_out_of_sample_calibration(self):
        regime = app.MarketRegimeOutput(60, "Neutral", (20, 40), 0.4, [], [], [], 75, {})
        plan = {"risk_pct": 5.0, "upside_pct": 12.0, "rr": 2.4}

        edge, adjusted_rr, confidence = app.expected_edge_from_plan(
            plan,
            80,
            regime,
            {"severity": "Low", "penalty": 0},
        )
        decision = app.build_action_decision(
            80,
            plan,
            regime,
            90,
            {"severity": "Low", "penalty": 0},
        )

        self.assertIsNone(edge)
        self.assertIsNone(adjusted_rr)
        self.assertEqual(confidence, 0.0)
        self.assertIn("검증된 승률 데이터 부족", decision.blockers)
        self.assertEqual(decision.max_position_pct, 0.0)

    def test_expected_edge_accepts_explicit_calibrated_probability(self):
        regime = app.MarketRegimeOutput(60, "Neutral", (20, 40), 0.4, [], [], [], 75, {})
        plan = {"risk_pct": 5.0, "upside_pct": 12.0, "rr": 2.4}

        edge, adjusted_rr, confidence = app.expected_edge_from_plan(
            plan,
            80,
            regime,
            {"severity": "Low", "penalty": 0},
            calibrated_win_probability=0.60,
            calibration_confidence=72.0,
            calibration_sample_size=80,
        )

        self.assertIsNotNone(edge)
        self.assertIsNotNone(adjusted_rr)
        self.assertEqual(confidence, 72.0)

    def test_briefing_validator_catches_duplicate_text(self):
        schema = "## A\n## B\n## C\n## D\n## E"
        text = "\n".join(
            [
                "## A",
                "중복 문장입니다 중복 문장입니다 중복 문장입니다",
                "## B",
                "중복 문장입니다 중복 문장입니다 중복 문장입니다",
                "## C",
                "내용",
                "## D",
                "내용",
                "## E",
                "내용",
            ]
        )
        ok, errors, _ = app.validate_briefing_output(text, schema)
        self.assertFalse(ok)
        self.assertTrue(any("중복" in err for err in errors))

    def test_saved_discovery_result_is_reusable_after_request_flag_resets(self):
        saved = (220, [{"code": "005930", "name": "삼성전자"}], ["warning"], 2500, 220)

        normalized = app.saved_discovery_scan_result(saved)

        self.assertIsNotNone(normalized)
        self.assertEqual(normalized[1][0]["code"], "005930")

    def test_kis_provider_disabled_without_credentials(self):
        app._get_kis_access_token_cached.clear()
        try:
            with patch.object(app, "KIS_APP_KEY", ""), patch.object(app, "KIS_APP_SECRET", ""):
                self.assertFalse(app.kis_enabled())
                token, error = app.get_kis_access_token(0)
                self.assertIsNone(token)
                self.assertIn("KIS_APP_KEY", error)
        finally:
            app._get_kis_access_token_cached.clear()

    def test_kis_transient_token_failure_is_not_cached(self):
        success = Mock()
        success.content = b"{}"
        success.status_code = 200
        success.reason = "OK"
        success.json.return_value = {"access_token": "test-access-token"}
        app._get_kis_access_token_cached.clear()
        try:
            with (
                patch.object(app, "KIS_APP_KEY", "test-app-key"),
                patch.object(app, "KIS_APP_SECRET", "test-app-secret"),
                patch.object(app, "KIS_BASE_URL", "https://example.invalid"),
                patch.object(app.requests, "post", side_effect=[app.requests.ConnectionError("temporary"), success]) as post,
            ):
                first_token, first_error = app.get_kis_access_token(0)
                second_token, second_error = app.get_kis_access_token(1)
        finally:
            app._get_kis_access_token_cached.clear()

        self.assertIsNone(first_token)
        self.assertIn("요청 실패", first_error)
        self.assertEqual(second_token, "test-access-token")
        self.assertIsNone(second_error)
        self.assertEqual(post.call_count, 2)

    def test_core_market_card_labels_historical_fdr_as_recent_close(self):
        snap = app.Snapshot(
            "KOSPI",
            "KOSPI",
            2746.79,
            2735.0,
            11.79,
            0.43,
            pd.Timestamp("2026-07-08"),
            source="FinanceDataReader",
            unit="index",
            frequency="historical",
            quality_score=88,
            is_fallback=True,
        )
        self.assertEqual("최근 종가", app.snapshot_metric_subtitle(snap, "현재가"))
        label = app.snapshot_source_label(snap)
        self.assertIn("FDR 최근 종가", label)
        self.assertIn("실시간 아님", label)
        self.assertIn("2026.07.08", label)

    def test_core_market_card_keeps_current_label_for_naver_intraday_snapshot(self):
        snap = app.Snapshot(
            "KOSPI",
            "KOSPI",
            2750.12,
            2735.0,
            15.12,
            0.55,
            pd.Timestamp("2026-07-09 10:15"),
            source="Naver Finance",
            unit="index",
            frequency="near_realtime",
            quality_score=88,
            is_fallback=True,
        )
        self.assertEqual("현재가", app.snapshot_metric_subtitle(snap, "현재가"))
        label = app.snapshot_source_label(snap)
        self.assertIn("네이버 금융 장중 스냅샷", label)
        self.assertNotIn("실시간 아님", label)
        self.assertIn("07.09 10:15", label)

    def test_core_market_snapshot_prefers_plausible_current_source(self):
        fallback = app.Snapshot(
            "KOSPI",
            "KOSPI",
            2700.0,
            2690.0,
            10.0,
            0.37,
            pd.Timestamp("2026-07-08"),
            source="FinanceDataReader",
            unit="index",
            frequency="historical",
            quality_score=88,
            is_fallback=True,
        )
        live = app.Snapshot(
            "KOSPI",
            "KOSPI",
            2720.0,
            2690.0,
            30.0,
            1.12,
            pd.Timestamp("2026-07-09 10:20"),
            source="Naver Finance",
            unit="index",
            frequency="near_realtime",
            quality_score=88,
            is_fallback=True,
        )
        self.assertIs(app.prefer_current_market_snapshot("KOSPI", fallback, live), live)

        bad_live = app.Snapshot(
            "KOSPI",
            "KOSPI",
            999999.0,
            2690.0,
            30.0,
            1.12,
            pd.Timestamp("2026-07-09 10:20"),
            source="Naver Finance",
            unit="index",
            frequency="near_realtime",
            quality_score=88,
            is_fallback=True,
        )
        self.assertIs(app.prefer_current_market_snapshot("KOSPI", fallback, bad_live), fallback)
        self.assertTrue(any("최근 종가" in warning for warning in (fallback.warnings or [])))


if __name__ == "__main__":
    unittest.main()
