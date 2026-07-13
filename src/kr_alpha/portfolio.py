from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .config import KRAlphaConfig
from .domain import AlphaCandidate


@dataclass(frozen=True)
class TargetWeight:
    instrument_id: str
    weight: float
    reason: str


@dataclass(frozen=True)
class TargetPortfolio:
    weights: tuple[TargetWeight, ...]
    cash_weight: float
    rejected: tuple[tuple[str, str], ...]
    status: str


def build_target_portfolio(candidates: Sequence[AlphaCandidate], config: KRAlphaConfig) -> TargetPortfolio:
    remaining = max(0.0, 1.0 - config.risk.minimum_cash_weight)
    accepted: list[TargetWeight] = []
    rejected: list[tuple[str, str]] = []
    sector_weights: dict[str, float] = {}
    for candidate in candidates:
        if not candidate.investment_eligible:
            rejected.append((candidate.instrument_id, "candidate_not_investment_eligible"))
            continue
        if candidate.risk_flags:
            rejected.append((candidate.instrument_id, "risk_flags_present"))
            continue
        cap = min(candidate.suggested_max_weight, config.risk.max_position_weight, remaining)
        if candidate.market == "KOSDAQ":
            cap = min(cap, config.risk.max_kosdaq_position_weight)
        sector_room = max(0.0, config.risk.max_sector_weight - sector_weights.get(candidate.sector, 0.0))
        weight = min(cap, sector_room)
        if weight <= 0:
            rejected.append((candidate.instrument_id, "portfolio_constraints_exhausted"))
            continue
        accepted.append(TargetWeight(candidate.instrument_id, weight, "risk_constrained_candidate_weight"))
        sector_weights[candidate.sector] = sector_weights.get(candidate.sector, 0.0) + weight
        remaining -= weight
    cash = 1.0 - sum(item.weight for item in accepted)
    status = "CASH_ONLY" if not accepted else "PROPOSED_PAPER_ONLY"
    return TargetPortfolio(tuple(accepted), cash, tuple(rejected), status)
