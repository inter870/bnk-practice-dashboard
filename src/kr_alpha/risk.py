from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .config import KRAlphaConfig
from .domain import AlphaCandidate


@dataclass(frozen=True)
class KillSwitchState:
    status: str
    new_entries_allowed: bool
    exposure_multiplier: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class LiveInterlockInput:
    enable_live_trading: bool
    approval_token_present: bool
    account_allowlisted: bool
    broker_healthy: bool
    positions_reconciled: bool
    model_approved: bool
    config_approved: bool
    data_fresh: bool
    kill_switch_clear: bool
    idempotency_key_present: bool
    pre_trade_risk_passed: bool


@dataclass(frozen=True)
class LiveInterlockDecision:
    allowed: bool
    status: str
    blocking_reasons: tuple[str, ...]
    order_submission_implemented: bool = False


@dataclass(frozen=True)
class PreTradeDecision:
    allowed: bool
    max_weight: float
    reasons: tuple[str, ...]


def evaluate_kill_switch(
    config: KRAlphaConfig,
    *,
    daily_return: float,
    weekly_return: float,
    drawdown: float,
) -> KillSwitchState:
    reasons: list[str] = []
    multiplier = 1.0
    if daily_return <= config.risk.daily_loss_hard:
        reasons.append("daily_loss_hard")
    if weekly_return <= config.risk.weekly_loss_hard:
        reasons.append("weekly_loss_hard")
    if drawdown <= config.risk.drawdown_stop_new_entries:
        reasons.append("drawdown_stop_new_entries")
    elif drawdown <= config.risk.drawdown_deleverage:
        reasons.append("drawdown_deleverage")
        multiplier = min(multiplier, 0.5)
    elif drawdown <= config.risk.drawdown_warning:
        reasons.append("drawdown_warning")
        multiplier = min(multiplier, 0.75)
    hard = any(reason in {"daily_loss_hard", "weekly_loss_hard", "drawdown_stop_new_entries"} for reason in reasons)
    return KillSwitchState("TRIGGERED" if hard else ("WARNING" if reasons else "CLEAR"), not hard, 0.0 if hard else multiplier, tuple(reasons))


def pre_trade_check(candidate: AlphaCandidate, config: KRAlphaConfig, *, proposed_weight: float) -> PreTradeDecision:
    reasons: list[str] = []
    maximum = min(candidate.suggested_max_weight, config.risk.max_position_weight)
    if candidate.market == "KOSDAQ":
        maximum = min(maximum, config.risk.max_kosdaq_position_weight)
    if not candidate.investment_eligible:
        reasons.append("candidate_not_investment_eligible")
    if candidate.risk_flags:
        reasons.extend(f"risk:{flag}" for flag in candidate.risk_flags)
    if proposed_weight > maximum:
        reasons.append("position_limit_exceeded")
    return PreTradeDecision(not reasons, maximum, tuple(dict.fromkeys(reasons)))


def evaluate_live_interlocks(values: LiveInterlockInput) -> LiveInterlockDecision:
    checks = {
        "live_flag_disabled": values.enable_live_trading,
        "approval_token_missing": values.approval_token_present,
        "account_not_allowlisted": values.account_allowlisted,
        "broker_unhealthy": values.broker_healthy,
        "positions_not_reconciled": values.positions_reconciled,
        "model_not_approved": values.model_approved,
        "config_not_approved": values.config_approved,
        "data_not_fresh": values.data_fresh,
        "kill_switch_triggered": values.kill_switch_clear,
        "idempotency_key_missing": values.idempotency_key_present,
        "pre_trade_risk_failed": values.pre_trade_risk_passed,
    }
    blockers = tuple(reason for reason, passed in checks.items() if not passed)
    # This repository deliberately has no live order transport. Even all-green inputs remain approval-only.
    if not blockers:
        blockers = ("live_order_transport_not_implemented",)
    return LiveInterlockDecision(False, "BLOCKED", blockers, order_submission_implemented=False)


def aggressive_sleeve_candidates(candidates: Sequence[AlphaCandidate], config: KRAlphaConfig) -> tuple[AlphaCandidate, ...]:
    sleeve = config.aggressive_sleeve
    if not sleeve.enabled or not sleeve.paper_only:
        return ()
    eligible = [
        candidate for candidate in candidates
        if candidate.investment_eligible
        and not candidate.risk_flags
        and candidate.expected_net_return is not None
        and candidate.expected_net_return > 0
        and candidate.confidence >= 0.80
    ]
    return tuple(eligible[: sleeve.max_open_positions])
