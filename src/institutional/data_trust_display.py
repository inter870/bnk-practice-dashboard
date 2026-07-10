from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from .models import SourceCoverageRow


KST = timezone(timedelta(hours=9))

_MISSING_TEXT = {"", "n/a", "na", "none", "null", "nan", "n\\a"}

_MODULE_LABEL_KO = {
    "portfolio": "포트폴리오 데이터",
    "market_price": "시장 가격 데이터",
    "valuation": "밸류에이션 데이터",
    "financial_statement": "재무제표 데이터",
    "dart_disclosure": "DART 공시 데이터",
    "macro": "매크로 데이터",
    "fx_rates": "환율·금리 데이터",
    "investor_flow": "수급 데이터",
    "short_selling": "공매도 데이터",
}

_STATUS_LABEL_KO = {
    "available": "사용 가능",
    "connected": "연결됨",
    "partial": "부분 연결",
    "partially_connected": "부분 연결",
    "manual": "수동 입력",
    "mock": "모의 데이터",
    "stale": "업데이트 필요",
    "missing": "데이터 없음",
    "missing_key": "키 필요",
    "adapter_missing": "어댑터 미연결",
    "planned": "연결 예정",
    "cache_only": "캐시 사용",
    "unavailable": "표시 불가",
    "error": "오류",
}

_ACCURACY_LABEL_KO = {
    "official_realtime": "공식 실시간",
    "official_eod": "공식 EOD",
    "exact_official": "공식 수치",
    "exact_broker": "브로커 수치",
    "public_snapshot": "공개 스냅샷",
    "public_delayed": "지연 공개 데이터",
    "manual": "수동 입력",
    "mock": "모의 데이터",
    "cached": "캐시",
    "planned": "표시 불가",
    "unavailable": "표시 불가",
}

_PLANNED_SOURCE_LABEL_KO = {
    "planned:krx_valuation": "KRX/OpenDART 어댑터 연결 예정",
    "planned:krx_investor_flow": "KRX 수급 어댑터 연결 예정",
    "planned:krx_short_selling": "KRX 공매도 어댑터 연결 예정",
}

_PLANNED_MESSAGE_KO = {
    "valuation": "밸류에이션 어댑터가 아직 연결되지 않아 정확 수치를 표시할 수 없습니다.",
    "investor_flow": "수급 데이터 어댑터가 아직 연결되지 않아 정확 수치를 표시할 수 없습니다.",
    "short_selling": "공매도 데이터 어댑터가 아직 연결되지 않아 정확 수치를 표시할 수 없습니다.",
}

_DEFAULT_MESSAGE_KO = {
    "portfolio": "포트폴리오 입력 출처와 보유 데이터의 신뢰도를 확인합니다.",
    "market_price": "시장 가격 데이터의 출처, 신선도, 키 필요 여부를 확인합니다.",
    "financial_statement": "재무제표 데이터는 사용 가능 시점 기준으로 검토합니다.",
    "dart_disclosure": "공시 데이터는 접수일과 사용 가능 시점 기준으로 검토합니다.",
    "macro": "매크로 데이터의 출처와 업데이트 상태를 확인합니다.",
    "fx_rates": "환율·금리 데이터의 출처와 신선도를 확인합니다.",
}


@dataclass(frozen=True)
class DataTrustDisplayFields:
    titleKo: str
    primaryMessageKo: str
    secondaryMessageKo: str | None
    statusBadgeKo: str
    accuracyBadgeKo: str
    confidenceKo: str
    keyStatusKo: str
    missingKeysKo: str | None
    sourceKo: str
    endpointKo: str
    asOfDateKo: str
    fetchedAtKo: str
    availableAtKo: str | None
    freshnessKo: str | None
    actionRequiredKo: str | None
    compactLineKo: str


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text.lower() in _MISSING_TEXT


def _parse_datetime(value: Any) -> tuple[datetime | None, bool]:
    if _is_missing(value):
        return None, False
    if isinstance(value, datetime):
        return value, False
    if isinstance(value, date):
        return datetime.combine(value, time.min), False
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")), False
    except ValueError:
        return None, True


