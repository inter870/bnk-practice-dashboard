from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from typing import Any

from .models import (
    AllocationSlice,
    DARTDisclosureCatalystPanelState,
    DARTDisclosureEventRow,
    DataPoint,
    DataTrustSourcePanelState,
    FXRatesImpactRow,
    FXRatesIndicatorRow,
    ForwardAlphaRankingPanelState,
    ForwardAlphaRankRow,
    FundamentalQualityPanelState,
    FundamentalQualityRow,
    HoldingRiskRow,
    KRWRatesFXDashboardState,
    MacroIndicatorRow,
    MarketRegimeMacroRadarState,
    PortfolioRiskCockpitState,
    OptimizerRecommendationRow,
    PortfolioAlertRow,
    PortfolioOptimizerAlertCenterState,
    RecentMacroChange,
    RiskAlert,
    SectorFlowHeatmapRow,
    SectorTailwindRow,
    SourceCoverageRow,
    SectorValuationRow,
    SmartMoneyFlowRow,
    SmartMoneyFlowShortPressurePanelState,
    StressScenarioRow,
    ValuationMetricRow,
    ValuationRelativeCheapnessPanelState,
)
from src.ui.korean_labels import (
    action_label,
    asset_class_label,
    dart_category_label,
    ko_sentence,
    module_title,
    rating_label,
    severity_label,
    signal_label,
    source_meta_line,
    status_label,
    ui_label,
)
from src.ui.korean_market_colors import (
    getActionColorClass,
    getChartSeriesColor,
    getRatingColorClass,
    getRiskSeverityColorClass,
)


