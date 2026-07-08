from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite, sqrt
from typing import Any, Iterable

from src.portfolio.mock_data import MOCK_HOLDINGS, MOCK_TOTAL_ASSETS

from .models import (
    AllocationSlice,
    DataPoint,
    DataSourceMeta,
    HoldingRiskRow,
    PortfolioRiskCockpitState,
    RiskAlert,
)


@dataclass(frozen=True)
class PortfolioRiskThresholds:
    single_stock_weight: float = 0.20
    sector_weight: float = 0.30
    cash_min_weight: float = 0.03
    top10_weight: float = 0.70
    stale_after_hours: float = 24.0
    illiquid_adv_weight: float = 0.05


def _now_iso(now: datetime | None = None) -> str:
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.isoformat(timespec="seconds")


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _get(item: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(item, dict) and name in item:
            return item.get(name)
        if hasattr(item, name):
            return getattr(item, name)
    return default


def _fmt_krw(value: Any) -> str:
    number = _finite(value)
    return "N/A" if number is None else f"KRW {number:,.0f}"


def _fmt_pct(value: Any) -> str:
    number = _finite(value)
    return "N/A" if number is None else f"{number * 100:.1f}%"


KST = timezone(timedelta(hours=9))


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


def _format_ko_date(value: Any) -> str:
    stamp = _as_datetime(value)
    if stamp is not None:
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp.astimezone(KST).strftime("%Y.%m.%d")
    text = str(value or "").strip()
    if len(text) >= 10:
        try:
            parsed = datetime.fromisoformat(text[:10])
            return parsed.strftime("%Y.%m.%d")
        except ValueError:
            return text[:10].replace("-", ".")
    return "N/A"


def _format_ko_datetime(value: Any) -> str:
    stamp = _as_datetime(value)
    if stamp is None:
        return "N/A"
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(KST).strftime("%Y.%m.%d %H:%M")


def _fmt_pp(value: Any) -> str:
    number = _finite(value)
    return "N/A" if number is None else f"{number * 100:+.1f}%p"


def _threshold_comparison(current: Any, threshold: Any, direction: str = "over") -> str:
    current_text = _fmt_pct(current)
    if threshold is None:
        return f"현재 {current_text}"
    threshold_text = _fmt_pct(threshold)
    gap = None
    current_number = _finite(current)
    threshold_number = _finite(threshold)
    if current_number is not None and threshold_number is not None:
        gap = current_number - threshold_number
    if direction == "below":
        return f"현재 {current_text} / 최소 {threshold_text} / 부족 {_fmt_pp(gap)}"
    if direction == "current":
        return f"현재 {current_text}"
    return f"현재 {current_text} / 기준 {threshold_text} / 초과 {_fmt_pp(gap)}"


def _data_mode(source_label: str, using_mock: bool) -> str:
    lowered = source_label.lower()
    if using_mock or "mock" in lowered:
        return "mock"
    if "csv" in lowered or "import" in lowered:
        return "imported"
    if "kis" in lowered or "broker" in lowered:
        return "broker"
    if "cache" in lowered:
        return "cache"
    if "sidebar" in lowered or "manual" in lowered:
        return "manual"
    return "manual"


def _actionability_for_alert(data_mode: str, *, stale: bool, alert_id: str) -> str:
    if data_mode == "mock":
        return "example_only"
    if stale and alert_id != "stale-data":
        return "blocked_by_stale_data"
    if alert_id == "stale-data":
        return "review_only"
    return "actionable"


def _display_severity_ko(severity: str, actionability: str) -> str:
    if actionability == "example_only":
        return "예시 알림"
    if actionability == "blocked_by_stale_data":
        return "오래된 데이터"
    if severity == "critical":
        return "긴급"
    if severity == "warning":
        return "주의"
    return "정보"


def _accuracy_grade(data_mode: str, stale: bool) -> tuple[str, str]:
    if data_mode == "mock":
        return "mock", "모의값"
    if stale:
        return "stale", "오래된 데이터"
    if data_mode == "broker":
        return "broker", "브로커 연동값"
    if data_mode == "imported":
        return "imported", "가져오기 입력값"
    if data_mode == "manual":
        return "manual", "수동 입력값"
    return "unavailable", "검증 필요"


def _risk_alert(
    *,
    alert_id: str,
    severity: str,
    title_ko: str,
    body_ko: str,
    review_action_ko: str,
    metric_key: str,
    current_value: float | None,
    threshold: float | None,
    meta: DataSourceMeta,
    holdings_source_label: str,
    using_mock: bool,
    direction: str = "over",
    affected_asset: str | None = None,
    affected_sector: str | None = None,
    sector_metadata_source: str | None = None,
    calculation_method: str = "concentration_threshold_rule",
    calculation_method_label_ko: str = "집중도 기준 규칙",
    missing_inputs: tuple[str, ...] = (),
) -> RiskAlert:
    mode = _data_mode(holdings_source_label, using_mock)
    stale = bool(meta.stale_data_flag)
    actionability = _actionability_for_alert(mode, stale=stale, alert_id=alert_id)
    display_severity_ko = _display_severity_ko(severity, actionability)
    accuracy_grade, accuracy_grade_ko = _accuracy_grade(mode, stale)
    price_source = meta.source
    holdings_source_ko = _source_label_ko(holdings_source_label)
    price_source_ko = _source_label_ko(price_source)
    sector_source = sector_metadata_source or price_source
    if actionability == "example_only":
        review_action_ko = "실제 보유 종목을 입력하면 실전 리스크 알림으로 전환됩니다."
    elif actionability == "blocked_by_stale_data":
        review_action_ko = "최신 가격 반영 후 다시 확인하세요."
    return RiskAlert(
        alert_id,
        severity,  # type: ignore[arg-type]
        title_ko,
        body_ko,
        metric_key,
        current_value,
        threshold,
        review_action_ko,
        meta,
        title_ko=title_ko,
        body_ko=body_ko,
        review_action_ko=review_action_ko,
        display_severity_ko=display_severity_ko,
        data_mode=mode,
        actionability=actionability,
        holdings_source=holdings_source_label,
        holdings_source_label_ko=holdings_source_ko,
        price_source=price_source,
        price_source_label_ko=price_source_ko,
        sector_metadata_source=sector_source,
        sector_metadata_source_label_ko=_source_label_ko(sector_source),
        calculation_method=calculation_method,
        calculation_method_label_ko=calculation_method_label_ko,
        as_of_date=meta.as_of_date,
        fetched_at=meta.fetched_at,
        fetched_at_ko=_format_ko_datetime(meta.fetched_at),
        stale_data_flag=stale,
        is_mock=mode == "mock",
        is_stale=stale,
        confidence_score=meta.confidence_score if meta.confidence_score is not None else meta.quality_score,
        accuracy_grade=accuracy_grade,
        accuracy_grade_ko=accuracy_grade_ko,
        missing_inputs=missing_inputs,
        unit="percent",
        affected_asset=affected_asset,
        affected_sector=affected_sector,
        explanation_ko=_threshold_comparison(current_value, threshold, direction),
        next_step_ko=review_action_ko,
    )


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        if hasattr(value, "to_pydatetime"):
            return value.to_pydatetime()
    except Exception:
        pass
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _as_date_text(value: Any) -> str | None:
    stamp = _as_datetime(value)
    if stamp is not None:
        return stamp.date().isoformat()
    if value:
        return str(value)[:10]
    return None


def _is_stale(asof: Any, *, now: datetime | None, stale_after_hours: float) -> bool:
    stamp = _as_datetime(asof)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if stamp is None:
        return True
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=current.tzinfo)
    return (current - stamp).total_seconds() > stale_after_hours * 3600


