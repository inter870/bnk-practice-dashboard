from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any, Iterable

from .config import FACTOR_WEIGHTS, SEVERE_RISK_FLAGS


def safeNumber(value: Any, fallback: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if math.isfinite(number) else fallback


def clamp(value: Any, min_value: float, max_value: float) -> float:
    number = safeNumber(value, min_value)
    if number is None:
        return min_value
    return max(min_value, min(max_value, number))


def _value(obj: Any, *names: str) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def _close(point: Any) -> float | None:
    if isinstance(point, (int, float)):
        return safeNumber(point)
    return safeNumber(_value(point, "close", "value"))


def _high(point: Any) -> float | None:
    return safeNumber(_value(point, "high")) or _close(point)


def _low(point: Any) -> float | None:
    return safeNumber(_value(point, "low")) or _close(point)


def _trading_value(point: Any) -> float | None:
    return safeNumber(_value(point, "trading_value", "tradingValue"))


def _sorted_series(price_series: Iterable[Any]) -> list[Any]:
    rows = list(price_series or [])
    return sorted(rows, key=lambda row: str(_value(row, "date") or ""))


def _closes(price_series: Iterable[Any]) -> list[float]:
    values = [_close(point) for point in _sorted_series(price_series)]
    return [float(value) for value in values if value is not None]


def winsorize(values: Iterable[Any], lowerPercentile: float = 0.05, upperPercentile: float = 0.95) -> list[float]:
    clean = sorted(float(v) for v in (safeNumber(value) for value in values) if v is not None)
    if not clean:
        return []
    lo_idx = int(clamp(lowerPercentile, 0, 1) * (len(clean) - 1))
    hi_idx = int(clamp(upperPercentile, 0, 1) * (len(clean) - 1))
    lo, hi = clean[lo_idx], clean[hi_idx]
    return [clamp(value, lo, hi) for value in clean]


def robustZScore(value: Any, distribution: Iterable[Any]) -> float:
    number = safeNumber(value)
    clean = sorted(float(v) for v in (safeNumber(item) for item in distribution) if v is not None)
    if number is None or not clean:
        return 0.0
    median = clean[len(clean) // 2]
    deviations = sorted(abs(item - median) for item in clean)
    mad = deviations[len(deviations) // 2] or 1e-9
    return (number - median) / (1.4826 * mad)


def normalizeBySector(values: dict[str, float]) -> dict[str, float]:
    clean = [v for v in values.values() if safeNumber(v) is not None]
    if not clean:
        return {key: 50.0 for key in values}
    avg = mean(clean)
    sd = pstdev(clean) or 1.0
    return {key: clamp(50 + ((value - avg) / sd) * 12, 0, 100) for key, value in values.items()}


def calculateMovingAverage(priceSeries: Iterable[Any], window: int) -> float | None:
    closes = _closes(priceSeries)
    if window <= 0 or len(closes) < window:
        return None
    return mean(closes[-window:])


def calculateReturn(priceSeries: Iterable[Any], lookbackDays: int) -> float | None:
    closes = _closes(priceSeries)
    if lookbackDays <= 0 or len(closes) <= lookbackDays:
        return None
    start = closes[-lookbackDays - 1]
    end = closes[-1]
    return None if start == 0 else end / start - 1


def calculateRelativeStrength(stockSeries: Iterable[Any], benchmarkSeries: Iterable[Any], lookbackDays: int) -> float | None:
    stock_return = calculateReturn(stockSeries, lookbackDays)
    benchmark_return = calculateReturn(benchmarkSeries, lookbackDays)
    if stock_return is None or benchmark_return is None:
        return None
    return stock_return - benchmark_return


def calculateMomentumScore(stockSeries: Iterable[Any], benchmarkSeries: Iterable[Any]) -> float:
    score = 50.0
    for lookback, weight in [(20, 18), (60, 22), (120, 18), (200, 14)]:
        value = calculateReturn(stockSeries, lookback)
        if value is not None:
            score += clamp(value * 100, -15, 15) * weight / 15
    for lookback, weight in [(60, 16), (120, 12)]:
        rs = calculateRelativeStrength(stockSeries, benchmarkSeries, lookback)
        if rs is not None:
            score += clamp(rs * 100, -10, 10) * weight / 10
    closes = _closes(stockSeries)
    if closes:
        last = closes[-1]
        for window in (20, 60, 200):
            ma = calculateMovingAverage(stockSeries, window)
            if ma:
                score += 4 if last >= ma else -4
    return clamp(score, 0, 100)


def calculateVolatility(priceSeries: Iterable[Any], window: int = 60) -> float | None:
    closes = _closes(priceSeries)
    if len(closes) < max(3, window):
        return None
    returns = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes)) if closes[i - 1] != 0]
    sample = returns[-window:]
    return pstdev(sample) * math.sqrt(252) if len(sample) >= 2 else None


