import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.monitoring.signal_ledger import (
    SignalOutcome,
    compute_forward_outcome,
    create_signal_record,
    get_kill_switch_state,
    list_recent_signals,
    store_outcome,
    store_signal,
)


def make_history(values: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(values), freq="B")
    close = pd.Series(values, index=idx)
    return pd.DataFrame(
        {
            "Open": close,
            "High": close + 2,
            "Low": close - 2,
            "Close": close,
            "Volume": 1000,
        },
        index=idx,
    )


class SignalMonitoringTests(unittest.TestCase):
    def test_signal_is_stored_with_required_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.sqlite3"
            record = create_signal_record(code="005930", name="삼성전자", action="Accumulate Small", score=66, confidence=70, market_regime="Neutral")
            store_signal(db, record)
            rows = list_recent_signals(db)
            self.assertEqual(rows[0]["signal_id"], record.signal_id)
            self.assertEqual(rows[0]["code"], "005930")

    def test_forward_outcome_and_target_before_stop_logic(self):
        record = create_signal_record(code="000001", name="테스트", action="Accumulate Small", score=70, confidence=75, market_regime="Neutral")
        hist = make_history([100, 105, 112, 108, 115])
        outcome = compute_forward_outcome(record, hist, horizon_days=4, target_price=110, stop_price=95, entry_price=100)
        self.assertTrue(outcome.hit_target_before_stop)
        self.assertFalse(outcome.hit_stop_before_target)
        self.assertGreater(outcome.forward_return, 0)

    def test_kill_switch_handles_insufficient_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = get_kill_switch_state(Path(tmp) / "ledger.sqlite3")
            self.assertFalse(state["active"])
            self.assertEqual(state["sample_size"], 0)

    def test_negative_performance_triggers_kill_switch(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.sqlite3"
            for idx in range(10):
                record = create_signal_record(code=f"{idx:06d}", name="테스트", action="Accumulate Small", score=70, confidence=75, market_regime="Neutral")
                store_signal(db, record)
                outcome = SignalOutcome(record.signal_id, record.code, "5d", -3.0, -2.0, False, True, 1.0, -5.0, -1.0, False)
                store_outcome(db, outcome)
            state = get_kill_switch_state(db, min_samples=8)
            self.assertTrue(state["active"])


if __name__ == "__main__":
    unittest.main()