def _meta_from_snapshot(
    *,
    symbol: str,
    snapshots: dict[str, Any] | None,
    unit: str,
    now: datetime | None,
    stale_after_hours: float,
    fallback_source: str = "Manual portfolio input",
) -> DataSourceMeta:
    snap = (snapshots or {}).get(symbol)
    fetched_at = _now_iso(now)
    if snap is None:
        return DataSourceMeta(
            source=fallback_source,
            provider=None,
            source_url=None,
            as_of_date=None,
            available_at=None,
            fetched_at=fetched_at,
            frequency="manual",
            unit=unit,
            quality_score=55,
            is_fallback=True,
            stale_data_flag=True,
            warnings=("Missing market snapshot for holding.",),
            errors=(),
        )

    asof = _get(snap, "asof")
    source = str(_get(snap, "source", default="unknown") or "unknown")
    quality = int(_finite(_get(snap, "quality_score", default=0)) or 0)
    is_fallback = bool(_get(snap, "is_fallback", default=True))
    warnings = tuple(str(item) for item in (_get(snap, "warnings", default=()) or ()))
    errors = tuple(str(item) for item in (_get(snap, "errors", default=()) or ()))
    stale = _is_stale(asof, now=now, stale_after_hours=stale_after_hours)
    if stale:
        warnings = (*warnings, "stale data")
    return DataSourceMeta(
        source=source,
        provider=source,
        source_url=None,
        as_of_date=_as_date_text(asof),
        available_at=None,
        fetched_at=fetched_at,
        frequency=str(_get(snap, "frequency", default="unknown") or "unknown"),
        unit=unit or str(_get(snap, "unit", default="unknown") or "unknown"),
        quality_score=quality,
        is_fallback=is_fallback,
        stale_data_flag=stale,
        warnings=warnings,
        errors=errors,
    )


