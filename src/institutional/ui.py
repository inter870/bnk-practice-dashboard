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
from .data_trust_display import (
    formatDataTrustMetadataKo,
    formatKoDateTime,
    isPlannedAdapter,
)
from .market_regime import (
    SECTOR_HEADWIND_MAX_SCORE,
    SECTOR_TAILWIND_MIN_SCORE,
    normalize_regime_label_ko,
)
from src.ui.korean_labels import (
    action_label,
    alpha_driver_label,
    asset_class_label,
    dart_category_label,
    ko_sentence,
    module_title,
    rating_label,
    risk_flag_label,
    sector_driver_text,
    sector_empty_state,
    sector_environment_labels,
    severity_label,
    sector_label,
    signal_label,
    source_meta_line,
    status_label,
    stock_name_label,
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


def _is_macro_mock_source(source: Any) -> bool:
    text = str(source or "").strip().lower()
    return text.startswith("mock") or " mock " in f" {text} " or "모의" in text


def _macro_row_is_mock(row: MacroIndicatorRow) -> bool:
    return _is_macro_mock_source(row.meta.source)


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


def _coverage_rows(rows: tuple[SourceCoverageRow, ...]) -> str:
    if not rows:
        return """
        <div class="pi-rebalance-item">
            <div class="pi-rebalance-asset">출처 커버리지 없음</div>
            <div class="pi-rebalance-reason">데이터 출처 메타데이터를 표시할 수 없습니다.</div>
        </div>
        """
    rendered = []
    for row in rows:
        fields = formatDataTrustMetadataKo(row)
        status_tone = "warn" if isPlannedAdapter(row) else _coverage_tone(row.status or row.coverage_status)
        accuracy_tone = "warn" if fields.accuracyBadgeKo == "표시 불가" else "info"
        key_tone = "warn" if fields.keyStatusKo.startswith(("누락 키:", "키 확인:", "선택 키")) else "info"
        freshness_badge = (
            f'<span class="pi-badge warn">{html.escape(fields.freshnessKo)}</span>'
            if fields.freshnessKo
            else ""
        )
        meta_parts = [
            f"출처: {fields.sourceKo}",
            fields.asOfDateKo,
            fields.fetchedAtKo,
        ]
        if fields.availableAtKo:
            meta_parts.append(fields.availableAtKo)
        metadata_line = " · ".join(meta_parts)
        rendered.append(
            f"""
            <div class="pi-rebalance-item data-trust-row" style="margin-bottom:10px;">
                <div class="pi-rebalance-top" style="align-items:flex-start; gap:10px;">
                    <div class="pi-rebalance-asset" style="min-width:0;">
                        <strong>{html.escape(fields.titleKo)}</strong>
                        <br/><span style="overflow-wrap:anywhere;">{html.escape(fields.endpointKo)}</span>
                    </div>
                    <div style="display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-end;">
                        <span class="pi-badge {status_tone}">{html.escape(fields.statusBadgeKo)}</span>
                        <span class="pi-badge {accuracy_tone}">{html.escape(fields.accuracyBadgeKo)}</span>
                        {freshness_badge}
                    </div>
                </div>
                <div class="pi-rebalance-reason" style="margin-top:8px;">{html.escape(fields.primaryMessageKo)}</div>
                <div class="pi-rebalance-impact" style="margin-top:6px;">
                    <span class="pi-badge {key_tone}" style="margin-right:6px;">{html.escape(fields.keyStatusKo)}</span>
                    <span>{html.escape(fields.confidenceKo)}</span>
                </div>
                <div class="pi-rebalance-impact" style="margin-top:6px; overflow-wrap:anywhere;">{html.escape(metadata_line)}</div>
            </div>
            """
        )
    return "".join(rendered)


def _coverage_status_counts(rows: tuple[SourceCoverageRow, ...]) -> dict[str, int]:
    counts = {"connected": 0, "partial": 0, "stale": 0, "missing_key": 0, "planned": 0, "mock": 0}
    for row in rows:
        status = "planned" if isPlannedAdapter(row) else row.status or row.coverage_status
        if row.is_mock:
            status = "mock"
        elif row.meta.stale_data_flag and status not in {"missing_key", "planned"}:
            status = "stale"
        if status in {"available", "connected", "manual"}:
            counts["connected"] += 1
        elif status in {"partial", "partially_connected"}:
            counts["partial"] += 1
        elif status == "stale":
            counts["stale"] += 1
        elif status == "missing_key":
            counts["missing_key"] += 1
        elif status == "planned":
            counts["planned"] += 1
        elif status == "mock":
            counts["mock"] += 1
    return counts


def _coverage_summary_metrics(rows: tuple[SourceCoverageRow, ...]) -> str:
    counts = _coverage_status_counts(rows)
    items = [
        ("정상", counts["connected"], "good"),
        ("부분 연결", counts["partial"], "info"),
        ("업데이트 필요", counts["stale"], "warn"),
        ("키 누락", counts["missing_key"], "risk"),
        ("연결 예정", counts["planned"], "warn"),
        ("모의 데이터", counts["mock"], "warn"),
    ]
    return "".join(
        f"""
        <div class="pi-rebalance-item" style="min-height:74px;">
            <div class="pi-rebalance-top">
                <div class="pi-rebalance-asset">{html.escape(label)}</div>
                <span class="pi-badge {tone}">{html.escape(str(count))}</span>
            </div>
        </div>
        """
        for label, count, tone in items
    )


def _coverage_rows(rows: tuple[SourceCoverageRow, ...]) -> str:
    if not rows:
        return """
        <div class="pi-rebalance-item">
            <div class="pi-rebalance-asset">출처 커버리지 없음</div>
            <div class="pi-rebalance-reason">데이터 출처 메타데이터를 표시할 수 없습니다.</div>
        </div>
        """

    header = """
    <div class="pi-signal-row" style="grid-template-columns:minmax(132px,1.1fr) 92px minmax(120px,1fr) 104px 96px 92px minmax(150px,1.1fr); font-weight:700;">
        <div>데이터</div>
        <div>상태</div>
        <div>출처</div>
        <div>기준일</div>
        <div>신선도</div>
        <div>신뢰도</div>
        <div>조치</div>
    </div>
    """
    body: list[str] = [header]
    detail_rows: list[str] = []
    for row in rows:
        fields = formatDataTrustMetadataKo(row)
        status = "planned" if isPlannedAdapter(row) else row.status or row.coverage_status
        if row.is_mock:
            status = "mock"
        tone = "warn" if status in {"planned", "stale", "mock"} else _coverage_tone(status)
        accuracy_tone = "warn" if fields.accuracyBadgeKo == "표시 불가" else "info"
        accuracy_badge = (
            ""
            if fields.accuracyBadgeKo == fields.statusBadgeKo
            else f'<span class="pi-badge {accuracy_tone}">{html.escape(fields.accuracyBadgeKo)}</span>'
        )
        confidence = fields.confidenceKo.replace("신뢰도 ", "")
        reference_date = fields.asOfDateKo.replace("기준일: ", "")
        action = fields.actionRequiredKo or fields.keyStatusKo
        freshness = fields.freshnessKo or ("일정 미정" if isPlannedAdapter(row) else "정상")
        source = fields.sourceKo
        body.append(
            f"""
            <div class="pi-signal-row data-trust-compact-row" style="grid-template-columns:minmax(132px,1.1fr) 92px minmax(120px,1fr) 104px 96px 92px minmax(150px,1.1fr);">
                <div><strong>{html.escape(fields.titleKo)}</strong></div>
                <div style="display:flex; gap:4px; flex-wrap:wrap;">
                    <span class="pi-badge {tone}">{html.escape(fields.statusBadgeKo)}</span>
                    {accuracy_badge}
                </div>
                <div>{html.escape(source)}</div>
                <div>{html.escape(reference_date)}</div>
                <div>{html.escape(freshness)}</div>
                <div>{html.escape(confidence)}</div>
                <div>{html.escape(action)}</div>
            </div>
            """
        )
        required = ", ".join(row.required_keys or row.required_api_keys) if (row.required_keys or row.required_api_keys) else "해당 없음"
        missing = ", ".join(row.missing_keys or row.missing_api_keys) if (row.missing_keys or row.missing_api_keys) else ""
        missing_line = f" · 누락 키: {html.escape(missing)}" if missing and not isPlannedAdapter(row) else ""
        notes = " / ".join(ko_sentence(note) for note in row.notes[:3]) if row.notes else "진단 메시지 없음"
        detail_rows.append(
            f"""
            <div class="pi-rebalance-item">
                <div class="pi-rebalance-top">
                    <div class="pi-rebalance-asset">{html.escape(fields.titleKo)}</div>
                    <span class="pi-badge {tone}">{html.escape(fields.statusBadgeKo)}</span>
                </div>
                <div class="pi-rebalance-reason">{html.escape(fields.primaryMessageKo)}</div>
                <div class="pi-rebalance-impact" style="overflow-wrap:anywhere;">
                    {html.escape(fields.endpointKo)} · 필요 키: {html.escape(required)}{missing_line}
                </div>
                <div class="pi-rebalance-impact" style="overflow-wrap:anywhere;">
                    {html.escape(fields.asOfDateKo)} · {html.escape(fields.fetchedAtKo)} · {html.escape(fields.availableAtKo or '사용 가능 시점: 해당 없음')}
                </div>
                <div class="pi-rebalance-impact">{html.escape(notes)}</div>
            </div>
            """
        )
    details = f"""
    <details class="pi-rebalance-item" style="margin-top:10px;">
        <summary style="cursor:pointer; font-weight:700;">데이터 진단 상세 보기</summary>
        <div style="margin-top:10px;">{''.join(detail_rows)}</div>
    </details>
    """
    return "".join(body) + details


def data_trust_source_panel_html(state: DataTrustSourcePanelState) -> str:
    key_text = ", ".join(state.missing_api_keys) if state.missing_api_keys else "필수 키 경고 없음"
    pit_tone = "good" if state.point_in_time_status == "compliant" else "warn"
    latest_refresh_text = formatKoDateTime(state.latest_refresh_time)
    stale_text = ", ".join(state.stale_sources[:4]) if state.stale_sources else "업데이트 필요 항목 없음"
    missing_text = ", ".join(state.missing_sources[:4]) if state.missing_sources else "확인된 누락 소스 없음"
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
            {_coverage_summary_metrics(state.source_coverage)}
        </div>
        <div class="pi-card" style="margin-top:14px;">
            <div class="pi-card-header"><strong>데이터 출처 커버리지</strong><span>{html.escape(latest_refresh_text)}</span></div>
            <div class="pi-card-body">
                <div class="pi-rebalance-item" style="margin-bottom:10px;">
                    <div class="pi-rebalance-top">
                        <div class="pi-rebalance-asset">키 상태 요약</div>
                        <span class="pi-badge {pit_tone}">PIT {html.escape(status_label(state.point_in_time_status))}</span>
                    </div>
                    <div class="pi-rebalance-reason">{html.escape(key_text)}</div>
                    <div class="pi-rebalance-impact">키 이름만 표시하며 실제 secret 값은 렌더링하지 않습니다.</div>
                </div>
                {_coverage_rows(state.source_coverage)}
            </div>
        </div>
        <details class="pi-card" style="margin-top:14px;">
            <summary class="pi-card-header" style="cursor:pointer;">
                <strong>데이터 신뢰도 기준</strong><span>신선도·출처·{html.escape(ui_label("Point-in-Time Gate"))}</span>
            </summary>
            <div class="pi-card-body">
                <div class="pi-rebalance-item">
                    <div class="pi-rebalance-top">
                        <div class="pi-rebalance-asset">최근 수집</div>
                        <span class="pi-badge info">수집 시각</span>
                    </div>
                    <div class="pi-rebalance-amount" style="text-align:left; margin-top:6px;">{html.escape(latest_refresh_text)}</div>
                    <div class="pi-rebalance-impact">모든 행은 출처, endpoint, 기준일, 사용 가능 시점, 수집 시각, 신뢰도, stale/missing 플래그를 포함합니다.</div>
                </div>
                <div class="pi-rebalance-item">
                    <div class="pi-rebalance-top">
                        <div class="pi-rebalance-asset">{html.escape(ui_label("Stale warnings"))}</div>
                        <span class="pi-badge warn">{html.escape(str(len(state.stale_sources)))}</span>
                    </div>
                    <div class="pi-rebalance-reason">{html.escape(stale_text)}</div>
                </div>
                <div class="pi-rebalance-item">
                    <div class="pi-rebalance-top">
                        <div class="pi-rebalance-asset">누락 소스</div>
                        <span class="pi-badge risk">{html.escape(str(len(state.missing_sources)))}</span>
                    </div>
                    <div class="pi-rebalance-reason">{html.escape(missing_text)}</div>
                </div>
                <div class="pi-rebalance-item">
                    <div class="pi-rebalance-top">
                        <div class="pi-rebalance-asset">{html.escape(ui_label("Point-in-Time Gate"))}</div>
                        <span class="pi-badge {pit_tone}">{html.escape(status_label(state.point_in_time_status))}</span>
                    </div>
                    <div class="pi-rebalance-reason">DART와 매크로 데이터는 분석에 쓰기 전에 접수일, 사용 가능 시점, 수집 시각 기준으로 검토합니다.</div>
                    <div class="pi-rebalance-impact">이 패널은 거래 신호가 아니라 데이터 검증 게이트입니다.</div>
                </div>
            </div>
        </details>
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
    if row.unit == "index_level":
        return f"{row.value:,.2f}"
    if row.unit == "%":
        return f"{row.value:.2f}%"
    if row.unit == "% YoY":
        return f"{row.value:.2f}% YoY"
    if row.unit == "1D %":
        return f"{row.value:.2f}%"
    if row.unit == "KRW per USD":
        return f"{row.value:,.2f}"
    return f"{row.value:,.2f} {row.unit}"


def _macro_change(row: MacroIndicatorRow) -> str:
    if row.change is None:
        return ""
    if row.key in {"kospi_momentum", "kosdaq_momentum"}:
        return f"{row.change:+.2f}%"
    if row.unit == "%":
        return f"{row.change:+.2f}%p"
    if row.unit == "% YoY":
        return f"{row.change:+.2f}%p"
    if row.unit == "KRW per USD":
        return f"{row.change:+.2f}%"
    return f"{row.change:+.2f}"


def _macro_heatmap_rows(rows: tuple[MacroIndicatorRow, ...]) -> str:
    if not rows:
        return f'<div class="pi-rebalance-reason">{html.escape(ko_sentence("No macro indicators available."))}</div>'
    rendered = [
        """
        <div class="macro-heatmap-header" role="row">
            <div>지표</div>
            <div>점수</div>
            <div>신호</div>
            <div>현재값</div>
        </div>
        """
    ]
    for row in rows:
        width = max(3, min(100, row.score))
        tone = _macro_signal_tone(row.signal)
        change_text = _macro_change(row)
        value_text = _macro_value(row)
        change_label = f"1D {change_text}" if change_text and row.key in {"kospi_momentum", "kosdaq_momentum"} else change_text
        source_line = html.escape(row.meta.source)
        mock_badge = '<span class="macro-source-badge warn">모의</span>' if _macro_row_is_mock(row) else ""
        rendered.append(
            f"""
            <div class="macro-heatmap-row {tone}" role="row">
                <div class="macro-heatmap-main">
                    <strong>{html.escape(ui_label(row.label))}</strong>
                    <span>{source_line} {mock_badge}</span>
                </div>
                <div class="macro-heatmap-score" aria-label="{html.escape(ui_label(row.label))} 점수 {row.score}">
                    <div class="macro-score-track"><div class="macro-score-fill" style="width:{width:.1f}%;"></div></div>
                    <span>{html.escape(str(row.score))}</span>
                </div>
                <div class="macro-heatmap-signal">
                    <span class="pi-badge {tone}">{html.escape(signal_label(row.signal))}</span>
                </div>
                <div class="macro-heatmap-value">
                    <strong>{html.escape(value_text)}</strong>
                    {f'<span>{html.escape(change_label)}</span>' if change_label else '<span>변화율 없음</span>'}
                </div>
            </div>
            """
        )
    return f'<div class="macro-heatmap-compact" role="table" aria-label="매크로 히트맵 compact table">{"".join(rendered)}</div>'


def _sector_tailwind_rows(rows: tuple[SectorTailwindRow, ...]) -> str:
    if not rows:
        return f'<div class="pi-rebalance-reason">{html.escape(ko_sentence("No sector tailwind data available."))}</div>'
    rendered = []
    for row in rows[:6]:
        positives = ", ".join(alpha_driver_label(item) for item in row.positive_drivers) if row.positive_drivers else "없음"
        negatives = ", ".join(alpha_driver_label(item) for item in row.negative_drivers) if row.negative_drivers else "없음"
        rendered.append(
            f"""
            <div class="pi-signal-row" style="grid-template-columns:minmax(130px,1fr) 76px minmax(160px,1.2fr);">
                <div><strong>{html.escape(sector_label(row.sector))}</strong><br/><span>+ {html.escape(positives)} / - {html.escape(negatives)}</span></div>
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
                    <div class="pi-rebalance-asset">{html.escape(ui_label(row.label))}</div>
                    <span class="pi-badge {tone_map.get(row.impact, 'info')}">{html.escape(severity_label(row.impact))}</span>
                </div>
                <div class="pi-rebalance-reason">{html.escape(ko_sentence(row.change_text))}</div>
                <div class="pi-rebalance-impact">{html.escape(source_meta_line(row.meta))}</div>
            </div>
            """
        )
    return "".join(rendered)


def _sector_driver_rows(rows: tuple[SectorTailwindRow, ...], label: str, *, limit: int = 3) -> str:
    selected = [row for row in rows if row.label == label][:limit]
    if not selected:
        message, criterion = sector_empty_state(
            label,
            tailwind_min_score=SECTOR_TAILWIND_MIN_SCORE,
            headwind_max_score=SECTOR_HEADWIND_MAX_SCORE,
        )
        return f"""
        <div class="sector-environment-empty" role="status">
            <strong>{html.escape(message)}</strong>
            <span>{html.escape(criterion)}</span>
        </div>
        """
    labels = sector_environment_labels(label)
    rendered: list[str] = []
    for row in selected:
        positives = sector_driver_text(row.positive_drivers[:2], role="positive")
        negatives = sector_driver_text(row.negative_drivers[:2], role="negative")
        score = max(0, min(100, int(row.tailwind_score)))
        rendered.append(
            f"""
            <div class="sector-environment-item {html.escape(row.label)}" role="listitem">
                <div class="sector-environment-heading">
                    <strong>{html.escape(sector_label(row.sector))}</strong>
                    <span class="sector-environment-score">{score}/100</span>
                </div>
                <div class="sector-environment-track" role="img" aria-label="섹터 환경 점수 {score}점">
                    <span class="sector-environment-fill" style="width:{score}%;"></span>
                </div>
                <div class="sector-environment-factor positive">
                    <span>{html.escape(labels['positive_label'])}</span>
                    <strong>{html.escape(positives)}</strong>
                </div>
                <div class="sector-environment-factor negative">
                    <span>{html.escape(labels['negative_label'])}</span>
                    <strong>{html.escape(negatives)}</strong>
                </div>
            </div>
            """
        )
    return f'<div class="sector-environment-list" role="list">{"".join(rendered)}</div>'


def _sector_environment_card(rows: tuple[SectorTailwindRow, ...], label: str) -> str:
    labels = sector_environment_labels(label)
    return f"""
    <section class="pi-card sector-environment-card {html.escape(label)}" aria-label="{html.escape(labels['title'])}">
        <div class="pi-card-header sector-environment-header">
            <strong>{html.escape(labels['title'])}</strong>
            <span>{html.escape(labels['subtitle'])}</span>
        </div>
        <div class="pi-card-body sector-environment-body">{_sector_driver_rows(rows, label)}</div>
    </section>
    """


def _macro_source_detail_rows(rows: tuple[MacroIndicatorRow, ...]) -> str:
    if not rows:
        return '<div class="pi-rebalance-reason">진단할 매크로 지표가 없습니다.</div>'
    rendered: list[str] = []
    for row in rows:
        mock = " · 모의 데이터" if _macro_row_is_mock(row) else ""
        stale = " · 업데이트 필요" if row.meta.stale_data_flag else ""
        rendered.append(
            f"""
            <div class="pi-rebalance-item">
                <div class="pi-rebalance-top">
                    <div class="pi-rebalance-asset">{html.escape(row.label)}</div>
                    <span class="pi-badge {_macro_signal_tone(row.signal)}">{html.escape(signal_label(row.signal))}</span>
                </div>
                <div class="pi-rebalance-reason">{html.escape(_macro_value(row))}{html.escape(' / ' + _macro_change(row) if _macro_change(row) else '')}</div>
                <div class="pi-rebalance-impact" style="overflow-wrap:anywhere;">
                    출처: {html.escape(row.meta.source)} · endpoint: {html.escape(row.meta.source_table_or_endpoint or '확인 필요')}{html.escape(mock)}{html.escape(stale)}
                </div>
            </div>
            """
        )
    return "".join(rendered)


def market_regime_macro_radar_html(state: MarketRegimeMacroRadarState) -> str:
    if state.status == "loading":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">{html.escape(status_label("loading"))}</div><div class="pi-rebalance-reason">시장 국면 데이터를 준비하고 있습니다.</div></div>'
    elif state.status == "error":
        body = f'<div class="pi-rebalance-item"><div class="pi-rebalance-asset">{html.escape(status_label("error"))}</div><div class="pi-rebalance-reason">시장 국면 계산에 실패했습니다.</div></div>'
    elif state.status == "empty":
        body = '<div class="pi-rebalance-item"><div class="pi-rebalance-asset">매크로 데이터 없음</div><div class="pi-rebalance-reason">시장 또는 매크로 출처를 연결하면 국면 레이더를 계산할 수 있습니다.</div></div>'
    else:
        mock_included = any(_macro_row_is_mock(row) for row in state.macro_heatmap)
        label_badges = "".join(f'<span class="pi-badge info">{html.escape(normalize_regime_label_ko(label))}</span>' for label in state.regime_labels)
        mock_badge = '<span class="pi-badge warn">모의 지표 포함</span>' if mock_included else ""
        latest_text = formatKoDateTime(state.latest_source_at)
        current_regime = normalize_regime_label_ko(state.current_regime_label)
        body = f"""
        <div class="pi-card">
            <div class="pi-card-header"><strong>시장 국면 요약</strong><span>위험선호/위험회피</span></div>
            <div class="pi-card-body">
                <div class="pi-rebalance-item">
                    <div class="pi-rebalance-top">
                        <div class="pi-rebalance-asset">{html.escape(current_regime)}</div>
                        <span class="pi-badge {_coverage_tone(state.status)}">{html.escape(status_label(state.status))}</span>
                    </div>
                    <div class="pi-rebalance-amount" style="text-align:left; margin-top:6px;">{state.regime_score}/100</div>
                    <div class="pi-rebalance-reason">{html.escape(state.summary)}</div>
                    <div class="pi-rebalance-impact">{html.escape(latest_text)}</div>
                </div>
                <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:10px;">{label_badges}{mock_badge}</div>
            </div>
        </div>
        <div class="portfolio-intelligence-grid sector-environment-grid">
            {_sector_environment_card(state.sector_tailwinds, "tailwind")}
            {_sector_environment_card(state.sector_tailwinds, "headwind")}
            {_sector_environment_card(state.sector_tailwinds, "neutral")}
        </div>
        <div class="pi-card" style="margin-top:14px;">
            <div class="pi-card-header"><strong>매크로 히트맵</strong><span>compact table</span></div>
            <div class="pi-card-body">{_macro_heatmap_rows(state.macro_heatmap)}</div>
        </div>
        <details class="pi-card" style="margin-top:14px;">
            <summary class="pi-card-header" style="cursor:pointer;">
                <strong>매크로 진단 상세 보기</strong><span>출처·endpoint·최근 변화</span>
            </summary>
            <div class="pi-card-body">
                <div class="pi-rebalance-item">
                    <div class="pi-rebalance-asset">최근 변화</div>
                    <div class="pi-rebalance-list">{_recent_change_rows(state.recent_changes)}</div>
                </div>
                {_macro_source_detail_rows(state.macro_heatmap)}
            </div>
        </details>
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
        return "데이터 없음"
    if row.unit == "%":
        return f"{row.value:.2f}%"
    if row.unit.startswith("KRW per"):
        return f"{row.value:,.2f}"
    return f"{row.value:,.2f} {row.unit}"


def _fx_change(row: FXRatesIndicatorRow) -> str:
    if row.change is None:
        return "변화 없음"
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
                <div class="pi-asset-label">{html.escape(ui_label(row.label))}<br/><small>{html.escape(row.meta.source)}{html.escape(stale)}</small></div>
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
                    <div class="pi-rebalance-asset">{html.escape(ui_label(row.channel))}</div>
                    <span class="pi-badge {tone}">{row.impact_score}/100</span>
                </div>
                <div class="pi-rebalance-reason">우호: {html.escape(ko_sentence(row.favored))} · 부담: {html.escape(ko_sentence(row.pressured))}</div>
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
        curve_text = "계산 불가" if state.yield_curve_slope is None else f"{state.yield_curve_slope:+.2f}%p"
        impact_text = "계산 불가" if state.portfolio_krw_impact_pct is None else f"{state.portfolio_krw_impact_pct * 100:+.2f}%"
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


def _alpha_driver_chips(items: tuple[str, ...], empty_label: str, *, kind: str) -> str:
    if not items:
        return f'<span class="pi-badge info" style="white-space:normal;">{html.escape(empty_label)}</span>'
    tone = {"positive": "good", "negative": "warn", "risk": "risk"}.get(kind, "info")
    formatter = risk_flag_label if kind == "risk" else alpha_driver_label
    return " ".join(
        f'<span class="pi-badge {tone}" style="white-space:normal; justify-content:flex-start; margin:2px 3px 2px 0;">{html.escape(formatter(item))}</span>'
        for item in items[:4]
    )


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
        display_name = stock_name_label(row.name)
        display_sector = sector_label(row.sector)
        risk_line = _alpha_driver_chips(row.risk_flags, "리스크 플래그 없음", kind="risk")
        positive_line = _alpha_driver_chips(row.positive_drivers, "긍정 근거 없음", kind="positive")
        negative_line = _alpha_driver_chips(row.negative_drivers, "부정 근거 없음", kind="negative")
        warning = f"<br/><small>{html.escape(ko_sentence(row.stale_data_warning))}</small>" if row.stale_data_warning else ""
        rendered.append(
            f"""
            <div class="pi-signal-row alpha-rank-row" style="grid-template-columns:minmax(170px,1fr) 76px 86px minmax(190px,1.15fr) minmax(220px,1.45fr); align-items:start;">
                <div><strong>{html.escape(display_name)}</strong><br/><span>{html.escape(row.code)} | {html.escape(display_sector)}</span></div>
                <div>알파<br/><strong>{row.final_alpha_score}</strong></div>
                <div>신뢰도<br/><strong>{row.confidence_score}</strong></div>
                <div><span class="pi-badge {_alpha_tone(row.rating)}">{html.escape(rating_label(row.rating))}</span><br/><small style="display:block; margin-top:6px;">리스크</small><div>{risk_line}</div>{warning}</div>
                <div>
                    <small style="display:block; margin-bottom:4px; color:#bbf7d0; font-weight:850;">긍정 근거</small>
                    <div>{positive_line}</div>
                    <small style="display:block; margin:8px 0 4px; color:#fde68a; font-weight:850;">점검할 부담 요인</small>
                    <div>{negative_line}</div>
                </div>
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
                <div class="pi-rebalance-top"><div class="pi-rebalance-asset">{html.escape(stock_name_label(row.name))}</div><span class="pi-badge {_alpha_tone(row.rating)}">{row.final_alpha_score}</span></div>
                <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:8px;">{pills}</div>
                <div class="pi-rebalance-impact">리스크 감점 {row.risk_penalty} · 스냅샷 {html.escape(row.feature_snapshot_id or "확인 불가")}</div>
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
