from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


AssetClass = Literal["stocks", "bonds", "mutualFunds", "cash", "crypto", "alternatives"]
ASSET_CLASSES: tuple[AssetClass, ...] = ("stocks", "bonds", "mutualFunds", "cash", "crypto", "alternatives")


@dataclass(frozen=True)
class Holding:
    id: str
    symbol: str
    name: str
    asset_class: AssetClass
    quantity: float
    average_cost: float
    current_price: float
    currency: str
    sector: str | None = None
    country: str | None = None
    benchmark_symbol: str | None = None


@dataclass(frozen=True)
class PortfolioSnapshot:
    date: str
    total_value: float
    invested_capital: float
    cash: float
    benchmark_value: float | None = None


@dataclass(frozen=True)
class TargetAllocation:
    asset_class: AssetClass
    target_weight: float
    min_weight: float | None = None
    max_weight: float | None = None


@dataclass(frozen=True)
class PricePoint:
    date: str
    value: float
    benchmark_value: float | None = None


@dataclass(frozen=True)
class WatchlistItem:
    symbol: str
    name: str
    current_price: float
    change_percent: float
    moving_average_20: float | None = None
    moving_average_60: float | None = None
    moving_average_200: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    volatility: float | None = None
