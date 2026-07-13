from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Sequence

from .config import KRAlphaConfig
from .domain import FixtureStock, MarketBar
from .service import estimate_cost_bps


@dataclass(frozen=True)
class TradeSimulation:
    instrument_id: str
    decision_time: datetime
    entry_time: datetime | None
    exit_time: datetime | None
    requested_value_krw: float
    filled_value_krw: float
    fill_ratio: float
    entry_price: float | None
    exit_price: float | None
    gross_return: float | None
    net_return: float | None
    cost_bps: float
    status: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class BacktestSummary:
    trades: tuple[TradeSimulation, ...]
    gross_return: float | None
    net_return: float | None
    turnover: float
    total_cost_bps: float
    data_quality_status: str
    methodology: str = "next_tradable_bar_fixture_v1"


def next_tradable_bar(bars: Sequence[MarketBar], decision_time: datetime) -> MarketBar | None:
    candidates = sorted((bar for bar in bars if bar.bar_start > decision_time), key=lambda bar: bar.bar_start)
    for bar in candidates:
        if bar.is_suspended or bar.volume <= 0:
            continue
        if bar.limit_state == "UP" or bar.is_vi:
            continue
        return bar
    return None


def simulate_long_trade(
    stock: FixtureStock,
    decision_time: datetime,
    config: KRAlphaConfig,
    *,
    holding_bars: int = 5,
) -> TradeSimulation:
    entry = next_tradable_bar(stock.bars, decision_time)
    cost_bps = estimate_cost_bps(stock, config)
    if entry is None:
        return TradeSimulation(
            stock.security.instrument_id,
            decision_time,
            None,
            None,
            stock.expected_order_krw,
            0.0,
            0.0,
            None,
            None,
            None,
            None,
            cost_bps,
            "UNAVAILABLE",
            ("no_tradable_entry_bar",),
        )
    ordered = sorted(stock.bars, key=lambda bar: bar.bar_start)
    entry_index = ordered.index(entry)
    future = [bar for bar in ordered[entry_index + 1 :] if not bar.is_suspended and bar.volume > 0]
    exit_bar = future[min(max(holding_bars - 1, 0), len(future) - 1)] if future else None
    if exit_bar is None:
        return TradeSimulation(
            stock.security.instrument_id, decision_time, entry.bar_start, None,
            stock.expected_order_krw, 0.0, 0.0, entry.open, None, None, None,
            cost_bps, "PENDING", ("exit_horizon_incomplete",),
        )
    max_fill = stock.adv_20d_krw * config.risk.maximum_adv_participation
    fill_ratio = min(1.0, max(0.0, max_fill / stock.expected_order_krw)) if stock.expected_order_krw > 0 else 0.0
    filled = stock.expected_order_krw * fill_ratio
    if fill_ratio <= 0:
        status = "UNFILLED"
        reasons = ("liquidity_unavailable",)
        gross = net = None
    else:
        delisted_during_trade = stock.security.delisted_at is not None and stock.security.delisted_at <= exit_bar.bar_end
        exit_price = 0.0 if delisted_during_trade else exit_bar.close
        gross = exit_price / entry.open - 1.0
        net = gross - cost_bps / 10_000.0
        status = "PARTIAL" if fill_ratio < 1.0 else "COMPLETE"
        reasons = tuple(
            code for code, present in (
                ("partial_fill", fill_ratio < 1.0),
                ("delisting_loss", delisted_during_trade),
            ) if present
        )
    return TradeSimulation(
        stock.security.instrument_id,
        decision_time,
        entry.bar_start,
        exit_bar.bar_end,
        stock.expected_order_krw,
        filled,
        fill_ratio,
        entry.open,
        0.0 if "delisting_loss" in reasons else exit_bar.close,
        gross,
        net,
        cost_bps,
        status,
        reasons,
    )


def summarize_backtest(trades: Sequence[TradeSimulation]) -> BacktestSummary:
    completed = [trade for trade in trades if trade.net_return is not None and trade.fill_ratio > 0]
    if not completed:
        return BacktestSummary(tuple(trades), None, None, 0.0, 0.0, "INSUFFICIENT_EVIDENCE")
    weights = [trade.filled_value_krw for trade in completed]
    total = sum(weights)
    if total <= 0:
        return BacktestSummary(tuple(trades), None, None, 0.0, 0.0, "INSUFFICIENT_EVIDENCE")
    gross = sum(float(trade.gross_return) * weight for trade, weight in zip(completed, weights)) / total
    net = sum(float(trade.net_return) * weight for trade, weight in zip(completed, weights)) / total
    costs = sum(trade.cost_bps * weight for trade, weight in zip(completed, weights)) / total
    return BacktestSummary(tuple(trades), gross, net, total * 2.0, costs, "FIXTURE_ONLY")
