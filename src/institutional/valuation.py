from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from statistics import median
from typing import Any, Iterable

from .models import DataPoint, DataSourceMeta, SectorValuationRow, ValuationMetricRow, ValuationRelativeCheapnessPanelState


MOCK_VALUATION_INPUTS: tuple[dict[str, Any], ...] = (
    {
        "code": "005930",
        "name": "Samsung Electronics",
        "sector": "Semiconductors",
        "per": 13.2,
        "forward_per": 10.8,
        "pbr": 1.18,
        "psr": 1.4,
        "ev_ebitda": 5.8,
        "dividend_yield": 0.021,
        "fcf_yield": 0.056,
        "quality_score": 78,
        "quality_trend": "improving",
        "history_per": [8.5, 10.2, 11.8, 13.0, 14.5, 16.8, 18.0, 20.5],
        "history_pbr": [0.9, 1.0, 1.1, 1.2, 1.4, 1.6, 1.8],
    },
    {
        "code": "000660",
        "name": "SK hynix",
        "sector": "Semiconductors",
        "per": 19.5,
        "forward_per": 8.9,
        "pbr": 1.65,
        "psr": 2.3,
        "ev_ebitda": 6.4,
        "dividend_yield": 0.009,
        "fcf_yield": 0.032,
        "quality_score": 74,
        "quality_trend": "improving",
        "history_per": [6.0, 8.0, 10.0, 12.0, 15.0, 18.0, 22.0, 28.0],
        "history_pbr": [0.8, 1.0, 1.2, 1.4, 1.7, 2.1, 2.5],
    },
    {
        "code": "034020",
        "name": "Doosan Enerbility",
        "sector": "Industrials",
        "per": 31.0,
        "forward_per": 24.0,
        "pbr": 2.3,
        "psr": 1.1,
        "ev_ebitda": 12.8,
        "dividend_yield": 0.0,
        "fcf_yield": -0.012,
        "quality_score": 49,
        "quality_trend": "deteriorating",
        "history_per": [12.0, 15.0, 18.0, 21.0, 26.0, 30.0, 36.0],
        "history_pbr": [0.8, 1.0, 1.2, 1.6, 2.0, 2.4, 3.0],
    },
    {
        "code": "035420",
        "name": "NAVER",
        "sector": "Internet / Growth",
        "per": 27.5,
        "forward_per": 22.0,
        "pbr": 1.35,
        "psr": 3.1,
        "ev_ebitda": 13.5,
        "dividend_yield": 0.004,
        "fcf_yield": 0.029,
        "quality_score": 70,
        "quality_trend": "stable",
        "history_per": [18.0, 22.0, 26.0, 32.0, 38.0, 45.0, 55.0],
        "history_pbr": [1.1, 1.4, 1.8, 2.2, 2.8, 3.5, 4.2],
    },
    {
        "code": "105560",
        "name": "KB Financial",
        "sector": "Banks / Insurance",
        "per": 5.8,
        "forward_per": 5.2,
        "pbr": 0.55,
        "psr": None,
        "ev_ebitda": None,
        "dividend_yield": 0.056,
        "fcf_yield": None,
        "quality_score": 67,
        "quality_trend": "stable",
        "history_per": [4.0, 4.8, 5.5, 6.2, 7.4, 8.0, 9.2],
        "history_pbr": [0.35, 0.42, 0.50, 0.60, 0.72, 0.85, 1.0],
    },
    {
        "code": "011200",
        "name": "HMM",
        "sector": "Industrials",
        "per": 4.8,
        "forward_per": 8.5,
        "pbr": 0.72,
        "psr": 0.7,
        "ev_ebitda": 4.1,
        "dividend_yield": 0.035,
        "fcf_yield": 0.08,
        "quality_score": 42,
        "quality_trend": "deteriorating",
        "history_per": [2.0, 3.0, 4.5, 6.0, 8.0, 12.0, 18.0],
        "history_pbr": [0.4, 0.6, 0.8, 1.1, 1.6, 2.2],
    },
)


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
        frequency="valuation",
        unit="multiple",
        quality_score=max(0, min(100, confidence)),
        is_fallback=is_fallback,
        stale_data_flag=stale,
        source_table_or_endpoint=endpoint,
        revised_at=None,
        confidence_score=max(0, min(100, confidence)),
        missing_data_flag=missing,
        warnings=("mock input" if is_fallback else "",) if is_fallback else (),
        errors=(),
    )


