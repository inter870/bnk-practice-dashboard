from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from src.common import atr_pct, clamp, find_ohlcv_columns, latest_close, safe_float


@dataclass
class ExitPlan:
    initial_stop: float | None
    hard_stop: float | None
    trailing_stop: float | None
    time_stop_date: date | None
    first_take_profit: float | None
    second_take_profit: float | None
    runner_position_pct: float
    break_even_move_trigger: float | None
    stop_to_break_even_rule: str
    exit_on_signal_deterioration_rule: str
    exit_on_event_risk_rule: str
    status: str
    exit_confidence: float
    invalidation_rules: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _volume_confirmed(history: pd.DataFrame) -> bool:
    if history is None or history.empty:
        return False
    _, _, _, _, volume_c = find_ohlcv_columns(history)
    if volume_c not in history.columns:
        return False
    volume = history[volume_c].dropna()
    if len(volume) < 20:
        return False
    avg20 = safe_float(volume.tail(20).mean())
    latest = safe_float(volume.iloc[-1])
    return avg20 not in (None, 0) and latest is not None and latest >= avg20


def _last_date(history: pd.DataFrame) -> pd.Timestamp:
    if history is None or history.empty:
        return pd.Timestamp.today().normalize()
    idx = history.index[-1]
    try:
        return pd.Timestamp(idx)
    except Exception:
        return pd.Timestamp.today().normalize()


def build_exit_plan(
    risk_plan: dict,
    history: pd.DataFrame,
    *,
    entry_price: float | None = None,
    expected_holding_days: int = 20,
    leadership_score: float | None = None,
    market_regime: str = "Neutral",
    catalyst_risk: str = "Low",
) -> ExitPlan:
    warnings: list[str] = []
    latest = latest_close(history) or safe_float(risk_plan.get("latest"))
    initial_stop = safe_float(risk_plan.get("stop"))
    resistance = safe_float(risk_plan.get("resistance"))
    if latest is None or initial_stop is None or initial_stop <= 0 or latest <= initial_stop:
        return ExitPlan(initial_stop, initial_stop, initial_stop, None, None, None, 0, None, "가격/손절 데이터 부족", "신호 악화 시 관망", "고위험 이벤트 전 신규 진입 금지", "계산 불가", 20, ["손절 기준 확인 필요"], ["가격 또는 손절 unavailable"])

    entry = entry_price or latest
    risk_per_share = max(entry - initial_stop, 0)
    if risk_per_share <= 0:
        return ExitPlan(initial_stop, initial_stop, initial_stop, None, None, None, 0, None, "진입가와 손절가 확인 필요", "신호 악화 시 관망", "고위험 이벤트 전 신규 진입 금지", "계산 불가", 20, ["진입가가 손절가보다 높아야 함"], ["R 계산 불가"])

    break_even_trigger = entry + risk_per_share
    vol_confirm = _volume_confirmed(history)
    hard_stop = initial_stop
    if latest >= break_even_trigger and vol_confirm:
        hard_stop = max(hard_stop, entry)

    first_r = entry + risk_per_share * 1.5
    first_tp = min(first_r, resistance) if resistance and resistance > entry else first_r
    second_tp = entry + risk_per_share * 2.5
    if resistance and resistance > first_tp:
        second_tp = min(second_tp, resistance * 1.03)

    atr = atr_pct(history, 14)
    if atr is None:
        warnings.append("ATR unavailable, 트레일링 스탑은 기존 손절 기준 사용")
        trailing_stop = hard_stop
    else:
        trailing_candidate = latest * (1 - (atr * 2.0) / 100.0)
        trailing_stop = max(hard_stop, trailing_candidate)

    if market_regime in {"Extreme Risk-Off", "Risk-Off"}:
        runner_pct = 0.25
    elif leadership_score is not None and leadership_score >= 70:
        runner_pct = 0.45
    else:
        runner_pct = 0.35
    if catalyst_risk in {"High", "Critical"}:
        runner_pct *= 0.35
        warnings.append("고위험 이벤트로 runner 비중 축소")
    runner_pct = clamp(runner_pct, 0.0, 0.50)

    last_day = _last_date(history)
    time_stop = (last_day + pd.tseries.offsets.BDay(expected_holding_days)).date()
    status = "위험 관리 구간"
    if latest >= first_tp:
        status = "수익 보호 구간"
    if latest >= second_tp and runner_pct > 0.25:
        status = "추세 러너 구간"

    invalidation = [
        f"종가가 hard stop {hard_stop:,.0f} 이탈",
        "품질조정 손익비 1.2x 하회",
        "공시/이벤트 리스크 High 이상",
    ]
    confidence = clamp(72 + (8 if atr is not None else -12) + (8 if vol_confirm else -4) - len(warnings) * 8, 25, 90)
    return ExitPlan(
        initial_stop=round(initial_stop, 2),
        hard_stop=round(hard_stop, 2),
        trailing_stop=round(trailing_stop, 2),
        time_stop_date=time_stop,
        first_take_profit=round(first_tp, 2),
        second_take_profit=round(second_tp, 2),
        runner_position_pct=round(runner_pct, 4),
        break_even_move_trigger=round(break_even_trigger, 2),
        stop_to_break_even_rule="1R 이상 상승 + 거래량 20일 평균 이상이면 손절선을 진입가로 상향",
        exit_on_signal_deterioration_rule="주도력 45점 미만 또는 시장 국면 방어 전환 시 비중 축소 검토",
        exit_on_event_risk_rule="High 이상 이벤트 전 기대값이 양수가 아니면 runner 축소/청산",
        status=status,
        exit_confidence=round(confidence, 2),
        invalidation_rules=invalidation,
        warnings=warnings,
    )

