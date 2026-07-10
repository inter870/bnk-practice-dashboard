from __future__ import annotations

from datetime import datetime, time, timezone
from math import isfinite
import re
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

from .models import DARTDisclosureCatalystPanelState, DARTDisclosureEventRow, DataPoint, DataSourceMeta


POSITIVE_CATEGORY_KEYWORDS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("share_buyback", "positive", ("share buyback", "자기주식취득", "자기주식 취득", "자사주 취득", "자사주매입")),
    ("treasury_stock_cancellation", "positive", ("treasury stock cancellation", "자기주식소각", "자기주식 소각", "자사주 소각")),
    ("dividend_increase", "positive", ("dividend increase", "배당 확대", "배당 증가", "현금배당", "중간배당")),
    ("large_contract", "positive", ("large contract", "단일판매", "공급계약", "수주", "판매공급계약")),
    ("earnings_improvement", "positive", ("earnings improvement", "실적개선", "영업이익 증가", "흑자전환", "잠정실적 증가")),
    ("value_up_plan", "positive", ("value-up", "value up", "밸류업", "기업가치 제고", "기업가치제고")),
    ("strategic_partnership", "positive", ("strategic partnership", "전략적 제휴", "mou", "합작", "joint venture")),
    ("regulatory_approval", "positive", ("regulatory approval", "품목허가", "승인", "허가", "인증")),
)

NEGATIVE_CATEGORY_KEYWORDS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("paid_in_capital_increase", "negative", ("paid-in capital increase", "유상증자", "주주배정증자", "제3자배정증자")),
    ("cb_bw_eb_issuance", "negative", ("cb", "bw", "eb", "전환사채", "신주인수권부사채", "교환사채")),
    ("dilution_risk", "negative", ("dilution", "희석", "주식관련사채", "전환청구권", "신주인수권")),
    ("audit_issue", "negative", ("audit issue", "감사의견", "의견거절", "한정", "부적정")),
    ("litigation", "negative", ("litigation", "소송", "피소", "중재")),
    ("embezzlement_breach_of_trust", "negative", ("embezzlement", "breach of trust", "횡령", "배임")),
    ("trading_halt", "negative", ("trading halt", "매매거래정지", "거래정지")),
    ("administrative_issue", "negative", ("administrative issue", "관리종목", "투자주의환기")),
    ("delisting_risk", "negative", ("delisting", "상장폐지", "실질심사")),
    ("earnings_shock", "negative", ("earnings shock", "실적악화", "영업손실", "적자전환", "어닝쇼크")),
)

SHAREHOLDER_RETURN_CATEGORIES = {"share_buyback", "treasury_stock_cancellation", "dividend_increase", "value_up_plan"}
DILUTION_CATEGORIES = {"paid_in_capital_increase", "cb_bw_eb_issuance", "dilution_risk"}


def _open_dart_receipt_datetime(date_value: Any, time_value: Any = None) -> datetime | None:
    date_text = str(date_value or "").strip()
    digits = re.sub(r"\D", "", date_text)
    try:
        receipt_date = datetime.strptime(digits[:8], "%Y%m%d").date() if len(digits) >= 8 else datetime.fromisoformat(date_text).date()
    except (TypeError, ValueError):
        return None
    time_match = re.search(r"(?<!\d)(\d{1,2}):(\d{2})(?::(\d{2}))?", str(time_value or ""))
    if time_match:
        hour, minute, second = (int(time_match.group(1)), int(time_match.group(2)), int(time_match.group(3) or 0))
        receipt_time = time(hour=hour, minute=minute, second=second)
    else:
        # list.json exposes only a receipt date. End-of-day admission avoids
        # treating a filing as tradable before its unknown intraday receipt time.
        receipt_time = time(23, 59, 59)
    return datetime.combine(receipt_date, receipt_time, tzinfo=ZoneInfo("Asia/Seoul"))


