from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Generic, Literal, TypeVar


DataStatus = Literal["loading", "ready", "empty", "error", "stale", "planned", "mock"]
T = TypeVar("T")


@dataclass(frozen=True)
class DataSourceMeta:
    source: str
    provider: str | None
    source_url: str | None
    as_of_date: str | None
    available_at: str | None
    fetched_at: str | None
    frequency: str
    unit: str
    quality_score: int
    is_fallback: bool
    stale_data_flag: bool
    source_table_or_endpoint: str | None = None
    revised_at: str | None = None
    confidence_score: int | None = None
    missing_data_flag: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)
    published_at: str | None = None
    timezone: str | None = None
    currency: str | None = None
    data_mode: str = "unavailable"
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provider_version: str | None = None
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderResult(Generic[T]):
    data: T | None
    meta: DataSourceMeta
    status: DataStatus = "ready"
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.data is not None and self.status in {"ready", "stale"} and not self.errors

    @property
    def value(self) -> T | None:
        """Compatibility alias for providers that call their payload value."""
        return self.data

    @property
    def metadata(self) -> DataSourceMeta:
        return self.meta

    def to_dict(self) -> dict[str, Any]:
        data = self.data
        if hasattr(data, "to_dict"):
            data = data.to_dict()  # type: ignore[union-attr]
        return {
            "data": data,
            "meta": self.meta.to_dict(),
            "status": self.status,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class DataPoint:
    key: str
    label: str
    value: Any
    meta: DataSourceMeta
    display_value: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "display_value": self.display_value,
            "description": self.description,
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class ModuleState:
    module_id: str
    status: DataStatus
    title: str
    summary: str
    data_points: tuple[DataPoint, ...]
    explanation: tuple[str, ...]
    risk_flags: tuple[str, ...]
    stale_after_minutes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "status": self.status,
            "title": self.title,
            "summary": self.summary,
            "data_points": [point.to_dict() for point in self.data_points],
            "explanation": list(self.explanation),
            "risk_flags": list(self.risk_flags),
            "stale_after_minutes": self.stale_after_minutes,
        }


@dataclass(frozen=True)
class AllocationSlice:
    key: str
    label: str
    value: float
    weight: float
    meta: DataSourceMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "weight": self.weight,
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class HoldingRiskRow:
    symbol: str
    name: str
    asset_class: str
    market: str
    sector: str
    country: str
    currency: str
    quantity: float
    current_price: float
    market_value: float
    weight: float
    pnl_pct: float | None
    liquidity_warning: str | None
    meta: DataSourceMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "asset_class": self.asset_class,
            "market": self.market,
            "sector": self.sector,
            "country": self.country,
            "currency": self.currency,
            "quantity": self.quantity,
            "current_price": self.current_price,
            "market_value": self.market_value,
            "weight": self.weight,
            "pnl_pct": self.pnl_pct,
            "liquidity_warning": self.liquidity_warning,
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class RiskAlert:
    id: str
    severity: Literal["info", "warning", "critical"]
    title: str
    message: str
    metric_key: str
    current_value: float | None
    threshold: float | None
    candidate_action: str
    meta: DataSourceMeta
    title_ko: str | None = None
    body_ko: str | None = None
    review_action_ko: str | None = None
    display_severity_ko: str | None = None
    data_mode: str = "unavailable"
    actionability: str = "review_only"
    holdings_source: str | None = None
    holdings_source_label_ko: str | None = None
    price_source: str | None = None
    price_source_label_ko: str | None = None
    sector_metadata_source: str | None = None
    sector_metadata_source_label_ko: str | None = None
    calculation_method: str = "concentration_threshold_rule"
    calculation_method_label_ko: str = "집중도 기준 규칙"
    as_of_date: str | None = None
    fetched_at: str | None = None
    fetched_at_ko: str | None = None
    stale_data_flag: bool = False
    is_mock: bool = False
    is_stale: bool = False
    confidence_score: int | None = None
    accuracy_grade: str = "unavailable"
    accuracy_grade_ko: str | None = None
    missing_inputs: tuple[str, ...] = field(default_factory=tuple)
    unit: str | None = None
    affected_asset: str | None = None
    affected_sector: str | None = None
    explanation_ko: str | None = None
    next_step_ko: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "metric_key": self.metric_key,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "candidate_action": self.candidate_action,
            "meta": self.meta.to_dict(),
            "title_ko": self.title_ko,
            "body_ko": self.body_ko,
            "review_action_ko": self.review_action_ko,
            "display_severity_ko": self.display_severity_ko,
            "data_mode": self.data_mode,
            "actionability": self.actionability,
            "holdings_source": self.holdings_source,
            "holdings_source_label_ko": self.holdings_source_label_ko,
            "price_source": self.price_source,
            "price_source_label_ko": self.price_source_label_ko,
            "sector_metadata_source": self.sector_metadata_source,
            "sector_metadata_source_label_ko": self.sector_metadata_source_label_ko,
            "calculation_method": self.calculation_method,
            "calculation_method_label_ko": self.calculation_method_label_ko,
            "as_of_date": self.as_of_date,
            "fetched_at": self.fetched_at,
            "fetched_at_ko": self.fetched_at_ko,
            "stale_data_flag": self.stale_data_flag,
            "is_mock": self.is_mock,
            "is_stale": self.is_stale,
            "confidence_score": self.confidence_score,
            "accuracy_grade": self.accuracy_grade,
            "accuracy_grade_ko": self.accuracy_grade_ko,
            "missing_inputs": list(self.missing_inputs),
            "unit": self.unit,
            "affected_asset": self.affected_asset,
            "affected_sector": self.affected_sector,
            "explanation_ko": self.explanation_ko,
            "next_step_ko": self.next_step_ko,
        }


