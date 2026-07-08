from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import unittest

from src.institutional import (
    DataPoint,
    DataSourceMeta,
    ForwardAlphaRankingPanelState,
    ForwardAlphaRankRow,
    OptimizerConstraints,
    alert_center_api_response,
    build_portfolio_optimizer_alert_center,
    generate_portfolio_alerts,
    optimize_target_weights,
    portfolio_optimizer_alert_center_html,
    portfolio_optimizer_api_response,
)
from src.ui.korean_labels import module_title, ui_label


def meta(stale: bool = False) -> DataSourceMeta:
    return DataSourceMeta(
        source="UnitAlpha",
        provider="UnitTest",
        source_url=None,
        as_of_date="2026-07-08",
        available_at="2026-07-08T12:00:00+00:00",
        fetched_at="2026-07-08T12:00:00+00:00",
        frequency="daily",
        unit="score",
        quality_score=90,
        is_fallback=False,
        stale_data_flag=stale,
        source_table_or_endpoint="/api/dashboard/forward-alpha-ranking",
        confidence_score=90,
        missing_data_flag=False,
    )


def alpha_row(
    code: str,
    score: int,
    *,
    sector: str = "Tech",
    rating: str = "BUY_CANDIDATE",
    liquidity: int = 80,
    risk_flags: tuple[str, ...] = (),
    stale: bool = False,
) -> ForwardAlphaRankRow:
    return ForwardAlphaRankRow(
        code=code,
        name=f"Stock {code}",
        sector=sector,
        final_alpha_score=score,
        confidence_score=82,
        rating=rating,  # type: ignore[arg-type]
        valuation_score=80,
        quality_score=78,
        catalyst_score=65,
        value_up_score=40,
        smart_money_score=70,
        short_pressure_score=65,
        macro_score=60,
        liquidity_score=liquidity,
        risk_penalty=0,
        positive_drivers=("quality", "flow"),
        negative_drivers=(),
        risk_flags=risk_flags,
        stale_data_warning="stale" if stale else None,
        score_version="baseline_rule_score_v1",
        feature_snapshot_id=f"snap-{code}",
        meta=meta(stale),
    )


def alpha_state(rows: tuple[ForwardAlphaRankRow, ...]) -> ForwardAlphaRankingPanelState:
    point_meta = meta(any(row.meta.stale_data_flag for row in rows))
    return ForwardAlphaRankingPanelState(
        module_id="ForwardAlphaRankingPanel",
        status="stale" if point_meta.stale_data_flag else "ready",
        title=module_title("Forward Alpha Ranking Panel"),
        summary="unit",
        data_points=(DataPoint("ranked_count", "Ranked Count", len(rows), point_meta, str(len(rows))),),
        explanation=("unit",),
        risk_flags=(),
        stale_after_minutes=1440,
        ranking_rows=rows,
        feature_snapshot_id="unit-snapshot",
        latest_source_at="2026-07-08T12:00:00+00:00",
    )


