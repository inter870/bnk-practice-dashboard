from __future__ import annotations

from dataclasses import replace
from typing import Any

from .config import MODEL_VERSION
from .factor_engine import calculateKoreaCompositeAlphaScore, calculateVolatility, classifyRecommendationGrade, generateKoreaStockRationale, safeNumber
from .models import FactorScores, KoreaFactorScore, KoreaFundamentalSnapshot, KoreaTicker
from .prediction_engine import calculatePredictionConfidence, estimateExpectedAlpha, estimateForwardReturnRange, estimateOutperformanceProbability, explainPredictionDrivers
from .risk_engine import calculateRiskAdjustedPositionSize, evaluateKoreaRisk


def buildKoreaFactorScore(
    ticker: KoreaTicker,
    price_series: list[Any],
    benchmark_series: list[Any],
    fundamentals: KoreaFundamentalSnapshot,
    supply_demand: list[Any],
    events: list[Any],
    market_status: Any,
    sector_peers: list[Any] | None = None,
) -> KoreaFactorScore:
    previous = replace(
        fundamentals,
        operating_profit=(fundamentals.operating_profit or 0) * 0.88,
        revenue=(fundamentals.revenue or 0) * 0.94,
    )
    inputs = {
        "price_series": price_series,
        "benchmark_series": benchmark_series,
        "fundamentals": fundamentals,
        "previous_fundamentals": previous,
        "supply_demand": supply_demand,
        "events": events,
        "sector_peers": sector_peers or [],
    }
    breakdown = calculateKoreaCompositeAlphaScore(inputs, market_status)
    factor_map = breakdown["factor_scores"]
    risk_flags = list(breakdown["risk_flags"])
    data_quality_flags = []
    if len(price_series) < 120:
        data_quality_flags.append("price_history_short")
    if fundamentals.per is None or fundamentals.pbr is None:
        data_quality_flags.append("valuation_missing")
    volatility = calculateVolatility(price_series, 60)
    confidence = calculatePredictionConfidence(
        data_quality_flags,
        risk_flags,
        factor_map,
        getattr(market_status, "regime", "neutral"),
        len(price_series),
    )
    risk_metrics = evaluateKoreaRisk(price_series, fundamentals, supply_demand, events, risk_flags)
    position = calculateRiskAdjustedPositionSize(
        breakdown["total_score"],
        risk_metrics,
        getattr(market_status, "regime", "neutral"),
    )
    expected = estimateForwardReturnRange(breakdown["total_score"], volatility, getattr(market_status, "regime", "neutral"))
    alpha = estimateExpectedAlpha(breakdown["total_score"], getattr(market_status, "regime", "neutral"))
    probability = estimateOutperformanceProbability(breakdown["total_score"], confidence, getattr(market_status, "regime", "neutral"))
    grade = classifyRecommendationGrade(breakdown["total_score"], confidence, risk_flags)
    positives, negatives = generateKoreaStockRationale(breakdown)
    positives.extend(explainPredictionDrivers(factor_map, [])[:2])
    if risk_flags:
        negatives.extend(f"리스크 플래그: {flag}" for flag in risk_flags[:2])
    last_close = safeNumber(getattr(price_series[-1], "close", None)) if price_series else None
    return KoreaFactorScore(
        code=ticker.code,
        name=ticker.name,
        date=getattr(market_status, "date", ""),
        market=ticker.market,
        sector=ticker.sector,
        total_score=round(breakdown["total_score"], 2),
        recommendation_grade=grade,
        confidence=round(confidence, 4),
        expected_return_1m=expected["expected_return_1m"],
        expected_return_3m=expected["expected_return_3m"],
        expected_excess_return_1m=alpha["expected_excess_return_1m"],
        expected_excess_return_3m=alpha["expected_excess_return_3m"],
        probability_outperform_1m=probability["probability_outperform_1m"],
        probability_outperform_3m=probability["probability_outperform_3m"],
        downside_risk=risk_metrics["downside_scenario"],
        suggested_weight=position["suggested_weight"],
        max_suggested_weight=position["max_suggested_weight"],
        stop_review_price=risk_metrics["stop_review_price"],
        invalidation_price=risk_metrics["invalidation_price"],
        target_review_range_low=None if last_close is None else last_close * (1 + expected["range_3m_low"]),
        target_review_range_high=None if last_close is None else last_close * (1 + expected["range_3m_high"]),
        factor_scores=FactorScores(
            value=factor_map["value"],
            quality=factor_map["quality"],
            momentum=factor_map["momentum"],
            earnings_revision=factor_map["earnings_revision"],
            supply_demand=factor_map["supply_demand"],
            event_catalyst=factor_map["event_catalyst"],
            value_up=factor_map["value_up"],
            liquidity=factor_map["liquidity"],
            risk=factor_map["risk"],
        ),
        positive_reasons=positives[:6],
        negative_reasons=negatives[:6],
        risk_flags=risk_flags,
        data_quality_flags=data_quality_flags,
        model_version=MODEL_VERSION,
        last_updated=getattr(market_status, "date", ""),
    )


def rankKoreaAlphaCandidates(scores: list[KoreaFactorScore], limit: int = 20) -> list[KoreaFactorScore]:
    return sorted(
        scores,
        key=lambda row: (row.total_score, row.confidence, row.expected_excess_return_3m or -1),
        reverse=True,
    )[:limit]
