from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .domain import FixtureStock, MarketBar, PITObservation, Security


KST = ZoneInfo("Asia/Seoul")
FACTOR_NAMES = (
    "earnings_surprise_pead",
    "near_52w_high",
    "earnings_revision",
    "quality_fscore",
    "value",
    "shareholder_yield",
    "medium_momentum",
    "short_reversal",
    "investor_flow",
    "short_borrow",
    "low_vol_beta",
    "liquidity_impact",
    "index_rebalance",
    "policy_disclosure",
)


def _at(day: int, hour: int = 15, minute: int = 30) -> datetime:
    return datetime(2026, 6, day, hour, minute, tzinfo=KST)


def _bars(instrument_id: str, base: float, *, suspended_day: int | None = None, limit_day: int | None = None) -> tuple[MarketBar, ...]:
    rows: list[MarketBar] = []
    for index in range(25):
        day = _at(1) + timedelta(days=index)
        if day.weekday() >= 5:
            continue
        close = base * (1.0 + 0.004 * index + 0.01 * ((index % 4) - 1.5))
        suspended = suspended_day == index
        rows.append(
            MarketBar(
                instrument_id=instrument_id,
                venue="KRX",
                bar_start=day.replace(hour=9, minute=0),
                bar_end=day,
                open=close * 0.995,
                high=close * 1.02,
                low=close * 0.98,
                close=close,
                volume=0.0 if suspended else 1_000_000 + index * 20_000,
                turnover_krw=0.0 if suspended else close * (1_000_000 + index * 20_000),
                available_at=day.replace(hour=15, minute=40),
                is_suspended=suspended,
                is_vi=index == 8,
                limit_state="UP" if limit_day == index else None,
            )
        )
    return tuple(rows)


def _observation(instrument_id: str, field: str, value: float | str | bool, available_at: datetime) -> PITObservation:
    return PITObservation(
        instrument_id=instrument_id,
        field=field,
        value=value,
        period_end=_at(1, 0, 0),
        filed_at=available_at,
        published_at=available_at,
        available_at=available_at,
        restated_at=None,
        source="KR Alpha deterministic fixture",
        unit="score",
    )


class FixtureKRAlphaProvider:
    name = "KR Alpha deterministic fixture"
    version = "fixture-v1"
    mode = "fixture"

    def snapshot(self, decision_time: datetime) -> tuple[FixtureStock, ...]:
        specs = (
            ("fixture-1", "900001", "실적모멘텀 예시", "KOSPI", "반도체", "large", 72_000.0,
             (1.8, 0.96, 0.8, 8.0, 0.55, 0.7, 0.22, -0.03, 1.4, -0.2, 0.8, 0.9, 0.2, 0.8),
             ("earnings_after_close", "earnings_surprise", "foreign_institution_joint_buy"), 90_000_000_000.0, 300_000_000.0),
            ("fixture-2", "900002", "신고가수급 예시", "KOSDAQ", "인터넷", "mid", 35_000.0,
             (0.9, 0.99, 0.5, 6.0, 0.25, 0.2, 0.35, -0.08, 1.8, -0.5, 0.2, 0.7, 0.6, 0.4),
             ("near_52w_high", "vi", "limit_up"), 18_000_000_000.0, 250_000_000.0),
            ("fixture-3", "900003", "주주환원 예시", "KOSPI", "금융", "large", 58_000.0,
             (0.2, 0.55, 0.3, 7.0, 0.85, 1.4, 0.08, 0.02, 0.6, -0.1, 1.1, 0.95, 0.0, 1.2),
             ("dividend", "share_split", "value_up"), 55_000_000_000.0, 200_000_000.0),
            ("fixture-4", "900004", "유동성경고 예시", "KOSDAQ", "산업재", "small", 8_000.0,
             (-0.4, 0.30, -0.7, 3.0, 0.7, 0.0, -0.18, 0.18, -1.1, -1.2, -0.8, -1.8, 0.0, -0.9),
             ("partial_fill", "illiquid", "suspension"), 300_000_000.0, 120_000_000.0),
            ("fixture-5", "900005", "공매도혼잡 예시", "KOSPI", "바이오", "mid", 24_000.0,
             (0.1, 0.70, -0.2, 4.0, -0.3, 0.0, 0.12, -0.02, -0.4, -1.9, -1.0, 0.4, 0.1, -0.2),
             ("short_crowding", "borrow_cost_high"), 9_000_000_000.0, 100_000_000.0),
            ("fixture-6", "900006", "상장폐지 예시", "KOSDAQ", "소재", "small", 3_000.0,
             (-1.2, 0.10, -1.1, 1.0, 0.9, -0.8, -0.45, 0.30, -1.5, -0.9, -1.4, -2.0, -0.5, -1.8),
             ("delisting", "administrative_issue"), 120_000_000.0, 80_000_000.0),
        )
        stocks: list[FixtureStock] = []
        for idx, (instrument_id, ticker, name, market, sector, size, base, values, events, adv, order) in enumerate(specs):
            security = Security(
                instrument_id=instrument_id,
                ticker=ticker,
                name_ko=name,
                market=market,
                venue="KRX",
                sector=sector,
                size_bucket=size,
                listed_at=datetime(2020, 1, 2, 9, 0, tzinfo=KST),
                delisted_at=(_at(25, 9, 0) if "delisting" in events else None),
                is_active="delisting" not in events,
            )
            available = _at(18, 18, 10) if "earnings_after_close" in events else _at(18, 14, 0)
            observations = tuple(
                _observation(instrument_id, factor, value, available)
                for factor, value in zip(FACTOR_NAMES, values)
            ) + (_observation(instrument_id, "future_revision", 9.9, decision_time + timedelta(days=2)),)
            stocks.append(
                FixtureStock(
                    security=security,
                    observations=observations,
                    factor_inputs=dict(zip(FACTOR_NAMES, values)),
                    bars=_bars(instrument_id, base, suspended_day=(10 if "suspension" in events else None), limit_day=(7 if "limit_up" in events else None)),
                    event_flags=events,
                    adv_20d_krw=adv,
                    expected_order_krw=order,
                )
            )
        return tuple(stocks)

    def securities(self, decision_time: datetime) -> tuple[Security, ...]:
        return tuple(stock.security for stock in self.snapshot(decision_time))
