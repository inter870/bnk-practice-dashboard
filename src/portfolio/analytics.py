from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
import math
from typing import Any, Iterable

from .models import Holding, PricePoint, TargetAllocation, WatchlistItem


def _obj_value(item: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(item, dict) and name in item:
            return item.get(name)
        if hasattr(item, name):
            return getattr(item, name)
    return default


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _holding_value(holding: Holding | dict[str, Any]) -> float:
    qty = _finite(_obj_value(holding, "quantity", "qty")) or 0.0
    price = _finite(_obj_value(holding, "current_price", "currentPrice", "latest", "price")) or 0.0
    return qty * price


def _holding_cost(holding: Holding | dict[str, Any]) -> float:
    qty = _finite(_obj_value(holding, "quantity", "qty")) or 0.0
    cost = _finite(_obj_value(holding, "average_cost", "averageCost", "avg_price", "avgPrice")) or 0.0
    return qty * cost


def _asset_class(holding: Holding | dict[str, Any]) -> str:
    return str(_obj_value(holding, "asset_class", "assetClass", default="stocks") or "stocks")


def _date_key(item: PricePoint | dict[str, Any]) -> datetime:
    raw = _obj_value(item, "date", default="")
    try:
        return datetime.fromisoformat(str(raw)[:10])
    except ValueError:
        return datetime.min


def _price_value(item: PricePoint | dict[str, Any], benchmark: bool = False) -> float | None:
    if benchmark:
        return _finite(_obj_value(item, "benchmark_value", "benchmarkValue"))
    return _finite(_obj_value(item, "value", "total_value", "totalValue"))


def _sorted_series(price_series: Iterable[PricePoint | dict[str, Any]], *, benchmark: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in price_series or []:
        value = _price_value(item, benchmark=benchmark)
        if value is None:
            continue
        rows.append({"date": str(_obj_value(item, "date", default="")), "value": value})
    return sorted(rows, key=_date_key)


def calculateTotalMarketValue(holdings: Iterable[Holding | dict[str, Any]]) -> float:
    return sum(_holding_value(holding) for holding in holdings or [])


def calculateInvestedCapital(holdings: Iterable[Holding | dict[str, Any]]) -> float:
    return sum(_holding_cost(holding) for holding in holdings or [])


def calculateUnrealizedPnL(holdings: Iterable[Holding | dict[str, Any]]) -> float:
    holdings = list(holdings or [])
    return calculateTotalMarketValue(holdings) - calculateInvestedCapital(holdings)


def calculateUnrealizedPnLPercent(holdings: Iterable[Holding | dict[str, Any]]) -> float | None:
    invested = calculateInvestedCapital(holdings or [])
    if invested <= 0:
        return None
    return calculateUnrealizedPnL(holdings or []) / invested


def calculateAllocationByAssetClass(holdings: Iterable[Holding | dict[str, Any]]) -> dict[str, dict[str, float]]:
    values: dict[str, float] = {}
    total = calculateTotalMarketValue(holdings or [])
    for holding in holdings or []:
        key = _asset_class(holding)
        values[key] = values.get(key, 0.0) + _holding_value(holding)
    if total <= 0:
        return {key: {"value": value, "weight": 0.0} for key, value in values.items()}
    return {key: {"value": value, "weight": value / total} for key, value in values.items()}


def _target_map(target_allocation: Iterable[TargetAllocation | dict[str, Any]] | dict[str, Any]) -> dict[str, float]:
    if isinstance(target_allocation, dict):
        result: dict[str, float] = {}
        for key, value in target_allocation.items():
            if isinstance(value, dict):
                weight = _finite(value.get("target_weight", value.get("targetWeight", value.get("weight"))))
            else:
                weight = _finite(value)
            if weight is not None:
                result[str(key)] = weight
        return result
    result = {}
    for item in target_allocation or []:
        key = str(_obj_value(item, "asset_class", "assetClass", default=""))
        weight = _finite(_obj_value(item, "target_weight", "targetWeight", "weight"))
        if key and weight is not None:
            result[key] = weight
    return result


def calculateAllocationDrift(
    current_allocation: dict[str, dict[str, float]] | dict[str, float],
    target_allocation: Iterable[TargetAllocation | dict[str, Any]] | dict[str, Any],
) -> dict[str, dict[str, float | str]]:
    targets = _target_map(target_allocation)
    keys = sorted(set(current_allocation.keys()) | set(targets.keys()))
    result: dict[str, dict[str, float | str]] = {}
    for key in keys:
        raw_current = current_allocation.get(key, 0.0)
        current_weight = _finite(raw_current.get("weight")) if isinstance(raw_current, dict) else _finite(raw_current)
        current_weight = current_weight or 0.0
        target_weight = targets.get(key, 0.0)
        drift = current_weight - target_weight
        if abs(drift) < 0.01:
            status = "On target"
        elif drift > 0:
            status = "Overweight"
        else:
            status = "Underweight"
        result[key] = {
            "currentWeight": current_weight,
            "targetWeight": target_weight,
            "drift": drift,
            "status": status,
        }
    return result


def generateRebalanceSuggestions(
    current_allocation: dict[str, dict[str, float]] | dict[str, float],
    target_allocation: Iterable[TargetAllocation | dict[str, Any]] | dict[str, Any],
    total_portfolio_value: float,
    options: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    options = options or {}
    threshold = _finite(options.get("threshold")) or 0.03
    minimum_trade_amount = _finite(options.get("minimum_trade_amount", options.get("minimumTradeAmount"))) or 100.0
    total_value = _finite(total_portfolio_value) or 0.0
    if total_value <= 0:
        return []
    drift_rows = calculateAllocationDrift(current_allocation, target_allocation)
    suggestions: list[dict[str, Any]] = []
    for asset_class, row in drift_rows.items():
        drift = _finite(row.get("drift")) or 0.0
        amount = abs(drift) * total_value
        if abs(drift) < threshold or amount < minimum_trade_amount:
            continue
        side = "SELL" if drift > 0 else "BUY"
        action = "비중 축소 후보" if drift > 0 else "비중 보강 후보"
        direction = "초과" if drift > 0 else "부족"
        suggestions.append(
            {
                "assetClass": asset_class,
                "side": side,
                "action": action,
                "drift": drift,
                "suggestedAmount": amount,
                "reason": f"목표 비중 대비 {abs(drift) * 100:.1f}%p {direction}",
                "impact": "목표 배분과 포트폴리오 변동성 균형을 점검합니다.",
            }
        )
    return suggestions


def calculatePeriodReturns(price_series: Iterable[PricePoint | dict[str, Any]]) -> list[float]:
    rows = _sorted_series(price_series)
    returns: list[float] = []
    for prev, current in zip(rows, rows[1:]):
        if prev["value"] == 0:
            continue
        ret = current["value"] / prev["value"] - 1.0
        if math.isfinite(ret):
            returns.append(ret)
    return returns


def calculateCAGR(price_series: Iterable[PricePoint | dict[str, Any]]) -> float | None:
    rows = _sorted_series(price_series)
    if len(rows) < 2 or rows[0]["value"] <= 0:
        return None
    start_date = _date_key(rows[0])
    end_date = _date_key(rows[-1])
    years = (end_date - start_date).days / 365.25 if start_date != datetime.min and end_date != datetime.min else len(rows) / 252
    if years <= 0:
        return None
    result = (rows[-1]["value"] / rows[0]["value"]) ** (1 / years) - 1.0
    return result if math.isfinite(result) else None


def calculateAnnualizedVolatility(return_series: Iterable[float], periodsPerYear: int = 252) -> float | None:
    values = [_finite(value) for value in return_series or []]
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    if len(clean) == 1:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    result = math.sqrt(variance) * math.sqrt(periodsPerYear)
    return result if math.isfinite(result) else None


def calculateSharpeRatio(annualizedReturn: float | None, annualizedVolatility: float | None, riskFreeRate: float) -> float | None:
    annualized_return = _finite(annualizedReturn)
    annualized_volatility = _finite(annualizedVolatility)
    risk_free_rate = _finite(riskFreeRate) or 0.0
    if annualized_return is None or annualized_volatility in (None, 0):
        return None
    result = (annualized_return - risk_free_rate) / annualized_volatility
    return result if math.isfinite(result) else None


def calculateMaxDrawdown(price_series: Iterable[PricePoint | dict[str, Any]]) -> float | None:
    rows = _sorted_series(price_series)
    if not rows:
        return None
    peak = rows[0]["value"]
    max_drawdown = 0.0
    for row in rows:
        value = row["value"]
        peak = max(peak, value)
        if peak <= 0:
            continue
        drawdown = value / peak - 1.0
        max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown if math.isfinite(max_drawdown) else None


def calculateDrawdownSeries(price_series: Iterable[PricePoint | dict[str, Any]]) -> list[dict[str, Any]]:
    rows = _sorted_series(price_series)
    result: list[dict[str, Any]] = []
    peak: float | None = None
    for row in rows:
        value = row["value"]
        peak = value if peak is None else max(peak, value)
        drawdown = 0.0 if peak in (None, 0) else value / peak - 1.0
        result.append({"date": row["date"], "drawdown": drawdown if math.isfinite(drawdown) else 0.0})
    return result


def calculateBenchmarkRelativeReturn(
    portfolio_series: Iterable[PricePoint | dict[str, Any]],
    benchmark_series: Iterable[PricePoint | dict[str, Any]],
) -> float | None:
    portfolio = _sorted_series(portfolio_series)
    benchmark = _sorted_series(benchmark_series)
    if len(portfolio) < 2 or len(benchmark) < 2 or portfolio[0]["value"] <= 0 or benchmark[0]["value"] <= 0:
        return None
    portfolio_return = portfolio[-1]["value"] / portfolio[0]["value"] - 1.0
    benchmark_return = benchmark[-1]["value"] / benchmark[0]["value"] - 1.0
    result = portfolio_return - benchmark_return
    return result if math.isfinite(result) else None


def calculateBeta(portfolioReturns: Iterable[float], benchmarkReturns: Iterable[float]) -> float | None:
    pairs = [
        (p, b)
        for p, b in zip(portfolioReturns or [], benchmarkReturns or [])
        if _finite(p) is not None and _finite(b) is not None
    ]
    if len(pairs) < 2:
        return None
    portfolio = [float(p) for p, _ in pairs]
    benchmark = [float(b) for _, b in pairs]
    mean_p = sum(portfolio) / len(portfolio)
    mean_b = sum(benchmark) / len(benchmark)
    variance_b = sum((b - mean_b) ** 2 for b in benchmark)
    if variance_b == 0:
        return None
    covariance = sum((p - mean_p) * (b - mean_b) for p, b in pairs)
    result = covariance / variance_b
    return result if math.isfinite(result) else None


def _concentration_denominator(values: list[float], total_portfolio_value: float | None) -> float:
    supplied_total = _finite(total_portfolio_value)
    invested_total = sum(values)
    if supplied_total is None:
        return invested_total
    return max(invested_total, supplied_total)


def calculateTopHoldingWeight(
    holdings: Iterable[Holding | dict[str, Any]],
    total_portfolio_value: float | None = None,
) -> float:
    values = [_holding_value(holding) for holding in holdings or []]
    total = _concentration_denominator(values, total_portfolio_value)
    if total <= 0 or not values:
        return 0.0
    return max(values) / total


def calculateHerfindahlIndex(
    holdings: Iterable[Holding | dict[str, Any]],
    total_portfolio_value: float | None = None,
) -> float:
    values = [_holding_value(holding) for holding in holdings or []]
    total = _concentration_denominator(values, total_portfolio_value)
    if total <= 0:
        return 0.0
    return sum((value / total) ** 2 for value in values)


def calculateConcentrationRisk(
    holdings: Iterable[Holding | dict[str, Any]],
    total_portfolio_value: float | None = None,
) -> dict[str, Any]:
    holdings = list(holdings or [])
    top_weight = calculateTopHoldingWeight(holdings, total_portfolio_value)
    hhi = calculateHerfindahlIndex(holdings, total_portfolio_value)
    if top_weight > 0.20 or hhi > 0.20:
        level = "High"
    elif top_weight >= 0.10 or hhi >= 0.12:
        level = "Medium"
    else:
        level = "Low"
    return {
        "level": level,
        "topHoldingWeight": top_weight,
        "herfindahlIndex": hhi,
        "reason": f"최대 보유 {top_weight * 100:.1f}%, HHI {hhi:.2f}",
    }


def generateWatchlistSignals(watchlistItems: Iterable[WatchlistItem | dict[str, Any]]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for item in watchlistItems or []:
        price = _finite(_obj_value(item, "current_price", "currentPrice")) or 0.0
        symbol = str(_obj_value(item, "symbol", default=""))
        name = str(_obj_value(item, "name", default=symbol))
        messages: list[str] = []
        ma20 = _finite(_obj_value(item, "moving_average_20", "movingAverage20"))
        ma60 = _finite(_obj_value(item, "moving_average_60", "movingAverage60"))
        ma200 = _finite(_obj_value(item, "moving_average_200", "movingAverage200"))
        high = _finite(_obj_value(item, "fifty_two_week_high", "fiftyTwoWeekHigh"))
        vol = _finite(_obj_value(item, "volatility"))
        if ma20 and price > ma20:
            messages.append("20일선 상회")
        if ma60 and price > ma60:
            messages.append("60일선 상회")
        if ma200 and price > ma200:
            messages.append("200일선 상회")
        if high and high > 0:
            gap_from_high = price / high - 1.0
            if gap_from_high >= -0.05:
                messages.append("52주 고점 근접")
            else:
                messages.append(f"고점 대비 {gap_from_high * 100:.1f}%")
        if vol and vol > 0.35:
            messages.append("변동성 확대")
        if not messages:
            messages.append("뚜렷한 우위 신호 없음")
        signals.append(
            {
                "symbol": symbol,
                "name": name,
                "changePercent": _finite(_obj_value(item, "change_percent", "changePercent")) or 0.0,
                "signals": messages,
                "tone": "positive" if any("상회" in msg or "근접" in msg for msg in messages) else "neutral",
            }
        )
    return signals


def generatePortfolioInsightSummary(metrics: dict[str, Any]) -> list[dict[str, str]]:
    insights: list[dict[str, str]] = []
    largest_drift = metrics.get("largestDrift")
    if largest_drift:
        insights.append(
            {
                "observation": str(largest_drift.get("observation", "배분 차이가 감지되었습니다.")),
                "why": "목표 비중과 실제 비중의 차이는 변동성과 회복력을 동시에 바꿉니다.",
                "candidate": "신규 자금과 리밸런싱 검토 대상을 목표 비중에서 벗어난 자산군부터 확인합니다.",
            }
        )
    max_drawdown = _finite(metrics.get("maxDrawdown"))
    sharpe = _finite(metrics.get("sharpeRatio"))
    risk_observation = "손실 구간은 관리 가능한 범위입니다."
    if max_drawdown is not None and max_drawdown < -0.20:
        risk_observation = "최대 낙폭이 -20%를 넘어 방어 점검이 필요합니다."
    elif sharpe is not None and sharpe < 0.5:
        risk_observation = "위험 대비 수익 효율이 낮은 구간입니다."
    insights.append(
        {
            "observation": risk_observation,
            "why": "드로다운과 샤프비율은 수익률보다 먼저 포트폴리오 생존력을 보여줍니다.",
            "candidate": "손절 규칙, 현금 비중, 변동성 높은 보유 종목을 우선 점검합니다.",
        }
    )
    suggestions = metrics.get("rebalanceSuggestions") or []
    candidate = "현재는 큰 리밸런싱 후보가 없습니다."
    if suggestions:
        first = suggestions[0]
        candidate = f"{first.get('assetClass')} {first.get('action')} {format_currency(first.get('suggestedAmount'))} 검토"
    insights.append(
        {
            "observation": "오늘의 실행 후보는 리밸런싱과 위험 축소 관점에서 선별됩니다.",
            "why": "확정 매매가 아니라 규칙 기반으로 검토 우선순위를 정합니다.",
            "candidate": candidate,
        }
    )
    return insights[:3]


def format_currency(value: Any, currency: str = "KRW") -> str:
    number = _finite(value)
    if number is None:
        return "N/A"
    if currency.upper() == "KRW":
        return f"{number:,.0f}원"
    return f"{number:,.2f} {currency.upper()}"


def format_percent(value: Any, decimals: int = 1, signed: bool = False) -> str:
    number = _finite(value)
    if number is None:
        return "N/A"
    prefix = "+" if signed and number > 0 else ""
    return f"{prefix}{number * 100:.{decimals}f}%"
