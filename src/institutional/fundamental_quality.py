from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from .models import DataPoint, DataSourceMeta, FundamentalQualityPanelState, FundamentalQualityRow, ROICValuationPoint


KST = ZoneInfo("Asia/Seoul")


MOCK_FINANCIAL_INPUTS: tuple[dict[str, Any], ...] = (
    {
        "code": "005930",
        "name": "Samsung Electronics",
        "sector": "Semiconductors",
        "valuation_percentile": 42.0,
        "per": 13.2,
        "pbr": 1.18,
        "periods": [
            {"period": "2025Q2", "available_at": "2025-08-14", "revenue": 74_000, "operating_income": 10_400, "gross_profit": 28_000, "net_income": 8_800, "cfo": 12_500, "capex": 8_000, "total_assets": 500_000, "equity": 360_000, "debt": 82_000, "cash": 95_000, "ebitda": 18_000, "interest_expense": 900, "invested_capital": 280_000},
            {"period": "2025Q3", "available_at": "2025-11-14", "revenue": 78_000, "operating_income": 11_300, "gross_profit": 30_000, "net_income": 9_500, "cfo": 13_200, "capex": 8_500, "total_assets": 512_000, "equity": 369_000, "debt": 84_000, "cash": 97_000, "ebitda": 19_000, "interest_expense": 920, "invested_capital": 287_000},
            {"period": "2025Q4", "available_at": "2026-03-15", "revenue": 82_000, "operating_income": 12_500, "gross_profit": 32_000, "net_income": 10_400, "cfo": 14_300, "capex": 9_200, "total_assets": 526_000, "equity": 381_000, "debt": 83_000, "cash": 102_000, "ebitda": 20_500, "interest_expense": 910, "invested_capital": 291_000},
            {"period": "2026Q1", "available_at": "2026-05-15", "revenue": 85_000, "operating_income": 13_600, "gross_profit": 33_700, "net_income": 11_200, "cfo": 15_100, "capex": 9_600, "total_assets": 535_000, "equity": 392_000, "debt": 81_000, "cash": 108_000, "ebitda": 21_800, "interest_expense": 880, "invested_capital": 292_000},
            {"period": "2024Q2", "available_at": "2024-08-14", "revenue": 62_000, "operating_income": 6_400, "gross_profit": 22_000, "net_income": 5_300, "cfo": 8_400, "capex": 7_600, "total_assets": 460_000, "equity": 330_000, "debt": 86_000, "cash": 83_000, "ebitda": 13_000, "interest_expense": 930, "invested_capital": 272_000},
            {"period": "2024Q3", "available_at": "2024-11-14", "revenue": 64_000, "operating_income": 6_900, "gross_profit": 23_000, "net_income": 5_900, "cfo": 9_000, "capex": 7_700, "total_assets": 468_000, "equity": 336_000, "debt": 87_000, "cash": 84_000, "ebitda": 13_700, "interest_expense": 940, "invested_capital": 274_000},
            {"period": "2024Q4", "available_at": "2025-03-15", "revenue": 67_000, "operating_income": 7_700, "gross_profit": 24_300, "net_income": 6_600, "cfo": 9_800, "capex": 7_900, "total_assets": 478_000, "equity": 344_000, "debt": 86_500, "cash": 87_000, "ebitda": 14_800, "interest_expense": 940, "invested_capital": 276_000},
            {"period": "2025Q1", "available_at": "2025-05-15", "revenue": 70_000, "operating_income": 8_500, "gross_profit": 25_700, "net_income": 7_300, "cfo": 10_900, "capex": 8_100, "total_assets": 489_000, "equity": 352_000, "debt": 85_000, "cash": 91_000, "ebitda": 16_000, "interest_expense": 920, "invested_capital": 279_000},
        ],
    },
    {
        "code": "000660",
        "name": "SK hynix",
        "sector": "Semiconductors",
        "valuation_percentile": 36.0,
        "per": 19.5,
        "pbr": 1.65,
        "periods": [
            {"period": "2025Q2", "available_at": "2025-08-14", "revenue": 18_000, "operating_income": 4_200, "gross_profit": 7_800, "net_income": 3_500, "cfo": 5_800, "capex": 4_200, "total_assets": 120_000, "equity": 73_000, "debt": 34_000, "cash": 18_000, "ebitda": 7_500, "interest_expense": 530, "invested_capital": 85_000},
            {"period": "2025Q3", "available_at": "2025-11-14", "revenue": 20_000, "operating_income": 5_000, "gross_profit": 8_900, "net_income": 4_100, "cfo": 6_500, "capex": 4_700, "total_assets": 126_000, "equity": 78_000, "debt": 35_000, "cash": 19_000, "ebitda": 8_500, "interest_expense": 520, "invested_capital": 88_000},
            {"period": "2025Q4", "available_at": "2026-03-15", "revenue": 22_000, "operating_income": 5_600, "gross_profit": 9_600, "net_income": 4_700, "cfo": 7_300, "capex": 5_200, "total_assets": 132_000, "equity": 83_000, "debt": 36_000, "cash": 20_000, "ebitda": 9_300, "interest_expense": 510, "invested_capital": 91_000},
            {"period": "2026Q1", "available_at": "2026-05-15", "revenue": 23_000, "operating_income": 6_000, "gross_profit": 10_100, "net_income": 5_100, "cfo": 7_900, "capex": 5_400, "total_assets": 136_000, "equity": 87_000, "debt": 35_000, "cash": 22_000, "ebitda": 9_900, "interest_expense": 500, "invested_capital": 92_000},
            {"period": "2024Q2", "available_at": "2024-08-14", "revenue": 12_000, "operating_income": 1_100, "gross_profit": 3_700, "net_income": 800, "cfo": 2_400, "capex": 3_700, "total_assets": 103_000, "equity": 62_000, "debt": 37_000, "cash": 15_000, "ebitda": 3_800, "interest_expense": 580, "invested_capital": 80_000},
            {"period": "2024Q3", "available_at": "2024-11-14", "revenue": 13_500, "operating_income": 1_700, "gross_profit": 4_400, "net_income": 1_250, "cfo": 3_100, "capex": 3_900, "total_assets": 107_000, "equity": 64_000, "debt": 37_500, "cash": 15_800, "ebitda": 4_600, "interest_expense": 570, "invested_capital": 81_000},
            {"period": "2024Q4", "available_at": "2025-03-15", "revenue": 15_000, "operating_income": 2_400, "gross_profit": 5_300, "net_income": 1_900, "cfo": 4_000, "capex": 4_000, "total_assets": 112_000, "equity": 67_000, "debt": 36_000, "cash": 16_500, "ebitda": 5_600, "interest_expense": 560, "invested_capital": 82_000},
            {"period": "2025Q1", "available_at": "2025-05-15", "revenue": 16_500, "operating_income": 3_300, "gross_profit": 6_400, "net_income": 2_700, "cfo": 4_900, "capex": 4_100, "total_assets": 116_000, "equity": 70_000, "debt": 35_000, "cash": 17_200, "ebitda": 6_600, "interest_expense": 540, "invested_capital": 84_000},
        ],
    },
    {
        "code": "034020",
        "name": "Doosan Enerbility",
        "sector": "Industrials",
        "valuation_percentile": 82.0,
        "per": 31.0,
        "pbr": 2.3,
        "periods": [
            {"period": "2025Q2", "available_at": "2025-08-14", "revenue": 4_700, "operating_income": 260, "gross_profit": 720, "net_income": 90, "cfo": 30, "capex": 420, "total_assets": 48_000, "equity": 13_000, "debt": 21_000, "cash": 4_200, "ebitda": 650, "interest_expense": 300, "invested_capital": 30_000},
            {"period": "2025Q3", "available_at": "2025-11-14", "revenue": 4_900, "operating_income": 250, "gross_profit": 710, "net_income": 70, "cfo": -20, "capex": 450, "total_assets": 49_000, "equity": 13_100, "debt": 21_500, "cash": 4_000, "ebitda": 640, "interest_expense": 310, "invested_capital": 30_800},
            {"period": "2025Q4", "available_at": "2026-03-15", "revenue": 5_000, "operating_income": 220, "gross_profit": 690, "net_income": 50, "cfo": -80, "capex": 500, "total_assets": 50_000, "equity": 13_000, "debt": 22_000, "cash": 3_700, "ebitda": 610, "interest_expense": 320, "invested_capital": 31_300},
            {"period": "2026Q1", "available_at": "2026-05-15", "revenue": 4_850, "operating_income": 180, "gross_profit": 650, "net_income": 20, "cfo": -120, "capex": 520, "total_assets": 50_500, "equity": 12_900, "debt": 22_400, "cash": 3_400, "ebitda": 560, "interest_expense": 330, "invested_capital": 31_900},
            {"period": "2024Q2", "available_at": "2024-08-14", "revenue": 4_400, "operating_income": 330, "gross_profit": 800, "net_income": 140, "cfo": 210, "capex": 380, "total_assets": 46_000, "equity": 13_600, "debt": 19_800, "cash": 4_500, "ebitda": 710, "interest_expense": 280, "invested_capital": 29_000},
            {"period": "2024Q3", "available_at": "2024-11-14", "revenue": 4_500, "operating_income": 320, "gross_profit": 790, "net_income": 130, "cfo": 180, "capex": 390, "total_assets": 46_800, "equity": 13_500, "debt": 20_000, "cash": 4_400, "ebitda": 700, "interest_expense": 285, "invested_capital": 29_300},
            {"period": "2024Q4", "available_at": "2025-03-15", "revenue": 4_600, "operating_income": 300, "gross_profit": 760, "net_income": 110, "cfo": 130, "capex": 400, "total_assets": 47_300, "equity": 13_400, "debt": 20_300, "cash": 4_350, "ebitda": 680, "interest_expense": 290, "invested_capital": 29_600},
            {"period": "2025Q1", "available_at": "2025-05-15", "revenue": 4_650, "operating_income": 280, "gross_profit": 740, "net_income": 100, "cfo": 70, "capex": 410, "total_assets": 47_700, "equity": 13_200, "debt": 20_800, "cash": 4_250, "ebitda": 660, "interest_expense": 295, "invested_capital": 30_000},
        ],
    },
    {
        "code": "105560",
        "name": "KB Financial",
        "sector": "Banks / Insurance",
        "valuation_percentile": 28.0,
        "per": 5.8,
        "pbr": 0.55,
        "periods": [
            {"period": "2025Q2", "available_at": "2025-08-14", "revenue": 7_200, "operating_income": 1_620, "gross_profit": 7_200, "net_income": 1_250, "cfo": 1_380, "capex": 120, "total_assets": 740_000, "equity": 58_000, "debt": 0, "cash": 0, "ebitda": 1_700, "interest_expense": 0, "invested_capital": 58_000},
            {"period": "2025Q3", "available_at": "2025-11-14", "revenue": 7_500, "operating_income": 1_700, "gross_profit": 7_500, "net_income": 1_310, "cfo": 1_430, "capex": 130, "total_assets": 752_000, "equity": 59_500, "debt": 0, "cash": 0, "ebitda": 1_780, "interest_expense": 0, "invested_capital": 59_500},
            {"period": "2025Q4", "available_at": "2026-03-15", "revenue": 7_650, "operating_income": 1_760, "gross_profit": 7_650, "net_income": 1_360, "cfo": 1_500, "capex": 130, "total_assets": 765_000, "equity": 61_000, "debt": 0, "cash": 0, "ebitda": 1_850, "interest_expense": 0, "invested_capital": 61_000},
            {"period": "2026Q1", "available_at": "2026-05-15", "revenue": 7_800, "operating_income": 1_820, "gross_profit": 7_800, "net_income": 1_420, "cfo": 1_540, "capex": 140, "total_assets": 778_000, "equity": 62_300, "debt": 0, "cash": 0, "ebitda": 1_900, "interest_expense": 0, "invested_capital": 62_300},
            {"period": "2024Q2", "available_at": "2024-08-14", "revenue": 6_900, "operating_income": 1_430, "gross_profit": 6_900, "net_income": 1_100, "cfo": 1_230, "capex": 120, "total_assets": 704_000, "equity": 54_000, "debt": 0, "cash": 0, "ebitda": 1_500, "interest_expense": 0, "invested_capital": 54_000},
            {"period": "2024Q3", "available_at": "2024-11-14", "revenue": 7_000, "operating_income": 1_480, "gross_profit": 7_000, "net_income": 1_140, "cfo": 1_260, "capex": 120, "total_assets": 713_000, "equity": 55_000, "debt": 0, "cash": 0, "ebitda": 1_550, "interest_expense": 0, "invested_capital": 55_000},
            {"period": "2024Q4", "available_at": "2025-03-15", "revenue": 7_050, "operating_income": 1_520, "gross_profit": 7_050, "net_income": 1_180, "cfo": 1_300, "capex": 125, "total_assets": 724_000, "equity": 56_000, "debt": 0, "cash": 0, "ebitda": 1_600, "interest_expense": 0, "invested_capital": 56_000},
            {"period": "2025Q1", "available_at": "2025-05-15", "revenue": 7_100, "operating_income": 1_560, "gross_profit": 7_100, "net_income": 1_210, "cfo": 1_340, "capex": 125, "total_assets": 732_000, "equity": 57_000, "debt": 0, "cash": 0, "ebitda": 1_650, "interest_expense": 0, "invested_capital": 57_000},
        ],
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
        return value
    try:
        if hasattr(value, "to_pydatetime"):
            return value.to_pydatetime()
    except Exception:
        pass
    text = str(value).strip()
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        if len(text) == 10 and text[4:5] == "-" and text[7:8] == "-":
            stamp = stamp.replace(hour=23, minute=59, second=59, tzinfo=KST)
        else:
            stamp = stamp.replace(tzinfo=KST)
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
    available_at: str | None = None,
) -> DataSourceMeta:
    return DataSourceMeta(
        source=source,
        provider=source,
        source_url=None,
        as_of_date=as_of_date,
        available_at=available_at or as_of_date,
        fetched_at=fetched_at,
        frequency="financial_statement",
        unit="ratio",
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


def select_point_in_time_periods(periods: Iterable[Any], as_of: datetime | None = None) -> list[Any]:
    cutoff = as_of or datetime.now(timezone.utc)
    selected = []
    for period in periods or []:
        available_at = _as_datetime(_get(period, "available_at", "availableAt"))
        if available_at is None:
            continue
        if available_at.tzinfo is None:
            available_at = available_at.replace(tzinfo=timezone.utc)
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        if available_at <= cutoff:
            selected.append(period)
    return sorted(selected, key=lambda item: str(_get(item, "available_at", "availableAt", default="")))


def calculate_ttm(periods: Iterable[Any], field: str, as_of: datetime | None = None) -> float | None:
    selected = select_point_in_time_periods(periods, as_of)[-4:]
    values = [_finite(_get(item, field)) for item in selected]
    clean = [value for value in values if value is not None]
    if len(clean) < 4:
        return None
    return sum(clean)


def _latest_period(periods: Iterable[Any], as_of: datetime | None = None) -> Any | None:
    selected = select_point_in_time_periods(periods, as_of)
    return selected[-1] if selected else None


def _previous_ttm(periods: Iterable[Any], field: str, as_of: datetime | None = None) -> float | None:
    selected = select_point_in_time_periods(periods, as_of)
    if len(selected) < 8:
        return None
    values = [_finite(_get(item, field)) for item in selected[-8:-4]]
    clean = [value for value in values if value is not None]
    if len(clean) < 4:
        return None
    return sum(clean)


def _growth(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return current / previous - 1.0


def calculate_accrual_ratio(net_income: Any, cfo: Any, total_assets: Any) -> float | None:
    ni = _finite(net_income)
    cash_flow = _finite(cfo)
    assets = _finite(total_assets)
    if ni is None or cash_flow is None or assets in (None, 0):
        return None
    result = (ni - cash_flow) / assets
    return result if isfinite(result) else None


def _score_high(value: float | None, low: float, high: float) -> int:
    if value is None:
        return 40
    return int(round(_clamp((value - low) / (high - low) * 100.0, 0.0, 100.0)))


def _score_low(value: float | None, good: float, bad: float) -> int:
    if value is None:
        return 40
    return int(round(_clamp((bad - value) / (bad - good) * 100.0, 0.0, 100.0)))


def calculate_quality_score(metrics: dict[str, Any]) -> dict[str, int]:
    profitability = round(
        (
            _score_high(_finite(metrics.get("roe")), 0.02, 0.18)
            + _score_high(_finite(metrics.get("roa")), 0.01, 0.10)
            + _score_high(_finite(metrics.get("roic")), 0.03, 0.18)
            + _score_high(_finite(metrics.get("operating_margin")), 0.03, 0.22)
        )
        / 4
    )
    cash_flow_quality = round(
        (
            _score_high(_finite(metrics.get("cfo_to_net_income")), 0.5, 1.4)
            + _score_high(_finite(metrics.get("fcf_conversion")), -0.1, 1.0)
            + _score_low(abs(_finite(metrics.get("accrual_ratio")) or 0.0), 0.0, 0.12)
        )
        / 3
    )
    balance_sheet = round(
        (
            _score_low(_finite(metrics.get("debt_to_equity")), 0.2, 2.0)
            + _score_low(_finite(metrics.get("net_debt_to_ebitda")), -1.0, 4.0)
            + _score_high(_finite(metrics.get("interest_coverage")), 2.0, 15.0)
        )
        / 3
    )
    growth = round(
        (
            _score_high(_finite(metrics.get("revenue_growth")), -0.05, 0.25)
            + _score_high(_finite(metrics.get("operating_income_growth")), -0.10, 0.35)
        )
        / 2
    )
    accounting_inverse = _score_low(abs(_finite(metrics.get("accrual_ratio")) or 0.0), 0.0, 0.18)
    quality = round(
        profitability * 0.28
        + cash_flow_quality * 0.24
        + balance_sheet * 0.22
        + growth * 0.16
        + accounting_inverse * 0.10
    )
    return {
        "profitability_score": int(profitability),
        "cash_flow_quality_score": int(cash_flow_quality),
        "balance_sheet_safety_score": int(balance_sheet),
        "growth_consistency_score": int(growth),
        "accounting_risk_inverse_score": int(accounting_inverse),
        "quality_score": int(_clamp(quality, 0, 100)),
    }


def _piotroski(metrics: dict[str, Any], current_revenue: float | None, previous_revenue: float | None) -> int | None:
    if not metrics:
        return None
    checks = [
        (_finite(metrics.get("roa")) or 0) > 0,
        (_finite(metrics.get("cfo")) or 0) > 0,
        (_finite(metrics.get("cfo_to_net_income")) or 0) > 1,
        (_finite(metrics.get("revenue_growth")) or 0) > 0,
        (_finite(metrics.get("operating_income_growth")) or 0) > 0,
        (_finite(metrics.get("gross_margin")) or 0) > 0.2,
        (_finite(metrics.get("debt_to_equity")) or 99) < 1.5,
        (_finite(metrics.get("fcf_conversion")) or -99) > 0,
        current_revenue is not None and previous_revenue is not None and current_revenue > previous_revenue,
    ]
    return sum(1 for item in checks if item)


def _altman_proxy(metrics: dict[str, Any]) -> float | None:
    roa = _finite(metrics.get("roa"))
    debt_to_equity = _finite(metrics.get("debt_to_equity"))
    operating_margin = _finite(metrics.get("operating_margin"))
    if roa is None or debt_to_equity is None or operating_margin is None:
        return None
    result = 1.2 + roa * 8.0 + operating_margin * 5.0 + max(0.0, 2.0 - debt_to_equity) * 0.6
    return result if isfinite(result) else None


def _metrics_from_periods(periods: Iterable[Any], as_of: datetime | None = None) -> dict[str, float | None]:
    selected = select_point_in_time_periods(periods, as_of)
    latest = selected[-1] if selected else None
    revenue = calculate_ttm(selected, "revenue", as_of)
    prev_revenue = _previous_ttm(selected, "revenue", as_of)
    op = calculate_ttm(selected, "operating_income", as_of)
    prev_op = _previous_ttm(selected, "operating_income", as_of)
    net_income = calculate_ttm(selected, "net_income", as_of)
    cfo = calculate_ttm(selected, "cfo", as_of)
    capex = calculate_ttm(selected, "capex", as_of)
    gross_profit = calculate_ttm(selected, "gross_profit", as_of)
    ebitda = calculate_ttm(selected, "ebitda", as_of)
    interest = calculate_ttm(selected, "interest_expense", as_of)
    assets = _finite(_get(latest, "total_assets")) if latest else None
    equity = _finite(_get(latest, "equity")) if latest else None
    debt = _finite(_get(latest, "debt")) if latest else None
    cash = _finite(_get(latest, "cash")) if latest else None
    invested_capital = _finite(_get(latest, "invested_capital")) if latest else None
    fcf = None if cfo is None or capex is None else cfo - capex
    return {
        "revenue": revenue,
        "previous_revenue": prev_revenue,
        "operating_income": op,
        "previous_operating_income": prev_op,
        "net_income": net_income,
        "cfo": cfo,
        "fcf": fcf,
        "ebitda": ebitda,
        "revenue_growth": _growth(revenue, prev_revenue),
        "operating_income_growth": _growth(op, prev_op),
        "gross_margin": None if gross_profit is None or revenue in (None, 0) else gross_profit / revenue,
        "operating_margin": None if op is None or revenue in (None, 0) else op / revenue,
        "net_margin": None if net_income is None or revenue in (None, 0) else net_income / revenue,
        "roe": None if net_income is None or equity in (None, 0) else net_income / equity,
        "roa": None if net_income is None or assets in (None, 0) else net_income / assets,
        "roic": None if op is None or invested_capital in (None, 0) else op / invested_capital,
        "cfo_to_net_income": None if cfo is None or net_income in (None, 0) else cfo / net_income,
        "fcf_conversion": None if fcf is None or net_income in (None, 0) else fcf / net_income,
        "accrual_ratio": calculate_accrual_ratio(net_income, cfo, assets),
        "debt_to_equity": None if debt is None or equity in (None, 0) else debt / equity,
        "net_debt_to_ebitda": None if debt is None or cash is None or ebitda in (None, 0) else (debt - cash) / ebitda,
        "interest_coverage": None if op is None or interest in (None, 0) else op / interest,
    }


def _flags(metrics: dict[str, Any]) -> tuple[str, ...]:
    flags = []
    if (_finite(metrics.get("cfo_to_net_income")) or 0) < 0.8:
        flags.append("low_cfo_to_net_income")
    if abs(_finite(metrics.get("accrual_ratio")) or 0.0) > 0.08:
        flags.append("high_accrual_ratio")
    if (_finite(metrics.get("fcf_conversion")) or 0) < 0:
        flags.append("negative_fcf_conversion")
    if (_finite(metrics.get("debt_to_equity")) or 0) > 1.5:
        flags.append("high_debt_to_equity")
    interest = _finite(metrics.get("interest_coverage"))
    if interest is not None and interest < 3:
        flags.append("low_interest_coverage")
    if (_finite(metrics.get("operating_income_growth")) or 0) < -0.10:
        flags.append("operating_income_deterioration")
    return tuple(flags)


def _label(quality_score: int, flags: tuple[str, ...], growth: float | None) -> str:
    if quality_score >= 78 and len(flags) <= 1:
        return "top_quality"
    if quality_score >= 65 and (growth or 0) > 0:
        return "improving"
    if quality_score <= 45 or len(flags) >= 3:
        return "deteriorating"
    return "watch"


def _build_row(item: Any, *, now: datetime | None, stale_after_hours: float, fallback: bool) -> FundamentalQualityRow:
    periods = list(_get(item, "periods", default=[]) or [])
    as_of = now or datetime.now(timezone.utc)
    selected = select_point_in_time_periods(periods, as_of)
    latest = selected[-1] if selected else None
    metrics = _metrics_from_periods(selected, as_of)
    for key in [
        "revenue_growth",
        "operating_income_growth",
        "roe",
        "roa",
        "roic",
        "gross_margin",
        "operating_margin",
        "net_margin",
        "cfo_to_net_income",
        "fcf_conversion",
        "accrual_ratio",
        "debt_to_equity",
        "net_debt_to_ebitda",
        "interest_coverage",
    ]:
        override = _finite(_get(item, key, default=None))
        if override is not None:
            metrics[key] = override
    scores = calculate_quality_score(metrics)
    piotroski = _piotroski(metrics, _finite(metrics.get("revenue")), _finite(metrics.get("previous_revenue")))
    altman = _altman_proxy(metrics)
    flags = _flags(metrics)
    quality_score = scores["quality_score"]
    quality_label = _label(quality_score, flags, _finite(metrics.get("operating_income_growth")))
    available_at = _get(latest, "available_at", "availableAt") if latest else _get(item, "available_at", "availableAt")
    available_stamp = _as_datetime(available_at)
    available_at_text = _now_iso(available_stamp) if available_stamp is not None else None
    as_of_date = _as_date_text(available_stamp)
    stale = _is_stale(available_stamp, now=now, stale_after_hours=stale_after_hours) if available_stamp else True
    missing = latest is None and not any(_finite(_get(item, key)) is not None for key in ["roe", "roa", "roic"])
    meta = _meta(
        source=str(_get(item, "source", default="Mock OpenDART financial statements") or "Mock OpenDART financial statements"),
        endpoint=str(_get(item, "endpoint", default="planned:opendart_financial_statements") or "planned:opendart_financial_statements"),
        as_of_date=as_of_date,
        fetched_at=_now_iso(now),
        confidence=int(_finite(_get(item, "confidence_score", "confidenceScore", default=66 if fallback else 84)) or 0),
        stale=stale,
        missing=missing,
        is_fallback=fallback or bool(_get(item, "is_fallback", "isFallback", default=False)),
        available_at=available_at_text,
    )
    return FundamentalQualityRow(
        code=str(_get(item, "code", "symbol", default="")),
        name=str(_get(item, "name", default=_get(item, "code", default="")) or _get(item, "code", default="")),
        sector=str(_get(item, "sector", default="Unclassified") or "Unclassified"),
        revenue_growth=_finite(metrics.get("revenue_growth")),
        operating_income_growth=_finite(metrics.get("operating_income_growth")),
        roe=_finite(metrics.get("roe")),
        roa=_finite(metrics.get("roa")),
        roic=_finite(metrics.get("roic")),
        gross_margin=_finite(metrics.get("gross_margin")),
        operating_margin=_finite(metrics.get("operating_margin")),
        net_margin=_finite(metrics.get("net_margin")),
        cfo_to_net_income=_finite(metrics.get("cfo_to_net_income")),
        fcf_conversion=_finite(metrics.get("fcf_conversion")),
        accrual_ratio=_finite(metrics.get("accrual_ratio")),
        debt_to_equity=_finite(metrics.get("debt_to_equity")),
        net_debt_to_ebitda=_finite(metrics.get("net_debt_to_ebitda")),
        interest_coverage=_finite(metrics.get("interest_coverage")),
        piotroski_f_score=piotroski,
        altman_z_score_proxy=altman,
        profitability_score=scores["profitability_score"],
        cash_flow_quality_score=scores["cash_flow_quality_score"],
        balance_sheet_safety_score=scores["balance_sheet_safety_score"],
        growth_consistency_score=scores["growth_consistency_score"],
        accounting_risk_inverse_score=scores["accounting_risk_inverse_score"],
        quality_score=quality_score,
        quality_label=quality_label,  # type: ignore[arg-type]
        valuation_percentile=_finite(_get(item, "valuation_percentile", "valuationPercentile")),
        per=_finite(_get(item, "per")),
        pbr=_finite(_get(item, "pbr")),
        available_at=available_at_text,
        accounting_flags=flags,
        meta=meta,
    )


def build_fundamental_quality_panel(
    *,
    financial_inputs: Iterable[Any] | None = None,
    now: datetime | None = None,
    stale_after_hours: float = 24.0 * 120,
    allow_mock: bool = True,
) -> FundamentalQualityPanelState:
    raw_inputs = list(financial_inputs or [])
    fallback = False
    if not raw_inputs and allow_mock:
        raw_inputs = [dict(item, is_fallback=True) for item in MOCK_FINANCIAL_INPUTS]
        fallback = True
    if not raw_inputs:
        meta = _meta(
            source="Not connected",
            endpoint="/api/dashboard/fundamental-quality",
            as_of_date=None,
            fetched_at=_now_iso(now),
            confidence=0,
            stale=True,
            missing=True,
            is_fallback=True,
        )
        return FundamentalQualityPanelState(
            module_id="FundamentalQualityPanel",
            status="empty",
            title="Fundamental Quality Panel",
            summary="No financial statement source is available.",
            data_points=(DataPoint("quality_row_count", "Quality Row Count", 0, meta, "0"),),
            explanation=("Connect OpenDART financial statement inputs with available_at timestamps to calculate quality.",),
            risk_flags=("missing_financial_statement_data",),
            stale_after_minutes=int(stale_after_hours * 60),
        )
    rows = tuple(_build_row(item, now=now, stale_after_hours=stale_after_hours, fallback=fallback) for item in raw_inputs)
    stale = any(row.meta.stale_data_flag for row in rows)
    missing = any(row.meta.missing_data_flag for row in rows)
    avg_quality = sum(row.quality_score for row in rows) / len(rows) if rows else 0.0
    meta = _meta(
        source="Fundamental Quality Panel",
        endpoint="/api/dashboard/fundamental-quality",
        as_of_date=(now or datetime.now()).date().isoformat(),
        fetched_at=_now_iso(now),
        confidence=int(round(sum((row.meta.confidence_score or row.meta.quality_score) for row in rows) / len(rows))) if rows else 0,
        stale=stale,
        missing=missing,
        is_fallback=any(row.meta.is_fallback for row in rows),
    )
    top_quality = tuple(sorted(rows, key=lambda row: row.quality_score, reverse=True)[:5])
    deteriorating = tuple(sorted([row for row in rows if row.quality_label == "deteriorating" or row.accounting_flags], key=lambda row: (row.quality_score, -len(row.accounting_flags)))[:5])
    cheap_quality = tuple(sorted([row for row in rows if row.quality_score >= 65 and (row.valuation_percentile is not None and row.valuation_percentile <= 45)], key=lambda row: (row.valuation_percentile or 101, -row.quality_score))[:5])
    red_flags = tuple(sorted([row for row in rows if row.accounting_flags], key=lambda row: len(row.accounting_flags), reverse=True)[:5])
    fcf_rank = tuple(sorted(rows, key=lambda row: -999 if row.fcf_conversion is None else row.fcf_conversion, reverse=True)[:5])
    roic_points = tuple(
        ROICValuationPoint(row.code, row.name, row.sector, row.roic, row.valuation_percentile, row.quality_score, row.meta)
        for row in rows
    )
    data_points = (
        DataPoint("average_quality_score", "Average Quality Score", avg_quality, meta, f"{avg_quality:.1f}/100"),
        DataPoint("quality_row_count", "Quality Row Count", len(rows), meta, str(len(rows))),
        DataPoint("accounting_red_flag_count", "Accounting Red Flags", len(red_flags), meta, str(len(red_flags))),
        DataPoint("cheap_quality_count", "Cheap Quality Count", len(cheap_quality), meta, str(len(cheap_quality))),
    )
    summary = "Fundamental quality scores are ready for later ranking modules. No buy/sell recommendation is generated."
    if fallback:
        summary = "Mock OpenDART-style financial quality data is shown until real financial statement adapters are connected."
    if missing:
        summary = "Some financial statement fields are missing; quality scores use available point-in-time data only."
    return FundamentalQualityPanelState(
        module_id="FundamentalQualityPanel",
        status="stale" if stale else "ready",
        title="Fundamental Quality Panel",
        summary=summary,
        data_points=data_points,
        explanation=(
            "DART financial data is admitted only from available_at or receipt_date, never fiscal period end date.",
            "QualityScore combines profitability, cash-flow quality, balance sheet safety, growth consistency, and inverse accounting risk.",
            "Cheap quality is a review bucket, not a recommendation.",
        ),
        risk_flags=tuple(["stale_financial_statement_data"] if stale else []) + tuple(["missing_financial_statement_fields"] if missing else []),
        stale_after_minutes=int(stale_after_hours * 60),
        quality_rows=rows,
        top_quality_stocks=top_quality,
        deteriorating_quality_stocks=deteriorating,
        cheap_quality_stocks=cheap_quality,
        accounting_red_flags=red_flags,
        fcf_conversion_ranking=fcf_rank,
        roic_vs_valuation=roic_points,
        latest_source_at=max((row.meta.fetched_at or "" for row in rows), default=None) or None,
    )


def fundamental_quality_api_response(state: FundamentalQualityPanelState) -> dict[str, Any]:
    payload = state.to_dict()
    payload["moduleId"] = payload.pop("module_id")
    payload["dataPoints"] = payload.pop("data_points")
    payload["qualityRows"] = payload.pop("quality_rows")
    payload["topQualityStocks"] = payload.pop("top_quality_stocks")
    payload["deterioratingQualityStocks"] = payload.pop("deteriorating_quality_stocks")
    payload["cheapQualityStocks"] = payload.pop("cheap_quality_stocks")
    payload["accountingRedFlags"] = payload.pop("accounting_red_flags")
    payload["fcfConversionRanking"] = payload.pop("fcf_conversion_ranking")
    payload["roicVsValuation"] = payload.pop("roic_vs_valuation")
    payload["latestSourceAt"] = payload.pop("latest_source_at")
    payload["staleAfterMinutes"] = payload.pop("stale_after_minutes")
    payload["apiPath"] = payload.pop("api_path")
    return payload
