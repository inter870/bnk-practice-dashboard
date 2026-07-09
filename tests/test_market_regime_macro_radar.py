from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from src.institutional import (
    build_market_regime_macro_radar,
    market_regime_macro_radar_api_response,
    market_regime_macro_radar_html,
    normalize_regime_label_ko,
)
from src.institutional.ui import _macro_change, _macro_value
from src.ui.korean_labels import module_title, status_label


class DummySnapshot:
    def __init__(
        self,
        last_close: float,
        change_pct: float,
        asof: datetime,
        source: str = "UnitTestFeed",
        quality_score: int = 90,
        prev_close: float | None = 1.0,
        is_fallback: bool = False,
    ):
        self.last_close = last_close
        self.change_pct = change_pct
        self.prev_close = prev_close
        self.asof = asof
        self.source = source
        self.frequency = "daily"
        self.unit = "market"
        self.quality_score = quality_score
        self.is_fallback = is_fallback
        self.warnings = []
        self.errors = []


def favorable_macro() -> dict[str, dict[str, float | str]]:
    return {
        "korea_growth": {"label": "Korea growth proxy", "value": 2.8, "change": 0.2, "unit": "% YoY", "source": "UnitMacro"},
        "inflation": {"label": "Inflation proxy", "value": 2.1, "change": -0.2, "unit": "% YoY", "source": "UnitMacro"},
        "export_growth": {"label": "Export growth proxy", "value": 11.0, "change": 2.0, "unit": "% YoY", "source": "UnitMacro"},
        "semiconductor_export": {"label": "Semiconductor export proxy", "value": 18.0, "change": 3.0, "unit": "% YoY", "source": "UnitMacro"},
        "usd_krw": {"label": "USD/KRW", "value": 1290.0, "change": -0.3, "unit": "KRW per USD", "source": "UnitMacro"},
        "korea_policy_rate": {"label": "Korea policy rate proxy", "value": 2.5, "change": -0.1, "unit": "%", "source": "UnitMacro"},
        "korea_10y": {"label": "Korea 10Y rate proxy", "value": 2.7, "change": -0.05, "unit": "%", "source": "UnitMacro"},
        "us_10y": {"label": "U.S. 10Y rate proxy", "value": 3.5, "change": -0.04, "unit": "%", "source": "UnitMacro"},
        "us_real_yield": {"label": "U.S. real yield proxy", "value": 0.8, "change": -0.02, "unit": "%", "source": "UnitMacro"},
        "vix": {"label": "Global risk proxy", "value": 14.0, "change": -1.0, "unit": "index", "source": "UnitMacro"},
    }


def unfavorable_macro() -> dict[str, dict[str, float | str]]:
    return {
        "korea_growth": {"label": "Korea growth proxy", "value": 0.8, "change": -0.4, "unit": "% YoY", "source": "UnitMacro"},
        "inflation": {"label": "Inflation proxy", "value": 3.8, "change": 0.3, "unit": "% YoY", "source": "UnitMacro"},
        "export_growth": {"label": "Export growth proxy", "value": -6.0, "change": -2.0, "unit": "% YoY", "source": "UnitMacro"},
        "semiconductor_export": {"label": "Semiconductor export proxy", "value": -8.0, "change": -3.0, "unit": "% YoY", "source": "UnitMacro"},
        "usd_krw": {"label": "USD/KRW", "value": 1460.0, "change": 0.9, "unit": "KRW per USD", "source": "UnitMacro"},
        "korea_policy_rate": {"label": "Korea policy rate proxy", "value": 3.6, "change": 0.1, "unit": "%", "source": "UnitMacro"},
        "korea_10y": {"label": "Korea 10Y rate proxy", "value": 3.8, "change": 0.12, "unit": "%", "source": "UnitMacro"},
        "us_10y": {"label": "U.S. 10Y rate proxy", "value": 4.7, "change": 0.15, "unit": "%", "source": "UnitMacro"},
        "us_real_yield": {"label": "U.S. real yield proxy", "value": 2.2, "change": 0.12, "unit": "%", "source": "UnitMacro"},
        "vix": {"label": "Global risk proxy", "value": 28.0, "change": 3.0, "unit": "index", "source": "UnitMacro"},
    }


