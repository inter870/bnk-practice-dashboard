from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from src.institutional import (
    build_fundamental_quality_panel,
    calculate_accrual_ratio,
    calculate_quality_score,
    calculate_ttm,
    fundamental_quality_api_response,
    fundamental_quality_panel_html,
    select_point_in_time_periods,
)
from src.ui.korean_labels import module_title, status_label


def sample_periods() -> list[dict[str, object]]:
    return [
        {"period": "2025Q1", "fiscal_period_end": "2025-03-31", "available_at": "2025-05-15", "revenue": 100.0, "net_income": 10.0, "cfo": 12.0, "total_assets": 200.0},
        {"period": "2025Q2", "fiscal_period_end": "2025-06-30", "available_at": "2025-08-14", "revenue": 110.0, "net_income": 11.0, "cfo": 13.0, "total_assets": 210.0},
        {"period": "2025Q3", "fiscal_period_end": "2025-09-30", "available_at": "2025-11-14", "revenue": 120.0, "net_income": 12.0, "cfo": 14.0, "total_assets": 220.0},
        {"period": "2025Q4", "fiscal_period_end": "2025-12-31", "available_at": "2026-03-15", "revenue": 130.0, "net_income": 13.0, "cfo": 15.0, "total_assets": 230.0},
        {"period": "2026Q1", "fiscal_period_end": "2026-03-31", "available_at": "2026-05-15", "revenue": 999.0, "net_income": 99.0, "cfo": 99.0, "total_assets": 999.0},
    ]


def financial_inputs(asof: datetime | None = None) -> list[dict[str, object]]:
    asof_value = asof or datetime(2026, 7, 8, tzinfo=timezone.utc)
    return [
        {
            "code": "AAA",
            "name": "Alpha Quality",
            "sector": "Tech",
            "valuation_percentile": 30.0,
            "per": 10.0,
            "pbr": 1.0,
            "source": "UnitDART",
            "periods": [
                {"period": "2024Q2", "available_at": "2024-08-14", "revenue": 80, "operating_income": 8, "gross_profit": 32, "net_income": 6, "cfo": 8, "capex": 2, "total_assets": 150, "equity": 100, "debt": 20, "cash": 30, "ebitda": 10, "interest_expense": 1, "invested_capital": 110},
                {"period": "2024Q3", "available_at": "2024-11-14", "revenue": 85, "operating_income": 9, "gross_profit": 34, "net_income": 7, "cfo": 9, "capex": 2, "total_assets": 155, "equity": 104, "debt": 20, "cash": 31, "ebitda": 11, "interest_expense": 1, "invested_capital": 112},
                {"period": "2024Q4", "available_at": "2025-03-15", "revenue": 90, "operating_income": 10, "gross_profit": 36, "net_income": 8, "cfo": 10, "capex": 2, "total_assets": 160, "equity": 108, "debt": 19, "cash": 32, "ebitda": 12, "interest_expense": 1, "invested_capital": 114},
                {"period": "2025Q1", "available_at": "2025-05-15", "revenue": 95, "operating_income": 11, "gross_profit": 38, "net_income": 9, "cfo": 11, "capex": 2, "total_assets": 165, "equity": 112, "debt": 18, "cash": 33, "ebitda": 13, "interest_expense": 1, "invested_capital": 116},
                {"period": "2025Q2", "available_at": "2025-08-14", "revenue": 105, "operating_income": 14, "gross_profit": 44, "net_income": 11, "cfo": 14, "capex": 3, "total_assets": 170, "equity": 116, "debt": 17, "cash": 36, "ebitda": 16, "interest_expense": 1, "invested_capital": 118},
                {"period": "2025Q3", "available_at": "2025-11-14", "revenue": 110, "operating_income": 15, "gross_profit": 46, "net_income": 12, "cfo": 15, "capex": 3, "total_assets": 175, "equity": 120, "debt": 16, "cash": 38, "ebitda": 17, "interest_expense": 1, "invested_capital": 120},
                {"period": "2025Q4", "available_at": "2026-03-15", "revenue": 115, "operating_income": 16, "gross_profit": 48, "net_income": 13, "cfo": 16, "capex": 3, "total_assets": 180, "equity": 124, "debt": 15, "cash": 40, "ebitda": 18, "interest_expense": 1, "invested_capital": 122},
                {"period": "2026Q1", "available_at": asof_value.isoformat(), "revenue": 120, "operating_income": 17, "gross_profit": 50, "net_income": 14, "cfo": 17, "capex": 3, "total_assets": 185, "equity": 128, "debt": 14, "cash": 42, "ebitda": 19, "interest_expense": 1, "invested_capital": 124},
            ],
        },
        {
            "code": "BBB",
            "name": "Beta Weak",
            "sector": "Industrials",
            "valuation_percentile": 80.0,
            "per": 30.0,
            "pbr": 2.5,
            "source": "UnitDART",
            "periods": [
                {"period": "2025Q2", "available_at": "2025-08-14", "revenue": 100, "operating_income": 8, "gross_profit": 18, "net_income": 4, "cfo": 1, "capex": 5, "total_assets": 250, "equity": 70, "debt": 150, "cash": 10, "ebitda": 12, "interest_expense": 4, "invested_capital": 210},
                {"period": "2025Q3", "available_at": "2025-11-14", "revenue": 95, "operating_income": 6, "gross_profit": 16, "net_income": 2, "cfo": -2, "capex": 5, "total_assets": 255, "equity": 68, "debt": 155, "cash": 8, "ebitda": 10, "interest_expense": 4, "invested_capital": 215},
                {"period": "2025Q4", "available_at": "2026-03-15", "revenue": 90, "operating_income": 4, "gross_profit": 14, "net_income": 1, "cfo": -3, "capex": 5, "total_assets": 260, "equity": 66, "debt": 160, "cash": 7, "ebitda": 8, "interest_expense": 4, "invested_capital": 220},
                {"period": "2026Q1", "available_at": asof_value.isoformat(), "revenue": 88, "operating_income": 2, "gross_profit": 12, "net_income": -1, "cfo": -5, "capex": 5, "total_assets": 265, "equity": 64, "debt": 165, "cash": 6, "ebitda": 6, "interest_expense": 4, "invested_capital": 225},
            ],
        },
    ]