def adapt_open_dart_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    source: str,
    fetched_at: str | None,
    is_fallback: bool,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in rows:
        receipt_at = _open_dart_receipt_datetime(
            row.get("date") or row.get("receipt_date") or row.get("rcept_dt"),
            row.get("time"),
        )
        if receipt_at is None:
            continue
        stock_digits = re.sub(r"\D", "", str(row.get("stock_code") or row.get("code") or ""))
        code = stock_digits.zfill(6) if 0 < len(stock_digits) <= 6 else "N/A"
        source_url = str(row.get("report_url") or row.get("source_url") or "").strip()
        receipt_match = re.search(r"(?:rcpNo=|rcept_no=)(\d+)", source_url, flags=re.IGNORECASE)
        receipt_no = str(row.get("receipt_no") or row.get("rcept_no") or "").strip()
        if not receipt_no and receipt_match:
            receipt_no = receipt_match.group(1)
        events.append(
            {
                "receipt_no": receipt_no or source_url or "N/A",
                "code": code,
                "name": str(row.get("corp_name") or row.get("name") or "종목 미확인"),
                "title": str(row.get("report_name") or row.get("title") or "공시"),
                "receipt_date": receipt_at.date().isoformat(),
                "available_at": receipt_at.isoformat(),
                "source_url": source_url,
                "source": source,
                "fetched_at": fetched_at,
                "is_fallback": bool(is_fallback),
            }
        )
    return events
GOVERNANCE_RISK_CATEGORIES = {"audit_issue", "litigation", "embezzlement_breach_of_trust", "trading_halt", "administrative_issue", "delisting_risk"}

