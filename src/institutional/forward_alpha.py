from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from math import isfinite
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from .dart_catalysts import build_dart_disclosure_catalyst_panel
from .flow_short_pressure import build_smart_money_flow_short_pressure_panel
from .fundamental_quality import build_fundamental_quality_panel
from .market_regime import build_market_regime_macro_radar
from .models import (
    DARTDisclosureCatalystPanelState,
    DARTDisclosureEventRow,
    DataPoint,
    DataSourceMeta,
    ForwardAlphaRankingPanelState,
    ForwardAlphaRankRow,
    FundamentalQualityPanelState,
    FundamentalQualityRow,
    MarketRegimeMacroRadarState,
    SectorTailwindRow,
    SmartMoneyFlowRow,
    SmartMoneyFlowShortPressurePanelState,
    ValuationMetricRow,
    ValuationRelativeCheapnessPanelState,
)
from .valuation import build_valuation_relative_cheapness_panel


SCORE_VERSION = "baseline_rule_score_v1"
SEVERE_RISK_FLAGS = {
    "severe_accounting_risk",
    "severe_dilution_risk",
    "delisting_or_administrative_risk",
    "stale_data_risk",
    "liquidity_risk",
}
VALUE_UP_CATEGORIES = {"share_buyback", "treasury_stock_cancellation", "dividend_increase", "value_up_plan"}
KST = ZoneInfo("Asia/Seoul")


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
    text = str(value).strip()
    if isinstance(value, datetime):
        stamp = value
    else:
        try:
            if hasattr(value, "to_pydatetime"):
                stamp = value.to_pydatetime()
            else:
                stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if stamp.tzinfo is None:
        if len(text) == 10 and text[4:5] == "-" and text[7:8] == "-":
            stamp = stamp.replace(hour=23, minute=59, second=59, tzinfo=KST)
        else:
            stamp = stamp.replace(tzinfo=KST)
    return stamp


def _meta_is_point_in_time_safe(meta: DataSourceMeta, prediction_as_of: datetime | None) -> bool:
    stamp = _as_datetime(meta.available_at or meta.as_of_date or meta.fetched_at)
    if stamp is None:
        return False
    cutoff = prediction_as_of or datetime.now(timezone.utc)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    return stamp <= cutoff


def validate_no_label_leakage(feature_available_at: Any, prediction_as_of: Any, label_start_at: Any | None = None) -> bool:
    feature_stamp = _as_datetime(feature_available_at)
    prediction_stamp = _as_datetime(prediction_as_of)
    label_stamp = _as_datetime(label_start_at) if label_start_at is not None else prediction_stamp
    if feature_stamp is None or prediction_stamp is None or label_stamp is None:
        return False
    return feature_stamp <= prediction_stamp <= label_stamp


def _source_meta_for_rows(
    rows: Iterable[Any],
    *,
    now: datetime | None,
    stale: bool,
    missing: bool,
    fallback: bool,
    additional_metas: Iterable[DataSourceMeta] = (),
) -> DataSourceMeta:
    metas = [getattr(row, "meta", None) for row in rows if getattr(row, "meta", None) is not None]
    metas.extend(meta for meta in additional_metas if meta is not None)
    confidence_values = [(meta.confidence_score or meta.quality_score) for meta in metas]
    confidence = int(round(sum(confidence_values) / len(confidence_values))) if confidence_values else 0
    available_stamps = [
        stamp
        for meta in metas
        if (stamp := _as_datetime(meta.available_at or meta.as_of_date or meta.fetched_at)) is not None
    ]
    latest_stamp = max(available_stamps) if available_stamps else None
    latest_available = latest_stamp.isoformat(timespec="seconds") if latest_stamp is not None else None
    source_names = sorted({str(meta.source) for meta in metas if meta.source})
    return DataSourceMeta(
        source=" + ".join(source_names[:4]) if source_names else "Forward alpha feature stack",
        provider="BaselineRuleScore",
        source_url=None,
        as_of_date=(latest_available or _now_iso(now))[:10],
        available_at=latest_available,
        fetched_at=_now_iso(now),
        frequency="daily",
        unit="score",
        quality_score=max(0, min(100, confidence)),
        is_fallback=fallback,
        stale_data_flag=stale,
        source_table_or_endpoint="/api/dashboard/forward-alpha-ranking",
        confidence_score=max(0, min(100, confidence)),
        missing_data_flag=missing,
        warnings=tuple(["baseline_rule_score_only"]),
    )


