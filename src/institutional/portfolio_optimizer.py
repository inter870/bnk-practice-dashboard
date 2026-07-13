from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Iterable

from .forward_alpha import build_forward_alpha_ranking_panel
from .krw_rates_fx import build_krw_rates_fx_dashboard
from .models import (
    DataPoint,
    DataSourceMeta,
    ForwardAlphaRankingPanelState,
    ForwardAlphaRankRow,
    KRWRatesFXDashboardState,
    OptimizerRecommendationRow,
    PortfolioAlertRow,
    PortfolioOptimizerAlertCenterState,
    StressScenarioRow,
)


SEVERE_RISK_FLAGS = {
    "severe_accounting_risk",
    "severe_dilution_risk",
    "delisting_or_administrative_risk",
    "stale_data_risk",
    "liquidity_risk",
}
RECOMMENDATION_ACTIONS = {"BUY", "ADD", "HOLD", "TRIM", "SELL", "AVOID", "EXCLUDE"}


@dataclass(frozen=True)
class OptimizerConstraints:
    max_single_stock_weight: float = 0.07
    max_kosdaq_single_stock_weight: float = 0.05
    max_sector_weight: float = 0.30
    cash_buffer: float = 0.05
    illiquid_cap: float = 0.02
    min_trade_weight: float = 0.005


MOCK_HOLDINGS: tuple[dict[str, Any], ...] = (
    {"code": "005930", "name": "Samsung Electronics", "sector": "Semiconductors", "market": "KOSPI", "current_weight": 0.11, "current_value": 35_000_000},
    {"code": "000660", "name": "SK hynix", "sector": "Semiconductors", "market": "KOSPI", "current_weight": 0.09, "current_value": 28_600_000},
    {"code": "034020", "name": "Doosan Enerbility", "sector": "Industrials", "market": "KOSPI", "current_weight": 0.06, "current_value": 19_000_000},
    {"code": "035420", "name": "NAVER", "sector": "Internet / Growth", "market": "KOSPI", "current_weight": 0.045, "current_value": 14_300_000},
    {"code": "105560", "name": "KB Financial", "sector": "Banks / Insurance", "market": "KOSPI", "current_weight": 0.035, "current_value": 11_100_000},
)


