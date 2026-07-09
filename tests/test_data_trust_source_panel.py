from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
import unittest

from src.institutional import (
    DataSourceMeta,
    SourceCoverageRow,
    build_data_trust_source_panel,
    data_trust_source_panel_api_response,
    data_trust_source_panel_html,
    formatDataTrustMetadataKo,
    formatKeyStatusKo,
    formatKoDateTime,
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


def source_meta(
    *,
    source: str = "Unit Test Source",
    endpoint: str = "unit:test",
    as_of_date: str | None = "2026-07-08",
    fetched_at: str | None = "2026-07-08T08:39:17+00:00",
    confidence_score: int | None = 80,
    missing: bool = False,
    stale: bool = False,
) -> DataSourceMeta:
    return DataSourceMeta(
        source=source,
        provider=source,
        source_url=None,
        as_of_date=as_of_date,
        available_at=as_of_date,
        fetched_at=fetched_at,
        frequency="metadata",
        unit="metadata",
        quality_score=confidence_score or 0,
        is_fallback=False,
        stale_data_flag=stale,
        source_table_or_endpoint=endpoint,
        revised_at=None,
        confidence_score=confidence_score,
        missing_data_flag=missing,
        warnings=(),
        errors=(),
    )


def coverage_row(
    *,
    module_key: str = "market_price",
    label: str = "Market price data",
    status: str = "connected",
    coverage_status: str = "available",
    required_keys: tuple[str, ...] = (),
    missing_keys: tuple[str, ...] = (),
    is_planned: bool = False,
    is_keyless: bool = False,
    active_source_id: str | None = "naver_finance_market_snapshot",
    active_source_label_ko: str | None = "Naver Finance",
    adapter_id: str | None = "naver:finance",
    meta: DataSourceMeta | None = None,
) -> SourceCoverageRow:
    return SourceCoverageRow(
        module_key=module_key,
        label=label,
        coverage_status=coverage_status,
        required_api_keys=required_keys,
        missing_api_keys=missing_keys,
        notes=(),
        meta=meta or source_meta(endpoint=adapter_id or "unit:test"),
        active_source_id=active_source_id,
        active_source_label_ko=active_source_label_ko,
        adapter_id=adapter_id,
        status=status,
        accuracy_grade="planned" if is_planned else "public_snapshot",
        exactness_level="unavailable" if is_planned else "public_snapshot",
        missing_keys=missing_keys,
        required_keys=required_keys,
        has_required_keys=not missing_keys,
        source_endpoint=adapter_id,
        is_planned=is_planned,
        is_keyless=is_keyless,
        can_compute_exact_value=not is_planned,
        can_compute_best_effort_value=not is_planned,
    )


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
        self.assertEqual("planned", valuation_row.status)
        self.assertTrue(valuation_row.is_planned)
        self.assertEqual("planned", valuation_row.accuracy_grade)
        self.assertFalse(valuation_row.meta.stale_data_flag)
        self.assertIsNone(valuation_row.meta.confidence_score)
        html = data_trust_source_panel_html(state)
        self.assertIn("연결 예정", html)
        self.assertIn("키 확인: 어댑터 구현 후 확인", html)
        self.assertIn("표시 불가", html)
        self.assertNotIn("필요 키 필요 키 없음", html)
        self.assertNotIn("필요 키 없음", html)
        self.assertNotIn("누락 없음", html)

    def test_format_key_status_ko_matrix(self):
        planned = coverage_row(
            module_key="valuation",
            label="Valuation data",
            status="adapter_missing",
            coverage_status="adapter_missing",
            is_planned=True,
            adapter_id="planned:krx_valuation",
            meta=source_meta(endpoint="planned:krx_valuation", as_of_date=None, confidence_score=0, missing=True, stale=True),
        )
        self.assertEqual("키 확인: 어댑터 구현 후 확인", formatKeyStatusKo(planned))

        keyless = coverage_row(
            is_keyless=True,
            active_source_id="manual_portfolio_holdings",
            active_source_label_ko="수동 입력",
            adapter_id="manual:portfolio",
        )
        self.assertEqual("필요 키: 없음", formatKeyStatusKo(keyless))

        public_keyless = coverage_row(is_keyless=True, active_source_id="naver_finance_market_snapshot")
        self.assertEqual("키 없이 공개 데이터 사용 중", formatKeyStatusKo(public_keyless))

        opendart_missing = coverage_row(required_keys=("OPENDART_API_KEY",), missing_keys=("OPENDART_API_KEY",), is_keyless=False)
        self.assertEqual("누락 키: OPENDART_API_KEY", formatKeyStatusKo(opendart_missing))

        kis_missing = coverage_row(
            required_keys=("KIS_APP_KEY", "KIS_APP_SECRET"),
            missing_keys=("KIS_APP_KEY", "KIS_APP_SECRET"),
            is_keyless=False,
        )
        self.assertEqual("누락 키: KIS_APP_KEY, KIS_APP_SECRET", formatKeyStatusKo(kis_missing))

        keys_present = coverage_row(required_keys=("OPENDART_API_KEY",), missing_keys=(), is_keyless=False)
        self.assertEqual("필요 키: 설정됨", formatKeyStatusKo(keys_present))
        self.assertNotIn("누락 없음", formatKeyStatusKo(keys_present))

    def test_timestamp_formatting_for_data_trust_ui(self):
        self.assertEqual("수집 시각: 2026.07.08 17:39", formatKoDateTime("2026-07-08T08:39:17+00:00"))
        self.assertEqual("수집 시각: 형식 오류", formatKoDateTime("not-a-timestamp"))
        self.assertEqual("수집 시각: 확인 불가", formatKoDateTime(None))

    def test_planned_valuation_row_display_fields_are_institutional_korean(self):
        row = coverage_row(
            module_key="valuation",
            label="Valuation data",
            status="adapter_missing",
            coverage_status="adapter_missing",
            is_planned=True,
            adapter_id="planned:krx_valuation",
            active_source_id="planned_krx_valuation",
            active_source_label_ko="KRX/OpenDART 어댑터 연결 예정",
            meta=source_meta(
                source="KRX/OpenDART 어댑터 연결 예정",
                endpoint="planned:krx_valuation",
                as_of_date=None,
                confidence_score=0,
                missing=True,
                stale=True,
            ),
        )
        fields = formatDataTrustMetadataKo(row)
        self.assertEqual("밸류에이션 데이터", fields.titleKo)
        self.assertEqual("연결 예정", fields.statusBadgeKo)
        self.assertEqual("표시 불가", fields.accuracyBadgeKo)
        self.assertEqual("키 확인: 어댑터 구현 후 확인", fields.keyStatusKo)
        self.assertEqual("신뢰도 N/A", fields.confidenceKo)
        self.assertEqual("기준일: 해당 없음", fields.asOfDateKo)
        self.assertIn("밸류에이션 어댑터가 아직 연결되지 않아 정확 수치를 표시할 수 없습니다.", fields.primaryMessageKo)
        self.assertIn("수집 시각: 2026.07.08 17:39", fields.compactLineKo)
        self.assertNotIn("필요 키 없음", fields.compactLineKo)
        self.assertNotIn("누락 없음", fields.compactLineKo)

    def test_data_trust_panel_sanitizes_planned_rows(self):
        now = datetime(2026, 7, 8, 8, 39, 17, tzinfo=timezone.utc)
        state = build_data_trust_source_panel(
            snapshots=current_snapshots(now),
            portfolio_holding_count=1,
            using_mock_portfolio=False,
            api_key_status=all_keys_present(),
            now=now,
        )
        html = data_trust_source_panel_html(state)
        for expected in [
            "밸류에이션 데이터",
            "수급 데이터",
            "공매도 데이터",
            "연결 예정",
            "표시 불가",
            "키 확인: 어댑터 구현 후 확인",
            "기준일: 해당 없음",
            "수집 시각: 2026.07.08 17:39",
        ]:
            self.assertIn(expected, html)
        for forbidden in [
            "필요 키 필요 키 없음",
            "누락 없음",
            "필요 키 없음",
            "adapter planned",
            "missing keys none",
        ]:
            self.assertNotIn(forbidden, html)
        self.assertIsNone(re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", html))

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

    def test_planned_and_none_reference_dates_are_not_stale(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_data_trust_source_panel(
            snapshots=current_snapshots(now),
            portfolio_holding_count=1,
            using_mock_portfolio=False,
            api_key_status=all_keys_present(),
            now=now,
        )
        planned_rows = [row for row in state.source_coverage if row.is_planned]
        self.assertTrue(planned_rows)
        for row in planned_rows:
            self.assertEqual("planned", row.status)
            self.assertFalse(row.meta.stale_data_flag)
            self.assertIsNone(row.meta.confidence_score)
            self.assertNotIn(row.label, state.stale_sources)

        partial_rows = [row for row in state.source_coverage if row.module_key in {"financial_statement", "dart_disclosure", "macro"}]
        for row in partial_rows:
            self.assertEqual("partially_connected", row.status)
            self.assertEqual("partial", row.coverage_status)
            self.assertFalse(row.meta.stale_data_flag)
            self.assertFalse(row.meta.missing_data_flag)

    def test_missing_key_is_source_specific_and_not_stale(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_data_trust_source_panel(
            snapshots=current_snapshots(now),
            portfolio_holding_count=1,
            using_mock_portfolio=False,
            api_key_status={
                "KIS_APP_KEY": True,
                "KIS_APP_SECRET": True,
                "OPENDART_API_KEY": False,
                "BOK_ECOS_API_KEY": False,
            },
            now=now,
        )
        dart_row = next(row for row in state.source_coverage if row.module_key == "dart_disclosure")
        macro_row = next(row for row in state.source_coverage if row.module_key == "macro")
        self.assertEqual("missing_key", dart_row.status)
        self.assertEqual(("OPENDART_API_KEY",), dart_row.missing_keys)
        self.assertFalse(dart_row.meta.stale_data_flag)
        self.assertEqual("missing_key", macro_row.status)
        self.assertEqual(("BOK_ECOS_API_KEY",), macro_row.missing_keys)
        self.assertFalse(macro_row.meta.stale_data_flag)


if __name__ == "__main__":
    unittest.main()