def _regime_feature_metas(state: MarketRegimeMacroRadarState) -> tuple[DataSourceMeta, ...]:
    metas: list[DataSourceMeta] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for collection in (
        state.data_points,
        state.macro_heatmap,
        state.sector_tailwinds,
        state.recent_changes,
    ):
        for item in collection:
            meta = getattr(item, "meta", None)
            if meta is None:
                continue
            identity = (str(meta.source), meta.available_at, meta.source_table_or_endpoint)
            if identity in seen:
                continue
            seen.add(identity)
            metas.append(meta)
    return tuple(metas)


def _valuation_score(row: ValuationMetricRow | None) -> tuple[int | None, list[str], list[str]]:
    positives: list[str] = []
    negatives: list[str] = []
    if row is None or row.historical_percentile is None:
        return None, positives, ["valuation data unavailable"]
    score = int(round(_clamp(100 - row.historical_percentile, 0, 100)))
    if row.pbr_below_1:
        score = min(100, score + 6)
        positives.append("PBR below 1")
    if row.valuation_label == "cheap":
        positives.append("cheap versus history")
    if row.valuation_label == "expensive":
        negatives.append("expensive versus history")
    return score, positives, negatives


def _quality_score(row: FundamentalQualityRow | None) -> tuple[int | None, list[str], list[str], list[str]]:
    positives: list[str] = []
    negatives: list[str] = []
    risk_flags: list[str] = []
    if row is None:
        return None, positives, ["fundamental quality unavailable"], risk_flags
    score = row.quality_score
    if score >= 75:
        positives.append("high fundamental quality")
    if row.roic is not None and row.roic >= 0.12:
        positives.append("ROIC above quality threshold")
    if row.fcf_conversion is not None and row.fcf_conversion >= 0.7:
        positives.append("strong FCF conversion")
    if row.quality_label == "deteriorating":
        negatives.append("quality deteriorating")
    if row.accounting_flags:
        negatives.extend(row.accounting_flags[:2])
    severe_terms = ("negative cash conversion", "high leverage", "weak interest coverage", "high accrual")
    if any(any(term in flag.lower() for term in severe_terms) for flag in row.accounting_flags) and score < 50:
        risk_flags.append("severe_accounting_risk")
    return score, positives, negatives, risk_flags


def _latest_event(events: tuple[DARTDisclosureEventRow, ...], code: str) -> DARTDisclosureEventRow | None:
    matches = [row for row in events if row.code == code]
    if not matches:
        return None
    return sorted(matches, key=lambda row: row.available_at or row.receipt_date or "", reverse=True)[0]


def _catalyst_scores(row: DARTDisclosureEventRow | None) -> tuple[int | None, int | None, list[str], list[str], list[str]]:
    positives: list[str] = []
    negatives: list[str] = []
    risk_flags: list[str] = []
    if row is None:
        return None, None, positives, ["no recent DART catalyst"], risk_flags
    catalyst = row.catalyst_score
    value_up = row.catalyst_score if row.category in VALUE_UP_CATEGORIES else 0
    if row.sentiment == "positive":
        positives.append(f"positive DART catalyst: {row.category}")
    if row.category in VALUE_UP_CATEGORIES:
        positives.append("shareholder return / value-up event")
    if row.sentiment == "negative":
        negatives.append(f"negative DART risk: {row.category}")
    if row.dilution_risk_score >= 70:
        risk_flags.append("severe_dilution_risk")
    if row.category in {"audit_issue", "embezzlement_breach_of_trust", "trading_halt", "administrative_issue", "delisting_risk"} or row.governance_risk_score >= 80:
        risk_flags.append("delisting_or_administrative_risk")
    return catalyst, value_up, positives, negatives, risk_flags


