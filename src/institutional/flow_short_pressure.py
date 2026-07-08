from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite, sqrt
from statistics import mean
from typing import Any, Iterable

from .models import DataPoint, DataSourceMeta, SectorFlowHeatmapRow, SmartMoneyFlowRow, SmartMoneyFlowShortPressurePanelState


MOCK_FLOW_SHORT_INPUTS: tuple[dict[str, Any], ...] = (
    {
        "code": "000660",
        "name": "SK hynix",
        "sector": "Semiconductors",
        "foreign_net_buy_history": [42, 51, -8, 33, 58, 64, 71, 52, 83, 90, 77, 64, 85, 92, 101, 108, 118, 122, 135, 148],
        "institution_net_buy_history": [15, 22, 18, 25, 30, 35, 44, 41, 39, 48, 50, 56, 59, 62, 68, 71, 75, 78, 82, 86],
        "individual_net_buy_history": [-20, -25, -30, -18, -35, -42, -40, -47, -52, -58, -60, -65, -70, -74, -78, -83, -88, -90, -96, -100],
        "pension_net_buy": 128,
        "program_net_buy": 240,
        "foreign_ownership_change": 0.018,
        "short_sell_ratio": 0.045,
        "short_position_ratio": 0.032,
        "short_position_quantity": 6_800_000,
        "avg_daily_volume": 3_100_000,
        "trading_value_20d": 980_000_000_000,
        "turnover": 0.021,
        "volatility": 0.31,
        "as_of_date": "2026-07-08",
        "available_at": "2026-07-08T18:10:00+09:00",
    },
    {
        "code": "005930",
        "name": "Samsung Electronics",
        "sector": "Semiconductors",
        "foreign_net_buy_history": [18, -20, 12, 5, 24, 36, 20, 18, 42, 50, 49, 38, 31, 28, 55, 61, 64, 59, 72, 80],
        "institution_net_buy_history": [-8, 4, 6, 7, 10, 12, 8, 13, 16, 19, 18, 20, 24, 25, 29, 31, 34, 33, 35, 38],
        "individual_net_buy_history": [-10, 15, -8, -12, -18, -24, -20, -25, -30, -34, -38, -41, -43, -47, -55, -61, -65, -67, -70, -74],
        "pension_net_buy": 72,
        "program_net_buy": 165,
        "foreign_ownership_change": 0.009,
        "short_sell_ratio": 0.022,
        "short_position_ratio": 0.015,
        "short_position_quantity": 9_500_000,
        "avg_daily_volume": 14_000_000,
        "trading_value_20d": 1_250_000_000_000,
        "turnover": 0.006,
        "volatility": 0.21,
        "as_of_date": "2026-07-08",
        "available_at": "2026-07-08T18:10:00+09:00",
    },
    {
        "code": "034020",
        "name": "Doosan Enerbility",
        "sector": "Industrials",
        "foreign_net_buy_history": [55, 48, 40, 30, 18, 5, -8, -15, -24, -33, -42, -55, -60, -73, -80, -92, -105, -110, -125, -138],
        "institution_net_buy_history": [22, 18, 14, 8, 5, -3, -8, -14, -20, -23, -28, -36, -41, -44, -49, -55, -61, -65, -70, -74],
        "individual_net_buy_history": [-30, -20, -12, 4, 12, 18, 28, 36, 45, 55, 67, 80, 92, 105, 118, 130, 145, 158, 170, 188],
        "pension_net_buy": -35,
        "program_net_buy": -95,
        "foreign_ownership_change": -0.014,
        "short_sell_ratio": 0.102,
        "short_position_ratio": 0.075,
        "short_position_quantity": 12_500_000,
        "avg_daily_volume": 1_150_000,
        "trading_value_20d": 72_000_000_000,
        "turnover": 0.018,
        "volatility": 0.48,
        "as_of_date": "2026-07-08",
        "available_at": "2026-07-08T18:10:00+09:00",
    },
    {
        "code": "035420",
        "name": "NAVER",
        "sector": "Internet / Growth",
        "foreign_net_buy_history": [-12, -10, -8, -4, 3, 9, 12, 18, 22, 26, 30, 35, 39, 44, 50, 54, 60, 66, 72, 78],
        "institution_net_buy_history": [4, 5, 8, 9, 12, 14, 16, 17, 19, 20, 23, 25, 28, 30, 32, 35, 38, 42, 45, 48],
        "individual_net_buy_history": [8, 6, 2, -4, -10, -15, -20, -25, -29, -34, -38, -42, -47, -52, -58, -62, -68, -74, -80, -86],
        "pension_net_buy": 40,
        "program_net_buy": 90,
        "foreign_ownership_change": 0.012,
        "short_sell_ratio": 0.082,
        "short_position_ratio": 0.068,
        "short_position_quantity": 4_200_000,
        "avg_daily_volume": 620_000,
        "trading_value_20d": 118_000_000_000,
        "turnover": 0.010,
        "volatility": 0.39,
        "as_of_date": "2026-07-08",
        "available_at": "2026-07-08T18:10:00+09:00",
    },
    {
        "code": "105560",
        "name": "KB Financial",
        "sector": "Banks / Insurance",
        "foreign_net_buy_history": [10, 12, 15, 18, 22, 24, 28, 31, 34, 37, 39, 42, 45, 47, 50, 53, 55, 58, 60, 64],
        "institution_net_buy_history": [8, 10, 12, 14, 16, 18, 20, 23, 25, 28, 31, 33, 35, 38, 40, 43, 45, 48, 50, 52],
        "individual_net_buy_history": [-6, -10, -13, -15, -18, -20, -24, -28, -31, -35, -38, -42, -45, -48, -52, -56, -60, -62, -65, -70],
        "pension_net_buy": 82,
        "program_net_buy": 76,
        "foreign_ownership_change": 0.007,
        "short_sell_ratio": 0.018,
        "short_position_ratio": 0.011,
        "short_position_quantity": 1_900_000,
        "avg_daily_volume": 2_500_000,
        "trading_value_20d": 165_000_000_000,
        "turnover": 0.014,
        "volatility": 0.24,
        "as_of_date": "2026-07-08",
        "available_at": "2026-07-08T18:10:00+09:00",
    },
    {
        "code": "083450",
        "name": "GST",
        "sector": "Small-cap Tech",
        "foreign_net_buy_history": [6, 3, -2, -5, -8, -10, -14, -18, -20, -24, -28, -30, -34, -36, -40, -44, -48, -50, -55, -60],
        "institution_net_buy_history": [2, 1, 0, -2, -3, -5, -6, -8, -10, -12, -14, -16, -18, -20, -22, -24, -26, -28, -30, -32],
        "individual_net_buy_history": [4, 8, 12, 16, 21, 25, 29, 34, 38, 43, 48, 53, 58, 64, 70, 76, 82, 88, 95, 102],
        "pension_net_buy": -8,
        "program_net_buy": -15,
        "foreign_ownership_change": -0.018,
        "short_sell_ratio": 0.064,
        "short_position_ratio": 0.052,
        "short_position_quantity": 850_000,
        "avg_daily_volume": 95_000,
        "trading_value_20d": 4_200_000_000,
        "turnover": 0.005,
        "volatility": 0.57,
        "as_of_date": "2026-07-08",
        "available_at": "2026-07-08T18:10:00+09:00",
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
        stamp = value
    else:
        try:
            if hasattr(value, "to_pydatetime"):
                stamp = value.to_pydatetime()
            else:
                stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


def _as_date_text(value: Any) -> str | None:
    stamp = _as_datetime(value)
    if stamp is not None:
        return stamp.date().isoformat()
    if value:
        return str(value)[:10]
    return None


def _is_stale(asof: Any, *, now: datetime | None, stale_after_hours: float) -> bool:
    stamp = _as_datetime(asof)
    if stamp is None:
        return True
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return (current - stamp).total_seconds() > stale_after_hours * 3600


def _series(values: Any) -> list[float]:
    if values is None:
        return []
    result: list[float] = []
    for value in values:
        number = _finite(value)
        if number is not None:
            result.append(number)
    return result


def _sum_last(values: list[float], n: int) -> float | None:
    if not values:
        return None
    return sum(values[-n:])


def _meta(
    *,
    source: str,
    endpoint: str,
    as_of_date: str | None,
    available_at: str | None,
    fetched_at: str | None,
    confidence: int,
    stale: bool,
    missing: bool,
    is_fallback: bool,
    warnings: tuple[str, ...] = (),
) -> DataSourceMeta:
    return DataSourceMeta(
        source=source,
        provider="KRX / short-selling adapter",
        source_url=None,
        as_of_date=as_of_date,
        available_at=available_at,
        fetched_at=fetched_at,
        frequency="daily",
        unit="KRW / ratio",
        quality_score=max(0, min(100, confidence)),
        is_fallback=is_fallback,
        stale_data_flag=stale,
        source_table_or_endpoint=endpoint,
        confidence_score=max(0, min(100, confidence)),
        missing_data_flag=missing,
        warnings=warnings,
    )


def calculate_flow_z_score(net_buy_series: Iterable[Any]) -> float | None:
    values = _series(net_buy_series)
    if not values:
        return None
    if len(values) == 1:
        return 0.0
    avg = mean(values)
    variance = sum((value - avg) ** 2 for value in values) / len(values)
    std = sqrt(variance)
    if std == 0:
        return 0.0
    return (values[-1] - avg) / std


def calculate_days_to_cover(short_position_quantity: Any, avg_daily_volume: Any) -> float | None:
    short_qty = _finite(short_position_quantity)
    volume = _finite(avg_daily_volume)
    if short_qty is None or volume is None or volume <= 0:
        return None
    return max(0.0, short_qty) / volume


def calculate_short_pressure_score(short_sell_ratio: Any, short_position_ratio: Any, days_to_cover: Any) -> int:
    sell_ratio = _finite(short_sell_ratio)
    position_ratio = _finite(short_position_ratio)
    cover_days = _finite(days_to_cover)
    score = 0.0
    if sell_ratio is not None:
        score += _clamp(sell_ratio / 0.15, 0, 1) * 35
    if position_ratio is not None:
        score += _clamp(position_ratio / 0.12, 0, 1) * 35
    if cover_days is not None:
        score += _clamp(cover_days / 8.0, 0, 1) * 30
    return int(round(_clamp(score, 0, 100)))


def calculate_short_squeeze_score(
    short_sell_ratio: Any,
    short_position_ratio: Any,
    days_to_cover: Any,
    flow_z_score: Any,
    volatility: Any,
) -> int:
    short_pressure = calculate_short_pressure_score(short_sell_ratio, short_position_ratio, days_to_cover)
    flow_z = _finite(flow_z_score)
    vol = _finite(volatility)
    score = short_pressure * 0.55
    if flow_z is not None and flow_z > 0:
        score += _clamp(flow_z / 2.5, 0, 1) * 25
    if vol is not None:
        score += _clamp(vol / 0.50, 0, 1) * 20
    return int(round(_clamp(score, 0, 100)))


def classify_short_squeeze(short_squeeze_score: Any) -> str:
    score = _finite(short_squeeze_score)
    if score is None:
        return "unavailable"
    if score >= 70:
        return "high_squeeze_candidate"
    if score >= 50:
        return "watch"
    return "low"


def classify_fragility(fragility_score: Any) -> str:
    score = _finite(fragility_score)
    if score is None:
        return "unavailable"
    if score >= 70:
        return "high_fragility"
    if score >= 50:
        return "watch"
    return "stable"


def _distribution_risk_score(
    *,
    foreign_20d: float | None,
    institution_20d: float | None,
    individual_20d: float | None,
    foreign_ownership_change: float | None,
    flow_z_score: float | None,
) -> int:
    score = 0.0
    if foreign_20d is not None and foreign_20d < 0:
        score += 25
    if institution_20d is not None and institution_20d < 0:
        score += 20
    if individual_20d is not None and individual_20d > 0:
        score += 20
    if foreign_ownership_change is not None and foreign_ownership_change < -0.005:
        score += 15
    if flow_z_score is not None and flow_z_score < -1.0:
        score += _clamp(abs(flow_z_score) / 2.5, 0, 1) * 20
    return int(round(_clamp(score, 0, 100)))


def _fragility_score(
    *,
    distribution_risk_score: int,
    short_pressure_score: int,
    volatility: float | None,
    turnover: float | None,
    trading_value_20d: float | None,
) -> int:
    score = distribution_risk_score * 0.40 + short_pressure_score * 0.30
    if volatility is not None:
        score += _clamp(volatility / 0.55, 0, 1) * 20
    if turnover is not None and turnover < 0.006:
        score += 6
    if trading_value_20d is not None and trading_value_20d < 5_000_000_000:
        score += 10
    return int(round(_clamp(score, 0, 100)))


def _accumulation_persistence(foreign: list[float], institution: list[float]) -> int:
    paired = list(zip(foreign[-20:], institution[-20:]))
    if not paired:
        return 0
    positive = sum(1 for foreign_value, institution_value in paired if foreign_value + institution_value > 0)
    return int(round(positive / len(paired) * 100))


def _liquidity_warning(trading_value_20d: float | None, turnover: float | None, avg_daily_volume: float | None) -> str | None:
    if avg_daily_volume is not None and avg_daily_volume <= 0:
        return "zero_volume"
    if trading_value_20d is not None and trading_value_20d < 5_000_000_000:
        return "low_trading_value"
    if turnover is not None and turnover < 0.003:
        return "low_turnover"
    return None


def _build_rows(
    inputs: Iterable[Any],
    *,
    now: datetime | None,
    stale_after_hours: float,
    fallback: bool,
) -> tuple[SmartMoneyFlowRow, ...]:
    rows: list[SmartMoneyFlowRow] = []
    fetched_at = _now_iso(now)
    for item in inputs:
        flow_multiplier = _finite(_get(item, "flow_unit_multiplier", "flowUnitMultiplier", default=1.0)) or 1.0
        foreign = [value * flow_multiplier for value in _series(_get(item, "foreign_net_buy_history", "foreignNetBuyHistory"))]
        institution = [value * flow_multiplier for value in _series(_get(item, "institution_net_buy_history", "institutionNetBuyHistory"))]
        individual = [value * flow_multiplier for value in _series(_get(item, "individual_net_buy_history", "individualNetBuyHistory"))]
        combined = [foreign_value + institution_value for foreign_value, institution_value in zip(foreign, institution)]
        flow_z = calculate_flow_z_score(combined)
        foreign_5d = _sum_last(foreign, 5)
        foreign_20d = _sum_last(foreign, 20)
        foreign_60d = _sum_last(foreign, 60)
        institution_5d = _sum_last(institution, 5)
        institution_20d = _sum_last(institution, 20)
        institution_60d = _sum_last(institution, 60)
        individual_5d = _sum_last(individual, 5)
        individual_20d = _sum_last(individual, 20)
        individual_60d = _sum_last(individual, 60)
        ownership_change = _finite(_get(item, "foreign_ownership_change", "foreignOwnershipChange"))
        distribution = _distribution_risk_score(
            foreign_20d=foreign_20d,
            institution_20d=institution_20d,
            individual_20d=individual_20d,
            foreign_ownership_change=ownership_change,
            flow_z_score=flow_z,
        )
        avg_daily_volume = _finite(_get(item, "avg_daily_volume", "average_daily_volume", "avgDailyVolume"))
        days_to_cover = calculate_days_to_cover(_get(item, "short_position_quantity", "shortPositionQuantity"), avg_daily_volume)
        short_sell_ratio = _finite(_get(item, "short_sell_ratio", "shortSellRatio"))
        short_position_ratio = _finite(_get(item, "short_position_ratio", "shortPositionRatio"))
        short_pressure = calculate_short_pressure_score(short_sell_ratio, short_position_ratio, days_to_cover)
        volatility = _finite(_get(item, "volatility"))
        short_squeeze = calculate_short_squeeze_score(short_sell_ratio, short_position_ratio, days_to_cover, flow_z, volatility)
        trading_value_20d = _finite(_get(item, "trading_value_20d", "tradingValue20d"))
        turnover = _finite(_get(item, "turnover"))
        fragility = _fragility_score(
            distribution_risk_score=distribution,
            short_pressure_score=short_pressure,
            volatility=volatility,
            turnover=turnover,
            trading_value_20d=trading_value_20d,
        )
        available_at = _get(item, "available_at", "availableAt", "as_of_date", "asOfDate")
        as_of_date = _as_date_text(_get(item, "as_of_date", "asOfDate", "date", default=available_at))
        warning = _liquidity_warning(trading_value_20d, turnover, avg_daily_volume)
        missing = not foreign or not institution or short_sell_ratio is None or short_position_ratio is None
        confidence = 70 if fallback else 88
        if missing:
            confidence -= 20
        if warning:
            confidence -= 8
        meta = _meta(
            source=str(_get(item, "source", default="Mock KRX investor flow / short selling") or "Mock KRX investor flow / short selling"),
            endpoint="/api/dashboard/flow-short-pressure",
            as_of_date=as_of_date,
            available_at=_now_iso(_as_datetime(available_at)) if _as_datetime(available_at) else None,
            fetched_at=fetched_at,
            confidence=confidence,
            stale=_is_stale(available_at, now=now, stale_after_hours=stale_after_hours),
            missing=missing,
            is_fallback=bool(fallback or _get(item, "is_fallback", default=False)),
            warnings=tuple([warning] if warning else []),
        )
        rows.append(
            SmartMoneyFlowRow(
                code=str(_get(item, "code", "stock_code", "stockCode", default="N/A") or "N/A").zfill(6),
                name=str(_get(item, "name", "corp_name", "corpName", default="Unknown") or "Unknown"),
                sector=str(_get(item, "sector", default="Unclassified") or "Unclassified"),
                foreign_net_buy_5d=foreign_5d,
                foreign_net_buy_20d=foreign_20d,
                foreign_net_buy_60d=foreign_60d,
                institution_net_buy_5d=institution_5d,
                institution_net_buy_20d=institution_20d,
                institution_net_buy_60d=institution_60d,
                individual_net_buy_5d=individual_5d,
                individual_net_buy_20d=individual_20d,
                individual_net_buy_60d=individual_60d,
                pension_net_buy=(_finite(_get(item, "pension_net_buy", "pensionNetBuy")) or 0.0) * flow_multiplier if _finite(_get(item, "pension_net_buy", "pensionNetBuy")) is not None else None,
                program_net_buy=(_finite(_get(item, "program_net_buy", "programNetBuy")) or 0.0) * flow_multiplier if _finite(_get(item, "program_net_buy", "programNetBuy")) is not None else None,
                foreign_ownership_change=ownership_change,
                flow_z_score=flow_z,
                accumulation_persistence=_accumulation_persistence(foreign, institution),
                distribution_risk_score=distribution,
                short_sell_ratio=short_sell_ratio,
                short_position_ratio=short_position_ratio,
                days_to_cover=days_to_cover,
                short_pressure_score=short_pressure,
                short_squeeze_score=short_squeeze,
                fragility_score=fragility,
                trading_value_20d=trading_value_20d,
                turnover=turnover,
                volatility=volatility,
                capacity_estimate=trading_value_20d * 0.05 if trading_value_20d is not None else None,
                illiquidity_warning=warning,
                meta=meta,
            )
        )
    return tuple(rows)


def _score_from_flow(value: float | None) -> int:
    if value is None:
        return 0
    return int(round(_clamp(50 + value / 10_000_000_000, 0, 100)))


def _sector_rows(rows: tuple[SmartMoneyFlowRow, ...], meta: DataSourceMeta) -> tuple[SectorFlowHeatmapRow, ...]:
    result: list[SectorFlowHeatmapRow] = []
    for sector in sorted({row.sector for row in rows}):
        group = [row for row in rows if row.sector == sector]
        foreign_score = int(round(mean([_score_from_flow(row.foreign_net_buy_20d) for row in group])))
        institution_score = int(round(mean([_score_from_flow(row.institution_net_buy_20d) for row in group])))
        retail_score = int(round(mean([_score_from_flow(row.individual_net_buy_20d) for row in group])))
        short_pressure = int(round(mean([row.short_pressure_score for row in group])))
        liquidity_values = [row.trading_value_20d for row in group if row.trading_value_20d is not None]
        liquidity_score = 0 if not liquidity_values else int(round(_clamp(mean(liquidity_values) / 10_000_000_000, 0, 100)))
        signal = "mixed"
        if foreign_score >= 60 and institution_score >= 55 and short_pressure < 55:
            signal = "accumulation"
        elif foreign_score < 45 and institution_score < 45 and retail_score >= 55:
            signal = "distribution"
        elif retail_score >= 65:
            signal = "crowded"
        elif short_pressure >= 65 or liquidity_score < 30:
            signal = "fragile"
        result.append(
            SectorFlowHeatmapRow(
                sector=sector,
                foreign_flow_score=foreign_score,
                institution_flow_score=institution_score,
                retail_crowding_score=retail_score,
                short_pressure_score=short_pressure,
                liquidity_score=liquidity_score,
                signal=signal,  # type: ignore[arg-type]
                meta=meta,
            )
        )
    return tuple(sorted(result, key=lambda row: (row.signal != "accumulation", -row.foreign_flow_score, -row.institution_flow_score)))


def build_smart_money_flow_short_pressure_panel(
    *,
    flow_inputs: Iterable[Any] | None = None,
    now: datetime | None = None,
    stale_after_hours: float = 24.0 * 3,
    allow_mock: bool = True,
) -> SmartMoneyFlowShortPressurePanelState:
    raw_inputs = list(flow_inputs or [])
    fallback = False
    if not raw_inputs and allow_mock:
        raw_inputs = [dict(item, is_fallback=True, flow_unit_multiplier=1_000_000_000) for item in MOCK_FLOW_SHORT_INPUTS]
        fallback = True
    if not raw_inputs:
        fetched_at = _now_iso(now)
        meta = _meta(
            source="Not connected",
            endpoint="/api/dashboard/flow-short-pressure",
            as_of_date=None,
            available_at=None,
            fetched_at=fetched_at,
            confidence=0,
            stale=True,
            missing=True,
            is_fallback=True,
        )
        return SmartMoneyFlowShortPressurePanelState(
            module_id="SmartMoneyFlowShortPressurePanel",
            status="empty",
            title="Smart Money Flow & Short Pressure Panel",
            summary="No investor flow, short-selling, or liquidity data is available.",
            data_points=(DataPoint("flow_row_count", "Flow Row Count", 0, meta, "0"),),
            explanation=("Connect KRX investor flow, short-selling, and market statistics data to calculate this panel.",),
            risk_flags=("missing_flow_short_pressure_data",),
            stale_after_minutes=int(stale_after_hours * 60),
        )

    rows = _build_rows(raw_inputs, now=now, stale_after_hours=stale_after_hours, fallback=fallback)
    stale = any(row.meta.stale_data_flag for row in rows)
    missing = any(row.meta.missing_data_flag for row in rows)
    avg_confidence = int(round(sum((row.meta.confidence_score or row.meta.quality_score) for row in rows) / len(rows))) if rows else 0
    module_meta = _meta(
        source="Smart Money Flow & Short Pressure Panel",
        endpoint="/api/dashboard/flow-short-pressure",
        as_of_date=max((row.meta.as_of_date or "" for row in rows), default=None) or None,
        available_at=max((row.meta.available_at or "" for row in rows), default=None) or None,
        fetched_at=_now_iso(now),
        confidence=avg_confidence,
        stale=stale,
        missing=missing,
        is_fallback=any(row.meta.is_fallback for row in rows),
    )
    foreign_leaders = tuple(sorted([row for row in rows if (row.foreign_net_buy_20d or 0) > 0], key=lambda row: (-(row.foreign_net_buy_20d or 0), -row.accumulation_persistence))[:6])
    institution_leaders = tuple(sorted([row for row in rows if (row.institution_net_buy_20d or 0) > 0], key=lambda row: (-(row.institution_net_buy_20d or 0), -row.accumulation_persistence))[:6])
    retail_crowding = tuple(sorted([row for row in rows if (row.individual_net_buy_20d or 0) > 0], key=lambda row: (-(row.individual_net_buy_20d or 0), -row.distribution_risk_score))[:6])
    squeeze_candidates = tuple(sorted([row for row in rows if row.short_squeeze_score >= 50], key=lambda row: (-row.short_squeeze_score, -(row.flow_z_score or 0)))[:6])
    fragile = tuple(sorted([row for row in rows if row.fragility_score >= 50], key=lambda row: (-row.fragility_score, -row.short_pressure_score))[:6])
    distribution = tuple(sorted([row for row in rows if row.distribution_risk_score >= 45], key=lambda row: (-row.distribution_risk_score, row.flow_z_score or 0))[:6])
    risk_flags = []
    if stale:
        risk_flags.append("stale_flow_short_data")
    if missing:
        risk_flags.append("missing_flow_short_fields")
    if fragile:
        risk_flags.append("fragile_long_candidates_active")
    if any(row.illiquidity_warning for row in rows):
        risk_flags.append("illiquidity_warning")
    data_points = (
        DataPoint("flow_row_count", "Flow Row Count", len(rows), module_meta, str(len(rows))),
        DataPoint("foreign_accumulation_count", "Foreign Accumulation Count", len(foreign_leaders), module_meta, str(len(foreign_leaders))),
        DataPoint("short_squeeze_candidate_count", "Short Squeeze Candidate Count", len(squeeze_candidates), module_meta, str(len(squeeze_candidates))),
        DataPoint("fragile_long_candidate_count", "Fragile Long Candidate Count", len(fragile), module_meta, str(len(fragile))),
        DataPoint("distribution_risk_count", "Distribution Risk Count", len(distribution), module_meta, str(len(distribution))),
    )
    status = "stale" if stale else "ready"
    summary = "Investor flow, liquidity, and short-pressure features are ready for future alpha ranking."
    if fallback:
        summary = "Mock KRX investor flow and short-selling context is shown until real adapters are connected."
    if missing:
        summary = "Some flow or short-selling fields are missing; rankings use available fields only."
    return SmartMoneyFlowShortPressurePanelState(
        module_id="SmartMoneyFlowShortPressurePanel",
        status=status,
        title="Smart Money Flow & Short Pressure Panel",
        summary=summary,
        data_points=data_points,
        explanation=(
            "Foreign and institution accumulation uses 5D/20D/60D net buy flow and persistence.",
            "Short pressure combines short sell ratio, short position ratio, and days to cover.",
            "Fragility rises when distribution risk, short pressure, volatility, or illiquidity are elevated.",
        ),
        risk_flags=tuple(risk_flags),
        stale_after_minutes=int(stale_after_hours * 60),
        flow_rows=rows,
        foreign_accumulation_leaderboard=foreign_leaders,
        institution_accumulation_leaderboard=institution_leaders,
        retail_crowding_list=retail_crowding,
        short_squeeze_candidates=squeeze_candidates,
        fragile_long_candidates=fragile,
        distribution_risk_list=distribution,
        sector_flow_heatmap=_sector_rows(rows, module_meta),
        latest_source_at=max((row.meta.available_at or "" for row in rows), default=None) or None,
    )


def smart_money_flow_short_pressure_api_response(state: SmartMoneyFlowShortPressurePanelState) -> dict[str, Any]:
    payload = state.to_dict()
    payload["moduleId"] = payload.pop("module_id")
    payload["dataPoints"] = payload.pop("data_points")
    payload["flowRows"] = payload.pop("flow_rows")
    payload["foreignAccumulationLeaderboard"] = payload.pop("foreign_accumulation_leaderboard")
    payload["institutionAccumulationLeaderboard"] = payload.pop("institution_accumulation_leaderboard")
    payload["retailCrowdingList"] = payload.pop("retail_crowding_list")
    payload["shortSqueezeCandidates"] = payload.pop("short_squeeze_candidates")
    payload["fragileLongCandidates"] = payload.pop("fragile_long_candidates")
    payload["distributionRiskList"] = payload.pop("distribution_risk_list")
    payload["sectorFlowHeatmap"] = payload.pop("sector_flow_heatmap")
    payload["latestSourceAt"] = payload.pop("latest_source_at")
    payload["staleAfterMinutes"] = payload.pop("stale_after_minutes")
    payload["apiPath"] = payload.pop("api_path")
    return payload
