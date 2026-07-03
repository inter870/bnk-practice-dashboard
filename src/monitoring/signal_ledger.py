from __future__ import annotations

from dataclasses import asdict, dataclass, field
from contextlib import closing
from datetime import datetime
import json
import sqlite3
from pathlib import Path
from typing import Any
import uuid

import pandas as pd

from src.common import calc_returns, find_ohlcv_columns, latest_close, safe_float


@dataclass
class SignalRecord:
    signal_id: str
    generated_at: str
    code: str
    name: str
    action: str
    score: float
    confidence: float
    market_regime: str
    leadership_score: float | None
    expected_edge: float | None
    risk_reward_ratio: float | None
    position_size_recommendation: float
    data_quality_score: float | None
    reasons_positive: list[str] = field(default_factory=list)
    reasons_negative: list[str] = field(default_factory=list)
    source_snapshot_id: str | None = None


@dataclass
class SignalOutcome:
    signal_id: str
    code: str
    horizon: str
    forward_return: float | None
    benchmark_relative_return: float | None
    hit_target_before_stop: bool | None
    hit_stop_before_target: bool | None
    max_favorable_excursion: float | None
    max_adverse_excursion: float | None
    realized_r_multiple: float | None
    action_correct: bool | None


def create_signal_record(
    *,
    code: str,
    name: str,
    action: str,
    score: float,
    confidence: float,
    market_regime: str,
    leadership_score: float | None = None,
    expected_edge: float | None = None,
    risk_reward_ratio: float | None = None,
    position_size_recommendation: float = 0.0,
    data_quality_score: float | None = None,
    reasons_positive: list[str] | None = None,
    reasons_negative: list[str] | None = None,
    source_snapshot_id: str | None = None,
) -> SignalRecord:
    return SignalRecord(
        signal_id=str(uuid.uuid4()),
        generated_at=datetime.now().isoformat(timespec="seconds"),
        code=code,
        name=name,
        action=action,
        score=score,
        confidence=confidence,
        market_regime=market_regime,
        leadership_score=leadership_score,
        expected_edge=expected_edge,
        risk_reward_ratio=risk_reward_ratio,
        position_size_recommendation=position_size_recommendation,
        data_quality_score=data_quality_score,
        reasons_positive=reasons_positive or [],
        reasons_negative=reasons_negative or [],
        source_snapshot_id=source_snapshot_id,
    )


def init_db(db_path: str | Path) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signals (
                signal_id TEXT PRIMARY KEY,
                generated_at TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                action TEXT NOT NULL,
                score REAL NOT NULL,
                confidence REAL NOT NULL,
                market_regime TEXT NOT NULL,
                leadership_score REAL,
                expected_edge REAL,
                risk_reward_ratio REAL,
                position_size_recommendation REAL,
                data_quality_score REAL,
                reasons_positive TEXT,
                reasons_negative TEXT,
                source_snapshot_id TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS outcomes (
                signal_id TEXT NOT NULL,
                code TEXT NOT NULL,
                horizon TEXT NOT NULL,
                forward_return REAL,
                benchmark_relative_return REAL,
                hit_target_before_stop INTEGER,
                hit_stop_before_target INTEGER,
                max_favorable_excursion REAL,
                max_adverse_excursion REAL,
                realized_r_multiple REAL,
                action_correct INTEGER,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (signal_id, horizon)
            )
            """
        )
        conn.commit()


def store_signal(db_path: str | Path, record: SignalRecord) -> None:
    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO signals VALUES (
                :signal_id, :generated_at, :code, :name, :action, :score, :confidence, :market_regime,
                :leadership_score, :expected_edge, :risk_reward_ratio, :position_size_recommendation,
                :data_quality_score, :reasons_positive, :reasons_negative, :source_snapshot_id
            )
            """,
            {
                **asdict(record),
                "reasons_positive": json.dumps(record.reasons_positive, ensure_ascii=False),
                "reasons_negative": json.dumps(record.reasons_negative, ensure_ascii=False),
            },
        )
        conn.commit()


