import unittest
from unittest.mock import Mock, patch

import pandas as pd
from bs4 import BeautifulSoup

import app


class MarketSnapshotLiveSourceTests(unittest.TestCase):
    def test_naver_timestamp_uses_provider_time(self):
        soup = BeautifulSoup('<span class="date">2026.07.13 15:23</span>', "html.parser")

        result = app.parse_naver_market_asof(soup)

        self.assertEqual(pd.Timestamp("2026-07-13 15:23"), result)

    def test_naver_fx_parses_value_change_and_provider_time(self):
        response = Mock()
        response.text = """
            <p class="no_today">1,503.80원</p>
            <p class="no_exday"><em class="up">1.80</em> (+0.12%)</p>
            <span class="date">2026.07.13 15:23</span>
        """

        with patch.object(app.requests, "get", return_value=response):
            snapshot = app.fetch_naver_fx_snapshot("USD/KRW")

        self.assertIsNotNone(snapshot)
        self.assertEqual(1503.80, snapshot.last_close)
        self.assertEqual(1.80, snapshot.change)
        self.assertEqual(0.12, snapshot.change_pct)
        self.assertEqual(pd.Timestamp("2026-07-13 15:23"), snapshot.asof)
        self.assertEqual("near_realtime", snapshot.frequency)

    def test_naver_kr3y_is_daily_and_keeps_negative_change(self):
        response = Mock()
        response.text = """
            <p class="no_today">3.76%</p>
            <p class="no_exday"><em class="down">0.01</em> (-0.27%)</p>
            <span class="date">2026.07.10</span>
        """

        with patch.object(app.requests, "get", return_value=response):
            snapshot = app.fetch_naver_yield_snapshot(
                "IRR_GOVT03Y",
                "KR 3Y",
                "한국 국고채 3년물",
            )

        self.assertIsNotNone(snapshot)
        self.assertEqual(3.76, snapshot.last_close)
        self.assertEqual(-0.01, snapshot.change)
        self.assertEqual(-0.27, snapshot.change_pct)
        self.assertEqual(pd.Timestamp("2026-07-10"), snapshot.asof)
        self.assertEqual("daily", snapshot.frequency)

    def test_daily_naver_value_can_replace_empty_historical_fallback(self):
        fallback = app.Snapshot(
            "KR 3Y",
            "KR 3Y",
            None,
            None,
            None,
            None,
            None,
            source="FinanceDataReader",
            unit="%",
            frequency="historical",
        )
        daily = app.Snapshot(
            "KR 3Y",
            "한국 국고채 3년물",
            3.76,
            3.77,
            -0.01,
            -0.27,
            pd.Timestamp("2026-07-10"),
            source="Naver Finance",
            unit="%",
            frequency="daily",
            quality_score=88,
        )

        self.assertIs(daily, app.prefer_current_market_snapshot("KR 3Y", fallback, daily))

    def test_fred_symbol_is_attributed_as_official_daily_data(self):
        source, frequency, is_fallback = app.historical_snapshot_source("FRED:DGS10")
        snapshot = app.Snapshot(
            "US 10Y",
            "FRED:DGS10",
            4.54,
            4.56,
            -0.02,
            -0.44,
            pd.Timestamp("2026-07-09"),
            source=source,
            unit="%",
            frequency=frequency,
            quality_score=100,
            is_fallback=is_fallback,
        )

        self.assertEqual(("FRED", "daily_official", False), (source, frequency, is_fallback))
        label = app.snapshot_source_label(snapshot)
        self.assertIn("미 연준 H.15 (FRED)", label)
        self.assertIn("공식 일별", label)


if __name__ == "__main__":
    unittest.main()