@dataclass(frozen=True)
class SourceCoverageRow:
    module_key: str
    label: str
    coverage_status: str
    required_api_keys: tuple[str, ...]
    missing_api_keys: tuple[str, ...]
    notes: tuple[str, ...]
    meta: DataSourceMeta
    category: str | None = None
    category_label_ko: str | None = None
    active_source_id: str | None = None
    active_source_label_ko: str | None = None
    adapter_id: str | None = None
    status: str | None = None
    status_label_ko: str | None = None
    accuracy_grade: str = "unavailable"
    accuracy_grade_label_ko: str | None = None
    exactness_level: str = "unavailable"
    exactness_label_ko: str | None = None
    missing_keys: tuple[str, ...] = field(default_factory=tuple)
    required_keys: tuple[str, ...] = field(default_factory=tuple)
    optional_keys: tuple[str, ...] = field(default_factory=tuple)
    has_required_keys: bool = True
    source_endpoint: str | None = None
    cache_age: str | None = None
    message_ko: str | None = None
    action_required_ko: str | None = None
    is_mock: bool = False
    is_planned: bool = False
    is_keyless: bool = False
    is_trade_safe: bool = False
    can_compute_exact_value: bool = False
    can_compute_best_effort_value: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_key": self.module_key,
            "label": self.label,
            "coverage_status": self.coverage_status,
            "required_api_keys": list(self.required_api_keys),
            "missing_api_keys": list(self.missing_api_keys),
            "notes": list(self.notes),
            "meta": self.meta.to_dict(),
            "category": self.category,
            "category_label_ko": self.category_label_ko,
            "active_source_id": self.active_source_id,
            "active_source_label_ko": self.active_source_label_ko,
            "adapter_id": self.adapter_id,
            "status": self.status or self.coverage_status,
            "status_label_ko": self.status_label_ko,
            "accuracy_grade": self.accuracy_grade,
            "accuracy_grade_label_ko": self.accuracy_grade_label_ko,
            "exactness_level": self.exactness_level,
            "exactness_label_ko": self.exactness_label_ko,
            "missing_keys": list(self.missing_keys or self.missing_api_keys),
            "required_keys": list(self.required_keys or self.required_api_keys),
            "optional_keys": list(self.optional_keys),
            "has_required_keys": self.has_required_keys,
            "source_endpoint": self.source_endpoint or self.meta.source_table_or_endpoint,
            "cache_age": self.cache_age,
            "message_ko": self.message_ko,
            "action_required_ko": self.action_required_ko,
            "is_mock": self.is_mock,
            "is_planned": self.is_planned,
            "is_keyless": self.is_keyless,
            "is_trade_safe": self.is_trade_safe,
            "can_compute_exact_value": self.can_compute_exact_value,
            "can_compute_best_effort_value": self.can_compute_best_effort_value,
        }


@dataclass(frozen=True)
class DataTrustSourcePanelState(ModuleState):
    latest_refresh_time: str | None = None
    point_in_time_status: str = "review_required"
    source_coverage: tuple[SourceCoverageRow, ...] = field(default_factory=tuple)
    stale_sources: tuple[str, ...] = field(default_factory=tuple)
    missing_sources: tuple[str, ...] = field(default_factory=tuple)
    missing_api_keys: tuple[str, ...] = field(default_factory=tuple)
    api_path: str = "/api/dashboard/data-trust"

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "latest_refresh_time": self.latest_refresh_time,
                "point_in_time_status": self.point_in_time_status,
                "source_coverage": [item.to_dict() for item in self.source_coverage],
                "stale_sources": list(self.stale_sources),
                "missing_sources": list(self.missing_sources),
                "missing_api_keys": list(self.missing_api_keys),
                "api_path": self.api_path,
            }
        )
        return base