def _get(item: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(item, dict) and name in item:
            return item.get(name)
        if hasattr(item, name):
            return getattr(item, name)
    return default


def calculate_valuation_percentile(current_value: Any, historical_values: Iterable[Any] | None) -> float | None:
    current = _finite(current_value)
    clean = sorted(value for value in (_finite(item) for item in historical_values or []) if value is not None)
    if current is None or not clean:
        return None
    lower_or_equal = sum(1 for value in clean if value <= current)
    return _clamp(lower_or_equal / len(clean) * 100.0, 0.0, 100.0)


def calculate_sector_relative_ranking(items: Iterable[Any], metric: str = "per") -> list[dict[str, Any]]:
    rows = list(items or [])
    sector_values: dict[str, list[float]] = {}
    for item in rows:
        sector = str(_get(item, "sector", default="Unclassified") or "Unclassified")
        value = _finite(_get(item, metric))
        if value is not None and value > 0:
            sector_values.setdefault(sector, []).append(value)
    sector_medians = {sector: median(values) for sector, values in sector_values.items() if values}
    ranked: list[dict[str, Any]] = []
    for item in rows:
        sector = str(_get(item, "sector", default="Unclassified") or "Unclassified")
        value = _finite(_get(item, metric))
        base = sector_medians.get(sector)
        relative = None if value is None or not base else value / base
        ranked.append(
            {
                "code": str(_get(item, "code", "symbol", default="")),
                "sector": sector,
                "metric": metric,
                "value": value,
                "sector_median": base,
                "relative": relative,
            }
        )
    ranked.sort(key=lambda row: float("inf") if row["relative"] is None else row["relative"])
    for idx, row in enumerate(ranked, 1):
        row["rank"] = idx
    return ranked


def _interpretation(percentile: float | None, quality_score: int | None, quality_trend: str) -> tuple[str, str]:
    if percentile is None:
        return "missing", "Valuation data missing"
    cheap = percentile <= 35
    expensive = percentile >= 75
    quality = quality_score or 0
    trend = quality_trend.lower()
    if cheap and quality < 50:
        return "cheap", "Cheap but low quality"
    if cheap and trend == "improving":
        return "cheap", "Cheap and improving"
    if expensive and quality >= 70:
        return "expensive", "Expensive but high quality"
    if expensive and (trend == "deteriorating" or quality < 55):
        return "expensive", "Expensive and deteriorating"
    if cheap:
        return "cheap", "Cheap, quality check required"
    if expensive:
        return "expensive", "Expensive, growth durability required"
    return "fair", "Fair valuation"


def _build_rows(raw_inputs: Iterable[Any], *, now: datetime | None, stale_after_hours: float, fallback: bool) -> tuple[ValuationMetricRow, ...]:
    items = list(raw_inputs or [])
    per_rank = {row["code"]: row for row in calculate_sector_relative_ranking(items, "per")}
    pbr_rank = {row["code"]: row for row in calculate_sector_relative_ranking(items, "pbr")}
    rows: list[ValuationMetricRow] = []
    fetched_at = _now_iso(now)
    for item in items:
        code = str(_get(item, "code", "symbol", default=""))
        per = _finite(_get(item, "per"))
        pbr = _finite(_get(item, "pbr"))
        forward_per = _finite(_get(item, "forward_per", "forwardPer"))
        earnings_yield = None if per in (None, 0) else 1.0 / per
        percentile = calculate_valuation_percentile(per, _get(item, "history_per", "historyPer", default=[]))
        quality_score = int(_finite(_get(item, "quality_score", "qualityScore", default=0)) or 0)
        quality_trend = str(_get(item, "quality_trend", "qualityTrend", default="stable") or "stable")
        valuation_label, interpretation = _interpretation(percentile, quality_score, quality_trend)
        asof = _get(item, "as_of_date", "asof", default=(now or datetime.now()).date().isoformat())
        stale = _is_stale(asof, now=now, stale_after_hours=stale_after_hours)
        missing = per is None and pbr is None
        confidence = int(_finite(_get(item, "confidence_score", "confidenceScore", default=65 if fallback else 84)) or 0)
        meta = _meta(
            source=str(_get(item, "source", default="Mock KRX/OpenDART valuation") or "Mock KRX/OpenDART valuation"),
            endpoint=str(_get(item, "endpoint", default="planned:krx_opendart_valuation") or "planned:krx_opendart_valuation"),
            as_of_date=_as_date_text(asof),
            fetched_at=fetched_at,
            confidence=confidence,
            stale=stale,
            missing=missing,
            is_fallback=fallback or bool(_get(item, "is_fallback", "isFallback", default=False)),
        )
        rows.append(
            ValuationMetricRow(
                code=code,
                name=str(_get(item, "name", default=code) or code),
                sector=str(_get(item, "sector", default="Unclassified") or "Unclassified"),
                per=per,
                forward_per=forward_per,
                pbr=pbr,
                psr=_finite(_get(item, "psr")),
                ev_ebitda=_finite(_get(item, "ev_ebitda", "evEbitda")),
                dividend_yield=_finite(_get(item, "dividend_yield", "dividendYield")),
                fcf_yield=_finite(_get(item, "fcf_yield", "fcfYield")),
                earnings_yield=earnings_yield,
                sector_relative_per=_finite((per_rank.get(code) or {}).get("relative")),
                sector_relative_pbr=_finite((pbr_rank.get(code) or {}).get("relative")),
                historical_percentile=percentile,
                pbr_below_1=bool(pbr is not None and pbr < 1.0),
                quality_score=quality_score,
                quality_trend=quality_trend,
                valuation_label=valuation_label,  # type: ignore[arg-type]
                interpretation=interpretation,
                meta=meta,
            )
        )
    return tuple(rows)


def _sector_rows(rows: tuple[ValuationMetricRow, ...], meta: DataSourceMeta) -> tuple[SectorValuationRow, ...]:
    sectors = sorted({row.sector for row in rows})
    result: list[SectorValuationRow] = []
    for sector in sectors:
        group = [row for row in rows if row.sector == sector]
        per_values = [row.per for row in group if row.per is not None]
        pbr_values = [row.pbr for row in group if row.pbr is not None]
        percentiles = [row.historical_percentile for row in group if row.historical_percentile is not None]
        cheap_count = sum(1 for row in group if row.valuation_label == "cheap")
        expensive_count = sum(1 for row in group if row.valuation_label == "expensive")
        med_pct = median(percentiles) if percentiles else None
        signal = "missing"
        if med_pct is not None:
            signal = "cheap" if med_pct <= 35 else "expensive" if med_pct >= 75 else "mixed" if cheap_count and expensive_count else "fair"
        result.append(
            SectorValuationRow(
                sector=sector,
                average_per=sum(per_values) / len(per_values) if per_values else None,
                average_pbr=sum(pbr_values) / len(pbr_values) if pbr_values else None,
                median_percentile=med_pct,
                cheap_count=cheap_count,
                expensive_count=expensive_count,
                signal=signal,  # type: ignore[arg-type]
                meta=meta,
            )
        )
    return tuple(sorted(result, key=lambda row: 101.0 if row.median_percentile is None else row.median_percentile))


def build_valuation_relative_cheapness_panel(
    *,
    valuation_inputs: Iterable[Any] | None = None,
    now: datetime | None = None,
    stale_after_hours: float = 24.0 * 30,
    allow_mock: bool = True,
) -> ValuationRelativeCheapnessPanelState:
    raw_inputs = list(valuation_inputs or [])
    fallback = False
    if not raw_inputs and allow_mock:
        raw_inputs = [dict(item, is_fallback=True) for item in MOCK_VALUATION_INPUTS]
        fallback = True
    if not raw_inputs:
        fetched_at = _now_iso(now)
        meta = _meta(
            source="Not connected",
            endpoint="/api/dashboard/valuation",
            as_of_date=None,
            fetched_at=fetched_at,
            confidence=0,
            stale=True,
            missing=True,
            is_fallback=True,
        )
        return ValuationRelativeCheapnessPanelState(
            module_id="ValuationRelativeCheapnessPanel",
            status="empty",
            title="Valuation & Relative Cheapness Panel",
            summary="No valuation source is available.",
            data_points=(DataPoint("market_percentile", "Market Valuation Percentile", None, meta, "N/A"),),
            explanation=("Connect KRX/OpenDART valuation inputs or enable mock data to calculate valuation context.",),
            risk_flags=("missing_valuation_data",),
            stale_after_minutes=int(stale_after_hours * 60),
        )

    rows = _build_rows(raw_inputs, now=now, stale_after_hours=stale_after_hours, fallback=fallback)
    stale = any(row.meta.stale_data_flag for row in rows)
    missing = any(row.meta.missing_data_flag for row in rows)
    percentiles = [row.historical_percentile for row in rows if row.historical_percentile is not None]
    market_percentile = sum(percentiles) / len(percentiles) if percentiles else None
    cheap_rows = [row for row in rows if row.valuation_label == "cheap"]
    expensive_rows = [row for row in rows if row.valuation_label == "expensive"]
    avg_confidence = int(round(sum((row.meta.confidence_score or row.meta.quality_score) for row in rows) / len(rows))) if rows else 0
    meta = _meta(
        source="Valuation Relative Cheapness Panel",
        endpoint="/api/dashboard/valuation",
        as_of_date=(now or datetime.now()).date().isoformat(),
        fetched_at=_now_iso(now),
        confidence=avg_confidence,
        stale=stale,
        missing=missing,
        is_fallback=any(row.meta.is_fallback for row in rows),
    )
    candidates = tuple(
        sorted(
            [row for row in rows if row.valuation_label == "cheap" and (row.quality_score or 0) >= 60],
            key=lambda row: (row.historical_percentile if row.historical_percentile is not None else 101.0, -(row.quality_score or 0)),
        )[:5]
    )
    expensive_list = tuple(
        sorted(
            expensive_rows,
            key=lambda row: (-(row.historical_percentile or 0.0), -(row.sector_relative_per or 0.0)),
        )[:5]
    )
    percentile_table = tuple(sorted(rows, key=lambda row: 101.0 if row.historical_percentile is None else row.historical_percentile))
    data_points = (
        DataPoint("market_percentile", "Market Valuation Percentile", market_percentile, meta, "N/A" if market_percentile is None else f"{market_percentile:.1f}/100"),
        DataPoint("cheap_count", "Cheap Count", len(cheap_rows), meta, str(len(cheap_rows))),
        DataPoint("expensive_count", "Expensive Count", len(expensive_rows), meta, str(len(expensive_rows))),
        DataPoint("valuation_row_count", "Valuation Row Count", len(rows), meta, str(len(rows))),
    )
    status = "stale" if stale else "ready"
    summary = "Valuation context is ready for future alpha ranking. No buy/sell recommendation is generated."
    if fallback:
        summary = "Mock KRX/OpenDART valuation context is shown until real valuation adapters are connected."
    if missing:
        summary = "Some valuation fields are missing; percentile and relative rankings use available data only."
    return ValuationRelativeCheapnessPanelState(
        module_id="ValuationRelativeCheapnessPanel",
        status=status,
        title="Valuation & Relative Cheapness Panel",
        summary=summary,
        data_points=data_points,
        explanation=(
            "Historical percentile is lower when a valuation multiple is cheap versus its own history.",
            "Sector-relative PER/PBR compare each stock with the current sector median.",
            "Cheapness is not a recommendation; quality, trend, liquidity, and disclosure risk must be checked.",
        ),
        risk_flags=tuple(["stale_valuation_data"] if stale else []) + tuple(["missing_valuation_fields"] if missing else []),
        stale_after_minutes=int(stale_after_hours * 60),
        market_percentile=market_percentile,
        cheap_count=len(cheap_rows),
        expensive_count=len(expensive_rows),
        valuation_rows=rows,
        cheapest_quality_candidates=candidates,
        sector_heatmap=_sector_rows(rows, meta),
        percentile_table=percentile_table,
        expensive_list=expensive_list,
        latest_source_at=max((row.meta.fetched_at or "" for row in rows), default=None) or None,
    )


def valuation_relative_cheapness_api_response(state: ValuationRelativeCheapnessPanelState) -> dict[str, Any]:
    payload = state.to_dict()
    payload["moduleId"] = payload.pop("module_id")
    payload["dataPoints"] = payload.pop("data_points")
    payload["marketPercentile"] = payload.pop("market_percentile")
    payload["cheapCount"] = payload.pop("cheap_count")
    payload["expensiveCount"] = payload.pop("expensive_count")
    payload["valuationRows"] = payload.pop("valuation_rows")
    payload["cheapestQualityCandidates"] = payload.pop("cheapest_quality_candidates")
    payload["sectorHeatmap"] = payload.pop("sector_heatmap")
    payload["percentileTable"] = payload.pop("percentile_table")
    payload["expensiveList"] = payload.pop("expensive_list")
    payload["latestSourceAt"] = payload.pop("latest_source_at")
    payload["staleAfterMinutes"] = payload.pop("stale_after_minutes")
    payload["apiPath"] = payload.pop("api_path")
    return payload
