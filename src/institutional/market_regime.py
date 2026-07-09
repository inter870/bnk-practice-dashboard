from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any
from zoneinfo import ZoneInfo

from .models import (
    DataPoint,
    DataSourceMeta,
    MacroIndicatorRow,
    MarketRegimeMacroRadarState,
    RecentMacroChange,
    SectorTailwindRow,
)


REGIME_LABELS = (
    "RISK_ON",
    "RISK_OFF",
    "EXPORT_UPCYCLE",
    "EXPORT_DOWNTURN",
    "RATE_PRESSURE",
    "FX_PRESSURE",
    "LIQUIDITY_SUPPORT",
    "STAGFLATION_RISK",
)

KST = ZoneInfo("Asia/Seoul")

REGIME_LABEL_KO = {
    "RISK_ON": "위험선호",
    "RISK_OFF": "위험회피",
    "EXPORT_UPCYCLE": "수출 개선",
    "EXPORT_DOWNTURN": "수출 둔화",
    "RATE_PRESSURE": "금리 부담",
    "FX_PRESSURE": "환율 부담",
    "환율_PRESSURE": "환율 부담",
    "LIQUIDITY_SUPPORT": "유동성 지원",
    "STAGFLATION_RISK": "스태그플레이션 위험",
    "mock_macro_included": "모의 지표 포함",
}


def normalize_regime_label_ko(label: str) -> str:
    return REGIME_LABEL_KO.get(str(label or "").strip(), str(label or "").strip())


MOCK_MACRO_INPUTS: dict[str, dict[str, Any]] = {
    "korea_growth": {"label": "Korea growth proxy", "value": 2.1, "change": 0.1, "unit": "% YoY", "source": "Mock macro model"},
    "inflation": {"label": "Inflation proxy", "value": 2.4, "change": -0.1, "unit": "% YoY", "source": "Mock macro model"},
    "export_growth": {"label": "Export growth proxy", "value": 7.5, "change": 1.2, "unit": "% YoY", "source": "Mock macro model"},
    "semiconductor_export": {"label": "Semiconductor export proxy", "value": 15.0, "change": 2.0, "unit": "% YoY", "source": "Mock macro model"},
    "usd_krw": {"label": "USD/KRW", "value": 1370.0, "change": 0.2, "unit": "KRW per USD", "source": "Mock FX"},
    "korea_policy_rate": {"label": "Korea policy rate proxy", "value": 3.0, "change": 0.0, "unit": "%", "source": "Mock rates"},
    "korea_10y": {"label": "Korea 10Y rate proxy", "value": 3.2, "change": -0.03, "unit": "%", "source": "Mock rates"},
    "us_10y": {"label": "U.S. 10Y rate proxy", "value": 4.1, "change": 0.02, "unit": "%", "source": "Mock rates"},
    "us_real_yield": {"label": "U.S. real yield proxy", "value": 1.8, "change": 0.01, "unit": "%", "source": "Mock rates"},
    "vix": {"label": "Global risk proxy", "value": 16.0, "change": -0.4, "unit": "index", "source": "Mock risk proxy"},
}


def _now_iso(now: datetime | None = None) -> str:
    stamp = now or datetime.now(KST)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=KST)
    return stamp.astimezone(KST).isoformat(timespec="seconds")


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _get(item: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(item, dict) and name in item:
            return item.get(name)
        if hasattr(item, name):
            return getattr(item, name)
    return default


def _is_mock_source(source: Any) -> bool:
    text = str(source or "").strip().lower()
    return text.startswith("mock") or " mock " in f" {text} " or "모의" in text


def _is_mock_indicator(row: MacroIndicatorRow) -> bool:
    return _is_mock_source(row.meta.source)


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
    current = now or datetime.now(KST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=KST)
    if stamp is None:
        return False
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=current.tzinfo)
    if stamp > current:
        return False
    return (current - stamp).total_seconds() > stale_after_hours * 3600


