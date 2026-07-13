from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import math
from typing import Any, Mapping


def ensure_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


@dataclass(frozen=True)
class SourceMeta:
    source: str
    provider_version: str
    available_at: datetime
    fetched_at: datetime
    mode: str
    quality_score: int
    is_stale: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        ensure_aware(self.available_at, "available_at")
        ensure_aware(self.fetched_at, "fetched_at")


@dataclass(frozen=True)
class Security:
    instrument_id: str
    ticker: str
    name_ko: str
    market: str
    venue: str
    sector: str
    size_bucket: str
    listed_at: datetime
    delisted_at: datetime | None = None
    is_active: bool = True

    def __post_init__(self) -> None:
        ensure_aware(self.listed_at, "listed_at")
        if self.delisted_at is not None:
            ensure_aware(self.delisted_at, "delisted_at")


@dataclass(frozen=True)
class PITObservation:
    instrument_id: str
    field: str
    value: float | str | bool | None
    period_end: datetime | None
    filed_at: datetime | None
    published_at: datetime | None
    available_at: datetime
    restated_at: datetime | None
    source: str
    unit: str

    def __post_init__(self) -> None:
        ensure_aware(self.available_at, "available_at")
        for name in ("period_end", "filed_at", "published_at", "restated_at"):
            value = getattr(self, name)
            if value is not None:
                ensure_aware(value, name)

    def eligible_at(self, decision_time: datetime) -> bool:
        return self.available_at <= ensure_aware(decision_time, "decision_time")


@dataclass(frozen=True)
class MarketBar:
    instrument_id: str
    venue: str
    bar_start: datetime
    bar_end: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover_krw: float
    available_at: datetime
    is_suspended: bool = False
    is_vi: bool = False
    limit_state: str | None = None

    def __post_init__(self) -> None:
        for name in ("bar_start", "bar_end", "available_at"):
            ensure_aware(getattr(self, name), name)


@dataclass(frozen=True)
class FixtureStock:
    security: Security
    observations: tuple[PITObservation, ...]
    factor_inputs: Mapping[str, float | None]
    bars: tuple[MarketBar, ...]
    event_flags: tuple[str, ...]
    adv_20d_krw: float
    expected_order_krw: float


@dataclass(frozen=True)
class FactorValue:
    instrument_id: str
    factor_name: str
    raw_value: float | None
    winsorized_value: float | None
    neutralized_value: float | None
    z_score: float | None
    percentile: float | None
    confidence: float
    available_at: datetime
    reason_code: str


@dataclass(frozen=True)
class AlphaCandidate:
    instrument_id: str
    ticker: str
    name_ko: str
    market: str
    sector: str
    composite_score: float
    expected_gross_return: float | None
    expected_net_return: float | None
    confidence: float
    cost_estimate_bps: float
    capacity_krw: float
    suggested_max_weight: float
    rating: str
    reason_codes: tuple[str, ...]
    risk_flags: tuple[str, ...]
    decision_time: datetime
    model_version: str
    config_hash: str
    factor_values: tuple[FactorValue, ...]
    investment_eligible: bool

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["decision_time"] = self.decision_time.isoformat()
        return result


def finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