def _fmt_krw(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"
    return f"KRW {number:,.0f}"


def _fmt_pct(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"
    return f"{number * 100:.1f}%"


KST = timezone(timedelta(hours=9))


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_ko_date(value: Any) -> str:
    stamp = _parse_datetime(value)
    if stamp is not None:
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp.astimezone(KST).strftime("%Y.%m.%d")
    text = str(value or "").strip()
    if len(text) >= 10:
        return text[:10].replace("-", ".")
    return "N/A"


def _format_ko_datetime(value: Any) -> str:
    stamp = _parse_datetime(value)
    if stamp is None:
        return "N/A"
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(KST).strftime("%Y.%m.%d %H:%M")


def _source_label_ko(source: str | None) -> str:
    text = str(source or "").strip()
    lowered = text.lower()
    if not text:
        return "N/A"
    if "mock portfolio" in lowered:
        return "모의 포트폴리오 데이터"
    if "sidebar" in lowered or "manual portfolio" in lowered or "manual_holdings" in lowered:
        return "수동 입력 보유 종목"
    if "csv" in lowered or "import" in lowered:
        return "CSV 가져오기 보유 종목"
    if "kis" in lowered or "broker" in lowered:
        return "브로커 보유 종목"
    if "finance" in lowered:
        return "FinanceDataReader"
    if "naver" in lowered:
        return "Naver Finance"
    return text


def _metric(state: PortfolioRiskCockpitState, key: str) -> DataPoint | None:
    return next((point for point in state.data_points if point.key == key), None)


def _badge(status: str) -> str:
    tone = {
        "ready": "good",
        "stale": "warn",
        "empty": "warn",
        "error": "risk",
        "loading": "info",
    }.get(status, "info")
    label = status_label(status)
    return f'<span class="pi-badge {tone}">{html.escape(label)}</span>'


def _source_line(point: DataPoint | None) -> str:
    if point is None:
        return "출처: N/A · 기준일: N/A · 수집 시각: N/A"
    meta = point.meta
    stale = " · 오래된 데이터" if meta.stale_data_flag else ""
    missing = " · 누락 데이터" if meta.missing_data_flag else ""
    return (
        f"출처: {_source_label_ko(meta.source)} · "
        f"기준일: {_format_ko_date(meta.as_of_date)} · "
        f"수집 시각: {_format_ko_datetime(meta.fetched_at)}{stale}{missing}"
    )


def _metric_card(point: DataPoint | None, fallback_label: str) -> str:
    label = ui_label(point.label if point else fallback_label)
    value = point.display_value if point and point.display_value is not None else "N/A"
    stale_class = " warn" if point and point.meta.stale_data_flag else " info"
    stale_label = "오래된 데이터" if point and point.meta.stale_data_flag else "출처"
    return f"""
    <div class="pi-rebalance-item">
        <div class="pi-rebalance-top">
            <div class="pi-rebalance-asset">{html.escape(label)}</div>
            <span class="pi-badge{stale_class}">{html.escape(stale_label)}</span>
        </div>
        <div class="pi-rebalance-amount" style="text-align:left; margin-top:6px;">{html.escape(str(value))}</div>
        <div class="pi-rebalance-impact">{html.escape(_source_line(point))}</div>
    </div>
    """


def _allocation_rows(items: tuple[AllocationSlice, ...], limit: int = 5) -> str:
    if not items:
        return f'<div class="pi-rebalance-reason">{html.escape(ko_sentence("No allocation data."))}</div>'
    rows = []
    colors = ["#a78bfa", "#38bdf8", "#34d399", "#f59e0b", "#fb7185", "#94a3b8"]
    for idx, item in enumerate(items[:limit]):
        width = max(2, min(100, item.weight * 100))
        rows.append(
            f"""
            <div class="pi-allocation-row">
                <div class="pi-asset-label">{html.escape(asset_class_label(item.label))}</div>
                <div class="pi-allocation-track"><div class="pi-allocation-fill" style="width:{width:.1f}%; background:{colors[idx % len(colors)]};"></div></div>
                <div class="pi-allocation-value">{html.escape(_fmt_pct(item.weight))}<br/><small>{html.escape(_fmt_krw(item.value))}</small></div>
            </div>
            """
        )
    return "".join(rows)


def _holding_rows(items: tuple[HoldingRiskRow, ...]) -> str:
    if not items:
        return f'<div class="pi-rebalance-reason">{html.escape(ko_sentence("No holdings data."))}</div>'
    rows = []
    for item in items:
        warning = f'<span class="pi-badge warn">{html.escape(ko_sentence(item.liquidity_warning))}</span>' if item.liquidity_warning else ""
        rows.append(
            f"""
            <div class="pi-signal-row" style="grid-template-columns: minmax(120px, 1fr) 84px 82px;">
                <div><strong>{html.escape(item.name)}</strong><br/><span>{html.escape(item.symbol)} | {html.escape(item.sector)}</span></div>
                <div>{html.escape(_fmt_krw(item.market_value))}</div>
                <div>{html.escape(_fmt_pct(item.weight))}</div>
            </div>
            {warning}
            """
        )
    return "".join(rows)


def _alert_actionability_label(alert: RiskAlert) -> str:
    return {
        "actionable": "실전 알림",
        "review_only": "검토용",
        "example_only": "예시 알림",
        "blocked_by_stale_data": "실전 판단 제한",
        "blocked_by_missing_holdings": "실전 판단 제한",
        "blocked_by_mock_data": "모의 데이터",
    }.get(alert.actionability, "검토용")


def _alert_tone(alert: RiskAlert) -> str:
    if alert.actionability == "example_only":
        return "warn"
    if alert.actionability == "blocked_by_stale_data" or alert.is_stale:
        return "warn"
    if alert.severity == "critical":
        return "risk"
    if alert.severity == "warning":
        return "warn"
    return "info"


def _alert_source_line(alert: RiskAlert) -> str:
    parts = [
        f"보유: {alert.holdings_source_label_ko or _source_label_ko(alert.holdings_source)}",
        f"가격: {alert.price_source_label_ko or _source_label_ko(alert.price_source or alert.meta.source)}",
    ]
    if alert.affected_sector:
        parts.append(f"섹터: {alert.sector_metadata_source_label_ko or _source_label_ko(alert.sector_metadata_source)}")
    parts.append(f"기준일: {_format_ko_date(alert.as_of_date or alert.meta.as_of_date)}")
    parts.append(f"수집: {alert.fetched_at_ko or _format_ko_datetime(alert.fetched_at or alert.meta.fetched_at)}")
    parts.append(f"계산: {alert.calculation_method_label_ko}")
    if alert.is_stale:
        parts.append("오래된 데이터")
    if alert.is_mock:
        parts.append("모의 데이터")
    return " · ".join(parts)


def _risk_alert_banner(alerts: tuple[RiskAlert, ...]) -> str:
    if not alerts:
        return ""
    if any(alert.is_mock for alert in alerts):
        text = "현재 모의 포트폴리오 기준입니다. 실제 보유 종목을 입력하면 실전 리스크 알림으로 전환됩니다."
        tone = "warn"
    elif any(alert.is_stale for alert in alerts):
        text = "일부 데이터가 오래되었습니다. 최신 가격으로 새로고침한 뒤 확인하세요."
        tone = "warn"
    else:
        text = "실제 또는 수동 보유 데이터와 최신 가격 기준으로 계산했습니다."
        tone = "good"
    return f'<div class="pi-rebalance-item pi-alert-banner"><span class="pi-badge {tone}">{html.escape(text)}</span></div>'


def _risk_alert_chips(alerts: tuple[RiskAlert, ...]) -> str:
    if not alerts:
        return ""
    counts = {
        "긴급": sum(1 for alert in alerts if alert.display_severity_ko == "긴급"),
        "주의": sum(1 for alert in alerts if alert.display_severity_ko == "주의"),
        "오래된 데이터": sum(1 for alert in alerts if alert.is_stale),
        "예시 알림": sum(1 for alert in alerts if alert.is_mock),
    }
    chips = [
        f'<span class="pi-badge {"risk" if label == "긴급" else "warn" if count else "info"}">{html.escape(label)} {count}</span>'
        for label, count in counts.items()
        if count
    ]
    return '<div style="display:flex; gap:6px; flex-wrap:wrap; margin-bottom:10px;">' + "".join(chips) + "</div>" if chips else ""


def _alert_rows(alerts: tuple[RiskAlert, ...]) -> str:
    if not alerts:
        return f"""
        <div class="pi-rebalance-item">
            <div class="pi-rebalance-asset">{html.escape(ko_sentence("No major alert"))}</div>
            <div class="pi-rebalance-reason">{html.escape(ko_sentence("Current thresholds do not flag concentration, cash, or liquidity warnings."))}</div>
        </div>
        """
    rows = []
    for alert in alerts[:5]:
        tone = _alert_tone(alert)
        title = alert.title_ko or alert.title
        body = alert.body_ko or alert.message
        action = alert.review_action_ko or alert.candidate_action
        threshold_line = alert.explanation_ko or ""
        severity_text = alert.display_severity_ko or severity_label(alert.severity)
        actionability_text = _alert_actionability_label(alert)
        mock_badge = '<span class="pi-badge warn">모의 데이터</span>' if alert.is_mock else ""
        stale_badge = '<span class="pi-badge warn">오래된 데이터</span>' if alert.is_stale else ""
        rows.append(
            f"""
            <div class="pi-rebalance-item">
                <div class="pi-rebalance-top">
                    <div class="pi-rebalance-asset">{html.escape(title)}</div>
                    <div style="display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-end;">
                        <span class="pi-badge {tone}">{html.escape(severity_text)}</span>
                        <span class="pi-badge info">{html.escape(actionability_text)}</span>
                        {mock_badge}
                        {stale_badge}
                    </div>
                </div>
                <div class="pi-rebalance-amount" style="text-align:left; margin-top:8px;">{html.escape(threshold_line)}</div>
                <div class="pi-rebalance-reason">{html.escape(body)}</div>
                <div class="pi-rebalance-impact">{html.escape(action)}</div>
                <div class="pi-rebalance-impact">{html.escape(_alert_source_line(alert))}</div>
            </div>
            """
        )
    return "".join(rows)


def portfolio_risk_cockpit_html(state: PortfolioRiskCockpitState) -> str:
    total = _metric(state, "total_portfolio_value")
    cash = _metric(state, "cash_ratio")
    top = _metric(state, "top_holding_weight")
    top10 = _metric(state, "top10_concentration")
    volatility = _metric(state, "portfolio_volatility_proxy")
    drawdown = _metric(state, "max_drawdown_proxy")

    if state.status == "loading":
        body = f"""
        <div class="pi-rebalance-item">
            <div class="pi-rebalance-asset">{html.escape(status_label("loading"))}</div>
            <div class="pi-rebalance-reason">{html.escape(ko_sentence("Portfolio risk data is being prepared."))}</div>
        </div>
        """
    elif state.status == "error":
        body = f"""
        <div class="pi-rebalance-item">
            <div class="pi-rebalance-asset">{html.escape(status_label("error"))}</div>
            <div class="pi-rebalance-reason">{html.escape(ko_sentence("Portfolio risk calculation failed."))}</div>
        </div>
        """
    elif state.status == "empty":
        body = f"""
        <div class="pi-rebalance-item">
            <div class="pi-rebalance-asset">보유종목 없음</div>
            <div class="pi-rebalance-reason">{html.escape(ko_sentence("Enter holdings CSV in the sidebar to calculate risk concentration."))}</div>
        </div>
        """
    else:
        body = f"""
        <div class="portfolio-intelligence-grid">
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Capital Risk Gates"))}</strong><span>{html.escape(ui_label("before adding capital"))}</span></div>
                <div class="pi-card-body">
                    {_metric_card(total, "Total Portfolio Value")}
                    {_metric_card(cash, "Cash Ratio")}
                    {_metric_card(top, "Largest Single Holding")}
                    {_metric_card(top10, "Top 10 Concentration")}
                </div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Allocation Map"))}</strong><span>{html.escape(ui_label("asset / market / sector / currency"))}</span></div>
                <div class="pi-card-body">
                    <div class="pi-badge info">{html.escape(ui_label("Asset"))}</div>
                    {_allocation_rows(state.asset_allocation, 4)}
                    <div class="pi-badge info" style="margin-top:10px;">{html.escape(ui_label("Sector"))}</div>
                    {_allocation_rows(state.sector_allocation, 4)}
                    <div class="pi-badge info" style="margin-top:10px;">{html.escape(ui_label("Currency"))}</div>
                    {_allocation_rows(state.currency_allocation, 4)}
                </div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Top Holdings"))}</strong><span>{html.escape(ui_label("top risk drivers"))}</span></div>
                <div class="pi-card-body">
                    {_holding_rows(state.top5_holdings)}
                    {_metric_card(volatility, "Volatility Proxy")}
                    {_metric_card(drawdown, "Max Drawdown Proxy")}
                </div>
            </div>
        </div>
        <div class="pi-detail-grid">
            <div class="pi-card pi-risk-card">
                <div class="pi-card-header"><strong>리스크 알림</strong><span>집중도, 현금 버퍼, 데이터 신선도 점검</span></div>
                <div class="pi-card-body">
                    {_risk_alert_banner(state.risk_alerts)}
                    {_risk_alert_chips(state.risk_alerts)}
                    <div class="pi-rebalance-list">{_alert_rows(state.risk_alerts)}</div>
                </div>
            </div>
            <div class="pi-card pi-insight-card" style="grid-column: span 7;">
                <div class="pi-card-header"><strong>점검 목록</strong><span>근거 기반 검토 기준</span></div>
                <div class="pi-card-body">
                    <div class="pi-reason-list">
                        {''.join(f'<div class="pi-reason"><span class="pi-dot"></span><span>{html.escape(ko_sentence(item))}</span></div>' for item in state.explanation)}
                    </div>
                    <div class="pi-rebalance-impact" style="margin-top:12px;">{html.escape(_source_line(total))}</div>
                </div>
            </div>
        </div>
        """
    return f"""
    <section class="portfolio-intelligence-shell" aria-label="PortfolioRiskCockpit" data-module-id="PortfolioRiskCockpit">
        <div class="portfolio-intelligence-title">
            <div>
                <strong>{html.escape(module_title("Portfolio Risk Cockpit"))}</strong>
                <span>{html.escape(ko_sentence("No holdings data.") if state.status == "empty" else ko_sentence(state.summary))}</span>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                {_badge(state.status)}
                <span class="pi-badge info">{html.escape(ui_label("No order execution"))}</span>
            </div>
        </div>
        {body}
    </section>
    """


def _coverage_tone(status: str) -> str:
    return {
        "available": "good",
        "partial": "info",
        "mock": "warn",
        "stale": "warn",
        "missing": "risk",
        "connected": "good",
        "partially_connected": "info",
        "manual": "info",
        "missing_key": "warn",
        "adapter_missing": "warn",
        "planned": "warn",
        "cache_only": "warn",
        "unavailable": "risk",
        "error": "risk",
    }.get(status, "info")


def _coverage_rows(rows: tuple[SourceCoverageRow, ...]) -> str:
    if not rows:
        return """
        <div class="pi-rebalance-item">
            <div class="pi-rebalance-asset">출처 커버리지 행 없음</div>
            <div class="pi-rebalance-reason">메타데이터 어댑터가 출처 커버리지를 반환하지 않았습니다.</div>
        </div>
        """
    rendered = []
    for row in rows:
        key_text = ", ".join(row.missing_api_keys) if row.missing_api_keys else "없음"
        notes = " / ".join(ko_sentence(note) for note in row.notes[:2]) if row.notes else ko_sentence("No additional note.")
        meta = row.meta
        endpoint = meta.source_table_or_endpoint or "N/A"
        rendered.append(
            f"""
            <div class="pi-signal-row" style="grid-template-columns: minmax(150px, 1fr) 86px minmax(120px, 1fr) minmax(130px, 1fr);">
                <div><strong>{html.escape(ui_label(row.label))}</strong><br/><span>{html.escape(endpoint)}</span></div>
                <div><span class="pi-badge {_coverage_tone(row.coverage_status)}">{html.escape(status_label(row.coverage_status))}</span></div>
                <div>{html.escape(meta.source)}<br/><span>신뢰도 {html.escape(str(meta.confidence_score if meta.confidence_score is not None else 'N/A'))}/100</span></div>
                <div>{html.escape(meta.as_of_date or 'N/A')}<br/><span>{html.escape('누락 키: ' + key_text)}</span></div>
            </div>
            <div class="pi-rebalance-impact" style="margin:0 0 8px 0;">{html.escape(notes)} · 수집 시각 {html.escape(meta.fetched_at or 'N/A')}</div>
            """
        )
    return "".join(rendered)


def _coverage_rows(rows: tuple[SourceCoverageRow, ...]) -> str:
    if not rows:
        return """
        <div class="pi-rebalance-item">
            <div class="pi-rebalance-asset">출처 커버리지 없음</div>
            <div class="pi-rebalance-reason">메타데이터 어댑터가 출처 커버리지를 반환하지 않았습니다.</div>
        </div>
        """
    rendered = []
    for row in rows:
        meta = row.meta
        endpoint = meta.source_table_or_endpoint or "N/A"
        status = row.status or row.coverage_status
        status_label_text = row.status_label_ko or status_label(status)
        source_label = row.active_source_label_ko or meta.source
        accuracy = row.accuracy_grade_label_ko or row.exactness_label_ko or "표시 불가"
        required = ", ".join(row.required_keys or row.required_api_keys) if (row.required_keys or row.required_api_keys) else "필요 키 없음"
        missing = ", ".join(row.missing_keys or row.missing_api_keys) if (row.missing_keys or row.missing_api_keys) else "없음"
        if row.missing_keys or row.missing_api_keys:
            key_text = "누락 키 " + missing
        elif row.is_planned:
            key_text = "키 확인 전 어댑터 미연결"
        elif row.is_keyless:
            key_text = "키 없이 공개 데이터 사용 중"
        elif row.required_keys or row.required_api_keys:
            key_text = "필요 키 설정됨"
        else:
            key_text = "필요 키 없음"
        notes = row.message_ko or (" / ".join(ko_sentence(note) for note in row.notes[:2]) if row.notes else ko_sentence("No additional note."))
        action = row.action_required_ko or key_text
        rendered.append(
            f"""
            <div class="pi-signal-row" style="grid-template-columns: minmax(150px, 1fr) 96px minmax(130px, 1fr) minmax(160px, 1fr);">
                <div><strong>{html.escape(ui_label(row.label))}</strong><br/><span>{html.escape(endpoint)}</span></div>
                <div><span class="pi-badge {_coverage_tone(status)}">{html.escape(status_label_text)}</span><br/><small>{html.escape(accuracy)}</small></div>
                <div>{html.escape(source_label)}<br/><span>신뢰도 {html.escape(str(meta.confidence_score if meta.confidence_score is not None else 'N/A'))}/100</span></div>
                <div>기준일 {html.escape(meta.as_of_date or 'N/A')}<br/><span>{html.escape(key_text)}</span></div>
            </div>
            <div class="pi-rebalance-impact" style="margin:0 0 8px 0;">{html.escape(notes)} · {html.escape(action)} · 수집 시각 {html.escape(meta.fetched_at or 'N/A')} · 필요 키 {html.escape(required)} · 누락 {html.escape(missing)}</div>
            """
        )
    return "".join(rendered)


def data_trust_source_panel_html(state: DataTrustSourcePanelState) -> str:
    stale_text = ", ".join(state.stale_sources[:4]) if state.stale_sources else "없음"
    missing_text = ", ".join(state.missing_sources[:4]) if state.missing_sources else "없음"
    key_text = ", ".join(state.missing_api_keys) if state.missing_api_keys else "없음"
    pit_tone = "good" if state.point_in_time_status == "compliant" else "warn"
    return f"""
    <section class="portfolio-intelligence-shell" aria-label="DataTrustSourcePanel" data-module-id="DataTrustSourcePanel">
        <div class="portfolio-intelligence-title">
            <div>
                <strong>{html.escape(module_title("Data Trust & Source Panel"))}</strong>
                <span>{html.escape(ko_sentence(state.summary))}</span>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                {_badge(state.status)}
                <span class="pi-badge {pit_tone}">PIT {html.escape(status_label(state.point_in_time_status))}</span>
            </div>
        </div>
        <div class="portfolio-intelligence-grid">
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Refresh & Trust"))}</strong><span>{html.escape(ui_label("metadata contract"))}</span></div>
                <div class="pi-card-body">
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-top"><div class="pi-rebalance-asset">{html.escape(ui_label("Latest refresh"))}</div><span class="pi-badge info">수집 시각</span></div>
                        <div class="pi-rebalance-amount" style="text-align:left; margin-top:6px;">{html.escape(state.latest_refresh_time or 'N/A')}</div>
                        <div class="pi-rebalance-impact">{html.escape(ko_sentence("All rows include source, endpoint, as_of_date, available_at, fetched_at, confidence, stale, and missing flags."))}</div>
                    </div>
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-asset">{html.escape(ui_label("API key warnings"))}</div>
                        <div class="pi-rebalance-reason">{html.escape(key_text)}</div>
                        <div class="pi-rebalance-impact">{html.escape(ko_sentence("Only key names are shown. Secret values are never rendered."))}</div>
                    </div>
                </div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Data Gaps"))}</strong><span>{html.escape(ui_label("stale / missing"))}</span></div>
                <div class="pi-card-body">
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-top"><div class="pi-rebalance-asset">{html.escape(ui_label("Stale warnings"))}</div><span class="pi-badge warn">{html.escape(str(len(state.stale_sources)))}</span></div>
                        <div class="pi-rebalance-reason">{html.escape(stale_text)}</div>
                    </div>
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-top"><div class="pi-rebalance-asset">{html.escape(ui_label("Missing modules"))}</div><span class="pi-badge risk">{html.escape(str(len(state.missing_sources)))}</span></div>
                        <div class="pi-rebalance-reason">{html.escape(missing_text)}</div>
                    </div>
                </div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Point-in-Time Gate"))}</strong><span>{html.escape(ui_label("anti look-ahead"))}</span></div>
                <div class="pi-card-body">
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-top"><div class="pi-rebalance-asset">{html.escape(ui_label("Compliance status"))}</div><span class="pi-badge {pit_tone}">{html.escape(status_label(state.point_in_time_status))}</span></div>
                        <div class="pi-rebalance-reason">{html.escape(ko_sentence("DART and macro data must use receipt_date, available_at, or fetched_at before analytics consume them."))}</div>
                        <div class="pi-rebalance-impact">{html.escape(ko_sentence("This is a metadata review gate, not a trading signal."))}</div>
                    </div>
                </div>
            </div>
        </div>
        <div class="pi-card" style="margin-top:14px;">
            <div class="pi-card-header"><strong>{html.escape(ui_label("Source Coverage Table"))}</strong><span>/api/dashboard/data-trust</span></div>
            <div class="pi-card-body">{_coverage_rows(state.source_coverage)}</div>
        </div>
    </section>
    """


def _macro_signal_tone(signal: str) -> str:
    return {
        "tailwind": "good",
        "neutral": "info",
        "headwind": "warn",
        "missing": "risk",
    }.get(signal, "info")


def _macro_value(row: MacroIndicatorRow) -> str:
    if row.value is None:
        return "N/A"
    if row.unit in {"%", "% YoY", "1D %"}:
        return f"{row.value:.2f}{row.unit.replace('%', '%') if row.unit == '%' else ' ' + row.unit}"
    if row.unit == "KRW per USD":
        return f"{row.value:,.2f}"
    return f"{row.value:,.2f} {row.unit}"


def _macro_heatmap_rows(rows: tuple[MacroIndicatorRow, ...]) -> str:
    if not rows:
        return f'<div class="pi-rebalance-reason">{html.escape(ko_sentence("No macro indicators available."))}</div>'
    rendered = []
    for row in rows:
        width = max(3, min(100, row.score))
        tone = _macro_signal_tone(row.signal)
        rendered.append(
            f"""
            <div class="pi-allocation-row">
                <div class="pi-asset-label">{html.escape(row.label)}<br/><small>{html.escape(row.meta.source)}</small></div>
                <div class="pi-allocation-track"><div class="pi-allocation-fill" style="width:{width:.1f}%;"></div></div>
                <div class="pi-allocation-value"><span class="pi-badge {tone}">{html.escape(signal_label(row.signal))}</span><br/><small>{html.escape(_macro_value(row))}</small></div>
            </div>
            """
        )
    return "".join(rendered)


def _sector_tailwind_rows(rows: tuple[SectorTailwindRow, ...]) -> str:
    if not rows:
        return f'<div class="pi-rebalance-reason">{html.escape(ko_sentence("No sector tailwind data available."))}</div>'
    rendered = []
    for row in rows[:6]:
        positives = ", ".join(ko_sentence(item) for item in row.positive_drivers) if row.positive_drivers else "없음"
        negatives = ", ".join(ko_sentence(item) for item in row.negative_drivers) if row.negative_drivers else "없음"
        rendered.append(
            f"""
            <div class="pi-signal-row" style="grid-template-columns:minmax(130px,1fr) 76px minmax(160px,1.2fr);">
                <div><strong>{html.escape(row.sector)}</strong><br/><span>+ {html.escape(positives)} / - {html.escape(negatives)}</span></div>
                <div>{html.escape(str(row.tailwind_score))}/100</div>
                <div><span class="pi-badge {_macro_signal_tone(row.label)}">{html.escape(signal_label(row.label))}</span></div>
            </div>
            """
        )
    return "".join(rendered)


def _recent_change_rows(rows: tuple[RecentMacroChange, ...]) -> str:
    if not rows:
        return """
        <div class="pi-rebalance-item">
            <div class="pi-rebalance-asset">최근 매크로 변화 없음</div>
            <div class="pi-rebalance-reason">최근 변화로 표시할 만큼 크게 움직인 지표가 없습니다.</div>
        </div>
        """
    rendered = []
    tone_map = {"positive": "good", "neutral": "info", "negative": "warn"}
    for row in rows[:5]:
        rendered.append(
            f"""
            <div class="pi-rebalance-item">
                <div class="pi-rebalance-top">
                    <div class="pi-rebalance-asset">{html.escape(row.label)}</div>
                    <span class="pi-badge {tone_map.get(row.impact, 'info')}">{html.escape(severity_label(row.impact))}</span>
                </div>
                <div class="pi-rebalance-reason">{html.escape(ko_sentence(row.change_text))}</div>
                <div class="pi-rebalance-impact">{html.escape(source_meta_line(row.meta))}</div>
            </div>
            """
        )
    return "".join(rendered)


def market_regime_macro_radar_html(state: MarketRegimeMacroRadarState) -> str:
    if state.status == "loading":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">{html.escape(status_label("loading"))}</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Market regime data is being prepared."))}</div></div>'
    elif state.status == "error":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">{html.escape(status_label("error"))}</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Market regime calculation failed."))}</div></div>'
    elif state.status == "empty":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">매크로 데이터 없음</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Connect market or macro sources to calculate the regime radar."))}</div></div>'
    else:
        label_badges = "".join(f'<span class="pi-badge info">{html.escape(label)}</span>' for label in state.regime_labels)
        body = f"""
        <div class="portfolio-intelligence-grid">
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Regime Score"))}</strong><span>{html.escape(ui_label("risk-on / risk-off"))}</span></div>
                <div class="pi-card-body">
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-top"><div class="pi-rebalance-asset">{html.escape(state.current_regime_label)}</div><span class="pi-badge {_coverage_tone(state.status)}">{html.escape(status_label(state.status))}</span></div>
                        <div class="pi-rebalance-amount" style="text-align:left; margin-top:6px;">{state.regime_score}/100</div>
                        <div class="pi-rebalance-impact">최근 출처 시각 {html.escape(state.latest_source_at or 'N/A')}</div>
                    </div>
                    <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:10px;">{label_badges}</div>
                </div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Macro Heatmap"))}</strong><span>{html.escape(ui_label("tailwinds / headwinds"))}</span></div>
                <div class="pi-card-body">{_macro_heatmap_rows(state.macro_heatmap)}</div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Recent Changes"))}</strong><span>{html.escape(ui_label("what moved"))}</span></div>
                <div class="pi-card-body"><div class="pi-rebalance-list">{_recent_change_rows(state.recent_changes)}</div></div>
            </div>
        </div>
        <div class="pi-card" style="margin-top:14px;">
            <div class="pi-card-header"><strong>{html.escape(ui_label("Sector Tailwind Table"))}</strong><span>{html.escape(ui_label("context only, no stock recommendation"))}</span></div>
            <div class="pi-card-body">{_sector_tailwind_rows(state.sector_tailwinds)}</div>
        </div>
        """
    return f"""
    <section class="portfolio-intelligence-shell" aria-label="MarketRegimeMacroRadar" data-module-id="MarketRegimeMacroRadar">
        <div class="portfolio-intelligence-title">
            <div>
                <strong>{html.escape(module_title("Market Regime & Macro Radar"))}</strong>
                <span>{html.escape(ko_sentence(state.summary))}</span>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                {_badge(state.status)}
                <span class="pi-badge info">{html.escape(ui_label("Context only"))}</span>
            </div>
        </div>
        {body}
    </section>
    """