def _meta(
    *,
    source: str,
    endpoint: str,
    as_of_date: str | None,
    fetched_at: str,
    unit: str,
    confidence: int,
    stale: bool,
    missing: bool = False,
    is_fallback: bool = False,
) -> DataSourceMeta:
    return DataSourceMeta(
        source=source,
        provider=source,
        source_url=None,
        as_of_date=as_of_date,
        available_at=as_of_date,
        fetched_at=fetched_at,
        frequency="macro",
        unit=unit,
        quality_score=confidence,
        is_fallback=is_fallback,
        stale_data_flag=stale,
        source_table_or_endpoint=endpoint,
        revised_at=None,
        confidence_score=confidence,
        missing_data_flag=missing,
        warnings=("mock input" if is_fallback and _is_mock_source(source) else "",) if is_fallback and _is_mock_source(source) else (),
        errors=(),
    )


def _indicator_from_input(key: str, payload: dict[str, Any], *, now: datetime | None, stale_after_hours: float) -> MacroIndicatorRow:
    fetched_at = _now_iso(now)
    value = _finite(payload.get("value"))
    change = _finite(payload.get("change"))
    asof = payload.get("as_of_date") or payload.get("asof") or (now or datetime.now()).date().isoformat()
    stale = _is_stale(asof, now=now, stale_after_hours=stale_after_hours) if asof else False
    is_fallback = bool(payload.get("is_fallback", False))
    confidence = int(_finite(payload.get("confidence_score", 70 if is_fallback else 84)) or 0)
    contribution = _indicator_contribution(key, value, change)
    score = int(round(_clamp(50.0 + contribution * 2.5, 0.0, 100.0)))
    signal = "missing" if value is None else "tailwind" if contribution > 2 else "headwind" if contribution < -2 else "neutral"
    meta = _meta(
        source=str(payload.get("source") or "Macro input"),
        endpoint=str(payload.get("endpoint") or f"macro:{key}"),
        as_of_date=_as_date_text(asof),
        fetched_at=fetched_at,
        unit=str(payload.get("unit") or "unknown"),
        confidence=confidence,
        stale=stale,
        missing=value is None,
        is_fallback=is_fallback,
    )
    return MacroIndicatorRow(
        key=key,
        label=str(payload.get("label") or key),
        value=value,
        change=change,
        unit=str(payload.get("unit") or "unknown"),
        score=score,
        contribution=contribution,
        signal=signal,  # type: ignore[arg-type]
        meta=meta,
    )


def _indicator_contribution(key: str, value: float | None, change: float | None) -> float:
    if value is None:
        return -2.0
    delta = change or 0.0
    if key == "korea_growth":
        return _clamp((value - 1.5) * 4.0 + delta * 2.0, -10.0, 10.0)
    if key == "inflation":
        return _clamp((2.5 - value) * 5.0 - max(delta, 0.0) * 3.0, -12.0, 8.0)
    if key == "export_growth":
        return _clamp(value / 20.0 * 14.0 + delta * 0.8, -12.0, 14.0)
    if key == "semiconductor_export":
        return _clamp(value / 25.0 * 12.0 + delta * 0.7, -12.0, 12.0)
    if key == "usd_krw":
        level_penalty = -5.0 if value >= 1450 else -2.5 if value >= 1380 else 2.0 if value <= 1300 else 0.0
        return _clamp(level_penalty - delta * 8.0, -14.0, 8.0)
    if key in {"korea_policy_rate", "korea_10y", "us_10y"}:
        level_penalty = -4.0 if value >= 4.0 else -2.0 if value >= 3.4 else 1.5 if value <= 2.5 else 0.0
        return _clamp(level_penalty - delta * 10.0, -10.0, 6.0)
    if key == "us_real_yield":
        return _clamp((1.0 - value) * 4.0 - delta * 8.0, -10.0, 6.0)
    if key == "vix":
        return _clamp((20.0 - value) * 0.8 - delta * 0.5, -12.0, 10.0)
    if key in {"kospi_momentum", "kosdaq_momentum"}:
        return _clamp(delta * 6.0, -10.0, 10.0)
    return 0.0


def _input_from_snapshot(key: str, snap: Any, label: str, unit: str, endpoint: str) -> dict[str, Any]:
    change = _finite(_get(snap, "change_pct"))
    previous_close = _finite(_get(snap, "prev_close", "previous_close"))
    if key in {"kospi_momentum", "kosdaq_momentum"} and previous_close is None:
        change = None
    return {
        "label": label,
        "value": _finite(_get(snap, "last_close")),
        "change": change,
        "unit": unit,
        "source": str(_get(snap, "source", default="market snapshot") or "market snapshot"),
        "endpoint": endpoint,
        "as_of_date": _get(snap, "asof"),
        "confidence_score": int(_finite(_get(snap, "quality_score", default=70)) or 70),
        "is_fallback": bool(_get(snap, "is_fallback", default=True)),
    }


