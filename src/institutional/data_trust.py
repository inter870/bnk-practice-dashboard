from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from .models import DataPoint, DataSourceMeta, DataTrustSourcePanelState, SourceCoverageRow
from .source_registry import (
    ACCURACY_LABEL_KO,
    CATEGORY_LABEL_KO,
    EXACTNESS_LABEL_KO,
    STATUS_LABEL_KO,
    DataSourceDefinition,
    accuracy_for_source,
    exactness_for_source,
    get_source,
    missing_required_keys,
    resolve_best_data_source,
)


SOURCE_MODULES: tuple[tuple[str, str], ...] = (
    ("portfolio", "Portfolio data"),
    ("market_price", "Market price data"),
    ("valuation", "Valuation data"),
    ("financial_statement", "Financial statement data"),
    ("dart_disclosure", "DART disclosure data"),
    ("macro", "Macro data"),
    ("fx_rates", "FX/rates data"),
    ("investor_flow", "Investor flow data"),
    ("short_selling", "Short-selling data"),
)

KST = ZoneInfo("Asia/Seoul")


def _now_iso(now: datetime | None = None) -> str:
    stamp = now or datetime.now(KST)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=KST)
    return stamp.astimezone(KST).isoformat(timespec="seconds")


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
        return False
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=current.tzinfo)
    if stamp > current:
        return False
    return (current - stamp).total_seconds() > stale_after_hours * 3600


def _is_future_date(value: Any, *, fetched_at: str | None = None, now: datetime | None = None) -> bool:
    stamp = _as_datetime(value)
    if stamp is None:
        return False
    current = _as_datetime(fetched_at) or now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=current.tzinfo)
    return stamp > current


