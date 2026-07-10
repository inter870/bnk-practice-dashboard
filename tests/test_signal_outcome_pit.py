import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.monitoring.signal_ledger import (
    SignalRecord,
    compute_forward_outcomes,
    list_recent_signals,
    signal_record_from_mapping,
    store_signal,
)


def make_record_mapping(generated_at: str = "2024-01-05T16:00:00") -> dict[str, object]:
    return {
        "signal_id": "signal-1",
        "generated_at": generated_at,
        "code": "005930",
        "name": "Samsung Electronics",
        "action": "Accumulate Small",
        "score": 72,
        "confidence": 68,
        "market_regime": "Neutral",
        "leadership_score": None,
        "expected_edge": 4.5,
        "risk_reward_ratio": 2.0,
        "position_size_recommendation": 3.0,
        "data_quality_score": 90,
        "reasons_positive": '["quality", "momentum"]',
        "reasons_negative": '["valuation"]',
        "source_snapshot_id": "snapshot-1",
    }


def make_history(index: pd.DatetimeIndex, values: list[float]) -> pd.DataFrame:
    close = pd.Series(values, index=index, dtype=float)
    return pd.DataFrame(
        {
            "Open": close,
            "High": close + 2,
            "Low": close - 2,
            "Close": close,
            "Volume": 1000,
        },
        index=index,
    )


class SignalOutcomePointInTimeTests(unittest.TestCase):
    def test_mapping_conversion_preserves_recent_signal_dict_contract(self):
        record = signal_record_from_mapping(make_record_mapping())
        self.assertIsInstance(record, SignalRecord)
        self.assertEqual(record.reasons_positive, ["quality", "momentum"])
        self.assertEqual(record.reasons_negative, ["valuation"])

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.sqlite3"
            store_signal(db, record)
            rows = list_recent_signals(db)

        self.assertIsInstance(rows[0], dict)
        restored = signal_record_from_mapping(rows[0])
        self.assertEqual(restored, record)

    def test_fixed_horizons_ignore_signal_day_pre_signal_and_later_future_rows(self):
        pre_signal = pd.DatetimeIndex(["2024-01-03", "2024-01-05"])
        post_signal = pd.bdate_range("2024-01-08", periods=61)
        index = pre_signal.append(post_signal)
        values = [1_000_000, 2_000_000, *[float(value) for value in range(100, 161)]]
        history = make_history(index, values).iloc[::-1]

        outcomes = compute_forward_outcomes(make_record_mapping(), history)
        by_horizon = {outcome.horizon: outcome for outcome in outcomes}

        self.assertEqual(list(by_horizon), ["1d", "5d", "20d", "60d"])
        self.assertAlmostEqual(by_horizon["1d"].forward_return, 1.0)
        self.assertAlmostEqual(by_horizon["5d"].forward_return, 5.0)
        self.assertAlmostEqual(by_horizon["20d"].forward_return, 20.0)
        self.assertAlmostEqual(by_horizon["60d"].forward_return, 60.0)

    def test_incomplete_horizons_remain_unavailable(self):
        post_signal = pd.bdate_range("2024-01-08", periods=6)
        history = make_history(post_signal, [100, 101, 102, 103, 104, 105])

        outcomes = compute_forward_outcomes(make_record_mapping(), history)
        by_horizon = {outcome.horizon: outcome for outcome in outcomes}

        self.assertIsNotNone(by_horizon["1d"].forward_return)
        self.assertIsNotNone(by_horizon["5d"].forward_return)
        for horizon in ("20d", "60d"):
            self.assertIsNone(by_horizon[horizon].forward_return)
            self.assertIsNone(by_horizon[horizon].benchmark_relative_return)
            self.assertIsNone(by_horizon[horizon].action_correct)

    def test_benchmark_prices_and_costs_are_safe_and_horizon_aligned(self):
        post_signal = pd.bdate_range("2024-01-08", periods=2)
        history = make_history(post_signal, [100, 102])
        benchmark = make_history(post_signal, [200, 202])

        outcome = compute_forward_outcomes(
            make_record_mapping(),
            history,
            benchmark_history=benchmark,
            target_price="101",
            stop_price="95",
            entry_price="100",
            cost_bps="25",
        )[0]
        self.assertAlmostEqual(outcome.forward_return, 1.75)
        self.assertAlmostEqual(outcome.benchmark_relative_return, 0.75)
        self.assertTrue(outcome.hit_target_before_stop)
        self.assertAlmostEqual(outcome.realized_r_multiple, 0.35)

        invalid_inputs = compute_forward_outcomes(
            make_record_mapping(),
            history,
            benchmark_history=pd.DataFrame({"Close": ["bad", "bad"]}, index=post_signal),
            target_price="bad",
            stop_price=float("nan"),
            entry_price=object(),
            cost_bps=float("inf"),
        )[0]
        self.assertAlmostEqual(invalid_inputs.forward_return, 2.0)
        self.assertIsNone(invalid_inputs.benchmark_relative_return)
        self.assertIsNone(invalid_inputs.hit_target_before_stop)
        self.assertIsNone(invalid_inputs.realized_r_multiple)

    def test_entry_bar_intraday_high_is_not_counted_after_close_entry(self):
        dates = pd.bdate_range("2024-01-08", periods=2)
        history = pd.DataFrame(
            {
                "Open": [99, 100],
                "High": [110, 100],
                "Low": [95, 98],
                "Close": [100, 99],
                "Volume": [1_000, 1_000],
            },
            index=dates,
        )
        outcome = compute_forward_outcomes(
            make_record_mapping(),
            history,
            target_price=105,
            stop_price=90,
            entry_price=100,
        )[0]

        self.assertFalse(outcome.hit_target_before_stop)
        self.assertFalse(outcome.hit_stop_before_target)
        self.assertEqual(outcome.max_favorable_excursion, 0.0)
        self.assertAlmostEqual(outcome.max_adverse_excursion, -2.0)


if __name__ == "__main__":
    unittest.main()
