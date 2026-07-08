from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.institutional import PortfolioRiskThresholds, build_portfolio_risk_cockpit, portfolio_risk_cockpit_html
from src.portfolio.mock_data import MOCK_HOLDINGS
from src.portfolio.models import Holding


class Snapshot:
    def __init__(self, asof: datetime, source: str = "FinanceDataReader") -> None:
        self.asof = asof
        self.source = source
        self.frequency = "daily"
        self.unit = "KRW"
        self.quality_score = 92
        self.is_fallback = False
        self.warnings: list[str] = []
        self.errors: list[str] = []


FORBIDDEN_VISIBLE_STRINGS = (
    "Single-stock concentration",
    "Sector concentration",
    "Low cash buffer",
    "Top-10 concentration",
    "Stale data check",
    "Review concentration",
    "Check whether",
    "Cash is",
    "Top 10 holdings",
    "At least one holding",
    "Refresh prices",
    "Weight =",
    "Volatility and drawdown",
    "Alerts are review gates",
)

RAW_ISO_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\+\d{2}:\d{2}|Z)")


def _mock_html(now: datetime) -> str:
    snapshots = {holding.symbol: Snapshot(now) for holding in MOCK_HOLDINGS}
    state = build_portfolio_risk_cockpit([], snapshots=snapshots, now=now, allow_mock=True)
    return portfolio_risk_cockpit_html(state)


def _stale_html(now: datetime) -> str:
    holdings = [
        Holding("h1", "005930", "Samsung Electronics", "stocks", 10, 70000, 100000, "KRW", "Semiconductor", "KR", "KS11")
    ]
    snapshots = {holding.symbol: Snapshot(now - timedelta(days=3)) for holding in holdings}
    state = build_portfolio_risk_cockpit(
        holdings,
        total_assets=1_000_000,
        cash=0,
        snapshots=snapshots,
        thresholds=PortfolioRiskThresholds(stale_after_hours=24),
        now=now,
        allow_mock=False,
    )
    return portfolio_risk_cockpit_html(state)


def main() -> int:
    now = datetime(2026, 7, 8, 7, 55, 27, tzinfo=timezone.utc)
    html_samples = [_mock_html(now), _stale_html(now)]
    failures: list[str] = []
    for html in html_samples:
        for forbidden in FORBIDDEN_VISIBLE_STRINGS:
            if forbidden in html:
                failures.append(f"Forbidden visible English string found: {forbidden}")
        if RAW_ISO_PATTERN.search(html):
            failures.append("Raw ISO timestamp found in risk alert UI HTML.")
    mock_html = html_samples[0]
    if "예시 알림" not in mock_html or "모의 데이터" not in mock_html:
        failures.append("Mock portfolio risk alerts are not clearly labeled as example/mock.")
    if ">긴급<" in mock_html:
        failures.append("Mock portfolio risk alert is displayed as real urgent.")
    if failures:
        for failure in failures:
            print(failure)
        return 1
    print("Risk alert Korean UI audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
