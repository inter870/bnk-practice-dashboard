from __future__ import annotations

from typing import Any

from .config import DEFAULT_MAX_SINGLE_STOCK_WEIGHT, DEFAULT_MAX_SECTOR_WEIGHT
from .factor_engine import (
    calculateATR,
    calculateLiquidityScore,
    calculateMaxDrawdown,
    calculateRiskPenalty,
    calculateShortSqueezeRisk,
    calculateSuggestedWeight,
    calculateVolatility,
    clamp,
    safeNumber,
)


def evaluateKoreaRisk(
    price_series: list[Any],
    fundamentals: Any,
    supply_demand: list[Any],
    events: list[Any],
    risk_flags: list[str],
    portfolio_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    volatility = calculateVolatility(price_series, 60)
    max_drawdown = calculateMaxDrawdown(price_series)
    atr = calculateATR(price_series, 14)
    liquidity = calculateLiquidityScore(price_series)
    short_risk = calculateShortSqueezeRisk(supply_demand, price_series)
    penalty = calculateRiskPenalty(price_series, fundamentals, risk_flags)
    latest = safeNumber(getattr(price_series[-1], "close", None)) if price_series else None
    atr_pct = None if latest in (None, 0) or atr is None else atr / latest
    level = "low"
    if penalty >= 30 or short_risk >= 75 or "negative_disclosure" in risk_flags:
        level = "high"
    elif penalty >= 16 or short_risk >= 55:
        level = "medium"
    stop_review_price = None if latest is None else latest * (1 - clamp((atr_pct or 0.05) * 2.4, 0.06, 0.18))
    invalidation_price = None if latest is None else latest * (1 - clamp((atr_pct or 0.05) * 3.4, 0.10, 0.25))
    return {
        "volatility": volatility,
        "max_drawdown": max_drawdown,
        "atr": atr,
        "atr_pct": atr_pct,
        "liquidity_score": liquidity,
        "short_squeeze_risk": short_risk,
        "risk_penalty": penalty,
        "risk_level": level,
        "stop_review_price": stop_review_price,
        "invalidation_price": invalidation_price,
        "downside_scenario": max_drawdown if max_drawdown < 0 else -(atr_pct or 0.05) * 3,
    }


def calculateRiskAdjustedPositionSize(
    score: float,
    risk_metrics: dict[str, Any],
    market_regime: str,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    constraints = constraints or {}
    max_single = safeNumber(constraints.get("max_single_stock_weight"), DEFAULT_MAX_SINGLE_STOCK_WEIGHT) or DEFAULT_MAX_SINGLE_STOCK_WEIGHT
    liquidity = safeNumber(risk_metrics.get("liquidity_score"), 50) or 50.0
    risk_score = 100 - (safeNumber(risk_metrics.get("risk_penalty"), 0) or 0)
    suggested = calculateSuggestedWeight(
        score,
        risk_score,
        liquidity,
        {"max_single_stock_weight": max_single},
    )
    cap_reason = "점수·리스크 기반"
    if market_regime == "panic":
        suggested *= 0.35
        cap_reason = "패닉 국면 비중 축소"
    elif market_regime == "risk_off":
        suggested *= 0.65
        cap_reason = "위험회피 국면 감산"
    if risk_metrics.get("risk_level") == "high":
        suggested *= 0.35
        cap_reason = "고위험 플래그 감산"
    if liquidity < 45:
        suggested *= 0.50
        cap_reason = "유동성 부족 감산"
    return {
        "suggested_weight": clamp(suggested, 0.0, max_single),
        "max_suggested_weight": max_single,
        "cap_reason": cap_reason,
        "portfolio_impact": clamp(suggested * risk_score / 100, 0.0, max_single),
    }


def portfolioRiskSummary(scores: list[Any]) -> dict[str, Any]:
    if not scores:
        return {"risk_alerts": ["후보 데이터 없음"], "high_risk_count": 0, "avg_confidence": None}
    high_risk = [row for row in scores if getattr(row, "risk_flags", None)]
    avg_conf = sum(float(getattr(row, "confidence", 0.0) or 0.0) for row in scores) / len(scores)
    sector_weights: dict[str, int] = {}
    for row in scores:
        sector = getattr(row, "sector", None) or "미분류"
        sector_weights[sector] = sector_weights.get(sector, 0) + 1
    alerts: list[str] = []
    if high_risk:
        alerts.append(f"리스크 플래그 보유 후보 {len(high_risk)}개")
    if max(sector_weights.values(), default=0) / max(len(scores), 1) > DEFAULT_MAX_SECTOR_WEIGHT:
        alerts.append("섹터 쏠림 가능성")
    if avg_conf < 0.55:
        alerts.append("예측 신뢰도 낮음")
    return {
        "risk_alerts": alerts or ["중대한 리스크 없음"],
        "high_risk_count": len(high_risk),
        "avg_confidence": avg_conf,
        "sector_counts": sector_weights,
    }