def _portfolio_meta(
    *,
    source: str,
    unit: str,
    now: datetime | None,
    stale: bool = False,
    is_fallback: bool = False,
    warning: str | None = None,
) -> DataSourceMeta:
    return DataSourceMeta(
        source=source,
        provider=source,
        source_url=None,
        as_of_date=(now or datetime.now()).date().isoformat(),
        available_at=None,
        fetched_at=_now_iso(now),
        frequency="session",
        unit=unit,
        quality_score=70 if is_fallback else 92,
        is_fallback=is_fallback,
        stale_data_flag=stale,
        warnings=(warning,) if warning else (),
        errors=(),
    )


def _holding_market(symbol: str, country: str, benchmark: str | None) -> str:
    if country.upper() == "KR" and symbol.isdigit() and len(symbol) == 6:
        return "KRX"
    if benchmark:
        return str(benchmark)
    return country.upper() or "Unknown"


KNOWN_KR_NAMES = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "034020": "두산에너빌리티",
    "035420": "NAVER",
    "KTB3Y": "국고채 3년 바스켓",
    "FUND10": "국내 성장 혼합펀드",
}

KNOWN_KR_SECTORS = {
    "005930": "반도체",
    "000660": "반도체",
    "034020": "에너지",
    "035420": "인터넷",
    "KTB3Y": "채권",
    "FUND10": "펀드",
}


def _display_name(symbol: str, raw_name: Any) -> str:
    return KNOWN_KR_NAMES.get(symbol, str(raw_name or symbol))


def _display_sector(symbol: str, raw_sector: Any) -> str:
    return KNOWN_KR_SECTORS.get(symbol, str(raw_sector or "미분류"))


def _holding_row(holding: Any, portfolio_value: float, meta: DataSourceMeta) -> HoldingRiskRow:
    quantity = _finite(_get(holding, "quantity", "qty")) or 0.0
    price = _finite(_get(holding, "current_price", "currentPrice", "price")) or 0.0
    avg = _finite(_get(holding, "average_cost", "averageCost", "avg_price"))
    value = quantity * price
    pnl_pct = None if avg in (None, 0) else price / avg - 1.0
    symbol = str(_get(holding, "symbol", "code", default=""))
    country = str(_get(holding, "country", default="KR") or "KR")
    adv = _finite(_get(holding, "average_traded_value", "averageTradedValue", "adv20"))
    liquidity_warning = None
    if adv not in (None, 0) and value / float(adv) >= 0.05:
        liquidity_warning = "Position value is above 5% of average traded value."
    return HoldingRiskRow(
        symbol=symbol,
        name=_display_name(symbol, _get(holding, "name", default=symbol)),
        asset_class=str(_get(holding, "asset_class", "assetClass", default="stocks") or "stocks"),
        market=_holding_market(symbol, country, _get(holding, "benchmark_symbol", "benchmarkSymbol")),
        sector=_display_sector(symbol, _get(holding, "sector", default="미분류")),
        country=country,
        currency=str(_get(holding, "currency", default="KRW") or "KRW"),
        quantity=quantity,
        current_price=price,
        market_value=value,
        weight=0.0 if portfolio_value <= 0 else value / portfolio_value,
        pnl_pct=pnl_pct,
        liquidity_warning=liquidity_warning,
        meta=meta,
    )


