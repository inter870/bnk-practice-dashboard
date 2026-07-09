from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


SourceType = Literal[
    "official_api",
    "public_web",
    "public_api",
    "broker_api",
    "manual_input",
    "cache",
    "mock",
    "planned",
]


KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "OPENDART_API_KEY": ("OPENDART_API_KEY", "DART_API_KEY", "OPEN_DART_API_KEY"),
    "BOK_ECOS_API_KEY": ("BOK_ECOS_API_KEY", "ECOS_API_KEY", "ECOS_AUTH_KEY", "BANK_OF_KOREA_API_KEY"),
}


STATUS_LABEL_KO = {
    "connected": "연결됨",
    "partially_connected": "일부 연결",
    "missing_key": "키 필요",
    "adapter_missing": "어댑터 미연결",
    "planned": "연결 예정",
    "stale": "업데이트 필요",
    "cache_only": "캐시 데이터",
    "mock": "모의 데이터",
    "manual": "수동 입력",
    "unavailable": "사용 불가",
    "error": "오류",
}

ACCURACY_LABEL_KO = {
    "official_realtime": "공식 실시간",
    "official_eod": "공식 일마감",
    "broker_realtime": "증권사 실시간",
    "public_delayed": "공개 지연",
    "public_snapshot": "공개 스냅샷",
    "cached": "캐시",
    "manual": "수동 입력",
    "mock": "모의",
    "planned": "연결 예정",
    "unavailable": "사용 불가",
    "derived": "계산값",
}

EXACTNESS_LABEL_KO = {
    "exact_official": "공식 원천값",
    "exact_broker": "증권사 원천값",
    "official_eod": "공식 일마감값",
    "derived": "계산값",
    "public_snapshot": "공개 스냅샷",
    "cached": "캐시값",
    "manual": "수동 입력값",
    "mock": "모의값",
    "unavailable": "표시 불가",
    "planned": "표시 불가",
}

CATEGORY_LABEL_KO = {
    "portfolio_holdings": "포트폴리오 보유 데이터",
    "market_price": "시장가격 데이터",
    "valuation": "밸류에이션 데이터",
    "financial_statements": "재무제표 데이터",
    "dart_disclosures": "DART 공시 데이터",
    "macro": "매크로 데이터",
    "fx_rates": "환율·금리 데이터",
    "investor_flow": "투자자 수급 데이터",
    "short_selling": "공매도 데이터",
}


@dataclass(frozen=True)
class DataSourceDefinition:
    source_id: str
    display_name_ko: str
    category: str
    adapter_id: str
    source_type: SourceType
    requires_auth: bool
    required_env_keys: tuple[str, ...] = ()
    optional_env_keys: tuple[str, ...] = ()
    supports_realtime: bool = False
    supports_eod: bool = False
    supports_historical: bool = False
    expected_latency: str = "unknown"
    officialness_level: str = "derived"
    reliability_base_score: int = 0
    legal_access_mode: str = "no_key_required"
    fallback_rank: int = 100
    stale_after_minutes: int | None = None
    stale_after_hours: int | None = None
    terms_note: str = ""
    user_visible_warning_ko: str = ""
    display_name_en: str | None = None
    adapter_available: bool = True


@dataclass(frozen=True)
class SourceResolution:
    category: str
    selected_source: DataSourceDefinition | None
    status: str
    accuracy_grade: str
    exactness_level: str
    confidence_score: int
    selected_reason_ko: str
    blocked_sources: tuple[tuple[str, str], ...] = ()
    missing_keys: tuple[str, ...] = ()
    fallback_path: tuple[str, ...] = ()
    can_compute_exact_value: bool = False
    can_compute_best_effort_value: bool = False
    cache_age: str | None = None