def _fx_signal_tone(signal: str) -> str:
    return {
        "supportive": "good",
        "neutral": "info",
        "pressure": "warn",
        "missing": "risk",
    }.get(signal, "info")


def _fx_value(row: FXRatesIndicatorRow) -> str:
    if row.value is None:
        return "N/A"
    if row.unit == "%":
        return f"{row.value:.2f}%"
    if row.unit.startswith("KRW per"):
        return f"{row.value:,.2f}"
    return f"{row.value:,.2f} {row.unit}"


def _fx_change(row: FXRatesIndicatorRow) -> str:
    if row.change is None:
        return "N/A"
    suffix = "%p" if row.unit == "%" else "%"
    return f"{row.change:+.2f}{suffix}"


def _fx_indicator_rows(rows: tuple[FXRatesIndicatorRow, ...]) -> str:
    if not rows:
        return f'<div class="pi-rebalance-reason">{html.escape(ko_sentence("No FX/rates indicators available."))}</div>'
    rendered = []
    for row in rows:
        width = max(3, min(100, row.pressure_score))
        tone = _fx_signal_tone(row.signal)
        stale = " · 오래된 데이터" if row.meta.stale_data_flag else ""
        rendered.append(
            f"""
            <div class="pi-allocation-row">
                <div class="pi-asset-label">{html.escape(row.label)}<br/><small>{html.escape(row.meta.source)}{html.escape(stale)}</small></div>
                <div class="pi-allocation-track"><div class="pi-allocation-fill" style="width:{width:.1f}%;"></div></div>
                <div class="pi-allocation-value"><span class="pi-badge {tone}">{html.escape(signal_label(row.signal))}</span><br/><small>{html.escape(_fx_value(row))} / {html.escape(_fx_change(row))}</small></div>
            </div>
            """
        )
    return "".join(rendered)