class FundamentalQualityPanelTests(unittest.TestCase):
    def test_ttm_calculation_uses_available_at(self):
        cutoff = datetime(2026, 4, 1, tzinfo=timezone.utc)
        self.assertEqual(calculate_ttm(sample_periods(), "revenue", cutoff), 460.0)
        selected = select_point_in_time_periods(sample_periods(), cutoff)
        self.assertEqual(selected[-1]["period"], "2025Q4")
        self.assertNotEqual(selected[-1]["period"], "2026Q1")

    def test_accrual_ratio_calculation(self):
        self.assertAlmostEqual(calculate_accrual_ratio(100, 80, 1000), 0.02)
        self.assertIsNone(calculate_accrual_ratio(100, 80, 0))
        self.assertIsNone(calculate_accrual_ratio(None, 80, 1000))

    def test_quality_score_calculation(self):
        strong = calculate_quality_score(
            {
                "roe": 0.18,
                "roa": 0.10,
                "roic": 0.18,
                "operating_margin": 0.22,
                "cfo_to_net_income": 1.3,
                "fcf_conversion": 0.9,
                "accrual_ratio": 0.01,
                "debt_to_equity": 0.2,
                "net_debt_to_ebitda": -0.5,
                "interest_coverage": 15,
                "revenue_growth": 0.20,
                "operating_income_growth": 0.30,
            }
        )
        weak = calculate_quality_score(
            {
                "roe": -0.02,
                "roa": -0.01,
                "roic": 0.01,
                "operating_margin": 0.01,
                "cfo_to_net_income": 0.2,
                "fcf_conversion": -0.5,
                "accrual_ratio": 0.16,
                "debt_to_equity": 3.0,
                "net_debt_to_ebitda": 6.0,
                "interest_coverage": 1.0,
                "revenue_growth": -0.1,
                "operating_income_growth": -0.2,
            }
        )
        self.assertGreater(strong["quality_score"], 80)
        self.assertLess(weak["quality_score"], 35)

    def test_dart_available_at_rule_not_fiscal_period_end(self):
        cutoff = datetime(2026, 2, 1, tzinfo=timezone.utc)
        periods = [
            {"period": "2025Q4", "fiscal_period_end": "2025-12-31", "available_at": "2026-03-15", "revenue": 999},
            {"period": "2025Q3", "fiscal_period_end": "2025-09-30", "available_at": "2025-11-14", "revenue": 100},
            {"period": "2025Q2", "fiscal_period_end": "2025-06-30", "revenue": 1000},
        ]
        selected = select_point_in_time_periods(periods, cutoff)
        self.assertEqual([row["period"] for row in selected], ["2025Q3"])

    def test_receipt_timestamp_precision_is_preserved(self):
        now = datetime(2026, 5, 16, tzinfo=timezone.utc)
        state = build_fundamental_quality_panel(
            financial_inputs=[
                {
                    "code": "005930",
                    "name": "삼성전자",
                    "sector": "반도체",
                    "periods": [
                        {
                            "period": "2026Q1",
                            "available_at": "2026-05-15T18:00:00+09:00",
                            "revenue": 100,
                            "operating_income": 10,
                            "net_income": 8,
                            "cfo": 9,
                            "total_assets": 200,
                        }
                    ],
                }
            ],
            now=now,
            allow_mock=False,
        )

        row = state.quality_rows[0]
        self.assertEqual(row.available_at, "2026-05-15T18:00:00+09:00")
        self.assertEqual(row.meta.available_at, "2026-05-15T18:00:00+09:00")
        self.assertEqual(row.meta.as_of_date, "2026-05-15")

    def test_panel_renders_loading_empty_error_and_stale_states(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        empty_state = build_fundamental_quality_panel(allow_mock=False, now=now)
        self.assertIn("재무제표 데이터 없음", fundamental_quality_panel_html(empty_state))
        self.assertIn("Loading", fundamental_quality_panel_html(replace(empty_state, status="loading", summary="Loading.")))
        self.assertIn("Error", fundamental_quality_panel_html(replace(empty_state, status="error", summary="Error.")))

        old = now - timedelta(days=500)
        stale_inputs = financial_inputs(now)
        for item in stale_inputs:
            for period in item["periods"]:
                period["available_at"] = old.isoformat()
        stale_state = build_fundamental_quality_panel(
            financial_inputs=stale_inputs,
            now=now,
            stale_after_hours=24 * 120,
            allow_mock=False,
        )
        self.assertEqual(stale_state.status, "stale")
        html = fundamental_quality_panel_html(stale_state)
        self.assertIn(status_label("stale"), html)
        self.assertIn(module_title("Fundamental Quality Panel"), html)

    def test_api_response_shape_and_quality_lists(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_fundamental_quality_panel(financial_inputs=financial_inputs(now), now=now, allow_mock=False)
        payload = fundamental_quality_api_response(state)
        self.assertEqual(payload["moduleId"], "FundamentalQualityPanel")
        self.assertEqual(payload["apiPath"], "/api/dashboard/fundamental-quality")
        self.assertIn("qualityRows", payload)
        self.assertIn("topQualityStocks", payload)
        self.assertIn("cheapQualityStocks", payload)
        self.assertIn("accountingRedFlags", payload)
        self.assertIn("fcfConversionRanking", payload)
        self.assertIn("roicVsValuation", payload)
        self.assertTrue(payload["qualityRows"])
        meta = payload["qualityRows"][0]["meta"]
        self.assertIn("source", meta)
        self.assertIn("as_of_date", meta)
        self.assertIn("fetched_at", meta)
        self.assertIn("stale_data_flag", meta)
        self.assertTrue(payload["topQualityStocks"])
        self.assertTrue(payload["accountingRedFlags"])


if __name__ == "__main__":
    unittest.main()