@dataclass(frozen=True)
class MacroIndicatorRow:
    key: str
    label: str
    value: float | None
    change: float | None
    unit: str
    score: int
    contribution: float
    signal: Literal["tailwind", "neutral", "headwind", "missing"]
    meta: DataSourceMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "change": self.change,
            "unit": self.unit,
            "score": self.score,
            "contribution": self.contribution,
            "signal": self.signal,
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class SectorTailwindRow:
    sector: str
    tailwind_score: int
    label: Literal["tailwind", "neutral", "headwind"]
    positive_drivers: tuple[str, ...]
    negative_drivers: tuple[str, ...]
    meta: DataSourceMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "sector": self.sector,
            "tailwind_score": self.tailwind_score,
            "label": self.label,
            "positive_drivers": list(self.positive_drivers),
            "negative_drivers": list(self.negative_drivers),
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class RecentMacroChange:
    key: str
    label: str
    change_text: str
    impact: Literal["positive", "neutral", "negative"]
    meta: DataSourceMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "change_text": self.change_text,
            "impact": self.impact,
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class MarketRegimeMacroRadarState(ModuleState):
    current_regime_label: str = "RISK_OFF"
    regime_labels: tuple[str, ...] = field(default_factory=tuple)
    regime_score: int = 50
    macro_heatmap: tuple[MacroIndicatorRow, ...] = field(default_factory=tuple)
    sector_tailwinds: tuple[SectorTailwindRow, ...] = field(default_factory=tuple)
    recent_changes: tuple[RecentMacroChange, ...] = field(default_factory=tuple)
    latest_source_at: str | None = None
    api_path: str = "/api/dashboard/market-regime"

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "current_regime_label": self.current_regime_label,
                "regime_labels": list(self.regime_labels),
                "regime_score": self.regime_score,
                "macro_heatmap": [item.to_dict() for item in self.macro_heatmap],
                "sector_tailwinds": [item.to_dict() for item in self.sector_tailwinds],
                "recent_changes": [item.to_dict() for item in self.recent_changes],
                "latest_source_at": self.latest_source_at,
                "api_path": self.api_path,
            }
        )
        return base


@dataclass(frozen=True)
class FXRatesIndicatorRow:
    key: str
    label: str
    value: float | None
    change: float | None
    unit: str
    pressure_score: int
    signal: Literal["supportive", "neutral", "pressure", "missing"]
    meta: DataSourceMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "change": self.change,
            "unit": self.unit,
            "pressure_score": self.pressure_score,
            "signal": self.signal,
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class FXRatesImpactRow:
    channel: str
    favored: str
    pressured: str
    interpretation: str
    impact_score: int
    meta: DataSourceMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "favored": self.favored,
            "pressured": self.pressured,
            "interpretation": self.interpretation,
            "impact_score": self.impact_score,
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class KRWRatesFXDashboardState(ModuleState):
    fx_shock_score: int = 50
    fx_shock_label: str = "NEUTRAL"
    rate_shock_score: int = 50
    rate_shock_label: str = "NEUTRAL"
    yield_curve_slope: float | None = None
    portfolio_krw_impact_pct: float | None = None
    indicators: tuple[FXRatesIndicatorRow, ...] = field(default_factory=tuple)
    impact_rows: tuple[FXRatesImpactRow, ...] = field(default_factory=tuple)
    latest_source_at: str | None = None
    api_path: str = "/api/dashboard/krw-rates-fx"

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "fx_shock_score": self.fx_shock_score,
                "fx_shock_label": self.fx_shock_label,
                "rate_shock_score": self.rate_shock_score,
                "rate_shock_label": self.rate_shock_label,
                "yield_curve_slope": self.yield_curve_slope,
                "portfolio_krw_impact_pct": self.portfolio_krw_impact_pct,
                "indicators": [item.to_dict() for item in self.indicators],
                "impact_rows": [item.to_dict() for item in self.impact_rows],
                "latest_source_at": self.latest_source_at,
                "api_path": self.api_path,
            }
        )
        return base