SOURCE_REGISTRY: dict[str, DataSourceDefinition] = {
    "manual_portfolio_holdings": DataSourceDefinition(
        source_id="manual_portfolio_holdings",
        display_name_ko="수동 입력 보유 종목",
        display_name_en="Manual portfolio holdings",
        category="portfolio_holdings",
        adapter_id="sidebar:portfolio_holdings_text",
        source_type="manual_input",
        requires_auth=False,
        supports_eod=True,
        expected_latency="manual",
        officialness_level="derived",
        reliability_base_score=85,
        legal_access_mode="no_key_required",
        fallback_rank=20,
    ),
    "mock_portfolio_holdings": DataSourceDefinition(
        source_id="mock_portfolio_holdings",
        display_name_ko="모의 포트폴리오 데이터",
        category="portfolio_holdings",
        adapter_id="mock:portfolio_holdings",
        source_type="mock",
        requires_auth=False,
        supports_eod=True,
        expected_latency="manual",
        officialness_level="mock",
        reliability_base_score=20,
        legal_access_mode="no_key_required",
        fallback_rank=90,
        user_visible_warning_ko="모의 데이터입니다. 실제 투자 판단에는 사용하지 마세요.",
    ),
    "kis_portfolio_holdings": DataSourceDefinition(
        source_id="kis_portfolio_holdings",
        display_name_ko="한국투자증권 보유 종목",
        category="portfolio_holdings",
        adapter_id="kis:portfolio_holdings",
        source_type="broker_api",
        requires_auth=True,
        required_env_keys=("KIS_APP_KEY", "KIS_APP_SECRET"),
        optional_env_keys=("KIS_ACCOUNT_NO", "KIS_ACCOUNT_PRODUCT_CODE"),
        supports_realtime=True,
        supports_eod=True,
        expected_latency="realtime",
        officialness_level="broker",
        reliability_base_score=88,
        legal_access_mode="user_key_required",
        fallback_rank=10,
        user_visible_warning_ko="한국투자증권 API 키와 계좌 설정이 필요합니다.",
        adapter_available=False,
    ),
    "naver_finance_market_snapshot": DataSourceDefinition(
        source_id="naver_finance_market_snapshot",
        display_name_ko="Naver Finance 시장 스냅샷",
        category="market_price",
        adapter_id="load_market_snapshot:naver",
        source_type="public_web",
        requires_auth=False,
        supports_eod=True,
        expected_latency="delayed",
        officialness_level="public_web",
        reliability_base_score=76,
        legal_access_mode="no_key_required",
        fallback_rank=40,
        user_visible_warning_ko="공개 웹 데이터 기반입니다. 지연 또는 구조 변경 가능성이 있습니다.",
    ),
    "finance_data_reader_market": DataSourceDefinition(
        source_id="finance_data_reader_market",
        display_name_ko="FinanceDataReader 시장 데이터",
        category="market_price",
        adapter_id="FinanceDataReader",
        source_type="public_web",
        requires_auth=False,
        supports_eod=True,
        supports_historical=True,
        expected_latency="delayed",
        officialness_level="derived",
        reliability_base_score=70,
        legal_access_mode="no_key_required",
        fallback_rank=50,
        user_visible_warning_ko="공개 데이터 래퍼 기반입니다. 공식 API와 값 차이가 있을 수 있습니다.",
    ),
    "kis_market_price": DataSourceDefinition(
        source_id="kis_market_price",
        display_name_ko="한국투자증권 시세 API",
        category="market_price",
        adapter_id="kis:market_price",
        source_type="broker_api",
        requires_auth=True,
        required_env_keys=("KIS_APP_KEY", "KIS_APP_SECRET"),
        supports_realtime=True,
        supports_eod=True,
        supports_historical=True,
        expected_latency="realtime",
        officialness_level="broker",
        reliability_base_score=88,
        legal_access_mode="user_key_required",
        fallback_rank=10,
    ),
    "public_data_krx_stock_price": DataSourceDefinition(
        source_id="public_data_krx_stock_price",
        display_name_ko="공공데이터포털 KRX 주식시세",
        category="market_price",
        adapter_id="public_data:krx_stock_price",
        source_type="public_api",
        requires_auth=True,
        required_env_keys=("PUBLIC_DATA_API_KEY",),
        supports_eod=True,
        supports_historical=True,
        expected_latency="daily",
        officialness_level="official",
        reliability_base_score=85,
        legal_access_mode="api_key_required",
        fallback_rank=20,
        user_visible_warning_ko="일마감 데이터입니다. 실시간 시세가 아닙니다.",
        adapter_available=False,
    ),
    "krx_data_marketplace": DataSourceDefinition(
        source_id="krx_data_marketplace",
        display_name_ko="KRX Data Marketplace",
        category="market_price",
        adapter_id="krx:data_marketplace",
        source_type="official_api",
        requires_auth=False,
        supports_eod=True,
        supports_historical=True,
        expected_latency="daily",
        officialness_level="official",
        reliability_base_score=88,
        legal_access_mode="no_key_required",
        fallback_rank=30,
        user_visible_warning_ko="한국거래소 공개 데이터 기준입니다. 실시간성은 항목별로 다를 수 있습니다.",
        adapter_available=False,
    ),
    "opendart_financials": DataSourceDefinition(
        source_id="opendart_financials",
        display_name_ko="OpenDART 재무제표",
        category="financial_statements",
        adapter_id="opendart:fins_acnt/fnlttSinglAcntAll",
        source_type="official_api",
        requires_auth=True,
        required_env_keys=("OPENDART_API_KEY",),
        supports_eod=True,
        supports_historical=True,
        expected_latency="daily",
        officialness_level="official",
        reliability_base_score=90,
        legal_access_mode="api_key_required",
        fallback_rank=10,
        user_visible_warning_ko="OpenDART 인증키가 필요합니다.",
    ),
    "opendart_disclosures": DataSourceDefinition(
        source_id="opendart_disclosures",
        display_name_ko="OpenDART 공시",
        category="dart_disclosures",
        adapter_id="opendart:list.json",
        source_type="official_api",
        requires_auth=True,
        required_env_keys=("OPENDART_API_KEY",),
        supports_eod=True,
        supports_historical=True,
        expected_latency="delayed",
        officialness_level="official",
        reliability_base_score=90,
        legal_access_mode="api_key_required",
        fallback_rank=10,
        user_visible_warning_ko="OpenDART 인증키가 필요합니다.",
    ),
    "bok_ecos_macro": DataSourceDefinition(
        source_id="bok_ecos_macro",
        display_name_ko="BOK ECOS 매크로",
        category="macro",
        adapter_id="ecos:KeyStatisticList",
        source_type="official_api",
        requires_auth=True,
        required_env_keys=("BOK_ECOS_API_KEY",),
        supports_eod=True,
        supports_historical=True,
        expected_latency="daily",
        officialness_level="official",
        reliability_base_score=90,
        legal_access_mode="api_key_required",
        fallback_rank=10,
    ),
    "kosis_macro": DataSourceDefinition(
        source_id="kosis_macro",
        display_name_ko="KOSIS 매크로",
        category="macro",
        adapter_id="kosis:macro",
        source_type="official_api",
        requires_auth=True,
        required_env_keys=("KOSIS_API_KEY",),
        supports_eod=True,
        supports_historical=True,
        expected_latency="daily",
        officialness_level="official",
        reliability_base_score=85,
        legal_access_mode="api_key_required",
        fallback_rank=20,
        adapter_available=False,
    ),
    "naver_finance_fx_rates": DataSourceDefinition(
        source_id="naver_finance_fx_rates",
        display_name_ko="Naver Finance 환율·금리 스냅샷",
        category="fx_rates",
        adapter_id="market_snapshot:fx_rates",
        source_type="public_web",
        requires_auth=False,
        supports_eod=True,
        expected_latency="delayed",
        officialness_level="public_web",
        reliability_base_score=72,
        legal_access_mode="no_key_required",
        fallback_rank=30,
        user_visible_warning_ko="공개 스냅샷입니다. 공식 실시간 데이터가 아닙니다.",
    ),
    "planned_krx_valuation": DataSourceDefinition(
        source_id="planned_krx_valuation",
        display_name_ko="KRX/OpenDART 밸류에이션 어댑터",
        category="valuation",
        adapter_id="planned:krx_valuation",
        source_type="planned",
        requires_auth=False,
        reliability_base_score=0,
        legal_access_mode="planned_not_available",
        fallback_rank=99,
        user_visible_warning_ko="아직 구현되지 않은 어댑터입니다.",
        adapter_available=False,
    ),
    "planned_krx_investor_flow": DataSourceDefinition(
        source_id="planned_krx_investor_flow",
        display_name_ko="KRX 투자자 수급 어댑터",
        category="investor_flow",
        adapter_id="planned:krx_investor_flow",
        source_type="planned",
        requires_auth=False,
        reliability_base_score=0,
        legal_access_mode="planned_not_available",
        fallback_rank=99,
        user_visible_warning_ko="아직 구현되지 않은 어댑터입니다.",
        adapter_available=False,
    ),
    "planned_krx_short_selling": DataSourceDefinition(
        source_id="planned_krx_short_selling",
        display_name_ko="KRX 공매도 어댑터",
        category="short_selling",
        adapter_id="planned:krx_short_selling",
        source_type="planned",
        requires_auth=False,
        reliability_base_score=0,
        legal_access_mode="planned_not_available",
        fallback_rank=99,
        user_visible_warning_ko="아직 구현되지 않은 어댑터입니다.",
        adapter_available=False,
    ),
}


