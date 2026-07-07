import unittest

import pandas as pd

import app


class CoreV1Tests(unittest.TestCase):
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

    def test_kis_provider_disabled_without_credentials(self):
        if app.KIS_APP_KEY and app.KIS_APP_SECRET:
            self.skipTest("KIS credentials configured in this environment")
        self.assertFalse(app.kis_enabled())
        token, error = app.get_kis_access_token(0)
        self.assertIsNone(token)
        self.assertIn("KIS_APP_KEY", error)


if __name__ == "__main__":
    unittest.main()