@dataclass(frozen=True)
class ValuationMetricRow:
    code: str
    name: str
    sector: str
    per: float | None
    forward_per: float | None
    pbr: float | None
    psr: float | None
    ev_ebitda: float | None
    dividend_yield: float | None
    fcf_yield: float | None
    earnings_yield: float | None
    sector_relative_per: float | None
    sector_relative_pbr: float | None
    historical_percentile: float | None
    pbr_below_1: bool
    quality_score: int | None
    quality_trend: str
    valuation_label: Literal["cheap", "fair", "expensive", "missing"]
    interpretation: str
    meta: DataSourceMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "sector": self.sector,
            "per": self.per,
            "forward_per": self.forward_per,
            "pbr": self.pbr,
            "psr": self.psr,
            "ev_ebitda": self.ev_ebitda,
            "dividend_yield": self.dividend_yield,
            "fcf_yield": self.fcf_yield,
            "earnings_yield": self.earnings_yield,
            "sector_relative_per": self.sector_relative_per,
            "sector_relative_pbr": self.sector_relative_pbr,
            "historical_percentile": self.historical_percentile,
            "pbr_below_1": self.pbr_below_1,
            "quality_score": self.quality_score,
            "quality_trend": self.quality_trend,
            "valuation_label": self.valuation_label,
            "interpretation": self.interpretation,
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class SectorValuationRow:
    sector: str
    average_per: float | None
    average_pbr: float | None
    median_percentile: float | None
    cheap_count: int
    expensive_count: int
    signal: Literal["cheap", "fair", "expensive", "mixed", "missing"]
    meta: DataSourceMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "sector": self.sector,
            "average_per": self.average_per,
            "average_pbr": self.average_pbr,
            "median_percentile": self.median_percentile,
            "cheap_count": self.cheap_count,
            "expensive_count": self.expensive_count,
            "signal": self.signal,
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class ValuationRelativeCheapnessPanelState(ModuleState):
    market_percentile: float | None = None
    cheap_count: int = 0
    expensive_count: int = 0
    valuation_rows: tuple[ValuationMetricRow, ...] = field(default_factory=tuple)
    cheapest_quality_candidates: tuple[ValuationMetricRow, ...] = field(default_factory=tuple)
    sector_heatmap: tuple[SectorValuationRow, ...] = field(default_factory=tuple)
    percentile_table: tuple[ValuationMetricRow, ...] = field(default_factory=tuple)
    expensive_list: tuple[ValuationMetricRow, ...] = field(default_factory=tuple)
    latest_source_at: str | None = None
    api_path: str = "/api/dashboard/valuation"

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "market_percentile": self.market_percentile,
                "cheap_count": self.cheap_count,
                "expensive_count": self.expensive_count,
                "valuation_rows": [item.to_dict() for item in self.valuation_rows],
                "cheapest_quality_candidates": [item.to_dict() for item in self.cheapest_quality_candidates],
                "sector_heatmap": [item.to_dict() for item in self.sector_heatmap],
                "percentile_table": [item.to_dict() for item in self.percentile_table],
                "expensive_list": [item.to_dict() for item in self.expensive_list],
                "latest_source_at": self.latest_source_at,
                "api_path": self.api_path,
            }
        )
        return base


