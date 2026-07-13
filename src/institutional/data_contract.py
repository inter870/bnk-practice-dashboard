from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from .models import DataMode, DataSourceMeta, ProviderResult


QUALITY_FORMULA_VERSION = "p0-v1"
QUALITY_COMPONENT_KEYS = (
    "completeness",
    "freshness",
    "source_reliability",
    "cross_source_agreement",
    "schema_validity",
    "outlier_status",
    "fallback_penalty",
    "revision_risk",
)


def normalize_data_mode(value: Any, *, stale: bool = False, fallback: bool = False) -> DataMode:
    text = str(value or "").strip().upper()
    aliases = {
        "READY": "LIVE",
        "MANUAL": "LIVE",
        "NEAR_REALTIME": "DELAYED",
        "CACHE": "DELAYED",
        "MOCK": "DEMO",
        "PLANNED": "DISCONNECTED",
        "EMPTY": "UNAVAILABLE",
    }
    text = aliases.get(text, text)
    if text == "DEMO":
        return "DEMO"
    if text in {"ERROR", "DISCONNECTED", "UNAVAILABLE"}:
        return text  # type: ignore[return-value]
    if stale:
        return "STALE"
    if fallback:
        return "FALLBACK"
    if text in {"LIVE", "DELAYED"}:
        return text  # type: ignore[return-value]
    return "UNAVAILABLE"


def calculate_quality_components(values: Mapping[str, Any]) -> tuple[int, dict[str, int]]:
    components: dict[str, int] = {}
    for key in QUALITY_COMPONENT_KEYS:
        default = 0 if key == "fallback_penalty" else 100
        try:
            number = int(round(float(values.get(key, default))))
        except (TypeError, ValueError):
            number = default
        components[key] = max(-100 if key == "fallback_penalty" else 0, min(100, number))
    positive_keys = tuple(key for key in QUALITY_COMPONENT_KEYS if key != "fallback_penalty")
    score = sum(components[key] for key in positive_keys) / len(positive_keys)
    score += components["fallback_penalty"]
    return max(0, min(100, int(round(score)))), components


def investment_eligibility(meta: DataSourceMeta) -> tuple[bool, tuple[str, ...]]:
    mode = normalize_data_mode(meta.data_mode, stale=meta.stale_data_flag, fallback=meta.is_fallback)
    reasons: list[str] = []
    if mode in {"DEMO", "STALE", "DISCONNECTED", "ERROR", "UNAVAILABLE"}:
        reasons.append(f"data_mode_{mode.lower()}")
    if meta.missing_data_flag:
        reasons.append("missing_data")
    if not meta.available_at and mode not in {"DELAYED", "FALLBACK"}:
        reasons.append("available_at_missing")
    if meta.errors:
        reasons.append("provider_error")
    return not reasons, tuple(dict.fromkeys(reasons))


def normalize_provider_result(result: ProviderResult[Any]) -> ProviderResult[Any]:
    score, components = calculate_quality_components(result.meta.quality_components)
    mode = normalize_data_mode(
        result.meta.data_mode or result.status,
        stale=result.meta.stale_data_flag,
        fallback=result.meta.is_fallback,
    )
    meta = replace(
        result.meta,
        data_mode=mode,
        quality_score=score if result.meta.quality_components else result.meta.quality_score,
        quality_components=components if result.meta.quality_components else {},
        quality_formula_version=(
            QUALITY_FORMULA_VERSION if result.meta.quality_components else result.meta.quality_formula_version
        ),
        as_of=result.meta.as_of or result.meta.as_of_date,
    )
    eligible, reasons = investment_eligibility(meta)
    meta = replace(meta, investment_eligible=eligible, quality_flags=tuple(dict.fromkeys((*meta.quality_flags, *reasons))))
    return replace(result, meta=meta)
