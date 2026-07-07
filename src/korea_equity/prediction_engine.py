from __future__ import annotations

from typing import Any

from .factor_engine import clamp, safeNumber


def estimateForwardReturnRange(score: Any, volatility: Any, marketRegime: str) -> dict[str, float]:
    score_value = safeNumber(score, 50) or 50.0
    vol = safeNumber(volatility, 0.25) or 0.25
    regime_adj = {"risk_on": 0.012, "recovery": 0.008, "neutral": 0.0, "risk_off": -0.014, "panic": -0.028}.get(str(marketRegime), 0.0)
    midpoint_1m = (score_value - 50) / 100 * 0.08 + regime_adj - vol * 0.025
    width = clamp(vol * 0.42, 0.04, 0.20)
    midpoint_3m = midpoint_1m * 2.4
    return {
        "expected_return_1m": clamp(midpoint_1m, -0.18, 0.22),
        "expected_return_3m": clamp(midpoint_3m, -0.30, 0.42),
        "range_1m_low": clamp(midpoint_1m - width * 0.5, -0.35, 0.35),
        "range_1m_high": clamp(midpoint_1m + width * 0.5, -0.35, 0.35),
        "range_3m_low": clamp(midpoint_3m - width, -0.55, 0.65),
        "range_3m_high": clamp(midpoint_3m + width, -0.55, 0.65),
    }


def estimateExpectedAlpha(score: Any, marketRegime: str) -> dict[str, float]:
    score_value = safeNumber(score, 50) or 50.0
    regime_adj = {"risk_on": 0.004, "recovery": 0.006, "neutral": 0.0, "risk_off": -0.006, "panic": -0.012}.get(str(marketRegime), 0.0)
    alpha_1m = (score_value - 50) / 100 * 0.055 + regime_adj
    return {
        "expected_excess_return_1m": clamp(alpha_1m, -0.12, 0.16),
        "expected_excess_return_3m": clamp(alpha_1m * 2.3, -0.22, 0.30),
    }


def estimateOutperformanceProbability(score: Any, confidence: Any, marketRegime: str) -> dict[str, float]:
    score_value = safeNumber(score, 50) or 50.0
    conf = safeNumber(confidence, 0.5) or 0.5
    regime_adj = {"risk_on": 0.04, "recovery": 0.03, "neutral": 0.0, "risk_off": -0.05, "panic": -0.10}.get(str(marketRegime), 0.0)
    base = 0.48 + (score_value - 50) / 100 * 0.44 + (conf - 0.5) * 0.20 + regime_adj
    return {
        "probability_outperform_1m": clamp(base, 0.05, 0.95),
        "probability_outperform_3m": clamp(base + 0.03 if score_value >= 65 else base - 0.02, 0.05, 0.95),
    }


def calculatePredictionConfidence(
    data_quality_flags: list[str] | None,
    risk_flags: list[str] | None,
    factor_scores: dict[str, float],
    marketRegime: str,
    history_length: int,
) -> float:
    confidence = 0.62
    if history_length >= 220:
        confidence += 0.08
    elif history_length < 80:
        confidence -= 0.14
    confidence -= min(len(data_quality_flags or []) * 0.08, 0.24)
    confidence -= min(len(risk_flags or []) * 0.05, 0.20)
    if marketRegime in {"risk_off", "panic"}:
        confidence -= 0.08 if marketRegime == "risk_off" else 0.16
    values = [safeNumber(value) for value in factor_scores.values()]
    clean = [value for value in values if value is not None]
    if clean:
        spread = max(clean) - min(clean)
        if spread < 28:
            confidence += 0.06
        elif spread > 58:
            confidence -= 0.10
        if sum(value >= 65 for value in clean) >= 4:
            confidence += 0.05
    return clamp(confidence, 0.15, 0.88)


def calibrateScoreToHistoricalReturns(score: Any) -> float:
    score_value = safeNumber(score, 50) or 50.0
    return clamp((score_value - 50) / 100 * 0.09, -0.08, 0.12)


def calculatePredictionUncertainty(volatility: Any, confidence: Any) -> float:
    vol = safeNumber(volatility, 0.25) or 0.25
    conf = safeNumber(confidence, 0.5) or 0.5
    return clamp(vol * (1.15 - conf), 0.03, 0.35)


def explainPredictionDrivers(factor_scores: dict[str, float], risk_flags: list[str] | None) -> list[str]:
    labels = {
        "momentum": "모멘텀",
        "quality": "퀄리티",
        "value": "밸류에이션",
        "earnings_revision": "실적 추정",
        "supply_demand": "수급",
        "event_catalyst": "이벤트",
        "value_up": "밸류업",
        "liquidity": "유동성",
    }
    ranked = sorted(
        ((key, safeNumber(value, 0) or 0.0) for key, value in factor_scores.items() if key in labels),
        key=lambda item: item[1],
        reverse=True,
    )
    drivers = [f"{labels[key]} {value:.0f}점" for key, value in ranked[:3]]
    if risk_flags:
        drivers.append(f"리스크 플래그 {len(risk_flags)}개")
    return drivers