def _fx_impact_rows(rows: tuple[FXRatesImpactRow, ...]) -> str:
    if not rows:
        return f'<div class="pi-rebalance-reason">{html.escape(ko_sentence("No interpretation rows available."))}</div>'
    rendered = []
    for row in rows:
        tone = "warn" if row.impact_score >= 60 else "good" if row.impact_score <= 35 else "info"
        rendered.append(
            f"""
            <div class="pi-rebalance-item">
                <div class="pi-rebalance-top">
                    <div class="pi-rebalance-asset">{html.escape(row.channel)}</div>
                    <span class="pi-badge {tone}">{row.impact_score}/100</span>
                </div>
                <div class="pi-rebalance-reason">우호: {html.escape(row.favored)} · 부담: {html.escape(row.pressured)}</div>
                <div class="pi-rebalance-impact">{html.escape(ko_sentence(row.interpretation))}</div>
            </div>
            """
        )
    return "".join(rendered)


def krw_rates_fx_dashboard_html(state: KRWRatesFXDashboardState) -> str:
    if state.status == "loading":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">{html.escape(status_label("loading"))}</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("KRW/rates/FX data is being prepared."))}</div></div>'
    elif state.status == "error":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">{html.escape(status_label("error"))}</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("KRW/rates/FX calculation failed."))}</div></div>'
    elif state.status == "empty":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">환율·금리 데이터 없음</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Connect FX or rates sources to calculate this dashboard."))}</div></div>'
    else:
        curve_text = "N/A" if state.yield_curve_slope is None else f"{state.yield_curve_slope:+.2f}%p"
        impact_text = "N/A" if state.portfolio_krw_impact_pct is None else f"{state.portfolio_krw_impact_pct * 100:+.2f}%"
        body = f"""
        <div class="portfolio-intelligence-grid">
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Shock Indicators"))}</strong><span>{html.escape(ui_label("FX / rates"))}</span></div>
                <div class="pi-card-body">
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-top"><div class="pi-rebalance-asset">{html.escape(ko_sentence(state.fx_shock_label))}</div><span class="pi-badge {_coverage_tone(state.status)}">{html.escape(status_label(state.status))}</span></div>
                        <div class="pi-rebalance-amount" style="text-align:left; margin-top:6px;">FX {state.fx_shock_score}/100</div>
                        <div class="pi-rebalance-impact">{html.escape(ko_sentence("USD/KRW pressure and one-day move."))}</div>
                    </div>
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-top"><div class="pi-rebalance-asset">{html.escape(ko_sentence(state.rate_shock_label))}</div><span class="pi-badge info">커브 {html.escape(curve_text)}</span></div>
                        <div class="pi-rebalance-amount" style="text-align:left; margin-top:6px;">금리 {state.rate_shock_score}/100</div>
                        <div class="pi-rebalance-impact">{html.escape(ko_sentence("Korea and U.S. rate pressure for equity valuations."))}</div>
                    </div>
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-asset">{html.escape(ui_label("Portfolio KRW impact"))}</div>
                        <div class="pi-rebalance-reason">{html.escape(impact_text)}</div>
                        <div class="pi-rebalance-impact">{html.escape(ko_sentence("Estimated only when non-KRW holdings exist."))}</div>
                    </div>
                </div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("FX & Rates Board"))}</strong><span>{html.escape(ui_label("source-aware indicators"))}</span></div>
                <div class="pi-card-body">{_fx_indicator_rows(state.indicators)}</div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Portfolio & Sector Impact"))}</strong><span>{html.escape(ui_label("interpretation"))}</span></div>
                <div class="pi-card-body"><div class="pi-rebalance-list">{_fx_impact_rows(state.impact_rows)}</div></div>
            </div>
        </div>
        """
    return f"""
    <section class="portfolio-intelligence-shell" aria-label="KRWRatesFXDashboard" data-module-id="KRWRatesFXDashboard">
        <div class="portfolio-intelligence-title">
            <div>
                <strong>{html.escape(module_title("KRW / Rates / FX Dashboard"))}</strong>
                <span>{html.escape(ko_sentence(state.summary))}</span>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                {_badge(state.status)}
                <span class="pi-badge info">{html.escape(ui_label("Context only"))}</span>
            </div>
        </div>
        {body}
    </section>
    """


def _valuation_tone(label: str) -> str:
    return {
        "cheap": "good",
        "fair": "info",
        "expensive": "warn",
        "mixed": "info",
        "missing": "risk",
    }.get(label, "info")


def _multiple(value: float | None, suffix: str = "x") -> str:
    return "N/A" if value is None else f"{value:.2f}{suffix}"


def _yield_text(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:.1f}%"


def _percentile_text(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1f}/100"


def _valuation_candidate_rows(rows: tuple[ValuationMetricRow, ...], empty_label: str) -> str:
    if not rows:
        return f"""
        <div class="pi-rebalance-item">
            <div class="pi-rebalance-asset">{html.escape(ko_sentence(empty_label))}</div>
            <div class="pi-rebalance-reason">{html.escape(ko_sentence("No row satisfies the current valuation and quality filter."))}</div>
        </div>
        """
    rendered = []
    for row in rows[:5]:
        rendered.append(
            f"""
            <div class="pi-signal-row" style="grid-template-columns:minmax(130px,1fr) 70px 70px minmax(110px,1fr);">
                <div><strong>{html.escape(row.name)}</strong><br/><span>{html.escape(row.code)} | {html.escape(row.sector)}</span></div>
                <div>PER<br/><strong>{html.escape(_multiple(row.per))}</strong></div>
                <div>PBR<br/><strong>{html.escape(_multiple(row.pbr))}</strong></div>
                <div><span class="pi-badge {_valuation_tone(row.valuation_label)}">{html.escape(row.interpretation)}</span><br/><small>{html.escape(_percentile_text(row.historical_percentile))}</small></div>
            </div>
            """
        )
    return "".join(rendered)


def _sector_valuation_rows(rows: tuple[SectorValuationRow, ...]) -> str:
    if not rows:
        return f'<div class="pi-rebalance-reason">{html.escape(ko_sentence("No sector valuation data available."))}</div>'
    rendered = []
    for row in rows[:7]:
        width = 50 if row.median_percentile is None else max(3, min(100, row.median_percentile))
        rendered.append(
            f"""
            <div class="pi-allocation-row">
                <div class="pi-asset-label">{html.escape(row.sector)}<br/><small>저평가 {row.cheap_count} / 고평가 {row.expensive_count}</small></div>
                <div class="pi-allocation-track"><div class="pi-allocation-fill" style="width:{width:.1f}%;"></div></div>
                <div class="pi-allocation-value"><span class="pi-badge {_valuation_tone(row.signal)}">{html.escape(signal_label(row.signal))}</span><br/><small>PER {html.escape(_multiple(row.average_per))}</small></div>
            </div>
            """
        )
    return "".join(rendered)


def _valuation_percentile_rows(rows: tuple[ValuationMetricRow, ...]) -> str:
    if not rows:
        return f'<div class="pi-rebalance-reason">{html.escape(ko_sentence("No valuation percentile rows available."))}</div>'
    rendered = []
    for row in rows[:8]:
        pbr_flag = "PBR<1" if row.pbr_below_1 else "PBR>=1"
        rendered.append(
            f"""
            <div class="pi-signal-row" style="grid-template-columns:minmax(130px,1fr) 74px 74px 76px;">
                <div><strong>{html.escape(row.name)}</strong><br/><span>{html.escape(row.code)} | {html.escape(row.interpretation)}</span></div>
                <div>{html.escape(_percentile_text(row.historical_percentile))}</div>
                <div>{html.escape('N/A' if row.sector_relative_per is None else f'{row.sector_relative_per:.2f}x')}</div>
                <div><span class="pi-badge {'good' if row.pbr_below_1 else 'info'}">{html.escape(pbr_flag)}</span></div>
            </div>
            """
        )
    return "".join(rendered)


def valuation_relative_cheapness_panel_html(state: ValuationRelativeCheapnessPanelState) -> str:
    if state.status == "loading":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">{html.escape(status_label("loading"))}</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Valuation data is being prepared."))}</div></div>'
    elif state.status == "error":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">{html.escape(status_label("error"))}</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Valuation calculation failed."))}</div></div>'
    elif state.status == "empty":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">밸류에이션 데이터 없음</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Connect KRX/OpenDART valuation sources to calculate this panel."))}</div></div>'
    else:
        market_text = _percentile_text(state.market_percentile)
        body = f"""
        <div class="portfolio-intelligence-grid">
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Market Valuation Summary"))}</strong><span>{html.escape(ui_label("relative cheapness"))}</span></div>
                <div class="pi-card-body">
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-top"><div class="pi-rebalance-asset">{html.escape(ui_label("Market percentile"))}</div><span class="pi-badge {_coverage_tone(state.status)}">{html.escape(status_label(state.status))}</span></div>
                        <div class="pi-rebalance-amount" style="text-align:left; margin-top:6px;">{html.escape(market_text)}</div>
                        <div class="pi-rebalance-impact">{html.escape(ko_sentence("Lower percentile means cheaper versus history."))}</div>
                    </div>
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-asset">{html.escape(ui_label("Cheap / expensive count"))}</div>
                        <div class="pi-rebalance-reason">저평가 {state.cheap_count} · 고평가 {state.expensive_count}</div>
                        <div class="pi-rebalance-impact">{html.escape(ko_sentence("No buy/sell recommendation is generated."))}</div>
                    </div>
                </div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Cheapest Quality Candidates"))}</strong><span>{html.escape(ui_label("placeholder for future alpha ranking"))}</span></div>
                <div class="pi-card-body">{_valuation_candidate_rows(state.cheapest_quality_candidates, "저평가 고품질 후보 없음")}</div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Expensive / Overheated List"))}</strong><span>{html.escape(ui_label("review risk"))}</span></div>
                <div class="pi-card-body">{_valuation_candidate_rows(state.expensive_list, "고평가·과열 행 없음")}</div>
            </div>
        </div>
        <div class="pi-detail-grid">
            <div class="pi-card pi-risk-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Sector Valuation Heatmap"))}</strong><span>{html.escape(ui_label("sector-relative"))}</span></div>
                <div class="pi-card-body">{_sector_valuation_rows(state.sector_heatmap)}</div>
            </div>
            <div class="pi-card pi-insight-card" style="grid-column: span 7;">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Valuation Percentile Table"))}</strong><span>{html.escape(ui_label("PER / PBR / history"))}</span></div>
                <div class="pi-card-body">{_valuation_percentile_rows(state.percentile_table)}</div>
            </div>
        </div>
        """
    return f"""
    <section class="portfolio-intelligence-shell" aria-label="ValuationRelativeCheapnessPanel" data-module-id="ValuationRelativeCheapnessPanel">
        <div class="portfolio-intelligence-title">
            <div>
                <strong>{html.escape(module_title("Valuation & Relative Cheapness Panel"))}</strong>
                <span>{html.escape(ko_sentence(state.summary))}</span>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                {_badge(state.status)}
                <span class="pi-badge info">{html.escape(ui_label("No recommendation"))}</span>
            </div>
        </div>
        {body}
    </section>
    """