class MarketRegimeMacroRadarTests(unittest.TestCase):
    def test_deterministic_risk_on_export_upcycle_labels(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_market_regime_macro_radar(macro_inputs=favorable_macro(), allow_mock=False, now=now)
        self.assertEqual(state.current_regime_label, "RISK_ON")
        self.assertIn("EXPORT_UPCYCLE", state.regime_labels)
        self.assertIn("LIQUIDITY_SUPPORT", state.regime_labels)
        self.assertGreater(state.regime_score, 60)

    def test_deterministic_risk_off_pressure_labels(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_market_regime_macro_radar(macro_inputs=unfavorable_macro(), allow_mock=False, now=now)
        self.assertEqual(state.current_regime_label, "RISK_OFF")
        self.assertIn("EXPORT_DOWNTURN", state.regime_labels)
        self.assertIn("RATE_PRESSURE", state.regime_labels)
        self.assertIn("FX_PRESSURE", state.regime_labels)
        self.assertIn("STAGFLATION_RISK", state.regime_labels)
        self.assertLess(state.regime_score, 40)

    def test_missing_macro_data_empty_and_mock_fallback(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        empty_state = build_market_regime_macro_radar(allow_mock=False, now=now)
        self.assertEqual(empty_state.status, "empty")
        self.assertEqual(empty_state.macro_heatmap, ())

        mock_state = build_market_regime_macro_radar(allow_mock=True, now=now)
        self.assertNotEqual(mock_state.status, "empty")
        self.assertTrue(mock_state.macro_heatmap)
        self.assertTrue(any(row.meta.is_fallback for row in mock_state.macro_heatmap))
        self.assertEqual(0, mock_state.data_points[0].meta.confidence_score)
        self.assertIn("모의 지표 포함", market_regime_macro_radar_html(mock_state))
        self.assertNotIn("모의 지표 포함", market_regime_macro_radar_html(empty_state))

    def test_panel_renders_loading_empty_error_and_stale_states(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        empty_state = build_market_regime_macro_radar(allow_mock=False, now=now)
        self.assertIn("매크로 데이터 없음", market_regime_macro_radar_html(empty_state))
        self.assertIn("Loading", market_regime_macro_radar_html(replace(empty_state, status="loading", summary="Loading macro.")))
        self.assertIn("Error", market_regime_macro_radar_html(replace(empty_state, status="error", summary="Error macro.")))

        old = now - timedelta(days=4)
        stale_state = build_market_regime_macro_radar(
            snapshots={"USD/KRW": DummySnapshot(1450.0, 0.7, old)},
            macro_inputs=favorable_macro(),
            allow_mock=False,
            now=now,
            stale_after_hours=24,
        )
        self.assertEqual(stale_state.status, "stale")
        html = market_regime_macro_radar_html(stale_state)
        self.assertIn(status_label("stale"), html)
        self.assertIn(module_title("Market Regime & Macro Radar"), html)

    def test_api_response_shape_and_source_metadata(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_market_regime_macro_radar(macro_inputs=favorable_macro(), allow_mock=False, now=now)
        payload = market_regime_macro_radar_api_response(state)
        self.assertEqual(payload["moduleId"], "MarketRegimeMacroRadar")
        self.assertEqual(payload["apiPath"], "/api/dashboard/market-regime")
        self.assertIn("regimeScore", payload)
        self.assertIn("macroHeatmap", payload)
        self.assertIn("sectorTailwinds", payload)
        meta = payload["macroHeatmap"][0]["meta"]
        self.assertIn("source", meta)
        self.assertIn("as_of_date", meta)
        self.assertIn("fetched_at", meta)
        self.assertIn("stale_data_flag", meta)

    def test_kospi_level_and_one_day_percent_are_separated(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_market_regime_macro_radar(
            snapshots={"KOSPI": DummySnapshot(2746.79, 0.42, now, prev_close=2735.0)},
            allow_mock=False,
            now=now,
        )
        row = next(item for item in state.macro_heatmap if item.key == "kospi_momentum")
        self.assertEqual("index_level", row.unit)
        self.assertEqual("2,746.79", _macro_value(row))
        self.assertEqual("+0.42%", _macro_change(row))
        html = market_regime_macro_radar_html(state)
        self.assertIn("<strong>2,746.79</strong>", html)
        self.assertIn("<span>1D +0.42%</span>", html)
        self.assertIn("macro-heatmap-compact", html)
        self.assertNotIn("2,746.79 1D %", html)

    def test_previous_close_missing_hides_one_day_percent(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_market_regime_macro_radar(
            snapshots={"KOSDAQ": DummySnapshot(842.18, 0.31, now, prev_close=None)},
            allow_mock=False,
            now=now,
        )
        row = next(item for item in state.macro_heatmap if item.key == "kosdaq_momentum")
        self.assertEqual("842.18", _macro_value(row))
        self.assertEqual("", _macro_change(row))
        self.assertNotIn("1D +0.31%", market_regime_macro_radar_html(state))

    def test_regime_label_normalization_handles_korean_fx_pressure_alias(self):
        self.assertEqual("환율 부담", normalize_regime_label_ko("FX_PRESSURE"))
        self.assertEqual("환율 부담", normalize_regime_label_ko("환율_PRESSURE"))
        self.assertEqual("위험선호", normalize_regime_label_ko("RISK_ON"))


    def test_naver_fallback_snapshot_is_not_displayed_as_mock_macro_data(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_market_regime_macro_radar(
            snapshots={"KOSPI": DummySnapshot(2746.79, 0.42, now, source="Naver Finance", is_fallback=True)},
            allow_mock=False,
            now=now,
        )
        html = market_regime_macro_radar_html(state)
        self.assertNotIn("mock_macro_included", state.risk_flags)
        self.assertGreater(state.data_points[0].meta.confidence_score, 0)
        self.assertNotIn("모의 지표 포함", html)
        self.assertNotIn("모의</span>", html)


if __name__ == "__main__":
    unittest.main()
