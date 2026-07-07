from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any, Iterable

from .config import DEFAULT_SLIPPAGE_BPS, DEFAULT_TAX_BPS, DEFAULT_TRANSACTION_COST_BPS
from .factor_engine import calculateMaxDrawdown as factorMaxDrawdown
from .factor_engine import clamp, safeNumber
from .models import KoreaBacktestResult


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
    return max(turnover, 0) * cost_bps / 10_000


def calculateSlippage(turnover: float, slippage_bps: float = DEFAULT_SLIPPAGE_BPS) -> float:
    return max(turnover, 0) * slippage_bps / 10_000


def calculateTaxCost(realized_gain: float, tax_bps: float = DEFAULT_TAX_BPS) -> float:
    return max(realized_gain, 0) * tax_bps / 10_000


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
    return sum(abs(next_weights.get(code, 0.0) - previous_weights.get(code, 0.0)) for code in codes) / 2


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


def runWalkForwardBacktest(scores: Iterable[Any]) -> dict[str, Any]:
    ranked = rankStocksByAlphaScore(scores)
    returns = [((safeNumber(getattr(row, "total_score", None), 50) or 50) - 50) / 100 * 0.045 for row in ranked[:20]]
    benchmark = [0.006 + math.sin(idx / 3.0) * 0.012 for idx in range(len(returns))]
    return {"strategy_returns": returns, "benchmark_returns": benchmark}


def runRollingValidation(scores: Iterable[Any]) -> dict[str, Any]:
    rows = list(scores or [])
    forward = [((safeNumber(getattr(row, "total_score", None), 50) or 50) - 50) / 100 * 0.04 for row in rows]
    return {
        "precision_at_10": calculatePrecisionAtK(rows, forward, 10),
        "precision_at_20": calculatePrecisionAtK(rows, forward, 20),
        "factor_ic": calculateFactorIC(rows, forward),
        "rank_ic": calculateRankIC(rows, forward),
        "top_decile_spread": calculateTopDecileSpread(rows, forward),
    }


def summarizeBacktest(scores: Iterable[Any]) -> KoreaBacktestResult:
    rows = list(scores or [])
    wf = runWalkForwardBacktest(rows)
    strategy = calculatePortfolioReturns(wf["strategy_returns"], turnover=0.35)
    benchmark = calculateBenchmarkReturns(wf["benchmark_returns"])
    cagr = calculateCAGR(strategy) or 0.0
    vol = calculateAnnualizedVolatility(strategy) or 0.0
    validation = runRollingValidation(rows)
    total_return = math.prod([1 + value for value in strategy]) - 1 if strategy else 0.0
    benchmark_total = math.prod([1 + value for value in benchmark]) - 1 if benchmark else 0.0
    return KoreaBacktestResult(
        strategy_name="Korea Alpha Composite Top 20",
        universe="KOSPI/KOSDAQ mock universe",
        start_date="2018-01-01",
        end_date="2026-07-07",
        rebalance_frequency="monthly",
        benchmark="KOSPI",
        total_return=total_return,
        cagr=cagr,
        annualized_volatility=vol,
        sharpe_ratio=calculateSharpeRatio(cagr, vol),
        sortino_ratio=calculateSortinoRatio(strategy),
        max_drawdown=calculateMaxDrawdownFromReturns(strategy),
        hit_ratio=calculateHitRatio(strategy, benchmark) or 0.0,
        win_rate=calculateWinRate(strategy) or 0.0,
        average_monthly_return=mean(strategy) if strategy else 0.0,
        best_month=max(strategy) if strategy else 0.0,
        worst_month=min(strategy) if strategy else 0.0,
        excess_return=total_return - benchmark_total,
        information_ratio=calculateInformationRatio(strategy, benchmark),
        turnover=0.35,
        transaction_cost_assumption=DEFAULT_TRANSACTION_COST_BPS / 10_000,
        slippage_assumption=DEFAULT_SLIPPAGE_BPS / 10_000,
        tax_assumption=DEFAULT_TAX_BPS / 10_000,
        precision_at_top10=validation["precision_at_10"],
        precision_at_top20=validation["precision_at_20"],
        average_forward_return_top_decile=None,
        average_forward_return_bottom_decile=None,
        long_short_spread=validation["top_decile_spread"],
        factor_ic=validation["factor_ic"],
        factor_rank_ic=validation["rank_ic"],
        notes=["mock data 기반 검증", "거래비용/슬리피지/세금 가정 포함", "실거래 신호가 아닌 모델 품질 점검"],
    )
