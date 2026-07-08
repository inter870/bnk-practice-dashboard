from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Iterable

from .models import DataPoint, DataSourceMeta, FXRatesImpactRow, FXRatesIndicatorRow, KRWRatesFXDashboardState


MOCK_KRW_RATES_FX_INPUTS: dict[str, dict[str, Any]] = {
    "usd_krw": {"label": "USD/KRW", "value": 1370.0, "change": 0.2, "unit": "KRW per USD", "source": "Mock FX"},
    "eur_krw": {"label": "EUR/KRW", "value": 1490.0, "change": 0.1, "unit": "KRW per EUR", "source": "Mock FX"},
    "jpy_krw": {"label": "JPY/KRW", "value": 9.2, "change": -0.1, "unit": "KRW per JPY", "source": "Mock FX"},
    "korea_base_rate": {"label": "Korea base rate", "value": 3.0, "change": 0.0, "unit": "%", "source": "Mock rates"},
    "korea_yield": {"label": "Korea 3Y/10Y yield", "value": 3.15, "change": -0.03, "unit": "%", "source": "Mock rates"},
    "us_2y": {"label": "U.S. 2Y yield", "value": 3.85, "change": 0.01, "unit": "%", "source": "Mock rates"},
    "us_10y": {"label": "U.S. 10Y yield", "value": 4.10, "change": 0.02, "unit": "%", "source": "Mock rates"},
    "us_10y_real": {"label": "U.S. 10Y real yield", "value": 1.80, "change": 0.01, "unit": "%", "source": "Mock rates"},
}


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


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _get(item: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(item, dict) and name in item:
            return item.get(name)
        if hasattr(item, name):
            return getattr(item, name)
    return default


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
        frequency="market",
        unit=unit,
        quality_score=confidence,
        is_fallback=is_fallback,
        stale_data_flag=stale,
        source_table_or_endpoint=endpoint,
        revised_at=None,
        confidence_score=confidence,
        missing_data_flag=missing,
        warnings=("mock input" if is_fallback else "",) if is_fallback else (),
        errors=(),
    )


def calculate_fx_shock(usd_krw: float | None, change_pct: float | None = None) -> tuple[int, str]:
    if usd_krw is None:
        return 50, "NEUTRAL"
    delta = change_pct or 0.0
    score = 50.0
    if usd_krw >= 1450:
        score += 25
    elif usd_krw >= 1400:
        score += 18
    elif usd_krw >= 1360:
        score += 10
    elif usd_krw <= 1220:
        score -= 18
    elif usd_krw <= 1280:
        score -= 10

    if delta >= 1.0:
        score += 20
    elif delta >= 0.5:
        score += 12
    elif delta <= -1.0:
        score -= 12
    elif delta <= -0.5:
        score -= 6

    score_int = int(round(_clamp(score, 0.0, 100.0)))
    if score_int >= 75:
        return score_int, "HIGH_FX_PRESSURE"
    if score_int >= 60:
        return score_int, "ELEVATED_FX_PRESSURE"
    if score_int <= 35:
        return score_int, "FX_SUPPORTIVE"
    return score_int, "NEUTRAL"


def calculate_rate_shock(
    *,
    korea_yield: float | None = None,
    korea_yield_change: float | None = None,
    us_2y: float | None = None,
    us_2y_change: float | None = None,
    us_10y: float | None = None,
    us_10y_change: float | None = None,
    us_10y_real: float | None = None,
    us_10y_real_change: float | None = None,
) -> tuple[int, str]:
    score = 50.0
    observed = False
    for value, change, high, medium in [
        (korea_yield, korea_yield_change, 3.8, 3.3),
        (us_2y, us_2y_change, 4.8, 4.2),
        (us_10y, us_10y_change, 4.6, 4.0),
        (us_10y_real, us_10y_real_change, 2.1, 1.6),
    ]:
        if value is None:
            continue
        observed = True
        if value >= high:
            score += 9
        elif value >= medium:
            score += 5
        elif value <= medium - 1.0:
            score -= 4
        delta = change or 0.0
        if delta >= 0.12:
            score += 7
        elif delta >= 0.05:
            score += 4
        elif delta <= -0.12:
            score -= 6
        elif delta <= -0.05:
            score -= 3
    if not observed:
        return 50, "NEUTRAL"
    score_int = int(round(_clamp(score, 0.0, 100.0)))
    if score_int >= 75:
        return score_int, "HIGH_RATE_PRESSURE"
    if score_int >= 60:
        return score_int, "ELEVATED_RATE_PRESSURE"
    if score_int <= 35:
        return score_int, "RATE_SUPPORTIVE"
    return score_int, "NEUTRAL"