def _flow_score(row: SmartMoneyFlowRow | None) -> tuple[int | None, int | None, int | None, list[str], list[str], list[str]]:
    positives: list[str] = []
    negatives: list[str] = []
    risk_flags: list[str] = []
    if row is None:
        return None, None, None, positives, ["smart money flow unavailable"], risk_flags
    flow_z = row.flow_z_score or 0.0
    smart_money = int(round(_clamp(50 + flow_z * 14 + row.accumulation_persistence * 0.25 - row.distribution_risk_score * 0.20, 0, 100)))
    short_component = int(round(_clamp(100 - row.short_pressure_score * 0.65 + row.short_squeeze_score * 0.20, 0, 100)))
    liquidity = 100
    if row.trading_value_20d is not None:
        liquidity = int(round(_clamp(row.trading_value_20d / 10_000_000_000, 0, 100)))
    if row.foreign_net_buy_20d is not None and row.foreign_net_buy_20d > 0:
        positives.append("foreign accumulation")
    if row.institution_net_buy_20d is not None and row.institution_net_buy_20d > 0:
        positives.append("institution accumulation")
    if row.short_squeeze_score >= 70:
        positives.append("short squeeze setup candidate")
    if row.distribution_risk_score >= 60:
        negatives.append("distribution risk elevated")
    if row.fragility_score >= 70:
        negatives.append("fragile long structure")
    if row.illiquidity_warning:
        negatives.append(row.illiquidity_warning)
        risk_flags.append("liquidity_risk")
    return smart_money, short_component, liquidity, positives, negatives, risk_flags


def _macro_score(sector: str, regime_state: MarketRegimeMacroRadarState | None) -> tuple[int | None, list[str], list[str]]:
    if regime_state is None or not regime_state.sector_tailwinds:
        return None, [], ["macro regime unavailable"]
    sector_lower = sector.lower()
    best: SectorTailwindRow | None = None
    for row in regime_state.sector_tailwinds:
        if row.sector.lower() == sector_lower or row.sector.lower() in sector_lower or sector_lower in row.sector.lower():
            best = row
            break
    if best is None:
        score = int(round((regime_state.regime_score + 50) / 2))
        return score, [f"market regime {regime_state.current_regime_label}"] if score >= 55 else [], ["sector-specific macro unavailable"]
    positives = [f"macro tailwind: {driver}" for driver in best.positive_drivers[:2]]
    negatives = [f"macro headwind: {driver}" for driver in best.negative_drivers[:2]]
    return best.tailwind_score, positives, negatives


def calculate_final_alpha_score(features: dict[str, Any]) -> int:
    weights = {
        "valuation_score": 0.18,
        "quality_score": 0.20,
        "catalyst_score": 0.14,
        "value_up_score": 0.08,
        "smart_money_score": 0.16,
        "short_pressure_score": 0.08,
        "macro_score": 0.08,
        "liquidity_score": 0.08,
    }
    total_weight = 0.0
    score = 0.0
    for key, weight in weights.items():
        value = _finite(features.get(key))
        if value is None:
            continue
        score += _clamp(value, 0, 100) * weight
        total_weight += weight
    if total_weight <= 0:
        return 0
    raw = score / total_weight
    penalty = _finite(features.get("risk_penalty")) or 0.0
    return int(round(_clamp(raw - penalty, 0, 100)))


def calculate_confidence_score(features: dict[str, Any]) -> int:
    expected_feature_count = int(features.get("expected_feature_count", 8) or 8)
    available_feature_count = int(features.get("available_feature_count", 0) or 0)
    meta_confidence = _finite(features.get("meta_confidence"))
    stale_count = int(features.get("stale_count", 0) or 0)
    fallback_count = int(features.get("fallback_count", 0) or 0)
    missing_count = max(0, expected_feature_count - available_feature_count)
    base = 30 + (available_feature_count / max(1, expected_feature_count)) * 50
    if meta_confidence is not None:
        base = base * 0.55 + meta_confidence * 0.45
    base -= stale_count * 14
    base -= fallback_count * 4
    base -= missing_count * 5
    return int(round(_clamp(base, 0, 100)))


