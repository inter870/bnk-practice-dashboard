from __future__ import annotations

from typing import Any

from .backtest_engine import summarizeBacktest
from .config import DATA_MODE
from .decision_os import buildKoreaInvestmentOS
from .mock_data import (
    DISCLOSURES,
    FUNDAMENTALS,
    KOREA_UNIVERSE,
    MARKET_STATUS,
    PRICE_HISTORY,
    SUPPLY_DEMAND,
    VALUE_UP_FLAGS,
    benchmark_series,
)
from .models import KoreaBacktestResult, KoreaDisclosureEvent, KoreaFactorScore, KoreaFundamentalSnapshot, KoreaMarketStatus, KoreaPricePoint, KoreaSupplyDemandPoint, KoreaTicker
from .recommendation_engine import buildKoreaFactorScore, rankKoreaAlphaCandidates
from .risk_engine import portfolioRiskSummary


def getKoreaUniverse() -> list[KoreaTicker]:
    return list(KOREA_UNIVERSE)


def getKoreaPriceHistory(code: str, options: dict[str, Any] | None = None) -> list[KoreaPricePoint]:
    return list(PRICE_HISTORY.get(str(code).zfill(6), []))


def getKoreaFundamentals(code: str) -> KoreaFundamentalSnapshot | None:
    return FUNDAMENTALS.get(str(code).zfill(6))


def getKoreaSupplyDemand(code: str, options: dict[str, Any] | None = None) -> list[KoreaSupplyDemandPoint]:
    return list(SUPPLY_DEMAND.get(str(code).zfill(6), []))


def getKoreaDisclosureEvents(code: str, options: dict[str, Any] | None = None) -> list[KoreaDisclosureEvent]:
    return list(DISCLOSURES.get(str(code).zfill(6), []))


def getKoreaMarketStatus(options: dict[str, Any] | None = None) -> KoreaMarketStatus:
    options = options or {}
    market_status = options.get("market_status")
    if isinstance(market_status, KoreaMarketStatus):
        return market_status
    return MARKET_STATUS


def getKoreaBenchmarkSeries(benchmark: str = "KOSPI", options: dict[str, Any] | None = None) -> list[KoreaPricePoint]:
    return benchmark_series(benchmark)


def getKoreaAlphaScores(options: dict[str, Any] | None = None) -> list[KoreaFactorScore]:
    options = options or {}
    market_filter = set(options.get("markets") or [])
    sector_filter = set(options.get("sectors") or [])
    min_trading_value = float(options.get("min_trading_value") or 0)
    market_status = getKoreaMarketStatus(options)
    benchmark = getKoreaBenchmarkSeries(options.get("benchmark", "KOSPI"), options)
    scores: list[KoreaFactorScore] = []
    fundamentals_by_sector: dict[str, list[KoreaFundamentalSnapshot]] = {}
    for ticker in getKoreaUniverse():
        fundamental = getKoreaFundamentals(ticker.code)
        if fundamental is not None:
            fundamentals_by_sector.setdefault(ticker.sector or "미분류", []).append(fundamental)
    for ticker in getKoreaUniverse():
        if market_filter and ticker.market not in market_filter:
            continue
        if sector_filter and (ticker.sector or "미분류") not in sector_filter:
            continue
        prices = getKoreaPriceHistory(ticker.code, options)
        if min_trading_value and prices:
            avg_value = sum(point.trading_value for point in prices[-20:]) / min(len(prices), 20)
            if avg_value < min_trading_value:
                continue
        fundamental = getKoreaFundamentals(ticker.code)
        if fundamental is None:
            continue
        scores.append(
            buildKoreaFactorScore(
                ticker,
                prices,
                benchmark,
                fundamental,
                getKoreaSupplyDemand(ticker.code, options),
                getKoreaDisclosureEvents(ticker.code, options),
                market_status,
                fundamentals_by_sector.get(ticker.sector or "미분류", []),
            )
        )
    return scores


def getKoreaTopCandidates(options: dict[str, Any] | None = None) -> list[KoreaFactorScore]:
    options = options or {}
    return rankKoreaAlphaCandidates(getKoreaAlphaScores(options), int(options.get("limit", 10)))


def getKoreaBacktestResults(options: dict[str, Any] | None = None) -> KoreaBacktestResult:
    return summarizeBacktest(getKoreaAlphaScores(options or {}))


def getKoreaDashboardData(options: dict[str, Any] | None = None) -> dict[str, Any]:
    options = options or {}
    scores = getKoreaAlphaScores(options)
    top = rankKoreaAlphaCandidates(scores, int(options.get("limit", 10)))
    disclosures = [event for events in DISCLOSURES.values() for event in events]
    value_up = [score for score in scores if VALUE_UP_FLAGS.get(score.code) or (score.factor_scores and score.factor_scores.value_up >= 65)]
    market_status = getKoreaMarketStatus(options)
    backtest = summarizeBacktest(scores)
    risk_summary = portfolioRiskSummary(scores)
    value_up_candidates = rankKoreaAlphaCandidates(value_up, 8)
    investment_os = buildKoreaInvestmentOS(
        top,
        market_status=market_status,
        backtest=backtest,
        disclosures=sorted(disclosures, key=lambda event: (event.date, event.importance), reverse=True)[:12],
        value_up_candidates=value_up_candidates,
        risk_summary=risk_summary,
        portfolio=options.get("portfolio"),
    )
    return {
        "dataMode": DATA_MODE,
        "marketStatus": market_status,
        "scores": scores,
        "topCandidates": top,
        "backtest": backtest,
        "disclosures": sorted(disclosures, key=lambda event: (event.date, event.importance), reverse=True)[:12],
        "valueUpCandidates": value_up_candidates,
        "riskSummary": risk_summary,
        "investmentOS": investment_os,
    }
