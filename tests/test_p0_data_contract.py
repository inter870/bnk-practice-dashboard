from __future__ import annotations

import unittest

from src.institutional.data_contract import (
    QUALITY_FORMULA_VERSION,
    calculate_quality_components,
    normalize_data_mode,
    normalize_provider_result,
)
from src.institutional.models import DataSourceMeta, ProviderResult


def meta(**overrides):
    values = {
        "source": "UnitTest",
        "provider": "UnitTest",
        "source_url": None,
        "as_of_date": "2026-07-10",
        "available_at": "2026-07-10T09:00:00+09:00",
        "fetched_at": "2026-07-10T09:01:00+09:00",
        "frequency": "snapshot",
        "unit": "KRW",
        "quality_score": 0,
        "is_fallback": False,
        "stale_data_flag": False,
        "data_mode": "LIVE",
    }
    values.update(overrides)
    return DataSourceMeta(**values)


class P0DataContractTests(unittest.TestCase):
    def test_mode_precedence_keeps_demo_and_stale_separate(self):
        self.assertEqual("DEMO", normalize_data_mode("mock", stale=True, fallback=True))
        self.assertEqual("STALE", normalize_data_mode("ready", stale=True, fallback=True))
        self.assertEqual("FALLBACK", normalize_data_mode("ready", fallback=True))
        self.assertEqual("LIVE", normalize_data_mode("manual"))

    def test_quality_components_are_versioned_and_bounded(self):
        score, components = calculate_quality_components(
            {"completeness": 90, "freshness": 80, "fallback_penalty": -10}
        )
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        self.assertEqual(-10, components["fallback_penalty"])

        result = normalize_provider_result(
            ProviderResult(
                data={"value": 1},
                meta=meta(quality_components={"completeness": 90, "freshness": 80}),
            )
        )
        self.assertEqual(QUALITY_FORMULA_VERSION, result.meta.quality_formula_version)
        self.assertTrue(result.meta.investment_eligible)
        self.assertEqual("2026-07-10", result.meta.as_of)

    def test_demo_stale_and_missing_availability_are_not_investment_eligible(self):
        for source_meta in (
            meta(data_mode="DEMO"),
            meta(stale_data_flag=True),
            meta(available_at=None),
        ):
            result = normalize_provider_result(ProviderResult(data={"value": 1}, meta=source_meta))
            self.assertFalse(result.meta.investment_eligible)


if __name__ == "__main__":
    unittest.main()
