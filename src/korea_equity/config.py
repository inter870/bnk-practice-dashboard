from __future__ import annotations


DATA_MODE = "mock"
KOREA_MARKET_DEFAULT_BENCHMARK = "KOSPI"
DEFAULT_REBALANCE_FREQUENCY = "monthly"
DEFAULT_TRANSACTION_COST_BPS = 15.0
DEFAULT_SLIPPAGE_BPS = 8.0
DEFAULT_TAX_BPS = 18.0
DEFAULT_MIN_TRADING_VALUE_KRW = 5_000_000_000
DEFAULT_MAX_SINGLE_STOCK_WEIGHT = 0.08
DEFAULT_MAX_SECTOR_WEIGHT = 0.28
DEFAULT_MAX_KOSDAQ_WEIGHT = 0.35
MODEL_VERSION = "korea-alpha-v1.0"

FACTOR_WEIGHTS = {
    "momentum": 0.22,
    "quality": 0.18,
    "value": 0.16,
    "earnings_revision": 0.14,
    "supply_demand": 0.14,
    "event_catalyst": 0.06,
    "value_up": 0.06,
    "liquidity": 0.04,
}

SEVERE_RISK_FLAGS = {
    "trading_halt",
    "management_issue",
    "investment_warning",
    "investment_danger",
    "insufficient_liquidity",
    "negative_disclosure",
    "missing_core_price_data",
    "data_quality_issue",
}