MOCK_DART_DISCLOSURES: tuple[dict[str, Any], ...] = (
    {
        "receipt_no": "20260705800111",
        "code": "005930",
        "name": "Samsung Electronics",
        "title": "자기주식 소각 결정",
        "summary": "Treasury stock cancellation supports shareholder return review.",
        "receipt_date": "2026-07-05T09:10:00+09:00",
        "available_at": "2026-07-05T09:12:00+09:00",
        "source_url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260705800111",
        "materiality_amount": 2_800_000_000_000,
        "market_cap": 460_000_000_000_000,
    },
    {
        "receipt_no": "20260702800047",
        "code": "000660",
        "name": "SK hynix",
        "title": "대규모 HBM 공급계약 체결",
        "summary": "Large contract disclosure is a positive operating catalyst, subject to margin confirmation.",
        "receipt_date": "2026-07-02T13:30:00+09:00",
        "available_at": "2026-07-02T13:32:00+09:00",
        "source_url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260702800047",
        "materiality_amount": 5_500_000_000_000,
        "market_cap": 210_000_000_000_000,
    },
    {
        "receipt_no": "20260701800033",
        "code": "034020",
        "name": "Doosan Enerbility",
        "title": "전환사채권 발행결정",
        "summary": "CB issuance creates dilution and balance sheet review needs.",
        "receipt_date": "2026-07-01T16:20:00+09:00",
        "available_at": "2026-07-01T16:22:00+09:00",
        "source_url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260701800033",
        "dilution_pct": 0.085,
        "materiality_amount": 720_000_000_000,
        "market_cap": 13_000_000_000_000,
    },
    {
        "receipt_no": "20260628800020",
        "code": "035420",
        "name": "NAVER",
        "title": "기업가치 제고 계획 공시",
        "summary": "Value-up plan needs execution tracking before ranking as durable catalyst.",
        "receipt_date": "2026-06-28T10:00:00+09:00",
        "available_at": "2026-06-28T10:03:00+09:00",
        "source_url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260628800020",
        "materiality_amount": 300_000_000_000,
        "market_cap": 36_000_000_000_000,
    },
    {
        "receipt_no": "20260623800151",
        "code": "105560",
        "name": "KB Financial",
        "title": "현금배당 확대 및 자사주 취득 신탁계약 체결",
        "summary": "Shareholder return disclosure supports value-up monitoring.",
        "receipt_date": "2026-06-23T15:40:00+09:00",
        "available_at": "2026-06-23T15:42:00+09:00",
        "source_url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260623800151",
        "materiality_amount": 1_100_000_000_000,
        "market_cap": 38_000_000_000_000,
    },
    {
        "receipt_no": "20260620800077",
        "code": "011200",
        "name": "HMM",
        "title": "잠정실적 영업이익 급감",
        "summary": "Earnings shock is a negative risk event until revisions stabilize.",
        "receipt_date": "2026-06-20T08:50:00+09:00",
        "available_at": "2026-06-20T08:55:00+09:00",
        "source_url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260620800077",
        "materiality_amount": 480_000_000_000,
        "market_cap": 8_700_000_000_000,
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


def _meta(
    *,
    source: str,
    endpoint: str,
    as_of_date: str | None,
    available_at: str | None,
    fetched_at: str | None,
    source_url: str | None,
    confidence: int,
    stale: bool,
    missing: bool,
    is_fallback: bool,
    warnings: tuple[str, ...] = (),
) -> DataSourceMeta:
    return DataSourceMeta(
        source=source,
        provider="OpenDART",
        source_url=source_url,
        as_of_date=as_of_date,
        available_at=available_at,
        fetched_at=fetched_at,
        frequency="event-driven",
        unit="disclosure_event",
        quality_score=max(0, min(100, confidence)),
        is_fallback=is_fallback,
        stale_data_flag=stale,
        source_table_or_endpoint=endpoint,
        confidence_score=max(0, min(100, confidence)),
        missing_data_flag=missing,
        warnings=warnings,
    )


def _text_blob(event: Any) -> str:
    parts = [
        _get(event, "category", "event_category", default=""),
        _get(event, "title", "report_name", "reportName", default=""),
        _get(event, "summary", "event_summary", default=""),
    ]
    return " ".join(str(part or "") for part in parts).lower().replace(" ", "")


def _match_category(event: Any) -> tuple[str, str]:
    explicit = str(_get(event, "category", "event_category", default="") or "").strip().lower().replace(" ", "_").replace("-", "_")
    category_ids = {row[0]: row[1] for row in POSITIVE_CATEGORY_KEYWORDS + NEGATIVE_CATEGORY_KEYWORDS}
    if explicit in category_ids:
        return explicit, category_ids[explicit]
    blob = _text_blob(event)
    for category, sentiment, keywords in NEGATIVE_CATEGORY_KEYWORDS:
        if any(keyword.lower().replace(" ", "") in blob for keyword in keywords):
            return category, sentiment
    for category, sentiment, keywords in POSITIVE_CATEGORY_KEYWORDS:
        if any(keyword.lower().replace(" ", "") in blob for keyword in keywords):
            return category, sentiment
    return "other", "neutral"


def classify_disclosure_event(event: Any) -> dict[str, Any]:
    category, sentiment = _match_category(event)
    summaries = {
        "share_buyback": "Share buyback disclosure; check size, method, and completion schedule.",
        "treasury_stock_cancellation": "Treasury stock cancellation; shareholder return catalyst candidate.",
        "dividend_increase": "Dividend increase or cash distribution; confirm sustainability.",
        "large_contract": "Large contract; confirm margins, duration, and customer concentration.",
        "earnings_improvement": "Earnings improvement; verify whether operating cash flow confirms it.",
        "value_up_plan": "Value-up plan; track execution milestones and shareholder return details.",
        "strategic_partnership": "Strategic partnership; confirm binding terms and expected economics.",
        "regulatory_approval": "Regulatory approval; check commercialization timing.",
        "paid_in_capital_increase": "Paid-in capital increase; dilution and use-of-proceeds review required.",
        "cb_bw_eb_issuance": "CB/BW/EB issuance; dilution and refinancing risk review required.",
        "dilution_risk": "Dilution-related event; check conversion terms and overhang.",
        "audit_issue": "Audit issue; governance and investability review required.",
        "litigation": "Litigation disclosure; check claim amount and probability.",
        "embezzlement_breach_of_trust": "Embezzlement or breach of trust risk; governance review required.",
        "trading_halt": "Trading halt; liquidity and exit-risk review required.",
        "administrative_issue": "Administrative issue; exchange status review required.",
        "delisting_risk": "Delisting risk; capital preservation review required.",
        "earnings_shock": "Earnings shock; reassess thesis and estimate risk.",
    }
    return {
        "category": category,
        "sentiment": sentiment,
        "event_summary": str(_get(event, "summary", default="") or summaries.get(category, "Unclassified disclosure; manual review required.")),
    }


def _materiality_ratio(event: Any) -> float | None:
    amount = _finite(_get(event, "materiality_amount", "amount", "contract_amount"))
    base = _finite(_get(event, "market_cap", "marketCap", "equity_value"))
    if amount is None or base is None or base <= 0:
        return None
    return abs(amount) / base


def calculate_materiality_score(event: Any, category: str | None = None) -> int:
    category = category or classify_disclosure_event(event)["category"]
    base_scores = {
        "share_buyback": 58,
        "treasury_stock_cancellation": 68,
        "dividend_increase": 52,
        "large_contract": 62,
        "earnings_improvement": 58,
        "value_up_plan": 56,
        "strategic_partnership": 52,
        "regulatory_approval": 60,
        "paid_in_capital_increase": 76,
        "cb_bw_eb_issuance": 72,
        "dilution_risk": 70,
        "audit_issue": 88,
        "litigation": 70,
        "embezzlement_breach_of_trust": 95,
        "trading_halt": 88,
        "administrative_issue": 82,
        "delisting_risk": 100,
        "earnings_shock": 76,
        "other": 35,
    }
    score = float(base_scores.get(category, 35))
    ratio = _materiality_ratio(event)
    if ratio is not None:
        if ratio >= 0.10:
            score += 22
        elif ratio >= 0.05:
            score += 16
        elif ratio >= 0.02:
            score += 10
        elif ratio >= 0.01:
            score += 5
    severity = str(_get(event, "severity", default="") or "").lower()
    if severity in {"critical", "high"}:
        score += 10 if severity == "high" else 18
    return int(round(_clamp(score, 0, 100)))


def calculate_dilution_risk_score(event: Any, category: str | None = None) -> int:
    category = category or classify_disclosure_event(event)["category"]
    base = 0.0
    if category == "paid_in_capital_increase":
        base = 70
    elif category == "cb_bw_eb_issuance":
        base = 64
    elif category == "dilution_risk":
        base = 62
    dilution_pct = _finite(_get(event, "dilution_pct", "dilutionPercent", "expected_dilution"))
    if dilution_pct is not None:
        if dilution_pct >= 0.20:
            base += 28
        elif dilution_pct >= 0.10:
            base += 20
        elif dilution_pct >= 0.05:
            base += 12
        elif dilution_pct > 0:
            base += 6
    return int(round(_clamp(base, 0, 100)))


def calculate_governance_risk_score(event: Any, category: str | None = None) -> int:
    category = category or classify_disclosure_event(event)["category"]
    base_scores = {
        "audit_issue": 84,
        "litigation": 60,
        "embezzlement_breach_of_trust": 96,
        "trading_halt": 78,
        "administrative_issue": 76,
        "delisting_risk": 100,
    }
    return int(round(_clamp(base_scores.get(category, 0), 0, 100)))


def _catalyst_score(event: Any, *, category: str, sentiment: str, materiality: int, dilution: int, governance: int) -> int:
    if sentiment == "positive":
        score = materiality
        if category in SHAREHOLDER_RETURN_CATEGORIES:
            score += 8
        return int(round(_clamp(score, 0, 100)))
    if sentiment == "negative":
        return int(round(_clamp(25 - max(dilution, governance) * 0.2, 0, 35)))
    return int(round(_clamp(materiality * 0.45, 0, 50)))


def select_point_in_time_disclosures(events: Iterable[Any], as_of: datetime | None = None) -> list[Any]:
    cutoff = as_of or datetime.now(timezone.utc)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    selected: list[tuple[datetime, Any]] = []
    for event in events:
        available_at = _as_datetime(_get(event, "available_at", "availableAt", "receipt_date", "receiptDate", "date"))
        if available_at is None:
            continue
        if available_at <= cutoff:
            selected.append((available_at, event))
    return [event for _, event in sorted(selected, key=lambda pair: pair[0], reverse=True)]


def _build_rows(
    events: Iterable[Any],
    *,
    now: datetime | None,
    stale_after_hours: float,
    fallback: bool,
) -> tuple[DARTDisclosureEventRow, ...]:
    rows: list[DARTDisclosureEventRow] = []
    default_fetched_at = _now_iso(now)
    for event in select_point_in_time_disclosures(events, now):
        classified = classify_disclosure_event(event)
        category = str(classified["category"])
        sentiment = str(classified["sentiment"])
        materiality = calculate_materiality_score(event, category)
        dilution = calculate_dilution_risk_score(event, category)
        governance = calculate_governance_risk_score(event, category)
        catalyst = _catalyst_score(event, category=category, sentiment=sentiment, materiality=materiality, dilution=dilution, governance=governance)
        available_at = _get(event, "available_at", "availableAt", "receipt_date", "receiptDate", "date")
        receipt_date = _get(event, "receipt_date", "receiptDate", "date")
        source_url = str(_get(event, "source_url", "url", "filing_url", default="") or "") or None
        reference = str(_get(event, "receipt_no", "rcp_no", "rcept_no", default="") or "") or source_url
        missing = not bool(reference)
        stale = _is_stale(available_at, now=now, stale_after_hours=stale_after_hours)
        event_fetched_at = _as_datetime(_get(event, "fetched_at", "fetchedAt"))
        fetched_at = _now_iso(event_fetched_at) if event_fetched_at is not None else default_fetched_at
        confidence = 72 if fallback else 88
        if missing:
            confidence -= 20
        if category == "other":
            confidence -= 15
        meta = _meta(
            source=str(_get(event, "source", default="Mock OpenDART disclosures") or "Mock OpenDART disclosures"),
            endpoint="/api/dashboard/dart-catalysts",
            as_of_date=_as_date_text(receipt_date or available_at),
            available_at=_now_iso(_as_datetime(available_at)) if _as_datetime(available_at) else None,
            fetched_at=fetched_at,
            source_url=source_url,
            confidence=confidence,
            stale=stale,
            missing=missing,
            is_fallback=bool(fallback or _get(event, "is_fallback", default=False)),
            warnings=tuple(["unclassified_disclosure"] if category == "other" else []),
        )
        raw_code = str(_get(event, "code", "stock_code", "stockCode", default="") or "").strip()
        normalized_code = raw_code.zfill(6) if raw_code.isdigit() and len(raw_code) <= 6 else "N/A"
        rows.append(
            DARTDisclosureEventRow(
                receipt_no=str(_get(event, "receipt_no", "rcp_no", "rcept_no", default=reference or "N/A") or "N/A"),
                code=normalized_code,
                name=str(_get(event, "name", "corp_name", "corpName", default="Unknown") or "Unknown"),
                title=str(_get(event, "title", "report_name", "reportName", default="Disclosure event") or "Disclosure event"),
                category=category,
                sentiment=sentiment,  # type: ignore[arg-type]
                materiality_score=materiality,
                catalyst_score=catalyst,
                dilution_risk_score=dilution,
                governance_risk_score=governance,
                event_summary=str(classified["event_summary"]),
                source_filing_reference=reference,
                receipt_date=_as_date_text(receipt_date),
                available_at=meta.available_at,
                meta=meta,
            )
        )
    return tuple(sorted(rows, key=lambda row: (row.available_at or "", row.materiality_score), reverse=True))


def build_dart_disclosure_catalyst_panel(
    *,
    disclosure_events: Iterable[Any] | None = None,
    now: datetime | None = None,
    stale_after_hours: float = 24.0 * 30,
    allow_mock: bool = True,
) -> DARTDisclosureCatalystPanelState:
    raw_events = list(disclosure_events or [])
    fallback = False
    if not raw_events and allow_mock:
        raw_events = [dict(item, is_fallback=True) for item in MOCK_DART_DISCLOSURES]
        fallback = True
    if not raw_events:
        fetched_at = _now_iso(now)
        meta = _meta(
            source="Not connected",
            endpoint="/api/dashboard/dart-catalysts",
            as_of_date=None,
            available_at=None,
            fetched_at=fetched_at,
            source_url=None,
            confidence=0,
            stale=True,
            missing=True,
            is_fallback=True,
        )
        return DARTDisclosureCatalystPanelState(
            module_id="DARTDisclosureCatalystPanel",
            status="empty",
            title="DART Disclosure Catalyst Panel",
            summary="No DART disclosure events are available.",
            data_points=(DataPoint("disclosure_count", "Disclosure Count", 0, meta, "0"),),
            explanation=("Connect OpenDART list/detail events with receipt_date or available_at timestamps.",),
            risk_flags=("missing_dart_disclosure_data",),
            stale_after_minutes=int(stale_after_hours * 60),
        )

    rows = _build_rows(raw_events, now=now, stale_after_hours=stale_after_hours, fallback=fallback)
    if not rows:
        fetched_at = _now_iso(now)
        meta = _meta(
            source="OpenDART",
            endpoint="/api/dashboard/dart-catalysts",
            as_of_date=None,
            available_at=None,
            fetched_at=fetched_at,
            source_url=None,
            confidence=20,
            stale=False,
            missing=True,
            is_fallback=fallback,
            warnings=("No point-in-time disclosures were available at the selected cutoff.",),
        )
        return DARTDisclosureCatalystPanelState(
            module_id="DARTDisclosureCatalystPanel",
            status="empty",
            title="DART Disclosure Catalyst Panel",
            summary="No point-in-time DART disclosures are available for the selected cutoff.",
            data_points=(DataPoint("disclosure_count", "Disclosure Count", 0, meta, "0"),),
            explanation=("Future disclosure rows are excluded until receipt_date or available_at.",),
            risk_flags=("no_point_in_time_disclosures",),
            stale_after_minutes=int(stale_after_hours * 60),
        )

    stale = any(row.meta.stale_data_flag for row in rows)
    missing = any(row.meta.missing_data_flag for row in rows)
    high_materiality = tuple(sorted([row for row in rows if row.materiality_score >= 70], key=lambda row: (-row.materiality_score, row.available_at or ""))[:6])
    positive = tuple(sorted([row for row in rows if row.sentiment == "positive"], key=lambda row: (-row.catalyst_score, -row.materiality_score))[:6])
    negative = tuple(sorted([row for row in rows if row.sentiment == "negative"], key=lambda row: (-max(row.dilution_risk_score, row.governance_risk_score, row.materiality_score), row.available_at or ""))[:6])
    dilution = tuple(sorted([row for row in rows if row.dilution_risk_score >= 40], key=lambda row: (-row.dilution_risk_score, row.available_at or ""))[:6])
    shareholder = tuple(sorted([row for row in rows if row.category in SHAREHOLDER_RETURN_CATEGORIES], key=lambda row: (-row.catalyst_score, row.available_at or ""))[:6])
    avg_confidence = int(round(sum((row.meta.confidence_score or row.meta.quality_score) for row in rows) / len(rows))) if rows else 0
    module_meta = _meta(
        source="DART Disclosure Catalyst Panel",
        endpoint="/api/dashboard/dart-catalysts",
        as_of_date=max((row.receipt_date or "" for row in rows), default=None) or None,
        available_at=max((row.available_at or "" for row in rows), default=None) or None,
        fetched_at=_now_iso(now),
        source_url=None,
        confidence=avg_confidence,
        stale=stale,
        missing=missing,
        is_fallback=any(row.meta.is_fallback for row in rows),
    )
    risk_flags = []
    if stale:
        risk_flags.append("stale_dart_disclosure_data")
    if missing:
        risk_flags.append("missing_filing_reference")
    if dilution:
        risk_flags.append("dilution_watchlist_active")
    if any(row.governance_risk_score >= 70 for row in negative):
        risk_flags.append("governance_risk_event")
    data_points = (
        DataPoint("disclosure_count", "Disclosure Count", len(rows), module_meta, str(len(rows))),
        DataPoint("high_materiality_count", "High Materiality Disclosures", len(high_materiality), module_meta, str(len(high_materiality))),
        DataPoint("positive_catalyst_count", "Positive Catalyst Count", len(positive), module_meta, str(len(positive))),
        DataPoint("negative_risk_count", "Negative Risk Count", len(negative), module_meta, str(len(negative))),
        DataPoint("dilution_watch_count", "Dilution Watch Count", len(dilution), module_meta, str(len(dilution))),
    )
    status = "stale" if stale else "ready"
    summary = "DART disclosure catalysts and risks are classified using point-in-time receipt_date / available_at."
    if fallback:
        summary = "Mock OpenDART disclosure catalysts are shown until real DART event adapters are connected."
    if missing:
        summary = "Some disclosure rows are missing source filing references; manual verification is required."
    return DARTDisclosureCatalystPanelState(
        module_id="DARTDisclosureCatalystPanel",
        status=status,
        title="DART Disclosure Catalyst Panel",
        summary=summary,
        data_points=data_points,
        explanation=(
            "Positive catalysts include buybacks, treasury stock cancellation, dividend increases, contracts, value-up plans, partnerships, and approvals.",
            "Negative risks include capital increases, CB/BW/EB, audit issues, litigation, governance events, trading halts, administrative issues, delisting risk, and earnings shocks.",
            "Events are admitted only from receipt_date or available_at; future filings are excluded.",
        ),
        risk_flags=tuple(risk_flags),
        stale_after_minutes=int(stale_after_hours * 60),
        event_rows=rows,
        latest_high_materiality_disclosures=high_materiality,
        positive_catalysts=positive,
        negative_risks=negative,
        dilution_watchlist=dilution,
        shareholder_return_announcements=shareholder,
        event_timeline=tuple(sorted(rows, key=lambda row: row.available_at or "", reverse=True)[:12]),
        latest_source_at=max((row.available_at or "" for row in rows), default=None) or None,
    )


def dart_disclosure_catalyst_api_response(state: DARTDisclosureCatalystPanelState) -> dict[str, Any]:
    payload = state.to_dict()
    payload["moduleId"] = payload.pop("module_id")
    payload["dataPoints"] = payload.pop("data_points")
    payload["eventRows"] = payload.pop("event_rows")
    payload["latestHighMaterialityDisclosures"] = payload.pop("latest_high_materiality_disclosures")
    payload["positiveCatalysts"] = payload.pop("positive_catalysts")
    payload["negativeRisks"] = payload.pop("negative_risks")
    payload["dilutionWatchlist"] = payload.pop("dilution_watchlist")
    payload["shareholderReturnAnnouncements"] = payload.pop("shareholder_return_announcements")
    payload["eventTimeline"] = payload.pop("event_timeline")
    payload["latestSourceAt"] = payload.pop("latest_source_at")
    payload["staleAfterMinutes"] = payload.pop("stale_after_minutes")
    payload["apiPath"] = payload.pop("api_path")
    return payload
