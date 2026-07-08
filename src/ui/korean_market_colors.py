from __future__ import annotations

import math
from typing import Any


MARKET_UP = "#FF4D4F"
MARKET_UP_STRONG = "#FF1F3D"
MARKET_DOWN = "#3B82F6"
MARKET_DOWN_STRONG = "#2563EB"
MARKET_FLAT = "#CBD5E1"
MARKET_NEUTRAL = "#94A3B8"

RISK_CRITICAL = "#F97316"
RISK_WARNING = "#FCD34D"
RISK_INFO = "#38BDF8"
SYSTEM_ERROR = "#FB7185"
DISABLED = "#64748B"


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def getKoreanMarketDirection(value: Any, *, zero_threshold: float = 1e-12) -> str:
    """Return the Korean market direction bucket for a numeric value."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"up", "positive", "gain", "buy", "net_buy", "accumulation"}:
            return "up"
        if normalized in {"down", "negative", "loss", "sell", "net_sell", "distribution"}:
            return "down"
        if normalized in {"flat", "neutral", "zero", "unchanged"}:
            return "flat"
    number = _to_float(value)
    if number is None:
        return "unavailable"
    if number > zero_threshold:
        return "up"
    if number < -zero_threshold:
        return "down"
    return "flat"


def getKoreanMarketColorToken(value: Any, *, zero_threshold: float = 1e-12) -> str:
    direction = getKoreanMarketDirection(value, zero_threshold=zero_threshold)
    return {
        "up": MARKET_UP,
        "down": MARKET_DOWN,
        "flat": MARKET_FLAT,
    }.get(direction, MARKET_NEUTRAL)


def getKoreanMarketColorClass(value: Any, *, zero_threshold: float = 1e-12) -> str:
    direction = getKoreanMarketDirection(value, zero_threshold=zero_threshold)
    return {
        "up": "market-up",
        "down": "market-down",
        "flat": "market-flat",
    }.get(direction, "market-neutral")


def getKoreanMarketBadgeClass(value: Any, *, zero_threshold: float = 1e-12) -> str:
    direction = getKoreanMarketDirection(value, zero_threshold=zero_threshold)
    return {
        "up": "market-badge-up",
        "down": "market-badge-down",
        "flat": "market-badge-flat",
    }.get(direction, "market-badge-neutral")


def getReturnColorClass(value: Any) -> str:
    return getKoreanMarketColorClass(value)


def getFlowColorClass(value: Any, *, risk_context: bool = False) -> str:
    if risk_context:
        return "risk-warning"
    return getKoreanMarketColorClass(value)


def getRiskSeverityColorClass(severity: Any) -> str:
    normalized = str(severity or "").strip().lower()
    if normalized in {"critical", "high", "severe", "error", "danger", "risk"}:
        return "risk-critical"
    if normalized in {"warning", "warn", "stale", "medium", "caution"}:
        return "risk-warning"
    if normalized in {"info", "low", "normal", "ok", "ready"}:
        return "risk-info"
    return "risk-neutral"


def getRatingColorClass(rating: Any) -> str:
    normalized = str(rating or "").strip().upper()
    if normalized in {"STRONG_BUY_CANDIDATE", "BUY_CANDIDATE"}:
        return "market-up"
    if normalized in {"WATCH", "HOLD"}:
        return "market-flat"
    if normalized == "AVOID":
        return "risk-warning"
    if normalized == "HIGH_RISK_EXCLUDE":
        return "risk-critical"
    return "market-neutral"


def getActionColorClass(action: Any) -> str:
    normalized = str(action or "").strip().upper()
    if normalized in {"BUY", "ADD"}:
        return "market-up"
    if normalized in {"TRIM", "SELL"}:
        return "market-down"
    if normalized in {"AVOID", "EXCLUDE"}:
        return "risk-critical"
    if normalized == "HOLD":
        return "market-flat"
    return "market-neutral"


def getChartSeriesColor(value_or_kind: Any, *, context: str = "return") -> str:
    normalized = str(value_or_kind or "").strip().lower()
    if context in {"risk", "severity"}:
        return {
            "critical": RISK_CRITICAL,
            "high": RISK_CRITICAL,
            "warning": RISK_WARNING,
            "warn": RISK_WARNING,
            "error": SYSTEM_ERROR,
            "info": RISK_INFO,
        }.get(normalized, MARKET_NEUTRAL)
    if normalized in {"up", "positive", "gain", "net_buy", "buy", "accumulation"}:
        return MARKET_UP
    if normalized in {"down", "negative", "loss", "net_sell", "sell", "distribution"}:
        return MARKET_DOWN
    if normalized in {"flat", "neutral", "unchanged"}:
        return MARKET_FLAT
    return getKoreanMarketColorToken(value_or_kind)
