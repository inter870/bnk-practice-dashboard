from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from src.institutional import (
    build_data_trust_source_panel,
    data_trust_source_panel_api_response,
    data_trust_source_panel_html,
)
from src.ui.korean_labels import module_title, status_label, ui_label


class DummySnapshot:
    def __init__(self, asof: datetime, source: str = "UnitTestFeed", quality_score: int = 90, is_fallback: bool = False):
        self.asof = asof
        self.source = source
        self.frequency = "daily"
        self.unit = "KRW"
        self.quality_score = quality_score
        self.is_fallback = is_fallback
        self.warnings = []
        self.errors = []


def all_keys_present() -> dict[str, bool]:
    return {
        "DART_API_KEY": True,
        "OPENDART_API_KEY": True,
        "ECOS_API_KEY": True,
        "BOK_ECOS_API_KEY": True,
        "OPENAI_API_KEY": True,
        "KIS_APP_KEY": True,
        "KIS_APP_SECRET": True,
        "PUBLIC_DATA_API_KEY": True,
    }


def current_snapshots(now: datetime) -> dict[str, DummySnapshot]:
    return {
        "KOSPI": DummySnapshot(now, "KIS Open API", 94),
        "KOSDAQ": DummySnapshot(now, "KIS Open API", 94),
        "USD/KRW": DummySnapshot(now, "BOK ECOS", 86),
        "US 10Y": DummySnapshot(now, "FRED", 80),
        "KR 3Y": DummySnapshot(now, "BOK ECOS", 86),
    }