def _format_datetime_value(value: Any) -> tuple[str, bool]:
    stamp, invalid = _parse_datetime(value)
    if invalid:
        return "형식 오류", True
    if stamp is None:
        return "확인 불가", False
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(KST).strftime("%Y.%m.%d %H:%M"), False


def formatKoDateTime(value: Any, timezone_name: str = "Asia/Seoul") -> str:
    # timezone_name is kept for the public helper contract. Current dashboard UI
    # displays all normal timestamps in Asia/Seoul.
    _ = timezone_name
    formatted, invalid = _format_datetime_value(value)
    if invalid:
        return "수집 시각: 형식 오류"
    if formatted == "확인 불가":
        return "수집 시각: 확인 불가"
    return f"수집 시각: {formatted}"


def _format_date_value(value: Any, *, planned: bool = False) -> tuple[str, bool]:
    if planned or _is_missing(value):
        return "해당 없음", False
    stamp, invalid = _parse_datetime(value)
    if invalid:
        text = str(value).strip()
        if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
            return text[:10].replace("-", "."), False
        return "형식 오류", True
    if stamp is None:
        return "해당 없음", False
    if stamp.tzinfo is not None:
        stamp = stamp.astimezone(KST)
    return stamp.strftime("%Y.%m.%d"), False


def formatDataTrustAsOfDateKo(value: Any, *, planned: bool = False) -> str:
    formatted, _ = _format_date_value(value, planned=planned)
    return f"기준일: {formatted}"


def _row_status(row: SourceCoverageRow) -> str:
    return str(row.status or row.coverage_status or "").strip()


def isPlannedAdapter(row: SourceCoverageRow) -> bool:
    adapter_id = str(row.adapter_id or row.source_endpoint or row.meta.source_table_or_endpoint or "")
    status = _row_status(row)
    source_type = str(getattr(row, "source_type", "") or "")
    return bool(
        row.is_planned
        or getattr(row, "is_adapter_missing", False)
        or source_type == "planned"
        or status in {"planned", "adapter_missing"}
        or adapter_id.startswith("planned:")
    )


def _required_keys(row: SourceCoverageRow) -> tuple[str, ...]:
    return tuple(row.required_keys or row.required_api_keys or ())


def _missing_keys(row: SourceCoverageRow) -> tuple[str, ...]:
    return tuple(row.missing_keys or row.missing_api_keys or ())


def _optional_missing_keys(row: SourceCoverageRow) -> tuple[str, ...]:
    return tuple(
        getattr(row, "optional_missing_keys", ())
        or getattr(row, "optional_missing_api_keys", ())
        or ()
    )


def _is_public_keyless(row: SourceCoverageRow) -> bool:
    source_text = " ".join(
        str(part or "")
        for part in (
            row.active_source_id,
            row.active_source_label_ko,
            row.meta.source,
            row.adapter_id,
        )
    ).lower()
    return row.is_keyless and any(token in source_text for token in ("naver", "finance", "public", "fdr"))


def formatKeyStatusKo(row: SourceCoverageRow) -> str:
    if isPlannedAdapter(row):
        return "키 확인: 어댑터 구현 후 확인"

    missing = _missing_keys(row)
    required = _required_keys(row)
    optional_missing = _optional_missing_keys(row)

    if missing:
        return "누락 키: " + ", ".join(missing)
    if required:
        return "필요 키: 설정됨"
    if optional_missing:
        return "선택 키 미설정: " + ", ".join(optional_missing)
    if _is_public_keyless(row):
        return "키 없이 공개 데이터 사용 중"
    if row.is_keyless:
        return "필요 키: 없음"
    return "키 상태: 확인 필요"


def _missing_keys_line(row: SourceCoverageRow) -> str | None:
    missing = _missing_keys(row)
    if not missing or isPlannedAdapter(row):
        return None
    return "누락 키: " + ", ".join(missing)


def _module_label(row: SourceCoverageRow) -> str:
    return _MODULE_LABEL_KO.get(row.module_key, str(row.label or row.module_key))