def _slice_rows(
    rows: Iterable[HoldingRiskRow],
    field: str,
    cash: float,
    total: float,
    cash_meta: DataSourceMeta,
) -> tuple[AllocationSlice, ...]:
    values: dict[str, tuple[str, float, DataSourceMeta]] = {}
    for row in rows:
        key = str(getattr(row, field) or "Unknown")
        current = values.get(key, (key, 0.0, row.meta))
        values[key] = (key, current[1] + row.market_value, current[2])

    if cash > 0:
        cash_key_by_field = {
            "asset_class": "cash",
            "currency": "KRW",
            "market": "Cash",
            "sector": "Cash",
        }
        cash_key = cash_key_by_field.get(field)
        if cash_key:
            current = values.get(cash_key, (cash_key, 0.0, cash_meta))
            values[cash_key] = (cash_key, current[1] + cash, cash_meta)

    slices = [
        AllocationSlice(key=key, label=label, value=value, weight=0.0 if total <= 0 else value / total, meta=meta)
        for key, (label, value, meta) in values.items()
        if value > 0
    ]
    return tuple(sorted(slices, key=lambda item: item.value, reverse=True))


def _series_values(price_series: Iterable[Any] | None) -> list[tuple[str, float]]:
    values = []
    for item in price_series or []:
        value = _finite(_get(item, "value", "total_value", "totalValue"))
        date = str(_get(item, "date", default=""))
        if value is not None and value > 0:
            values.append((date, value))
    values.sort(key=lambda item: item[0])
    return values


def _returns_from_series(price_series: Iterable[Any] | None) -> list[float]:
    values = _series_values(price_series)
    return [current / prev - 1.0 for (_, prev), (_, current) in zip(values, values[1:]) if prev > 0]


def _volatility_proxy(price_series: Iterable[Any] | None) -> float | None:
    returns = _returns_from_series(price_series)
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    result = sqrt(variance) * sqrt(252)
    return result if isfinite(result) else None


def _max_drawdown_proxy(price_series: Iterable[Any] | None) -> float | None:
    values = _series_values(price_series)
    if not values:
        return None
    peak = values[0][1]
    mdd = 0.0
    for _, value in values:
        peak = max(peak, value)
        if peak > 0:
            mdd = min(mdd, value / peak - 1.0)
    return mdd if isfinite(mdd) else None


def _period_return(price_series: Iterable[Any] | None) -> float | None:
    values = _series_values(price_series)
    if len(values) < 2 or values[0][1] <= 0:
        return None
    result = values[-1][1] / values[0][1] - 1.0
    return result if isfinite(result) else None


def _make_metric(
    key: str,
    label: str,
    value: Any,
    display: str,
    unit: str,
    meta: DataSourceMeta,
    description: str = "",
) -> DataPoint:
    metric_meta = DataSourceMeta(
        source=meta.source,
        provider=meta.provider,
        source_url=meta.source_url,
        as_of_date=meta.as_of_date,
        available_at=meta.available_at,
        fetched_at=meta.fetched_at,
        frequency=meta.frequency,
        unit=unit,
        quality_score=meta.quality_score,
        is_fallback=meta.is_fallback,
        stale_data_flag=meta.stale_data_flag,
        warnings=meta.warnings,
        errors=meta.errors,
    )
    return DataPoint(key, label, value, metric_meta, display, description or None)


