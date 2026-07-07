from __future__ import annotations

from typing import Any

from .analytics import (
    calculateAllocationByAssetClass,
    calculateInvestedCapital,
    calculateTotalMarketValue,
    calculateUnrealizedPnL,
    calculateUnrealizedPnLPercent,
)
from .mock_data import MOCK_HOLDINGS, MOCK_PRICE_POINTS, TARGET_ALLOCATIONS, WATCHLIST
from .models import Holding, PricePoint, WatchlistItem


def rowsToHoldings(
    rows: list[dict[str, Any]] | None,
    snapshot: dict[str, Any] | None = None,
    code_to_name: dict[str, str] | None = None,
) -> list[Holding]:
    holdings: list[Holding] = []
    if not rows:
        return []
    snapshot = snapshot or {}
    code_to_name = code_to_name or {}
    for row in rows:
        code = str(row.get("code", "")).zfill(6)
        qty = float(row.get("qty") or 0)
        avg_price = float(row.get("avg_price") or 0)
        snap = snapshot.get(code)
        current_price = getattr(snap, "last_close", None) if snap is not None else None
        if current_price in (None, 0):
            current_price = avg_price
        sector = str(row.get("sector") or "미분류")
        holdings.append(
            Holding(
                id=f"kr-{code}",
                symbol=code,
                name=code_to_name.get(code, code),
                asset_class="stocks",
                quantity=qty,
                average_cost=avg_price,
                current_price=float(current_price),
                currency="KRW",
                sector=sector,
                country="KR",
                benchmark_symbol="KS11",
            )
        )
    return holdings


def getHoldings(
    rows: list[dict[str, Any]] | None = None,
    snapshot: dict[str, Any] | None = None,
    code_to_name: dict[str, str] | None = None,
) -> list[Holding]:
    holdings = rowsToHoldings(rows, snapshot, code_to_name)
    return holdings if holdings else list(MOCK_HOLDINGS)


def getPortfolioSnapshots() -> list[PricePoint]:
    return list(MOCK_PRICE_POINTS)


def getBenchmarkSeries() -> list[PricePoint]:
    return [PricePoint(point.date, point.benchmark_value or 0.0) for point in MOCK_PRICE_POINTS if point.benchmark_value is not None]


def getWatchlist() -> list[WatchlistItem]:
    return list(WATCHLIST)


def getPortfolioSummary(holdings: list[Holding]) -> dict[str, Any]:
    return {
        "totalValue": calculateTotalMarketValue(holdings),
        "investedCapital": calculateInvestedCapital(holdings),
        "unrealizedPnL": calculateUnrealizedPnL(holdings),
        "unrealizedPnLPercent": calculateUnrealizedPnLPercent(holdings),
        "allocation": calculateAllocationByAssetClass(holdings),
        "targetAllocation": TARGET_ALLOCATIONS,
    }