def rating_from_score(final_alpha_score: int, confidence_score: int) -> str:
    if final_alpha_score >= 82 and confidence_score >= 70:
        return "STRONG_BUY_CANDIDATE"
    if final_alpha_score >= 70 and confidence_score >= 60:
        return "BUY_CANDIDATE"
    if final_alpha_score >= 55:
        return "WATCH"
    if final_alpha_score >= 40:
        return "HOLD"
    return "AVOID"


def apply_high_risk_override(rating: str, risk_flags: Iterable[str]) -> str:
    flags = set(risk_flags)
    if flags & SEVERE_RISK_FLAGS:
        return "HIGH_RISK_EXCLUDE"
    return rating


def _safe_rows_by_code(rows: Iterable[Any], *, now: datetime | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for row in rows:
        meta = getattr(row, "meta", None)
        if meta is not None and not _meta_is_point_in_time_safe(meta, now):
            continue
        code = str(getattr(row, "code", "") or "").zfill(6)
        if code:
            result[code] = row
    return result


def _snapshot_id(parts: Iterable[str]) -> str:
    payload = "|".join(sorted(str(part) for part in parts if part))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _build_rank_rows(
    *,
    valuation_state: ValuationRelativeCheapnessPanelState,
    quality_state: FundamentalQualityPanelState,
    dart_state: DARTDisclosureCatalystPanelState,
    flow_state: SmartMoneyFlowShortPressurePanelState,
    regime_state: MarketRegimeMacroRadarState,
    now: datetime | None,
) -> tuple[ForwardAlphaRankRow, ...]:
    valuation_map = _safe_rows_by_code(valuation_state.valuation_rows, now=now)
    quality_map = _safe_rows_by_code(quality_state.quality_rows, now=now)
    flow_map = _safe_rows_by_code(flow_state.flow_rows, now=now)
    dart_events = tuple(row for row in dart_state.event_rows if getattr(row, "meta", None) is None or _meta_is_point_in_time_safe(row.meta, now))
    regime_metas = _regime_feature_metas(regime_state)
    regime_is_point_in_time_safe = bool(regime_metas) and all(
        _meta_is_point_in_time_safe(meta, now) for meta in regime_metas
    )
    used_regime_metas = regime_metas if regime_is_point_in_time_safe else ()
    candidate_codes = set(valuation_map) | set(quality_map) | set(flow_map) | {row.code for row in dart_events}
    codes = sorted(code for code in candidate_codes if code.isdigit() and len(code) == 6)
    rows: list[ForwardAlphaRankRow] = []
    for code in codes:
        valuation = valuation_map.get(code)
        quality = quality_map.get(code)
        flow = flow_map.get(code)
        event = _latest_event(dart_events, code)
        name = str(getattr(valuation, "name", "") or getattr(quality, "name", "") or getattr(flow, "name", "") or getattr(event, "name", "") or code)
        sector = str(getattr(valuation, "sector", "") or getattr(quality, "sector", "") or getattr(flow, "sector", "") or "Unclassified")
        market = str(
            getattr(valuation, "market", "")
            or getattr(quality, "market", "")
            or getattr(flow, "market", "")
            or getattr(event, "market", "")
            or "UNKNOWN"
        ).upper()
        positive_drivers: list[str] = []
        negative_drivers: list[str] = []
        risk_flags: list[str] = []

        valuation_score, pos, neg = _valuation_score(valuation)
        positive_drivers.extend(pos)
        negative_drivers.extend(neg)
        quality_score, pos, neg, risks = _quality_score(quality)
        positive_drivers.extend(pos)
        negative_drivers.extend(neg)
        risk_flags.extend(risks)
        catalyst_score, value_up_score, pos, neg, risks = _catalyst_scores(event)
        positive_drivers.extend(pos)
        negative_drivers.extend(neg)
        risk_flags.extend(risks)
        smart_money_score, short_component, liquidity_score, pos, neg, risks = _flow_score(flow)
        positive_drivers.extend(pos)
        negative_drivers.extend(neg)
        risk_flags.extend(risks)
        if regime_is_point_in_time_safe:
            macro_score, pos, neg = _macro_score(sector, regime_state)
            positive_drivers.extend(pos)
            negative_drivers.extend(neg)
        else:
            macro_score = None
            negative_drivers.append("macro regime unavailable at prediction time")
            if regime_metas:
                risk_flags.append("future_macro_data_excluded")

        feature_values = {
            "valuation_score": valuation_score,
            "quality_score": quality_score,
            "catalyst_score": catalyst_score,
            "value_up_score": value_up_score,
            "smart_money_score": smart_money_score,
            "short_pressure_score": short_component,
            "macro_score": macro_score,
            "liquidity_score": liquidity_score,
        }
        available_features = [value for value in feature_values.values() if value is not None]
        row_metas = [getattr(row, "meta", None) for row in (valuation, quality, flow, event) if getattr(row, "meta", None) is not None]
        all_metas = [*row_metas, *used_regime_metas]
        stale_metas = [meta for meta in all_metas if meta.stale_data_flag]
        fallback_metas = [meta for meta in all_metas if meta.is_fallback]
        meta_confidence = sum((meta.confidence_score or meta.quality_score) for meta in all_metas) / len(all_metas) if all_metas else 0.0
        if stale_metas:
            risk_flags.append("stale_data_risk")
        risk_penalty = 0
        if quality_score is not None and quality_score < 45:
            risk_penalty += 8
        if event is not None:
            risk_penalty += int(round(max(event.dilution_risk_score, event.governance_risk_score) * 0.18))
        if flow is not None:
            risk_penalty += int(round(flow.distribution_risk_score * 0.12 + flow.fragility_score * 0.12))
        if stale_metas:
            risk_penalty += 12
        features = dict(feature_values)
        features["risk_penalty"] = risk_penalty
        final_score = calculate_final_alpha_score(features)
        confidence = calculate_confidence_score(
            {
                "expected_feature_count": 8,
                "available_feature_count": len(available_features),
                "meta_confidence": meta_confidence,
                "stale_count": len(stale_metas),
                "fallback_count": len(fallback_metas),
            }
        )
        rating = apply_high_risk_override(rating_from_score(final_score, confidence), risk_flags)
        used_rows = [row for row in (valuation, quality, flow, event) if row is not None]
        stale_warning = "One or more feature sources are stale; candidate ratings are capped by risk override." if stale_metas else None
        snapshot = _snapshot_id(
            [SCORE_VERSION, code]
            + [getattr(row.meta, "available_at", "") or getattr(row.meta, "as_of_date", "") or "" for row in used_rows]
            + [meta.available_at or meta.as_of_date or "" for meta in used_regime_metas]
        )
        meta = _source_meta_for_rows(
            used_rows,
            now=now,
            stale=bool(stale_metas),
            missing=len(available_features) < 5,
            fallback=bool(fallback_metas),
            additional_metas=used_regime_metas,
        )
        rows.append(
            ForwardAlphaRankRow(
                code=code,
                name=name,
                sector=sector,
                market=market,
                final_alpha_score=final_score,
                confidence_score=confidence,
                rating=rating,  # type: ignore[arg-type]
                valuation_score=valuation_score,
                quality_score=quality_score,
                catalyst_score=catalyst_score,
                value_up_score=value_up_score,
                smart_money_score=smart_money_score,
                short_pressure_score=short_component,
                macro_score=macro_score,
                liquidity_score=liquidity_score,
                risk_penalty=risk_penalty,
                positive_drivers=tuple(dict.fromkeys(positive_drivers))[:5],
                negative_drivers=tuple(dict.fromkeys(negative_drivers))[:5],
                risk_flags=tuple(dict.fromkeys(risk_flags)),
                stale_data_warning=stale_warning,
                score_version=SCORE_VERSION,
                feature_snapshot_id=snapshot,
                meta=meta,
            )
        )
    return tuple(sorted(rows, key=lambda row: (row.rating == "HIGH_RISK_EXCLUDE", -row.final_alpha_score, -row.confidence_score, row.code)))


def build_forward_alpha_ranking_panel(
    *,
    valuation_state: ValuationRelativeCheapnessPanelState | None = None,
    quality_state: FundamentalQualityPanelState | None = None,
    dart_state: DARTDisclosureCatalystPanelState | None = None,
    flow_state: SmartMoneyFlowShortPressurePanelState | None = None,
    regime_state: MarketRegimeMacroRadarState | None = None,
    now: datetime | None = None,
    allow_mock: bool = True,
) -> ForwardAlphaRankingPanelState:
    if valuation_state is None and allow_mock:
        valuation_state = build_valuation_relative_cheapness_panel(now=now, allow_mock=True)
    if quality_state is None and allow_mock:
        quality_state = build_fundamental_quality_panel(now=now, allow_mock=True)
    if dart_state is None and allow_mock:
        dart_state = build_dart_disclosure_catalyst_panel(now=now, allow_mock=True)
    if flow_state is None and allow_mock:
        flow_state = build_smart_money_flow_short_pressure_panel(now=now, allow_mock=True)
    if regime_state is None and allow_mock:
        regime_state = build_market_regime_macro_radar(now=now, allow_mock=True)

    if valuation_state is None or quality_state is None or dart_state is None or flow_state is None or regime_state is None:
        fetched_at = _now_iso(now)
        meta = DataSourceMeta(
            source="Not connected",
            provider="BaselineRuleScore",
            source_url=None,
            as_of_date=None,
            available_at=None,
            fetched_at=fetched_at,
            frequency="daily",
            unit="score",
            quality_score=0,
            is_fallback=True,
            stale_data_flag=True,
            source_table_or_endpoint="/api/dashboard/forward-alpha-ranking",
            confidence_score=0,
            missing_data_flag=True,
        )
        return ForwardAlphaRankingPanelState(
            module_id="ForwardAlphaRankingPanel",
            status="empty",
            title="Forward Alpha Ranking Panel",
            summary="Required feature panels are not available.",
            data_points=(DataPoint("ranked_count", "Ranked Count", 0, meta, "0"),),
            explanation=("Forward alpha ranking requires valuation, quality, DART catalyst, flow/short, macro, liquidity, and freshness features.",),
            risk_flags=("missing_forward_alpha_features",),
            stale_after_minutes=24 * 60,
        )

    rows = _build_rank_rows(
        valuation_state=valuation_state,
        quality_state=quality_state,
        dart_state=dart_state,
        flow_state=flow_state,
        regime_state=regime_state,
        now=now,
    )
    if not rows:
        fetched_at = _now_iso(now)
        meta = DataSourceMeta(
            source="Feature stack",
            provider="BaselineRuleScore",
            source_url=None,
            as_of_date=None,
            available_at=None,
            fetched_at=fetched_at,
            frequency="daily",
            unit="score",
            quality_score=0,
            is_fallback=True,
            stale_data_flag=False,
            source_table_or_endpoint="/api/dashboard/forward-alpha-ranking",
            confidence_score=0,
            missing_data_flag=True,
        )
        return ForwardAlphaRankingPanelState(
            module_id="ForwardAlphaRankingPanel",
            status="empty",
            title="Forward Alpha Ranking Panel",
            summary="No point-in-time feature rows are available for ranking.",
            data_points=(DataPoint("ranked_count", "Ranked Count", 0, meta, "0"),),
            explanation=("Future-dated feature rows are excluded to prevent label leakage.",),
            risk_flags=("no_point_in_time_feature_rows",),
            stale_after_minutes=24 * 60,
        )

    stale = any(row.meta.stale_data_flag for row in rows)
    fallback = any(row.meta.is_fallback for row in rows)
    missing = any(row.meta.missing_data_flag for row in rows)
    panel_snapshot_id = _snapshot_id([SCORE_VERSION] + [row.feature_snapshot_id for row in rows])
    panel_meta = _source_meta_for_rows(rows, now=now, stale=stale, missing=missing, fallback=fallback)
    strong = tuple(row for row in rows if row.rating == "STRONG_BUY_CANDIDATE")
    buy = tuple(row for row in rows if row.rating == "BUY_CANDIDATE")
    watch = tuple(row for row in rows if row.rating == "WATCH")
    excluded = tuple(row for row in rows if row.rating == "HIGH_RISK_EXCLUDE")
    hold_or_avoid = tuple(row for row in rows if row.rating in {"HOLD", "AVOID"})
    data_points = (
        DataPoint("ranked_count", "Ranked Count", len(rows), panel_meta, str(len(rows))),
        DataPoint("candidate_count", "Candidate Count", len(strong) + len(buy), panel_meta, str(len(strong) + len(buy))),
        DataPoint("watch_count", "Watch Count", len(watch), panel_meta, str(len(watch))),
        DataPoint("high_risk_exclusion_count", "High Risk Exclusion Count", len(excluded), panel_meta, str(len(excluded))),
    )
    status = "stale" if stale else "ready"
    summary = "BaselineRuleScore ranks forward alpha candidates from economically meaningful features. No automatic trading is implemented."
    if fallback:
        summary = "Mock feature-stack alpha ranking is shown until real KRX/OpenDART/macro adapters are connected."
    if excluded:
        summary = "High-risk override is active; severe risk rows cannot receive Buy candidate ratings."
    return ForwardAlphaRankingPanelState(
        module_id="ForwardAlphaRankingPanel",
        status=status,
        title="Forward Alpha Ranking Panel",
        summary=summary,
        data_points=data_points,
        explanation=(
            "BaselineRuleScore combines valuation, quality, DART catalysts, value-up/shareholder return, smart money flow, short pressure, macro, liquidity, risk flags, and data freshness.",
            "Past returns are not used to chase performance; they may only support volatility, drawdown, liquidity, trend confirmation, and validation in future phases.",
            "Severe accounting, dilution, delisting/administrative, stale data, or liquidity risk prevents Buy candidate ratings.",
        ),
        risk_flags=tuple(["stale_feature_data"] if stale else []) + tuple(["fallback_feature_stack"] if fallback else []) + tuple(["high_risk_override_active"] if excluded else []),
        stale_after_minutes=24 * 60,
        ranking_rows=rows,
        strong_buy_candidates=strong,
        buy_candidates=buy,
        watchlist=watch,
        hold_or_avoid=hold_or_avoid,
        high_risk_exclusions=excluded,
        score_version=SCORE_VERSION,
        feature_snapshot_id=panel_snapshot_id,
        latest_source_at=max((row.meta.available_at or row.meta.as_of_date or "" for row in rows), default=None) or None,
    )


def forward_alpha_ranking_api_response(state: ForwardAlphaRankingPanelState) -> dict[str, Any]:
    payload = state.to_dict()
    payload["moduleId"] = payload.pop("module_id")
    payload["dataPoints"] = payload.pop("data_points")
    payload["rankingRows"] = payload.pop("ranking_rows")
    payload["strongBuyCandidates"] = payload.pop("strong_buy_candidates")
    payload["buyCandidates"] = payload.pop("buy_candidates")
    payload["holdOrAvoid"] = payload.pop("hold_or_avoid")
    payload["highRiskExclusions"] = payload.pop("high_risk_exclusions")
    payload["scoreVersion"] = payload.pop("score_version")
    payload["featureSnapshotId"] = payload.pop("feature_snapshot_id")
    payload["latestSourceAt"] = payload.pop("latest_source_at")
    payload["staleAfterMinutes"] = payload.pop("stale_after_minutes")
    payload["apiPath"] = payload.pop("api_path")
    return payload
