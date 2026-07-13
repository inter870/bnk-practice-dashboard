from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class RegimeState:
    label: str
    score: float
    confidence: float
    multipliers: Mapping[str, float]
    reasons: tuple[str, ...]
    version: str = "kr-alpha-regime-v1"


def classify_regime(
    *,
    market_trend: float | None,
    volatility_pressure: float | None,
    fx_pressure: float | None,
    liquidity_support: float | None,
) -> RegimeState:
    inputs = [value for value in (market_trend, volatility_pressure, fx_pressure, liquidity_support) if value is not None]
    if len(inputs) < 3:
        return RegimeState("INSUFFICIENT_DATA", 0.0, len(inputs) / 4.0, {}, ("regime_inputs_missing",))
    score = (
        0.40 * float(market_trend)
        - 0.25 * float(volatility_pressure)
        - 0.20 * float(fx_pressure)
        + 0.15 * float(liquidity_support)
    )
    label = "RISK_ON" if score >= 0.25 else ("RISK_OFF" if score <= -0.25 else "NEUTRAL")
    multipliers = {
        "medium_momentum": 1.20 if label == "RISK_ON" else (0.70 if label == "RISK_OFF" else 1.0),
        "low_vol_beta": 1.25 if label == "RISK_OFF" else 1.0,
        "liquidity_impact": 1.20 if label == "RISK_OFF" else 1.0,
    }
    reasons = tuple(
        reason for reason, present in (
            ("market_trend_positive", float(market_trend) > 0),
            ("volatility_pressure", float(volatility_pressure) > 0.5),
            ("fx_pressure", float(fx_pressure) > 0.5),
            ("liquidity_support", float(liquidity_support) > 0),
        ) if present
    )
    return RegimeState(label, score, 1.0, multipliers, reasons)
