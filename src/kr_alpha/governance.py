from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

import numpy as np

from .factors import prior_weights


@dataclass(frozen=True)
class FactorGovernanceState:
    weights: Mapping[str, float]
    statuses: Mapping[str, str]
    ewma_ic: Mapping[str, float | None]
    icir: Mapping[str, float | None]
    evidence_months: int
    version: str = "kr-alpha-weight-governance-v1"


@dataclass(frozen=True)
class PromotionEvidence:
    oos_months: int
    trades: int
    net_information_ratio: float | None
    max_drawdown: float | None
    deflated_sharpe: float | None
    pbo: float | None
    paper_months: int
    data_quality: float
    capacity_krw: float


@dataclass(frozen=True)
class PromotionDecision:
    approved: bool
    reasons: tuple[str, ...]


def _ewma(values: Sequence[float], alpha: float = 0.25) -> float | None:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if not finite:
        return None
    estimate = finite[0]
    for value in finite[1:]:
        estimate = alpha * value + (1 - alpha) * estimate
    return estimate


def build_dynamic_weights(
    ic_history: Mapping[str, Sequence[float]],
    *,
    cost_drag: Mapping[str, float] | None = None,
    instability: Mapping[str, float] | None = None,
    regime_multiplier: Mapping[str, float] | None = None,
    previous_weights: Mapping[str, float] | None = None,
    minimum_oos_months: int = 12,
    monthly_change_cap: float = 0.03,
) -> FactorGovernanceState:
    priors = prior_weights()
    months = max((len(values) for values in ic_history.values()), default=0)
    if months < minimum_oos_months:
        return FactorGovernanceState(
            weights=priors,
            statuses={name: "INSUFFICIENT_EVIDENCE" for name in priors},
            ewma_ic={name: _ewma(ic_history.get(name, ())) for name in priors},
            icir={name: None for name in priors},
            evidence_months=months,
        )
    raw: dict[str, float] = {}
    statuses: dict[str, str] = {}
    ewma_values: dict[str, float | None] = {}
    icir_values: dict[str, float | None] = {}
    for name, prior in priors.items():
        values = np.asarray(tuple(ic_history.get(name, ())), dtype=float)
        values = values[np.isfinite(values)]
        ewma_ic = _ewma(values.tolist())
        stdev = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
        icir = None if ewma_ic is None or stdev <= 1e-12 else ewma_ic / stdev
        ewma_values[name] = ewma_ic
        icir_values[name] = icir
        after_cost = (ewma_ic or 0.0) - max(0.0, float((cost_drag or {}).get(name, 0.0)))
        stability_penalty = max(0.0, min(1.0, float((instability or {}).get(name, 0.0))))
        multiplier = max(0.0, min(2.0, float((regime_multiplier or {}).get(name, 1.0))))
        efficacy = max(0.0, after_cost) * (1.0 - stability_penalty) * multiplier
        candidate = 0.70 * prior + 0.30 * efficacy
        prior_month = float((previous_weights or priors).get(name, prior))
        raw[name] = max(prior_month - monthly_change_cap, min(prior_month + monthly_change_cap, candidate))
        statuses[name] = "DEGRADED" if after_cost <= 0 else "ACTIVE"
    total = sum(raw.values()) or 1.0
    weights = {name: value / total for name, value in raw.items()}
    return FactorGovernanceState(weights, statuses, ewma_values, icir_values, months)


def evaluate_promotion(evidence: PromotionEvidence) -> PromotionDecision:
    reasons: list[str] = []
    if evidence.oos_months < 24:
        reasons.append("insufficient_oos_period")
    if evidence.trades < 100:
        reasons.append("insufficient_trades")
    if evidence.net_information_ratio is None or evidence.net_information_ratio <= 0:
        reasons.append("net_performance_not_positive")
    if evidence.max_drawdown is None or evidence.max_drawdown < -0.20:
        reasons.append("drawdown_gate_failed")
    if evidence.deflated_sharpe is None or evidence.deflated_sharpe <= 0:
        reasons.append("deflated_sharpe_gate_failed")
    if evidence.pbo is None or evidence.pbo > 0.20:
        reasons.append("pbo_gate_failed")
    if evidence.paper_months < 6:
        reasons.append("paper_period_too_short")
    if evidence.data_quality < 0.90:
        reasons.append("data_quality_gate_failed")
    if evidence.capacity_krw <= 0:
        reasons.append("capacity_not_verified")
    return PromotionDecision(not reasons, tuple(reasons))
