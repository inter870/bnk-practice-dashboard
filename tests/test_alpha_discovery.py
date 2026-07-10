import unittest

import pandas as pd

from src.discovery import build_universe, scan_universe, score_candidate


def make_history(start: float, step: float, periods: int = 90, volume: int = 100_000) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=periods, freq="B")
    close = pd.Series([start + step * i for i in range(periods)], index=idx)
    return pd.DataFrame(
        {
            "Open": close,
            "High": close * 1.02,
            "Low": close * 0.98,
            "Close": close,
            "Volume": volume,
        },
        index=idx,
    )


class AlphaDiscoveryTests(unittest.TestCase):
    def test_universe_excludes_invalid_securities_when_data_exists(self):
        listing = pd.DataFrame(
            [
                {"Code": "005930", "Name": "삼성전자", "Market": "KOSPI"},
                {"Code": "123456", "Name": "테스트ETF", "Market": "KOSPI"},
                {"Code": "654321", "Name": "스팩1호", "Market": "KOSDAQ"},
                {"Code": "000995", "Name": "DB하이텍우", "Market": "KOSPI"},
            ]
        )
        universe, warnings = build_universe(listing)
        self.assertEqual([row["code"] for row in universe], ["005930"])
        self.assertTrue(warnings)

    def test_scanner_ranks_strong_rs_candidate_higher_than_weak(self):
        benchmark = make_history(100, 0.1)["Close"]
        strong = make_history(100, 1.2)
        weak = make_history(100, -0.2)
        strong_candidate = score_candidate("000001", "강한종목", "KOSPI", strong, benchmark)
        weak_candidate = score_candidate("000002", "약한종목", "KOSPI", weak, benchmark)
        self.assertIsNotNone(strong_candidate)
        self.assertIsNotNone(weak_candidate)
        self.assertGreater(strong_candidate.discovery_score, weak_candidate.discovery_score)
        self.assertIsNone(strong_candidate.expected_edge)
        self.assertIsNone(strong_candidate.quality_adjusted_rr)
        self.assertTrue(any("표본외 보정" in warning for warning in strong_candidate.warnings))

    def test_graceful_unavailable_when_history_loader_fails(self):
        universe = [{"code": "000001", "name": "테스트", "market": "KOSPI"}]

        def loader(_: str) -> pd.DataFrame:
            raise RuntimeError("provider down")

        candidates, warnings = scan_universe(universe, loader)
        self.assertEqual(candidates, [])
        self.assertTrue(any("로딩 실패" in warning for warning in warnings))

    def test_avoid_list_catches_poor_liquidity(self):
        benchmark = make_history(100, 0.1)["Close"]
        illiquid = make_history(100, -0.1, volume=10)
        candidate = score_candidate("000003", "저유동성", "KOSDAQ", illiquid, benchmark)
        self.assertEqual(candidate.category, "매수 금지 후보")
        self.assertEqual(candidate.max_position_pct, 0.0)


if __name__ == "__main__":
    unittest.main()
