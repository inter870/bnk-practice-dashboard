from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date, datetime, timezone
from statistics import mean, pstdev
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from .config import DEFAULT_SLIPPAGE_BPS, DEFAULT_TAX_BPS, DEFAULT_TRANSACTION_COST_BPS
from .factor_engine import calculateMaxDrawdown as factorMaxDrawdown
from .factor_engine import safeNumber
from .models import KoreaBacktestResult


KST = ZoneInfo("Asia/Seoul")


def createBacktestUniverse(scores: Iterable[Any], min_score: float = 0.0) -> list[Any]:
    return [row for row in scores or [] if (safeNumber(getattr(row, "total_score", None), 0) or 0) >= min_score]


def rankStocksByAlphaScore(scores: Iterable[Any]) -> list[Any]:
    return sorted(scores or [], key=lambda row: safeNumber(getattr(row, "total_score", None), 0) or 0, reverse=True)


def rebalancePortfolio(scores: Iterable[Any], top_n: int = 10, weighting: str = "score") -> dict[str, float]:
    ranked = rankStocksByAlphaScore(scores)[: max(1, top_n)]
    if not ranked:
        return {}
    if weighting == "equal":
        return {getattr(row, "code"): 1 / len(ranked) for row in ranked}
    total = sum(max(safeNumber(getattr(row, "total_score", None), 0) or 0, 1) for row in ranked)
    return {getattr(row, "code"): max(safeNumber(getattr(row, "total_score", None), 0) or 0, 1) / total for row in ranked}


def calculateTransactionCosts(turnover: float, cost_bps: float = DEFAULT_TRANSACTION_COST_BPS) -> float:
    clean_turnover = safeNumber(turnover, 0) or 0
    clean_bps = safeNumber(cost_bps, 0) or 0
    return max(clean_turnover, 0) * max(clean_bps, 0) / 10_000


def calculateSlippage(turnover: float, slippage_bps: float = DEFAULT_SLIPPAGE_BPS) -> float:
    clean_turnover = safeNumber(turnover, 0) or 0
    clean_bps = safeNumber(slippage_bps, 0) or 0
    return max(clean_turnover, 0) * max(clean_bps, 0) / 10_000


def calculateTaxCost(realized_gain: float, tax_bps: float = DEFAULT_TAX_BPS) -> float:
    taxable_amount = safeNumber(realized_gain, 0) or 0
    clean_bps = safeNumber(tax_bps, 0) or 0
    return max(taxable_amount, 0) * max(clean_bps, 0) / 10_000


def calculatePortfolioReturns(period_returns: Iterable[Any], turnover: float = 0.0) -> list[float]:
    cost = calculateTransactionCosts(turnover) + calculateSlippage(turnover)
    clean = [safeNumber(value) for value in period_returns]
    rows = [float(value) for value in clean if value is not None]
    if rows:
        rows[0] -= cost
    return rows


def calculateBenchmarkReturns(period_returns: Iterable[Any]) -> list[float]:
    clean = [safeNumber(value) for value in period_returns]
    return [float(value) for value in clean if value is not None]


def calculateCAGR(period_returns: Iterable[Any], periods_per_year: int = 12) -> float | None:
    rows = [float(value) for value in (safeNumber(item) for item in period_returns) if value is not None]
    if not rows:
        return None
    total = 1.0
    for value in rows:
        total *= 1 + value
    years = len(rows) / periods_per_year
    return None if years <= 0 or total <= 0 else total ** (1 / years) - 1


def calculateAnnualizedVolatility(period_returns: Iterable[Any], periods_per_year: int = 12) -> float | None:
    rows = [float(value) for value in (safeNumber(item) for item in period_returns) if value is not None]
    return None if len(rows) < 2 else pstdev(rows) * math.sqrt(periods_per_year)


def calculateSharpeRatio(annualized_return: float | None, annualized_volatility: float | None, risk_free_rate: float = 0.025) -> float | None:
    if annualized_return is None or annualized_volatility in (None, 0):
        return None
    return (annualized_return - risk_free_rate) / annualized_volatility


def calculateSortinoRatio(period_returns: Iterable[Any], risk_free_rate: float = 0.025, periods_per_year: int = 12) -> float | None:
    rows = [float(value) for value in (safeNumber(item) for item in period_returns) if value is not None]
    downside = [min(0.0, value) for value in rows]
    if not rows or len(downside) < 2:
        return None
    cagr = calculateCAGR(rows, periods_per_year)
    downside_dev = pstdev(downside) * math.sqrt(periods_per_year)
    if cagr is None or downside_dev == 0:
        return None
    return (cagr - risk_free_rate) / downside_dev


def calculateMaxDrawdownFromReturns(period_returns: Iterable[Any]) -> float:
    value = 1.0
    points = []
    for ret in (safeNumber(item) for item in period_returns):
        if ret is None:
            continue
        value *= 1 + ret
        points.append(value)
    return factorMaxDrawdown(points)


def calculateMaxDrawdown(price_series: Iterable[Any]) -> float:
    return factorMaxDrawdown(price_series)


def calculateHitRatio(strategy_returns: Iterable[Any], benchmark_returns: Iterable[Any]) -> float | None:
    strategy = [safeNumber(value) for value in strategy_returns]
    benchmark = [safeNumber(value) for value in benchmark_returns]
    pairs = [(s, b) for s, b in zip(strategy, benchmark) if s is not None and b is not None]
    if not pairs:
        return None
    return sum(1 for s, b in pairs if s > b) / len(pairs)


