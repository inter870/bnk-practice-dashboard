from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from src.institutional import (
    adapt_open_dart_rows,
    build_dart_disclosure_catalyst_panel,
    calculate_dilution_risk_score,
    calculate_materiality_score,
    classify_disclosure_event,
    dart_disclosure_catalyst_api_response,
    dart_disclosure_catalyst_panel_html,
    select_point_in_time_disclosures,
)
from src.ui.korean_labels import module_title, status_label


def disclosure_events(asof: datetime | None = None) -> list[dict[str, object]]:
    asof_value = asof or datetime(2026, 7, 8, tzinfo=timezone.utc)
    return [
        {
            "receipt_no": "202607080001",
            "code": "005930",
            "name": "Alpha Return",
            "title": "자기주식 소각 결정",
            "receipt_date": asof_value.isoformat(),
            "available_at": asof_value.isoformat(),
            "source_url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=202607080001",
            "materiality_amount": 900,
            "market_cap": 10_000,
            "source": "UnitDART",
        },
        {
            "receipt_no": "202607070001",
            "code": "034020",
            "name": "Beta Dilution",
            "title": "전환사채권 발행결정",
            "receipt_date": (asof_value - timedelta(days=1)).isoformat(),
            "available_at": (asof_value - timedelta(days=1)).isoformat(),
            "source_url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=202607070001",
            "dilution_pct": 0.12,
            "materiality_amount": 500,
            "market_cap": 4_000,
            "source": "UnitDART",
        },
        {
            "receipt_no": "202607060001",
            "code": "000660",
            "name": "Gamma Contract",
            "title": "대규모 공급계약 체결",
            "receipt_date": (asof_value - timedelta(days=2)).isoformat(),
            "available_at": (asof_value - timedelta(days=2)).isoformat(),
            "source_url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=202607060001",
            "materiality_amount": 400,
            "market_cap": 8_000,
            "source": "UnitDART",
        },
    ]


class DARTDisclosureCatalystPanelTests(unittest.TestCase):
    def test_event_source_fetch_timestamp_is_preserved(self):
        now = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
        state = build_dart_disclosure_catalyst_panel(
            disclosure_events=[
                {
                    "code": "005930",
                    "name": "삼성전자",
                    "title": "자기주식 소각 결정",
                    "available_at": "2026-07-02T09:00:00+09:00",
                    "fetched_at": "2026-07-02T09:05:00+09:00",
                    "receipt_no": "202607020001",
                    "source": "OpenDART",
                }
            ],
            now=now,
            allow_mock=False,
        )

        self.assertEqual(state.event_rows[0].meta.fetched_at, "2026-07-02T09:05:00+09:00")

    def test_open_dart_adapter_uses_receipt_date_and_conservative_availability(self):
        events = adapt_open_dart_rows(
            [
                {
                    "corp_name": "테스트전자",
                    "report_name": "자기주식 소각 결정",
                    "date": "20260708",
                    "stock_code": "5930",
                    "report_url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=202607080001",
                }
            ],
            source="OpenDART list.json",
            fetched_at="2026-07-08T18:00:00+09:00",
            is_fallback=False,
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["code"], "005930")
        self.assertEqual(events[0]["receipt_date"], "2026-07-08")
        self.assertTrue(str(events[0]["available_at"]).startswith("2026-07-08T23:59:59"))
        self.assertEqual(events[0]["receipt_no"], "202607080001")
        self.assertNotIn("crtfc_key", str(events[0]))

    def test_event_classification_positive_and_negative(self):
        positive = classify_disclosure_event({"title": "자사주 취득 신탁계약 체결"})
        negative = classify_disclosure_event({"title": "유상증자 결정"})
        audit = classify_disclosure_event({"title": "감사의견 의견거절"})

        self.assertEqual(positive["category"], "share_buyback")
        self.assertEqual(positive["sentiment"], "positive")
        self.assertEqual(negative["category"], "paid_in_capital_increase")
        self.assertEqual(negative["sentiment"], "negative")
        self.assertEqual(audit["category"], "audit_issue")

    def test_materiality_and_dilution_scoring(self):
        contract = {
            "title": "단일판매 공급계약 체결",
            "materiality_amount": 200,
            "market_cap": 2_000,
        }
        cb = {
            "title": "전환사채권 발행결정",
            "dilution_pct": 0.15,
            "materiality_amount": 500,
            "market_cap": 5_000,
        }

        self.assertGreaterEqual(calculate_materiality_score(contract), 80)
        self.assertGreaterEqual(calculate_dilution_risk_score(cb), 80)
        self.assertEqual(calculate_dilution_risk_score(contract), 0)

    def test_no_future_disclosure_leakage(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        future = {
            "receipt_no": "202608010001",
            "code": "999999",
            "name": "Future Leak",
            "title": "상장폐지 위험 공시",
            "receipt_date": "2026-08-01T09:00:00+09:00",
            "available_at": "2026-08-01T09:01:00+09:00",
        }
        events = disclosure_events(now) + [future]

        selected = select_point_in_time_disclosures(events, now)
        self.assertFalse(any(event["receipt_no"] == "202608010001" for event in selected))

        state = build_dart_disclosure_catalyst_panel(disclosure_events=events, now=now, allow_mock=False)
        self.assertFalse(any(row.receipt_no == "202608010001" for row in state.event_rows))

    def test_panel_renders_loading_empty_error_and_stale_states(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        empty_state = build_dart_disclosure_catalyst_panel(allow_mock=False, now=now)
        self.assertIn("DART 공시 이벤트 없음", dart_disclosure_catalyst_panel_html(empty_state))
        self.assertIn("Loading", dart_disclosure_catalyst_panel_html(replace(empty_state, status="loading", summary="Loading.")))
        self.assertIn("Error", dart_disclosure_catalyst_panel_html(replace(empty_state, status="error", summary="Error.")))

        old = now - timedelta(days=90)
        stale_state = build_dart_disclosure_catalyst_panel(
            disclosure_events=disclosure_events(old),
            now=now,
            stale_after_hours=24 * 30,
            allow_mock=False,
        )
        self.assertEqual(stale_state.status, "stale")
        html = dart_disclosure_catalyst_panel_html(stale_state)
        self.assertIn(status_label("stale"), html)
        self.assertIn(module_title("DART Disclosure Catalyst Panel"), html)

    def test_api_response_shape_source_metadata_and_lists(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        state = build_dart_disclosure_catalyst_panel(disclosure_events=disclosure_events(now), now=now, allow_mock=False)
        payload = dart_disclosure_catalyst_api_response(state)

        self.assertEqual(payload["moduleId"], "DARTDisclosureCatalystPanel")
        self.assertEqual(payload["apiPath"], "/api/dashboard/dart-catalysts")
        self.assertIn("latestHighMaterialityDisclosures", payload)
        self.assertIn("positiveCatalysts", payload)
        self.assertIn("negativeRisks", payload)
        self.assertIn("dilutionWatchlist", payload)
        self.assertIn("shareholderReturnAnnouncements", payload)
        self.assertIn("eventTimeline", payload)
        self.assertTrue(payload["eventRows"])
        self.assertTrue(payload["positiveCatalysts"])
        self.assertTrue(payload["negativeRisks"])
        self.assertTrue(payload["dilutionWatchlist"])
        meta = payload["eventRows"][0]["meta"]
        self.assertIn("source", meta)
        self.assertIn("as_of_date", meta)
        self.assertIn("available_at", meta)
        self.assertIn("fetched_at", meta)
        self.assertIn("stale_data_flag", meta)


if __name__ == "__main__":
    unittest.main()