def _quality_tone(label: str) -> str:
    return {
        "top_quality": "good",
        "improving": "good",
        "watch": "info",
        "deteriorating": "warn",
        "missing": "risk",
    }.get(label, "info")


def _ratio_text(value: float | None, digits: int = 1) -> str:
    return "N/A" if value is None else f"{value:.{digits}f}x"


def _quality_percent(value: float | None, digits: int = 1) -> str:
    return "N/A" if value is None else f"{value * 100:.{digits}f}%"


def _quality_rows(rows: tuple[FundamentalQualityRow, ...], empty_label: str) -> str:
    if not rows:
        return f"""
        <div class="pi-rebalance-item">
            <div class="pi-rebalance-asset">{html.escape(ko_sentence(empty_label))}</div>
            <div class="pi-rebalance-reason">{html.escape(ko_sentence("No company meets this quality bucket."))}</div>
        </div>
        """
    rendered = []
    for row in rows[:5]:
        flags = ", ".join(ko_sentence(flag) for flag in row.accounting_flags[:2]) if row.accounting_flags else "중요 플래그 없음"
        rendered.append(
            f"""
            <div class="pi-signal-row" style="grid-template-columns:minmax(130px,1fr) 72px 72px minmax(120px,1fr);">
                <div><strong>{html.escape(row.name)}</strong><br/><span>{html.escape(row.code)} | {html.escape(row.sector)}</span></div>
                <div>Q<br/><strong>{row.quality_score}</strong></div>
                <div>ROIC<br/><strong>{html.escape(_quality_percent(row.roic))}</strong></div>
                <div><span class="pi-badge {_quality_tone(row.quality_label)}">{html.escape(signal_label(row.quality_label))}</span><br/><small>{html.escape(flags)}</small></div>
            </div>
            """
        )
    return "".join(rendered)


def _fcf_rows(rows: tuple[FundamentalQualityRow, ...]) -> str:
    if not rows:
        return f'<div class="pi-rebalance-reason">{html.escape(ko_sentence("No FCF conversion data available."))}</div>'
    rendered = []
    for row in rows[:5]:
        rendered.append(
            f"""
            <div class="pi-allocation-row">
                <div class="pi-asset-label">{html.escape(row.name)}<br/><small>{html.escape(row.code)}</small></div>
                <div class="pi-allocation-track"><div class="pi-allocation-fill" style="width:{max(3, min(100, (row.fcf_conversion or 0) * 80)):.1f}%;"></div></div>
                <div class="pi-allocation-value">{html.escape(_quality_percent(row.fcf_conversion))}<br/><small>CFO/NI {html.escape(_ratio_text(row.cfo_to_net_income))}</small></div>
            </div>
            """
        )
    return "".join(rendered)


def _roic_valuation_rows(rows: tuple[Any, ...]) -> str:
    if not rows:
        return f'<div class="pi-rebalance-reason">{html.escape(ko_sentence("No ROIC versus valuation points available."))}</div>'
    clean = sorted(rows, key=lambda row: row.quality_score, reverse=True)
    rendered = []
    for row in clean[:6]:
        percentile = "N/A" if row.valuation_percentile is None else f"{row.valuation_percentile:.1f}/100"
        rendered.append(
            f"""
            <div class="pi-signal-row" style="grid-template-columns:minmax(130px,1fr) 72px 82px 72px;">
                <div><strong>{html.escape(row.name)}</strong><br/><span>{html.escape(row.sector)}</span></div>
                <div>ROIC<br/><strong>{html.escape(_quality_percent(row.roic))}</strong></div>
                <div>밸류<br/><strong>{html.escape(percentile)}</strong></div>
                <div>Q<br/><strong>{row.quality_score}</strong></div>
            </div>
            """
        )
    return "".join(rendered)


def fundamental_quality_panel_html(state: FundamentalQualityPanelState) -> str:
    if state.status == "loading":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">{html.escape(status_label("loading"))}</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Fundamental quality data is being prepared."))}</div></div>'
    elif state.status == "error":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">{html.escape(status_label("error"))}</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Fundamental quality calculation failed."))}</div></div>'
    elif state.status == "empty":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">재무제표 데이터 없음</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Connect OpenDART financial statements with available_at timestamps."))}</div></div>'
    else:
        avg_score = next((point.display_value for point in state.data_points if point.key == "average_quality_score"), "N/A")
        body = f"""
        <div class="portfolio-intelligence-grid">
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Quality Score"))}</strong><span>{html.escape(ui_label("durability composite"))}</span></div>
                <div class="pi-card-body">
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-top"><div class="pi-rebalance-asset">{html.escape(ui_label("Average quality"))}</div><span class="pi-badge {_coverage_tone(state.status)}">{html.escape(status_label(state.status))}</span></div>
                        <div class="pi-rebalance-amount" style="text-align:left; margin-top:6px;">{html.escape(str(avg_score))}</div>
                        <div class="pi-rebalance-impact">{html.escape(ko_sentence("Profitability, cash-flow quality, balance sheet, growth, and accounting risk."))}</div>
                    </div>
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-asset">{html.escape(ui_label("Point-in-time rule"))}</div>
                        <div class="pi-rebalance-reason">{html.escape(ko_sentence("Uses available_at / receipt_date only."))}</div>
                        <div class="pi-rebalance-impact">{html.escape(ko_sentence("Fiscal period end date is not treated as data availability."))}</div>
                    </div>
                </div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Top Quality Stocks"))}</strong><span>{html.escape(ui_label("durability"))}</span></div>
                <div class="pi-card-body">{_quality_rows(state.top_quality_stocks, "품질 상위 종목 없음")}</div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Deteriorating Quality"))}</strong><span>{html.escape(ui_label("review risk"))}</span></div>
                <div class="pi-card-body">{_quality_rows(state.deteriorating_quality_stocks, "품질 악화 종목 없음")}</div>
            </div>
        </div>
        <div class="pi-detail-grid">
            <div class="pi-card pi-risk-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Cheap Quality Stocks"))}</strong><span>{html.escape(ui_label("quality + valuation context"))}</span></div>
                <div class="pi-card-body">{_quality_rows(state.cheap_quality_stocks, "저평가 고품질 종목 없음")}</div>
            </div>
            <div class="pi-card pi-insight-card" style="grid-column: span 7;">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Accounting Red Flags"))}</strong><span>{html.escape(ui_label("accrual / cash flow / leverage"))}</span></div>
                <div class="pi-card-body">{_quality_rows(state.accounting_red_flags, "회계 위험 신호 없음")}</div>
            </div>
        </div>
        <div class="pi-detail-grid">
            <div class="pi-card pi-risk-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("FCF Conversion Ranking"))}</strong><span>{html.escape(ui_label("cash conversion"))}</span></div>
                <div class="pi-card-body">{_fcf_rows(state.fcf_conversion_ranking)}</div>
            </div>
            <div class="pi-card pi-insight-card" style="grid-column: span 7;">
                <div class="pi-card-header"><strong>{html.escape(ui_label("ROIC Versus Valuation"))}</strong><span>{html.escape(ui_label("chart-style table"))}</span></div>
                <div class="pi-card-body">{_roic_valuation_rows(state.roic_vs_valuation)}</div>
            </div>
        </div>
        """
    return f"""
    <section class="portfolio-intelligence-shell" aria-label="FundamentalQualityPanel" data-module-id="FundamentalQualityPanel">
        <div class="portfolio-intelligence-title">
            <div>
                <strong>{html.escape(module_title("Fundamental Quality Panel"))}</strong>
                <span>{html.escape(ko_sentence(state.summary))}</span>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                {_badge(state.status)}
                <span class="pi-badge info">{html.escape(ui_label("No recommendation"))}</span>
            </div>
        </div>
        {body}
    </section>
    """


def _dart_tone(row: DARTDisclosureEventRow) -> str:
    if row.sentiment == "positive":
        return "market-up"
    if row.governance_risk_score >= 70 or row.dilution_risk_score >= 60 or row.materiality_score >= 85:
        return "risk-critical"
    if row.sentiment == "negative":
        return "warn"
    return "info"


def _dart_category_label(category: str) -> str:
    return dart_category_label(category)


def _dart_rows(rows: tuple[DARTDisclosureEventRow, ...], empty_label: str, *, score_mode: str = "materiality") -> str:
    if not rows:
        return f"""
        <div class="pi-rebalance-item">
            <div class="pi-rebalance-asset">{html.escape(ko_sentence(empty_label))}</div>
            <div class="pi-rebalance-reason">{html.escape(ko_sentence("No matching DART disclosure event is available."))}</div>
        </div>
        """
    rendered = []
    for row in rows[:6]:
        if score_mode == "dilution":
            score_label = "희석"
            score = row.dilution_risk_score
        elif score_mode == "governance":
            score_label = "지배구조"
            score = row.governance_risk_score
        elif score_mode == "catalyst":
            score_label = "촉매"
            score = row.catalyst_score
        else:
            score_label = "중요도"
            score = row.materiality_score
        ref = ""
        if row.meta.source_url:
            ref = f'<br/><a href="{html.escape(row.meta.source_url)}" target="_blank" rel="noopener noreferrer">{html.escape(ui_label("Source filing"))}</a>'
        rendered.append(
            f"""
            <div class="pi-signal-row" style="grid-template-columns:minmax(170px,1fr) 82px 92px minmax(150px,1fr);">
                <div><strong>{html.escape(row.name)}</strong><br/><span>{html.escape(row.code)} | {html.escape(row.receipt_date or "N/A")}</span></div>
                <div>{html.escape(score_label)}<br/><strong>{score}</strong></div>
                <div><span class="pi-badge {_dart_tone(row)}">{html.escape(severity_label(row.sentiment))}</span><br/><small>{html.escape(_dart_category_label(row.category))}</small></div>
                <div><strong>{html.escape(row.title)}</strong><br/><small>{html.escape(row.event_summary)}</small>{ref}</div>
            </div>
            """
        )
    return "".join(rendered)


