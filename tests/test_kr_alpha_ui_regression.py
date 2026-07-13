from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class KRAlphaUIRegressionTests(unittest.TestCase):
    def test_existing_nine_routes_are_preserved_and_feature_flagged_view_is_last(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        for slug in (
            "dashboard", "portfolio", "stocks", "alpha-discovery", "disclosures",
            "macro", "briefing", "signal-outcome", "settings",
        ):
            self.assertIn(f'"{slug}"', source)
        self.assertIn('config_bool("KR_ALPHA_ENABLED", False)', source)
        self.assertIn('MAIN_VIEW_SLUGS["KR Alpha"] = "kr-alpha"', source)

    def test_live_order_transport_is_not_implemented(self):
        risk_source = (ROOT / "src" / "kr_alpha" / "risk.py").read_text(encoding="utf-8")
        provider_source = (ROOT / "src" / "kr_alpha" / "providers.py").read_text(encoding="utf-8")
        self.assertIn("live_order_transport_not_implemented", risk_source)
        self.assertIn("raise RuntimeError", provider_source)
        self.assertNotIn("requests.post", risk_source + provider_source)

    def test_fixture_disclaimer_and_download_are_visible_contracts(self):
        source = (ROOT / "src" / "kr_alpha" / "ui.py").read_text(encoding="utf-8")
        self.assertIn("DEMO DATA", (ROOT / "src" / "kr_alpha" / "service.py").read_text(encoding="utf-8"))
        self.assertIn("CSV 다운로드", source)
        self.assertIn("자동 주문은 지원하지 않습니다", source)


if __name__ == "__main__":
    unittest.main()