def store_outcome(db_path: str | Path, outcome: SignalOutcome) -> None:
    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO outcomes VALUES (
                :signal_id, :code, :horizon, :forward_return, :benchmark_relative_return,
                :hit_target_before_stop, :hit_stop_before_target, :max_favorable_excursion,
                :max_adverse_excursion, :realized_r_multiple, :action_correct, :updated_at
            )
            """,
            {
                **asdict(outcome),
                "hit_target_before_stop": None if outcome.hit_target_before_stop is None else int(outcome.hit_target_before_stop),
                "hit_stop_before_target": None if outcome.hit_stop_before_target is None else int(outcome.hit_stop_before_target),
                "action_correct": None if outcome.action_correct is None else int(outcome.action_correct),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
        conn.commit()


def list_recent_signals(db_path: str | Path, limit: int = 50) -> list[dict[str, Any]]:
    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM signals ORDER BY generated_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def _first_hit(data: pd.DataFrame, target_price: float | None, stop_price: float | None) -> tuple[bool | None, bool | None]:
    if data is None or data.empty or target_price is None or stop_price is None:
        return None, None
    _, high_c, low_c, _, _ = find_ohlcv_columns(data)
    for _, row in data.iterrows():
        high = safe_float(row.get(high_c))
        low = safe_float(row.get(low_c))
        hit_target = high is not None and high >= target_price
        hit_stop = low is not None and low <= stop_price
        if hit_target and hit_stop:
            return False, True
        if hit_target:
            return True, False
        if hit_stop:
            return False, True
    return False, False


def compute_forward_outcome(
    record: SignalRecord,
    history_after_signal: pd.DataFrame,
    *,
    horizon_days: int,
    benchmark_after_signal: pd.DataFrame | None = None,
    target_price: float | None = None,
    stop_price: float | None = None,
    entry_price: float | None = None,
) -> SignalOutcome:
    horizon = f"{horizon_days}d"
    if history_after_signal is None or history_after_signal.empty:
        return SignalOutcome(record.signal_id, record.code, horizon, None, None, None, None, None, None, None, None)
    _, high_c, low_c, close_c, _ = find_ohlcv_columns(history_after_signal)
    data = history_after_signal.dropna(subset=[close_c]).head(horizon_days + 1)
    if len(data) < 2:
        return SignalOutcome(record.signal_id, record.code, horizon, None, None, None, None, None, None, None, None)
    start = entry_price or safe_float(data[close_c].iloc[0])
    end = safe_float(data[close_c].iloc[-1])
    if start in (None, 0) or end is None:
        fwd = None
    else:
        fwd = (end / start - 1.0) * 100.0

    bench_rel = None
    if benchmark_after_signal is not None and not benchmark_after_signal.empty and fwd is not None:
        _, _, _, bench_close_c, _ = find_ohlcv_columns(benchmark_after_signal)
        bench = benchmark_after_signal.dropna(subset=[bench_close_c]).head(horizon_days + 1)
        if len(bench) >= 2:
            base = safe_float(bench[bench_close_c].iloc[0])
            last = safe_float(bench[bench_close_c].iloc[-1])
            if base not in (None, 0) and last is not None:
                bench_rel = fwd - ((last / base - 1.0) * 100.0)

    highs = data[high_c].astype(float) if high_c in data.columns else data[close_c].astype(float)
    lows = data[low_c].astype(float) if low_c in data.columns else data[close_c].astype(float)
    mfe = None if start in (None, 0) else (safe_float(highs.max()) / start - 1.0) * 100.0
    mae = None if start in (None, 0) else (safe_float(lows.min()) / start - 1.0) * 100.0
    hit_target, hit_stop = _first_hit(data, target_price, stop_price)
    risk_per_share = None if stop_price is None or start is None else start - stop_price
    realized_r = None
    if risk_per_share not in (None, 0) and end is not None:
        realized_r = (end - start) / risk_per_share
    action_correct = None
    if fwd is not None:
        if record.action in {"Strong Buy", "Buy on Pullback", "Accumulate Small", "매수", "소액 분할"}:
            action_correct = fwd > 0
        elif record.action in {"Trim", "Sell / Avoid", "매도", "회피"}:
            action_correct = fwd <= 0
        else:
            action_correct = abs(fwd) < 3
    return SignalOutcome(record.signal_id, record.code, horizon, fwd, bench_rel, hit_target, hit_stop, mfe, mae, realized_r, action_correct)


def get_kill_switch_state(db_path: str | Path, *, min_samples: int = 8, hit_rate_floor: float = 0.35) -> dict[str, Any]:
    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM outcomes WHERE horizon IN ('5d', '20d') AND action_correct IS NOT NULL ORDER BY updated_at DESC LIMIT 80"
        ).fetchall()
    if len(rows) < min_samples:
        return {"active": False, "reason": "성과 표본 부족", "sample_size": len(rows), "hit_rate": None}
    hit_rate = sum(int(row["action_correct"]) for row in rows) / len(rows)
    avg_return_values = [safe_float(row["forward_return"]) for row in rows if safe_float(row["forward_return"]) is not None]
    avg_return = sum(avg_return_values) / len(avg_return_values) if avg_return_values else None
    active = hit_rate < hit_rate_floor and (avg_return is None or avg_return <= 0)
    reason = "최근 신호 적중률/평균성과 저하" if active else "정상"
    return {"active": active, "reason": reason, "sample_size": len(rows), "hit_rate": round(hit_rate, 3), "avg_forward_return": None if avg_return is None else round(avg_return, 3)}