def _get(item: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(item, dict) and name in item:
            return item.get(name)
        if hasattr(item, name):
            return getattr(item, name)
    return default


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _key_present(api_key_status: dict[str, bool] | None, key: str) -> bool:
    return bool((api_key_status or {}).get(key))


def _missing_keys(api_key_status: dict[str, bool] | None, required: Iterable[str]) -> tuple[str, ...]:
    return tuple(key for key in required if not _key_present(api_key_status, key))


def _coverage_status(status: str) -> str:
    return {
        "connected": "available",
        "partially_connected": "partial",
        "missing_key": "missing_key",
        "adapter_missing": "adapter_missing",
        "planned": "planned",
        "stale": "stale",
        "cache_only": "cache_only",
        "mock": "mock",
        "manual": "manual",
        "unavailable": "unavailable",
        "error": "error",
    }.get(status, status)


def _key_message(source: DataSourceDefinition | None, missing_keys: tuple[str, ...]) -> tuple[str, str]:
    if source is None:
        return "데이터 소스 확인 필요", "합법적으로 사용할 수 있는 데이터 소스를 연결하세요."
    if source.source_type == "planned":
        return "키 확인 전 어댑터 미연결", "어댑터 구현 후 필요한 키를 다시 확인하세요."
    if missing_keys:
        return "누락 키 " + ", ".join(missing_keys), "필요한 API 키를 환경변수 또는 Streamlit secrets에 설정하세요."
    if not source.required_env_keys:
        if source.source_type == "public_web":
            return "키 없이 공개 데이터 사용 중", "공식 실시간 데이터가 필요하면 증권사 또는 공식 API 키를 설정하세요."
        return "필요 키 없음", "이 소스는 현재 별도 인증키가 필요하지 않습니다."
    return "필요 키 설정됨", "필요한 API 키 이름만 확인하며 실제 값은 표시하지 않습니다."


def _confidence_for_source(
    source: DataSourceDefinition,
    *,
    stale: bool,
    missing: bool,
    metadata_missing: bool = False,
    quality_score: int | None = None,
) -> int:
    score = int(quality_score if quality_score is not None else source.reliability_base_score)
    if source.source_type == "mock":
        score = min(score, 25)
    if source.source_type == "planned":
        return 0
    if missing:
        return 0
    if source.source_type == "public_web":
        score -= 8
    if stale:
        score -= 25
    if metadata_missing:
        score -= 10
    return max(0, min(95, score))


def _meta(
    *,
    source: str,
    endpoint: str,
    as_of_date: str | None,
    available_at: str | None,
    fetched_at: str,
    unit: str,
    quality_score: int,
    confidence_score: int | None,
    stale: bool,
    missing: bool,
    is_fallback: bool,
    revised_at: str | None = None,
    warnings: tuple[str, ...] = (),
    errors: tuple[str, ...] = (),
) -> DataSourceMeta:
    return DataSourceMeta(
        source=source,
        provider=source,
        source_url=None,
        as_of_date=as_of_date,
        available_at=available_at,
        fetched_at=fetched_at,
        frequency="metadata",
        unit=unit,
        quality_score=max(0, min(100, quality_score)),
        is_fallback=is_fallback,
        stale_data_flag=stale,
        source_table_or_endpoint=endpoint,
        revised_at=revised_at,
        confidence_score=None if confidence_score is None else max(0, min(100, confidence_score)),
        missing_data_flag=missing,
        warnings=warnings,
        errors=errors,
    )


def _coverage_row(
    *,
    module_key: str,
    label: str,
    status: str,
    source: str,
    endpoint: str,
    as_of_date: str | None,
    available_at: str | None,
    fetched_at: str,
    quality_score: int,
    confidence_score: int | None,
    stale: bool,
    missing: bool,
    is_fallback: bool,
    required_api_keys: tuple[str, ...] = (),
    missing_api_keys: tuple[str, ...] = (),
    notes: tuple[str, ...] = (),
    source_definition: DataSourceDefinition | None = None,
    connection_status: str | None = None,
    accuracy_grade: str | None = None,
    exactness_level: str | None = None,
    message_ko: str | None = None,
    action_required_ko: str | None = None,
    optional_keys: tuple[str, ...] = (),
    can_compute_exact_value: bool | None = None,
    can_compute_best_effort_value: bool | None = None,
) -> SourceCoverageRow:
    connection_status = connection_status or status
    is_planned_source = bool(
        (source_definition and source_definition.source_type == "planned")
        or connection_status in {"planned", "adapter_missing"}
        or endpoint.startswith("planned:")
    )
    if is_planned_source:
        status = "planned"
        connection_status = "planned"
        stale = False
        missing = False
        is_fallback = False
        quality_score = 0
        confidence_score = None
        accuracy_grade = accuracy_grade or "planned"
        exactness_level = exactness_level or "unavailable"
    elif connection_status == "missing_key":
        stale = False
    if as_of_date is None and available_at is None:
        stale = False
    diagnostic_notes = list(notes)
    if _is_future_date(as_of_date, fetched_at=fetched_at) or _is_future_date(available_at, fetched_at=fetched_at):
        diagnostic_notes.append("future_date_detected")
        stale = False
    coverage_status = _coverage_status(connection_status)
    if stale and status == "available":
        coverage_status = "stale"
    if missing and connection_status in {"available", "connected"}:
        coverage_status = "unavailable"
    meta = _meta(
        source=source,
        endpoint=endpoint,
        as_of_date=as_of_date,
        available_at=available_at,
        fetched_at=fetched_at,
        unit="metadata",
        quality_score=quality_score,
        confidence_score=confidence_score,
        stale=stale,
        missing=missing,
        is_fallback=is_fallback,
        warnings=tuple(diagnostic_notes),
    )
    active_source_id = source_definition.source_id if source_definition else None
    active_source_label_ko = source_definition.display_name_ko if source_definition else source
    adapter_id = source_definition.adapter_id if source_definition else endpoint
    is_planned = is_planned_source
    is_mock = bool(source_definition and source_definition.source_type == "mock")
    is_keyless = bool(source_definition and not source_definition.required_env_keys and source_definition.legal_access_mode == "no_key_required")
    required_keys = tuple(required_api_keys or (source_definition.required_env_keys if source_definition else ()))
    missing_keys = tuple(missing_api_keys)
    has_required_keys = not missing_keys
    accuracy_grade = accuracy_grade or (accuracy_for_source(source_definition) if source_definition else "unavailable")
    exactness_level = exactness_level or (exactness_for_source(source_definition) if source_definition else "unavailable")
    can_exact = can_compute_exact_value if can_compute_exact_value is not None else exactness_level in {"exact_official", "exact_broker", "official_eod"}
    can_best = (
        can_compute_best_effort_value
        if can_compute_best_effort_value is not None
        else can_exact or accuracy_grade in {"public_snapshot", "public_delayed", "manual", "cached"}
    )
    return SourceCoverageRow(
        module_key=module_key,
        label=label,
        coverage_status=coverage_status,
        required_api_keys=required_api_keys,
        missing_api_keys=missing_api_keys,
        notes=tuple(diagnostic_notes),
        meta=meta,
        category=source_definition.category if source_definition else module_key,
        category_label_ko=CATEGORY_LABEL_KO.get(source_definition.category if source_definition else module_key),
        active_source_id=active_source_id,
        active_source_label_ko=active_source_label_ko,
        adapter_id=adapter_id,
        status=connection_status,
        status_label_ko=STATUS_LABEL_KO.get(connection_status),
        accuracy_grade=accuracy_grade,
        accuracy_grade_label_ko=ACCURACY_LABEL_KO.get(accuracy_grade),
        exactness_level=exactness_level,
        exactness_label_ko=EXACTNESS_LABEL_KO.get(exactness_level),
        missing_keys=missing_keys,
        required_keys=required_keys,
        optional_keys=optional_keys or (source_definition.optional_env_keys if source_definition else ()),
        has_required_keys=has_required_keys,
        source_endpoint=endpoint,
        message_ko=message_ko,
        action_required_ko=action_required_ko,
        is_mock=is_mock,
        is_planned=is_planned,
        is_keyless=is_keyless,
        is_trade_safe=False,
        can_compute_exact_value=can_exact,
        can_compute_best_effort_value=can_best,
    )


def _snapshot_coverage(
    *,
    module_key: str,
    label: str,
    snapshots: dict[str, Any] | None,
    keys: tuple[str, ...],
    endpoint: str,
    now: datetime | None,
    stale_after_hours: float,
    required_api_keys: tuple[str, ...] = (),
    api_key_status: dict[str, bool] | None = None,
    category: str = "market_price",
    default_source_id: str = "naver_finance_market_snapshot",
) -> SourceCoverageRow:
    fetched_at = _now_iso(now)
    snapshot_map = snapshots or {}
    present = [snapshot_map[key] for key in keys if key in snapshot_map and snapshot_map[key] is not None]
    missing_names = tuple(key for key in keys if key not in snapshot_map or snapshot_map[key] is None)
    source_names = sorted({str(_get(item, "source", default="unknown") or "unknown") for item in present})

    source_id = default_source_id
    source_text = " ".join(source_names).lower()
    if "kis" in source_text or "korea investment" in source_text or "한국투자" in source_text:
        source_id = "kis_market_price"
    elif "finance" in source_text and "datareader" in source_text:
        source_id = "finance_data_reader_market" if category == "market_price" else "naver_finance_fx_rates"
    elif "naver" in source_text or "네이버" in source_text:
        source_id = "naver_finance_market_snapshot" if category == "market_price" else "naver_finance_fx_rates"
    source_definition = get_source(source_id)
    required_api_keys = source_definition.required_env_keys
    missing_api_keys = missing_required_keys(source_definition, api_key_status)
    key_message, key_action = _key_message(source_definition, missing_api_keys)
    if not present:
        connection_status = "missing_key" if missing_api_keys else "unavailable"
        return _coverage_row(
            module_key=module_key,
            label=label,
            status="missing",
            connection_status=connection_status,
            source=source_definition.display_name_ko,
            endpoint=endpoint,
            as_of_date=None,
            available_at=None,
            fetched_at=fetched_at,
            quality_score=0,
            confidence_score=0,
            stale=True,
            missing=True,
            is_fallback=True,
            required_api_keys=required_api_keys,
            missing_api_keys=missing_api_keys,
            notes=("현재 소스 스냅샷이 없습니다.", key_message),
            source_definition=source_definition,
            accuracy_grade="unavailable",
            exactness_level="unavailable",
            message_ko="정확 수치 표시 불가: 현재 소스 스냅샷이 없습니다.",
            action_required_ko=key_action,
        )

    asofs = [_as_datetime(_get(item, "asof")) for item in present]
    valid_asofs = [item for item in asofs if item is not None]
    latest_asof = max(valid_asofs) if valid_asofs else None
    stale = any(_is_stale(_get(item, "asof"), now=now, stale_after_hours=stale_after_hours) for item in present)
    quality_values = [_finite(_get(item, "quality_score", default=0)) or 0 for item in present]
    avg_quality = int(sum(quality_values) / len(quality_values)) if quality_values else 50
    is_fallback = any(bool(_get(item, "is_fallback", default=True)) for item in present)
    status = "available" if not missing_names and not missing_api_keys else "partial"
    connection_status = "missing_key" if missing_api_keys else "stale" if stale else "connected" if not missing_names else "partially_connected"
    notes = []
    if missing_names:
        notes.append("누락 데이터: " + ", ".join(missing_names))
    if missing_api_keys:
        notes.append("누락 키 " + ", ".join(missing_api_keys))
    else:
        notes.append(key_message)
    if stale:
        notes.append("일부 스냅샷이 오래되었습니다.")
    if source_definition.source_type == "public_web":
        notes.append(source_definition.user_visible_warning_ko)
    avg_quality = _confidence_for_source(
        source_definition,
        stale=stale,
        missing=False,
        metadata_missing=latest_asof is None,
        quality_score=avg_quality,
    )
    return _coverage_row(
        module_key=module_key,
        label=label,
        status=status,
        connection_status=connection_status,
        source=", ".join(source_names) if source_names else source_definition.display_name_ko,
        endpoint=endpoint,
        as_of_date=_as_date_text(latest_asof),
        available_at=_as_date_text(latest_asof),
        fetched_at=fetched_at,
        quality_score=avg_quality,
        confidence_score=max(0, min(95, avg_quality - (10 if missing_names else 0))),
        stale=stale,
        missing=False,
        is_fallback=is_fallback,
        required_api_keys=required_api_keys,
        missing_api_keys=missing_api_keys,
        notes=tuple(notes),
        source_definition=source_definition,
        accuracy_grade=accuracy_for_source(source_definition),
        exactness_level=exactness_for_source(source_definition),
        message_ko=(
            "키 없이 공개 데이터 스냅샷을 사용 중입니다."
            if source_definition.source_type == "public_web"
            else "선택된 데이터 소스를 사용 중입니다."
        ),
        action_required_ko=key_action,
    )


def build_data_trust_source_panel(
    *,
    snapshots: dict[str, Any] | None = None,
    portfolio_holding_count: int = 0,
    using_mock_portfolio: bool = False,
    api_key_status: dict[str, bool] | None = None,
    runtime_source_status: dict[str, dict[str, Any]] | None = None,
    now: datetime | None = None,
    stale_after_hours: float = 24.0,
) -> DataTrustSourcePanelState:
    fetched_at = _now_iso(now)
    runtime_source_status = runtime_source_status or {}
    rows: list[SourceCoverageRow] = []

    if portfolio_holding_count > 0 and not using_mock_portfolio:
        portfolio_status = "available"
        portfolio_connection_status = "manual"
        portfolio_missing = False
        portfolio_source_def = get_source("manual_portfolio_holdings")
        portfolio_source = portfolio_source_def.display_name_ko
        portfolio_confidence = 85
        portfolio_notes = ("사용자가 입력한 보유 종목 기준입니다.",)
        portfolio_message = "사용자가 입력한 보유 종목 기준입니다."
    elif using_mock_portfolio:
        portfolio_status = "mock"
        portfolio_connection_status = "mock"
        portfolio_missing = False
        portfolio_source_def = get_source("mock_portfolio_holdings")
        portfolio_source = portfolio_source_def.display_name_ko
        portfolio_confidence = 20
        portfolio_notes = ("실제 보유 종목을 입력하기 전까지 모의 데이터가 표시됩니다.",)
        portfolio_message = "실제 보유 종목을 입력하기 전까지 모의 데이터가 표시됩니다."
    else:
        portfolio_status = "missing"
        portfolio_connection_status = "unavailable"
        portfolio_missing = True
        portfolio_source_def = get_source("manual_portfolio_holdings")
        portfolio_source = "보유 종목 미입력"
        portfolio_confidence = 0
        portfolio_notes = ("보유 종목을 직접 입력하면 실제 포트폴리오 기준으로 계산합니다.",)
        portfolio_message = "보유 종목 데이터가 연결되지 않았습니다."

    rows.append(
        _coverage_row(
            module_key="portfolio",
            label="Portfolio data",
            status=portfolio_status,
            connection_status=portfolio_connection_status,
            source=portfolio_source,
            endpoint="sidebar:portfolio_holdings_text",
            as_of_date=(now or datetime.now()).date().isoformat(),
            available_at=(now or datetime.now()).date().isoformat(),
            fetched_at=fetched_at,
            quality_score=70 if portfolio_status == "mock" else 90 if portfolio_status == "available" else 0,
            confidence_score=portfolio_confidence,
            stale=False,
            missing=portfolio_missing,
            is_fallback=portfolio_status == "mock",
            notes=portfolio_notes,
            source_definition=portfolio_source_def,
            accuracy_grade=accuracy_for_source(portfolio_source_def),
            exactness_level=exactness_for_source(portfolio_source_def),
            message_ko=portfolio_message,
            action_required_ko="실제 보유 종목을 입력하면 모의 데이터 대신 수동 입력값을 사용합니다.",
        )
    )

    rows.append(
        _snapshot_coverage(
            module_key="market_price",
            label="Market price data",
            snapshots=snapshots,
            keys=("KOSPI", "KOSDAQ"),
            endpoint="load_market_snapshot:indices",
            now=now,
            stale_after_hours=stale_after_hours,
            api_key_status=api_key_status,
            category="market_price",
            default_source_id="naver_finance_market_snapshot",
        )
    )

    valuation_source = get_source("planned_krx_valuation")
    valuation_key_message, valuation_action = _key_message(valuation_source, ())
    rows.append(
        _coverage_row(
            module_key="valuation",
            label="Valuation data",
            status="missing",
            connection_status="adapter_missing",
            source=valuation_source.display_name_ko,
            endpoint="planned:krx_valuation",
            as_of_date=None,
            available_at=None,
            fetched_at=fetched_at,
            quality_score=0,
            confidence_score=0,
            stale=True,
            missing=True,
            is_fallback=True,
            notes=("밸류에이션 어댑터가 아직 연결되지 않았습니다.", valuation_key_message),
            source_definition=valuation_source,
            accuracy_grade="planned",
            exactness_level="unavailable",
            message_ko="밸류에이션 어댑터가 아직 연결되지 않아 정확 수치를 표시할 수 없습니다.",
            action_required_ko=valuation_action,
        )
    )

    financial_source = get_source("opendart_financials")
    dart_required = financial_source.required_env_keys
    dart_missing = missing_required_keys(financial_source, api_key_status)
    dart_available = not dart_missing
    dart_key_message, dart_key_action = _key_message(financial_source, dart_missing)
    rows.append(
        _coverage_row(
            module_key="financial_statement",
            label="Financial statement data",
            status="partial" if dart_available else "missing",
            connection_status="partially_connected" if dart_available else "missing_key",
            source=financial_source.display_name_ko if dart_available else "OpenDART 키 필요",
            endpoint="opendart:fins_acnt/fnlttSinglAcntAll",
            as_of_date=None,
            available_at=None,
            fetched_at=fetched_at,
            quality_score=45 if dart_available else 0,
            confidence_score=40 if dart_available else 0,
            stale=not dart_available,
            missing=not dart_available,
            is_fallback=False,
            required_api_keys=dart_required,
            missing_api_keys=dart_missing,
            notes=("시점 기준 분석에는 접수일 또는 사용 가능 시점을 사용해야 합니다.", dart_key_message),
            source_definition=financial_source,
            accuracy_grade="unavailable" if not dart_available else "official_eod",
            exactness_level="unavailable" if not dart_available else "official_eod",
            message_ko=(
                "OpenDART 키는 확인됐지만 선택 종목/기간의 재무제표 데이터는 별도 조회가 필요합니다."
                if dart_available
                else "OpenDART 재무제표 API 사용을 위해 인증키가 필요합니다."
            ),
            action_required_ko=dart_key_action,
        )
    )
    disclosure_source = get_source("opendart_disclosures")
    disclosure_missing = missing_required_keys(disclosure_source, api_key_status)
    disclosure_runtime = runtime_source_status.get("dart_disclosure", {})
    disclosure_runtime_status = str(disclosure_runtime.get("status") or "unknown")
    disclosure_usable = bool(disclosure_runtime.get("usable_data"))
    disclosure_available = not disclosure_missing and disclosure_runtime_status == "ready" and disclosure_usable
    disclosure_fallback = disclosure_runtime_status == "fallback" and disclosure_usable
    active_disclosure_source = get_source("dart_public_disclosures") if disclosure_fallback else disclosure_source
    active_disclosure_missing = () if disclosure_fallback else disclosure_missing
    disclosure_key_message, disclosure_key_action = _key_message(disclosure_source, disclosure_missing)
    rows.append(
        _coverage_row(
            module_key="dart_disclosure",
            label="DART disclosure data",
            status="available" if disclosure_available else "partial" if disclosure_fallback or not disclosure_missing else "missing",
            connection_status="connected" if disclosure_available else "fallback" if disclosure_fallback else "partially_connected" if not disclosure_missing else "missing_key",
            source=(
                str(disclosure_runtime.get("source") or active_disclosure_source.display_name_ko)
                if disclosure_fallback or not disclosure_missing
                else "OpenDART 키 필요"
            ),
            endpoint=active_disclosure_source.adapter_id,
            as_of_date=disclosure_runtime.get("as_of_date"),
            available_at=disclosure_runtime.get("as_of_date"),
            fetched_at=str(disclosure_runtime.get("fetched_at") or fetched_at),
            quality_score=90 if disclosure_available else 60 if disclosure_fallback else 30 if not disclosure_missing else 0,
            confidence_score=90 if disclosure_available else 55 if disclosure_fallback else 20 if not disclosure_missing else 0,
            stale=False,
            missing=not disclosure_usable,
            is_fallback=disclosure_fallback,
            required_api_keys=active_disclosure_source.required_env_keys,
            missing_api_keys=active_disclosure_missing,
            notes=(
                "공시 시각은 사용 가능 시점으로 처리해야 합니다.",
                "OpenDART API는 인증키 설정 후 우선 출처로 사용할 수 있습니다."
                if disclosure_fallback and disclosure_missing
                else disclosure_key_message,
            ),
            source_definition=active_disclosure_source,
            accuracy_grade="official_eod" if disclosure_available else "public_snapshot" if disclosure_fallback else "unavailable",
            exactness_level="official_eod" if disclosure_available else "best_effort" if disclosure_fallback else "unavailable",
            message_ko=(
                "OpenDART 공시 목록에서 사용 가능한 데이터를 확인했습니다."
                if disclosure_available
                else "OpenDART 호출에 실패해 DART 공개 최근공시 페이지를 보조 출처로 사용 중입니다."
                if disclosure_fallback
                else "OpenDART 키는 설정됐지만 현재 사용 가능한 공시 응답을 확인하지 못했습니다."
                if not disclosure_missing
                else "OpenDART 공시 API 사용을 위해 인증키가 필요합니다."
            ),
            action_required_ko=disclosure_key_action,
        )
    )

    ecos_source = get_source("bok_ecos_macro")
    ecos_required = ecos_source.required_env_keys
    ecos_missing = missing_required_keys(ecos_source, api_key_status)
    ecos_runtime = runtime_source_status.get("macro", {})
    ecos_runtime_status = str(ecos_runtime.get("status") or "unknown")
    ecos_usable = bool(ecos_runtime.get("usable_data"))
    ecos_available = not ecos_missing and ecos_runtime_status == "ready" and ecos_usable
    ecos_stale = bool(ecos_runtime.get("stale_data_flag")) if ecos_available else False
    ecos_key_message, ecos_key_action = _key_message(ecos_source, ecos_missing)
    rows.append(
        _coverage_row(
            module_key="macro",
            label="Macro data",
            status="available" if ecos_available else "partial" if not ecos_missing else "missing",
            connection_status="connected" if ecos_available else "partially_connected" if not ecos_missing else "missing_key",
            source=ecos_source.display_name_ko if not ecos_missing else "BOK ECOS 키 필요",
            endpoint="ecos:KeyStatisticList",
            as_of_date=ecos_runtime.get("as_of_date"),
            available_at=ecos_runtime.get("available_at") or ecos_runtime.get("fetched_at"),
            fetched_at=str(ecos_runtime.get("fetched_at") or fetched_at),
            quality_score=65 if ecos_stale else 90 if ecos_available else 30 if not ecos_missing else 0,
            confidence_score=60 if ecos_stale else 90 if ecos_available else 20 if not ecos_missing else 0,
            stale=ecos_stale,
            missing=not ecos_usable,
            is_fallback=False,
            required_api_keys=ecos_required,
            missing_api_keys=ecos_missing,
            notes=("매크로 발표 사용 가능 시점을 저장한 뒤 백테스트에 써야 합니다.", ecos_key_message),
            source_definition=ecos_source,
            accuracy_grade="official_eod" if ecos_available else "unavailable",
            exactness_level="official_eod" if ecos_available else "unavailable",
            message_ko=(
                "BOK ECOS 응답은 확인했지만 최신 관측일이 신선도 기준을 초과했습니다."
                if ecos_stale
                else "BOK ECOS 핵심 지표 응답에서 사용 가능한 데이터를 확인했습니다."
                if ecos_available
                else "BOK ECOS 키는 설정됐지만 현재 사용 가능한 응답을 확인하지 못했습니다."
                if not ecos_missing
                else "BOK ECOS 공식 API 사용을 위해 인증키가 필요합니다."
            ),
            action_required_ko=ecos_key_action,
        )
    )
    rows.append(
        _snapshot_coverage(
            module_key="fx_rates",
            label="FX/rates data",
            snapshots=snapshots,
            keys=("USD/KRW", "US 10Y", "KR 3Y"),
            endpoint="market_snapshot:fx_rates",
            now=now,
            stale_after_hours=stale_after_hours,
            api_key_status=api_key_status,
            category="fx_rates",
            default_source_id="naver_finance_fx_rates",
        )
    )

    investor_flow_source = get_source("planned_krx_investor_flow")
    investor_key_message, investor_action = _key_message(investor_flow_source, ())
    rows.append(
        _coverage_row(
            module_key="investor_flow",
            label="Investor flow data",
            status="missing",
            connection_status="adapter_missing",
            source=investor_flow_source.display_name_ko,
            endpoint="planned:krx_investor_flow",
            as_of_date=None,
            available_at=None,
            fetched_at=fetched_at,
            quality_score=0,
            confidence_score=0,
            stale=True,
            missing=True,
            is_fallback=True,
            notes=("투자자 수급 출처가 아직 연결되지 않았습니다.", investor_key_message),
            source_definition=investor_flow_source,
            accuracy_grade="planned",
            exactness_level="unavailable",
            message_ko="투자자 수급 데이터 어댑터가 아직 연결되지 않았습니다.",
            action_required_ko=investor_action,
        )
    )
    short_source = get_source("planned_krx_short_selling")
    short_key_message, short_action = _key_message(short_source, ())
    rows.append(
        _coverage_row(
            module_key="short_selling",
            label="Short-selling data",
            status="missing",
            connection_status="adapter_missing",
            source=short_source.display_name_ko,
            endpoint="planned:krx_short_selling",
            as_of_date=None,
            available_at=None,
            fetched_at=fetched_at,
            quality_score=0,
            confidence_score=0,
            stale=True,
            missing=True,
            is_fallback=True,
            notes=("공매도 데이터 어댑터가 아직 연결되지 않았습니다.", short_key_message),
            source_definition=short_source,
            accuracy_grade="planned",
            exactness_level="unavailable",
            message_ko="공매도 데이터 어댑터가 아직 연결되지 않았습니다.",
            action_required_ko=short_action,
        )
    )

    stale_sources = tuple(row.label for row in rows if row.meta.stale_data_flag and not row.meta.missing_data_flag and not row.is_planned and not row.is_mock)
    missing_sources = tuple(row.label for row in rows if row.meta.missing_data_flag and not row.is_planned)
    missing_api_keys = tuple(sorted({key for row in rows for key in row.missing_api_keys}))
    latest_refresh_time = max((row.meta.fetched_at or "" for row in rows), default=None) or None
    point_in_time_status = "compliant" if not missing_sources and not stale_sources else "review_required"
    status = "stale" if stale_sources else "ready"
    summary = "Source coverage is visible for portfolio, market, filings, macro, FX/rates, flow, and short pressure data."
    if missing_sources or missing_api_keys:
        summary = f"{len(missing_sources)} missing source(s), {len(missing_api_keys)} missing API key group(s)."
    elif stale_sources:
        summary = f"{len(stale_sources)} stale source(s) need refresh."

    panel_meta = _meta(
        source="Data Trust metadata contract",
        endpoint="/api/dashboard/data-trust",
        as_of_date=(now or datetime.now()).date().isoformat(),
        available_at=(now or datetime.now()).date().isoformat(),
        fetched_at=fetched_at,
        unit="metadata",
        quality_score=85,
        confidence_score=85,
        stale=bool(stale_sources),
        missing=bool(missing_sources),
        is_fallback=False,
    )
    data_points = (
        DataPoint("latest_refresh_time", "Latest Refresh Time", latest_refresh_time, panel_meta, latest_refresh_time),
        DataPoint("stale_source_count", "Stale Sources", len(stale_sources), panel_meta, str(len(stale_sources))),
        DataPoint("missing_source_count", "Missing Sources", len(missing_sources), panel_meta, str(len(missing_sources))),
        DataPoint("point_in_time_status", "Point-in-Time Status", point_in_time_status, panel_meta, point_in_time_status),
    )

    return DataTrustSourcePanelState(
        module_id="DataTrustSourcePanel",
        status=status,
        title="Data Trust & Source Panel",
        summary=summary,
        data_points=data_points,
        explanation=(
            "Every source row carries source, endpoint, as_of_date, available_at, fetched_at, stale, confidence, and missing flags.",
            "API key warnings show only key names and never secret values.",
            "Point-in-time status is a review gate for future backtests and decision modules.",
        ),
        risk_flags=tuple([*stale_sources, *missing_sources, *missing_api_keys]),
        stale_after_minutes=int(stale_after_hours * 60),
        latest_refresh_time=latest_refresh_time,
        point_in_time_status=point_in_time_status,
        source_coverage=tuple(rows),
        stale_sources=stale_sources,
        missing_sources=missing_sources,
        missing_api_keys=missing_api_keys,
    )


def data_trust_source_panel_api_response(state: DataTrustSourcePanelState) -> dict[str, Any]:
    payload = state.to_dict()
    payload["moduleId"] = payload.pop("module_id")
    payload["dataPoints"] = payload.pop("data_points")
    payload["latestRefreshTime"] = payload.pop("latest_refresh_time")
    payload["pointInTimeStatus"] = payload.pop("point_in_time_status")
    payload["sourceCoverage"] = payload.pop("source_coverage")
    payload["staleSources"] = payload.pop("stale_sources")
    payload["missingSources"] = payload.pop("missing_sources")
    payload["missingApiKeys"] = payload.pop("missing_api_keys")
    payload["staleAfterMinutes"] = payload.pop("stale_after_minutes")
    payload["apiPath"] = payload.pop("api_path")
    return payload