def calculateWinRate(strategy_returns: Iterable[Any]) -> float | None:
    rows = [safeNumber(value) for value in strategy_returns]
    clean = [value for value in rows if value is not None]
    return None if not clean else sum(1 for value in clean if value > 0) / len(clean)


def calculateTurnover(previous_weights: dict[str, float], next_weights: dict[str, float]) -> float:
    codes = set(previous_weights) | set(next_weights)
    previous = {code: max(safeNumber(previous_weights.get(code), 0) or 0, 0) for code in codes}
    following = {code: max(safeNumber(next_weights.get(code), 0) or 0, 0) for code in codes}
    asset_change = sum(abs(following[code] - previous[code]) for code in codes)
    previous_cash = max(0.0, 1.0 - sum(previous.values()))
    next_cash = max(0.0, 1.0 - sum(following.values()))
    return (asset_change + abs(next_cash - previous_cash)) / 2


def calculateRebalanceCosts(
    previous_weights: dict[str, float],
    next_weights: dict[str, float],
    transaction_cost_bps: float = DEFAULT_TRANSACTION_COST_BPS,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    tax_bps: float = DEFAULT_TAX_BPS,
) -> dict[str, float]:
    turnover = calculateTurnover(previous_weights, next_weights)
    sell_turnover = sum(
        max((safeNumber(previous_weights.get(code), 0) or 0) - (safeNumber(next_weights.get(code), 0) or 0), 0)
        for code in set(previous_weights) | set(next_weights)
    )
    transaction_cost = calculateTransactionCosts(turnover, transaction_cost_bps)
    slippage_cost = calculateSlippage(turnover, slippage_bps)
    tax_cost = calculateTaxCost(sell_turnover, tax_bps)
    return {
        "turnover": turnover,
        "sell_turnover": sell_turnover,
        "transaction_cost": transaction_cost,
        "slippage_cost": slippage_cost,
        "tax_cost": tax_cost,
        "total_cost": transaction_cost + slippage_cost + tax_cost,
    }


def calculateInformationRatio(strategy_returns: Iterable[Any], benchmark_returns: Iterable[Any]) -> float | None:
    active = []
    for s, b in zip(strategy_returns, benchmark_returns):
        s_value, b_value = safeNumber(s), safeNumber(b)
        if s_value is not None and b_value is not None:
            active.append(s_value - b_value)
    if len(active) < 2:
        return None
    tracking_error = pstdev(active) * math.sqrt(12)
    return None if tracking_error == 0 else mean(active) * 12 / tracking_error


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    mx, my = mean(xs), mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / len(xs)
    vx = sum((x - mx) ** 2 for x in xs) / len(xs)
    vy = sum((y - my) ** 2 for y in ys) / len(ys)
    denom = math.sqrt(vx * vy)
    return None if denom == 0 else cov / denom


def calculateFactorIC(scores: Iterable[Any], forward_returns: Iterable[Any]) -> float | None:
    xs = [safeNumber(getattr(row, "total_score", row)) for row in scores]
    ys = [safeNumber(value) for value in forward_returns]
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    return _pearson([x for x, _ in pairs], [y for _, y in pairs])


def calculateRankIC(scores: Iterable[Any], forward_returns: Iterable[Any]) -> float | None:
    xs = [safeNumber(getattr(row, "total_score", row)) for row in scores]
    ys = [safeNumber(value) for value in forward_returns]
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 2:
        return None
    ranked_x = {value: rank for rank, value in enumerate(sorted({x for x, _ in pairs}), 1)}
    ranked_y = {value: rank for rank, value in enumerate(sorted({y for _, y in pairs}), 1)}
    return _pearson([ranked_x[x] for x, _ in pairs], [ranked_y[y] for _, y in pairs])


def calculatePrecisionAtK(scores: Iterable[Any], forward_returns: Iterable[Any], k: int = 10) -> float | None:
    pairs = [
        (safeNumber(getattr(score, "total_score", score)), safeNumber(ret))
        for score, ret in zip(scores, forward_returns)
    ]
    clean = [(score, ret) for score, ret in pairs if score is not None and ret is not None]
    if not clean:
        return None
    top = sorted(clean, key=lambda item: item[0], reverse=True)[: max(1, min(k, len(clean)))]
    return sum(1 for _, ret in top if ret > 0) / len(top)


def calculateTopDecileSpread(scores: Iterable[Any], forward_returns: Iterable[Any]) -> float | None:
    clean = [
        (safeNumber(getattr(score, "total_score", score)), safeNumber(ret))
        for score, ret in zip(scores, forward_returns)
    ]
    rows = sorted([(score, ret) for score, ret in clean if score is not None and ret is not None], key=lambda item: item[0])
    if len(rows) < 4:
        return None
    bucket = max(1, len(rows) // 10)
    bottom = mean(ret for _, ret in rows[:bucket])
    top = mean(ret for _, ret in rows[-bucket:])
    return top - bottom


def calculateLongShortSpread(scores: Iterable[Any], forward_returns: Iterable[Any]) -> float | None:
    return calculateTopDecileSpread(scores, forward_returns)


def _fieldValue(row: Any, *names: str) -> Any:
    for name in names:
        if isinstance(row, Mapping) and name in row:
            value = row[name]
        else:
            value = getattr(row, name, None)
        if value is not None:
            return value
    return None


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time())
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        normalized = f"{text[:-1]}+00:00" if text.endswith(("Z", "z")) else text
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            parsed = None
            for pattern in ("%Y%m%d", "%Y.%m.%d", "%Y-%m-%d"):
                try:
                    parsed = datetime.strptime(text, pattern)
                    break
                except ValueError:
                    continue
            if parsed is None:
                return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    return parsed.astimezone(timezone.utc)