def _build_inputs(
    snapshots: dict[str, Any] | None,
    macro_inputs: dict[str, dict[str, Any]] | None,
    *,
    allow_mock: bool,
) -> dict[str, dict[str, Any]]:
    inputs: dict[str, dict[str, Any]] = {}
    if allow_mock:
        inputs.update({key: {**value, "is_fallback": True} for key, value in MOCK_MACRO_INPUTS.items()})
    if macro_inputs:
        inputs.update(macro_inputs)

    snapshot_map = snapshots or {}
    snapshot_specs = {
        "usd_krw": ("USD/KRW", "USD/KRW", "KRW per USD", "market_snapshot:USD/KRW"),
        "korea_10y": ("KR 3Y", "Korea rate proxy", "%", "market_snapshot:KR 3Y"),
        "us_10y": ("US 10Y", "U.S. 10Y rate proxy", "%", "market_snapshot:US 10Y"),
        "kospi_momentum": ("KOSPI", "KOSPI momentum", "index_level", "market_snapshot:KOSPI"),
        "kosdaq_momentum": ("KOSDAQ", "KOSDAQ momentum", "index_level", "market_snapshot:KOSDAQ"),
        "vix": ("VIX", "Global risk proxy", "index", "market_snapshot:VIX"),
    }
    for input_key, (snapshot_key, label, unit, endpoint) in snapshot_specs.items():
        snap = snapshot_map.get(snapshot_key)
        if snap is not None:
            inputs[input_key] = _input_from_snapshot(input_key, snap, label, unit, endpoint)
    return inputs


def calculate_regime_labels(indicators: tuple[MacroIndicatorRow, ...]) -> tuple[str, ...]:
    values = {row.key: row.value for row in indicators}
    changes = {row.key: row.change for row in indicators}
    score = calculate_regime_score(indicators)
    labels: list[str] = ["RISK_ON" if score >= 50 else "RISK_OFF"]
    export_growth = values.get("export_growth")
    semi_export = values.get("semiconductor_export")
    if (export_growth is not None and export_growth >= 5.0) or (semi_export is not None and semi_export >= 8.0):
        labels.append("EXPORT_UPCYCLE")
    if (export_growth is not None and export_growth <= -3.0) or (semi_export is not None and semi_export <= -5.0):
        labels.append("EXPORT_DOWNTURN")
    if any((values.get(key) or 0.0) >= threshold or (changes.get(key) or 0.0) > 0.08 for key, threshold in [("korea_10y", 3.5), ("us_10y", 4.3), ("us_real_yield", 2.0)]):
        labels.append("RATE_PRESSURE")
    if (values.get("usd_krw") or 0.0) >= 1380.0 or (changes.get("usd_krw") or 0.0) >= 0.5:
        labels.append("FX_PRESSURE")
    if (values.get("korea_policy_rate") or 99.0) <= 2.75 or (changes.get("korea_policy_rate") or 0.0) < 0:
        labels.append("LIQUIDITY_SUPPORT")
    if (values.get("inflation") or 0.0) >= 3.2 and (values.get("korea_growth") or 99.0) <= 1.2:
        labels.append("STAGFLATION_RISK")
    return tuple(dict.fromkeys(labels))


def calculate_regime_score(indicators: tuple[MacroIndicatorRow, ...]) -> int:
    contribution = sum(row.contribution for row in indicators)
    confidence_penalty = sum(1 for row in indicators if row.meta.missing_data_flag) * 1.5
    score = 50.0 + contribution - confidence_penalty
    return int(round(_clamp(score, 0.0, 100.0)))


