from __future__ import annotations

import html
import math
from typing import Any


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def format_portfolio_krw(value: Any) -> str:
    """Format a full KRW amount without abbreviating the displayed value."""
    number = _finite_number(value)
    return "계산 불가" if number is None else f"{number:,.0f}원"


def format_portfolio_percent(value: Any) -> str:
    """Format a percentage value that is already expressed on a 0-100 scale."""
    number = _finite_number(value)
    return "계산 불가" if number is None else f"{number:.1f}%"


def resolve_portfolio_number(value: Any, *, default: float) -> float:
    """Use the default only for missing/invalid input, never for a valid zero."""
    number = _finite_number(value)
    return float(default) if number is None else number


def portfolio_kpi_cards_html(
    *,
    total_assets: Any,
    cash: Any,
    cash_percent: Any,
    regime_label: Any,
    regime_score: Any,
) -> str:
    """Render the portfolio KPI values with stable, responsive semantics."""
    score = _finite_number(regime_score)
    score_text = "계산 불가" if score is None else f"{score:.0f}"
    regime_text = f"{str(regime_label or '확인 필요')} / {score_text}"
    cards = (
        ("총자산", format_portfolio_krw(total_assets)),
        ("현금", format_portfolio_krw(cash)),
        ("현금 비중", format_portfolio_percent(cash_percent)),
    )
    card_html = "".join(
        f"""
        <article class="portfolio-kpi-card">
            <div class="portfolio-kpi-label">{html.escape(label)}</div>
            <div class="portfolio-kpi-value">{html.escape(value)}</div>
        </article>
        """
        for label, value in cards
    )
    return f"""
    <section class="portfolio-kpi-region" aria-label="포트폴리오 핵심 지표">
        <div class="portfolio-kpi-grid">{card_html}</div>
        <div class="portfolio-kpi-context">
            <span>시장 국면</span>
            <strong>{html.escape(regime_text)}</strong>
        </div>
    </section>
    """
