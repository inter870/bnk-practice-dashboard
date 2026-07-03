import unittest

import pandas as pd

from src.exits import build_exit_plan


def make_history(latest: float = 112, volume: int = 200_000, periods: int = 40) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=periods, freq="B")
    close = pd.Series([100 + (latest - 100) * i / (periods - 1) for i in range(periods)], index=idx)
    return pd.DataFrame(
        {
            "Open": close,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": volume,
        },
        index=idx,
    )


class ExitPlanTests(unittest.TestCase):
    def test_one_r_move_triggers_break_even_only_when_volume_confirms(self):
        risk_plan = {"latest": 112, "stop": 90, "resistance": 130}
        confirmed = build_exit_plan(risk_plan, make_history(volume=200_000), entry_price=100)
        weak_volume_hist = make_history(volume=200_000)
        weak_volume_hist.iloc[-1, weak_volume_hist.columns.get_loc("Volume")] = 1
        not_confirmed = build_exit_plan(risk_plan, weak_volume_hist, entry_price=100)
        self.assertGreaterEqual(confirmed.hard_stop, 100)
        self.assertLess(not_confirmed.hard_stop, 100)

    def test_atr_trailing_stop_never_widens_risk_after_entry(self):
        plan = build_exit_plan({"latest": 112, "stop": 90, "resistance": 130}, make_history(), entry_price=100)
        self.assertGreaterEqual(plan.trailing_stop, plan.initial_stop)

    def test_time_stop_is_created(self):
        plan = build_exit_plan({"latest": 112, "stop": 90, "resistance": 130}, make_history(), entry_price=100, expected_holding_days=10)
        self.assertIsNotNone(plan.time_stop_date)

    def test_high_risk_catalyst_reduces_runner_position(self):
        normal = build_exit_plan({"latest": 112, "stop": 90, "resistance": 130}, make_history(), entry_price=100, catalyst_risk="Low")
        high = build_exit_plan({"latest": 112, "stop": 90, "resistance": 130}, make_history(), entry_price=100, catalyst_risk="High")
        self.assertLess(high.runner_position_pct, normal.runner_position_pct)


if __name__ == "__main__":
    unittest.main()