def _input_from_snapshot(key: str, snap: Any, label: str, unit: str, endpoint: str) -> dict[str, Any]:
    return {
        "label": label,
        "value": _finite(_get(snap, "last_close")),
        "change": _finite(_get(snap, "change_pct")),
        "unit": unit,
        "source": str(_get(snap, "source", default="market snapshot") or "market snapshot"),
        "endpoint": endpoint,
        "as_of_date": _get(snap, "asof"),
        "confidence_score": int(_finite(_get(snap, "quality_score", default=70)) or 70),
        "is_fallback": bool(_get(snap, "is_fallback", default=True)),
    }


def _build_inputs(
    snapshots: dict[str, Any] | None,
    fx_rates_inputs: dict[str, dict[str, Any]] | None,
    *,
    allow_mock: bool,
) -> dict[str, dict[str, Any]]:
    inputs: dict[str, dict[str, Any]] = {}
    if allow_mock:
        inputs.update({key: {**value, "is_fallback": True} for key, value in MOCK_KRW_RATES_FX_INPUTS.items()})
    if fx_rates_inputs:
        inputs.update(fx_rates_inputs)
    snapshot_map = snapshots or {}
    snapshot_specs = {
        "usd_krw": ("USD/KRW", "USD/KRW", "KRW per USD", "market_snapshot:USD/KRW"),
        "eur_krw": ("EUR/KRW", "EUR/KRW", "KRW per EUR", "market_snapshot:EUR/KRW"),
        "jpy_krw": ("JPY/KRW", "JPY/KRW", "KRW per JPY", "market_snapshot:JPY/KRW"),
        "korea_yield": ("KR 3Y", "Korea 3Y/10Y yield", "%", "market_snapshot:KR 3Y"),
        "us_2y": ("US 2Y", "U.S. 2Y yield", "%", "market_snapshot:US 2Y"),
        "us_10y": ("US 10Y", "U.S. 10Y yield", "%", "market_snapshot:US 10Y"),
        "us_10y_real": ("US 10Y REAL", "U.S. 10Y real yield", "%", "market_snapshot:US 10Y REAL"),
    }
    for input_key, (snapshot_key, label, unit, endpoint) in snapshot_specs.items():
        snap = snapshot_map.get(snapshot_key)
        if snap is not None:
            inputs[input_key] = _input_from_snapshot(input_key, snap, label, unit, endpoint)
    return inputs


def _indicator_pressure(key: str, value: float | None, change: float | None) -> int:
    if value is None:
        return 50
    if key in {"usd_krw", "eur_krw", "jpy_krw"}:
        if key == "usd_krw":
            return calculate_fx_shock(value, change)[0]
        score = 50.0 + (change or 0.0) * 8.0
        return int(round(_clamp(score, 0.0, 100.0)))
    if key in {"korea_base_rate", "korea_yield", "us_2y", "us_10y", "us_10y_real"}:
        return calculate_rate_shock(
            korea_yield=value if key in {"korea_base_rate", "korea_yield"} else None,
            korea_yield_change=change if key in {"korea_base_rate", "korea_yield"} else None,
            us_2y=value if key == "us_2y" else None,
            us_2y_change=change if key == "us_2y" else None,
            us_10y=value if key == "us_10y" else None,
            us_10y_change=change if key == "us_10y" else None,
            us_10y_real=value if key == "us_10y_real" else None,
            us_10y_real_change=change if key == "us_10y_real" else None,
        )[0]
    return 50


