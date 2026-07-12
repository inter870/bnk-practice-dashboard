from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from contextlib import closing
from datetime import datetime
from datetime import timezone
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any
import uuid

import pandas as pd

from src.common import calc_returns, find_ohlcv_columns, latest_close, safe_float


FORWARD_OUTCOME_HORIZONS = (1, 5, 20, 60)


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
    signal_key: str | None = None
    decision_at: str | None = None
    next_executable_at: str | None = None
    model_version: str = "legacy"
    feature_version: str = "legacy"
    score_version: str = "legacy"
    universe_version: str = "unknown"
    data_status: str = "UNAVAILABLE"
    expected_return_gross: float | None = None
    expected_return_net: float | None = None
    benchmark_expected_return: float | None = None
    downside_estimate: float | None = None
    cost_policy_id: str | None = None
    portfolio_snapshot_id: str | None = None


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
    entry_at: str | None = None
    exit_at: str | None = None
    entry_price: float | None = None
    realized_cost: float | None = None
    estimated_slippage: float | None = None
    outcome_status: str = "PENDING"
    evaluation_version: str = "p0-v1"
    price_source: str | None = None
    benchmark_source: str | None = None


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
    decision_at: str | None = None,
    model_version: str = "legacy",
    feature_version: str = "legacy",
    score_version: str = "legacy",
    universe_version: str = "unknown",
    data_status: str = "UNAVAILABLE",
    portfolio_snapshot_id: str | None = None,
    cost_policy_id: str | None = None,
    expected_return_gross: float | None = None,
    expected_return_net: float | None = None,
) -> SignalRecord:
    generated_at = decision_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    canonical_key = "|".join(
        (
            str(code),
            generated_at,
            str(action),
            str(model_version),
            str(score_version),
            str(source_snapshot_id or ""),
            str(portfolio_snapshot_id or ""),
        )
    )
    signal_key = hashlib.sha256(canonical_key.encode("utf-8")).hexdigest()
    return SignalRecord(
        signal_id=str(uuid.uuid4()),
        generated_at=generated_at,
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
        signal_key=signal_key,
        decision_at=generated_at,
        model_version=model_version,
        feature_version=feature_version,
        score_version=score_version,
        universe_version=universe_version,
        data_status=data_status,
        cost_policy_id=cost_policy_id,
        portfolio_snapshot_id=portfolio_snapshot_id,
        expected_return_gross=expected_return_gross,
        expected_return_net=expected_return_net,
    )


def _finite_float(value: Any) -> float | None:
    number = safe_float(value)
    if number is None or not math.isfinite(number):
        return None
    return number


def _optional_float(value: Any) -> float | None:
    return _finite_float(value) if value is not None else None


def _reason_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        if not value.strip():
            return []
        try:
            value = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return [value]
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def signal_record_from_mapping(value: Mapping[str, Any] | SignalRecord) -> SignalRecord:
    """Restore a SignalRecord from the dict contract used by list_recent_signals."""
    if isinstance(value, SignalRecord):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("signal record must be a SignalRecord or mapping")

    required_text = ("signal_id", "generated_at", "code", "name", "action", "market_regime")
    missing = [key for key in required_text if value.get(key) in (None, "")]
    if missing:
        raise ValueError(f"signal record is missing required fields: {', '.join(missing)}")

    score = _finite_float(value.get("score"))
    confidence = _finite_float(value.get("confidence"))
    if score is None or confidence is None:
        raise ValueError("signal record score and confidence must be finite numbers")

    position_size = _finite_float(value.get("position_size_recommendation", 0.0))
    return SignalRecord(
        signal_id=str(value["signal_id"]),
        generated_at=str(value["generated_at"]),
        code=str(value["code"]),
        name=str(value["name"]),
        action=str(value["action"]),
        score=score,
        confidence=confidence,
        market_regime=str(value["market_regime"]),
        leadership_score=_optional_float(value.get("leadership_score")),
        expected_edge=_optional_float(value.get("expected_edge")),
        risk_reward_ratio=_optional_float(value.get("risk_reward_ratio")),
        position_size_recommendation=0.0 if position_size is None else position_size,
        data_quality_score=_optional_float(value.get("data_quality_score")),
        reasons_positive=_reason_list(value.get("reasons_positive")),
        reasons_negative=_reason_list(value.get("reasons_negative")),
        source_snapshot_id=(
            None if value.get("source_snapshot_id") in (None, "") else str(value["source_snapshot_id"])
        ),
        signal_key=None if value.get("signal_key") in (None, "") else str(value["signal_key"]),
        decision_at=None if value.get("decision_at") in (None, "") else str(value["decision_at"]),
        next_executable_at=None if value.get("next_executable_at") in (None, "") else str(value["next_executable_at"]),
        model_version=str(value.get("model_version") or "legacy"),
        feature_version=str(value.get("feature_version") or "legacy"),
        score_version=str(value.get("score_version") or "legacy"),
        universe_version=str(value.get("universe_version") or "unknown"),
        data_status=str(value.get("data_status") or "UNAVAILABLE"),
        expected_return_gross=_optional_float(value.get("expected_return_gross")),
        expected_return_net=_optional_float(value.get("expected_return_net")),
        benchmark_expected_return=_optional_float(value.get("benchmark_expected_return")),
        downside_estimate=_optional_float(value.get("downside_estimate")),
        cost_policy_id=None if value.get("cost_policy_id") in (None, "") else str(value["cost_policy_id"]),
        portfolio_snapshot_id=None if value.get("portfolio_snapshot_id") in (None, "") else str(value["portfolio_snapshot_id"]),
    )


