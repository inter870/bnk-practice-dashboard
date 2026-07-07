from __future__ import annotations

from datetime import date
import math

from .models import Holding, PortfolioSnapshot, PricePoint, TargetAllocation, WatchlistItem


MOCK_TOTAL_ASSETS = 325_980_650.0
MOCK_INVESTED_CAPITAL = 270_560_200.0
MOCK_TOTAL_PROFITS = 55_420_450.0

TARGET_ALLOCATIONS = [
    TargetAllocation("stocks", 0.60, 0.55, 0.65),
    TargetAllocation("bonds", 0.25, 0.20, 0.30),
    TargetAllocation("mutualFunds", 0.10, 0.07, 0.13),
    TargetAllocation("cash", 0.05, 0.03, 0.10),
]

MOCK_HOLDINGS = [
    Holding("kr-005930", "005930", "삼성전자", "stocks", 920, 56_000, 72_000, "KRW", "반도체", "KR", "KS11"),
    Holding("kr-000660", "000660", "SK하이닉스", "stocks", 430, 142_000, 196_000, "KRW", "반도체", "KR", "KS11"),
    Holding("kr-034020", "034020", "두산에너빌리티", "stocks", 1_180, 21_000, 29_800, "KRW", "에너지", "KR", "KS11"),
    Holding("kr-035420", "035420", "NAVER", "stocks", 110, 185_000, 198_000, "KRW", "인터넷", "KR", "KS11"),
    Holding("bond-ktb3", "KTB3Y", "국고채 3년 바스켓", "bonds", 1, 72_300_000, 81_495_162.5, "KRW", "채권", "KR", "KS11"),
    Holding("fund-balanced", "FUND10", "국내 성장 혼합펀드", "mutualFunds", 1, 29_760_200, 32_598_065.5, "KRW", "펀드", "KR", "KS11"),
]

WATCHLIST = [
    WatchlistItem("AAPL", "Apple", 214.3, 0.012, 208.1, 199.4, 182.2, 219.0, 164.0, 0.24),
    WatchlistItem("TSLA", "Tesla", 252.8, -0.018, 260.4, 244.1, 226.0, 299.0, 152.0, 0.52),
    WatchlistItem("NKE", "Nike", 78.5, 0.004, 76.9, 80.1, 88.4, 112.0, 68.0, 0.31),
    WatchlistItem("META", "Meta", 584.6, 0.021, 562.2, 540.0, 499.8, 602.0, 381.0, 0.29),
    WatchlistItem("NVDA", "NVIDIA", 147.9, 0.028, 140.4, 132.8, 119.2, 153.0, 86.0, 0.46),
    WatchlistItem("AMZN", "Amazon", 193.7, -0.006, 192.9, 187.1, 174.3, 201.2, 144.0, 0.27),
]


def build_mock_snapshots() -> list[PortfolioSnapshot]:
    points: list[PortfolioSnapshot] = []
    start_value = 165_000_000.0
    start_benchmark = 100.0
    for month_index in range(102):
        year = 2018 + month_index // 12
        month = month_index % 12 + 1
        if year > 2026:
            break
        growth = 1 + month_index * 0.0065
        cycle = math.sin(month_index / 5.0) * 0.035
        shock = -0.13 if 27 <= month_index <= 31 else -0.08 if 73 <= month_index <= 77 else 0.0
        total_value = start_value * growth * (1 + cycle + shock)
        benchmark_value = start_benchmark * (1 + month_index * 0.0058) * (1 + math.sin(month_index / 6.5) * 0.025 + shock * 0.72)
        invested = max(total_value - MOCK_TOTAL_PROFITS * min(month_index / 101, 1), 1)
        points.append(
            PortfolioSnapshot(
                date=date(year, month, 1).isoformat(),
                total_value=round(total_value, 2),
                invested_capital=round(invested, 2),
                cash=0.0,
                benchmark_value=round(benchmark_value, 4),
            )
        )
    if points:
        points[-1] = PortfolioSnapshot(
            date=points[-1].date,
            total_value=MOCK_TOTAL_ASSETS,
            invested_capital=MOCK_INVESTED_CAPITAL,
            cash=0.0,
            benchmark_value=points[-1].benchmark_value,
        )
    return points


MOCK_SNAPSHOTS = build_mock_snapshots()
MOCK_PRICE_POINTS = [
    PricePoint(point.date, point.total_value, point.benchmark_value)
    for point in MOCK_SNAPSHOTS
]
