from pathlib import Path
import unittest


APP_TEXT = Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")


class PortfolioVisibilityTests(unittest.TestCase):
    def test_portfolio_intelligence_shell_classes_exist(self) -> None:
        for token in [
            ".portfolio-intelligence-shell",
            ".portfolio-intelligence-grid",
            ".pi-detail-grid",
            ".pi-card",
            ".pi-card-header",
            ".pi-progress",
            ".pi-rebalance-item",
            ".pi-metric-tile",
            ".pi-benchmark-strip",
            ".pi-holding-row",
            ".pi-signal-row",
            ".pi-insight-block",
        ]:
            self.assertIn(token, APP_TEXT)

    def test_top_portfolio_cards_render_inside_one_dark_grid(self) -> None:
        section_start = APP_TEXT.index("def render_portfolio_intelligence_section")
        section_text = APP_TEXT[section_start : section_start + 4000]
        self.assertIn('<section class="portfolio-intelligence-shell"', section_text)
        self.assertIn('<div class="portfolio-intelligence-grid">', section_text)
        self.assertIn("portfolio_health_card_html", section_text)
        self.assertIn("allocation_drift_card_html", section_text)
        self.assertIn("rebalance_candidates_card_html", section_text)

    def test_rebalance_card_uses_readable_card_rows(self) -> None:
        card_start = APP_TEXT.index("def rebalance_candidates_card_html")
        card_text = APP_TEXT[card_start : card_start + 2200]
        self.assertIn("pi-rebalance-item", card_text)
        self.assertIn("주문 아님", card_text)
        self.assertNotIn("rank-row", card_text)
        self.assertNotIn("signal-row", card_text)

    def test_risk_return_uses_metric_tiles_and_benchmark_strip(self) -> None:
        card_start = APP_TEXT.index("def risk_return_panel_html")
        card_text = APP_TEXT[card_start : card_start + 3400]
        for token in ["CAGR", "기간 수익률", "연율 변동성", "Sharpe", "최대 낙폭", "Beta"]:
            self.assertIn(token, card_text)
        self.assertIn("pi-metric-grid", card_text)
        self.assertIn("pi-benchmark-strip", card_text)
        self.assertIn("벤치마크 대비 기간 초과수익", card_text)

    def test_concentration_watchlist_and_insight_cards_are_structured(self) -> None:
        concentration_start = APP_TEXT.index("def concentration_card_html")
        concentration_text = APP_TEXT[concentration_start : concentration_start + 2800]
        self.assertIn("pi-holding-row", concentration_text)
        self.assertIn("상위 비중", concentration_text)
        self.assertIn("HHI", concentration_text)
        self.assertNotIn("signal-row", concentration_text)

        watchlist_start = APP_TEXT.index("def watchlist_signals_card_html")
        watchlist_text = APP_TEXT[watchlist_start : watchlist_start + 2200]
        self.assertIn("pi-signal-row", watchlist_text)
        self.assertIn("신호 없음", APP_TEXT)
        self.assertNotIn("rank-row", watchlist_text)

        insight_start = APP_TEXT.index("def insight_engine_card_html")
        insight_text = APP_TEXT[insight_start : insight_start + 3400]
        self.assertIn("pi-insight-block", insight_text)
        self.assertIn("관찰", insight_text)
        self.assertIn("후보 행동", insight_text)

    def test_detail_section_renders_cards_before_charts(self) -> None:
        section_start = APP_TEXT.index("def render_portfolio_intelligence_section")
        section_text = APP_TEXT[section_start : section_start + 7000]
        self.assertIn("리스크·신호·인사이트", section_text)
        self.assertIn("risk_return_panel_html(portfolio_metrics, relative_return)", section_text)
        self.assertIn("concentration_card_html(holdings, concentration)", section_text)
        self.assertIn("insight_engine_card_html(insights, portfolio_metrics)", section_text)
        self.assertIn("watchlist_signals_card_html(watchlist_signals)", section_text)
        self.assertNotIn("st.caption(f\"벤치마크 대비 기간 초과수익", section_text)

    def test_mobile_grid_collapses_to_single_column(self) -> None:
        self.assertIn(".portfolio-intelligence-grid", APP_TEXT)
        self.assertIn("grid-template-columns: 1fr;", APP_TEXT)


if __name__ == "__main__":
    unittest.main()