SIGNAL_SCHEMA_VERSION = 2


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: Mapping[str, str]) -> None:
    existing = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, declaration in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")


def init_db(db_path: str | Path) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
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
        _ensure_columns(
            conn,
            "signals",
            {
                "signal_key": "TEXT",
                "decision_at": "TEXT",
                "next_executable_at": "TEXT",
                "model_version": "TEXT",
                "feature_version": "TEXT",
                "score_version": "TEXT",
                "universe_version": "TEXT",
                "data_status": "TEXT",
                "expected_return_gross": "REAL",
                "expected_return_net": "REAL",
                "benchmark_expected_return": "REAL",
                "downside_estimate": "REAL",
                "cost_policy_id": "TEXT",
                "portfolio_snapshot_id": "TEXT",
            },
        )
        _ensure_columns(
            conn,
            "outcomes",
            {
                "entry_at": "TEXT",
                "exit_at": "TEXT",
                "entry_price": "REAL",
                "realized_cost": "REAL",
                "estimated_slippage": "REAL",
                "outcome_status": "TEXT",
                "evaluation_version": "TEXT",
                "price_source": "TEXT",
                "benchmark_source": "TEXT",
            },
        )
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_signals_signal_key ON signals(signal_key)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_code_generated ON signals(code, generated_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_outcomes_horizon_updated ON outcomes(horizon, updated_at)")
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (SIGNAL_SCHEMA_VERSION, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        conn.execute(f"PRAGMA user_version={SIGNAL_SCHEMA_VERSION}")
        conn.commit()


def store_signal(db_path: str | Path, record: SignalRecord) -> None:
    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        payload = {
            **asdict(record),
            "reasons_positive": json.dumps(record.reasons_positive, ensure_ascii=False),
            "reasons_negative": json.dumps(record.reasons_negative, ensure_ascii=False),
        }
        columns = tuple(payload)
        assignments = ", ".join(f"{column}=excluded.{column}" for column in columns if column not in {"signal_id", "signal_key"})
        conflict = "signal_key" if record.signal_key else "signal_id"
        conn.execute(
            f"INSERT INTO signals ({', '.join(columns)}) VALUES ({', '.join(':' + column for column in columns)}) "
            f"ON CONFLICT({conflict}) DO UPDATE SET {assignments}",
            payload,
        )
        conn.commit()


def store_outcome(db_path: str | Path, outcome: SignalOutcome) -> None:
    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        payload = {
            **asdict(outcome),
            "hit_target_before_stop": None if outcome.hit_target_before_stop is None else int(outcome.hit_target_before_stop),
            "hit_stop_before_target": None if outcome.hit_stop_before_target is None else int(outcome.hit_stop_before_target),
            "action_correct": None if outcome.action_correct is None else int(outcome.action_correct),
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        columns = tuple(payload)
        assignments = ", ".join(
            (
                "outcome_status=CASE "
                "WHEN outcomes.outcome_status='COMPLETE' AND excluded.outcome_status='PENDING' "
                "THEN outcomes.outcome_status ELSE COALESCE(excluded.outcome_status, outcomes.outcome_status) END"
                if column == "outcome_status"
                else f"{column}=COALESCE(excluded.{column}, outcomes.{column})"
            )
            for column in columns
            if column not in {"signal_id", "horizon", "updated_at"}
        )
        assignments += ", updated_at=excluded.updated_at"
        conn.execute(
            f"INSERT INTO outcomes ({', '.join(columns)}) VALUES ({', '.join(':' + column for column in columns)}) "
            f"ON CONFLICT(signal_id, horizon) DO UPDATE SET {assignments}",
            payload,
        )
        conn.commit()


def list_recent_signals(db_path: str | Path, limit: int = 50) -> list[dict[str, Any]]:
    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM signals ORDER BY generated_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def _price(value: Any) -> float | None:
    number = _finite_float(value)
    if number is None or number <= 0:
        return None
    return number


def _empty_outcome(record: SignalRecord, horizon_days: int) -> SignalOutcome:
    return SignalOutcome(
        record.signal_id,
        record.code,
        f"{horizon_days}d",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )


def _first_hit(data: pd.DataFrame, target_price: Any, stop_price: Any) -> tuple[bool | None, bool | None]:
    target = _price(target_price)
    stop = _price(stop_price)
    if data is None or data.empty or target is None or stop is None:
        return None, None
    _, high_c, low_c, _, _ = find_ohlcv_columns(data)
    for _, row in data.iterrows():
        high = _finite_float(row.get(high_c))
        low = _finite_float(row.get(low_c))
        hit_target = high is not None and high >= target
        hit_stop = low is not None and low <= stop
        if hit_target and hit_stop:
            return False, True
        if hit_target:
            return True, False
        if hit_stop:
            return False, True
    return False, False


def compute_forward_outcome(
    record: Mapping[str, Any] | SignalRecord,
    history_after_signal: pd.DataFrame,
    *,
    horizon_days: int,
    benchmark_after_signal: pd.DataFrame | None = None,
    target_price: Any = None,
    stop_price: Any = None,
    entry_price: Any = None,
    cost_bps: Any = 0.0,
) -> SignalOutcome:
    record = signal_record_from_mapping(record)
    if isinstance(horizon_days, bool):
        return _empty_outcome(record, int(horizon_days))
    try:
        horizon_days = int(horizon_days)
    except (TypeError, ValueError, OverflowError):
        return _empty_outcome(record, 0)
    if horizon_days < 1:
        return _empty_outcome(record, horizon_days)
    if not isinstance(history_after_signal, pd.DataFrame) or history_after_signal.empty:
        return _empty_outcome(record, horizon_days)

    _, high_c, low_c, close_c, _ = find_ohlcv_columns(history_after_signal)
    if close_c not in history_after_signal.columns:
        return _empty_outcome(record, horizon_days)
    data = history_after_signal.copy()
    data[close_c] = pd.to_numeric(data[close_c], errors="coerce")
    data = data.dropna(subset=[close_c]).head(horizon_days + 1)
    if len(data) < 2:
        return _empty_outcome(record, horizon_days)

    start = _price(entry_price) or _price(data[close_c].iloc[0])
    end = _price(data[close_c].iloc[-1])
    post_entry_path = data.iloc[1:].copy()
    normalized_cost_bps = _finite_float(cost_bps)
    if normalized_cost_bps is None or normalized_cost_bps < 0:
        normalized_cost_bps = 0.0
    cost_pct = normalized_cost_bps / 100.0
    if start is None or end is None:
        fwd = None
    else:
        fwd = (end / start - 1.0) * 100.0 - cost_pct

    bench_rel = None
    if isinstance(benchmark_after_signal, pd.DataFrame) and not benchmark_after_signal.empty and fwd is not None:
        _, _, _, bench_close_c, _ = find_ohlcv_columns(benchmark_after_signal)
        if bench_close_c in benchmark_after_signal.columns:
            bench = benchmark_after_signal.copy()
            bench[bench_close_c] = pd.to_numeric(bench[bench_close_c], errors="coerce")
            bench = bench.dropna(subset=[bench_close_c]).head(horizon_days + 1)
        else:
            bench = pd.DataFrame()
        if len(bench) >= 2:
            base = _price(bench[bench_close_c].iloc[0])
            last = _price(bench[bench_close_c].iloc[-1])
            if base is not None and last is not None:
                bench_rel = fwd - ((last / base - 1.0) * 100.0)

    highs = pd.to_numeric(
        post_entry_path[high_c] if high_c in post_entry_path.columns else post_entry_path[close_c],
        errors="coerce",
    )
    lows = pd.to_numeric(
        post_entry_path[low_c] if low_c in post_entry_path.columns else post_entry_path[close_c],
        errors="coerce",
    )
    highest = _price(highs.max())
    lowest = _price(lows.min())
    mfe = None if start is None or highest is None else (highest / start - 1.0) * 100.0
    mae = None if start is None or lowest is None else (lowest / start - 1.0) * 100.0
    target = _price(target_price)
    stop = _price(stop_price)
    if start is None or target is None or stop is None or not (stop < start < target):
        hit_target, hit_stop = None, None
    else:
        hit_target, hit_stop = _first_hit(post_entry_path, target, stop)
    risk_per_share = None if stop is None or start is None or stop >= start else start - stop
    realized_r = None
    if risk_per_share not in (None, 0) and end is not None:
        net_profit = end - start - (start * normalized_cost_bps / 10_000.0)
        realized_r = net_profit / risk_per_share
    action_correct = None
    if fwd is not None:
        if record.action in {"Strong Buy", "Buy on Pullback", "Accumulate Small", "매수", "소액 분할"}:
            action_correct = fwd > 0
        elif record.action in {"Trim", "Sell / Avoid", "매도", "회피"}:
            action_correct = fwd <= 0
        else:
            action_correct = abs(fwd) < 3
    return SignalOutcome(
        record.signal_id,
        record.code,
        f"{horizon_days}d",
        fwd,
        bench_rel,
        hit_target,
        hit_stop,
        mfe,
        mae,
        realized_r,
        action_correct,
        entry_at=str(data.index[0]),
        exit_at=str(data.index[-1]),
        entry_price=start,
        realized_cost=cost_pct,
        estimated_slippage=cost_pct,
        outcome_status="COMPLETE" if fwd is not None else "UNAVAILABLE",
    )


def _naive_timestamp(value: Any) -> pd.Timestamp | None:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if pd.isna(timestamp):
        return None
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("Asia/Seoul").tz_localize(None)
    return timestamp


def _history_after_generated_at(history: pd.DataFrame | None, generated_at: str) -> pd.DataFrame:
    if not isinstance(history, pd.DataFrame) or history.empty:
        return pd.DataFrame() if not isinstance(history, pd.DataFrame) else history.iloc[0:0].copy()
    generated = _naive_timestamp(generated_at)
    if generated is None:
        return history.iloc[0:0].copy()

    generated_day = generated.normalize()
    rows_by_day: dict[pd.Timestamp, tuple[pd.Timestamp, int]] = {}
    for position, index_value in enumerate(history.index):
        timestamp = _naive_timestamp(index_value)
        if timestamp is None:
            continue
        trading_day = timestamp.normalize()
        if trading_day <= generated_day:
            continue
        current = rows_by_day.get(trading_day)
        if current is None or (timestamp, position) >= current:
            rows_by_day[trading_day] = (timestamp, position)

    ordered = sorted(rows_by_day.items(), key=lambda item: item[0])
    if not ordered:
        return history.iloc[0:0].copy()
    result = history.iloc[[metadata[1] for _, metadata in ordered]].copy()
    result.index = pd.DatetimeIndex([trading_day for trading_day, _ in ordered])
    return result


def _aligned_benchmark_window(benchmark: pd.DataFrame, trading_days: pd.Index) -> pd.DataFrame | None:
    if benchmark.empty or len(trading_days) < 2:
        return None
    try:
        aligned = benchmark.reindex(trading_days)
    except (TypeError, ValueError):
        return None
    _, _, _, close_c, _ = find_ohlcv_columns(aligned)
    if close_c not in aligned.columns:
        return None
    first = _price(aligned[close_c].iloc[0])
    last = _price(aligned[close_c].iloc[-1])
    return aligned if first is not None and last is not None else None


def compute_forward_outcomes(
    record: Mapping[str, Any] | SignalRecord,
    history: pd.DataFrame,
    *,
    benchmark_history: pd.DataFrame | None = None,
    target_price: Any = None,
    stop_price: Any = None,
    entry_price: Any = None,
    cost_bps: Any = 0.0,
) -> list[SignalOutcome]:
    """Compute fixed point-in-time outcomes without reading or writing external state."""
    normalized_record = signal_record_from_mapping(record)
    history_after_signal = _history_after_generated_at(history, normalized_record.generated_at)
    benchmark_after_signal = _history_after_generated_at(benchmark_history, normalized_record.generated_at)
    outcomes: list[SignalOutcome] = []

    for horizon_days in FORWARD_OUTCOME_HORIZONS:
        required_rows = horizon_days + 1
        if len(history_after_signal) < required_rows:
            outcomes.append(_empty_outcome(normalized_record, horizon_days))
            continue
        window = history_after_signal.iloc[:required_rows]
        benchmark_window = _aligned_benchmark_window(benchmark_after_signal, window.index)
        outcomes.append(
            compute_forward_outcome(
                normalized_record,
                window,
                horizon_days=horizon_days,
                benchmark_after_signal=benchmark_window,
                target_price=target_price,
                stop_price=stop_price,
                entry_price=entry_price,
                cost_bps=cost_bps,
            )
        )
    return outcomes


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
