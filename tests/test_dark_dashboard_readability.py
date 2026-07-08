from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
THEME_TEXT = ROOT.joinpath("src", "ui", "korea_os_theme.py").read_text(encoding="utf-8")
SCRIPT_PATH = ROOT / "scripts" / "check_dark_dashboard_readability.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("check_dark_dashboard_readability", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load readability audit script.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DarkDashboardReadabilityTests(unittest.TestCase):
    def test_semantic_dark_theme_tokens_exist(self) -> None:
        for token in [
            "--stance-bg: #05070D",
            "--stance-card-bg: #0B1020",
            "--stance-card-bg-soft: #111827",
            "--stance-surface-elevated: #172033",
            "--stance-text-primary: #F8FAFC",
            "--stance-text-secondary: #E5E7EB",
            "--stance-text-tertiary: #CBD5E1",
            "--stance-text-muted: #94A3B8",
            "--stance-text-disabled: #64748B",
            "--stance-focus-ring: #38BDF8",
            "--stance-positive: #4ADE80",
            "--stance-negative: #FB7185",
            "--stance-warning: #FCD34D",
            "--stance-info: #38BDF8",
            "--stance-neutral: #CBD5E1",
            "--kos-market-up: #FF4D4F",
            "--kos-market-down: #3B82F6",
            "--kos-risk-critical: #F97316",
        ]:
            self.assertIn(token, THEME_TEXT)

    def test_common_dashboard_selectors_are_overridden(self) -> None:
        for selector in [
            ".stApp .hero-title",
            ".stApp .section-title",
            ".stApp .metric-card",
            ".stApp .signal-box",
            ".stApp [data-testid=\"stTabs\"] button",
            ".stApp [data-baseweb=\"popover\"]",
            ".stApp [role=\"listbox\"]",
        ]:
            self.assertIn(selector, THEME_TEXT)

    def test_visual_polish_guards_for_korean_dashboard(self) -> None:
        for token in [
            "Final visual polish",
            "word-break: keep-all",
            "overflow-wrap: anywhere",
            ".pi-card-body",
            ".command-table",
            ".stApp [data-baseweb=\"popover\"]",
            ".stApp [role=\"tooltip\"]",
            ".stApp [data-testid=\"stSkeleton\"]",
            "grid-template-columns: 1fr !important",
            "font-variant-numeric: tabular-nums",
        ]:
            self.assertIn(token, THEME_TEXT)

    def test_readability_audit_passes_for_dashboard_ui_files(self) -> None:
        module = _load_audit_module()
        self.assertEqual([], module.audit_files())


if __name__ == "__main__":
    unittest.main()