def _dart_timeline(rows: tuple[DARTDisclosureEventRow, ...]) -> str:
    if not rows:
        return f'<div class="pi-rebalance-reason">{html.escape(ko_sentence("No event timeline available."))}</div>'
    rendered = []
    for row in rows[:8]:
        risk_score = max(row.dilution_risk_score, row.governance_risk_score)
        width = max(4, min(100, row.materiality_score))
        color = (
            getChartSeriesColor("critical", context="risk")
            if risk_score >= 60
            else getChartSeriesColor("up")
            if row.sentiment == "positive"
            else getChartSeriesColor("warning", context="risk")
        )
        rendered.append(
            f"""
            <div class="pi-allocation-row">
                <div class="pi-asset-label">{html.escape(row.receipt_date or "N/A")}<br/><small>{html.escape(row.name)}</small></div>
                <div class="pi-allocation-track"><div class="pi-allocation-fill" style="width:{width:.1f}%; background:{color};"></div></div>
                <div class="pi-allocation-value">{row.materiality_score}<br/><small>{html.escape(_dart_category_label(row.category))}</small></div>
            </div>
            """
        )
    return "".join(rendered)


def dart_disclosure_catalyst_panel_html(state: DARTDisclosureCatalystPanelState) -> str:
    if state.status == "loading":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">{html.escape(status_label("loading"))}</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("DART catalyst events are being prepared."))}</div></div>'
    elif state.status == "error":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">{html.escape(status_label("error"))}</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("DART catalyst calculation failed."))}</div></div>'
    elif state.status == "empty":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">DART 공시 이벤트 없음</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Connect OpenDART list/detail events with receipt_date or available_at timestamps."))}</div></div>'
    else:
        disclosure_count = next((point.display_value for point in state.data_points if point.key == "disclosure_count"), "0")
        high_count = next((point.display_value for point in state.data_points if point.key == "high_materiality_count"), "0")
        body = f"""
        <div class="portfolio-intelligence-grid">
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Catalyst Overview"))}</strong><span>{html.escape(ui_label("point-in-time DART"))}</span></div>
                <div class="pi-card-body">
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-top"><div class="pi-rebalance-asset">{html.escape(ui_label("Tracked disclosures"))}</div><span class="pi-badge {_coverage_tone(state.status)}">{html.escape(status_label(state.status))}</span></div>
                        <div class="pi-rebalance-amount" style="text-align:left; margin-top:6px;">{html.escape(str(disclosure_count))}</div>
                        <div class="pi-rebalance-impact">고중요도 이벤트: {html.escape(str(high_count))}</div>
                    </div>
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-asset">{html.escape(ui_label("Point-in-time rule"))}</div>
                        <div class="pi-rebalance-reason">{html.escape(ko_sentence("Uses available_at / receipt_date only."))}</div>
                        <div class="pi-rebalance-impact">{html.escape(ko_sentence("Future filings are excluded from catalyst features."))}</div>
                    </div>
                </div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Latest High-Materiality"))}</strong><span>{html.escape(ui_label("materiality score"))}</span></div>
                <div class="pi-card-body">{_dart_rows(state.latest_high_materiality_disclosures, "고중요도 공시 없음")}</div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Positive Catalysts"))}</strong><span>{html.escape(ui_label("shareholder return / growth"))}</span></div>
                <div class="pi-card-body">{_dart_rows(state.positive_catalysts, "긍정 촉매 없음", score_mode="catalyst")}</div>
            </div>
        </div>
        <div class="pi-detail-grid">
            <div class="pi-card pi-risk-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Negative Risk List"))}</strong><span>{html.escape(ui_label("review risk"))}</span></div>
                <div class="pi-card-body">{_dart_rows(state.negative_risks, "부정 리스크 공시 없음", score_mode="governance")}</div>
            </div>
            <div class="pi-card pi-insight-card" style="grid-column: span 7;">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Dilution Watchlist"))}</strong><span>{html.escape(ui_label("capital increase / CB / BW / EB"))}</span></div>
                <div class="pi-card-body">{_dart_rows(state.dilution_watchlist, "희석 위험 관찰 항목 없음", score_mode="dilution")}</div>
            </div>
        </div>
        <div class="pi-detail-grid">
            <div class="pi-card pi-risk-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Shareholder Return"))}</strong><span>{html.escape(ui_label("buyback / cancellation / dividend / value-up"))}</span></div>
                <div class="pi-card-body">{_dart_rows(state.shareholder_return_announcements, "주주환원 공시 없음", score_mode="catalyst")}</div>
            </div>
            <div class="pi-card pi-insight-card" style="grid-column: span 7;">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Event Timeline"))}</strong><span>{html.escape(ui_label("recent receipts"))}</span></div>
                <div class="pi-card-body">{_dart_timeline(state.event_timeline)}</div>
            </div>
        </div>
        """
    return f"""
    <section class="portfolio-intelligence-shell" aria-label="DARTDisclosureCatalystPanel" data-module-id="DARTDisclosureCatalystPanel">
        <div class="portfolio-intelligence-title">
            <div>
                <strong>{html.escape(module_title("DART Disclosure Catalyst Panel"))}</strong>
                <span>{html.escape(ko_sentence(state.summary))}</span>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                {_badge(state.status)}
                <span class="pi-badge info">{html.escape(ui_label("Review candidates only"))}</span>
            </div>
        </div>
        {body}
    </section>
    """


def _flow_money(value: float | None) -> str:
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    abs_value = abs(value)
    if abs_value >= 1_000_000_000_000:
        return f"{sign}KRW {value / 1_000_000_000_000:.2f}T"
    if abs_value >= 1_000_000_000:
        return f"{sign}KRW {value / 1_000_000_000:.1f}B"
    return f"{sign}KRW {value:,.0f}"


def _flow_z(value: float | None) -> str:
    return "N/A" if value is None else f"{value:+.2f}z"


def _flow_tone(score: int) -> str:
    if score >= 70:
        return "risk"
    if score >= 50:
        return "warn"
    return "good"


def _flow_rows(rows: tuple[SmartMoneyFlowRow, ...], empty_label: str, *, mode: str) -> str:
    if not rows:
        return f"""
        <div class="pi-rebalance-item">
            <div class="pi-rebalance-asset">{html.escape(ko_sentence(empty_label))}</div>
            <div class="pi-rebalance-reason">{html.escape(ko_sentence("No matching flow or short-pressure item is available."))}</div>
        </div>
        """
    rendered = []
    for row in rows[:6]:
        if mode == "foreign":
            label = "외국인 20D"
            value = _flow_money(row.foreign_net_buy_20d)
            badge = f"{row.accumulation_persistence}% 지속"
            score = max(0, min(100, int(round((row.flow_z_score or 0) * 12 + 50))))
        elif mode == "institution":
            label = "기관 20D"
            value = _flow_money(row.institution_net_buy_20d)
            badge = f"{row.accumulation_persistence}% 지속"
            score = max(0, min(100, int(round((row.flow_z_score or 0) * 12 + 50))))
        elif mode == "retail":
            label = "개인 20D"
            value = _flow_money(row.individual_net_buy_20d)
            badge = "쏠림"
            score = row.distribution_risk_score
        elif mode == "squeeze":
            label = "숏스퀴즈"
            value = str(row.short_squeeze_score)
            badge = f"DTC {_ratio_text(row.days_to_cover)}"
            score = row.short_squeeze_score
        elif mode == "fragile":
            label = "취약도"
            value = str(row.fragility_score)
            badge = ko_sentence(row.illiquidity_warning) if row.illiquidity_warning else "리스크 누적"
            score = row.fragility_score
        else:
            label = "매도 압력"
            value = str(row.distribution_risk_score)
            badge = f"flow {_flow_z(row.flow_z_score)}"
            score = row.distribution_risk_score
        if mode in {"foreign", "institution"}:
            tone = "market-up" if score >= 50 else "market-flat"
        elif mode == "squeeze":
            tone = "market-up" if score >= 70 else "info"
        elif mode in {"retail", "fragile"}:
            tone = "risk-critical" if score >= 70 else "warn" if score >= 50 else "info"
        else:
            tone = "market-down" if score >= 50 else "market-flat"
        rendered.append(
            f"""
            <div class="pi-signal-row" style="grid-template-columns:minmax(145px,1fr) 98px 84px minmax(130px,1fr);">
                <div><strong>{html.escape(row.name)}</strong><br/><span>{html.escape(row.code)} | {html.escape(row.sector)}</span></div>
                <div>{html.escape(label)}<br/><strong>{html.escape(value)}</strong></div>
                <div><span class="pi-badge {tone}">{html.escape(str(score))}</span><br/><small>{html.escape(badge)}</small></div>
                <div>공매도 {html.escape(_fmt_pct(row.short_sell_ratio))}<br/><small>수용액 {html.escape(_flow_money(row.capacity_estimate))}</small></div>
            </div>
            """
        )
    return "".join(rendered)


def _sector_flow_rows(rows: tuple[SectorFlowHeatmapRow, ...]) -> str:
    if not rows:
        return f'<div class="pi-rebalance-reason">{html.escape(ko_sentence("No sector flow data available."))}</div>'
    rendered = []
    for row in rows[:8]:
        width = max(4, min(100, row.foreign_flow_score))
        color = (
            getChartSeriesColor("up")
            if row.signal == "accumulation"
            else getChartSeriesColor("critical", context="risk")
            if row.signal == "fragile"
            else getChartSeriesColor("down")
            if row.signal == "distribution"
            else "#8b5cf6"
        )
        rendered.append(
            f"""
            <div class="pi-allocation-row">
                <div class="pi-asset-label">{html.escape(row.sector)}<br/><small>{html.escape(signal_label(row.signal))}</small></div>
                <div class="pi-allocation-track"><div class="pi-allocation-fill" style="width:{width:.1f}%; background:{color};"></div></div>
                <div class="pi-allocation-value">외 {row.foreign_flow_score} / 기 {row.institution_flow_score}<br/><small>공매도 {row.short_pressure_score}</small></div>
            </div>
            """
        )
    return "".join(rendered)


