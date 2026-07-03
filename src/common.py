from __future__ import annotations

from typing import Any

import pandas as pd


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        return None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def find_ohlcv_columns(df: pd.DataFrame) -> tuple[str, str, str, str, str]:
    if df is None or df.empty:
        return "Open", "High", "Low", "Close", "Volume"
    lower_map = {str(c).lower(): c for c in df.columns}
    close = lower_map.get("close", df.columns[0])
    open_ = lower_map.get("open", close)
    high = lower_map.get("high", close)
    low = lower_map.get("low", close)
    volume = lower_map.get("volume", close)
    return str(open_), str(high), str(low), str(close), str(volume)


def pct_change(close: pd.Series, periods: int) -> float | None:
    if close is None:
        return None
    close = close.dropna()
    if len(close) <= periods:
        return None
    base = safe_float(close.iloc[-periods - 1])
    latest = safe_float(close.iloc[-1])
    if base in (None, 0) or latest is None:
        return None
    return (latest / base - 1.0) * 100.0


def calc_returns(close: pd.Series) -> dict[str, float | None]:
    return {
        "1d": pct_change(close, 1),
        "5d": pct_change(close, 5),
        "20d": pct_change(close, 20),
        "60d": pct_change(close, 60),
    }


def atr_pct(history: pd.DataFrame, window: int = 14) -> float | None:
    if history is None or history.empty:
        return None
    _, high_c, low_c, close_c, _ = find_ohlcv_columns(history)
    if high_c not in history.columns or low_c not in history.columns or close_c not in history.columns:
        return None
    data = history[[high_c, low_c, close_c]].dropna().tail(max(window + 2, 20))
    if len(data) < 5:
        return None
    high = data[high_c].astype(float)
    low = data[low_c].astype(float)
    close = data[close_c].astype(float)
    prev_close = close.shift(1)
    true_range = pd.concat([(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    latest = safe_float(close.iloc[-1])
    atr = safe_float(true_range.tail(window).mean())
    if latest in (None, 0) or atr is None:
        return None
    return atr / latest * 100.0


def latest_close(history: pd.DataFrame) -> float | None:
    if history is None or history.empty:
        return None
    _, _, _, close_c, _ = find_ohlcv_columns(history)
    if close_c not in history.columns:
        return None
    close = history[close_c].dropna()
    if close.empty:
        return None
    return safe_float(close.iloc[-1])


def latest_volume(history: pd.DataFrame) -> float | None:
    if history is None or history.empty:
        return None
    _, _, _, _, volume_c = find_ohlcv_columns(history)
    if volume_c not in history.columns:
        return None
    volume = history[volume_c].dropna()
    if volume.empty:
        return None
    return safe_float(volume.iloc[-1])


def average_traded_value(history: pd.DataFrame, window: int = 20) -> float | None:
    if history is None or history.empty:
        return None
    _, _, _, close_c, volume_c = find_ohlcv_columns(history)
    if close_c not in history.columns or volume_c not in history.columns:
        return None
    data = history[[close_c, volume_c]].dropna().tail(window)
    if data.empty:
        return None
    value = (data[close_c].astype(float) * data[volume_c].astype(float)).mean()
    return safe_float(value)

