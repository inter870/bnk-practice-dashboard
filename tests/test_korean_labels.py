from __future__ import annotations

import unittest

from src.ui.korean_labels import (
    action_label,
    asset_class_label,
    ko_sentence,
    module_title,
    rating_label,
    source_meta_line,
    status_label,
)


class KoreanLabelsTests(unittest.TestCase):
    def test_priority_module_titles_are_korean_first(self) -> None:
        self.assertEqual("포트폴리오 리스크 관제실", module_title("Portfolio Risk Cockpit"))
        self.assertEqual("데이터 신뢰도·출처 패널", module_title("Data Trust & Source Panel"))
        self.assertEqual("포트폴리오 최적화·알림 센터", module_title("Portfolio Optimizer & Alert Center"))

    def test_rating_and_action_labels(self) -> None:
        self.assertEqual("강력 매수 후보", rating_label("STRONG_BUY_CANDIDATE"))
        self.assertEqual("고위험 제외", rating_label("HIGH_RISK_EXCLUDE"))
        self.assertEqual("비중 확대", action_label("ADD"))
        self.assertEqual("투자 제외", action_label("EXCLUDE"))

    def test_status_and_asset_class_labels(self) -> None:
        self.assertEqual("업데이트 필요", status_label("stale"))
        self.assertEqual("데모 데이터", status_label("mock"))
        self.assertEqual("펀드", asset_class_label("mutualFunds"))

    def test_sentence_localization(self) -> None:
        self.assertEqual(
            "추가 자금 투입 전 보유 구성, 집중도, 유동성, 현금 버퍼, 데이터 신선도를 점검합니다.",
            ko_sentence("Check ownership, concentration, liquidity, cash buffer, and data freshness before adding capital."),
        )
        self.assertEqual("2개 오래된 출처는 갱신이 필요합니다.", ko_sentence("2 stale source(s) need refresh."))

    def test_source_meta_line_is_korean(self) -> None:
        class Meta:
            source = "Mock portfolio data"
            as_of_date = "2026-07-08"
            fetched_at = "2026-07-08T09:00:00+09:00"
            stale_data_flag = True
            missing_data_flag = True

        text = source_meta_line(Meta())
        self.assertIn("출처 Mock portfolio data", text)
        self.assertIn("기준일 2026-07-08", text)
        self.assertIn("수집 시각", text)
        self.assertIn("오래된 데이터", text)
        self.assertIn("누락 데이터", text)


if __name__ == "__main__":
    unittest.main()
