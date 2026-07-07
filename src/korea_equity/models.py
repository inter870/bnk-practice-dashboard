from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Market = Literal["KOSPI", "KOSDAQ", "KONEX", "ETF", "ETN"]
RecommendationGrade = Literal[
    "STRONG_REVIEW",
    "BUY_REVIEW",
    "WATCHLIST",
    "NEUTRAL",
    "CAUTION",
    "EXCLUDE",
]
Regime = Literal["risk_on", "neutral", "risk_off", "panic", "recovery"]


@dataclass(frozen=True)
class KoreaTicker:
    code: str
    name: str
    market: Market
    sector: str | None = None
    industry: str | None = None
    theme_tags: list[str] = field(default_factory=list)
    is_preferred_stock: bool = False
    is_etf: bool = False
    is_etn: bool = False
    listing_date: str | None = None
    fiscal_month: int | None = 12


@dataclass(frozen=True)
class KoreaPricePoint:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    trading_value: float
    market_cap: float | None = None
    shares_outstanding: float | None = None
    foreign_ownership_rate: float | None = None
    benchmark_close: float | None = None


@dataclass(frozen=True)
class KoreaFundamentalSnapshot:
    code: str
    date: str
    fiscal_year: int | None = None
    fiscal_quarter: str | None = None
    revenue: float | None = None
    operating_profit: float | None = None
    net_income: float | None = None
    assets: float | None = None
    equity: float | None = None
    debt: float | None = None
    operating_cash_flow: float | None = None
    free_cash_flow: float | None = None
    eps: float | None = None
    bps: float | None = None
    dps: float | None = None
    per: float | None = None
    pbr: float | None = None
    psr: float | None = None
    ev_ebitda: float | None = None
    roe: float | None = None
    roa: float | None = None
    roic: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    debt_to_equity: float | None = None
    dividend_yield: float | None = None
    payout_ratio: float | None = None


@dataclass(frozen=True)
class KoreaSupplyDemandPoint:
    date: str
    code: str
    individual_net_buy: float | None = None
    foreign_net_buy: float | None = None
    institution_net_buy: float | None = None
    pension_net_buy: float | None = None
    financial_investment_net_buy: float | None = None
    insurance_net_buy: float | None = None
    investment_trust_net_buy: float | None = None
    private_equity_net_buy: float | None = None
    bank_net_buy: float | None = None
    other_finance_net_buy: float | None = None
    program_net_buy: float | None = None
    short_sell_value: float | None = None
    short_balance: float | None = None
    short_balance_ratio: float | None = None
    foreign_ownership_rate: float | None = None


@dataclass(frozen=True)
class KoreaDisclosureEvent:
    id: str
    code: str
    date: str
    title: str
    category: str
    sentiment: str
    importance: float
    source: str
    url: str | None = None
    summary: str | None = None


@dataclass(frozen=True)
class KoreaMarketStatus:
    date: str
    kospi_close: float | None = None
    kosdaq_close: float | None = None
    kospi_return_1d: float | None = None
    kosdaq_return_1d: float | None = None
    kospi_above_ma200: bool | None = None
    kosdaq_above_ma200: bool | None = None
    market_breadth: float | None = None
    advance_decline_ratio: float | None = None
    new_high_new_low_ratio: float | None = None
    turnover_trend: float | None = None
    usd_krw: float | None = None
    bond_yield_3y: float | None = None
    volatility_proxy: float | None = None
    regime: Regime = "neutral"
    regime_score: float = 50.0
    reason: list[str] = field(default_factory=list)
    source: str = "mock"
    updated_at: str | None = None
    is_live: bool = False


@dataclass(frozen=True)
class FactorScores:
    value: float
    quality: float
    momentum: float
    earnings_revision: float
    supply_demand: float
    event_catalyst: float
    value_up: float
    liquidity: float
    risk: float


@dataclass(frozen=True)
class KoreaFactorScore:
    code: str
    name: str
    date: str
    market: Market
    sector: str | None
    total_score: float
    recommendation_grade: RecommendationGrade
    confidence: float
    expected_return_1m: float | None = None
    expected_return_3m: float | None = None
    expected_excess_return_1m: float | None = None
    expected_excess_return_3m: float | None = None
    probability_outperform_1m: float | None = None
    probability_outperform_3m: float | None = None
    downside_risk: float | None = None
    suggested_weight: float | None = None
    max_suggested_weight: float | None = None
    stop_review_price: float | None = None
    invalidation_price: float | None = None
    target_review_range_low: float | None = None
    target_review_range_high: float | None = None
    factor_scores: FactorScores | None = None
    positive_reasons: list[str] = field(default_factory=list)
    negative_reasons: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    data_quality_flags: list[str] = field(default_factory=list)
    model_version: str = "korea-alpha-v1.0"
    last_updated: str = ""


@dataclass(frozen=True)
class KoreaBacktestResult:
    strategy_name: str
    universe: str
    start_date: str
    end_date: str
    rebalance_frequency: str
    benchmark: str
    total_return: float
    cagr: float
    annualized_volatility: float
    sharpe_ratio: float | None
    sortino_ratio: float | None
    max_drawdown: float
    hit_ratio: float
    win_rate: float
    average_monthly_return: float
    best_month: float
    worst_month: float
    excess_return: float
    information_ratio: float | None
    turnover: float
    transaction_cost_assumption: float
    slippage_assumption: float
    tax_assumption: float
    precision_at_top10: float | None = None
    precision_at_top20: float | None = None
    average_forward_return_top_decile: float | None = None
    average_forward_return_bottom_decile: float | None = None
    long_short_spread: float | None = None
    factor_ic: float | None = None
    factor_rank_ic: float | None = None
    notes: list[str] = field(default_factory=list)
