from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from src.institutional import (
    build_smart_money_flow_short_pressure_panel,
    calculate_days_to_cover,
    calculate_flow_z_score,
    calculate_short_squeeze_score,
    classify_fragility,
    classify_short_squeeze,
    smart_money_flow_short_pressure_api_response,
    smart_money_flow_short_pressure_panel_html,
)
from src.ui.korean_labels import module_title, status_label


def flow_inputs(asof: datetime | None = None) -> list[dict[str, object]]:
    asof_value = asof or datetime(2026, 7, 8, tzinfo=timezone.utc)
    return [
        {
            "code": "AAA",
            "name": "Alpha Accumulation",
            "sector": "Tech",
            "foreign_net_buy_history": [10, 12, 14, 18, 22, 26, 30, 34, 38, 42],
            "institution_net_buy_history": [5, 8, 10, 12, 15, 18, 20, 24, 28, 32],
            "individual_net_buy_history": [-6, -8, -10, -12, -15, -18, -20, -24, -28, -32],
            "pension_net_buy": 20,
            "program_net_buy": 30,
            "foreign_ownership_change": 0.01,
            "short_sell_ratio": 0.12,
            "short_position_ratio": 0.10,
            "short_position_quantity": 1_200_000,
            "avg_daily_volume": 150_000,
            "trading_value_20d": 12_000_000_000,
            "turnover": 0.01,
            "volatility": 0.42,
            "as_of_date": asof_value.date().isoformat(),
            "available_at": asof_value.isoformat(),
            "source": "UnitKRX",
        },
        {
            "code": "BBB",
            "name": "Beta Distribution",
            "sector": "Industrials",
            "foreign_net_buy_history": [20, 10, 5, -5, -10, -20, -30, -40, -50, -60],
            "institution_net_buy_history": [8, 4, 0, -5, -8, -12, -16, -20, -24, -30],
            "individual_net_buy_history": [-5, 5, 12, 20, 28, 36, 45, 55, 66, 80],
            "pension_net_buy": -10,
            "program_net_buy": -20,
            "foreign_ownership_change": -0.02,
            "short_sell_ratio": 0.08,
            "short_position_ratio": 0.07,
            "short_position_quantity": 900_000,
            "avg_daily_volume": 80_000,
            "trading_value_20d": 3_000_000_000,
            "turnover": 0.004,
            "volatility": 0.55,
            "as_of_date": asof_value.date().isoformat(),
            "available_at": asof_value.isoformat(),
            "source": "UnitKRX",
        },
        {
            "code": "CCC",
            "name": "Gamma Zero Volume",
            "sector": "Small Cap",
            "foreign_net_buy_history": [-2, -3, -4],
            "institution_net_buy_history": [-1, -2, -3],
            "individual_net_buy_history": [3, 5, 7],
            "short_sell_ratio": 0.04,
            "short_position_ratio": 0.03,
            "short_position_quantity": 100_000,
            "avg_daily_volume": 0,
            "trading_value_20d": 500_000_000,
            "turnover": 0.001,
            "volatility": 0.60,
            "as_of_date": asof_value.date().isoformat(),
            "available_at": asof_value.isoformat(),
            "source": "UnitKRX",
        },
    ]


class SmartMoneyFlowShortPressurePanelTests(unittest.TestCase):
    def test_flow_z_score_calculation(self):
        self.assertIsNone(calculate_flow_z_score([]))
        self.assertEqual(calculate_flow_z_score([5, 5, 5]), 0.0)
        self.assertGreater(calculate_flow_z_score([0, 1, 2, 3, 4, 10]), 1.0)

    def test_days_to_cover_and_zero_volume(self):
        self.assertAlmostEqual(calculate_days_to_cover(1_000_000, 250_000), 4.0)
        self.assertIsNone(calculate_days_to_cover(1_000_000, 0))
        self.assertIsNone(calculate_days_to_cover(None, 250_000))

    def test_short_squeeze_and_fragility_classification(self):
        squeeze_score = calculate_short_squeeze_score(0.18, 0.12, 9.0, 2.0, 0.45)
        self.assertEqual(classify_short_squeeze(squeeze_score), "high_squeeze_candidate")
        self.assertEqual(classify_short_squeeze(40), "low")
        self.assertEqual(classify_fragility(76), "high_fragility")
        self.assertEqual(classify_fragility(35), "stable")

    def test_zero_volume_handling_in_panel(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_smart_money_flow_short_pressure_panel(flow_inputs=flow_inputs(now), now=now, allow_mock=False)
        zero_volume = next(row for row in state.flow_rows if row.code == "000CCC" or row.name == "Gamma Zero Volume")
        self.assertIsNone(zero_volume.days_to_cover)
        self.assertEqual(zero_volume.illiquidity_warning, "zero_volume")

    def test_panel_renders_loading_empty_error_and_stale_states(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        empty_state = build_smart_money_flow_short_pressure_panel(allow_mock=False, now=now)
        self.assertIn("수급·공매도 데이터 없음", smart_money_flow_short_pressure_panel_html(empty_state))
        self.assertIn("Loading", smart_money_flow_short_pressure_panel_html(replace(empty_state, status="loading", summary="Loading.")))
        self.assertIn("Error", smart_money_flow_short_pressure_panel_html(replace(empty_state, status="error", summary="Error.")))

        old = now - timedelta(days=10)
        stale_state = build_smart_money_flow_short_pressure_panel(
            flow_inputs=flow_inputs(old),
            now=now,
            stale_after_hours=24 * 3,
            allow_mock=False,
        )
        self.assertEqual(stale_state.status, "stale")
        html = smart_money_flow_short_pressure_panel_html(stale_state)
        self.assertIn(status_label("stale"), html)
        self.assertIn(module_title("Smart Money Flow & Short Pressure Panel"), html)

    def test_api_response_shape_source_metadata_and_lists(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_smart_money_flow_short_pressure_panel(flow_inputs=flow_inputs(now), now=now, allow_mock=False)
        payload = smart_money_flow_short_pressure_api_response(state)

        self.assertEqual(payload["moduleId"], "SmartMoneyFlowShortPressurePanel")
        self.assertEqual(payload["apiPath"], "/api/dashboard/flow-short-pressure")
        self.assertIn("flowRows", payload)
        self.assertIn("foreignAccumulationLeaderboard", payload)
        self.assertIn("institutionAccumulationLeaderboard", payload)
        self.assertIn("retailCrowdingList", payload)
        self.assertIn("shortSqueezeCandidates", payload)
        self.assertIn("fragileLongCandidates", payload)
        self.assertIn("distributionRiskList", payload)
        self.assertIn("sectorFlowHeatmap", payload)
        self.assertTrue(payload["flowRows"])
        self.assertTrue(payload["foreignAccumulationLeaderboard"])
        self.assertTrue(payload["distributionRiskList"])
        meta = payload["flowRows"][0]["meta"]
        self.assertIn("source", meta)
        self.assertIn("as_of_date", meta)
        self.assertIn("available_at", meta)
        self.assertIn("fetched_at", meta)
        self.assertIn("stale_data_flag", meta)


if __name__ == "__main__":
    unittest.main()
