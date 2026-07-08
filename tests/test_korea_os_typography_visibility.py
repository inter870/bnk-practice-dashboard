from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP_TEXT = ROOT.joinpath("app.py").read_text(encoding="utf-8")
THEME_TEXT = ROOT.joinpath("src", "ui", "korea_os_theme.py").read_text(encoding="utf-8")
GUARDRAIL_TEXT = ROOT.joinpath("scripts", "check_korea_os_visibility.py").read_text(encoding="utf-8")


class KoreaOSTypographyVisibilityTests(unittest.TestCase):
    def test_theme_is_imported_injected_and_scoped(self) -> None:
        self.assertIn("from src.ui.korea_os_theme import inject_korea_os_theme", APP_TEXT)
        self.assertIn("inject_korea_os_theme()", APP_TEXT)
        self.assertIn("korea-os-theme", APP_TEXT)
        self.assertIn(".korea-os-theme", THEME_TEXT)

    def test_required_typography_and_color_tokens_exist(self) -> None:
        for token in [
            "Pretendard",
            '"Noto Sans KR"',
            '"Malgun Gothic"',
            "--stance-text-primary: #F8FAFC",
            "--stance-text-secondary: #E5E7EB",
            "--stance-text-tertiary: #CBD5E1",
            "--stance-text-muted: #94A3B8",
            "--kos-text-hero: var(--stance-text-primary)",
            "--kos-text-primary: var(--stance-text-primary)",
            "--kos-text-secondary: var(--stance-text-secondary)",
            "--kos-text-tertiary: var(--stance-text-tertiary)",
            "--kos-card-bg: var(--stance-card-bg)",
            "--kos-accent: #8B5CF6",
        ]:
            self.assertIn(token, THEME_TEXT)

    def test_tables_heatmap_and_filter_summary_use_final_classes(self) -> None:
        self.assertIn("korea-table-wrap korea-os-table-wrap", APP_TEXT)
        self.assertIn("korea-table korea-os-table", APP_TEXT)
        self.assertIn("korea-os-heatmap-cell", APP_TEXT)
        self.assertIn("korea-filter-summary", APP_TEXT)
        self.assertIn(".korea-os-table", THEME_TEXT)
        self.assertIn(".korea-os-heatmap-cell", THEME_TEXT)
        self.assertIn(".korea-filter-summary", THEME_TEXT)

    def test_streamlit_defaults_are_covered_by_theme(self) -> None:
        for selector in [
            '[data-testid="stAppViewContainer"]',
            '[data-testid="stSidebar"]',
            '[data-testid="stDataFrame"]',
            ".stTable",
            '[data-testid="stSlider"]',
            '[data-testid="stCheckbox"]',
            '[role="radiogroup"]',
        ]:
            self.assertIn(selector, THEME_TEXT)

    def test_guardrail_script_checks_the_failure_modes(self) -> None:
        for token in [
            "inject_korea_os_theme()",
            "korea-os-theme",
            "korea-os-table",
            "korea-os-heatmap-cell",
            "st\\.table",
            "st\\.dataframe",
            "text-black",
        ]:
            self.assertIn(token, GUARDRAIL_TEXT)


if __name__ == "__main__":
    unittest.main()