def calculateMaxDrawdown(priceSeries: Iterable[Any]) -> float:
    closes = _closes(priceSeries)
    if not closes:
        return 0.0
    peak = closes[0]
    max_dd = 0.0
    for close in closes:
        peak = max(peak, close)
        if peak:
            max_dd = min(max_dd, close / peak - 1)
    return max_dd


def calculateATR(priceSeries: Iterable[Any], window: int = 14) -> float | None:
    rows = _sorted_series(priceSeries)
    if len(rows) < window + 1:
        return None
    true_ranges: list[float] = []
    prev_close = _close(rows[0])
    for point in rows[1:]:
        high = _high(point)
        low = _low(point)
        close = _close(point)
        if high is None or low is None or prev_close is None:
            prev_close = close
            continue
        true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
        prev_close = close
    if len(true_ranges) < window:
        return None
    return mean(true_ranges[-window:])


def calculateLiquidityScore(priceSeries: Iterable[Any]) -> float:
    rows = _sorted_series(priceSeries)
    values = [_trading_value(point) for point in rows[-60:]]
    clean = [value for value in values if value is not None]
    if not clean:
        return 20.0
    avg_value = mean(clean)
    if avg_value >= 100_000_000_000:
        return 95.0
    if avg_value >= 30_000_000_000:
        return 82.0
    if avg_value >= 10_000_000_000:
        return 68.0
    if avg_value >= 3_000_000_000:
        return 48.0
    return 25.0


def calculateValueScore(fundamentals: Any, sectorPeers: Iterable[Any] | None = None) -> float:
    per = safeNumber(_value(fundamentals, "per"))
    pbr = safeNumber(_value(fundamentals, "pbr"))
    dividend_yield = safeNumber(_value(fundamentals, "dividend_yield", "dividendYield")) or 0.0
    roe = safeNumber(_value(fundamentals, "roe")) or 0.0
    score = 50.0
    if per is not None:
        score += clamp((24 - per) * 2.0, -28, 28)
    if pbr is not None:
        score += clamp((1.5 - pbr) * 16.0, -24, 24)
    score += clamp(dividend_yield * 400, 0, 20)
    if pbr is not None and roe > 0.08 and pbr < 1.0:
        score += 10
    return clamp(score, 0, 100)


def calculateQualityScore(fundamentals: Any, history: Iterable[Any] | None = None) -> float:
    roe = safeNumber(_value(fundamentals, "roe"))
    margin = safeNumber(_value(fundamentals, "operating_margin", "operatingMargin"))
    debt = safeNumber(_value(fundamentals, "debt_to_equity", "debtToEquity"))
    fcf = safeNumber(_value(fundamentals, "free_cash_flow", "freeCashFlow"))
    score = 50.0
    if roe is not None:
        score += clamp((roe - 0.06) * 220, -18, 28)
    if margin is not None:
        score += clamp((margin - 0.06) * 180, -14, 24)
    if debt is not None:
        score += clamp((0.85 - debt) * 22, -18, 16)
    if fcf is not None:
        score += 10 if fcf > 0 else -16
    return clamp(score, 0, 100)


