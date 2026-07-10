from pathlib import Path
import pickle
import re
import unittest
from unittest.mock import patch

import pandas as pd

from src.market_snapshot import Snapshot


ROOT = Path(__file__).resolve().parents[1]
APP_TEXT = (ROOT / "app.py").read_text(encoding="utf-8")
RENDER_TEXT = (ROOT / "render.yaml").read_text(encoding="utf-8")
ENV_EXAMPLE_TEXT = (ROOT / ".env.example").read_text(encoding="utf-8")


class RuntimeSafetyTests(unittest.TestCase):
    def test_market_snapshot_is_pickle_safe_across_streamlit_cache_boundaries(self) -> None:
        snapshot = Snapshot("KOSPI", "코스피", 2700.0, 2690.0, 10.0, 0.37, None)
        restored = pickle.loads(pickle.dumps(snapshot))
        self.assertEqual(restored.key, "KOSPI")
        self.assertNotIn("class Snapshot", APP_TEXT)

    def test_tls_verification_cannot_be_disabled_in_app_runtime(self) -> None:
        self.assertIn("HTTP_VERIFY_SSL = True", APP_TEXT)
        self.assertIsNone(re.search(r"verify\s*=\s*False", APP_TEXT))
        self.assertNotIn("requests.sessions.Session.request =", APP_TEXT)
        self.assertNotIn("BNK_VERIFY_SSL", APP_TEXT)
        self.assertNotIn("BNK_VERIFY_SSL", RENDER_TEXT)

    def test_private_ca_bundle_is_the_only_documented_tls_override(self) -> None:
        self.assertIn("BNK_CA_BUNDLE", APP_TEXT)
        self.assertIn("REQUESTS_CA_BUNDLE", APP_TEXT)
        self.assertIn("BNK_CA_BUNDLE=", ENV_EXAMPLE_TEXT)

    def test_production_mock_data_defaults_to_disabled(self) -> None:
        self.assertIn('SHOW_MOCK_DATA = config_bool("SHOW_MOCK_DATA", config_bool("DEMO_MODE", False))', APP_TEXT)
        self.assertRegex(RENDER_TEXT, r'key:\s*SHOW_MOCK_DATA\s*\n\s*value:\s*["\']?false["\']?')
        self.assertIn("SHOW_MOCK_DATA=false", ENV_EXAMPLE_TEXT)
        for builder in (
            "build_market_regime_macro_radar",
            "build_valuation_relative_cheapness_panel",
            "build_fundamental_quality_panel",
            "build_smart_money_flow_short_pressure_panel",
        ):
            self.assertRegex(APP_TEXT, rf"{builder}\([^\n]*allow_mock=mock_data_enabled\(\)")
        self.assertRegex(
            APP_TEXT,
            r"def build_runtime_dart_catalyst_state[\s\S]{0,500}allow_mock=mock_data_enabled\(\)",
        )
        self.assertRegex(
            APP_TEXT,
            r"def build_runtime_forward_alpha_state[\s\S]{0,1200}allow_mock = mock_data_enabled\(\)",
        )

    def test_kis_oauth_cache_is_independent_from_dashboard_refresh_token(self) -> None:
        self.assertIn("def _get_kis_access_token_cached(credential_fingerprint: str)", APP_TEXT)
        self.assertIn("def get_kis_access_token(_refresh_token: int)", APP_TEXT)
        self.assertNotIn("def get_kis_access_token(refresh_token: int)", APP_TEXT)

    def test_refresh_does_not_clear_shared_cross_session_caches(self) -> None:
        refresh_start = APP_TEXT.index("if refresh_allowed:")
        refresh_end = APP_TEXT.index("selected_view = select_main_view()", refresh_start)
        self.assertNotIn(".clear()", APP_TEXT[refresh_start:refresh_end])

    def test_korea_context_query_sync_preserves_unrelated_view_parameter(self) -> None:
        sync_start = APP_TEXT.index("def _sync_korea_query_params")
        sync_end = APP_TEXT.index("\ndef ", sync_start + 1)
        sync_text = APP_TEXT[sync_start:sync_end]
        self.assertIn("CONTEXT_QUERY_KEYS", sync_text)
        self.assertNotIn("st.query_params.clear()", sync_text)

    def test_lightweight_views_render_before_market_snapshot_loading(self) -> None:
        main_text = APP_TEXT[APP_TEXT.index("def main()"):]
        selector_index = main_text.index("selected_view = select_main_view()")
        snapshot_index = main_text.index("snapshot = load_market_snapshot")
        self.assertLess(selector_index, snapshot_index)
        for label in ("알파 후보 탐색", "매크로", "설정"):
            self.assertIn(f'"{label}"', main_text[selector_index:snapshot_index])
        disclosure_index = main_text.index('if selected_view == "공시"')
        self.assertLess(disclosure_index, snapshot_index)

    def test_runtime_dart_provider_error_is_not_reported_as_valid_empty_data(self) -> None:
        import app

        frame = pd.DataFrame()
        frame.attrs.update(
            {
                "provider_status": "error",
                "source": "OpenDART",
                "fetched_at": "2026-07-10T09:00:00+09:00",
                "error_code": "tls_error",
            }
        )
        with (
            patch.object(app, "load_recent_disclosures", return_value=frame),
            patch.object(app, "mock_data_enabled", return_value=False),
        ):
            state = app.build_runtime_dart_catalyst_state(0)

        self.assertEqual(state.status, "error")
        self.assertIn("공급자 연결에 실패", state.summary)
        self.assertIn("dart_provider_error", state.risk_flags)
        self.assertEqual(state.data_points[0].meta.error_code, "tls_error")
        self.assertNotIn("공시 이벤트 없음", state.summary)

    def test_runtime_dart_empty_response_remains_empty_not_error(self) -> None:
        import app

        frame = pd.DataFrame()
        frame.attrs.update(
            {
                "provider_status": "empty",
                "source": "OpenDART",
                "fetched_at": "2026-07-10T09:00:00+09:00",
                "error_code": None,
            }
        )
        with (
            patch.object(app, "load_recent_disclosures", return_value=frame),
            patch.object(app, "mock_data_enabled", return_value=False),
        ):
            state = app.build_runtime_dart_catalyst_state(0)

        self.assertEqual(state.status, "empty")


if __name__ == "__main__":
    unittest.main()
