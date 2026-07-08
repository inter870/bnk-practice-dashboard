from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from src.institutional import (
    build_valuation_relative_cheapness_panel,
    calculate_sector_relative_ranking,
    calculate_valuation_percentile,
    valuation_relative_cheapness_api_response,
    valuation_relative_cheapness_panel_html,
)
from src.ui.korean_labels import module_title, status_label


def valuation_inputs(asof: datetime | None = None) -> list[dict[str, object]]:
    asof_value = asof or datetime(2026, 7, 8, tzinfo=timezone.utc)
    return [
        {
            "code": "AAA",
            "name": "Alpha",
            "sector": "Tech",
            "per": 8.0,
            "forward_per": 7.0,
            "pbr": 0.9,
            "dividend_yield": 0.02,
            "quality_score": 72,
            "quality_trend": "improving",
            "history_per": [6, 8, 10, 12, 14],
            "as_of_date": asof_value,
            "source": "UnitValuation",
        },
        {
            "code": "BBB",
            "name": "Beta",
            "sector": "Tech",
            "per": 20.0,
            "forward_per": 18.0,
            "pbr": 2.0,
            "dividend_yield": 0.005,
            "quality_score": 80,
            "quality_trend": "stable",
            "history_per": [8, 10, 12, 15, 18],
            "as_of_date": asof_value,
            "source": "UnitValuation",
        },
        {
            "code": "CCC",
            "name": "Core Bank",
            "sector": "Financials",
            "per": 5.0,
            "forward_per": 5.2,
            "pbr": 0.5,
            "dividend_yield": 0.06,
            "quality_score": 45,
            "quality_trend": "deteriorating",
            "history_per": [4, 5, 6, 7, 8],
            "as_of_date": asof_value,
            "source": "UnitValuation",
        },
    ]


class ValuationRelativeCheapnessPanelTests(unittest.TestCase):
    def test_valuation_percentile_calculation(self):
        self.assertEqual(calculate_valuation_percentile(8, [4, 6, 8, 10]), 75.0)
        self.assertEqual(calculate_valuation_percentile(3, [4, 6, 8, 10]), 0.0)
        self.assertIsNone(calculate_valuation_percentile(None, [4, 6, 8]))
        self.assertIsNone(calculate_valuation_percentile(8, []))

    def test_sector_relative_ranking(self):
        ranked = calculate_sector_relative_ranking(valuation_inputs(), "per")
        alpha = next(row for row in ranked if row["code"] == "AAA")
        beta = next(row for row in ranked if row["code"] == "BBB")
        self.assertLess(alpha["relative"], beta["relative"])
        self.assertLess(alpha["rank"], beta["rank"])

    def test_missing_valuation_handling_and_mock_fallback(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        empty_state = build_valuation_relative_cheapness_panel(allow_mock=False, now=now)
        self.assertEqual(empty_state.status, "empty")
        self.assertEqual(empty_state.valuation_rows, ())

        mock_state = build_valuation_relative_cheapness_panel(allow_mock=True, now=now)
        self.assertNotEqual(mock_state.status, "empty")
        self.assertTrue(mock_state.valuation_rows)
        self.assertTrue(any(row.meta.is_fallback for row in mock_state.valuation_rows))

    def test_panel_renders_loading_empty_error_and_stale_states(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        empty_state = build_valuation_relative_cheapness_panel(allow_mock=False, now=now)
        self.assertIn("밸류에이션 데이터 없음", valuation_relative_cheapness_panel_html(empty_state))
        self.assertIn("Loading", valuation_relative_cheapness_panel_html(replace(empty_state, status="loading", summary="Loading.")))
        self.assertIn("Error", valuation_relative_cheapness_panel_html(replace(empty_state, status="error", summary="Error.")))

        old = now - timedelta(days=80)
        stale_state = build_valuation_relative_cheapness_panel(
            valuation_inputs=valuation_inputs(old),
            now=now,
            stale_after_hours=24 * 30,
            allow_mock=False,
        )
        self.assertEqual(stale_state.status, "stale")
        html = valuation_relative_cheapness_panel_html(stale_state)
        self.assertIn(status_label("stale"), html)
        self.assertIn(module_title("Valuation & Relative Cheapness Panel"), html)

    def test_api_response_shape_source_metadata_and_lists(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_valuation_relative_cheapness_panel(valuation_inputs=valuation_inputs(now), now=now, allow_mock=False)
        payload = valuation_relative_cheapness_api_response(state)
        self.assertEqual(payload["moduleId"], "ValuationRelativeCheapnessPanel")
        self.assertEqual(payload["apiPath"], "/api/dashboard/valuation")
        self.assertIn("marketPercentile", payload)
        self.assertIn("cheapestQualityCandidates", payload)
        self.assertIn("sectorHeatmap", payload)
        self.assertIn("expensiveList", payload)
        meta = payload["valuationRows"][0]["meta"]
        self.assertIn("source", meta)
        self.assertIn("as_of_date", meta)
        self.assertIn("fetched_at", meta)
        self.assertIn("stale_data_flag", meta)


if __name__ == "__main__":
    unittest.main()