def _indicator_from_input(key: str, payload: dict[str, Any], *, now: datetime | None, stale_after_hours: float) -> FXRatesIndicatorRow:
    fetched_at = _now_iso(now)
    value = _finite(payload.get("value"))
    change = _finite(payload.get("change"))
    asof = payload.get("as_of_date") or payload.get("asof") or (now or datetime.now()).date().isoformat()
    stale = _is_stale(asof, now=now, stale_after_hours=stale_after_hours) if asof else False
    is_fallback = bool(payload.get("is_fallback", False))
    confidence = int(_finite(payload.get("confidence_score", 70 if is_fallback else 84)) or 0)
    pressure = _indicator_pressure(key, value, change)
    signal = "missing" if value is None else "pressure" if pressure >= 60 else "supportive" if pressure <= 35 else "neutral"
    meta = _meta(
        source=str(payload.get("source") or "FX/rates input"),
        endpoint=str(payload.get("endpoint") or f"krw_rates_fx:{key}"),
        as_of_date=_as_date_text(asof),
        fetched_at=fetched_at,
        unit=str(payload.get("unit") or "unknown"),
        confidence=confidence,
        stale=stale,
        missing=value is None,
        is_fallback=is_fallback,
    )
    return FXRatesIndicatorRow(
        key=key,
        label=str(payload.get("label") or key),
        value=value,
        change=change,
        unit=str(payload.get("unit") or "unknown"),
        pressure_score=pressure,
        signal=signal,  # type: ignore[arg-type]
        meta=meta,
    )


def _currency_exposure(holdings: Iterable[Any] | None) -> dict[str, float]:
    exposures: dict[str, float] = {}
    for item in holdings or []:
        currency = str(_get(item, "currency", default="KRW") or "KRW").upper()
        quantity = _finite(_get(item, "quantity", "qty")) or 0.0
        price = _finite(_get(item, "current_price", "currentPrice", "price")) or 0.0
        exposures[currency] = exposures.get(currency, 0.0) + quantity * price
    return exposures


def _portfolio_krw_impact(holdings: Iterable[Any] | None, usd_change_pct: float | None) -> float | None:
    if usd_change_pct is None:
        return None
    exposures = _currency_exposure(holdings)
    total = sum(exposures.values())
    if total <= 0:
        return None
    usd_weight = exposures.get("USD", 0.0) / total
    return usd_weight * usd_change_pct / 100.0


def _impact_rows(
    *,
    fx_score: int,
    rate_score: int,
    usd_change_pct: float | None,
    portfolio_impact: float | None,
    meta: DataSourceMeta,
) -> tuple[FXRatesImpactRow, ...]:
    krw_weak = fx_score >= 60
    rate_pressure = rate_score >= 60
    rows = [
        FXRatesImpactRow(
            "KRW weakness impact",
            "Exporters" if krw_weak else "Domestic demand / importers",
            "Import-cost sensitive sectors" if krw_weak else "Export translation tailwind",
            "A weaker KRW may support export revenue translation but can pressure foreign outflows and input costs.",
            fx_score,
            meta,
        ),
        FXRatesImpactRow(
            "USD asset translation",
            "USD assets" if (usd_change_pct or 0.0) > 0 else "KRW assets",
            "Unhedged KRW-only portfolios" if (usd_change_pct or 0.0) > 0 else "USD assets after KRW rebound",
            "Estimated portfolio KRW translation impact is N/A without non-KRW holdings." if portfolio_impact is None else f"Estimated KRW translation impact: {portfolio_impact * 100:+.2f}%.",
            fx_score,
            meta,
        ),
        FXRatesImpactRow(
            "Exporter tailwind/headwind",
            "Autos / semiconductors / exporters" if krw_weak else "Domestic stocks",
            "Domestic cost-heavy names" if krw_weak else "Exporters losing FX tailwind",
            "FX is a context input only; revenue mix, hedging, and input costs must be checked separately.",
            fx_score,
            meta,
        ),
        FXRatesImpactRow(
            "Growth stock rate pressure",
            "Value / cash-flow visibility" if rate_pressure else "Long-duration growth",
            "Long-duration growth" if rate_pressure else "Banks if curve compresses",
            "Higher discount rates can pressure valuation multiples for growth stocks.",
            rate_score,
            meta,
        ),
        FXRatesImpactRow(
            "Bank / insurance sensitivity",
            "Banks / insurers" if rate_pressure else "Borrowers / duration assets",
            "Highly leveraged borrowers" if rate_pressure else "Net-interest-margin beneficiaries",
            "Rate level can help financial margins, but curve shape and credit risk decide the final effect.",
            rate_score,
            meta,
        ),
    ]
    return tuple(rows)