def canonical_key_present(env_status: dict[str, bool] | None, key: str) -> bool:
    env = env_status or {}
    for candidate in KEY_ALIASES.get(key, (key,)):
        if bool(env.get(candidate)):
            return True
    return False


def missing_required_keys(source: DataSourceDefinition, env_status: dict[str, bool] | None) -> tuple[str, ...]:
    return tuple(key for key in source.required_env_keys if not canonical_key_present(env_status, key))


def get_source(source_id: str) -> DataSourceDefinition:
    return SOURCE_REGISTRY[source_id]


def sources_for_category(category: str) -> tuple[DataSourceDefinition, ...]:
    return tuple(
        sorted(
            (source for source in SOURCE_REGISTRY.values() if source.category == category),
            key=lambda item: item.fallback_rank,
        )
    )


def accuracy_for_source(source: DataSourceDefinition) -> str:
    if source.source_type == "broker_api" and source.supports_realtime:
        return "broker_realtime"
    if source.source_type == "official_api" and source.supports_realtime:
        return "official_realtime"
    if source.source_type in {"official_api", "public_api"}:
        return "official_eod"
    if source.source_type == "public_web":
        return "public_snapshot"
    if source.source_type == "manual_input":
        return "manual"
    if source.source_type == "cache":
        return "cached"
    if source.source_type == "mock":
        return "mock"
    if source.source_type == "planned":
        return "planned"
    return "unavailable"


