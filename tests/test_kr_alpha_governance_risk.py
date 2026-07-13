from __future__ import annotations

from datetime import datetime
import unittest
from zoneinfo import ZoneInfo

from src.kr_alpha.config import KRAlphaConfig
from src.kr_alpha.governance import PromotionEvidence, build_dynamic_weights, evaluate_promotion
from src.kr_alpha.risk import LiveInterlockInput, evaluate_kill_switch, evaluate_live_interlocks, pre_trade_check
from src.kr_alpha.service import build_overview


class KRAlphaGovernanceRiskTests(unittest.TestCase):
    def test_insufficient_oos_keeps_prior_and_blocks_promotion(self):
        state = build_dynamic_weights({"value": [0.02] * 6})
        self.assertEqual(6, state.evidence_months)
        self.assertTrue(all(status == "INSUFFICIENT_EVIDENCE" for status in state.statuses.values()))
        decision = evaluate_promotion(PromotionEvidence(6, 20, 0.5, -0.1, 0.2, 0.1, 2, 0.95, 1_000_000_000))
        self.assertFalse(decision.approved)
        self.assertIn("insufficient_oos_period", decision.reasons)

    def test_dynamic_weight_change_is_capped_and_negative_factor_degraded(self):
        history = {
            "value": [0.05] * 12,
            "medium_momentum": [-0.03] * 12,
        }
        previous = build_dynamic_weights({}).weights
        state = build_dynamic_weights(history, previous_weights=previous, monthly_change_cap=0.03)
        self.assertLessEqual(abs(state.weights["value"] - previous["value"]), 0.04)
        self.assertEqual("DEGRADED", state.statuses["medium_momentum"])
        self.assertAlmostEqual(1.0, sum(state.weights.values()))

    def test_kill_switch_hard_loss_blocks_new_entries(self):
        state = evaluate_kill_switch(KRAlphaConfig(), daily_return=-0.03, weekly_return=0.0, drawdown=-0.05)
        self.assertEqual("TRIGGERED", state.status)
        self.assertFalse(state.new_entries_allowed)
        self.assertEqual(0.0, state.exposure_multiplier)

    def test_live_interlocks_never_submit_orders(self):
        all_green = LiveInterlockInput(True, True, True, True, True, True, True, True, True, True, True)
        decision = evaluate_live_interlocks(all_green)
        self.assertFalse(decision.allowed)
        self.assertFalse(decision.order_submission_implemented)
        self.assertIn("live_order_transport_not_implemented", decision.blocking_reasons)

    def test_fixture_candidate_fails_pretrade_gate(self):
        decision_time = datetime(2026, 6, 18, 16, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        candidate = build_overview(decision_time, KRAlphaConfig()).candidates[0]
        result = pre_trade_check(candidate, KRAlphaConfig(), proposed_weight=0.01)
        self.assertFalse(result.allowed)
        self.assertIn("candidate_not_investment_eligible", result.reasons)


if __name__ == "__main__":
    unittest.main()
