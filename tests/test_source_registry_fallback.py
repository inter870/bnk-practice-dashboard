from __future__ import annotations

import unittest

from src.institutional.source_registry import (
    ACCURACY_LABEL_KO,
    get_source,
    missing_required_keys,
    resolve_best_data_source,
)


class SourceRegistryFallbackTests(unittest.TestCase):
    def test_source_specific_required_keys(self) -> None:
        naver = get_source("naver_finance_market_snapshot")
        kis = get_source("kis_market_price")
        opendart = get_source("opendart_financials")
        planned = get_source("planned_krx_valuation")

        self.assertEqual((), naver.required_env_keys)
        self.assertEqual(("KIS_APP_KEY", "KIS_APP_SECRET"), kis.required_env_keys)
        self.assertEqual(("OPENDART_API_KEY",), opendart.required_env_keys)
        self.assertEqual("planned", planned.source_type)
        self.assertFalse(planned.adapter_available)

    def test_opendart_alias_accepts_existing_dart_api_key(self) -> None:
        opendart = get_source("opendart_financials")
        self.assertEqual((), missing_required_keys(opendart, {"DART_API_KEY": True}))
        self.assertEqual(("OPENDART_API_KEY",), missing_required_keys(opendart, {"DART_API_KEY": False}))

    def test_market_price_prefers_kis_when_keys_present_and_preferred(self) -> None:
        result = resolve_best_data_source(
            "market_price",
            preferred_source="kis_market_price",
            env_status={"KIS_APP_KEY": True, "KIS_APP_SECRET": True},
        )
        self.assertEqual("kis_market_price", result.selected_source.source_id if result.selected_source else None)
        self.assertEqual("broker_realtime", result.accuracy_grade)

    def test_market_price_falls_back_to_keyless_public_source(self) -> None:
        result = resolve_best_data_source(
            "market_price",
            preferred_source="kis_market_price",
            env_status={"KIS_APP_KEY": False, "KIS_APP_SECRET": False},
            allow_keyless_public_sources=True,
        )
        self.assertEqual("naver_finance_market_snapshot", result.selected_source.source_id if result.selected_source else None)
        self.assertEqual("public_snapshot", result.accuracy_grade)
        self.assertIn("KIS_APP_KEY", result.missing_keys)

    def test_market_price_unavailable_when_no_legal_source_or_cache(self) -> None:
        result = resolve_best_data_source(
            "market_price",
            env_status={"KIS_APP_KEY": False, "KIS_APP_SECRET": False, "PUBLIC_DATA_API_KEY": False},
            allow_keyless_public_sources=False,
            allow_cache=False,
        )
        self.assertIsNone(result.selected_source)
        self.assertEqual("missing_key", result.status)

    def test_planned_categories_return_planned_unavailable(self) -> None:
        valuation = resolve_best_data_source("valuation")
        flow = resolve_best_data_source("investor_flow")
        short = resolve_best_data_source("short_selling")
        self.assertEqual("adapter_missing", valuation.status)
        self.assertEqual("planned", valuation.accuracy_grade)
        self.assertEqual("adapter_missing", flow.status)
        self.assertEqual("adapter_missing", short.status)

    def test_financials_and_disclosures_do_not_use_opendart_without_key(self) -> None:
        financials = resolve_best_data_source("financial_statements", env_status={"OPENDART_API_KEY": False})
        disclosures = resolve_best_data_source("dart_disclosures", env_status={"OPENDART_API_KEY": False})
        self.assertEqual("missing_key", financials.status)
        self.assertEqual("missing_key", disclosures.status)
        self.assertEqual(("OPENDART_API_KEY",), financials.missing_keys)
        self.assertEqual(("OPENDART_API_KEY",), disclosures.missing_keys)

    def test_manual_holdings_preferred_over_mock(self) -> None:
        result = resolve_best_data_source(
            "portfolio_holdings",
            env_status={"KIS_APP_KEY": False, "KIS_APP_SECRET": False},
            manual_data_available=True,
            mock_data_available=True,
            allow_mock=True,
        )
        self.assertEqual("manual_portfolio_holdings", result.selected_source.source_id if result.selected_source else None)
        self.assertEqual("manual", result.accuracy_grade)

    def test_mock_holdings_only_when_enabled(self) -> None:
        disabled = resolve_best_data_source(
            "portfolio_holdings",
            env_status={"KIS_APP_KEY": False, "KIS_APP_SECRET": False},
            manual_data_available=False,
            mock_data_available=True,
            allow_mock=False,
        )
        enabled = resolve_best_data_source(
            "portfolio_holdings",
            env_status={"KIS_APP_KEY": False, "KIS_APP_SECRET": False},
            manual_data_available=False,
            mock_data_available=True,
            allow_mock=True,
        )
        self.assertNotEqual("mock_portfolio_holdings", disabled.selected_source.source_id if disabled.selected_source else None)
        self.assertEqual("mock_portfolio_holdings", enabled.selected_source.source_id if enabled.selected_source else None)
        self.assertEqual("모의", ACCURACY_LABEL_KO[enabled.accuracy_grade])


if __name__ == "__main__":
    unittest.main()