def _sector_tailwinds(indicators: tuple[MacroIndicatorRow, ...], meta: DataSourceMeta) -> tuple[SectorTailwindRow, ...]:
    labels = set(calculate_regime_labels(indicators))
    values = {row.key: row.value for row in indicators}
    export_good = "EXPORT_UPCYCLE" in labels
    fx_pressure = "FX_PRESSURE" in labels
    rate_pressure = "RATE_PRESSURE" in labels
    risk_on = "RISK_ON" in labels
    semi_good = (values.get("semiconductor_export") or 0.0) >= 8.0

    sector_defs = [
        ("Semiconductors", 50 + (18 if semi_good else -8) + (10 if export_good else -6) - (6 if rate_pressure else 0), ["semi exports", "export cycle"], ["rates"] if rate_pressure else []),
        ("Autos / Exporters", 50 + (12 if export_good else -8) + (5 if fx_pressure else 0), ["exports", "weak KRW"] if fx_pressure else ["exports"], []),
        ("Internet / Growth", 50 + (10 if risk_on else -8) - (14 if rate_pressure else 0) - (5 if fx_pressure else 0), ["risk appetite"] if risk_on else [], ["rates"] if rate_pressure else []),
        ("Banks / Insurance", 50 + (8 if rate_pressure else 0) - (6 if not risk_on else 0), ["rate level"] if rate_pressure else [], ["risk-off"] if not risk_on else []),
        ("Defensives", 50 + (8 if not risk_on else -3) + (4 if fx_pressure else 0), ["risk buffer"] if not risk_on else [], []),
        ("Materials / Industrials", 50 + (12 if export_good else -6) - (6 if fx_pressure else 0), ["export demand"] if export_good else [], ["FX pressure"] if fx_pressure else []),
    ]
    rows: list[SectorTailwindRow] = []
    for sector, raw_score, positives, negatives in sector_defs:
        score = int(round(_clamp(raw_score, 0.0, 100.0)))
        label = "tailwind" if score >= 60 else "headwind" if score <= 44 else "neutral"
        rows.append(
            SectorTailwindRow(
                sector=sector,
                tailwind_score=score,
                label=label,  # type: ignore[arg-type]
                positive_drivers=tuple(positives),
                negative_drivers=tuple(negatives),
                meta=meta,
            )
        )
    return tuple(sorted(rows, key=lambda item: item.tailwind_score, reverse=True))


def _recent_changes(indicators: tuple[MacroIndicatorRow, ...]) -> tuple[RecentMacroChange, ...]:
    rows: list[RecentMacroChange] = []
    for row in indicators:
        if row.change is None:
            continue
        if abs(row.change) < 0.01:
            continue
        impact = "positive" if row.contribution > 1.5 else "negative" if row.contribution < -1.5 else "neutral"
        change_text = f"{row.change:+.2f} {row.unit}"
        rows.append(RecentMacroChange(row.key, row.label, change_text, impact, row.meta))
    rows.sort(key=lambda item: abs(_finite(item.change_text.split()[0]) or 0.0), reverse=True)
    return tuple(rows[:6])


def _display_score(value: int) -> str:
    return f"{value}/100"


