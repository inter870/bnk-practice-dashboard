from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.common import average_traded_value, atr_pct, clamp, find_ohlcv_columns, latest_close, latest_volume, safe_float


@dataclass
class ExecutionPlan:
    execution_quality_score: float
    liquidity_score: float
    estimated_spread_cost_bps: float | None
    estimated_slippage_bps: float | None
    estimated_market_impact_bps: float | None
    total_execution_cost_bps: float | None
    max_order_value_without_impact: float | None
    recommended_order_style: str
    recommended_slices: int
    avoid_execution_window: str | None
    confidence: float
    unavailable_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_execution_plan(
    history: pd.DataFrame,
    *,
    target_order_value: float,
    expected_edge_pct: float | None = None,
    market_regime: str = "Neutral",
) -> ExecutionPlan:
    unavailable: list[str] = ["bid", "ask", "order_book_spread"]
    warnings: list[str] = []
    if history is None or history.empty:
        return ExecutionPlan(0, 0, None, None, None, None, None, "대기", 0, "가격 데이터 없음", 10, ["OHLCV"], ["가격 데이터 unavailable"])

    latest = latest_close(history)
    volume_now = latest_volume(history)
    adv20 = average_traded_value(history, 20)
    volatility = atr_pct(history, 14)
    if latest in (None, 0) or volume_now is None:
        return ExecutionPlan(0, 0, None, None, None, None, None, "대기", 0, "거래량 없음", 15, unavailable, ["현재가/거래량 unavailable"])
    if volume_now <= 0:
        return ExecutionPlan(0, 0, None, None, None, None, 0, "대기", 0, "거래량 0", 20, unavailable, ["거래량 0으로 실행 차단"])
    if adv20 in (None, 0):
        return ExecutionPlan(20, 10, None, None, None, None, None, "대기", 0, "평균 거래대금 없음", 25, unavailable + ["average_traded_value"], ["평균 거래대금 unavailable"])

    order_ratio = max(target_order_value, 0) / adv20
    liquidity_score = clamp(100 - order_ratio * 900, 0, 100)
    if adv20 >= 20_000_000_000:
        liquidity_score = min(100, liquidity_score + 12)
    elif adv20 < 1_000_000_000:
        liquidity_score = max(0, liquidity_score - 25)

    vol = volatility if volatility is not None else 4.0
    if volatility is None:
        unavailable.append("ATR")
        warnings.append("ATR unavailable, 보수적 변동성 4% 적용")

    estimated_spread = None
    estimated_slippage = clamp(6 + vol * 1.8 + order_ratio * 350, 5, 180)
    estimated_impact = clamp(order_ratio * 1200 + max(vol - 4, 0) * 2.0, 0, 350)
    total_cost = estimated_slippage + estimated_impact
    max_order_value = adv20 * 0.015

    quality = clamp((liquidity_score * 0.62) + (100 - min(total_cost, 200) / 2.0) * 0.38, 0, 100)
    if market_regime in {"Extreme Risk-Off", "Risk-Off"}:
        quality *= 0.85
        warnings.append("방어 장세로 체결 품질 할인")

    avoid_window = None
    if vol >= 9 or total_cost >= 160:
        avoid_window = "변동성/비용 과다 구간"
        style = "대기"
        slices = 0
    elif order_ratio >= 0.025:
        style = "TWAP"
        slices = 5
    elif order_ratio >= 0.01:
        style = "VWAP"
        slices = 3
    elif quality >= 75:
        style = "지정가"
        slices = 1
    else:
        style = "분할 지정가"
        slices = 2

    if expected_edge_pct is not None and total_cost / 100.0 >= expected_edge_pct:
        warnings.append("예상 체결비용이 기대값 이상")
        quality = min(quality, 35)
        style = "대기"
        slices = 0

    confidence = clamp(72 - len(unavailable) * 4 - len(warnings) * 6 + (10 if adv20 >= 5_000_000_000 else 0), 20, 85)
    return ExecutionPlan(
        execution_quality_score=round(quality, 2),
        liquidity_score=round(liquidity_score, 2),
        estimated_spread_cost_bps=estimated_spread,
        estimated_slippage_bps=round(estimated_slippage, 2),
        estimated_market_impact_bps=round(estimated_impact, 2),
        total_execution_cost_bps=round(total_cost, 2),
        max_order_value_without_impact=round(max_order_value, 0),
        recommended_order_style=style,
        recommended_slices=slices,
        avoid_execution_window=avoid_window,
        confidence=round(confidence, 2),
        unavailable_fields=list(dict.fromkeys(unavailable)),
        warnings=warnings,
    )


def should_block_for_execution(plan: ExecutionPlan, expected_edge_pct: float | None) -> bool:
    if plan.execution_quality_score <= 20:
        return True
    if expected_edge_pct is None or plan.total_execution_cost_bps is None:
        return False
    return plan.total_execution_cost_bps / 100.0 >= expected_edge_pct

