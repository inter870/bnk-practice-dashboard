from __future__ import annotations

from datetime import datetime
import unittest
from zoneinfo import ZoneInfo

from src.kr_alpha.config import KRAlphaConfig, config_from_mapping
from src.kr_alpha.factors import FACTOR_SPECS, calculate_factor_panel, prior_weights, robust_zscores, winsorize
from src.kr_alpha.fixtures import FACTOR_NAMES, FixtureKRAlphaProvider
from src.kr_alpha.service import build_overview


KST = ZoneInfo("Asia/Seoul")
DECISION = datetime(2026, 6, 18, 16, 0, tzinfo=KST)


class KRAlphaDomainFactorTests(unittest.TestCase):
    def test_fixture_mode_is_safe_default_and_hash_is_deterministic(self):
        config = config_from_mapping({})
        self.assertFalse(config.enabled)
        self.assertEqual("fixture", config.data_mode)
        self.assertEqual(config.config_hash, KRAlphaConfig().config_hash)

    def test_fixture_contains_required_market_edge_cases(self):
        stocks = FixtureKRAlphaProvider().snapshot(DECISION)
        events = {event for stock in stocks for event in stock.event_flags}
        required = {
            "earnings_after_close", "earnings_surprise", "near_52w_high", "vi", "limit_up",
            "suspension", "dividend", "share_split", "delisting", "partial_fill", "illiquid",
            "short_crowding", "foreign_institution_joint_buy",
        }
        self.assertTrue(required.issubset(events))

    def test_after_close_and_future_observations_are_excluded(self):
        stocks = FixtureKRAlphaProvider().snapshot(DECISION)
        panel = calculate_factor_panel(stocks, DECISION)
        first = {value.factor_name: value for value in panel["fixture-1"]}
        self.assertIsNone(first["earnings_surprise_pead"].raw_value)
        self.assertTrue(all(value.available_at <= DECISION for values in panel.values() for value in values))
        self.assertFalse(any(value.factor_name == "future_revision" for values in panel.values() for value in values))

    def test_fourteen_factor_contract_and_prior_weights(self):
        self.assertEqual(14, len(FACTOR_SPECS))
        self.assertEqual(tuple(spec.name for spec in FACTOR_SPECS), FACTOR_NAMES)
        self.assertAlmostEqual(1.0, sum(prior_weights().values()))

    def test_robust_preprocessing_is_finite_and_bounded(self):
        clipped = winsorize([-100.0, 0.0, 1.0, 2.0, 100.0])
        self.assertGreater(clipped[0], -100.0)
        self.assertLess(clipped[-1], 100.0)
        zscores = robust_zscores([1.0, 1.0, 1.0])
        self.assertEqual([0.0, 0.0, 0.0], zscores)

    def test_fixture_candidates_never_become_investment_actions(self):
        overview = build_overview(DECISION, KRAlphaConfig())
        self.assertEqual(6, len(overview.candidates))
        self.assertTrue(all(not candidate.investment_eligible for candidate in overview.candidates))
        self.assertTrue(all(candidate.rating in {"WATCH", "HIGH_RISK_EXCLUDE"} for candidate in overview.candidates))
        self.assertTrue(all(candidate.expected_net_return is None for candidate in overview.candidates))

    def test_unconnected_paper_mode_does_not_fallback_to_fixture(self):
        overview = build_overview(DECISION, KRAlphaConfig(data_mode="paper"))
        self.assertEqual((), overview.candidates)
        self.assertEqual("DISABLED", overview.model_status)
        self.assertIn("어댑터 미연결", overview.data_badge)


if __name__ == "__main__":
    unittest.main()
