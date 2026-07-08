from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from src.institutional import (
    PortfolioRiskThresholds,
    build_portfolio_risk_cockpit,
    portfolio_risk_cockpit_api_response,
    portfolio_risk_cockpit_html,
)
from src.portfolio.mock_data import MOCK_HOLDINGS
from src.portfolio.models import Holding, PricePoint
from src.ui.korean_labels import ko_sentence, module_title, status_label, ui_label


class DummySnapshot:
    def __init__(self, asof: datetime, source: str = "UnitTestFeed", quality_score: int = 91):
        self.asof = asof
        self.source = source
        self.frequency = "daily"
        self.unit = "KRW"
        self.quality_score = quality_score
        self.is_fallback = False
        self.warnings = []
        self.errors = []


def sample_holdings() -> list[Holding]:
    return [
        Holding("h1", "005930", "Samsung Electronics", "stocks", 10, 70000, 80000, "KRW", "Semiconductor", "KR", "KS11"),
        Holding("h2", "000660", "SK hynix", "stocks", 5, 150000, 180000, "KRW", "Semiconductor", "KR", "KS11"),
        Holding("h3", "KTB3", "KTB 3Y Basket", "bonds", 1, 500000, 500000, "KRW", "Bonds", "KR", "KS11"),
    ]


class PortfolioRiskCockpitTests(unittest.TestCase):
    def test_component_renders_with_mock_data(self):
        state = build_portfolio_risk_cockpit([], now=datetime(2026, 7, 8, tzinfo=timezone.utc), allow_mock=True)
        html = portfolio_risk_cockpit_html(state)
        self.assertEqual(state.module_id, "PortfolioRiskCockpit")
        self.assertIn(module_title("Portfolio Risk Cockpit"), html)
        self.assertIn(ui_label("Total Portfolio Value"), html)
        self.assertTrue(state.top5_holdings)

    def test_component_handles_empty_data(self):
        state = build_portfolio_risk_cockpit([], now=datetime(2026, 7, 8, tzinfo=timezone.utc), allow_mock=False)
        html = portfolio_risk_cockpit_html(state)
        self.assertEqual(state.status, "empty")
        self.assertIn(ko_sentence("No holdings data."), html)
        self.assertEqual(state.risk_flags, ("empty",))

    def test_component_handles_stale_data(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        old = now - timedelta(days=3)
        snapshots = {"005930": DummySnapshot(old)}
        state = build_portfolio_risk_cockpit(
            [sample_holdings()[0]],
            total_assets=1_000_000,
            cash=100_000,
            snapshots=snapshots,
            thresholds=PortfolioRiskThresholds(stale_after_hours=24),
            now=now,
            allow_mock=False,
        )
        self.assertEqual(state.status, "stale")
        self.assertTrue(any(point.meta.stale_data_flag for point in state.data_points))
        html = portfolio_risk_cockpit_html(state)
        self.assertIn(status_label("stale"), html)
        self.assertIn("오래된 데이터", html)

    def test_api_returns_expected_shape_and_metadata(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        snapshots = {holding.symbol: DummySnapshot(now) for holding in sample_holdings()}
        state = build_portfolio_risk_cockpit(
            sample_holdings(),
            total_assets=2_500_000,
            cash=300_000,
            snapshots=snapshots,
            price_series=[PricePoint("2026-07-01", 2_300_000), PricePoint("2026-07-08", 2_500_000)],
            now=now,
            allow_mock=False,
        )
        payload = portfolio_risk_cockpit_api_response(state)
        self.assertEqual(payload["moduleId"], "PortfolioRiskCockpit")
        self.assertEqual(payload["apiPath"], "/api/dashboard/portfolio-risk")
        self.assertIn("dataPoints", payload)
        self.assertIn("assetAllocation", payload)
        first_metric = payload["dataPoints"][0]
        self.assertIn("meta", first_metric)
        self.assertIn("source", first_metric["meta"])
        self.assertIn("as_of_date", first_metric["meta"])
        self.assertIn("fetched_at", first_metric["meta"])
        self.assertIn("stale_data_flag", first_metric["meta"])

    def test_concentration_alerts_include_single_stock_sector_and_cash(self):
        now = datetime(2026, 7, 8, tzinfo=timezone.utc)
        holdings = [
            Holding("h1", "005930", "Samsung Electronics", "stocks", 20, 70000, 100000, "KRW", "Semiconductor", "KR", "KS11"),
            Holding("h2", "000660", "SK hynix", "stocks", 2, 150000, 180000, "KRW", "Semiconductor", "KR", "KS11"),
        ]
        snapshots = {holding.symbol: DummySnapshot(now) for holding in holdings}
        state = build_portfolio_risk_cockpit(
            holdings,
            total_assets=2_400_000,
            cash=0,
            snapshots=snapshots,
            thresholds=PortfolioRiskThresholds(single_stock_weight=0.20, sector_weight=0.30, cash_min_weight=0.03),
            now=now,
            allow_mock=False,
        )
        alert_ids = {alert.id for alert in state.risk_alerts}
        self.assertIn("single-stock-concentration", alert_ids)
        self.assertIn("sector-concentration", alert_ids)
        self.assertIn("low-cash", alert_ids)

    def test_mock_alerts_are_korean_example_only_not_real_urgent(self):
        now = datetime(2026, 7, 8, 7, 55, 27, tzinfo=timezone.utc)
        snapshots = {holding.symbol: DummySnapshot(now, "FinanceDataReader") for holding in MOCK_HOLDINGS}
        state = build_portfolio_risk_cockpit([], snapshots=snapshots, now=now, allow_mock=True)
        html = portfolio_risk_cockpit_html(state)
        single = next(alert for alert in state.risk_alerts if alert.id == "single-stock-concentration")
        self.assertEqual(single.data_mode, "mock")
        self.assertEqual(single.actionability, "example_only")
        self.assertEqual(single.display_severity_ko, "예시 알림")
        self.assertEqual(single.holdings_source_label_ko, "모의 포트폴리오 데이터")
        self.assertEqual(single.price_source_label_ko, "FinanceDataReader")
        self.assertIn("단일 종목 집중도 초과", html)
        self.assertIn("예시 알림", html)
        self.assertIn("모의 데이터", html)
        self.assertIn("보유: 모의 포트폴리오 데이터", html)
        self.assertIn("가격: FinanceDataReader", html)
        self.assertIn("2026.07.08 16:55", html)
        self.assertNotIn("Single-stock concentration", html)
        self.assertNotIn("Review concentration", html)
        self.assertNotIn("2026-07-08T07:55:27+00:00", html)
        self.assertNotIn(">긴급<", html)

    def test_fresh_manual_alerts_can_be_actionable_urgent(self):
        now = datetime(2026, 7, 8, 7, 55, 27, tzinfo=timezone.utc)
        holdings = [
            Holding("h1", "000660", "SK hynix", "stocks", 10, 100000, 100000, "KRW", "Semiconductor", "KR", "KS11"),
        ]
        snapshots = {holding.symbol: DummySnapshot(now, "FinanceDataReader") for holding in holdings}
        state = build_portfolio_risk_cockpit(
            holdings,
            total_assets=1_000_000,
            cash=0,
            snapshots=snapshots,
            thresholds=PortfolioRiskThresholds(single_stock_weight=0.20, sector_weight=0.30, cash_min_weight=0.03),
            now=now,
            allow_mock=False,
        )
        single = next(alert for alert in state.risk_alerts if alert.id == "single-stock-concentration")
        html = portfolio_risk_cockpit_html(state)
        self.assertEqual(single.data_mode, "manual")
        self.assertEqual(single.actionability, "actionable")
        self.assertEqual(single.display_severity_ko, "긴급")
        self.assertIn("실전 알림", html)
        self.assertIn("긴급", html)
        self.assertIn("현재 100.0% / 기준 20.0% / 초과 +80.0%p", html)

    def test_stale_prices_block_actionability_and_format_time(self):
        now = datetime(2026, 7, 8, 7, 55, 27, tzinfo=timezone.utc)
        old = now - timedelta(days=3)
        holdings = [
            Holding("h1", "005930", "Samsung Electronics", "stocks", 10, 70000, 100000, "KRW", "Semiconductor", "KR", "KS11"),
        ]
        snapshots = {holding.symbol: DummySnapshot(old, "FinanceDataReader") for holding in holdings}
        state = build_portfolio_risk_cockpit(
            holdings,
            total_assets=1_000_000,
            cash=0,
            snapshots=snapshots,
            thresholds=PortfolioRiskThresholds(stale_after_hours=24),
            now=now,
            allow_mock=False,
        )
        single = next(alert for alert in state.risk_alerts if alert.id == "single-stock-concentration")
        stale_alert = next(alert for alert in state.risk_alerts if alert.id == "stale-data")
        html = portfolio_risk_cockpit_html(state)
        self.assertEqual(single.actionability, "blocked_by_stale_data")
        self.assertEqual(stale_alert.actionability, "review_only")
        self.assertTrue(single.is_stale)
        self.assertIn("오래된 데이터", html)
        self.assertIn("최신 가격 반영 후 다시 확인하세요.", html)
        self.assertIn("2026.07.08 16:55", html)
        self.assertNotIn("2026-07-08T07:55:27+00:00", html)


if __name__ == "__main__":
    unittest.main()