@dataclass(frozen=True)
class FundamentalQualityRow:
    code: str
    name: str
    sector: str
    revenue_growth: float | None
    operating_income_growth: float | None
    roe: float | None
    roa: float | None
    roic: float | None
    gross_margin: float | None
    operating_margin: float | None
    net_margin: float | None
    cfo_to_net_income: float | None
    fcf_conversion: float | None
    accrual_ratio: float | None
    debt_to_equity: float | None
    net_debt_to_ebitda: float | None
    interest_coverage: float | None
    piotroski_f_score: int | None
    altman_z_score_proxy: float | None
    profitability_score: int
    cash_flow_quality_score: int
    balance_sheet_safety_score: int
    growth_consistency_score: int
    accounting_risk_inverse_score: int
    quality_score: int
    quality_label: Literal["top_quality", "improving", "watch", "deteriorating", "missing"]
    valuation_percentile: float | None
    per: float | None
    pbr: float | None
    available_at: str | None
    accounting_flags: tuple[str, ...]
    meta: DataSourceMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "sector": self.sector,
            "revenue_growth": self.revenue_growth,
            "operating_income_growth": self.operating_income_growth,
            "roe": self.roe,
            "roa": self.roa,
            "roic": self.roic,
            "gross_margin": self.gross_margin,
            "operating_margin": self.operating_margin,
            "net_margin": self.net_margin,
            "cfo_to_net_income": self.cfo_to_net_income,
            "fcf_conversion": self.fcf_conversion,
            "accrual_ratio": self.accrual_ratio,
            "debt_to_equity": self.debt_to_equity,
            "net_debt_to_ebitda": self.net_debt_to_ebitda,
            "interest_coverage": self.interest_coverage,
            "piotroski_f_score": self.piotroski_f_score,
            "altman_z_score_proxy": self.altman_z_score_proxy,
            "profitability_score": self.profitability_score,
            "cash_flow_quality_score": self.cash_flow_quality_score,
            "balance_sheet_safety_score": self.balance_sheet_safety_score,
            "growth_consistency_score": self.growth_consistency_score,
            "accounting_risk_inverse_score": self.accounting_risk_inverse_score,
            "quality_score": self.quality_score,
            "quality_label": self.quality_label,
            "valuation_percentile": self.valuation_percentile,
            "per": self.per,
            "pbr": self.pbr,
            "available_at": self.available_at,
            "accounting_flags": list(self.accounting_flags),
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class ROICValuationPoint:
    code: str
    name: str
    sector: str
    roic: float | None
    valuation_percentile: float | None
    quality_score: int
    meta: DataSourceMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "sector": self.sector,
            "roic": self.roic,
            "valuation_percentile": self.valuation_percentile,
            "quality_score": self.quality_score,
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class FundamentalQualityPanelState(ModuleState):
    quality_rows: tuple[FundamentalQualityRow, ...] = field(default_factory=tuple)
    top_quality_stocks: tuple[FundamentalQualityRow, ...] = field(default_factory=tuple)
    deteriorating_quality_stocks: tuple[FundamentalQualityRow, ...] = field(default_factory=tuple)
    cheap_quality_stocks: tuple[FundamentalQualityRow, ...] = field(default_factory=tuple)
    accounting_red_flags: tuple[FundamentalQualityRow, ...] = field(default_factory=tuple)
    fcf_conversion_ranking: tuple[FundamentalQualityRow, ...] = field(default_factory=tuple)
    roic_vs_valuation: tuple[ROICValuationPoint, ...] = field(default_factory=tuple)
    latest_source_at: str | None = None
    api_path: str = "/api/dashboard/fundamental-quality"

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "quality_rows": [item.to_dict() for item in self.quality_rows],
                "top_quality_stocks": [item.to_dict() for item in self.top_quality_stocks],
                "deteriorating_quality_stocks": [item.to_dict() for item in self.deteriorating_quality_stocks],
                "cheap_quality_stocks": [item.to_dict() for item in self.cheap_quality_stocks],
                "accounting_red_flags": [item.to_dict() for item in self.accounting_red_flags],
                "fcf_conversion_ranking": [item.to_dict() for item in self.fcf_conversion_ranking],
                "roic_vs_valuation": [item.to_dict() for item in self.roic_vs_valuation],
                "latest_source_at": self.latest_source_at,
                "api_path": self.api_path,
            }
        )
        return base


@dataclass(frozen=True)
class DARTDisclosureEventRow:
    receipt_no: str
    code: str
    name: str
    title: str
    category: str
    sentiment: Literal["positive", "negative", "neutral"]
    materiality_score: int
    catalyst_score: int
    dilution_risk_score: int
    governance_risk_score: int
    event_summary: str
    source_filing_reference: str | None
    receipt_date: str | None
    available_at: str | None
    meta: DataSourceMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_no": self.receipt_no,
            "code": self.code,
            "name": self.name,
            "title": self.title,
            "category": self.category,
            "sentiment": self.sentiment,
            "materiality_score": self.materiality_score,
            "catalyst_score": self.catalyst_score,
            "dilution_risk_score": self.dilution_risk_score,
            "governance_risk_score": self.governance_risk_score,
            "event_summary": self.event_summary,
            "source_filing_reference": self.source_filing_reference,
            "receipt_date": self.receipt_date,
            "available_at": self.available_at,
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class DARTDisclosureCatalystPanelState(ModuleState):
    event_rows: tuple[DARTDisclosureEventRow, ...] = field(default_factory=tuple)
    latest_high_materiality_disclosures: tuple[DARTDisclosureEventRow, ...] = field(default_factory=tuple)
    positive_catalysts: tuple[DARTDisclosureEventRow, ...] = field(default_factory=tuple)
    negative_risks: tuple[DARTDisclosureEventRow, ...] = field(default_factory=tuple)
    dilution_watchlist: tuple[DARTDisclosureEventRow, ...] = field(default_factory=tuple)
    shareholder_return_announcements: tuple[DARTDisclosureEventRow, ...] = field(default_factory=tuple)
    event_timeline: tuple[DARTDisclosureEventRow, ...] = field(default_factory=tuple)
    latest_source_at: str | None = None
    api_path: str = "/api/dashboard/dart-catalysts"

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "event_rows": [item.to_dict() for item in self.event_rows],
                "latest_high_materiality_disclosures": [item.to_dict() for item in self.latest_high_materiality_disclosures],
                "positive_catalysts": [item.to_dict() for item in self.positive_catalysts],
                "negative_risks": [item.to_dict() for item in self.negative_risks],
                "dilution_watchlist": [item.to_dict() for item in self.dilution_watchlist],
                "shareholder_return_announcements": [item.to_dict() for item in self.shareholder_return_announcements],
                "event_timeline": [item.to_dict() for item in self.event_timeline],
                "latest_source_at": self.latest_source_at,
                "api_path": self.api_path,
            }
        )
        return base