def build_portfolio_risk_cockpit(
    holdings: Iterable[Any] | None,
    *,
    total_assets: float | None = None,
    cash: float | None = None,
    snapshots: dict[str, Any] | None = None,
    price_series: Iterable[Any] | None = None,
    thresholds: PortfolioRiskThresholds | None = None,
    now: datetime | None = None,
    allow_mock: bool = True,
    source_label: str = "Sidebar portfolio input",
) -> PortfolioRiskCockpitState:
    thresholds = thresholds or PortfolioRiskThresholds()
    raw_holdings = list(holdings or [])
    using_mock = False
    if not raw_holdings and allow_mock:
        raw_holdings = list(MOCK_HOLDINGS)
        using_mock = True
        source_label = "Mock portfolio data"
        total_assets = MOCK_TOTAL_ASSETS if total_assets in (None, 0) else total_assets

    if not raw_holdings and not allow_mock:
        meta = _portfolio_meta(source=source_label, unit="KRW", now=now, warning="No holdings supplied.")
        return PortfolioRiskCockpitState(
            module_id="PortfolioRiskCockpit",
            status="empty",
            title="Portfolio Risk Cockpit",
            summary="No holdings data is available, so portfolio risk cannot be calculated.",
            data_points=(
                _make_metric("total_portfolio_value", "Total Portfolio Value", None, "N/A", "KRW", meta),
                _make_metric("cash_ratio", "Cash Ratio", None, "N/A", "percent", meta),
            ),
            explanation=("Connect holdings or enter the sidebar CSV to calculate concentration and capital-at-risk.",),
            risk_flags=("empty",),
            stale_after_minutes=int(thresholds.stale_after_hours * 60),
        )

    row_metas = {
        str(_get(holding, "symbol", "code", default="")): _meta_from_snapshot(
            symbol=str(_get(holding, "symbol", "code", default="")),
            snapshots=snapshots,
            unit=str(_get(holding, "currency", default="KRW") or "KRW"),
            now=now,
            stale_after_hours=thresholds.stale_after_hours,
            fallback_source=source_label,
        )
        for holding in raw_holdings
    }
    preliminary_rows = [
        _holding_row(holding, 1.0, row_metas[str(_get(holding, "symbol", "code", default=""))])
        for holding in raw_holdings
    ]
    holdings_value = sum(row.market_value for row in preliminary_rows)
    if using_mock and cash is None:
        cash_value = max((total_assets or MOCK_TOTAL_ASSETS) - holdings_value, 0.0)
    else:
        cash_value = max(_finite(cash) or 0.0, 0.0)

    declared_total = _finite(total_assets)
    computed_total = holdings_value + cash_value
    portfolio_value = declared_total if declared_total and declared_total > 0 else computed_total
    if portfolio_value <= 0:
        portfolio_value = computed_total

    rows = [
        _holding_row(holding, portfolio_value, row_metas[str(_get(holding, "symbol", "code", default=""))])
        for holding in raw_holdings
    ]
    rows = sorted(rows, key=lambda row: row.market_value, reverse=True)
    cash_meta = _portfolio_meta(
        source=source_label,
        unit="KRW",
        now=now,
        is_fallback=using_mock,
        warning="Demo portfolio values." if using_mock else None,
    )
    source_meta = cash_meta
    stale = any(row.meta.stale_data_flag for row in rows)
    if stale:
        source_meta = _portfolio_meta(
            source=source_label,
            unit="mixed",
            now=now,
            stale=True,
            is_fallback=using_mock,
            warning="One or more holding prices are stale.",
        )

    asset_allocation = _slice_rows(rows, "asset_class", cash_value, portfolio_value, cash_meta)
    market_allocation = _slice_rows(rows, "market", cash_value, portfolio_value, cash_meta)
    sector_allocation = _slice_rows(rows, "sector", cash_value, portfolio_value, cash_meta)
    currency_allocation = _slice_rows(rows, "currency", cash_value, portfolio_value, cash_meta)

    top5 = tuple(rows[:5])
    top10_weight = sum(row.weight for row in rows[:10])
    top_weight = rows[0].weight if rows else 0.0
    largest_sector = sector_allocation[0] if sector_allocation else None
    cash_ratio = 0.0 if portfolio_value <= 0 else cash_value / portfolio_value
    vol = _volatility_proxy(price_series)
    mdd = _max_drawdown_proxy(price_series)
    krw_return = _period_return(price_series)
    local_return = krw_return if all(row.currency.upper() == "KRW" for row in rows) else None

    alerts: list[RiskAlert] = []
    if top_weight > thresholds.single_stock_weight and rows:
        if using_mock:
            body = f"{rows[0].name} 비중은 {_fmt_pct(top_weight)}로 표시되지만 현재 보유 데이터는 모의 데이터입니다."
            action = "실제 보유 종목을 입력하면 실전 집중도 리스크를 확인할 수 있습니다."
        else:
            body = f"{rows[0].name} 비중은 {_fmt_pct(top_weight)}로 기준치 {_fmt_pct(thresholds.single_stock_weight)}를 초과했습니다."
            action = "같은 종목에 추가 자금을 투입하기 전 단일 종목 집중 리스크를 먼저 점검하세요."
        alerts.append(
            _risk_alert(
                alert_id="single-stock-concentration",
                severity="critical" if top_weight >= thresholds.single_stock_weight * 1.5 else "warning",
                title_ko="단일 종목 집중도 초과",
                body_ko=body,
                review_action_ko=action,
                metric_key="top_holding_weight",
                current_value=top_weight,
                threshold=thresholds.single_stock_weight,
                meta=rows[0].meta,
                holdings_source_label=source_label,
                using_mock=using_mock,
                affected_asset=rows[0].name,
            )
        )
    if largest_sector and largest_sector.weight > thresholds.sector_weight:
        if using_mock:
            body = f"{largest_sector.label} 섹터 비중은 {_fmt_pct(largest_sector.weight)}로 표시되지만 현재 보유 데이터는 모의 데이터입니다."
            action = "실제 포트폴리오 기준으로 섹터 집중도를 다시 계산해야 합니다."
        else:
            body = f"{largest_sector.label} 섹터 비중은 {_fmt_pct(largest_sector.weight)}로 기준치 {_fmt_pct(thresholds.sector_weight)}를 초과했습니다."
            action = "신규 자금이 같은 섹터 노출을 더 키우는지 확인하세요."
        alerts.append(
            _risk_alert(
                alert_id="sector-concentration",
                severity="warning",
                title_ko="섹터 집중도 초과",
                body_ko=body,
                review_action_ko=action,
                metric_key="largest_sector_weight",
                current_value=largest_sector.weight,
                threshold=thresholds.sector_weight,
                meta=largest_sector.meta,
                holdings_source_label=source_label,
                using_mock=using_mock,
                affected_sector=largest_sector.label,
                sector_metadata_source=largest_sector.meta.source,
            )
        )
    if cash_ratio < thresholds.cash_min_weight:
        if using_mock:
            body = f"현금 비중은 {_fmt_pct(cash_ratio)}로 표시되지만 현재 값은 모의 포트폴리오 기준입니다."
            action = "실제 현금 잔고를 입력하면 정확한 현금 버퍼를 확인할 수 있습니다."
        else:
            body = f"현금 비중은 {_fmt_pct(cash_ratio)}로 최소 기준 {_fmt_pct(thresholds.cash_min_weight)}보다 낮습니다."
            action = "추가 매수 전 현금 여력과 강제 매도 가능성을 점검하세요."
        alerts.append(
            _risk_alert(
                alert_id="low-cash",
                severity="warning",
                title_ko="현금 버퍼 부족",
                body_ko=body,
                review_action_ko=action,
                metric_key="cash_ratio",
                current_value=cash_ratio,
                threshold=thresholds.cash_min_weight,
                meta=cash_meta,
                holdings_source_label=source_label,
                using_mock=using_mock,
                direction="below",
            )
        )
    if top10_weight > thresholds.top10_weight:
        if len(rows) <= 10:
            body = f"현재 보유 종목 수가 10개 이하이므로 상위 10개 집중도가 {_fmt_pct(top10_weight)}로 표시됩니다."
            action = "종목 수가 적을수록 개별 종목과 섹터 리스크가 커질 수 있습니다."
        else:
            body = f"상위 10개 보유 종목이 포트폴리오의 {_fmt_pct(top10_weight)}를 차지합니다."
            action = "상위 종목들이 같은 매크로, 섹터, 스타일 리스크에 노출되어 있는지 확인하세요."
        if using_mock:
            body = f"{body} 현재 보유 데이터는 모의 데이터입니다."
        alerts.append(
            _risk_alert(
                alert_id="top10-concentration",
                severity="warning",
                title_ko="상위 10개 종목 집중도",
                body_ko=body,
                review_action_ko=action,
                metric_key="top10_concentration",
                current_value=top10_weight,
                threshold=None,
                meta=source_meta,
                holdings_source_label=source_label,
                using_mock=using_mock,
                direction="current",
            )
        )
    for row in rows:
        if row.liquidity_warning:
            alerts.append(
                _risk_alert(
                    alert_id=f"illiquid-{row.symbol}",
                    severity="warning",
                    title_ko="유동성 점검",
                    body_ko=f"{row.name} 보유 규모가 평균 거래대금 대비 높습니다.",
                    review_action_ko="보수적 수량과 분할 실행 가정을 사용하세요.",
                    metric_key="liquidity",
                    current_value=row.weight,
                    threshold=thresholds.illiquid_adv_weight,
                    meta=row.meta,
                    holdings_source_label=source_label,
                    using_mock=using_mock,
                    affected_asset=row.name,
                )
            )
    if stale:
        alerts.append(
            _risk_alert(
                alert_id="stale-data",
                severity="warning",
                title_ko="오래된 데이터 점검",
                body_ko="일부 가격 또는 메타데이터가 신선도 기준보다 오래되었습니다.",
                review_action_ko="추가 투자 전 가격, 평가금액, 보유 비중을 새로고침하세요.",
                metric_key="stale_data",
                current_value=None,
                threshold=None,
                meta=source_meta,
                holdings_source_label=source_label,
                using_mock=using_mock,
                direction="current",
            )
        )

    metrics = (
        _make_metric("total_portfolio_value", "Total Portfolio Value", portfolio_value, _fmt_krw(portfolio_value), "KRW", source_meta),
        _make_metric("cash_ratio", "Cash Ratio", cash_ratio, _fmt_pct(cash_ratio), "percent", cash_meta),
        _make_metric("top_holding_weight", "Largest Single Holding", top_weight, _fmt_pct(top_weight), "percent", rows[0].meta if rows else source_meta),
        _make_metric("top10_concentration", "Top 10 Concentration", top10_weight, _fmt_pct(top10_weight), "percent", source_meta),
        _make_metric("portfolio_volatility_proxy", "Volatility Proxy", vol, _fmt_pct(vol), "annualized percent", source_meta, "Annualized volatility from portfolio value series."),
        _make_metric("max_drawdown_proxy", "Max Drawdown Proxy", mdd, _fmt_pct(mdd), "percent", source_meta, "Maximum drawdown from portfolio value series."),
        _make_metric("krw_return", "KRW Return", krw_return, _fmt_pct(krw_return), "percent", source_meta),
        _make_metric("local_currency_return", "Local Currency Return", local_return, _fmt_pct(local_return), "percent", source_meta),
    )
    status = "stale" if stale else "ready"
    summary = "포트폴리오 보유, 집중도, 유동성, 현금 버퍼, 데이터 신선도를 점검합니다."
    if alerts:
        if using_mock:
            summary = f"{len(alerts)}개 예시 알림이 표시됩니다. 실제 보유 종목 입력 전에는 실전 판단으로 사용하지 않습니다."
        else:
            summary = f"{len(alerts)}개 리스크 알림을 추가 자금 투입 전 검토해야 합니다."

    return PortfolioRiskCockpitState(
        module_id="PortfolioRiskCockpit",
        status=status,
        title="Portfolio Risk Cockpit",
        summary=summary,
        data_points=metrics,
        explanation=(
            "비중 = 보유 종목 평가금액 / 전체 포트폴리오 평가금액",
            "변동성·낙폭 추정치는 포트폴리오 가치 이력이 있을 때만 계산합니다.",
            "알림은 매매 지시가 아니라 투자 전 점검 기준입니다.",
        ),
        risk_flags=tuple(alert.id for alert in alerts),
        stale_after_minutes=int(thresholds.stale_after_hours * 60),
        asset_allocation=asset_allocation,
        market_allocation=market_allocation,
        sector_allocation=sector_allocation,
        currency_allocation=currency_allocation,
        top_holdings=tuple(rows[:10]),
        top5_holdings=top5,
        risk_alerts=tuple(alerts),
    )


def portfolio_risk_cockpit_api_response(state: PortfolioRiskCockpitState) -> dict[str, Any]:
    payload = state.to_dict()
    payload["moduleId"] = payload.pop("module_id")
    payload["dataPoints"] = payload.pop("data_points")
    payload["assetAllocation"] = payload.pop("asset_allocation")
    payload["marketAllocation"] = payload.pop("market_allocation")
    payload["sectorAllocation"] = payload.pop("sector_allocation")
    payload["currencyAllocation"] = payload.pop("currency_allocation")
    payload["topHoldings"] = payload.pop("top_holdings")
    payload["top5Holdings"] = payload.pop("top5_holdings")
    payload["riskAlerts"] = payload.pop("risk_alerts")
    payload["staleAfterMinutes"] = payload.pop("stale_after_minutes")
    payload["apiPath"] = payload.pop("api_path")
    return payload