def calculateEarningsRevisionScore(current: Any, previous: Any | None = None) -> float:
    current_op = safeNumber(_value(current, "operating_profit", "operatingProfit"))
    prev_op = safeNumber(_value(previous, "operating_profit", "operatingProfit")) if previous is not None else None
    revenue = safeNumber(_value(current, "revenue"))
    score = 52.0
    if current_op is not None and prev_op not in (None, 0):
        score += clamp((current_op / prev_op - 1) * 110, -28, 28)
    elif current_op is not None:
        score += 10 if current_op > 0 else -20
    if revenue is not None and revenue > 0:
        score += 4
    return clamp(score, 0, 100)


def _sum_flow(series: Iterable[Any], field: str, days: int = 20) -> float:
    rows = list(series or [])[-days:]
    return sum(safeNumber(_value(row, field)) or 0.0 for row in rows)


def calculateForeignFlowScore(supplyDemandSeries: Iterable[Any]) -> float:
    flow = _sum_flow(supplyDemandSeries, "foreign_net_buy", 20)
    return clamp(50 + flow / 25_000_000_000 * 35, 0, 100)


def calculateInstitutionFlowScore(supplyDemandSeries: Iterable[Any]) -> float:
    flow = _sum_flow(supplyDemandSeries, "institution_net_buy", 20)
    return clamp(50 + flow / 20_000_000_000 * 35, 0, 100)


def calculatePensionFlowScore(supplyDemandSeries: Iterable[Any]) -> float:
    flow = _sum_flow(supplyDemandSeries, "pension_net_buy", 40)
    return clamp(50 + flow / 12_000_000_000 * 30, 0, 100)


def calculateSupplyDemandScore(supplyDemandSeries: Iterable[Any]) -> float:
    foreign = calculateForeignFlowScore(supplyDemandSeries)
    institution = calculateInstitutionFlowScore(supplyDemandSeries)
    pension = calculatePensionFlowScore(supplyDemandSeries)
    return clamp(foreign * 0.42 + institution * 0.38 + pension * 0.20, 0, 100)


def calculateShortSqueezeRisk(supplyDemandSeries: Iterable[Any], priceSeries: Iterable[Any]) -> float:
    rows = list(supplyDemandSeries or [])
    ratio = safeNumber(_value(rows[-1], "short_balance_ratio", "shortBalanceRatio")) if rows else None
    momentum = calculateReturn(priceSeries, 20) or 0.0
    if ratio is None:
        return 20.0
    return clamp(ratio * 1800 + max(momentum, 0) * 80, 0, 100)


def calculateDisclosureEventScore(events: Iterable[Any]) -> float:
    score = 50.0
    for event in events or []:
        sentiment = str(_value(event, "sentiment") or "unknown")
        importance = safeNumber(_value(event, "importance")) or 40.0
        category = str(_value(event, "category") or "")
        if sentiment == "positive":
            score += importance * 0.18
        elif sentiment == "negative":
            score -= importance * 0.28
        if category in {"buyback", "dividend", "value_up", "major_contract"}:
            score += 5
        if category in {"capital_increase", "convertible_bond", "litigation", "management_issue"}:
            score -= 10
    return clamp(score, 0, 100)


def calculateValueUpScore(fundamentals: Any, events: Iterable[Any]) -> float:
    pbr = safeNumber(_value(fundamentals, "pbr"))
    roe = safeNumber(_value(fundamentals, "roe")) or 0.0
    dividend_yield = safeNumber(_value(fundamentals, "dividend_yield", "dividendYield")) or 0.0
    score = 42.0
    if pbr is not None and pbr < 1.0:
        score += 18
    if roe >= 0.08:
        score += 14
    if dividend_yield >= 0.035:
        score += 12
    for event in events or []:
        if str(_value(event, "category")) in {"value_up", "buyback", "dividend", "treasury_stock"}:
            score += 14
    return clamp(score, 0, 100)


def calculateRiskPenalty(priceSeries: Iterable[Any], fundamentals: Any, issueFlags: Iterable[str] | None = None) -> float:
    flags = set(issueFlags or [])
    volatility = calculateVolatility(priceSeries, 60)
    drawdown = calculateMaxDrawdown(priceSeries)
    liquidity = calculateLiquidityScore(priceSeries)
    debt = safeNumber(_value(fundamentals, "debt_to_equity", "debtToEquity")) or 0.0
    penalty = 0.0
    if volatility is not None:
        penalty += clamp((volatility - 0.25) * 55, 0, 22)
    penalty += clamp(abs(min(drawdown, 0)) * 70, 0, 18)
    if liquidity < 45:
        penalty += 12
    if debt > 1.0:
        penalty += clamp((debt - 1.0) * 18, 0, 12)
    if flags & SEVERE_RISK_FLAGS:
        penalty += 32
    else:
        penalty += min(len(flags) * 4, 16)
    return clamp(penalty, 0, 70)