def smart_money_flow_short_pressure_panel_html(state: SmartMoneyFlowShortPressurePanelState) -> str:
    if state.status == "loading":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">{html.escape(status_label("loading"))}</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Investor flow and short-pressure data is being prepared."))}</div></div>'
    elif state.status == "error":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">{html.escape(status_label("error"))}</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Flow and short-pressure calculation failed."))}</div></div>'
    elif state.status == "empty":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">수급·공매도 데이터 없음</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Connect KRX investor flow, short-selling, and liquidity data."))}</div></div>'
    else:
        flow_count = next((point.display_value for point in state.data_points if point.key == "flow_row_count"), "0")
        squeeze_count = next((point.display_value for point in state.data_points if point.key == "short_squeeze_candidate_count"), "0")
        fragile_count = next((point.display_value for point in state.data_points if point.key == "fragile_long_candidate_count"), "0")
        body = f"""
        <div class="portfolio-intelligence-grid">
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Flow / Short Overview"))}</strong><span>{html.escape(ui_label("KRX microstructure"))}</span></div>
                <div class="pi-card-body">
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-top"><div class="pi-rebalance-asset">{html.escape(ui_label("Tracked names"))}</div><span class="pi-badge {_coverage_tone(state.status)}">{html.escape(status_label(state.status))}</span></div>
                        <div class="pi-rebalance-amount" style="text-align:left; margin-top:6px;">{html.escape(str(flow_count))}</div>
                        <div class="pi-rebalance-impact">숏스퀴즈 후보 {html.escape(str(squeeze_count))} · 취약 후보 {html.escape(str(fragile_count))}</div>
                    </div>
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-asset">{html.escape(ui_label("Execution safety"))}</div>
                        <div class="pi-rebalance-reason">{html.escape(ko_sentence("No order execution or deterministic trade instruction."))}</div>
                        <div class="pi-rebalance-impact">{html.escape(ko_sentence("Use as features for future alpha ranking and risk review."))}</div>
                    </div>
                </div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Foreign Accumulation"))}</strong><span>{html.escape(ui_label("5D / 20D / 60D flow"))}</span></div>
                <div class="pi-card-body">{_flow_rows(state.foreign_accumulation_leaderboard, "외국인 누적 매수 없음", mode="foreign")}</div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Institution Accumulation"))}</strong><span>{html.escape(ui_label("institution / pension / program"))}</span></div>
                <div class="pi-card-body">{_flow_rows(state.institution_accumulation_leaderboard, "기관 누적 매수 없음", mode="institution")}</div>
            </div>
        </div>
        <div class="pi-detail-grid">
            <div class="pi-card pi-risk-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Retail Crowding"))}</strong><span>{html.escape(ui_label("individual net buy pressure"))}</span></div>
                <div class="pi-card-body">{_flow_rows(state.retail_crowding_list, "개인 쏠림 없음", mode="retail")}</div>
            </div>
            <div class="pi-card pi-insight-card" style="grid-column: span 7;">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Short Squeeze Candidates"))}</strong><span>{html.escape(ui_label("short pressure + positive flow"))}</span></div>
                <div class="pi-card-body">{_flow_rows(state.short_squeeze_candidates, "숏스퀴즈 후보 없음", mode="squeeze")}</div>
            </div>
        </div>
        <div class="pi-detail-grid">
            <div class="pi-card pi-risk-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Fragile Long Candidates"))}</strong><span>{html.escape(ui_label("distribution + short + liquidity"))}</span></div>
                <div class="pi-card-body">{_flow_rows(state.fragile_long_candidates, "취약 롱 후보 없음", mode="fragile")}</div>
            </div>
            <div class="pi-card pi-insight-card" style="grid-column: span 7;">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Distribution Risk List"))}</strong><span>{html.escape(ui_label("foreign/institution sell + retail buy"))}</span></div>
                <div class="pi-card-body">{_flow_rows(state.distribution_risk_list, "매도 압력 위험 없음", mode="distribution")}</div>
            </div>
        </div>
        <div class="pi-detail-grid">
            <div class="pi-card pi-insight-card" style="grid-column: span 12;">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Sector Flow Heatmap"))}</strong><span>{html.escape(ui_label("foreign / institution / retail / short / liquidity"))}</span></div>
                <div class="pi-card-body">{_sector_flow_rows(state.sector_flow_heatmap)}</div>
            </div>
        </div>
        """
    return f"""
    <section class="portfolio-intelligence-shell" aria-label="SmartMoneyFlowShortPressurePanel" data-module-id="SmartMoneyFlowShortPressurePanel">
        <div class="portfolio-intelligence-title">
            <div>
                <strong>{html.escape(module_title("Smart Money Flow & Short Pressure Panel"))}</strong>
                <span>{html.escape(ko_sentence(state.summary))}</span>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                {_badge(state.status)}
                <span class="pi-badge info">{html.escape(ui_label("Feature layer"))}</span>
            </div>
        </div>
        {body}
    </section>
    """


def _alpha_tone(rating: str) -> str:
    tone = getRatingColorClass(rating)
    return "warn" if tone == "risk-warning" else tone


def _alpha_drivers(items: tuple[str, ...], empty_label: str) -> str:
    if not items:
        return html.escape(ko_sentence(empty_label))
    return " / ".join(html.escape(ko_sentence(item)) for item in items[:3])


def _alpha_rows(rows: tuple[ForwardAlphaRankRow, ...], empty_label: str) -> str:
    if not rows:
        return f"""
        <div class="pi-rebalance-item">
            <div class="pi-rebalance-asset">{html.escape(ko_sentence(empty_label))}</div>
            <div class="pi-rebalance-reason">{html.escape(ko_sentence("No matching forward alpha row is available."))}</div>
        </div>
        """
    rendered = []
    for row in rows[:8]:
        risk_line = _alpha_drivers(row.risk_flags, "리스크 플래그 없음")
        positive_line = _alpha_drivers(row.positive_drivers, "긍정 근거 없음")
        negative_line = _alpha_drivers(row.negative_drivers, "부정 근거 없음")
        warning = f"<br/><small>{html.escape(ko_sentence(row.stale_data_warning))}</small>" if row.stale_data_warning else ""
        rendered.append(
            f"""
            <div class="pi-signal-row" style="grid-template-columns:minmax(160px,1fr) 76px 86px minmax(180px,1.2fr) minmax(140px,1fr);">
                <div><strong>{html.escape(row.name)}</strong><br/><span>{html.escape(row.code)} | {html.escape(row.sector)}</span></div>
                <div>알파<br/><strong>{row.final_alpha_score}</strong></div>
                <div>신뢰도<br/><strong>{row.confidence_score}</strong></div>
                <div><span class="pi-badge {_alpha_tone(row.rating)}">{html.escape(rating_label(row.rating))}</span><br/><small>리스크: {risk_line}</small>{warning}</div>
                <div><strong>+</strong> {positive_line}<br/><small><strong>-</strong> {negative_line}</small></div>
            </div>
            """
        )
    return "".join(rendered)


def _alpha_component_rows(rows: tuple[ForwardAlphaRankRow, ...]) -> str:
    if not rows:
        return f'<div class="pi-rebalance-reason">{html.escape(ko_sentence("No component rows available."))}</div>'
    rendered = []
    for row in rows[:6]:
        components = [
            ("밸류", row.valuation_score),
            ("품질", row.quality_score),
            ("촉매", row.catalyst_score),
            ("수급", row.smart_money_score),
            ("매크로", row.macro_score),
            ("유동성", row.liquidity_score),
        ]
        pills = " ".join(
            f'<span class="pi-badge info">{html.escape(label)} {"N/A" if value is None else int(value)}</span>'
            for label, value in components
        )
        rendered.append(
            f"""
            <div class="pi-rebalance-item">
                <div class="pi-rebalance-top"><div class="pi-rebalance-asset">{html.escape(row.name)}</div><span class="pi-badge {_alpha_tone(row.rating)}">{row.final_alpha_score}</span></div>
                <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:8px;">{pills}</div>
                <div class="pi-rebalance-impact">리스크 감점 {row.risk_penalty} · 스냅샷 {html.escape(row.feature_snapshot_id)}</div>
            </div>
            """
        )
    return "".join(rendered)


def forward_alpha_ranking_panel_html(state: ForwardAlphaRankingPanelState) -> str:
    if state.status == "loading":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">{html.escape(status_label("loading"))}</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Forward alpha feature stack is being prepared."))}</div></div>'
    elif state.status == "error":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">{html.escape(status_label("error"))}</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Forward alpha ranking calculation failed."))}</div></div>'
    elif state.status == "empty":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">미래 알파 랭킹 없음</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Connect valuation, quality, DART, flow, macro, liquidity, and freshness features."))}</div></div>'
    else:
        ranked_count = next((point.display_value for point in state.data_points if point.key == "ranked_count"), "0")
        candidate_count = next((point.display_value for point in state.data_points if point.key == "candidate_count"), "0")
        exclusion_count = next((point.display_value for point in state.data_points if point.key == "high_risk_exclusion_count"), "0")
        top_rows = tuple(row for row in state.ranking_rows if row.rating != "HIGH_RISK_EXCLUDE")
        body = f"""
        <div class="portfolio-intelligence-grid">
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("BaselineRuleScore"))}</strong><span>{html.escape(state.score_version)}</span></div>
                <div class="pi-card-body">
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-top"><div class="pi-rebalance-asset">{html.escape(ui_label("Ranked stocks"))}</div><span class="pi-badge {_coverage_tone(state.status)}">{html.escape(status_label(state.status))}</span></div>
                        <div class="pi-rebalance-amount" style="text-align:left; margin-top:6px;">{html.escape(str(ranked_count))}</div>
                        <div class="pi-rebalance-impact">후보 {html.escape(str(candidate_count))} · 고위험 제외 {html.escape(str(exclusion_count))}</div>
                    </div>
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-asset">{html.escape(ui_label("Model discipline"))}</div>
                        <div class="pi-rebalance-reason">{html.escape(ko_sentence("No historical return chasing. No automatic trading."))}</div>
                        <div class="pi-rebalance-impact">스냅샷 {html.escape(str(state.feature_snapshot_id or "N/A"))}</div>
                    </div>
                </div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Top Forward Alpha Rows"))}</strong><span>{html.escape(ui_label("explainable ranking"))}</span></div>
                <div class="pi-card-body">{_alpha_rows(top_rows, "알파 후보 없음")}</div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("High-Risk Exclusions"))}</strong><span>{html.escape(ui_label("override wins over score"))}</span></div>
                <div class="pi-card-body">{_alpha_rows(state.high_risk_exclusions, "고위험 제외 없음")}</div>
            </div>
        </div>
        <div class="pi-detail-grid">
            <div class="pi-card pi-risk-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Watchlist"))}</strong><span>{html.escape(ui_label("needs confirmation"))}</span></div>
                <div class="pi-card-body">{_alpha_rows(state.watchlist, "관심 행 없음")}</div>
            </div>
            <div class="pi-card pi-insight-card" style="grid-column: span 7;">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Feature Components"))}</strong><span>{html.escape(ui_label("score decomposition"))}</span></div>
                <div class="pi-card-body">{_alpha_component_rows(state.ranking_rows)}</div>
            </div>
        </div>
        """
    return f"""
    <section class="portfolio-intelligence-shell" aria-label="ForwardAlphaRankingPanel" data-module-id="ForwardAlphaRankingPanel">
        <div class="portfolio-intelligence-title">
            <div>
                <strong>{html.escape(module_title("Forward Alpha Ranking Panel"))}</strong>
                <span>{html.escape(ko_sentence(state.summary))}</span>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                {_badge(state.status)}
                <span class="pi-badge info">{html.escape(ui_label("No auto trading"))}</span>
            </div>
        </div>
        {body}
    </section>
    """