def _status_label(row: SourceCoverageRow) -> str:
    if isPlannedAdapter(row):
        return "연결 예정"
    return _STATUS_LABEL_KO.get(_row_status(row), row.status_label_ko or "상태 확인 필요")


def _accuracy_label(row: SourceCoverageRow) -> str:
    if isPlannedAdapter(row):
        return "표시 불가"
    return _ACCURACY_LABEL_KO.get(row.accuracy_grade, row.accuracy_grade_label_ko or row.exactness_label_ko or "확인 필요")


def _source_label(row: SourceCoverageRow) -> str:
    endpoint = str(row.meta.source_table_or_endpoint or row.source_endpoint or row.adapter_id or "")
    if isPlannedAdapter(row):
        return _PLANNED_SOURCE_LABEL_KO.get(endpoint, "어댑터 연결 예정")
    source = str(row.active_source_label_ko or row.meta.source or "").strip()
    return source if source and source.lower() not in _MISSING_TEXT else "출처 확인 필요"


def _endpoint_label(row: SourceCoverageRow) -> str:
    endpoint = str(row.meta.source_table_or_endpoint or row.source_endpoint or row.adapter_id or "").strip()
    if not endpoint or endpoint.lower() in _MISSING_TEXT:
        return "엔드포인트: 확인 필요"
    return f"엔드포인트: {endpoint}"


def _primary_message(row: SourceCoverageRow) -> str:
    if isPlannedAdapter(row):
        return _PLANNED_MESSAGE_KO.get(
            row.module_key,
            f"{_module_label(row)} 어댑터가 아직 연결되지 않아 정확 수치를 표시할 수 없습니다.",
        )
    return _DEFAULT_MESSAGE_KO.get(row.module_key, row.message_ko or "데이터 출처 상태를 확인합니다.")


def _freshness(row: SourceCoverageRow) -> str | None:
    if isPlannedAdapter(row):
        return "일정 미정"
    if row.meta.stale_data_flag:
        return "업데이트 필요"
    if row.meta.missing_data_flag and not isPlannedAdapter(row):
        return "데이터 없음"
    return "정상"


def _confidence(row: SourceCoverageRow) -> str:
    score = row.meta.confidence_score
    if isPlannedAdapter(row):
        return "신뢰도 해당 없음"
    if score is None:
        return "신뢰도 확인 불가"
    return f"신뢰도 {max(0, min(100, int(score)))}/100"


def formatDataTrustMetadataKo(row: SourceCoverageRow) -> DataTrustDisplayFields:
    planned = isPlannedAdapter(row)
    key_status = formatKeyStatusKo(row)
    fetched_at = formatKoDateTime(row.meta.fetched_at)
    as_of = formatDataTrustAsOfDateKo(row.meta.as_of_date, planned=planned)
    available_at = None if planned else formatDataTrustAsOfDateKo(row.meta.available_at).replace("기준일", "사용 가능 시점", 1)
    primary = _primary_message(row)
    action = key_status if planned or key_status.startswith(("누락 키:", "선택 키 미설정:")) else None
    compact_parts = [primary, key_status, fetched_at]
    compact = " · ".join(part for part in compact_parts if part)
    return DataTrustDisplayFields(
        titleKo=_module_label(row),
        primaryMessageKo=primary,
        secondaryMessageKo=None,
        statusBadgeKo=_status_label(row),
        accuracyBadgeKo=_accuracy_label(row),
        confidenceKo=_confidence(row),
        keyStatusKo=key_status,
        missingKeysKo=_missing_keys_line(row),
        sourceKo=_source_label(row),
        endpointKo=_endpoint_label(row),
        asOfDateKo=as_of,
        fetchedAtKo=fetched_at,
        availableAtKo=available_at,
        freshnessKo=_freshness(row),
        actionRequiredKo=action,
        compactLineKo=compact,
    )


def buildDataSourceStatusLine(row: SourceCoverageRow) -> str:
    return formatDataTrustMetadataKo(row).compactLineKo
