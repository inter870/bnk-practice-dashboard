from __future__ import annotations

from pathlib import Path
import unittest

from src.institutional.models import DataSourceMeta, SectorTailwindRow
from src.institutional.ui import _sector_driver_rows
from src.ui.korean_labels import (
    sector_driver_text,
    sector_empty_state,
    sector_environment_labels,
    sector_label,
)
from src.ui.portfolio_display import (
    format_portfolio_krw,
    format_portfolio_percent,
    portfolio_kpi_cards_html,
    resolve_portfolio_number,
)


ROOT = Path(__file__).resolve().parents[1]
THEME_TEXT = (ROOT / "src" / "ui" / "korea_os_theme.py").read_text(encoding="utf-8")
APP_TEXT = (ROOT / "app.py").read_text(encoding="utf-8")


def source_meta() -> DataSourceMeta:
    return DataSourceMeta(
        source="Unit test",
        provider="Unit test",
        source_url=None,
        as_of_date="2026-07-11",
        available_at="2026-07-11T00:00:00+09:00",
        fetched_at="2026-07-11T00:00:00+09:00",
        frequency="daily",
        unit="score",
        quality_score=100,
        is_fallback=False,
        stale_data_flag=False,
    )


class PortfolioMobileUiTests(unittest.TestCase):
    def test_full_krw_values_are_never_abbreviated(self) -> None:
        expected = {
            0: "0원",
            1: "1원",
            999: "999원",
            1_000: "1,000원",
            50_000_000: "50,000,000원",
            100_000_000: "100,000,000원",
            9_876_543_210_000: "9,876,543,210,000원",
        }
        for value, display in expected.items():
            with self.subTest(value=value):
                self.assertEqual(display, format_portfolio_krw(value))

    def test_cash_ratio_format_keeps_one_decimal_place(self) -> None:
        self.assertEqual("0.0%", format_portfolio_percent(0))
        self.assertEqual("50.0%", format_portfolio_percent(50))
        self.assertEqual("100.0%", format_portfolio_percent(100))

    def test_valid_zero_is_not_replaced_by_the_demo_default(self) -> None:
        self.assertEqual(0.0, resolve_portfolio_number(0, default=100_000_000.0))
        self.assertEqual(100_000_000.0, resolve_portfolio_number(None, default=100_000_000.0))

    def test_kpi_component_uses_dynamic_values_and_scoped_classes(self) -> None:
        rendered = portfolio_kpi_cards_html(
            total_assets=123_456_789,
            cash=12_345_678,
            cash_percent=10,
            regime_label="중립",
            regime_score=58,
        )
        self.assertIn('class="portfolio-kpi-grid"', rendered)
        self.assertIn("123,456,789원", rendered)
        self.assertIn("12,345,678원", rendered)
        self.assertIn("10.0%", rendered)
        self.assertIn("중립 / 58", rendered)
        self.assertNotIn("100,000,000원", rendered)
        self.assertIn("portfolio_kpi_cards_html(", APP_TEXT)

    def test_sector_display_terms_are_korean_first(self) -> None:
        self.assertEqual("강세 섹터 TOP 3", sector_environment_labels("tailwind")["title"])
        self.assertEqual("약세 섹터 TOP 3", sector_environment_labels("headwind")["title"])
        self.assertEqual("중립 섹터 TOP 3", sector_environment_labels("neutral")["title"])
        self.assertEqual("경기방어주", sector_label("Defensives"))
        self.assertEqual("자동차·수출주", sector_label("Autos / Exporters"))
        self.assertEqual(
            "반도체 수출·업황 사이클",
            sector_driver_text(("semi exports", "export cycle"), role="positive"),
        )
        self.assertEqual(
            "수출 모멘텀·원화 약세 수혜",
            sector_driver_text(("exports", "weak KRW"), role="positive"),
        )
        self.assertEqual("환율 부담", sector_driver_text(("환율 pressure",), role="negative"))
        self.assertEqual("확인되지 않음", sector_driver_text((), role="positive"))
        self.assertEqual("제한적", sector_driver_text((), role="negative"))

    def test_sector_card_html_removes_old_mixed_terms(self) -> None:
        rows = (
            SectorTailwindRow(
                sector="Autos / Exporters",
                tailwind_score=42,
                label="headwind",
                positive_drivers=("exports", "weak KRW"),
                negative_drivers=(),
                meta=source_meta(),
            ),
            SectorTailwindRow(
                sector="Semiconductors",
                tailwind_score=36,
                label="headwind",
                positive_drivers=("semi exports", "export cycle"),
                negative_drivers=("rates",),
                meta=source_meta(),
            ),
        )
        rendered = _sector_driver_rows(rows, "headwind")
        for expected in (
            "상승 촉매",
            "하방 리스크",
            "자동차·수출주",
            "반도체 수출·업황 사이클",
            "수출 모멘텀·원화 약세 수혜",
        ):
            self.assertIn(expected, rendered)
        for forbidden in (
            "순풍:",
            "역풍:",
            "환율 pressure",
            "weak KRW",
            "Defensives",
            "Autos·Exporters",
            "Autos / Exporters",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_empty_states_use_the_actual_thresholds(self) -> None:
        self.assertEqual(
            ("현재 강세 기준을 충족한 섹터가 없습니다.", "기준: 섹터 환경 점수 60점 이상"),
            sector_empty_state("tailwind", tailwind_min_score=60, headwind_max_score=44),
        )
        self.assertEqual(
            ("현재 약세 기준에 해당하는 섹터가 없습니다.", "기준: 섹터 환경 점수 44점 이하"),
            sector_empty_state("headwind", tailwind_min_score=60, headwind_max_score=44),
        )
        self.assertEqual(
            ("현재 중립 구간에 해당하는 섹터가 없습니다.", "기준: 섹터 환경 점수 45~59점"),
            sector_empty_state("neutral", tailwind_min_score=60, headwind_max_score=44),
        )
        empty_html = "".join(
            _sector_driver_rows((), label)
            for label in ("tailwind", "headwind", "neutral")
        )
        self.assertIn("현재 강세 기준을 충족한 섹터가 없습니다.", empty_html)
        self.assertIn("현재 약세 기준에 해당하는 섹터가 없습니다.", empty_html)
        self.assertIn("현재 중립 구간에 해당하는 섹터가 없습니다.", empty_html)
        self.assertNotIn("표시할 섹터가 없습니다.", empty_html)

    def test_mobile_css_is_scoped_and_content_driven(self) -> None:
        for selector in (
            ".portfolio-kpi-grid",
            ".portfolio-kpi-card",
            ".portfolio-kpi-value",
            ".sector-environment-grid",
            ".sector-environment-card",
            ".sector-environment-item",
        ):
            self.assertIn(selector, THEME_TEXT)
        self.assertIn("height: auto;", THEME_TEXT)
        self.assertIn("font-variant-numeric: tabular-nums;", THEME_TEXT)
        self.assertIn("overflow-wrap: anywhere;", THEME_TEXT)
        self.assertNotIn("user-select", THEME_TEXT)
        self.assertNotIn(".st-emotion-cache-", THEME_TEXT)


if __name__ == "__main__":
    unittest.main()