@dataclass(frozen=True)
class SmartMoneyFlowRow:
    code: str
    name: str
    sector: str
    foreign_net_buy_5d: float | None
    foreign_net_buy_20d: float | None
    foreign_net_buy_60d: float | None
    institution_net_buy_5d: float | None
    institution_net_buy_20d: float | None
    institution_net_buy_60d: float | None
    individual_net_buy_5d: float | None
    individual_net_buy_20d: float | None
    individual_net_buy_60d: float | None
    pension_net_buy: float | None
    program_net_buy: float | None
    foreign_ownership_change: float | None
    flow_z_score: float | None
    accumulation_persistence: int
    distribution_risk_score: int
    short_sell_ratio: float | None
    short_position_ratio: float | None
    days_to_cover: float | None
    short_pressure_score: int
    short_squeeze_score: int
    fragility_score: int
    trading_value_20d: float | None
    turnover: float | None
    volatility: float | None
    capacity_estimate: float | None
    illiquidity_warning: str | None
    meta: DataSourceMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "sector": self.sector,
            "foreign_net_buy_5d": self.foreign_net_buy_5d,
            "foreign_net_buy_20d": self.foreign_net_buy_20d,
            "foreign_net_buy_60d": self.foreign_net_buy_60d,
            "institution_net_buy_5d": self.institution_net_buy_5d,
            "institution_net_buy_20d": self.institution_net_buy_20d,
            "institution_net_buy_60d": self.institution_net_buy_60d,
            "individual_net_buy_5d": self.individual_net_buy_5d,
            "individual_net_buy_20d": self.individual_net_buy_20d,
            "individual_net_buy_60d": self.individual_net_buy_60d,
            "pension_net_buy": self.pension_net_buy,
            "program_net_buy": self.program_net_buy,
            "foreign_ownership_change": self.foreign_ownership_change,
            "flow_z_score": self.flow_z_score,
            "accumulation_persistence": self.accumulation_persistence,
            "distribution_risk_score": self.distribution_risk_score,
            "short_sell_ratio": self.short_sell_ratio,
            "short_position_ratio": self.short_position_ratio,
            "days_to_cover": self.days_to_cover,
            "short_pressure_score": self.short_pressure_score,
            "short_squeeze_score": self.short_squeeze_score,
            "fragility_score": self.fragility_score,
            "trading_value_20d": self.trading_value_20d,
            "turnover": self.turnover,
            "volatility": self.volatility,
            "capacity_estimate": self.capacity_estimate,
            "illiquidity_warning": self.illiquidity_warning,
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class SectorFlowHeatmapRow:
    sector: str
    foreign_flow_score: int
    institution_flow_score: int
    retail_crowding_score: int
    short_pressure_score: int
    liquidity_score: int
    signal: Literal["accumulation", "distribution", "crowded", "fragile", "mixed", "missing"]
    meta: DataSourceMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "sector": self.sector,
            "foreign_flow_score": self.foreign_flow_score,
            "institution_flow_score": self.institution_flow_score,
            "retail_crowding_score": self.retail_crowding_score,
            "short_pressure_score": self.short_pressure_score,
            "liquidity_score": self.liquidity_score,
            "signal": self.signal,
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class SmartMoneyFlowShortPressurePanelState(ModuleState):
    flow_rows: tuple[SmartMoneyFlowRow, ...] = field(default_factory=tuple)
    foreign_accumulation_leaderboard: tuple[SmartMoneyFlowRow, ...] = field(default_factory=tuple)
    institution_accumulation_leaderboard: tuple[SmartMoneyFlowRow, ...] = field(default_factory=tuple)
    retail_crowding_list: tuple[SmartMoneyFlowRow, ...] = field(default_factory=tuple)
    short_squeeze_candidates: tuple[SmartMoneyFlowRow, ...] = field(default_factory=tuple)
    fragile_long_candidates: tuple[SmartMoneyFlowRow, ...] = field(default_factory=tuple)
    distribution_risk_list: tuple[SmartMoneyFlowRow, ...] = field(default_factory=tuple)
    sector_flow_heatmap: tuple[SectorFlowHeatmapRow, ...] = field(default_factory=tuple)
    latest_source_at: str | None = None
    api_path: str = "/api/dashboard/flow-short-pressure"

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "flow_rows": [item.to_dict() for item in self.flow_rows],
                "foreign_accumulation_leaderboard": [item.to_dict() for item in self.foreign_accumulation_leaderboard],
                "institution_accumulation_leaderboard": [item.to_dict() for item in self.institution_accumulation_leaderboard],
                "retail_crowding_list": [item.to_dict() for item in self.retail_crowding_list],
                "short_squeeze_candidates": [item.to_dict() for item in self.short_squeeze_candidates],
                "fragile_long_candidates": [item.to_dict() for item in self.fragile_long_candidates],
                "distribution_risk_list": [item.to_dict() for item in self.distribution_risk_list],
                "sector_flow_heatmap": [item.to_dict() for item in self.sector_flow_heatmap],
                "latest_source_at": self.latest_source_at,
                "api_path": self.api_path,
            }
        )
        return base