def build_market_regime_macro_radar(
    *,
    snapshots: dict[str, Any] | None = None,
    macro_inputs: dict[str, dict[str, Any]] | None = None,
    now: datetime | None = None,
    stale_after_hours: float = 24.0,
    allow_mock: bool = True,
) -> MarketRegimeMacroRadarState:
    inputs = _build_inputs(snapshots, macro_inputs, allow_mock=allow_mock)
    if not inputs:
        fetched_at = _now_iso(now)
        meta = _meta(
            source="Not connected",
            endpoint="/api/dashboard/market-regime",
            as_of_date=None,
            fetched_at=fetched_at,
            unit="metadata",
            confidence=0,
            stale=False,
            missing=True,
            is_fallback=True,
        )
        return MarketRegimeMacroRadarState(
            module_id="MarketRegimeMacroRadar",
            status="empty",
            title="Market Regime & Macro Radar",
            summary="No macro or market source is available.",
            data_points=(DataPoint("regime_score", "Regime Score", None, meta, "N/A"),),
            explanation=("Connect market and macro sources or enable mock inputs to calculate a regime context.",),
            risk_flags=("missing_macro_data",),
            stale_after_minutes=int(stale_after_hours * 60),
            current_regime_label="RISK_OFF",
            regime_labels=("RISK_OFF",),
            regime_score=0,
            macro_heatmap=(),
            sector_tailwinds=(),
            recent_changes=(),
            latest_source_at=None,
        )

    ordered_keys = (
        "korea_growth",
        "inflation",
        "export_growth",
        "semiconductor_export",
        "usd_krw",
        "korea_policy_rate",
        "korea_10y",
        "us_10y",
        "us_real_yield",
        "vix",
        "kospi_momentum",
        "kosdaq_momentum",
    )
    indicators = tuple(
        _indicator_from_input(key, inputs[key], now=now, stale_after_hours=stale_after_hours)
        for key in ordered_keys
        if key in inputs
    )
    score = calculate_regime_score(indicators)
    labels = calculate_regime_labels(indicators)
    primary = labels[0] if labels else ("RISK_ON" if score >= 50 else "RISK_OFF")
    stale = any(row.meta.stale_data_flag for row in indicators)
    missing = any(row.meta.missing_data_flag for row in indicators)
    latest_source_at = max((row.meta.fetched_at or "" for row in indicators), default=None) or None
    confidence_inputs = [row for row in indicators if not _is_mock_indicator(row) and row.meta.confidence_score is not None]
    avg_confidence = (
        int(round(sum(row.meta.confidence_score or 0 for row in confidence_inputs) / len(confidence_inputs)))
        if confidence_inputs
        else 0
    )
    mock_included = any(_is_mock_indicator(row) for row in indicators)
    meta = _meta(
        source="Market Regime Macro Radar",
        endpoint="/api/dashboard/market-regime",
        as_of_date=(now or datetime.now()).date().isoformat(),
        fetched_at=_now_iso(now),
        unit="score",
        confidence=avg_confidence,
        stale=stale,
        missing=missing,
        is_fallback=mock_included,
    )
    data_points = (
        DataPoint("regime_score", "Regime Score", score, meta, _display_score(score)),
        DataPoint("current_regime_label", "Current Regime", primary, meta, primary),
        DataPoint("macro_indicator_count", "Macro Indicators", len(indicators), meta, str(len(indicators))),
        DataPoint("source_freshness", "Source Freshness", "stale" if stale else "fresh", meta, "stale" if stale else "fresh"),
    )
    status = "stale" if stale else "ready"
    summary = f"{normalize_regime_label_ko(primary)} 점수 {score}/100. 핵심 라벨: {', '.join(normalize_regime_label_ko(label) for label in labels)}."
    risk_flags = tuple(label for label in labels if label in {"RISK_OFF", "RATE_PRESSURE", "FX_PRESSURE", "STAGFLATION_RISK"})
    if mock_included:
        risk_flags = (*risk_flags, "mock_macro_included")
    return MarketRegimeMacroRadarState(
        module_id="MarketRegimeMacroRadar",
        status=status,
        title="Market Regime & Macro Radar",
        summary=summary,
        data_points=data_points,
        explanation=(
            "This module is market context only and does not recommend individual stocks.",
            "Positive export and semiconductor signals support KOSPI cyclicals; rate and FX pressure reduce risk appetite.",
            "Future alpha ranking can consume the regime score as a context variable.",
        ),
        risk_flags=risk_flags,
        stale_after_minutes=int(stale_after_hours * 60),
        current_regime_label=primary,
        regime_labels=labels,
        regime_score=score,
        macro_heatmap=indicators,
        sector_tailwinds=_sector_tailwinds(indicators, meta),
        recent_changes=_recent_changes(indicators),
        latest_source_at=latest_source_at,
    )


def market_regime_macro_radar_api_response(state: MarketRegimeMacroRadarState) -> dict[str, Any]:
    payload = state.to_dict()
    payload["moduleId"] = payload.pop("module_id")
    payload["dataPoints"] = payload.pop("data_points")
    payload["currentRegimeLabel"] = payload.pop("current_regime_label")
    payload["regimeLabels"] = payload.pop("regime_labels")
    payload["regimeScore"] = payload.pop("regime_score")
    payload["macroHeatmap"] = payload.pop("macro_heatmap")
    payload["sectorTailwinds"] = payload.pop("sector_tailwinds")
    payload["recentChanges"] = payload.pop("recent_changes")
    payload["latestSourceAt"] = payload.pop("latest_source_at")
    payload["staleAfterMinutes"] = payload.pop("stale_after_minutes")
    payload["apiPath"] = payload.pop("api_path")
    return payload