def exactness_for_source(source: DataSourceDefinition) -> str:
    if source.source_type == "broker_api":
        return "exact_broker"
    if source.source_type in {"official_api", "public_api"}:
        return "official_eod"
    if source.source_type == "public_web":
        return "public_snapshot"
    if source.source_type == "manual_input":
        return "manual"
    if source.source_type == "cache":
        return "cached"
    if source.source_type == "mock":
        return "mock"
    return "unavailable"


def resolve_best_data_source(
    category: str,
    *,
    preferred_source: str | None = None,
    allow_keyless_public_sources: bool = True,
    allow_cache: bool = True,
    allow_mock: bool = False,
    allow_manual: bool = True,
    require_official: bool = False,
    require_realtime: bool = False,
    env_status: dict[str, bool] | None = None,
    adapter_available: dict[str, bool] | None = None,
    cache_available: bool = False,
    manual_data_available: bool = False,
    mock_data_available: bool = False,
    source_registry: dict[str, DataSourceDefinition] | None = None,
) -> SourceResolution:
    registry = source_registry or SOURCE_REGISTRY
    candidates = [source for source in registry.values() if source.category == category]
    if preferred_source:
        candidates.sort(key=lambda item: (0 if item.source_id == preferred_source else 1, item.fallback_rank))
    else:
        candidates.sort(key=lambda item: item.fallback_rank)

    blocked: list[tuple[str, str]] = []
    fallback_path: list[str] = []
    missing_keys_seen: list[str] = []

    for source in candidates:
        fallback_path.append(source.source_id)
        source_adapter_available = (adapter_available or {}).get(source.adapter_id, source.adapter_available)
        if source.source_type == "planned":
            blocked.append((source.source_id, "adapter_not_implemented"))
            continue
        if not source_adapter_available and source.source_type not in {"manual_input", "mock", "cache"}:
            blocked.append((source.source_id, "adapter_not_implemented"))
            continue
        if require_official and source.officialness_level not in {"official", "broker"}:
            blocked.append((source.source_id, "not_official"))
            continue
        if require_realtime and not source.supports_realtime:
            blocked.append((source.source_id, "not_realtime"))
            continue
        missing = missing_required_keys(source, env_status)
        if missing:
            missing_keys_seen.extend(missing)
            blocked.append((source.source_id, "missing_key:" + ",".join(missing)))
            continue
        if source.source_type in {"public_web", "public_api"} and not source.requires_auth and not allow_keyless_public_sources:
            blocked.append((source.source_id, "keyless_public_disabled"))
            continue
        if source.source_type == "manual_input" and (not allow_manual or not manual_data_available):
            blocked.append((source.source_id, "manual_data_missing"))
            continue
        if source.source_type == "mock" and (not allow_mock or not mock_data_available):
            blocked.append((source.source_id, "mock_disabled"))
            continue
        if source.source_type == "cache" and (not allow_cache or not cache_available):
            blocked.append((source.source_id, "cache_missing"))
            continue

        accuracy = accuracy_for_source(source)
        exactness = exactness_for_source(source)
        status = {
            "manual_input": "manual",
            "mock": "mock",
            "cache": "cache_only",
        }.get(source.source_type, "connected")
        can_exact = exactness in {"exact_official", "exact_broker", "official_eod"}
        can_best_effort = accuracy in {"public_snapshot", "public_delayed", "manual", "cached"}
        return SourceResolution(
            category=category,
            selected_source=source,
            status=status,
            accuracy_grade=accuracy,
            exactness_level=exactness,
            confidence_score=source.reliability_base_score,
            selected_reason_ko="사용 가능한 최상위 합법 데이터 소스를 선택했습니다.",
            blocked_sources=tuple(blocked),
            missing_keys=tuple(sorted(set(missing_keys_seen))),
            fallback_path=tuple(fallback_path),
            can_compute_exact_value=can_exact,
            can_compute_best_effort_value=can_exact or can_best_effort,
        )

    planned = next((source for source in candidates if source.source_type == "planned"), None)
    if planned is not None:
        return SourceResolution(
            category=category,
            selected_source=planned,
            status="adapter_missing",
            accuracy_grade="planned",
            exactness_level="unavailable",
            confidence_score=0,
            selected_reason_ko="데이터 어댑터가 아직 연결되지 않았습니다.",
            blocked_sources=tuple(blocked),
            missing_keys=tuple(sorted(set(missing_keys_seen))),
            fallback_path=tuple(fallback_path),
            can_compute_exact_value=False,
            can_compute_best_effort_value=False,
        )

    status = "missing_key" if missing_keys_seen else "unavailable"
    return SourceResolution(
        category=category,
        selected_source=None,
        status=status,
        accuracy_grade="unavailable",
        exactness_level="unavailable",
        confidence_score=0,
        selected_reason_ko="사용 가능한 합법 데이터 소스가 없습니다.",
        blocked_sources=tuple(blocked),
        missing_keys=tuple(sorted(set(missing_keys_seen))),
        fallback_path=tuple(fallback_path),
        can_compute_exact_value=False,
        can_compute_best_effort_value=False,
    )
