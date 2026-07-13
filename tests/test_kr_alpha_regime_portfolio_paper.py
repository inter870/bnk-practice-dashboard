from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import unittest
from zoneinfo import ZoneInfo

from src.kr_alpha.api import get_kr_alpha_health
from src.kr_alpha.config import AggressiveSleeveConfig, KRAlphaConfig, validate_config
from src.kr_alpha.domain import AlphaCandidate
from src.kr_alpha.paper import PaperBroker, PaperOrderRequest
from src.kr_alpha.portfolio import build_target_portfolio
from src.kr_alpha.regime import classify_regime


KST = ZoneInfo("Asia/Seoul")


def candidate(**overrides) -> AlphaCandidate:
    values = dict(
        instrument_id="fixture-allowed",
        ticker="900099",
        name_ko="허용 예시",
        market="KOSPI",
        sector="반도체",
        composite_score=80.0,
        expected_gross_return=0.04,
        expected_net_return=0.03,
        confidence=0.9,
        cost_estimate_bps=40.0,
        capacity_krw=1_000_000_000.0,
        suggested_max_weight=0.06,
        rating="WATCH",
        reason_codes=("factor_ready",),
        risk_flags=(),
        decision_time=datetime(2026, 6, 18, 16, 0, tzinfo=KST),
        model_version="test",
        config_hash="hash",
        factor_values=(),
        investment_eligible=True,
    )
    values.update(overrides)
    return AlphaCandidate(**values)


class KRAlphaRegimePortfolioPaperTests(unittest.TestCase):
    def test_regime_is_deterministic_and_missing_inputs_are_blocked(self):
        risk_on = classify_regime(market_trend=1.0, volatility_pressure=0.0, fx_pressure=0.0, liquidity_support=1.0)
        self.assertEqual("RISK_ON", risk_on.label)
        missing = classify_regime(market_trend=1.0, volatility_pressure=None, fx_pressure=None, liquidity_support=None)
        self.assertEqual("INSUFFICIENT_DATA", missing.label)

    def test_fixture_candidates_keep_portfolio_in_cash(self):
        blocked = candidate(investment_eligible=False)
        portfolio = build_target_portfolio((blocked,), KRAlphaConfig())
        self.assertEqual("CASH_ONLY", portfolio.status)
        self.assertEqual(1.0, portfolio.cash_weight)
        self.assertEqual((), portfolio.weights)

    def test_target_portfolio_respects_position_and_cash_limits(self):
        portfolio = build_target_portfolio((candidate(),), KRAlphaConfig())
        self.assertLessEqual(portfolio.weights[0].weight, 0.07)
        self.assertGreaterEqual(portfolio.cash_weight, 0.05)
        self.assertAlmostEqual(1.0, portfolio.cash_weight + sum(row.weight for row in portfolio.weights))

    def test_paper_broker_is_idempotent_and_partial_fill_safe(self):
        broker = PaperBroker(starting_cash=1_000_000, max_adv_participation=0.10)
        decision_time = datetime(2026, 6, 18, 16, 0, tzinfo=KST)
        request = PaperOrderRequest("order-1", "fixture-1", "BUY", 100.0, decision_time, "model-v1", "hash")
        first = broker.submit(
            request,
            next_tradable_time=decision_time + timedelta(hours=17),
            price=10_000.0,
            available_volume=500.0,
            fee_bps=10.0,
        )
        second = broker.submit(
            request,
            next_tradable_time=decision_time + timedelta(hours=17),
            price=99_999.0,
            available_volume=1.0,
            fee_bps=99.0,
        )
        self.assertEqual(first, second)
        self.assertEqual("PARTIAL", first.status)
        self.assertEqual(50.0, first.filled_quantity)
        self.assertEqual(1, len(broker.audit_log))

    def test_paper_fill_cannot_use_decision_bar(self):
        broker = PaperBroker()
        now = datetime(2026, 6, 18, 16, 0, tzinfo=KST)
        request = PaperOrderRequest("order-2", "fixture-1", "BUY", 1.0, now, "model", "hash")
        with self.assertRaises(ValueError):
            broker.submit(request, next_tradable_time=now, price=10_000, available_volume=100, fee_bps=10)

    def test_config_validation_and_health_never_claim_live_transport(self):
        invalid = KRAlphaConfig(aggressive_sleeve=AggressiveSleeveConfig(enabled=True, paper_only=False))
        self.assertIn("aggressive_sleeve_must_be_paper_only", validate_config(invalid))
        health = get_kr_alpha_health(KRAlphaConfig())
        self.assertEqual("ready", health["status"])
        self.assertFalse(health["live_order_transport"])


if __name__ == "__main__":
    unittest.main()