@dataclass(frozen=True)
class ForwardAlphaRankRow:
    code: str
    name: str
    sector: str
    market: str
    final_alpha_score: int
    confidence_score: int
    rating: Literal["STRONG_BUY_CANDIDATE", "BUY_CANDIDATE", "WATCH", "HOLD", "AVOID", "HIGH_RISK_EXCLUDE"]
    valuation_score: int | None
    quality_score: int | None
    catalyst_score: int | None
    value_up_score: int | None
    smart_money_score: int | None
    short_pressure_score: int | None
    macro_score: int | None
    liquidity_score: int | None
    risk_penalty: int
    positive_drivers: tuple[str, ...]
    negative_drivers: tuple[str, ...]
    risk_flags: tuple[str, ...]
    stale_data_warning: str | None
    score_version: str
    feature_snapshot_id: str
    meta: DataSourceMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "sector": self.sector,
            "market": self.market,
            "final_alpha_score": self.final_alpha_score,
            "confidence_score": self.confidence_score,
            "rating": self.rating,
            "valuation_score": self.valuation_score,
            "quality_score": self.quality_score,
            "catalyst_score": self.catalyst_score,
            "value_up_score": self.value_up_score,
            "smart_money_score": self.smart_money_score,
            "short_pressure_score": self.short_pressure_score,
            "macro_score": self.macro_score,
            "liquidity_score": self.liquidity_score,
            "risk_penalty": self.risk_penalty,
            "positive_drivers": list(self.positive_drivers),
            "negative_drivers": list(self.negative_drivers),
            "risk_flags": list(self.risk_flags),
            "stale_data_warning": self.stale_data_warning,
            "score_version": self.score_version,
            "feature_snapshot_id": self.feature_snapshot_id,
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class ForwardAlphaRankingPanelState(ModuleState):
    ranking_rows: tuple[ForwardAlphaRankRow, ...] = field(default_factory=tuple)
    strong_buy_candidates: tuple[ForwardAlphaRankRow, ...] = field(default_factory=tuple)
    buy_candidates: tuple[ForwardAlphaRankRow, ...] = field(default_factory=tuple)
    watchlist: tuple[ForwardAlphaRankRow, ...] = field(default_factory=tuple)
    hold_or_avoid: tuple[ForwardAlphaRankRow, ...] = field(default_factory=tuple)
    high_risk_exclusions: tuple[ForwardAlphaRankRow, ...] = field(default_factory=tuple)
    score_version: str = "baseline_rule_score_v1"
    feature_snapshot_id: str | None = None
    latest_source_at: str | None = None
    api_path: str = "/api/dashboard/forward-alpha-ranking"

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "ranking_rows": [item.to_dict() for item in self.ranking_rows],
                "strong_buy_candidates": [item.to_dict() for item in self.strong_buy_candidates],
                "buy_candidates": [item.to_dict() for item in self.buy_candidates],
                "watchlist": [item.to_dict() for item in self.watchlist],
                "hold_or_avoid": [item.to_dict() for item in self.hold_or_avoid],
                "high_risk_exclusions": [item.to_dict() for item in self.high_risk_exclusions],
                "score_version": self.score_version,
                "feature_snapshot_id": self.feature_snapshot_id,
                "latest_source_at": self.latest_source_at,
                "api_path": self.api_path,
            }
        )
        return base