def build_krw_rates_fx_dashboard(
    *,
    snapshots: dict[str, Any] | None = None,
    holdings: Iterable[Any] | None = None,
    fx_rates_inputs: dict[str, dict[str, Any]] | None = None,
    now: datetime | None = None,
    stale_after_hours: float = 24.0,
    allow_mock: bool = True,
) -> KRWRatesFXDashboardState:
    inputs = _build_inputs(snapshots, fx_rates_inputs, allow_mock=allow_mock)
    if not inputs:
        fetched_at = _now_iso(now)
        meta = _meta(
            source="Not connected",
            endpoint="/api/dashboard/krw-rates-fx",
            as_of_date=None,
            fetched_at=fetched_at,
            unit="metadata",
            confidence=0,
            stale=True,
            missing=True,
            is_fallback=True,
        )
        return KRWRatesFXDashboardState(
            module_id="KRWRatesFXDashboard",
            status="empty",
            title="KRW / Rates / FX Dashboard",
            summary="No KRW, rates, or FX source is available.",
            data_points=(DataPoint("fx_shock_score", "FX Shock", None, meta, "N/A"),),
            explanation=("Connect FX/rates sources or enable mock inputs to calculate pressure indicators.",),
            risk_flags=("missing_fx_rates_data",),
            stale_after_minutes=int(stale_after_hours * 60),
        )

    ordered_keys = (
        "usd_krw",
        "eur_krw",
        "jpy_krw",
        "korea_base_rate",
        "korea_yield",
        "us_2y",
        "us_10y",
        "us_10y_real",
    )
    indicators = tuple(
        _indicator_from_input(key, inputs[key], now=now, stale_after_hours=stale_after_hours)
        for key in ordered_keys
        if key in inputs
    )
    by_key = {row.key: row for row in indicators}
    usd = by_key.get("usd_krw")
    korea_yield = by_key.get("korea_yield")
    us2 = by_key.get("us_2y")
    us10 = by_key.get("us_10y")
    real10 = by_key.get("us_10y_real")
    fx_score, fx_label = calculate_fx_shock(usd.value if usd else None, usd.change if usd else None)
    rate_score, rate_label = calculate_rate_shock(
        korea_yield=korea_yield.value if korea_yield else None,
        korea_yield_change=korea_yield.change if korea_yield else None,
        us_2y=us2.value if us2 else None,
        us_2y_change=us2.change if us2 else None,
        us_10y=us10.value if us10 else None,
        us_10y_change=us10.change if us10 else None,
        us_10y_real=real10.value if real10 else None,
        us_10y_real_change=real10.change if real10 else None,
    )
    slope = None if us10 is None or us2 is None or us10.value is None or us2.value is None else us10.value - us2.value
    portfolio_impact = _portfolio_krw_impact(holdings, usd.change if usd else None)
    stale = any(row.meta.stale_data_flag for row in indicators)
    missing = any(row.meta.missing_data_flag for row in indicators)
    avg_confidence = int(round(sum((row.meta.confidence_score or row.meta.quality_score) for row in indicators) / len(indicators))) if indicators else 0
    meta = _meta(
        source="KRW Rates FX Dashboard",
        endpoint="/api/dashboard/krw-rates-fx",
        as_of_date=(now or datetime.now()).date().isoformat(),
        fetched_at=_now_iso(now),
        unit="score",
        confidence=avg_confidence,
        stale=stale,
        missing=missing,
        is_fallback=any(row.meta.is_fallback for row in indicators),
    )
    data_points = (
        DataPoint("fx_shock_score", "FX Shock Indicator", fx_score, meta, f"{fx_score}/100"),
        DataPoint("fx_shock_label", "FX Shock Label", fx_label, meta, fx_label),
        DataPoint("rate_shock_score", "Rate Shock Indicator", rate_score, meta, f"{rate_score}/100"),
        DataPoint("rate_shock_label", "Rate Shock Label", rate_label, meta, rate_label),
        DataPoint("yield_curve_slope", "Yield Curve Slope", slope, meta, "N/A" if slope is None else f"{slope:+.2f}%p"),
        DataPoint("portfolio_krw_impact_pct", "Portfolio KRW Impact", portfolio_impact, meta, "N/A" if portfolio_impact is None else f"{portfolio_impact * 100:+.2f}%"),
    )
    pressure_flags = []
    if fx_score >= 60:
        pressure_flags.append(fx_label)
    if rate_score >= 60:
        pressure_flags.append(rate_label)
    if slope is not None and slope < 0:
        pressure_flags.append("INVERTED_US_CURVE")
    status = "stale" if stale else "ready"
    summary = f"FX {fx_label} ({fx_score}/100), rates {rate_label} ({rate_score}/100)."
    return KRWRatesFXDashboardState(
        module_id="KRWRatesFXDashboard",
        status=status,
        title="KRW / Rates / FX Dashboard",
        summary=summary,
        data_points=data_points,
        explanation=(
            "Higher USD/KRW can help exporters but may hurt KRW risk appetite and import-cost-sensitive stocks.",
            "Higher yields can pressure growth valuation multiples while supporting some bank and insurance margins.",
            "Portfolio KRW impact is estimated only when non-KRW holdings are present.",
        ),
        risk_flags=tuple(pressure_flags),
        stale_after_minutes=int(stale_after_hours * 60),
        fx_shock_score=fx_score,
        fx_shock_label=fx_label,
        rate_shock_score=rate_score,
        rate_shock_label=rate_label,
        yield_curve_slope=slope,
        portfolio_krw_impact_pct=portfolio_impact,
        indicators=indicators,
        impact_rows=_impact_rows(
            fx_score=fx_score,
            rate_score=rate_score,
            usd_change_pct=usd.change if usd else None,
            portfolio_impact=portfolio_impact,
            meta=meta,
        ),
        latest_source_at=max((row.meta.fetched_at or "" for row in indicators), default=None) or None,
    )


def krw_rates_fx_dashboard_api_response(state: KRWRatesFXDashboardState) -> dict[str, Any]:
    payload = state.to_dict()
    payload["moduleId"] = payload.pop("module_id")
    payload["dataPoints"] = payload.pop("data_points")
    payload["fxShockScore"] = payload.pop("fx_shock_score")
    payload["fxShockLabel"] = payload.pop("fx_shock_label")
    payload["rateShockScore"] = payload.pop("rate_shock_score")
    payload["rateShockLabel"] = payload.pop("rate_shock_label")
    payload["yieldCurveSlope"] = payload.pop("yield_curve_slope")
    payload["portfolioKrwImpactPct"] = payload.pop("portfolio_krw_impact_pct")
    payload["impactRows"] = payload.pop("impact_rows")
    payload["latestSourceAt"] = payload.pop("latest_source_at")
    payload["staleAfterMinutes"] = payload.pop("stale_after_minutes")
    payload["apiPath"] = payload.pop("api_path")
    return payload
