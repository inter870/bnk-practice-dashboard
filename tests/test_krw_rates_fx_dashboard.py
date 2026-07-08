from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from src.institutional import (
    build_krw_rates_fx_dashboard,
    calculate_fx_shock,
    calculate_rate_shock,
    krw_rates_fx_dashboard_api_response,
    krw_rates_fx_dashboard_html,
)
from src.portfolio.models import Holding
from src.ui.korean_labels import module_title, status_label


class DummySnapshot:
    def __init__(self, last_close: float, change_pct: float, asof: datetime, source: str = "UnitTestFeed", quality_score: int = 90):
        self.last_close = last_close
        self.change_pct = change_pct
        self.asof = asof
        self.source = source
        self.frequency = "daily"
        self.unit = "market"
        self.quality_score = quality_score
        self.is_fallback = False
        self.warnings = []
        self.errors = []


def fx_rates_inputs() -> dict[str, dict[str, float | str]]:
    return {
        "usd_krw": {"label": "USD/KRW", "value": 1460.0, "change": 1.1, "unit": "KRW per USD", "source": "UnitFX"},
        "eur_krw": {"label": "EUR/KRW", "value": 1510.0, "change": 0.2, "unit": "KRW per EUR", "source": "UnitFX"},
        "jpy_krw": {"label": "JPY/KRW", "value": 9.5, "change": -0.1, "unit": "KRW per JPY", "source": "UnitFX"},
        "korea_base_rate": {"label": "Korea base rate", "value": 3.5, "change": 0.0, "unit": "%", "source": "UnitRates"},
        "korea_yield": {"label": "Korea 3Y/10Y yield", "value": 3.9, "change": 0.15, "unit": "%", "source": "UnitRates"},
        "us_2y": {"label": "U.S. 2Y yield", "value": 5.0, "change": 0.13, "unit": "%", "source": "UnitRates"},
        "us_10y": {"label": "U.S. 10Y yield", "value": 4.8, "change": 0.14, "unit": "%", "source": "UnitRates"},
        "us_10y_real": {"label": "U.S. 10Y real yield", "value": 2.2, "change": 0.12, "unit": "%", "source": "UnitRates"},
    }


class KRWRatesFXDashboardTests(unittest.TestCase):
    def test_fx_shock_calculation(self):
        high_score, high_label = calculate_fx_shock(1460.0, 1.2)
        self.assertGreaterEqual(high_score, 75)
        self.assertEqual(high_label, "HIGH_FX_PRESSURE")

        support_score, support_label = calculate_fx_shock(1240.0, -1.1)
        self.assertLessEqual(support_score, 35)
        self.assertEqual(support_label, "FX_SUPPORTIVE")

    def test_rate_shock_calculation(self):
        high_score, high_label = calculate_rate_shock(
            korea_yield=4.0,
            korea_yield_change=0.15,
            us_2y=5.0,
            us_2y_change=0.13,
            us_10y=4.8,
            us_10y_change=0.14,
            us_10y_real=2.3,
            us_10y_real_change=0.12,
        )
        self.assertGreaterEqual(high_score, 75)
        self.assertEqual(high_label, "HIGH_RATE_PRESSURE")

        support_score, support_label = calculate_rate_shock(
            korea_yield=2.1,
            korea_yield_change=-0.2,
            us_2y=2.8,
            us_2y_change=-0.2,
            us_10y=2.9,
            us_10y_change=-0.2,
            us_10y_real=0.4,
            us_10y_real_change=-0.2,
        )
        self.assertLessEqual(support_score, 35)
        self.assertEqual(support_label, "RATE_SUPPORTIVE")

    def test_missing_data_empty_and_mock_fallback(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        empty_state = build_krw_rates_fx_dashboard(allow_mock=False, now=now)
        self.assertEqual(empty_state.status, "empty")
        self.assertEqual(empty_state.indicators, ())

        mock_state = build_krw_rates_fx_dashboard(allow_mock=True, now=now)
        self.assertNotEqual(mock_state.status, "empty")
        self.assertTrue(mock_state.indicators)
        self.assertTrue(any(row.meta.is_fallback for row in mock_state.indicators))

    def test_panel_renders_loading_empty_error_and_stale_states(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        empty_state = build_krw_rates_fx_dashboard(allow_mock=False, now=now)
        self.assertIn("환율·금리 데이터 없음", krw_rates_fx_dashboard_html(empty_state))
        self.assertIn("Loading", krw_rates_fx_dashboard_html(replace(empty_state, status="loading", summary="Loading.")))
        self.assertIn("Error", krw_rates_fx_dashboard_html(replace(empty_state, status="error", summary="Error.")))

        old = now - timedelta(days=4)
        stale_state = build_krw_rates_fx_dashboard(
            snapshots={"USD/KRW": DummySnapshot(1450.0, 0.8, old)},
            allow_mock=False,
            now=now,
            stale_after_hours=24,
        )
        self.assertEqual(stale_state.status, "stale")
        html = krw_rates_fx_dashboard_html(stale_state)
        self.assertIn(status_label("stale"), html)
        self.assertIn(module_title("KRW / Rates / FX Dashboard"), html)

    def test_api_response_shape_source_metadata_and_portfolio_impact(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        holdings = [
            Holding("usd-1", "AAPL", "Apple", "stocks", 10, 100, 100, "USD", "Technology", "US", "SPY"),
            Holding("kr-1", "005930", "Samsung", "stocks", 100, 10, 10, "KRW", "Semiconductor", "KR", "KS11"),
        ]
        state = build_krw_rates_fx_dashboard(
            holdings=holdings,
            fx_rates_inputs=fx_rates_inputs(),
            allow_mock=False,
            now=now,
        )
        self.assertIsNotNone(state.portfolio_krw_impact_pct)
        payload = krw_rates_fx_dashboard_api_response(state)
        self.assertEqual(payload["moduleId"], "KRWRatesFXDashboard")
        self.assertEqual(payload["apiPath"], "/api/dashboard/krw-rates-fx")
        self.assertIn("fxShockScore", payload)
        self.assertIn("rateShockScore", payload)
        self.assertIn("yieldCurveSlope", payload)
        self.assertIn("impactRows", payload)
        meta = payload["indicators"][0]["meta"]
        self.assertIn("source", meta)
        self.assertIn("as_of_date", meta)
        self.assertIn("fetched_at", meta)
        self.assertIn("stale_data_flag", meta)


if __name__ == "__main__":
    unittest.main()