def _now_iso(now: datetime | None = None) -> str:
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.isoformat(timespec="seconds")


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _get(item: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(item, dict) and name in item:
            return item.get(name)
        if hasattr(item, name):
            return getattr(item, name)
    return default


def _meta(
    *,
    source: str,
    as_of_date: str | None,
    fetched_at: str,
    confidence: int,
    stale: bool,
    missing: bool,
    fallback: bool,
    endpoint: str = "/api/dashboard/portfolio-optimizer",
    warnings: tuple[str, ...] = (),
) -> DataSourceMeta:
    return DataSourceMeta(
        source=source,
        provider="Risk-controlled optimizer",
        source_url=None,
        as_of_date=as_of_date,
        available_at=as_of_date,
        fetched_at=fetched_at,
        frequency="daily",
        unit="portfolio_weight",
        quality_score=max(0, min(100, confidence)),
        is_fallback=fallback,
        stale_data_flag=stale,
        source_table_or_endpoint=endpoint,
        confidence_score=max(0, min(100, confidence)),
        missing_data_flag=missing,
        warnings=warnings,
    )


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    return text.zfill(6) if text else "N/A"


def _holding_map(holdings: Iterable[Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in holdings:
        code = _normalize_code(_get(item, "code", "symbol", "stock_code", "stockCode"))
        if code == "N/A":
            continue
        weight = _finite(_get(item, "current_weight", "weight", "currentWeight"))
        current_value = _finite(_get(item, "current_value", "market_value", "marketValue", default=0.0)) or 0.0
        result[code] = {
            "code": code,
            "name": str(_get(item, "name", default=code) or code),
            "sector": str(_get(item, "sector", default="Unclassified") or "Unclassified"),
            "market": str(_get(item, "market", default="UNKNOWN") or "UNKNOWN").upper(),
            "current_weight": max(0.0, weight if weight is not None else 0.0),
            "current_value": max(0.0, current_value),
        }
    return result


def _row_cap(row: ForwardAlphaRankRow, holdings_by_code: dict[str, dict[str, Any]], constraints: OptimizerConstraints) -> tuple[float, list[str]]:
    reasons: list[str] = []
    holding_market = str(holdings_by_code.get(row.code, {}).get("market", "") or "").upper()
    row_market = str(getattr(row, "market", "UNKNOWN") or "UNKNOWN").upper()
    market = holding_market if holding_market not in {"", "UNKNOWN", "N/A"} else row_market
    if "KOSDAQ" in market:
        cap = constraints.max_kosdaq_single_stock_weight
    elif "KOSPI" in market:
        cap = constraints.max_single_stock_weight
    else:
        cap = min(constraints.max_single_stock_weight, constraints.max_kosdaq_single_stock_weight)
        reasons.append("market unknown; conservative cap applied")
    if row.liquidity_score is not None and row.liquidity_score < 30:
        cap = min(cap, constraints.illiquid_cap)
        reasons.append("illiquid stock capped")
    if row.rating == "HIGH_RISK_EXCLUDE" or set(row.risk_flags) & SEVERE_RISK_FLAGS:
        cap = 0.0
        reasons.append("severe risk excluded")
    return cap, reasons


def optimize_target_weights(
    alpha_rows: Iterable[ForwardAlphaRankRow],
    *,
    holdings: Iterable[Any] | None = None,
    constraints: OptimizerConstraints | None = None,
) -> dict[str, float]:
    constraints = constraints or OptimizerConstraints()
    holdings_by_code = _holding_map(holdings or [])
    rows = list(alpha_rows)
    alpha_codes = {row.code for row in rows}
    eligible: list[tuple[ForwardAlphaRankRow, float, float]] = []
    targets: dict[str, float] = {}
    sector_allocated: dict[str, float] = {}
    stock_budget = max(0.0, 1.0 - constraints.cash_buffer)

    # Preserve every current holding in the review universe. Without alpha data,
    # scale current weights proportionally so ticker ordering cannot drive trims.
    unscored_candidates: dict[str, tuple[float, str]] = {}
    for code, holding in sorted(holdings_by_code.items()):
        if code in alpha_codes:
            continue
        market = str(holding.get("market", "UNKNOWN")).upper()
        cap = (
            constraints.max_kosdaq_single_stock_weight
            if "KOSDAQ" in market
            else constraints.max_single_stock_weight
            if "KOSPI" in market
            else min(constraints.max_single_stock_weight, constraints.max_kosdaq_single_stock_weight)
        )
        sector = str(holding.get("sector", "Unclassified"))
        current_weight = max(0.0, float(holding.get("current_weight", 0.0) or 0.0))
        unscored_candidates[code] = (min(current_weight, cap), sector)

    for sector in sorted({sector for _, sector in unscored_candidates.values()}):
        sector_codes = [code for code, (_, name) in unscored_candidates.items() if name == sector]
        sector_total = sum(unscored_candidates[code][0] for code in sector_codes)
        scale = min(1.0, constraints.max_sector_weight / sector_total) if sector_total > 0 else 1.0
        for code in sector_codes:
            weight, name = unscored_candidates[code]
            unscored_candidates[code] = (weight * scale, name)

    unscored_total = sum(weight for weight, _ in unscored_candidates.values())
    portfolio_scale = min(1.0, stock_budget / unscored_total) if unscored_total > 0 else 1.0
    for code, (weight, sector) in unscored_candidates.items():
        targets[code] = weight * portfolio_scale
        sector_allocated[sector] = sector_allocated.get(sector, 0.0) + targets[code]

    for row in rows:
        cap, _ = _row_cap(row, holdings_by_code, constraints)
        if cap <= 0:
            targets[row.code] = 0.0
            continue
        if row.rating in {"AVOID", "HIGH_RISK_EXCLUDE"} or row.confidence_score < 45:
            targets[row.code] = 0.0
            continue
        raw_score = max(0.0, row.final_alpha_score - 45) * max(0.35, row.confidence_score / 100)
        if raw_score <= 0:
            targets[row.code] = 0.0
            continue
        eligible.append((row, raw_score, cap))

    reserved_weight = sum(targets.values())
    investable_weight = max(0.0, stock_budget - reserved_weight)
    total_raw = sum(item[1] for item in eligible)
    for row, raw_score, cap in sorted(eligible, key=lambda item: item[1], reverse=True):
        desired = investable_weight * raw_score / total_raw if total_raw > 0 else 0.0
        sector_room = max(0.0, constraints.max_sector_weight - sector_allocated.get(row.sector, 0.0))
        target = min(desired, cap, sector_room)
        targets[row.code] = round(_clamp(target, 0.0, cap), 6)
        sector_allocated[row.sector] = sector_allocated.get(row.sector, 0.0) + targets[row.code]
    for code in holdings_by_code:
        targets.setdefault(code, 0.0)
    return targets


def action_from_delta(current_weight: float, target_weight: float, rating: str, rejection_reasons: Iterable[str], min_trade_weight: float = 0.005) -> str:
    if rejection_reasons:
        return "EXCLUDE" if "severe risk excluded" in set(rejection_reasons) else "NO_TRADE"
    delta = target_weight - current_weight
    if target_weight <= 0 and current_weight > min_trade_weight:
        return "SELL"
    if abs(delta) < min_trade_weight:
        return "HOLD"
    if delta > 0:
        return "BUY" if current_weight <= min_trade_weight else "ADD"
    return "TRIM"


def _build_recommendations(
    alpha_state: ForwardAlphaRankingPanelState,
    *,
    holdings: Iterable[Any],
    total_portfolio_value: float,
    constraints: OptimizerConstraints,
    now: datetime | None,
    fallback: bool,
) -> tuple[OptimizerRecommendationRow, ...]:
    holdings_by_code = _holding_map(holdings)
    targets = optimize_target_weights(alpha_state.ranking_rows, holdings=holdings, constraints=constraints)
    alpha_map = {row.code: row for row in alpha_state.ranking_rows}
    rows: list[OptimizerRecommendationRow] = []
    fetched_at = _now_iso(now)
    for code in sorted(set(alpha_map) | set(holdings_by_code)):
        alpha = alpha_map.get(code)
        holding = holdings_by_code.get(code, {})
        if alpha is None:
            current_weight = _finite(holding.get("current_weight")) or 0.0
            target_weight = max(0.0, targets.get(code, 0.0))
            current_value = _finite(holding.get("current_value")) or total_portfolio_value * current_weight
            target_value = total_portfolio_value * target_weight
            action = "WATCH"
            meta = _meta(
                source="Holdings input; forward alpha unavailable",
                as_of_date=None,
                fetched_at=fetched_at,
                confidence=0,
                stale=False,
                missing=True,
                fallback=fallback,
                warnings=("alpha_data_unavailable",),
            )
            rows.append(
                OptimizerRecommendationRow(
                    code=code,
                    name=str(holding.get("name", code) or code),
                    sector=str(holding.get("sector", "Unclassified") or "Unclassified"),
                    market=str(holding.get("market", "UNKNOWN") or "UNKNOWN"),
                    current_weight=current_weight,
                    target_weight=target_weight,
                    weight_delta=target_weight - current_weight,
                    current_value=current_value,
                    target_value=target_value,
                    trade_value_estimate=target_value - current_value,
                    action=action,
                    final_alpha_score=None,
                    confidence_score=None,
                    liquidity_score=None,
                    transaction_cost_bps=0.0,
                    reasons=("현재 보유 비중과 포트폴리오 제약만 반영",),
                    rejection_reasons=("미래 알파 데이터 부족",),
                    risk_flags=("alpha_data_unavailable",),
                    meta=meta,
                    analytical_action=("TRIM" if target_weight + constraints.min_trade_weight < current_weight else "HOLD"),
                    action_eligible=False,
                    blocking_reason_codes=("alpha_data_unavailable",),
                )
            )
            continue
        cap, cap_reasons = _row_cap(alpha, holdings_by_code, constraints)
        current_weight = _finite(holding.get("current_weight")) or 0.0
        target_weight = min(targets.get(code, 0.0), cap)
        weight_delta = target_weight - current_weight
        current_value = _finite(holding.get("current_value")) or total_portfolio_value * current_weight
        target_value = total_portfolio_value * target_weight
        trade_value = target_value - current_value
        informational_cap_reasons = [reason for reason in cap_reasons if reason.startswith("market unknown")]
        rejection_reasons = [reason for reason in cap_reasons if reason not in informational_cap_reasons]
        if alpha.rating in {"HIGH_RISK_EXCLUDE", "AVOID"} and target_weight <= 0:
            rejection_reasons.append(alpha.rating.lower())
        if alpha.confidence_score < 45:
            rejection_reasons.append("low confidence")
        if alpha.meta.stale_data_flag:
            rejection_reasons.append("stale data")
        action = action_from_delta(current_weight, target_weight, alpha.rating, rejection_reasons, constraints.min_trade_weight)
        reasons = list(alpha.positive_drivers[:3])
        reasons.extend(informational_cap_reasons)
        if not reasons:
            reasons.append(f"alpha score {alpha.final_alpha_score}")
        warnings = tuple(alpha.risk_flags)
        meta = _meta(
            source="ForwardAlphaRankingPanel + holdings",
            as_of_date=alpha.meta.as_of_date,
            fetched_at=fetched_at,
            confidence=alpha.confidence_score,
            stale=alpha.meta.stale_data_flag,
            missing=alpha.meta.missing_data_flag,
            fallback=fallback or alpha.meta.is_fallback,
            warnings=warnings,
        )
        rows.append(
            OptimizerRecommendationRow(
                code=code,
                name=alpha.name,
                sector=alpha.sector,
                market=str(holding.get("market") or alpha.market or "UNKNOWN"),
                current_weight=current_weight,
                target_weight=target_weight,
                weight_delta=weight_delta,
                current_value=current_value,
                target_value=target_value,
                trade_value_estimate=trade_value,
                action=action,  # type: ignore[arg-type]
                final_alpha_score=alpha.final_alpha_score,
                confidence_score=alpha.confidence_score,
                liquidity_score=alpha.liquidity_score,
                transaction_cost_bps=12.0 if abs(weight_delta) > constraints.min_trade_weight else 0.0,
                reasons=tuple(dict.fromkeys(reasons)),
                rejection_reasons=tuple(dict.fromkeys(rejection_reasons)),
                risk_flags=tuple(dict.fromkeys(alpha.risk_flags)),
                meta=meta,
                analytical_action=action,
                action_eligible=action not in {"NO_TRADE"},
                blocking_reason_codes=tuple(dict.fromkeys(rejection_reasons)),
            )
        )
    return tuple(sorted(rows, key=lambda row: (row.action in {"EXCLUDE", "AVOID"}, -abs(row.weight_delta), -float(row.final_alpha_score or 0), row.code)))


def _alert_meta(now: datetime | None, fallback: bool) -> DataSourceMeta:
    return _meta(
        source="Portfolio optimizer alert rules",
        as_of_date=(now or datetime.now(timezone.utc)).date().isoformat(),
        fetched_at=_now_iso(now),
        confidence=82 if not fallback else 68,
        stale=False,
        missing=False,
        fallback=fallback,
        endpoint="/api/dashboard/alerts",
    )


def generate_portfolio_alerts(
    recommendations: Iterable[OptimizerRecommendationRow],
    *,
    cash_ratio: float,
    constraints: OptimizerConstraints,
    fx_shock_score: int | None = None,
    rate_shock_score: int | None = None,
    now: datetime | None = None,
    fallback: bool = False,
) -> tuple[PortfolioAlertRow, ...]:
    rows = list(recommendations)
    meta = _alert_meta(now, fallback)
    alerts: list[PortfolioAlertRow] = []
    for row in rows:
        if row.current_weight > constraints.max_single_stock_weight:
            alerts.append(PortfolioAlertRow(f"concentration-{row.code}", "concentration_warning", "warning", row.code, "Single stock concentration", f"{row.name} exceeds max single-stock weight.", row.current_weight, constraints.max_single_stock_weight, "Review target trim before adding capital.", meta))
        if row.meta.stale_data_flag:
            alerts.append(PortfolioAlertRow(f"stale-{row.code}", "stale_data_warning", "warning", row.code, "Stale feature data", f"{row.name} has stale feature data.", None, None, "Refresh source data before acting on this row.", meta))
        if "severe_dilution_risk" in row.risk_flags or "delisting_or_administrative_risk" in row.risk_flags:
            alerts.append(PortfolioAlertRow(f"dart-{row.code}", "negative_dart_event", "critical", row.code, "Negative DART event", f"{row.name} has severe disclosure risk.", None, None, "Read source filing and keep target weight at zero unless risk clears.", meta))
        if row.liquidity_score is not None and row.liquidity_score < 30:
            alerts.append(PortfolioAlertRow(f"liquidity-{row.code}", "liquidity_deterioration", "warning", row.code, "Liquidity deterioration", f"{row.name} is capped due to low liquidity.", float(row.liquidity_score), 30.0, "Limit order size and reassess capacity.", meta))
        if row.final_alpha_score is not None and row.current_weight >= 0.03 and row.final_alpha_score < 45:
            alerts.append(PortfolioAlertRow(f"downgrade-{row.code}", "top_holding_score_downgrade", "warning", row.code, "Top holding score downgrade", f"{row.name} score is below optimizer threshold.", float(row.final_alpha_score), 45.0, "Review thesis before adding more capital.", meta))
        if row.final_alpha_score is not None and row.final_alpha_score < 35:
            alerts.append(PortfolioAlertRow(f"model-{row.code}", "model_score_deterioration", "warning", row.code, "Model score deterioration", f"{row.name} has weak forward alpha score.", float(row.final_alpha_score), 35.0, "Check negative drivers and risk flags.", meta))

    sector_weights: dict[str, float] = {}
    for row in rows:
        sector_weights[row.sector] = sector_weights.get(row.sector, 0.0) + row.target_weight
    for sector, weight in sector_weights.items():
        if weight > constraints.max_sector_weight:
            alerts.append(PortfolioAlertRow(f"sector-{sector}", "sector_overweight", "warning", None, "Sector overweight", f"{sector} target weight exceeds sector cap.", weight, constraints.max_sector_weight, "Rebalance target weights across sectors.", meta))
    if cash_ratio < constraints.cash_buffer:
        alerts.append(PortfolioAlertRow("cash-buffer", "concentration_warning", "warning", None, "Cash buffer below target", "Cash is below optimizer buffer.", cash_ratio, constraints.cash_buffer, "Hold or rebuild cash before adding capital.", meta))
    if fx_shock_score is not None and fx_shock_score >= 70:
        alerts.append(PortfolioAlertRow("fx-shock", "fx_shock", "warning", None, "FX shock", "FX shock score is elevated.", float(fx_shock_score), 70.0, "Review KRW sensitivity and exporter/importer exposure.", meta))
    if rate_shock_score is not None and rate_shock_score >= 70:
        alerts.append(PortfolioAlertRow("rate-shock", "rate_shock", "warning", None, "Rate shock", "Rate shock score is elevated.", float(rate_shock_score), 70.0, "Review growth stock and duration-sensitive exposure.", meta))
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    return tuple(sorted(alerts, key=lambda alert: (severity_rank[alert.severity], alert.alert_type, alert.code or "")))


def _stress_scenarios(recommendations: tuple[OptimizerRecommendationRow, ...], *, now: datetime | None, fallback: bool) -> tuple[StressScenarioRow, ...]:
    meta = _meta(
        source="Portfolio optimizer stress rules",
        as_of_date=(now or datetime.now(timezone.utc)).date().isoformat(),
        fetched_at=_now_iso(now),
        confidence=70,
        stale=False,
        missing=False,
        fallback=fallback,
    )
    affected_fx = tuple(row.code for row in recommendations if row.sector in {"Semiconductors", "Internet / Growth"} and row.target_weight > 0)[:5]
    affected_rates = tuple(row.code for row in recommendations if row.sector in {"Internet / Growth", "Semiconductors"} and row.target_weight > 0)[:5]
    affected_liquidity = tuple(row.code for row in recommendations if row.liquidity_score is not None and row.liquidity_score < 35)[:5]
    fx_impact = -sum(row.target_weight for row in recommendations if row.code in affected_fx) * 0.08
    rate_impact = -sum(row.target_weight for row in recommendations if row.code in affected_rates) * 0.06
    liquidity_impact = -sum(row.target_weight for row in recommendations if row.code in affected_liquidity) * 0.12
    return (
        StressScenarioRow("usdkrw_shock", "USD/KRW +5% shock", fx_impact, affected_fx, "KRW shock proxy applied to export/growth exposure.", meta),
        StressScenarioRow("rate_shock", "KR/US rates +50bp shock", rate_impact, affected_rates, "Rate shock proxy applied to growth and duration-sensitive exposure.", meta),
        StressScenarioRow("liquidity_shock", "Liquidity -30% shock", liquidity_impact, affected_liquidity, "Low-liquidity holdings receive larger haircut.", meta),
    )


def build_portfolio_optimizer_alert_center(
    *,
    alpha_state: ForwardAlphaRankingPanelState | None = None,
    holdings: Iterable[Any] | None = None,
    total_portfolio_value: float | None = None,
    cash_ratio: float | None = None,
    constraints: OptimizerConstraints | None = None,
    fx_rates_state: KRWRatesFXDashboardState | None = None,
    now: datetime | None = None,
    allow_mock: bool = True,
    action_eligible: bool = True,
    blocking_reason_codes: Iterable[str] = (),
) -> PortfolioOptimizerAlertCenterState:
    constraints = constraints or OptimizerConstraints()
    if alpha_state is None and allow_mock:
        alpha_state = build_forward_alpha_ranking_panel(now=now, allow_mock=True)
    raw_holdings = list(holdings or [])
    fallback = False
    if not raw_holdings and allow_mock:
        raw_holdings = [dict(item, is_fallback=True) for item in MOCK_HOLDINGS]
        fallback = True
    if fx_rates_state is None and allow_mock:
        fx_rates_state = build_krw_rates_fx_dashboard(now=now, allow_mock=True)
    if alpha_state is None:
        fetched_at = _now_iso(now)
        meta = _meta(
            source="Not connected",
            as_of_date=None,
            fetched_at=fetched_at,
            confidence=0,
            stale=True,
            missing=True,
            fallback=True,
        )
        return PortfolioOptimizerAlertCenterState(
            module_id="PortfolioOptimizerAlertCenter",
            status="empty",
            title="Portfolio Optimizer & Alert Center",
            summary="Forward alpha ranking is required before optimizer targets can be calculated.",
            data_points=(DataPoint("recommendation_count", "Recommendation Count", 0, meta, "0"),),
            explanation=("Connect holdings and ForwardAlphaRankingPanel output to calculate target weights.",),
            risk_flags=("missing_optimizer_inputs",),
            stale_after_minutes=24 * 60,
            target_cash_ratio=constraints.cash_buffer,
            max_single_stock_weight=constraints.max_single_stock_weight,
            max_kosdaq_single_stock_weight=constraints.max_kosdaq_single_stock_weight,
            max_sector_weight=constraints.max_sector_weight,
        )

    holding_map = _holding_map(raw_holdings)
    inferred_value = sum(item["current_value"] for item in holding_map.values())
    total_value = total_portfolio_value or (inferred_value / max(0.01, sum(item["current_weight"] for item in holding_map.values())) if holding_map else 100_000_000.0)
    cash = cash_ratio if cash_ratio is not None else max(0.0, 1.0 - sum(item["current_weight"] for item in holding_map.values()))
    recommendations = _build_recommendations(
        alpha_state,
        holdings=raw_holdings,
        total_portfolio_value=total_value,
        constraints=constraints,
        now=now,
        fallback=fallback,
    )
    gate_reasons = tuple(dict.fromkeys(str(item) for item in blocking_reason_codes if str(item)))
    if not action_eligible:
        recommendations = tuple(
            replace(
                row,
                analytical_action=row.analytical_action or row.action,
                action="NO_TRADE",
                target_weight=row.current_weight,
                weight_delta=0.0,
                target_value=row.current_value,
                trade_value_estimate=0.0,
                transaction_cost_bps=0.0,
                action_eligible=False,
                blocking_reason_codes=tuple(dict.fromkeys((*row.blocking_reason_codes, *gate_reasons))),
                rejection_reasons=tuple(dict.fromkeys((*row.rejection_reasons, *gate_reasons))),
            )
            for row in recommendations
        )
    target_stock_ratio = min(1.0, sum(max(0.0, row.target_weight) for row in recommendations))
    target_cash_ratio = max(constraints.cash_buffer, 1.0 - target_stock_ratio)
    alerts = generate_portfolio_alerts(
        recommendations,
        cash_ratio=cash,
        constraints=constraints,
        fx_shock_score=fx_rates_state.fx_shock_score if fx_rates_state else None,
        rate_shock_score=fx_rates_state.rate_shock_score if fx_rates_state else None,
        now=now,
        fallback=fallback or alpha_state.status == "stale",
    )
    stale = alpha_state.status == "stale" or any(row.meta.stale_data_flag for row in recommendations)
    missing = not recommendations
    alpha_coverage_missing = bool(recommendations) and all(row.final_alpha_score is None for row in recommendations)
    fetched_at = _now_iso(now)
    meta = _meta(
        source="ForwardAlphaRankingPanel + holdings + alert rules",
        as_of_date=alpha_state.latest_source_at[:10] if alpha_state.latest_source_at else (now or datetime.now(timezone.utc)).date().isoformat(),
        fetched_at=fetched_at,
        confidence=0 if alpha_coverage_missing else 70 if fallback else 84,
        stale=stale,
        missing=missing or alpha_coverage_missing,
        fallback=fallback or alpha_state.status == "stale",
    )
    rejected = tuple(row for row in recommendations if row.action in {"AVOID", "EXCLUDE"} or row.rejection_reasons)
    data_points = (
        DataPoint("recommendation_count", "Recommendation Count", len(recommendations), meta, str(len(recommendations))),
        DataPoint("alert_count", "Alert Count", len(alerts), meta, str(len(alerts))),
        DataPoint("cash_ratio", "Cash Ratio", cash, meta, f"{cash * 100:.1f}%"),
        DataPoint("target_cash_ratio", "Target Cash Ratio", target_cash_ratio, meta, f"{target_cash_ratio * 100:.1f}%"),
    )
    status = "empty" if missing else "stale" if stale or not action_eligible else "ready"
    summary = "Risk-controlled target weights and monitoring alerts are ready. No automatic order execution is implemented."
    if rejected:
        summary = "Optimizer excludes or avoids severe-risk candidates before assigning target weights."
    if fallback:
        summary = "Mock holdings and optimizer outputs are shown until real portfolio holdings are connected."
    elif alpha_coverage_missing:
        summary = "보유종목은 연결됐지만 미래 알파 데이터가 부족해 현재 비중과 위험 제약만 표시합니다."
    elif not action_eligible:
        summary = "포트폴리오 대사 또는 데이터 적격성 점검이 완료되지 않아 행동 생성을 차단했습니다."
    return PortfolioOptimizerAlertCenterState(
        module_id="PortfolioOptimizerAlertCenter",
        status=status,
        title="Portfolio Optimizer & Alert Center",
        summary=summary,
        data_points=data_points,
        explanation=(
            "Long-only and no leverage constraints are enforced.",
            "Targets respect max single-stock, KOSDAQ, sector, cash buffer, illiquidity, and severe-risk constraints.",
            "Recommendations are portfolio review actions only; no order placement API is created.",
        ),
        risk_flags=tuple(["stale_optimizer_inputs"] if stale else [])
        + tuple(["portfolio_action_gate_blocked"] if not action_eligible else [])
        + tuple(["optimizer_alpha_coverage_missing"] if alpha_coverage_missing else [])
        + tuple(["optimizer_rejections_active"] if rejected else [])
        + tuple(["alerts_active"] if alerts else []),
        stale_after_minutes=24 * 60,
        recommendation_rows=recommendations,
        rejected_candidates=rejected,
        alerts=alerts,
        stress_scenarios=_stress_scenarios(recommendations, now=now, fallback=fallback),
        total_portfolio_value=total_value,
        cash_ratio=cash,
        target_cash_ratio=target_cash_ratio,
        max_single_stock_weight=constraints.max_single_stock_weight,
        max_kosdaq_single_stock_weight=constraints.max_kosdaq_single_stock_weight,
        max_sector_weight=constraints.max_sector_weight,
        latest_source_at=alpha_state.latest_source_at,
    )


def portfolio_optimizer_api_response(state: PortfolioOptimizerAlertCenterState) -> dict[str, Any]:
    payload = state.to_dict()
    payload["moduleId"] = payload.pop("module_id")
    payload["dataPoints"] = payload.pop("data_points")
    payload["recommendationRows"] = payload.pop("recommendation_rows")
    payload["rejectedCandidates"] = payload.pop("rejected_candidates")
    payload["stressScenarios"] = payload.pop("stress_scenarios")
    payload["totalPortfolioValue"] = payload.pop("total_portfolio_value")
    payload["cashRatio"] = payload.pop("cash_ratio")
    payload["targetCashRatio"] = payload.pop("target_cash_ratio")
    payload["maxSingleStockWeight"] = payload.pop("max_single_stock_weight")
    payload["maxKosdaqSingleStockWeight"] = payload.pop("max_kosdaq_single_stock_weight")
    payload["maxSectorWeight"] = payload.pop("max_sector_weight")
    payload["latestSourceAt"] = payload.pop("latest_source_at")
    payload["apiPath"] = payload.pop("optimizer_api_path")
    payload.pop("alerts_api_path", None)
    return payload


def alert_center_api_response(state: PortfolioOptimizerAlertCenterState) -> dict[str, Any]:
    return {
        "moduleId": state.module_id,
        "apiPath": state.alerts_api_path,
        "alerts": [item.to_dict() for item in state.alerts],
        "status": state.status,
        "latestSourceAt": state.latest_source_at,
        "staleAfterMinutes": state.stale_after_minutes,
    }