def _isoTimestamp(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(KST).isoformat(timespec="seconds")


def _crossSectionMetrics(scores: list[float], returns: list[float]) -> dict[str, float | None]:
    if len(scores) < 2 or len(scores) != len(returns) or len(set(scores)) < 2:
        return {
            "factor_ic": None,
            "rank_ic": None,
            "precision_at_10": None,
            "precision_at_20": None,
            "top_decile_return": None,
            "bottom_decile_return": None,
            "top_decile_spread": None,
        }
    top_decile, bottom_decile = _decileForwardReturns(scores, returns)
    return {
        "factor_ic": calculateFactorIC(scores, returns),
        "rank_ic": calculateRankIC(scores, returns),
        "precision_at_10": calculatePrecisionAtK(scores, returns, 10),
        "precision_at_20": calculatePrecisionAtK(scores, returns, 20),
        "top_decile_return": top_decile,
        "bottom_decile_return": bottom_decile,
        "top_decile_spread": calculateTopDecileSpread(scores, returns),
    }


def _aggregateCrossSectionMetrics(periods: list[dict[str, Any]]) -> dict[str, float | None]:
    keys = (
        "factor_ic",
        "rank_ic",
        "precision_at_10",
        "precision_at_20",
        "top_decile_return",
        "bottom_decile_return",
        "top_decile_spread",
    )
    return {
        key: mean(values) if (values := [float(row[key]) for row in periods if row.get(key) is not None]) else None
        for key in keys
    }


def _rows(values: Iterable[Any] | Mapping[Any, Any] | None) -> list[Any]:
    if values is None:
        return []
    if isinstance(values, Mapping):
        return [values]
    if isinstance(values, (str, bytes)):
        return []
    return list(values)


def applyPointInTimeCutoff(
    rows: Iterable[Any],
    cutoff: Any,
    timestamp_fields: Iterable[str] = ("available_at", "fetched_at", "timestamp", "date", "as_of_date"),
) -> list[Any]:
    cutoff_at = _timestamp(cutoff)
    if cutoff_at is None:
        return []
    fields = (timestamp_fields,) if isinstance(timestamp_fields, str) else tuple(timestamp_fields)
    filtered: list[Any] = []
    for row in list(rows or []):
        row_at = _timestamp(_fieldValue(row, *fields))
        if row_at is not None and row_at <= cutoff_at:
            filtered.append(row)
    return filtered


def _normalizeFeatureSnapshots(rows: Iterable[Any] | None, cutoff: datetime | None) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for row in _rows(rows):
        code_value = _fieldValue(row, "code", "ticker", "symbol")
        score = safeNumber(_fieldValue(row, "total_score", "score", "alpha_score"))
        available_at = _timestamp(
            _fieldValue(row, "available_at", "fetched_at", "published_at", "receipt_at", "timestamp")
        )
        as_of_date = _timestamp(_fieldValue(row, "as_of_date", "feature_at", "date", "timestamp"))
        code = "" if code_value is None else str(code_value).strip()
        if not code or score is None or available_at is None:
            continue
        as_of_date = as_of_date or available_at
        if as_of_date > available_at or (cutoff is not None and (available_at > cutoff or as_of_date > cutoff)):
            continue
        snapshots.append(
            {
                "code": code,
                "score": float(score),
                "as_of_date": as_of_date,
                "available_at": available_at,
                "source": _fieldValue(row, "source") or "timestamped_feature_input",
            }
        )
    return snapshots


def _universeRows(historical_universe: Iterable[Any] | Mapping[Any, Any] | None) -> list[Any]:
    if not isinstance(historical_universe, Mapping):
        return _rows(historical_universe)
    timestamp_keys = {"rebalance_at", "effective_at", "timestamp", "date", "as_of_date"}
    if timestamp_keys.intersection(historical_universe):
        return [historical_universe]
    return [{"timestamp": timestamp, "members": members} for timestamp, members in historical_universe.items()]


def _memberCodes(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, Mapping):
        values = [code for code, included in value.items() if included]
    elif isinstance(value, (str, bytes)):
        values = [value]
    else:
        try:
            values = list(value)
        except TypeError:
            values = [value]
    members: set[str] = set()
    for item in values:
        code = _fieldValue(item, "code", "ticker", "symbol") if isinstance(item, Mapping) or hasattr(item, "code") else item
        if code is not None and str(code).strip():
            members.add(str(code).strip())
    return members


def _normalizeHistoricalUniverse(
    historical_universe: Iterable[Any] | Mapping[Any, Any] | None,
    cutoff: datetime | None,
) -> list[tuple[datetime, set[str]]]:
    snapshots: dict[datetime, set[str]] = {}
    for row in _universeRows(historical_universe):
        effective_at = _timestamp(_fieldValue(row, "rebalance_at", "effective_at", "timestamp", "date", "as_of_date"))
        available_at = _timestamp(_fieldValue(row, "available_at", "fetched_at")) or effective_at
        if effective_at is None or available_at is None:
            continue
        decision_at = max(effective_at, available_at)
        if cutoff is not None and decision_at > cutoff:
            continue
        members_value = _fieldValue(row, "members", "codes", "constituents", "universe")
        members = _memberCodes(members_value)
        if members_value is None:
            included = _fieldValue(row, "is_member", "included")
            if included is not False:
                members = _memberCodes([_fieldValue(row, "code", "ticker", "symbol")])
        if members:
            snapshots.setdefault(decision_at, set()).update(members)
    return sorted(snapshots.items(), key=lambda item: item[0])


def _priceRows(price_inputs: Iterable[Any] | Mapping[Any, Any] | None) -> list[tuple[str | None, Any]]:
    if not isinstance(price_inputs, Mapping):
        return [(None, row) for row in _rows(price_inputs)]
    point_fields = {"timestamp", "date", "as_of_date", "close", "adjusted_close", "price"}
    if point_fields.intersection(price_inputs):
        return [(None, price_inputs)]
    flattened: list[tuple[str | None, Any]] = []
    for code, series in price_inputs.items():
        for row in _rows(series):
            flattened.append((str(code), row))
    return flattened


def _normalizePrices(
    price_inputs: Iterable[Any] | Mapping[Any, Any] | None,
    cutoff: datetime | None,
    default_code: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    prices: dict[str, list[dict[str, Any]]] = {}
    for supplied_code, row in _priceRows(price_inputs):
        code_value = _fieldValue(row, "code", "ticker", "symbol") or supplied_code or default_code
        observed_at = _timestamp(_fieldValue(row, "timestamp", "date", "as_of_date"))
        available_at = _timestamp(_fieldValue(row, "available_at")) or observed_at
        close = safeNumber(_fieldValue(row, "adjusted_close", "close", "price"))
        code = "" if code_value is None else str(code_value).strip()
        if not code or observed_at is None or available_at is None or close is None or close <= 0:
            continue
        if available_at < observed_at or (cutoff is not None and (observed_at > cutoff or available_at > cutoff)):
            continue
        prices.setdefault(code, []).append(
            {
                "timestamp": observed_at,
                "available_at": available_at,
                "close": float(close),
                "source": _fieldValue(row, "source") or "timestamped_price_input",
            }
        )
    for series in prices.values():
        series.sort(key=lambda point: (point["timestamp"], point["available_at"]))
    return prices


def _featuresAt(
    snapshots: list[dict[str, Any]],
    members: set[str],
    rebalance_at: datetime,
) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        code = snapshot["code"]
        if code not in members or snapshot["available_at"] > rebalance_at or snapshot["as_of_date"] > rebalance_at:
            continue
        current = latest.get(code)
        if current is None or (snapshot["available_at"], snapshot["as_of_date"]) > (
            current["available_at"],
            current["as_of_date"],
        ):
            latest[code] = snapshot
    return list(latest.values())


def _targetWeights(features: list[dict[str, Any]], top_n: int, weighting: str) -> dict[str, float]:
    ranked = sorted(features, key=lambda row: (-row["score"], row["code"]))[: max(1, top_n)]
    if not ranked:
        return {}
    if weighting == "equal":
        return {row["code"]: 1 / len(ranked) for row in ranked}
    denominator = sum(max(row["score"], 1.0) for row in ranked)
    return {row["code"]: max(row["score"], 1.0) / denominator for row in ranked}


def _firstTradablePriceAfter(series: list[dict[str, Any]], boundary: datetime) -> dict[str, Any] | None:
    eligible = [
        point
        for point in series
        if point["timestamp"] > boundary and point["available_at"] <= point["timestamp"]
    ]
    return min(eligible, key=lambda point: (point["timestamp"], point["available_at"])) if eligible else None


def _periodPriceReturn(
    series: list[dict[str, Any]],
    start_at: datetime,
    end_at: datetime,
) -> tuple[float, dict[str, Any], dict[str, Any]] | None:
    start = _firstTradablePriceAfter(series, start_at)
    end = _firstTradablePriceAfter(series, end_at)
    if start is None or end is None or end["timestamp"] <= start["timestamp"]:
        return None
    return end["close"] / start["close"] - 1, start, end


def _driftWeights(weights: dict[str, float], returns: dict[str, float], gross_return: float) -> dict[str, float]:
    ending_value = 1 + gross_return
    if ending_value <= 0:
        return {}
    return {code: weight * (1 + returns[code]) / ending_value for code, weight in weights.items()}


def _benchmarkSeries(prices: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    for code in ("__benchmark__", "KOSPI", "kospi"):
        if code in prices:
            return prices[code]
    return max(prices.values(), key=len) if prices else []


_UNAVAILABLE_REASON_TEXT = {
    "current_scores_are_not_historical_inputs": "현재 점수는 timestamped 역사 데이터가 아님",
    "historical_universe_missing": "시점별 역사적 유니버스가 없음",
    "invalid_point_in_time_cutoff": "point-in-time cutoff가 유효한 timestamp가 아님",
    "timestamped_feature_inputs_missing": "available_at이 있는 feature snapshot이 없음",
    "timestamped_price_inputs_missing": "timestamped price 입력이 없음",
    "insufficient_rebalance_history": "리밸런싱 시점이 2개 미만임",
    "eligible_features_missing": "해당 시점 유니버스에서 이용 가능한 feature가 없음",
    "feature_history_incomplete": "유니버스 구성원의 point-in-time feature 이력이 불완전함",
    "selected_price_history_incomplete": "선정 종목의 구간 가격 이력이 불완전함",
    "non_positive_portfolio_value": "비용 반영 후 포트폴리오 가치가 0 이하임",
}


def _unavailableWalkForward(
    reason: str,
    *,
    synthetic_demo: bool = False,
    details: Iterable[str] | None = None,
) -> dict[str, Any]:
    mode = "synthetic_demo" if synthetic_demo else "historical_inputs_incomplete"
    notes = [
        "검증 불가 (validation_unavailable)",
        f"데이터 상태: {mode}",
        _UNAVAILABLE_REASON_TEXT.get(reason, reason),
    ]
    notes.extend(str(item) for item in (details or []))
    return {
        "status": "validation_unavailable",
        "validation_status": "validation_unavailable",
        "validation_available": False,
        "reason": reason,
        "data_mode": mode,
        "synthetic": synthetic_demo,
        "demo": synthetic_demo,
        "strategy_returns": [],
        "benchmark_returns": [],
        "periods": [],
        "feature_scores": [],
        "forward_returns": [],
        "average_turnover": None,
        "source": "unavailable",
        "as_of_date": None,
        "available_at": None,
        "unit": "decimal_return",
        "quality_status": "validation_unavailable",
        "notes": notes,
    }


def runChronologicalWalkForwardBacktest(
    feature_inputs: Iterable[Any],
    price_inputs: Iterable[Any] | Mapping[Any, Any] | None,
    historical_universe: Iterable[Any] | Mapping[Any, Any] | None,
    benchmark_prices: Iterable[Any] | Mapping[Any, Any] | None = None,
    *,
    top_n: int = 10,
    weighting: str = "score",
    point_in_time_cutoff: Any | None = None,
    transaction_cost_bps: float = DEFAULT_TRANSACTION_COST_BPS,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    tax_bps: float = DEFAULT_TAX_BPS,
) -> dict[str, Any]:
    cutoff = _timestamp(point_in_time_cutoff) if point_in_time_cutoff is not None else None
    if point_in_time_cutoff is not None and cutoff is None:
        return _unavailableWalkForward("invalid_point_in_time_cutoff")

    universe = _normalizeHistoricalUniverse(historical_universe, cutoff)
    if not universe:
        return _unavailableWalkForward("historical_universe_missing")
    if len(universe) < 2:
        return _unavailableWalkForward("insufficient_rebalance_history")

    features = _normalizeFeatureSnapshots(feature_inputs, cutoff)
    if not features:
        return _unavailableWalkForward("timestamped_feature_inputs_missing")
    prices = _normalizePrices(price_inputs, cutoff)
    if not prices:
        return _unavailableWalkForward("timestamped_price_inputs_missing")
    benchmark_series = _benchmarkSeries(_normalizePrices(benchmark_prices, cutoff, "__benchmark__"))

    clean_top_n = max(1, int(safeNumber(top_n, 10) or 10))
    previous_weights: dict[str, float] = {}
    periods: list[dict[str, Any]] = []
    strategy_returns: list[float] = []
    benchmark_by_period: list[float | None] = []
    validation_periods: list[dict[str, Any]] = []
    eligible_observations = 0
    validated_observations = 0

    for index in range(len(universe) - 1):
        rebalance_at, members = universe[index]
        period_end, _ = universe[index + 1]
        eligible_features = _featuresAt(features, members, rebalance_at)
        if not eligible_features:
            return _unavailableWalkForward(
                "eligible_features_missing",
                details=[f"rebalance_at: {_isoTimestamp(rebalance_at)}"],
            )
        if len(eligible_features) != len(members):
            covered_codes = {feature["code"] for feature in eligible_features}
            missing_codes = sorted(members - covered_codes)
            return _unavailableWalkForward(
                "feature_history_incomplete",
                details=[
                    f"rebalance_at: {_isoTimestamp(rebalance_at)}",
                    f"missing_codes: {','.join(missing_codes)}",
                ],
            )
        target_weights = _targetWeights(eligible_features, clean_top_n, weighting)
        selected_features = {row["code"]: row for row in eligible_features if row["code"] in target_weights}
        decision_available_at = max(
            [rebalance_at, *(feature["available_at"] for feature in selected_features.values())]
        )

        security_returns: dict[str, float] = {}
        start_points: list[dict[str, Any]] = []
        end_points: list[dict[str, Any]] = []
        for code in target_weights:
            period_return = _periodPriceReturn(prices.get(code, []), decision_available_at, period_end)
            if period_return is None:
                return _unavailableWalkForward(
                    "selected_price_history_incomplete",
                    details=[f"code: {code}", f"rebalance_at: {_isoTimestamp(rebalance_at)}"],
                )
            security_returns[code], start_point, end_point = period_return
            start_points.append(start_point)
            end_points.append(end_point)

        execution_times = {point["timestamp"] for point in start_points}
        exit_times = {point["timestamp"] for point in end_points}
        if len(execution_times) != 1 or len(exit_times) != 1:
            return _unavailableWalkForward(
                "selected_price_history_incomplete",
                details=[f"rebalance_at: {_isoTimestamp(rebalance_at)}", "unaligned_execution_prices"],
            )
        execution_at = next(iter(execution_times))
        exit_at = next(iter(exit_times))

        gross_return = sum(target_weights[code] * security_returns[code] for code in target_weights)
        costs = calculateRebalanceCosts(
            previous_weights,
            target_weights,
            transaction_cost_bps,
            slippage_bps,
            tax_bps,
        )
        net_return = gross_return - costs["total_cost"]
        if net_return <= -1:
            return _unavailableWalkForward(
                "non_positive_portfolio_value",
                details=[f"rebalance_at: {_isoTimestamp(rebalance_at)}"],
            )

        benchmark_result = _periodPriceReturn(benchmark_series, decision_available_at, period_end) if benchmark_series else None
        if benchmark_result is not None and (
            benchmark_result[1]["timestamp"] != execution_at or benchmark_result[2]["timestamp"] != exit_at
        ):
            benchmark_result = None
        benchmark_return = benchmark_result[0] if benchmark_result is not None else None
        benchmark_by_period.append(benchmark_return)

        eligible_observations += len(eligible_features)
        validation_decision_at = max(
            [rebalance_at, *(feature["available_at"] for feature in eligible_features)]
        )
        validation_rows: list[tuple[dict[str, Any], tuple[float, dict[str, Any], dict[str, Any]]]] = []
        for feature in eligible_features:
            observed_return = _periodPriceReturn(
                prices.get(feature["code"], []),
                validation_decision_at,
                period_end,
            )
            if observed_return is None:
                validation_rows = []
                break
            validation_rows.append((feature, observed_return))
        validation_entries = {row[1][1]["timestamp"] for row in validation_rows}
        validation_exits = {row[1][2]["timestamp"] for row in validation_rows}
        if (
            len(validation_rows) == len(eligible_features)
            and len(validation_entries) == 1
            and len(validation_exits) == 1
        ):
            period_scores = [float(feature["score"]) for feature, _ in validation_rows]
            period_returns = [float(result[0]) for _, result in validation_rows]
            metrics = _crossSectionMetrics(period_scores, period_returns)
            validation_periods.append(
                {
                    "rebalance_at": _isoTimestamp(rebalance_at),
                    "execution_at": _isoTimestamp(next(iter(validation_entries))),
                    "exit_at": _isoTimestamp(next(iter(validation_exits))),
                    "sample_count": len(period_scores),
                    **metrics,
                }
            )
            validated_observations += len(period_scores)

        available_at = max(point["available_at"] for point in end_points)
        periods.append(
            {
                "rebalance_at": _isoTimestamp(rebalance_at),
                "period_end": _isoTimestamp(period_end),
                "execution_at": _isoTimestamp(execution_at),
                "exit_at": _isoTimestamp(exit_at),
                "weights": dict(target_weights),
                "previous_weights": dict(previous_weights),
                "selected_features": {
                    code: {
                        "score": feature["score"],
                        "as_of_date": _isoTimestamp(feature["as_of_date"]),
                        "available_at": _isoTimestamp(feature["available_at"]),
                        "source": feature["source"],
                    }
                    for code, feature in selected_features.items()
                },
                "security_returns": dict(security_returns),
                "gross_return": gross_return,
                "turnover": costs["turnover"],
                "sell_turnover": costs["sell_turnover"],
                "transaction_cost": costs["transaction_cost"],
                "slippage_cost": costs["slippage_cost"],
                "tax_cost": costs["tax_cost"],
                "total_cost": costs["total_cost"],
                "net_return": net_return,
                "benchmark_return": benchmark_return,
                "source": "timestamped_feature_price_inputs",
                "as_of_date": exit_at.astimezone(KST).date().isoformat(),
                "available_at": _isoTimestamp(available_at),
                "unit": "decimal_return",
                "quality_status": "point_in_time_validated",
            }
        )
        strategy_returns.append(net_return)
        previous_weights = _driftWeights(target_weights, security_returns, gross_return)

    benchmark_returns = (
        [float(value) for value in benchmark_by_period if value is not None]
        if benchmark_by_period and all(value is not None for value in benchmark_by_period)
        else []
    )
    notes = [
        "검증 완료 (validated): historical_point_in_time",
        "각 rebalance 시점의 available_at 이전 feature만 사용",
        "의사결정 및 feature 사용 가능 시각 이후 첫 공통 거래가격으로 진입",
        "매 rebalance turnover·transaction cost·slippage·tax 반영",
    ]
    if cutoff is not None:
        notes.append(f"point-in-time cutoff: {_isoTimestamp(cutoff)}")
    if not benchmark_returns:
        notes.append("벤치마크 검증 불가: timestamped benchmark price 입력 없음 또는 불완전")
    validation_coverage = validated_observations / eligible_observations if eligible_observations else None
    cross_section_valid = validation_coverage == 1.0 and bool(validation_periods)
    validation_summary = _aggregateCrossSectionMetrics(validation_periods) if cross_section_valid else _aggregateCrossSectionMetrics([])
    if not cross_section_valid:
        notes.append("횡단면 검증 불가: 전체 유니버스의 forward price 이력이 불완전함")

    return {
        "status": "validated",
        "validation_status": "validated",
        "validation_available": True,
        "reason": None,
        "data_mode": "historical_point_in_time",
        "synthetic": False,
        "demo": False,
        "strategy_returns": strategy_returns,
        "benchmark_returns": benchmark_returns,
        "periods": periods,
        "feature_scores": [],
        "forward_returns": [],
        "validation_periods": validation_periods if cross_section_valid else [],
        "validation_summary": validation_summary,
        "validation_coverage": validation_coverage,
        "cross_section_validation_status": "validated" if cross_section_valid else "validation_unavailable",
        "average_turnover": mean(period["turnover"] for period in periods),
        "total_transaction_cost": sum(period["transaction_cost"] for period in periods),
        "total_slippage_cost": sum(period["slippage_cost"] for period in periods),
        "total_tax_cost": sum(period["tax_cost"] for period in periods),
        "start_date": periods[0]["execution_at"][:10],
        "end_date": periods[-1]["exit_at"][:10],
        "source": "timestamped_feature_price_inputs",
        "as_of_date": periods[-1]["exit_at"][:10],
        "available_at": periods[-1]["available_at"],
        "unit": "decimal_return",
        "quality_status": "point_in_time_validated",
        "notes": notes,
    }


def runWalkForwardBacktest(
    scores: Iterable[Any],
    price_inputs: Iterable[Any] | Mapping[Any, Any] | None = None,
    historical_universe: Iterable[Any] | Mapping[Any, Any] | None = None,
    benchmark_prices: Iterable[Any] | Mapping[Any, Any] | None = None,
    *,
    feature_snapshots: Iterable[Any] | None = None,
    price_history: Iterable[Any] | Mapping[Any, Any] | None = None,
    top_n: int = 10,
    weighting: str = "score",
    point_in_time_cutoff: Any | None = None,
    transaction_cost_bps: float = DEFAULT_TRANSACTION_COST_BPS,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    tax_bps: float = DEFAULT_TAX_BPS,
) -> dict[str, Any]:
    features = feature_snapshots if feature_snapshots is not None else scores
    prices = price_history if price_history is not None else price_inputs
    if prices is None:
        return _unavailableWalkForward("current_scores_are_not_historical_inputs", synthetic_demo=True)
    return runChronologicalWalkForwardBacktest(
        features,
        prices,
        historical_universe,
        benchmark_prices,
        top_n=top_n,
        weighting=weighting,
        point_in_time_cutoff=point_in_time_cutoff,
        transaction_cost_bps=transaction_cost_bps,
        slippage_bps=slippage_bps,
        tax_bps=tax_bps,
    )


def runRollingValidation(
    scores: Iterable[Any],
    forward_returns: Iterable[Any] | None = None,
) -> dict[str, Any]:
    rows = list(scores or [])
    if forward_returns is None:
        return {
            "status": "validation_unavailable",
            "validation_available": False,
            "precision_at_10": None,
            "precision_at_20": None,
            "factor_ic": None,
            "rank_ic": None,
            "top_decile_spread": None,
        }
    forward = list(forward_returns)
    pairs = [
        (score, ret)
        for score, ret in zip(rows, forward)
        if safeNumber(getattr(score, "total_score", score)) is not None and safeNumber(ret) is not None
    ]
    if not pairs:
        return {
            "status": "validation_unavailable",
            "validation_available": False,
            "precision_at_10": None,
            "precision_at_20": None,
            "factor_ic": None,
            "rank_ic": None,
            "top_decile_spread": None,
        }
    clean_scores = [score for score, _ in pairs]
    clean_forward = [ret for _, ret in pairs]
    return {
        "status": "validated",
        "validation_available": True,
        "precision_at_10": calculatePrecisionAtK(clean_scores, clean_forward, 10),
        "precision_at_20": calculatePrecisionAtK(clean_scores, clean_forward, 20),
        "factor_ic": calculateFactorIC(clean_scores, clean_forward),
        "rank_ic": calculateRankIC(clean_scores, clean_forward),
        "top_decile_spread": calculateTopDecileSpread(clean_scores, clean_forward),
    }


def _unavailableBacktestResult(walk_forward: Mapping[str, Any]) -> KoreaBacktestResult:
    unavailable: Any = None
    reason = str(walk_forward.get("reason") or "validation_unavailable")
    notes = ["검증 불가 (validation_unavailable)"]
    if walk_forward.get("synthetic"):
        notes.append("합성/데모 데이터 (synthetic_demo): 현재 점수로 수익률을 재생성하지 않음")
    else:
        notes.append("실제 역사 입력 불완전: 성과 지표를 생성하지 않음")
    notes.append(_UNAVAILABLE_REASON_TEXT.get(reason, reason))
    return KoreaBacktestResult(
        strategy_name="Korea Alpha Composite Top 20",
        universe="시점별 역사적 유니버스 검증 불가",
        start_date="N/A",
        end_date="N/A",
        rebalance_frequency="monthly",
        benchmark="KOSPI",
        total_return=unavailable,
        cagr=unavailable,
        annualized_volatility=unavailable,
        sharpe_ratio=None,
        sortino_ratio=None,
        max_drawdown=unavailable,
        hit_ratio=unavailable,
        win_rate=unavailable,
        average_monthly_return=unavailable,
        best_month=unavailable,
        worst_month=unavailable,
        excess_return=unavailable,
        information_ratio=None,
        turnover=unavailable,
        transaction_cost_assumption=DEFAULT_TRANSACTION_COST_BPS / 10_000,
        slippage_assumption=DEFAULT_SLIPPAGE_BPS / 10_000,
        tax_assumption=DEFAULT_TAX_BPS / 10_000,
        precision_at_top10=None,
        precision_at_top20=None,
        average_forward_return_top_decile=None,
        average_forward_return_bottom_decile=None,
        long_short_spread=None,
        factor_ic=None,
        factor_rank_ic=None,
        notes=notes,
    )


def _decileForwardReturns(scores: Iterable[Any], forward_returns: Iterable[Any]) -> tuple[float | None, float | None]:
    clean = [
        (safeNumber(getattr(score, "total_score", score)), safeNumber(ret))
        for score, ret in zip(scores, forward_returns)
    ]
    ranked = sorted(
        [(score, ret) for score, ret in clean if score is not None and ret is not None],
        key=lambda item: item[0],
    )
    if len(ranked) < 4:
        return None, None
    bucket = max(1, len(ranked) // 10)
    return mean(ret for _, ret in ranked[-bucket:]), mean(ret for _, ret in ranked[:bucket])


def summarizeBacktest(
    scores: Iterable[Any],
    price_inputs: Iterable[Any] | Mapping[Any, Any] | None = None,
    historical_universe: Iterable[Any] | Mapping[Any, Any] | None = None,
    benchmark_prices: Iterable[Any] | Mapping[Any, Any] | None = None,
    *,
    feature_snapshots: Iterable[Any] | None = None,
    price_history: Iterable[Any] | Mapping[Any, Any] | None = None,
    top_n: int = 20,
    weighting: str = "score",
    point_in_time_cutoff: Any | None = None,
    periods_per_year: int = 12,
    transaction_cost_bps: float = DEFAULT_TRANSACTION_COST_BPS,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    tax_bps: float = DEFAULT_TAX_BPS,
) -> KoreaBacktestResult:
    walk_forward = runWalkForwardBacktest(
        scores,
        price_inputs,
        historical_universe,
        benchmark_prices,
        feature_snapshots=feature_snapshots,
        price_history=price_history,
        top_n=top_n,
        weighting=weighting,
        point_in_time_cutoff=point_in_time_cutoff,
        transaction_cost_bps=transaction_cost_bps,
        slippage_bps=slippage_bps,
        tax_bps=tax_bps,
    )
    if not walk_forward["validation_available"]:
        return _unavailableBacktestResult(walk_forward)

    strategy = calculateBenchmarkReturns(walk_forward["strategy_returns"])
    benchmark = calculateBenchmarkReturns(walk_forward["benchmark_returns"])
    cagr = calculateCAGR(strategy, periods_per_year)
    volatility = calculateAnnualizedVolatility(strategy, periods_per_year)
    total_return = math.prod(1 + value for value in strategy) - 1
    benchmark_total = math.prod(1 + value for value in benchmark) - 1 if benchmark else None
    validation = walk_forward.get("validation_summary") or runRollingValidation(
        walk_forward["feature_scores"],
        walk_forward["forward_returns"],
    )
    top_decile = validation.get("top_decile_return")
    bottom_decile = validation.get("bottom_decile_return")
    return KoreaBacktestResult(
        strategy_name=f"Korea Alpha Composite Top {max(1, int(top_n))}",
        universe="시점별 역사적 유니버스",
        start_date=walk_forward["start_date"],
        end_date=walk_forward["end_date"],
        rebalance_frequency="monthly",
        benchmark="KOSPI",
        total_return=total_return,
        cagr=cagr,
        annualized_volatility=volatility,
        sharpe_ratio=calculateSharpeRatio(cagr, volatility),
        sortino_ratio=calculateSortinoRatio(strategy, periods_per_year=periods_per_year),
        max_drawdown=calculateMaxDrawdownFromReturns(strategy),
        hit_ratio=calculateHitRatio(strategy, benchmark) if benchmark else None,
        win_rate=calculateWinRate(strategy),
        average_monthly_return=mean(strategy),
        best_month=max(strategy),
        worst_month=min(strategy),
        excess_return=total_return - benchmark_total if benchmark_total is not None else None,
        information_ratio=calculateInformationRatio(strategy, benchmark) if benchmark else None,
        turnover=walk_forward["average_turnover"],
        transaction_cost_assumption=max(safeNumber(transaction_cost_bps, 0) or 0, 0) / 10_000,
        slippage_assumption=max(safeNumber(slippage_bps, 0) or 0, 0) / 10_000,
        tax_assumption=max(safeNumber(tax_bps, 0) or 0, 0) / 10_000,
        precision_at_top10=validation["precision_at_10"],
        precision_at_top20=validation["precision_at_20"],
        average_forward_return_top_decile=top_decile,
        average_forward_return_bottom_decile=bottom_decile,
        long_short_spread=validation["top_decile_spread"],
        factor_ic=validation["factor_ic"],
        factor_rank_ic=validation["rank_ic"],
        notes=list(walk_forward["notes"]),
    )


apply_point_in_time_cutoff = applyPointInTimeCutoff
calculate_rebalance_costs = calculateRebalanceCosts
run_chronological_walk_forward_backtest = runChronologicalWalkForwardBacktest