class PortfolioOptimizerAlertCenterTests(unittest.TestCase):
    def test_optimizer_respects_max_weight(self):
        rows = (
            alpha_row("001111", 95, sector="Tech"),
            alpha_row("002222", 90, sector="Tech"),
            alpha_row("003333", 88, sector="Financials"),
        )
        targets = optimize_target_weights(rows, constraints=OptimizerConstraints(max_single_stock_weight=0.07, max_sector_weight=0.30))
        self.assertTrue(targets)
        self.assertTrue(all(weight <= 0.07 + 1e-9 for weight in targets.values()))

    def test_severe_risk_stocks_get_zero_target_weight(self):
        rows = (
            alpha_row("001111", 95),
            alpha_row("009999", 92, rating="HIGH_RISK_EXCLUDE", risk_flags=("severe_dilution_risk",)),
        )
        targets = optimize_target_weights(rows, constraints=OptimizerConstraints())
        self.assertEqual(targets["009999"], 0.0)

    def test_illiquid_stocks_are_capped(self):
        rows = (
            alpha_row("001111", 95, liquidity=90),
            alpha_row("008888", 94, liquidity=15),
        )
        holdings = [{"code": "008888", "market": "KOSPI", "current_weight": 0.0, "current_value": 0.0}]
        constraints = OptimizerConstraints(illiquid_cap=0.02)
        targets = optimize_target_weights(rows, holdings=holdings, constraints=constraints)
        self.assertLessEqual(targets["008888"], 0.02 + 1e-9)

    def test_alerts_trigger_correctly(self):
        state = build_portfolio_optimizer_alert_center(
            alpha_state=alpha_state(
                (
                    alpha_row("001111", 30, liquidity=20, risk_flags=("severe_dilution_risk",)),
                    alpha_row("002222", 82, stale=True),
                )
            ),
            holdings=[
                {"code": "001111", "name": "Risky", "sector": "Tech", "market": "KOSPI", "current_weight": 0.12, "current_value": 12_000_000},
                {"code": "002222", "name": "Stale", "sector": "Tech", "market": "KOSPI", "current_weight": 0.04, "current_value": 4_000_000},
            ],
            total_portfolio_value=100_000_000,
            cash_ratio=0.02,
            constraints=OptimizerConstraints(max_single_stock_weight=0.07, cash_buffer=0.05),
            now=datetime(2026, 7, 8, tzinfo=timezone.utc),
            allow_mock=False,
        )
        alert_types = {alert.alert_type for alert in state.alerts}
        self.assertIn("concentration_warning", alert_types)
        self.assertIn("negative_dart_event", alert_types)
        self.assertIn("liquidity_deterioration", alert_types)
        self.assertIn("stale_data_warning", alert_types)
        self.assertIn("top_holding_score_downgrade", alert_types)

    def test_no_automatic_trading_endpoint_exists(self):
        state = build_portfolio_optimizer_alert_center(now=datetime(2026, 7, 8, tzinfo=timezone.utc), allow_mock=True)
        optimizer_payload = portfolio_optimizer_api_response(state)
        alerts_payload = alert_center_api_response(state)
        serialized = json.dumps([optimizer_payload, alerts_payload], sort_keys=True)
        self.assertEqual(optimizer_payload["apiPath"], "/api/dashboard/portfolio-optimizer")
        self.assertEqual(alerts_payload["apiPath"], "/api/dashboard/alerts")
        self.assertNotIn("place-order", serialized)
        self.assertNotIn("execute-trade", serialized)
        self.assertNotIn("/orders", serialized)

    def test_panel_renders_loading_empty_error_and_ready_states(self):
        empty_state = build_portfolio_optimizer_alert_center(allow_mock=False)
        self.assertEqual(empty_state.status, "empty")
        self.assertIn("최적화 결과 없음", portfolio_optimizer_alert_center_html(empty_state))
        self.assertIn("Loading", portfolio_optimizer_alert_center_html(replace(empty_state, status="loading", summary="Loading.")))
        self.assertIn("Error", portfolio_optimizer_alert_center_html(replace(empty_state, status="error", summary="Error.")))

        ready_state = build_portfolio_optimizer_alert_center(now=datetime(2026, 7, 8, tzinfo=timezone.utc), allow_mock=True)
        self.assertTrue(ready_state.recommendation_rows)
        html = portfolio_optimizer_alert_center_html(ready_state)
        self.assertIn(module_title("Portfolio Optimizer & Alert Center"), html)
        self.assertIn(ui_label("No order API"), html)
        self.assertTrue(ready_state.stress_scenarios)

    def test_api_response_shape(self):
        state = build_portfolio_optimizer_alert_center(now=datetime(2026, 7, 8, tzinfo=timezone.utc), allow_mock=True)
        optimizer_payload = portfolio_optimizer_api_response(state)
        alerts_payload = alert_center_api_response(state)
        self.assertEqual(optimizer_payload["moduleId"], "PortfolioOptimizerAlertCenter")
        self.assertIn("recommendationRows", optimizer_payload)
        self.assertIn("rejectedCandidates", optimizer_payload)
        self.assertIn("stressScenarios", optimizer_payload)
        self.assertIn("alerts", optimizer_payload)
        self.assertEqual(alerts_payload["moduleId"], "PortfolioOptimizerAlertCenter")
        self.assertIn("alerts", alerts_payload)
        self.assertTrue(optimizer_payload["recommendationRows"])


if __name__ == "__main__":
    unittest.main()
