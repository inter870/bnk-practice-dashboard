from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Mapping, Sequence

from .config import KRAlphaConfig
from .domain import AlphaCandidate, FactorValue, FixtureStock
from .factors import calculate_factor_panel, factor_spec
from .fixtures import FixtureKRAlphaProvider
from .governance import FactorGovernanceState, build_dynamic_weights
from .portfolio import TargetPortfolio, build_target_portfolio
from .regime import RegimeState, classify_regime


SEVERE_FLAGS = {"delisting", "administrative_issue", "suspension"}


@dataclass(frozen=True)
class KRAlphaOverview:
    data_mode: str
    data_badge: str
    decision_time: datetime
    model_status: str
    governance: FactorGovernanceState
    candidates: tuple[AlphaCandidate, ...]
    warnings: tuple[str, ...]
    config_hash: str
    provider: str
    provider_version: str
    regime: RegimeState
    target_portfolio: TargetPortfolio


def estimate_cost_bps(stock: FixtureStock, config: KRAlphaConfig) -> float:
    participation = 0.0 if stock.adv_20d_krw <= 0 else max(0.0, stock.expected_order_krw / stock.adv_20d_krw)
    impact = config.transaction_costs.market_impact_coefficient * math.sqrt(participation)
    return config.transaction_costs.base_round_trip_bps + impact


def _candidate(
    stock: FixtureStock,
    values: Sequence[FactorValue],
    weights: Mapping[str, float],
    decision_time: datetime,
    config: KRAlphaConfig,
) -> AlphaCandidate:
    ready = [value for value in values if value.z_score is not None and value.available_at <= decision_time]
    weighted = sum(float(value.z_score) * weights.get(value.factor_name, 0.0) for value in ready)
    coverage = len(ready) / max(1, len(values))
    score = max(0.0, min(100.0, 50.0 + weighted * 15.0))
    cost_bps = estimate_cost_bps(stock, config)
    participation = stock.expected_order_krw / stock.adv_20d_krw if stock.adv_20d_krw > 0 else float("inf")
    risk_flags = set(stock.event_flags) & SEVERE_FLAGS
    if participation > config.risk.maximum_adv_participation:
        risk_flags.add("adv_participation_exceeded")
    if "short_crowding" in stock.event_flags:
        risk_flags.add("short_crowding")
    fixture_mode = config.data_mode == "fixture"
    investment_eligible = not fixture_mode and not risk_flags and coverage >= 0.80
    rating = "HIGH_RISK_EXCLUDE" if risk_flags & SEVERE_FLAGS else "WATCH"
    max_weight = min(
        config.risk.max_position_weight,
        config.risk.max_kosdaq_position_weight if stock.security.market == "KOSDAQ" else config.risk.max_position_weight,
        max(0.0, config.risk.maximum_adv_participation * stock.adv_20d_krw / 100_000_000.0),
    )
    reason_codes = tuple(
        f"{value.factor_name}:{'positive' if (value.z_score or 0) > 0 else 'negative'}"
        for value in sorted(ready, key=lambda item: abs(item.z_score or 0), reverse=True)[:4]
    )
    return AlphaCandidate(
        instrument_id=stock.security.instrument_id,
        ticker=stock.security.ticker,
        name_ko=stock.security.name_ko,
        market=stock.security.market,
        sector=stock.security.sector,
        composite_score=round(score, 2),
        expected_gross_return=None,
        expected_net_return=None,
        confidence=round(coverage * (0.55 if fixture_mode else 1.0), 3),
        cost_estimate_bps=round(cost_bps, 2),
        capacity_krw=max(0.0, stock.adv_20d_krw * config.risk.maximum_adv_participation),
        suggested_max_weight=max_weight,
        rating=rating,
        reason_codes=reason_codes,
        risk_flags=tuple(sorted(risk_flags)),
        decision_time=decision_time,
        model_version=config.model_version,
        config_hash=config.config_hash,
        factor_values=tuple(values),
        investment_eligible=investment_eligible,
    )


def build_overview(
    decision_time: datetime,
    config: KRAlphaConfig,
    *,
    provider: FixtureKRAlphaProvider | None = None,
    ic_history: Mapping[str, Sequence[float]] | None = None,
) -> KRAlphaOverview:
    if provider is None and config.data_mode != "fixture":
        governance = build_dynamic_weights(ic_history or {})
        regime = classify_regime(market_trend=None, volatility_pressure=None, fx_pressure=None, liquidity_support=None)
        return KRAlphaOverview(
            data_mode=config.data_mode,
            data_badge=f"{config.data_mode.upper()} · 어댑터 미연결",
            decision_time=decision_time,
            model_status="DISABLED",
            governance=governance,
            candidates=(),
            warnings=(f"{config.data_mode} 데이터 공급자가 연결되지 않아 계산을 중단했습니다.",),
            config_hash=config.config_hash,
            provider="unavailable",
            provider_version="none",
            regime=regime,
            target_portfolio=build_target_portfolio((), config),
        )
    provider = provider or FixtureKRAlphaProvider()
    stocks = provider.snapshot(decision_time)
    panel = calculate_factor_panel(stocks, decision_time)
    governance = build_dynamic_weights(ic_history or {})
    candidates = tuple(
        sorted(
            (
                _candidate(stock, panel[stock.security.instrument_id], governance.weights, decision_time, config)
                for stock in stocks
            ),
            key=lambda item: (item.investment_eligible, item.composite_score),
            reverse=True,
        )
    )
    regime = classify_regime(market_trend=0.45, volatility_pressure=0.20, fx_pressure=0.35, liquidity_support=0.25)
    target_portfolio = build_target_portfolio(candidates, config)
    warnings = ["DEMO DATA · 투자판단 미반영"] if config.data_mode == "fixture" else []
    if governance.evidence_months < 12:
        warnings.append("OOS 표본 부족 · prior weight 유지")
    return KRAlphaOverview(
        data_mode=config.data_mode,
        data_badge="DEMO DATA · 투자판단 미반영" if config.data_mode == "fixture" else config.data_mode.upper(),
        decision_time=decision_time,
        model_status="INSUFFICIENT_EVIDENCE" if governance.evidence_months < 12 else "SHADOW",
        governance=governance,
        candidates=candidates,
        warnings=tuple(warnings),
        config_hash=config.config_hash,
        provider=provider.name,
        provider_version=provider.version,
        regime=regime,
        target_portfolio=target_portfolio,
    )
