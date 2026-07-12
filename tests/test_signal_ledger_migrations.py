from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from src.monitoring.signal_ledger import (
    SIGNAL_SCHEMA_VERSION,
    SignalOutcome,
    create_signal_record,
    init_db,
    list_recent_signals,
    store_outcome,
    store_signal,
)


class SignalLedgerMigrationTests(unittest.TestCase):
    def test_legacy_database_migrates_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "legacy.sqlite3"
            with closing(sqlite3.connect(db)) as conn:
                conn.execute(
                    "CREATE TABLE signals (signal_id TEXT PRIMARY KEY, generated_at TEXT NOT NULL, "
                    "code TEXT NOT NULL, name TEXT NOT NULL, action TEXT NOT NULL, score REAL NOT NULL, "
                    "confidence REAL NOT NULL, market_regime TEXT NOT NULL, leadership_score REAL, "
                    "expected_edge REAL, risk_reward_ratio REAL, position_size_recommendation REAL, "
                    "data_quality_score REAL, reasons_positive TEXT, reasons_negative TEXT, source_snapshot_id TEXT)"
                )
                conn.execute(
                    "CREATE TABLE outcomes (signal_id TEXT NOT NULL, code TEXT NOT NULL, horizon TEXT NOT NULL, "
                    "forward_return REAL, benchmark_relative_return REAL, hit_target_before_stop INTEGER, "
                    "hit_stop_before_target INTEGER, max_favorable_excursion REAL, max_adverse_excursion REAL, "
                    "realized_r_multiple REAL, action_correct INTEGER, updated_at TEXT NOT NULL, "
                    "PRIMARY KEY (signal_id, horizon))"
                )
                conn.commit()
            init_db(db)
            init_db(db)
            with closing(sqlite3.connect(db)) as conn:
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                signal_columns = {row[1] for row in conn.execute("PRAGMA table_info(signals)")}
            self.assertEqual(SIGNAL_SCHEMA_VERSION, version)
            self.assertIn("signal_key", signal_columns)
            self.assertIn("cost_policy_id", signal_columns)

    def test_same_signal_key_is_upserted_without_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.sqlite3"
            kwargs = dict(
                code="005930",
                name="삼성전자",
                action="WATCH",
                score=70,
                confidence=60,
                market_regime="Neutral",
                decision_at="2026-07-10T06:00:00+00:00",
                source_snapshot_id="snapshot-1",
                model_version="baseline-v1",
                score_version="score-v1",
            )
            first = create_signal_record(**kwargs)
            second = create_signal_record(**kwargs)
            self.assertEqual(first.signal_key, second.signal_key)
            store_signal(db, first)
            store_signal(db, second)
            self.assertEqual(1, len(list_recent_signals(db)))

    def test_pending_replay_does_not_erase_completed_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.sqlite3"
            complete = SignalOutcome(
                "signal-1", "005930", "5d", 3.0, 1.0, True, False, 4.0, -1.0, 1.5, True,
                outcome_status="COMPLETE",
            )
            pending = SignalOutcome(
                "signal-1", "005930", "5d", None, None, None, None, None, None, None, None,
                outcome_status="PENDING",
            )
            store_outcome(db, complete)
            store_outcome(db, pending)
            with closing(sqlite3.connect(db)) as conn:
                row = conn.execute(
                    "SELECT forward_return, outcome_status FROM outcomes WHERE signal_id=? AND horizon=?",
                    ("signal-1", "5d"),
                ).fetchone()
            self.assertEqual(3.0, row[0])
            self.assertEqual("COMPLETE", row[1])


if __name__ == "__main__":
    unittest.main()