@dataclass(frozen=True)
class OptimizerRecommendationRow:
    code: str
    name: str
    sector: str
    market: str
    current_weight: float
    target_weight: float
    weight_delta: float
    current_value: float
    target_value: float
    trade_value_estimate: float
    action: Literal["BUY", "ADD", "HOLD", "TRIM", "SELL", "AVOID", "EXCLUDE"]
    final_alpha_score: int | None
    confidence_score: int | None
    liquidity_score: int | None
    transaction_cost_bps: float | None
    reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    risk_flags: tuple[str, ...]
    meta: DataSourceMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "sector": self.sector,
            "market": self.market,
            "current_weight": self.current_weight,
            "target_weight": self.target_weight,
            "weight_delta": self.weight_delta,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "trade_value_estimate": self.trade_value_estimate,
            "action": self.action,
            "final_alpha_score": self.final_alpha_score,
            "confidence_score": self.confidence_score,
            "liquidity_score": self.liquidity_score,
            "transaction_cost_bps": self.transaction_cost_bps,
            "reasons": list(self.reasons),
            "rejection_reasons": list(self.rejection_reasons),
            "risk_flags": list(self.risk_flags),
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class PortfolioAlertRow:
    alert_id: str
    alert_type: Literal[
        "concentration_warning",
        "sector_overweight",
        "stale_data_warning",
        "top_holding_score_downgrade",
        "negative_dart_event",
        "liquidity_deterioration",
        "fx_shock",
        "rate_shock",
        "model_score_deterioration",
    ]
    severity: Literal["info", "warning", "critical"]
    code: str | None
    title: str
    message: str
    trigger_value: float | None
    threshold: float | None
    recommended_review: str
    meta: DataSourceMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "code": self.code,
            "title": self.title,
            "message": self.message,
            "trigger_value": self.trigger_value,
            "threshold": self.threshold,
            "recommended_review": self.recommended_review,
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class StressScenarioRow:
    scenario_id: str
    name: str
    estimated_portfolio_impact_pct: float
    most_affected: tuple[str, ...]
    explanation: str
    meta: DataSourceMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "estimated_portfolio_impact_pct": self.estimated_portfolio_impact_pct,
            "most_affected": list(self.most_affected),
            "explanation": self.explanation,
            "meta": self.meta.to_dict(),
        }


@dataclass(frozen=True)
class PortfolioOptimizerAlertCenterState(ModuleState):
    recommendation_rows: tuple[OptimizerRecommendationRow, ...] = field(default_factory=tuple)
    rejected_candidates: tuple[OptimizerRecommendationRow, ...] = field(default_factory=tuple)
    alerts: tuple[PortfolioAlertRow, ...] = field(default_factory=tuple)
    stress_scenarios: tuple[StressScenarioRow, ...] = field(default_factory=tuple)
    total_portfolio_value: float = 0.0
    cash_ratio: float = 0.0
    target_cash_ratio: float = 0.05
    max_single_stock_weight: float = 0.07
    max_kosdaq_single_stock_weight: float = 0.05
    max_sector_weight: float = 0.30
    latest_source_at: str | None = None
    optimizer_api_path: str = "/api/dashboard/portfolio-optimizer"
    alerts_api_path: str = "/api/dashboard/alerts"

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "recommendation_rows": [item.to_dict() for item in self.recommendation_rows],
                "rejected_candidates": [item.to_dict() for item in self.rejected_candidates],
                "alerts": [item.to_dict() for item in self.alerts],
                "stress_scenarios": [item.to_dict() for item in self.stress_scenarios],
                "total_portfolio_value": self.total_portfolio_value,
                "cash_ratio": self.cash_ratio,
                "target_cash_ratio": self.target_cash_ratio,
                "max_single_stock_weight": self.max_single_stock_weight,
                "max_kosdaq_single_stock_weight": self.max_kosdaq_single_stock_weight,
                "max_sector_weight": self.max_sector_weight,
                "latest_source_at": self.latest_source_at,
                "optimizer_api_path": self.optimizer_api_path,
                "alerts_api_path": self.alerts_api_path,
            }
        )
        return base


@dataclass(frozen=True)
class PortfolioRiskCockpitState(ModuleState):
    asset_allocation: tuple[AllocationSlice, ...] = field(default_factory=tuple)
    market_allocation: tuple[AllocationSlice, ...] = field(default_factory=tuple)
    sector_allocation: tuple[AllocationSlice, ...] = field(default_factory=tuple)
    currency_allocation: tuple[AllocationSlice, ...] = field(default_factory=tuple)
    top_holdings: tuple[HoldingRiskRow, ...] = field(default_factory=tuple)
    top5_holdings: tuple[HoldingRiskRow, ...] = field(default_factory=tuple)
    risk_alerts: tuple[RiskAlert, ...] = field(default_factory=tuple)
    api_path: str = "/api/dashboard/portfolio-risk"

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "asset_allocation": [item.to_dict() for item in self.asset_allocation],
                "market_allocation": [item.to_dict() for item in self.market_allocation],
                "sector_allocation": [item.to_dict() for item in self.sector_allocation],
                "currency_allocation": [item.to_dict() for item in self.currency_allocation],
                "top_holdings": [item.to_dict() for item in self.top_holdings],
                "top5_holdings": [item.to_dict() for item in self.top5_holdings],
                "risk_alerts": [item.to_dict() for item in self.risk_alerts],
                "api_path": self.api_path,
            }
        )
        return base