def calculateSectorRelativeScore(stock: Any, sectorPeers: Iterable[Any]) -> float:
    peers = list(sectorPeers or [])
    if not peers:
        return 50.0
    per = safeNumber(_value(stock, "per"))
    peer_pers = [safeNumber(_value(peer, "per")) for peer in peers]
    clean = [value for value in peer_pers if value is not None]
    if per is None or not clean:
        return 50.0
    return clamp(50 - robustZScore(per, clean) * 12, 0, 100)


def generateKoreaRiskFlags(inputs: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    price_series = inputs.get("price_series") or []
    fundamentals = inputs.get("fundamentals")
    events = inputs.get("events") or []
    liquidity = calculateLiquidityScore(price_series)
    volatility = calculateVolatility(price_series, 60)
    drawdown = calculateMaxDrawdown(price_series)
    debt = safeNumber(_value(fundamentals, "debt_to_equity", "debtToEquity")) or 0.0
    if not price_series:
        flags.append("missing_core_price_data")
    if liquidity < 35:
        flags.append("insufficient_liquidity")
    if volatility is not None and volatility > 0.42:
        flags.append("high_volatility")
    if drawdown < -0.28:
        flags.append("large_drawdown")
    if debt > 1.1:
        flags.append("debt_risk")
    if any(str(_value(event, "sentiment")) == "negative" and (safeNumber(_value(event, "importance")) or 0) >= 70 for event in events):
        flags.append("negative_disclosure")
    return flags


def calculateKoreaCompositeAlphaScore(inputs: dict[str, Any], marketStatus: Any) -> dict[str, Any]:
    price_series = inputs.get("price_series") or []
    benchmark_series = inputs.get("benchmark_series") or []
    fundamentals = inputs.get("fundamentals")
    previous_fundamentals = inputs.get("previous_fundamentals")
    supply = inputs.get("supply_demand") or []
    events = inputs.get("events") or []
    value = calculateValueScore(fundamentals, inputs.get("sector_peers"))
    quality = calculateQualityScore(fundamentals, price_series)
    momentum = calculateMomentumScore(price_series, benchmark_series)
    earnings = calculateEarningsRevisionScore(fundamentals, previous_fundamentals)
    supply_demand = calculateSupplyDemandScore(supply)
    event = calculateDisclosureEventScore(events)
    value_up = calculateValueUpScore(fundamentals, events)
    liquidity = calculateLiquidityScore(price_series)
    risk_flags = generateKoreaRiskFlags(inputs)
    penalty = calculateRiskPenalty(price_series, fundamentals, risk_flags)
    weights = dict(FACTOR_WEIGHTS)
    regime = str(_value(marketStatus, "regime") or "neutral")
    if regime == "risk_on":
        weights["momentum"] += 0.04
        weights["earnings_revision"] += 0.02
        weights["value"] -= 0.03
        weights["quality"] -= 0.03
    elif regime in {"risk_off", "panic"}:
        weights["quality"] += 0.04
        weights["value"] += 0.03
        weights["liquidity"] += 0.02
        weights["momentum"] -= 0.05
        weights["event_catalyst"] -= 0.04
    factor_map = {
        "momentum": momentum,
        "quality": quality,
        "value": value,
        "earnings_revision": earnings,
        "supply_demand": supply_demand,
        "event_catalyst": event,
        "value_up": value_up,
        "liquidity": liquidity,
    }
    total_weight = sum(max(w, 0) for w in weights.values()) or 1.0
    raw = sum(factor_map[key] * max(weights[key], 0) for key in factor_map) / total_weight
    score = clamp(raw - penalty, 0, 100)
    return {
        "total_score": score,
        "raw_score": raw,
        "risk_penalty": penalty,
        "factor_scores": factor_map | {"risk": 100 - penalty},
        "risk_flags": risk_flags,
    }


def classifyRecommendationGrade(score: Any, confidence: Any, riskFlags: Iterable[str] | None = None) -> str:
    score_value = safeNumber(score, 0) or 0.0
    confidence_value = safeNumber(confidence, 0) or 0.0
    flags = set(riskFlags or [])
    if flags & SEVERE_RISK_FLAGS:
        return "EXCLUDE" if score_value < 75 else "CAUTION"
    if score_value >= 82 and confidence_value >= 0.70:
        return "STRONG_REVIEW"
    if score_value >= 70 and confidence_value >= 0.60:
        return "BUY_REVIEW"
    if score_value >= 60:
        return "WATCHLIST"
    if score_value >= 48:
        return "NEUTRAL"
    if score_value >= 35:
        return "CAUTION"
    return "EXCLUDE"


def estimateExpectedReturnFromScore(score: Any, volatility: Any, marketRegime: str) -> dict[str, float]:
    score_value = safeNumber(score, 50) or 50.0
    vol = safeNumber(volatility, 0.25) or 0.25
    regime_adj = {"risk_on": 0.012, "recovery": 0.008, "neutral": 0.0, "risk_off": -0.012, "panic": -0.025}.get(str(marketRegime), 0.0)
    base_1m = (score_value - 50) / 100 * 0.075 + regime_adj - vol * 0.035
    return {
        "expected_return_1m": clamp(base_1m, -0.18, 0.22),
        "expected_return_3m": clamp(base_1m * 2.4, -0.30, 0.42),
    }


def estimateProbabilityOutperform(score: Any, confidence: Any, marketRegime: str) -> float:
    score_value = safeNumber(score, 50) or 50.0
    conf = safeNumber(confidence, 0.5) or 0.5
    regime_adj = {"risk_on": 0.04, "recovery": 0.03, "neutral": 0.0, "risk_off": -0.05, "panic": -0.10}.get(str(marketRegime), 0.0)
    return clamp(0.48 + (score_value - 50) / 100 * 0.42 + (conf - 0.5) * 0.18 + regime_adj, 0.05, 0.95)


def calculateSuggestedWeight(score: Any, risk: Any, liquidity: Any, portfolioConstraints: dict[str, Any] | None = None) -> float:
    constraints = portfolioConstraints or {}
    max_single = safeNumber(constraints.get("max_single_stock_weight"), 0.08) or 0.08
    score_value = safeNumber(score, 0) or 0.0
    risk_value = safeNumber(risk, 50) or 50.0
    liquidity_value = safeNumber(liquidity, 50) or 50.0
    if score_value < 60 or risk_value < 35:
        return 0.0
    base = 0.01 + (score_value - 60) / 40 * 0.06
    risk_haircut = clamp(risk_value / 100, 0.2, 1.0)
    liquidity_haircut = clamp(liquidity_value / 100, 0.25, 1.0)
    return clamp(base * risk_haircut * liquidity_haircut, 0.0, max_single)


def generateKoreaStockRationale(scoreBreakdown: dict[str, Any]) -> tuple[list[str], list[str]]:
    factors = scoreBreakdown.get("factor_scores", {})
    positives: list[str] = []
    negatives: list[str] = []
    label_map = {
        "momentum": "모멘텀",
        "quality": "퀄리티",
        "value": "밸류에이션",
        "earnings_revision": "실적 추정",
        "supply_demand": "수급",
        "event_catalyst": "공시 이벤트",
        "value_up": "밸류업",
        "liquidity": "유동성",
    }
    for key, label in label_map.items():
        value = safeNumber(factors.get(key))
        if value is None:
            continue
        if value >= 68:
            positives.append(f"{label} 점수 우수({value:.0f})")
        elif value <= 42:
            negatives.append(f"{label} 점수 취약({value:.0f})")
    penalty = safeNumber(scoreBreakdown.get("risk_penalty"), 0) or 0.0
    if penalty >= 18:
        negatives.append(f"리스크 감점 {penalty:.0f}점")
    return positives[:5], negatives[:5]