def _optimizer_action_tone(action: str) -> str:
    tone = getActionColorClass(action)
    if tone == "market-flat":
        return "info"
    if tone == "risk-critical":
        return "risk-critical"
    return tone


def _weight_text(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:.1f}%"


def _optimizer_rows(rows: tuple[OptimizerRecommendationRow, ...], empty_label: str) -> str:
    if not rows:
        return f"""
        <div class="pi-rebalance-item">
            <div class="pi-rebalance-asset">{html.escape(ko_sentence(empty_label))}</div>
            <div class="pi-rebalance-reason">{html.escape(ko_sentence("No optimizer row is available."))}</div>
        </div>
        """
    rendered = []
    for row in rows[:8]:
        width = max(2, min(100, row.target_weight * 100 / max(0.01, 0.07)))
        color = (
            getChartSeriesColor("up")
            if row.action in {"BUY", "ADD"}
            else getChartSeriesColor("down")
            if row.action in {"TRIM", "SELL"}
            else getChartSeriesColor("critical", context="risk")
            if row.action in {"AVOID", "EXCLUDE"}
            else "#8b5cf6"
        )
        reason = " / ".join(ko_sentence(item) for item in row.reasons[:2]) if row.reasons else "리스크 제어 목표"
        rejection = " / ".join(ko_sentence(item) for item in row.rejection_reasons[:2]) if row.rejection_reasons else "제약 통과"
        rendered.append(
            f"""
            <div class="pi-signal-row" style="grid-template-columns:minmax(145px,1fr) 72px 90px minmax(160px,1.2fr) minmax(130px,1fr);">
                <div><strong>{html.escape(row.name)}</strong><br/><span>{html.escape(row.code)} | {html.escape(row.sector)}</span></div>
                <div><span class="pi-badge {_optimizer_action_tone(row.action)}">{html.escape(action_label(row.action))}</span><br/><small>{html.escape(str(row.final_alpha_score or "N/A"))}</small></div>
                <div>{html.escape(_weight_text(row.current_weight))}<br/><strong>{html.escape(_weight_text(row.target_weight))}</strong></div>
                <div><div class="pi-allocation-track"><div class="pi-allocation-fill" style="width:{width:.1f}%; background:{color};"></div></div><small>{html.escape(reason)}</small></div>
                <div>차이 {html.escape(_weight_text(row.weight_delta))}<br/><small>{html.escape(rejection)}</small></div>
            </div>
            """
        )
    return "".join(rendered)


def _portfolio_alert_rows(rows: tuple[PortfolioAlertRow, ...]) -> str:
    if not rows:
        return f'<div class="pi-rebalance-reason">{html.escape(ko_sentence("No active portfolio alerts."))}</div>'
    rendered = []
    for row in rows[:8]:
        severity_tone = getRiskSeverityColorClass(row.severity)
        tone = "risk-critical" if severity_tone == "risk-critical" else "warn" if severity_tone == "risk-warning" else "info"
        rendered.append(
            f"""
            <div class="pi-rebalance-item">
                <div class="pi-rebalance-top"><div class="pi-rebalance-asset">{html.escape(ko_sentence(row.title))}</div><span class="pi-badge {tone}">{html.escape(severity_label(row.severity))}</span></div>
                <div class="pi-rebalance-reason">{html.escape(ko_sentence(row.message))}</div>
                <div class="pi-rebalance-impact">{html.escape(ko_sentence(row.recommended_review))}</div>
            </div>
            """
        )
    return "".join(rendered)


def _stress_rows(rows: tuple[StressScenarioRow, ...]) -> str:
    if not rows:
        return f'<div class="pi-rebalance-reason">{html.escape(ko_sentence("No stress scenarios available."))}</div>'
    rendered = []
    for row in rows:
        impact = f"{row.estimated_portfolio_impact_pct * 100:+.2f}%"
        affected = ", ".join(row.most_affected) if row.most_affected else "N/A"
        rendered.append(
            f"""
            <div class="pi-signal-row" style="grid-template-columns:minmax(150px,1fr) 80px minmax(140px,1fr) minmax(180px,1.2fr);">
                <div><strong>{html.escape(row.name)}</strong><br/><span>{html.escape(row.scenario_id)}</span></div>
                <div>영향<br/><strong>{html.escape(impact)}</strong></div>
                <div>민감 종목<br/><small>{html.escape(affected)}</small></div>
                <div>{html.escape(ko_sentence(row.explanation))}</div>
            </div>
            """
        )
    return "".join(rendered)


def portfolio_optimizer_alert_center_html(state: PortfolioOptimizerAlertCenterState) -> str:
    if state.status == "loading":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">{html.escape(status_label("loading"))}</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Portfolio optimizer and alert rules are being prepared."))}</div></div>'
    elif state.status == "error":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">{html.escape(status_label("error"))}</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Portfolio optimizer calculation failed."))}</div></div>'
    elif state.status == "empty":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">최적화 결과 없음</div><div class="pi-rebalance-reason">{html.escape(ko_sentence("Connect holdings and Forward Alpha Ranking output."))}</div></div>'
    else:
        recommendation_count = next((point.display_value for point in state.data_points if point.key == "recommendation_count"), "0")
        alert_count = next((point.display_value for point in state.data_points if point.key == "alert_count"), "0")
        cash_ratio = next((point.display_value for point in state.data_points if point.key == "cash_ratio"), "N/A")
        actionable = tuple(row for row in state.recommendation_rows if row.action not in {"AVOID", "EXCLUDE"})
        body = f"""
        <div class="portfolio-intelligence-grid">
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Optimizer Summary"))}</strong><span>{html.escape(ui_label("long-only / no leverage"))}</span></div>
                <div class="pi-card-body">
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-top"><div class="pi-rebalance-asset">{html.escape(ui_label("Recommendations"))}</div><span class="pi-badge {_coverage_tone(state.status)}">{html.escape(status_label(state.status))}</span></div>
                        <div class="pi-rebalance-amount" style="text-align:left; margin-top:6px;">{html.escape(str(recommendation_count))}</div>
                        <div class="pi-rebalance-impact">알림 {html.escape(str(alert_count))} · 현금 {html.escape(str(cash_ratio))}</div>
                    </div>
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-asset">{html.escape(ui_label("Risk constraints"))}</div>
                        <div class="pi-rebalance-reason">단일 {html.escape(_weight_text(state.max_single_stock_weight))} · KOSDAQ {html.escape(_weight_text(state.max_kosdaq_single_stock_weight))} · 섹터 {html.escape(_weight_text(state.max_sector_weight))}</div>
                        <div class="pi-rebalance-impact">현금 버퍼 {html.escape(_weight_text(state.target_cash_ratio))}. 주문 실행 API는 없습니다.</div>
                    </div>
                </div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Current vs Target Weights"))}</strong><span>{html.escape(ui_label("review actions only"))}</span></div>
                <div class="pi-card-body">{_optimizer_rows(actionable, "검토 가능한 목표 없음")}</div>
            </div>
            <div class="pi-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Rejected Candidates"))}</strong><span>{html.escape(ui_label("risk gates"))}</span></div>
                <div class="pi-card-body">{_optimizer_rows(state.rejected_candidates, "제외 후보 없음")}</div>
            </div>
        </div>
        <div class="pi-detail-grid">
            <div class="pi-card pi-risk-card">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Alert Center"))}</strong><span>{html.escape(ui_label("monitoring rules"))}</span></div>
                <div class="pi-card-body">{_portfolio_alert_rows(state.alerts)}</div>
            </div>
            <div class="pi-card pi-insight-card" style="grid-column: span 7;">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Stress Scenario Table"))}</strong><span>{html.escape(ui_label("risk proxy"))}</span></div>
                <div class="pi-card-body">{_stress_rows(state.stress_scenarios)}</div>
            </div>
        </div>
        <div class="pi-detail-grid">
            <div class="pi-card pi-insight-card" style="grid-column: span 12;">
                <div class="pi-card-header"><strong>{html.escape(ui_label("Explanation Drawer"))}</strong><span>{html.escape(ui_label("constraint logic"))}</span></div>
                <div class="pi-card-body">
                    <div class="pi-rebalance-item">
                        <div class="pi-rebalance-asset">{html.escape(ui_label("How targets are created"))}</div>
                        <div class="pi-rebalance-reason">{html.escape(ko_sentence("ForwardAlphaScore and ConfidenceScore set initial target weight; liquidity, sector caps, cash buffer, and severe risk flags cap or exclude positions."))}</div>
                        <div class="pi-rebalance-impact">{html.escape(ko_sentence("Actions are portfolio review labels only. No automatic order execution is implemented."))}</div>
                    </div>
                </div>
            </div>
        </div>
        """
    return f"""
    <section class="portfolio-intelligence-shell" aria-label="PortfolioOptimizerAlertCenter" data-module-id="PortfolioOptimizerAlertCenter">
        <div class="portfolio-intelligence-title">
            <div>
                <strong>{html.escape(module_title("Portfolio Optimizer & Alert Center"))}</strong>
                <span>{html.escape(ko_sentence(state.summary))}</span>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                {_badge(state.status)}
                <span class="pi-badge info">{html.escape(ui_label("No order API"))}</span>
            </div>
        </div>
        {body}
    </section>
    """