class DataTrustSourcePanelTests(unittest.TestCase):
    def test_api_returns_source_metadata_contract(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_data_trust_source_panel(
            snapshots=current_snapshots(now),
            portfolio_holding_count=3,
            using_mock_portfolio=False,
            api_key_status=all_keys_present(),
            now=now,
        )
        payload = data_trust_source_panel_api_response(state)
        self.assertEqual(payload["moduleId"], "DataTrustSourcePanel")
        self.assertEqual(payload["apiPath"], "/api/dashboard/data-trust")
        self.assertIn("sourceCoverage", payload)
        self.assertGreaterEqual(len(payload["sourceCoverage"]), 9)

        meta = payload["sourceCoverage"][0]["meta"]
        for key in [
            "source",
            "source_table_or_endpoint",
            "as_of_date",
            "available_at",
            "fetched_at",
            "revised_at",
            "stale_data_flag",
            "confidence_score",
            "missing_data_flag",
        ]:
            self.assertIn(key, meta)

    def test_panel_renders_normal_state(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_data_trust_source_panel(
            snapshots=current_snapshots(now),
            portfolio_holding_count=2,
            using_mock_portfolio=False,
            api_key_status=all_keys_present(),
            now=now,
        )
        html = data_trust_source_panel_html(state)
        self.assertIn(module_title("Data Trust & Source Panel"), html)
        self.assertIn(ui_label("Source Coverage Table"), html)
        self.assertIn(ui_label("Portfolio data"), html)
        self.assertIn(ui_label("Point-in-Time Gate"), html)

    def test_panel_renders_stale_state(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        old = now - timedelta(days=5)
        state = build_data_trust_source_panel(
            snapshots=current_snapshots(old),
            portfolio_holding_count=2,
            using_mock_portfolio=False,
            api_key_status=all_keys_present(),
            now=now,
            stale_after_hours=24,
        )
        self.assertEqual(state.status, "stale")
        self.assertIn("Market price data", state.stale_sources)
        html = data_trust_source_panel_html(state)
        self.assertIn(ui_label("Stale warnings"), html)
        self.assertIn(status_label("stale"), html)

    def test_panel_renders_missing_api_key_state_without_secret_values(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_data_trust_source_panel(
            snapshots=current_snapshots(now),
            portfolio_holding_count=0,
            using_mock_portfolio=True,
            api_key_status={
                "DART_API_KEY": False,
                "ECOS_API_KEY": False,
                "OPENAI_API_KEY": False,
                "KIS_APP_KEY": False,
                "KIS_APP_SECRET": False,
            },
            now=now,
        )
        self.assertIn("OPENDART_API_KEY", state.missing_api_keys)
        self.assertIn("BOK_ECOS_API_KEY", state.missing_api_keys)
        html = data_trust_source_panel_html(state)
        self.assertIn("OPENDART_API_KEY", html)
        self.assertIn("BOK_ECOS_API_KEY", html)
        self.assertNotIn("sk-", html)
        self.assertNotIn("secret=", html.lower())

    def test_source_coverage_includes_all_priority_categories(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_data_trust_source_panel(
            snapshots=current_snapshots(now),
            portfolio_holding_count=1,
            using_mock_portfolio=False,
            api_key_status=all_keys_present(),
            now=now,
        )
        module_keys = {row.module_key for row in state.source_coverage}
        self.assertEqual(
            module_keys,
            {
                "portfolio",
                "market_price",
                "valuation",
                "financial_statement",
                "dart_disclosure",
                "macro",
                "fx_rates",
                "investor_flow",
                "short_selling",
            },
        )

    def test_naver_finance_market_snapshot_does_not_require_kis_keys(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        snapshots = {
            "KOSPI": DummySnapshot(now, "Naver Finance", 88, True),
            "KOSDAQ": DummySnapshot(now, "Naver Finance", 88, True),
        }
        state = build_data_trust_source_panel(
            snapshots=snapshots,
            portfolio_holding_count=1,
            using_mock_portfolio=False,
            api_key_status={
                "KIS_APP_KEY": False,
                "KIS_APP_SECRET": False,
                "OPENDART_API_KEY": True,
                "BOK_ECOS_API_KEY": True,
            },
            now=now,
        )
        market_row = next(row for row in state.source_coverage if row.module_key == "market_price")
        self.assertEqual("naver_finance_market_snapshot", market_row.active_source_id)
        self.assertEqual((), market_row.required_keys)
        self.assertEqual((), market_row.missing_keys)
        self.assertNotIn("KIS_APP_KEY", market_row.to_dict()["missing_keys"])
        html = data_trust_source_panel_html(state)
        market_html = html[html.find("load_market_snapshot:indices") : html.find("planned:krx_valuation")]
        self.assertNotIn("KIS_APP_KEY", market_html)
        self.assertIn("키 없이 공개 데이터 사용 중", market_html)

    def test_kis_market_source_requires_kis_keys_when_active(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        snapshots = {
            "KOSPI": DummySnapshot(now, "KIS Open API", 94, False),
            "KOSDAQ": DummySnapshot(now, "KIS Open API", 94, False),
        }
        state = build_data_trust_source_panel(
            snapshots=snapshots,
            portfolio_holding_count=1,
            using_mock_portfolio=False,
            api_key_status={
                "KIS_APP_KEY": False,
                "KIS_APP_SECRET": False,
                "OPENDART_API_KEY": True,
                "BOK_ECOS_API_KEY": True,
            },
            now=now,
        )
        market_row = next(row for row in state.source_coverage if row.module_key == "market_price")
        self.assertEqual("kis_market_price", market_row.active_source_id)
        self.assertEqual(("KIS_APP_KEY", "KIS_APP_SECRET"), market_row.missing_keys)
        self.assertEqual("missing_key", market_row.status)

    def test_planned_adapters_show_adapter_missing_not_missing_keys_none(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_data_trust_source_panel(
            snapshots=current_snapshots(now),
            portfolio_holding_count=1,
            using_mock_portfolio=False,
            api_key_status=all_keys_present(),
            now=now,
        )
        valuation_row = next(row for row in state.source_coverage if row.module_key == "valuation")
        self.assertEqual("adapter_missing", valuation_row.status)
        self.assertTrue(valuation_row.is_planned)
        self.assertEqual("planned", valuation_row.accuracy_grade)
        html = data_trust_source_panel_html(state)
        self.assertIn("어댑터 미연결", html)
        self.assertIn("키 확인 전 어댑터 미연결", html)
        self.assertNotIn("누락 키 없음", html)

    def test_mock_portfolio_is_explicit_low_confidence_mock(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_data_trust_source_panel(
            snapshots=current_snapshots(now),
            portfolio_holding_count=0,
            using_mock_portfolio=True,
            api_key_status=all_keys_present(),
            now=now,
        )
        portfolio_row = next(row for row in state.source_coverage if row.module_key == "portfolio")
        self.assertEqual("mock", portfolio_row.status)
        self.assertEqual("mock", portfolio_row.accuracy_grade)
        self.assertLessEqual(portfolio_row.meta.confidence_score or 100, 25)


if __name__ == "__main__":
    unittest.main()
