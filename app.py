from __future__ import annotations

from dataclasses import dataclass
import hashlib
import html
import io
import json
from datetime import datetime, timedelta
import math
import os
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin

import numpy as np
import pandas as pd
import requests
import urllib3

try:
    import streamlit as st
except Exception as exc:  # pragma: no cover - streamlit runtime only
    raise RuntimeError(
        "Streamlit is required to run this app. Install it with `pip install streamlit`."
    ) from exc

try:
    import FinanceDataReader as fdr
except Exception as exc:  # pragma: no cover - finance runtime only
    fdr = None
    FDR_IMPORT_ERROR = exc
else:
    FDR_IMPORT_ERROR = None

import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib import dates as mdates
from bs4 import BeautifulSoup

from src.discovery import build_universe, scan_universe
from src.execution import build_execution_plan, should_block_for_execution
from src.exits import build_exit_plan
from src.monitoring.signal_ledger import (
    compute_forward_outcome,
    create_signal_record,
    get_kill_switch_state,
    init_db,
    list_recent_signals,
    SignalRecord,
    store_outcome,
    store_signal,
)


NAVER_HEADERS = {"User-Agent": "Mozilla/5.0"}
DART_RECENT_URL = "https://dart.fss.or.kr/dsac001/mainAll.do"
DART_LIST_API_URL = "https://opendart.fss.or.kr/api/list.json"


HTTP_VERIFY_SSL = os.getenv("BNK_VERIFY_SSL", "false").strip().lower() in {"1", "true", "yes", "on"}


def configure_http_ssl() -> None:
    if HTTP_VERIFY_SSL:
        return
    if getattr(requests.sessions.Session.request, "_bnk_ssl_configured", False):
        return

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    original_request = requests.sessions.Session.request

    def request_with_default_ssl(self: requests.Session, method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("verify", False)
        return original_request(self, method, url, **kwargs)

    request_with_default_ssl._bnk_ssl_configured = True
    requests.sessions.Session.request = request_with_default_ssl


configure_http_ssl()


def load_env_file(env_path: str = ".env") -> None:
    path = os.path.join(os.path.dirname(__file__), env_path)
    if not os.path.exists(path):
        return

    try:
        with open(path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


load_env_file()
DART_API_KEY = os.getenv("DART_API_KEY", "YOUR_API_KEY").strip()
DART_API_TOKEN = hashlib.sha256(DART_API_KEY.encode("utf-8")).hexdigest()[:12] if DART_API_KEY else "no-key"
ECOS_API_KEY = os.getenv("ECOS_API_KEY", "YOUR_ECOS_KEY").strip()
ECOS_API_URL = "https://ecos.bok.or.kr/api/KeyStatisticList"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_BRIEFING_MODEL = "gpt-5.5"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SIGNAL_LEDGER_DB = DATA_DIR / "signal_ledger.sqlite3"
BRIEFING_DIR = BASE_DIR / "briefings"
BRIEFING_SYSTEM_FILES = [
    BASE_DIR / "system_prompt_briefing.md",
    BASE_DIR / "kb_market_indicators.md",
    BASE_DIR / "kb_sector_mapping.md",
    BASE_DIR / "kb_signal_rules.md",
]
OUTPUT_SCHEMA_FILE = BASE_DIR / "output_schema.md"
BRIEFING_DISCLAIMER = "본 브리핑은 투자 참고용이며 투자 판단과 책임은 투자자 본인에게 있습니다."
BRIEFING_BANNED_PHRASES = ["매수 추천", "목표가", "보장"]


def configure_korean_font() -> None:
    preferred_fonts = [
        "Malgun Gothic",
        "AppleGothic",
        "NanumGothic",
        "Noto Sans CJK KR",
        "Noto Sans KR",
        "Arial Unicode MS",
    ]
    available_fonts = {font.name for font in fm.fontManager.ttflist}
    for font_name in preferred_fonts:
        if font_name in available_fonts:
            plt.rcParams["font.family"] = font_name
            break
    plt.rcParams["axes.unicode_minus"] = False


configure_korean_font()


st.set_page_config(
    page_title="BNK 금융 대시보드",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


CUSTOM_CSS = """
<style>
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(255, 77, 77, 0.08), transparent 28%),
            radial-gradient(circle at top right, rgba(65, 105, 225, 0.08), transparent 24%),
            linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
        font-family: "Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans KR", "NanumGothic", sans-serif;
    }
    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2rem;
    }
    .hero-title {
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin-bottom: 0.2rem;
        color: #111827;
    }
    .hero-subtitle {
        color: #475569;
        margin-bottom: 1rem;
        font-size: 0.96rem;
    }
    .metric-card {
        border-radius: 18px;
        padding: 16px 16px 14px 16px;
        background: rgba(255, 255, 255, 0.84);
        border: 1px solid rgba(148, 163, 184, 0.28);
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
        min-height: 120px;
    }
    .metric-label {
        font-size: 0.84rem;
        color: #334155;
        font-weight: 700;
        margin-bottom: 6px;
    }
    .metric-name {
        font-size: 1.04rem;
        color: #0f172a;
        font-weight: 800;
        line-height: 1.25;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 1.55rem;
        font-weight: 900;
        color: #0f172a;
        line-height: 1.1;
    }
    .metric-change-pos {
        color: #dc2626;
        font-weight: 700;
        margin-top: 8px;
    }
    .metric-change-neg {
        color: #2563eb;
        font-weight: 700;
        margin-top: 8px;
    }
    .metric-change-flat {
        color: #64748b;
        font-weight: 700;
        margin-top: 8px;
    }
    .section-title {
        margin-top: 0.8rem;
        margin-bottom: 0.4rem;
        color: #0f172a;
        font-size: 1.15rem;
        font-weight: 800;
    }
    .small-note {
        color: #64748b;
        font-size: 0.85rem;
    }
    .signal-box {
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.9);
        border: 1px solid rgba(148, 163, 184, 0.3);
        padding: 14px 16px;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
    }
    .signal-buy { color: #dc2626; font-weight: 900; }
    .signal-neutral { color: #64748b; font-weight: 900; }
    .signal-sell { color: #2563eb; font-weight: 900; }
    .insight-grid {
        display: grid;
        grid-template-columns: 1.05fr 1.45fr 1.05fr;
        gap: 12px;
        margin: 0.8rem 0 1rem 0;
    }
    .insight-panel {
        border-radius: 8px;
        padding: 14px 14px 12px 14px;
        background: rgba(255, 255, 255, 0.94);
        border: 1px solid rgba(100, 116, 139, 0.24);
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
        min-height: 258px;
    }
    .insight-head {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 10px;
        margin-bottom: 10px;
    }
    .insight-title {
        color: #0f172a;
        font-size: 0.98rem;
        font-weight: 900;
        line-height: 1.2;
    }
    .insight-kicker {
        color: #64748b;
        font-size: 0.76rem;
        font-weight: 800;
        text-transform: uppercase;
    }
    .insight-badge {
        border-radius: 999px;
        padding: 4px 9px;
        color: white;
        font-size: 0.76rem;
        font-weight: 900;
        white-space: nowrap;
    }
    .pressure-score {
        display: flex;
        align-items: baseline;
        gap: 7px;
        margin-bottom: 9px;
    }
    .pressure-score strong {
        color: #0f172a;
        font-size: 2.25rem;
        font-weight: 950;
        line-height: 1;
    }
    .pressure-score span {
        color: #64748b;
        font-size: 0.85rem;
        font-weight: 800;
    }
    .meter-track {
        height: 9px;
        border-radius: 999px;
        background: linear-gradient(90deg, #2563eb 0%, #64748b 48%, #dc2626 100%);
        position: relative;
        margin: 6px 0 12px 0;
    }
    .meter-pin {
        position: absolute;
        top: -4px;
        width: 3px;
        height: 17px;
        border-radius: 999px;
        background: #111827;
        box-shadow: 0 0 0 2px #fff;
    }
    .signal-row,
    .rank-row,
    .risk-row {
        display: grid;
        align-items: center;
        gap: 8px;
        padding: 7px 0;
        border-top: 1px solid rgba(148, 163, 184, 0.18);
    }
    .signal-row {
        grid-template-columns: 70px 1fr 54px;
    }
    .rank-row {
        grid-template-columns: 30px minmax(132px, 1fr) 92px 64px 76px 64px;
    }
    .risk-row {
        grid-template-columns: minmax(86px, 1fr) auto;
    }
    .row-label {
        color: #334155;
        font-size: 0.82rem;
        font-weight: 850;
        white-space: nowrap;
    }
    .row-sub {
        color: #64748b;
        font-size: 0.74rem;
        font-weight: 700;
    }
    .row-value {
        color: #0f172a;
        font-size: 0.8rem;
        font-weight: 900;
        text-align: right;
        white-space: nowrap;
    }
    .mini-track {
        height: 7px;
        border-radius: 999px;
        background: #e2e8f0;
        overflow: hidden;
    }
    .mini-fill {
        height: 100%;
        border-radius: 999px;
    }
    .rank-header {
        color: #64748b;
        font-size: 0.75rem;
        font-weight: 900;
        text-align: right;
        padding: 2px 0 5px 0;
    }
    .rank-header:first-child,
    .rank-header:nth-child(2) {
        text-align: left;
    }
    .rank-name {
        min-width: 0;
    }
    .rank-name strong {
        display: block;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        color: #0f172a;
        font-size: 0.86rem;
        font-weight: 900;
    }
    .rank-name span {
        color: #64748b;
        font-size: 0.74rem;
        font-weight: 800;
    }
    .thesis {
        margin-top: 10px;
        padding: 10px;
        border-radius: 8px;
        background: #f8fafc;
        border: 1px solid rgba(148, 163, 184, 0.22);
        color: #334155;
        font-size: 0.84rem;
        font-weight: 750;
        line-height: 1.45;
    }
    .quality-banner {
        border-radius: 8px;
        padding: 12px 14px;
        background: #ffffff;
        border: 1px solid rgba(100, 116, 139, 0.24);
        margin: 0.6rem 0 1rem 0;
        box-shadow: 0 8px 22px rgba(15, 23, 42, 0.05);
    }
    .quality-top {
        display: flex;
        justify-content: space-between;
        gap: 14px;
        align-items: center;
        margin-bottom: 8px;
    }
    .quality-score {
        font-size: 1.45rem;
        font-weight: 950;
        color: #0f172a;
    }
    .quality-status {
        border-radius: 999px;
        padding: 4px 10px;
        color: #fff;
        font-size: 0.78rem;
        font-weight: 900;
        white-space: nowrap;
    }
    .quality-warnings {
        color: #475569;
        font-size: 0.82rem;
        font-weight: 750;
        line-height: 1.45;
    }
    .action-console {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
        margin: 0.6rem 0 1rem 0;
    }
    .action-panel {
        border-radius: 8px;
        padding: 12px 14px;
        background: rgba(255, 255, 255, 0.96);
        border: 1px solid rgba(100, 116, 139, 0.22);
    }
    .action-panel strong {
        display: block;
        color: #0f172a;
        font-size: 0.95rem;
        margin-bottom: 6px;
    }
    .action-panel div {
        color: #334155;
        font-size: 0.84rem;
        font-weight: 760;
        line-height: 1.5;
        margin: 3px 0;
    }
    .command-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.82rem;
    }
    .command-table th,
    .command-table td {
        padding: 7px 8px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.18);
        text-align: right;
        white-space: nowrap;
    }
    .command-table th:first-child,
    .command-table td:first-child {
        text-align: left;
    }
    .command-table th {
        color: #64748b;
        font-weight: 900;
    }
    .command-table td {
        color: #0f172a;
        font-weight: 760;
    }
    @media (max-width: 1100px) {
        .insight-grid {
            grid-template-columns: 1fr;
        }
        .action-console {
            grid-template-columns: 1fr;
        }
    }
    .meta-pill {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        background: #e2e8f0;
        color: #334155;
        font-size: 0.78rem;
        margin-right: 6px;
        margin-bottom: 6px;
    }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


DEFAULT_CODES = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "009150",  # 삼성전기
    "298040",  # 효성중공업
    "010120",  # LS ELECTRIC
    "267260",  # HD현대일렉트릭
    "083450",  # GST
    "089030",  # 테크윙
    "042700",  # 한미반도체
    "089860",  # 롯데렌탈
]

STOCK_UNIVERSE_NAME_HINTS = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "009150": "삼성전기",
    "298040": "효성중공업",
    "010120": "LS ELECTRIC",
    "267260": "HD현대일렉트릭",
    "083450": "GST",
    "089030": "테크윙",
    "042700": "한미반도체",
    "089860": "롯데렌탈",
    "034020": "두산에너빌리티",
}

INDEX_SYMBOLS = {
    "KOSPI": ["KS11"],
    "KOSDAQ": ["KQ11"],
}

FX_SYMBOLS = {
    "USD/KRW": ["USD/KRW", "USDKRW", "USDKRW=X", "FRED:DEXKOUS"],
}

YIELD_SYMBOLS = {
    "US 10Y": ["FRED:DGS10", "DGS10", "US10Y"],
    "KR 3Y": ["KR3Y", "FRED:IR3TIB03Y", "FRED:IR3TIB03", "KOR3Y"],
}


RISK_DEFAULTS = {
    "risk_per_trade_pct": 0.0025,
    "max_position_pct": 0.10,
    "max_sector_pct": 0.30,
    "min_raw_rr": 2.0,
    "min_quality_adjusted_rr": 1.5,
    "extreme_risk_off_min_rr": 3.0,
    "trading_cost_pct": 0.35,
    "slippage_pct": 0.15,
}


@dataclass
class Snapshot:
    key: str
    display_name: str
    last_close: float | None
    prev_close: float | None
    change: float | None
    change_pct: float | None
    asof: pd.Timestamp | None
    raw: pd.DataFrame | None = None
    source: str = "unknown"
    unit: str = "unknown"
    frequency: str = "unknown"
    quality_score: int = 0
    warnings: list[str] | None = None
    errors: list[str] | None = None
    is_fallback: bool = True


@dataclass
class MarketRegimeOutput:
    score: int
    regime: str
    recommended_cash_range: tuple[int, int]
    max_new_exposure: float
    allowed_actions: list[str]
    prohibited_actions: list[str]
    primary_drivers: list[str]
    confidence: int
    components: dict[str, int]


@dataclass
class ActionDecision:
    action: str
    score: int
    expected_edge: float | None
    quality_adjusted_rr: float | None
    max_position_pct: float
    reasons: list[str]
    blockers: list[str]


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        return None


def last_trading_ts(df: pd.DataFrame) -> pd.Timestamp | None:
    if df is None or df.empty:
        return None
    idx = df.index[-1]
    if isinstance(idx, pd.Timestamp):
        return idx
    return pd.Timestamp(idx)


def parse_code_input(text: str) -> tuple[list[str], list[str]]:
    raw_tokens = [token.strip() for token in re.split(r"[,\n\r\t ]+", text or "") if token.strip()]
    cleaned: list[str] = []
    invalid: list[str] = []
    for token in raw_tokens:
        token = re.sub(r"\D", "", token)
        if not token:
            continue
        if len(token) != 6:
            invalid.append(token)
            continue
        if token not in cleaned:
            cleaned.append(token)
    return cleaned, invalid


def format_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:+.2f}%"


def format_num(value: float | None, decimals: int = 2) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:,.{decimals}f}"


def format_price(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    if abs(value) >= 100:
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def format_snapshot_value(snap: Snapshot) -> str:
    value = snap.last_close
    if value is None or pd.isna(value):
        return "N/A"
    if snap.key in {"KOSPI", "KOSDAQ", "USD/KRW"} or snap.unit == "index":
        return f"{value:,.2f}"
    if snap.unit == "%":
        return f"{value:,.2f}%"
    return format_price(value)


SOURCE_LABELS = {
    "Naver Finance": "네이버 금융",
    "Naver": "네이버 금융",
    "FinanceDataReader": "FDR 보조 데이터",
    "Alternative.me": "Alternative.me",
    "BOK ECOS": "한국은행 ECOS",
    "FRED": "FRED",
}


def snapshot_source_label(snap: Snapshot) -> str:
    source = SOURCE_LABELS.get(snap.source, snap.source or "출처 확인")
    score = snap.quality_score if snap.quality_score else 0
    return f"{source} · 품질 {score}"


ACTION_LABELS_KO = {
    "Strong Buy": "강한 매수 후보",
    "Buy on Pullback": "눌림 매수",
    "Accumulate Small": "소액 분할",
    "Hold / Watch": "보유·관찰",
    "Watch Only": "관찰만",
    "Trim": "일부 축소",
    "Sell / Avoid": "회피",
}


def action_label_ko(action: str | None) -> str:
    return ACTION_LABELS_KO.get(action or "", action or "관찰만")


SEVERITY_LABELS_KO = {
    "Low": "낮음",
    "Medium": "주의",
    "High": "높음",
    "Critical": "치명",
}


def severity_label_ko(severity: str | None) -> str:
    return SEVERITY_LABELS_KO.get(str(severity or "Low"), str(severity or "낮음"))


REGIME_LABELS_KO = {
    "Extreme Risk-Off": "극단 방어",
    "Risk-Off": "방어",
    "Neutral": "중립",
    "Risk-On": "공격 가능",
    "Euphoria": "과열",
}


def regime_label_ko(regime: str | None) -> str:
    return REGIME_LABELS_KO.get(str(regime or "Neutral"), str(regime or "중립"))


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def change_class(change: float | None) -> str:
    if change is None or pd.isna(change) or abs(change) < 1e-12:
        return "flat"
    return "pos" if change > 0 else "neg"


def color_for_change(change: float | None) -> str:
    if change is None or pd.isna(change) or abs(change) < 1e-12:
        return "#64748b"
    return "#dc2626" if change > 0 else "#2563eb"


def parse_float_text(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = text.replace(",", "").replace(" ", "").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    try:
        return float(match.group(0))
    except Exception:
        return None


def quality_level(score: int) -> tuple[str, str]:
    if score >= 85:
        return "사용 가능", "#16a34a"
    if score >= 70:
        return "일부 경고", "#f97316"
    if score >= 50:
        return "주의", "#eab308"
    return "판단 제한", "#2563eb"


def assess_data_quality(
    *,
    source: str,
    unit: str,
    frequency: str,
    updated_at: pd.Timestamp | None,
    last_close: float | None,
    prev_close: float | None,
    change: float | None,
    change_pct: float | None,
    is_fallback: bool,
) -> tuple[int, list[str], list[str]]:
    score = 100
    warnings: list[str] = []
    errors: list[str] = []

    if not source or source == "unknown":
        score -= 40
        errors.append("source 누락")
    if updated_at is None:
        score -= 25
        errors.append("updated_at 누락")
    else:
        age_hours = max((pd.Timestamp.now() - pd.Timestamp(updated_at)).total_seconds() / 3600, 0)
        if frequency in {"near_realtime", "intraday"} and age_hours > 6:
            score -= 30
            warnings.append("장중 데이터 시점 지연")
        elif frequency in {"daily", "historical"} and age_hours > 96:
            score -= 20
            warnings.append("일별 데이터 stale 가능성")
    if not unit or unit == "unknown":
        score -= 20
        warnings.append("unit 불명확")
    if is_fallback:
        score -= 12
        warnings.append("보조 데이터 소스 사용")
    if last_close is None:
        score -= 35
        errors.append("가격/수치 결측")
    elif safe_float(last_close) is not None and float(last_close) <= 0:
        score -= 45
        errors.append("0 이하 값")
    if prev_close is None and change is not None:
        score -= 10
        warnings.append("이전 값 결측")
    if last_close not in (None, 0) and prev_close not in (None, 0) and change is not None and change_pct is not None:
        calc_pct = (float(change) / float(prev_close)) * 100
        if abs(calc_pct - float(change_pct)) > 0.2:
            score -= 15
            warnings.append("전일 대비 재검산 차이")

    return int(max(0, min(100, score))), warnings, errors


def apply_snapshot_quality(snap: Snapshot) -> Snapshot:
    score, warnings, errors = assess_data_quality(
        source=snap.source,
        unit=snap.unit,
        frequency=snap.frequency,
        updated_at=snap.asof,
        last_close=snap.last_close,
        prev_close=snap.prev_close,
        change=snap.change,
        change_pct=snap.change_pct,
        is_fallback=snap.is_fallback,
    )
    snap.quality_score = score
    snap.warnings = warnings
    snap.errors = errors
    return snap


def make_snapshot(
    key: str,
    display_name: str,
    last_close: float | None,
    prev_close: float | None,
    change: float | None,
    change_pct: float | None,
    raw: pd.DataFrame | None = None,
    source: str = "unknown",
    unit: str = "unknown",
    frequency: str = "unknown",
    is_fallback: bool = True,
) -> Snapshot:
    return apply_snapshot_quality(Snapshot(
        key=key,
        display_name=display_name,
        last_close=last_close,
        prev_close=prev_close,
        change=change,
        change_pct=change_pct,
        asof=pd.Timestamp.now(),
        raw=raw,
        source=source,
        unit=unit,
        frequency=frequency,
        is_fallback=is_fallback,
    ))


def fetch_naver_index_snapshot(code: str, display_name: str) -> Snapshot | None:
    try:
        url = f"https://finance.naver.com/sise/sise_index.naver?code={code}"
        html = requests.get(url, headers=NAVER_HEADERS, timeout=10).text
        soup = BeautifulSoup(html, "html.parser")
        value_el = soup.select_one("#now_value")
        if value_el is None:
            return None
        last_close = parse_float_text(value_el.get_text(strip=True))
        change_wrap = soup.select_one("#quotient")
        change_abs_el = soup.select_one("#change_value_and_rate > span")
        change_text = soup.select_one("#change_value_and_rate")
        change_abs = parse_float_text(change_abs_el.get_text(strip=True) if change_abs_el else None)
        change_pct = None
        if change_text is not None:
            pct_match = re.search(r"([+-]?\d+(?:\.\d+)?)%", change_text.get_text(" ", strip=True))
            if pct_match:
                change_pct = float(pct_match.group(1))
        if change_wrap is not None and change_abs is not None:
            classes = set(change_wrap.get("class", []))
            if "dn" in classes:
                change_abs = -abs(change_abs)
            elif "up" in classes:
                change_abs = abs(change_abs)
        prev_close = None
        if last_close is not None and change_abs is not None:
            prev_close = last_close - change_abs
        if change_pct is None and last_close is not None and prev_close not in (None, 0):
            change_pct = (change_abs / prev_close) * 100 if change_abs is not None else None
        return make_snapshot(
            code,
            display_name,
            last_close,
            prev_close,
            change_abs,
            change_pct,
            source="Naver Finance",
            unit="index",
            frequency="near_realtime",
            is_fallback=True,
        )
    except Exception:
        return None


def fetch_naver_fx_snapshot(display_name: str) -> Snapshot | None:
    try:
        url = "https://finance.naver.com/marketindex/exchangeDetail.naver?marketindexCd=FX_USDKRW"
        html = requests.get(url, headers=NAVER_HEADERS, timeout=10).text
        soup = BeautifulSoup(html, "html.parser")
        today_el = soup.select_one("p.no_today")
        if today_el is None:
            return None
        last_close = parse_float_text(today_el.get_text("", strip=True))
        exday_el = soup.select_one("p.no_exday")
        change_abs = None
        change_pct = None
        if exday_el is not None:
            change_abs_el = exday_el.select_one("em")
            if change_abs_el is not None:
                change_abs = parse_float_text(change_abs_el.get_text("", strip=True))
                classes = set(change_abs_el.get("class", []))
                ico = change_abs_el.select_one(".ico")
                if "down" in classes or (ico is not None and "down" in set(ico.get("class", []))):
                    change_abs = -abs(change_abs) if change_abs is not None else None
                elif "up" in classes or (ico is not None and "up" in set(ico.get("class", []))):
                    change_abs = abs(change_abs) if change_abs is not None else None
            text = exday_el.get_text("", strip=True)
            pct_match = re.search(r"([+-]?\d+(?:\.\d+)?)%", text)
            if pct_match:
                change_pct = float(pct_match.group(1))
        prev_close = None
        if last_close is not None and change_abs is not None:
            prev_close = last_close - change_abs
        if change_pct is None and last_close is not None and prev_close not in (None, 0) and change_abs is not None:
            change_pct = (change_abs / prev_close) * 100
        return make_snapshot(
            "USD/KRW",
            display_name,
            last_close,
            prev_close,
            change_abs,
            change_pct,
            source="Naver Finance",
            unit="KRW",
            frequency="near_realtime",
            is_fallback=True,
        )
    except Exception:
        return None


def fetch_naver_yield_snapshot(marketindex_cd: str, key: str, display_name: str) -> Snapshot | None:
    try:
        url = f"https://finance.naver.com/marketindex/interestDetail.naver?marketindexCd={marketindex_cd}"
        html = requests.get(url, headers=NAVER_HEADERS, timeout=10).text
        soup = BeautifulSoup(html, "html.parser")
        today_el = soup.select_one("p.no_today")
        if today_el is None:
            return None
        last_close = parse_float_text(today_el.get_text("", strip=True))
        exday_el = soup.select_one("p.no_exday")
        change_abs = None
        change_pct = None
        if exday_el is not None:
            change_abs_el = exday_el.select_one("em")
            if change_abs_el is not None:
                change_abs = parse_float_text(change_abs_el.get_text("", strip=True))
                classes = set(change_abs_el.get("class", []))
                ico = change_abs_el.select_one(".ico")
                if "down" in classes or (ico is not None and "down" in set(ico.get("class", []))):
                    change_abs = -abs(change_abs) if change_abs is not None else None
                elif "up" in classes or (ico is not None and "up" in set(ico.get("class", []))):
                    change_abs = abs(change_abs) if change_abs is not None else None
            text = exday_el.get_text("", strip=True)
            pct_match = re.search(r"([+-]?\d+(?:\.\d+)?)%", text)
            if pct_match:
                change_pct = float(pct_match.group(1))
        prev_close = None
        if last_close is not None and change_abs is not None:
            prev_close = last_close - change_abs
        if change_pct is None and last_close is not None and prev_close not in (None, 0) and change_abs is not None:
            change_pct = (change_abs / prev_close) * 100
        return make_snapshot(
            key,
            display_name,
            last_close,
            prev_close,
            change_abs,
            change_pct,
            source="Naver Finance",
            unit="%",
            frequency="near_realtime",
            is_fallback=True,
        )
    except Exception:
        return None


@st.cache_data(ttl=20, show_spinner=False)
def load_live_market_snapshot(refresh_token: int) -> dict[str, Snapshot]:
    data: dict[str, Snapshot] = {}

    kospi = fetch_naver_index_snapshot("KOSPI", "코스피")
    if kospi is not None:
        data["KOSPI"] = kospi

    kosdaq = fetch_naver_index_snapshot("KOSDAQ", "코스닥")
    if kosdaq is not None:
        data["KOSDAQ"] = kosdaq

    fx = fetch_naver_fx_snapshot("USD/KRW")
    if fx is not None:
        data["USD/KRW"] = fx

    kr3y = fetch_naver_yield_snapshot("IRR_GOVT03Y", "KR 3Y", "한국 국고채 3년물")
    if kr3y is None:
        kr3y = fetch_naver_yield_snapshot("IRR_CORP03Y", "KR 3Y", "한국 회사채 3년물")
    if kr3y is not None:
        data["KR 3Y"] = kr3y

    return data


def choose_candidate(candidates: Iterable[str], start: str | None = None, end: str | None = None) -> tuple[str | None, pd.DataFrame | None]:
    if fdr is None:
        return None, None
    for symbol in candidates:
        try:
            df = fdr.DataReader(symbol, start, end)
        except Exception:
            continue
        if isinstance(df, pd.Series):
            df = df.to_frame("Close")
        if isinstance(df, pd.DataFrame) and not df.empty:
            return symbol, df.sort_index()
    return None, None


@st.cache_data(ttl=300, show_spinner=False)
def load_listing_cache(refresh_token: int) -> pd.DataFrame:
    if fdr is None:
        return pd.DataFrame(columns=["Code", "Name"])
    try:
        listing = fdr.StockListing("KRX")
    except Exception:
        listing = pd.DataFrame(columns=["Code", "Name"])
    if "Code" in listing.columns:
        listing["Code"] = listing["Code"].astype(str).str.zfill(6)
    return listing


@st.cache_data(ttl=300, show_spinner=False)
def load_market_snapshot(refresh_token: int, watch_codes: tuple[str, ...] = ()) -> dict[str, Snapshot]:
    if fdr is None:
        return {}

    end = pd.Timestamp.today().normalize()
    start = end - pd.Timedelta(days=420)
    data: dict[str, Snapshot] = {}

    live_data = load_live_market_snapshot(refresh_token)

    def build_snapshot(name: str, candidates: list[str]) -> None:
        picked, df = choose_candidate(candidates, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if df is None or df.empty:
            data[name] = apply_snapshot_quality(Snapshot(name, name, None, None, None, None, None, None, source="FinanceDataReader", unit="unknown", frequency="historical", is_fallback=True))
            return
        close = df["Close"] if "Close" in df.columns else df.iloc[:, 0]
        last_close = safe_float(close.iloc[-1])
        prev_close = safe_float(close.iloc[-2]) if len(close) >= 2 else None
        change = None if last_close is None or prev_close is None else last_close - prev_close
        change_pct = None if last_close is None or prev_close in (None, 0) else (change / prev_close) * 100
        unit = "%" if "Y" in name or "10Y" in name or "3Y" in name else ("KRW" if "USD/KRW" in name else "price")
        data[name] = apply_snapshot_quality(Snapshot(name, picked or name, last_close, prev_close, change, change_pct, last_trading_ts(df), df, source="FinanceDataReader", unit=unit, frequency="historical", is_fallback=True))

    for name, candidates in INDEX_SYMBOLS.items():
        build_snapshot(name, candidates)
    for name, candidates in FX_SYMBOLS.items():
        build_snapshot(name, candidates)
    for name, candidates in YIELD_SYMBOLS.items():
        build_snapshot(name, candidates)

    for name in ("KOSPI", "KOSDAQ", "USD/KRW", "KR 3Y"):
        if name in live_data and live_data[name].last_close is not None:
            live_snap = live_data[name]
            fallback_snap = data.get(name)
            data[name] = Snapshot(
                key=name,
                display_name=live_snap.display_name,
                last_close=live_snap.last_close,
                prev_close=live_snap.prev_close if live_snap.prev_close is not None else (fallback_snap.prev_close if fallback_snap else None),
                change=live_snap.change if live_snap.change is not None else (fallback_snap.change if fallback_snap else None),
                change_pct=live_snap.change_pct if live_snap.change_pct is not None else (fallback_snap.change_pct if fallback_snap else None),
                asof=live_snap.asof,
                raw=fallback_snap.raw if fallback_snap else None,
                source=live_snap.source,
                unit=live_snap.unit,
                frequency=live_snap.frequency,
                quality_score=live_snap.quality_score,
                warnings=live_snap.warnings,
                errors=live_snap.errors,
                is_fallback=live_snap.is_fallback,
            )

    fng_snap = load_fear_greed_index(refresh_token)
    if fng_snap is not None:
        data["FNG"] = fng_snap

    # Core default list plus user-entered KRX watchlist codes.
    listing = load_listing_cache(refresh_token)
    snapshot_codes = list(dict.fromkeys([*DEFAULT_CODES, *watch_codes]))
    for code in snapshot_codes:
        row = listing.loc[listing["Code"] == code]
        display_name = row["Name"].iloc[0] if not row.empty else STOCK_UNIVERSE_NAME_HINTS.get(code, code)
        build_snapshot(code, [code])
        snap = data.get(code)
        if snap is not None:
            snap.display_name = display_name
            snap.key = code

    return data


@st.cache_data(ttl=180, show_spinner=False)
def load_recent_disclosures(refresh_token: int, api_token: str, limit: int = 150) -> pd.DataFrame:
    columns = ["time", "corp_name", "report_name", "submitter", "date", "note", "corp_code", "stock_code", "report_url"]

    def empty_frame() -> pd.DataFrame:
        return pd.DataFrame(columns=columns)

    if DART_API_KEY:
        try:
            rows: list[dict[str, Any]] = []
            end_dt = pd.Timestamp.today().normalize()
            start_dt = end_dt - pd.Timedelta(days=90)
            page_no = 1
            page_size = 100
            while len(rows) < limit and page_no <= 3:
                params = {
                    "crtfc_key": DART_API_KEY,
                    "bgn_de": start_dt.strftime("%Y%m%d"),
                    "end_de": end_dt.strftime("%Y%m%d"),
                    "last_reprt_at": "Y",
                    "sort": "date",
                    "sort_mth": "desc",
                    "page_no": page_no,
                    "page_count": min(page_size, limit - len(rows)),
                }
                response = requests.get(DART_LIST_API_URL, params=params, headers=NAVER_HEADERS, timeout=12)
                response.raise_for_status()
                payload = response.json()
                if payload.get("status") != "000":
                    break
                items = payload.get("list") or []
                if not items:
                    break
                for item in items:
                    corp_name = clean_text(item.get("corp_name", ""))
                    report_name = clean_text(item.get("report_nm", ""))
                    rcept_no = clean_text(item.get("rcept_no", ""))
                    rcept_dt = clean_text(item.get("rcept_dt", ""))
                    submitter = clean_text(item.get("flr_nm", ""))
                    note = clean_text(item.get("rm", ""))
                    corp_code = clean_text(item.get("corp_code", ""))
                    stock_code = clean_text(item.get("stock_code", ""))
                    rows.append(
                        {
                            "time": rcept_dt,
                            "corp_name": corp_name,
                            "report_name": report_name,
                            "submitter": submitter,
                            "date": rcept_dt,
                            "note": note,
                            "corp_code": corp_code,
                            "stock_code": stock_code,
                            "report_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}" if rcept_no else "",
                        }
                    )
                    if len(rows) >= limit:
                        break
                page_no += 1
            if rows:
                return pd.DataFrame(rows, columns=columns)
        except Exception:
            pass

    try:
        html = requests.get(DART_RECENT_URL, headers=NAVER_HEADERS, timeout=12).text
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if table is None:
            return empty_frame()

        rows: list[dict[str, Any]] = []
        for tr in table.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue
            time_text = clean_text(tds[0].get_text(" ", strip=True))
            corp_anchor = tds[1].find("a", href=True)
            report_anchor = tds[2].find("a", href=True)
            corp_name = clean_text(corp_anchor.get_text(" ", strip=True) if corp_anchor else tds[1].get_text(" ", strip=True))
            report_name = clean_text(report_anchor.get_text(" ", strip=True) if report_anchor else tds[2].get_text(" ", strip=True))
            submitter = clean_text(tds[3].get_text(" ", strip=True))
            report_date = clean_text(tds[4].get_text(" ", strip=True))
            note = clean_text(tds[5].get_text(" ", strip=True)) if len(tds) > 5 else ""
            corp_code = None
            if corp_anchor and corp_anchor.get("href"):
                code_match = re.search(r"openCorpInfoNew\('([^']+)'", corp_anchor["href"])
                if code_match:
                    corp_code = code_match.group(1)
            report_url = urljoin(DART_RECENT_URL, report_anchor["href"]) if report_anchor and report_anchor.get("href") else ""
            rows.append(
                {
                    "time": time_text,
                    "corp_name": corp_name,
                    "report_name": report_name,
                    "submitter": submitter,
                    "date": report_date,
                    "note": note,
                    "corp_code": corp_code,
                    "stock_code": "",
                    "report_url": report_url,
                }
            )
            if len(rows) >= limit:
                break
        return pd.DataFrame(rows, columns=columns)
    except Exception:
        return empty_frame()


@st.cache_data(ttl=300, show_spinner=False)
def load_symbol_history(symbol: str, refresh_token: int, periods: int = 220) -> pd.DataFrame:
    if fdr is None:
        return pd.DataFrame()
    end = pd.Timestamp.today().normalize()
    start = end - pd.Timedelta(days=max(periods * 2, 120))
    try:
        df = fdr.DataReader(symbol, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    except Exception:
        return pd.DataFrame()
    if isinstance(df, pd.Series):
        df = df.to_frame("Close")
    if df is None or df.empty:
        return pd.DataFrame()
    return df.sort_index()


@st.cache_data(ttl=3600, show_spinner=False)
def run_alpha_discovery_scan(refresh_token: int, max_symbols: int = 220) -> tuple[list[dict[str, Any]], list[str], int, int]:
    listing = load_listing_cache(refresh_token)
    universe, universe_warnings = build_universe(listing)
    kospi_hist = load_symbol_history("KS11", refresh_token, periods=260)
    benchmark_close = None
    if not kospi_hist.empty:
        _, _, _, close_c, _ = find_ohlcv_columns(kospi_hist)
        if close_c in kospi_hist.columns:
            benchmark_close = kospi_hist[close_c].dropna()
    scan_rows = universe[: max(1, int(max_symbols))]
    candidates, scan_warnings = scan_universe(
        scan_rows,
        lambda code: load_symbol_history(code, refresh_token, periods=260),
        benchmark_close,
        market_regime_score=50.0,
        limit=20,
    )
    return [candidate.__dict__ for candidate in candidates], universe_warnings + scan_warnings, len(universe), len(scan_rows)


def find_ohlcv_columns(df: pd.DataFrame) -> tuple[str, str, str, str, str]:
    lower_map = {c.lower(): c for c in df.columns}
    close = lower_map.get("close")
    open_ = lower_map.get("open")
    high = lower_map.get("high")
    low = lower_map.get("low")
    volume = lower_map.get("volume")

    if close is None:
        close = df.columns[0]
    if open_ is None:
        open_ = close
    if high is None:
        high = close
    if low is None:
        low = close
    if volume is None:
        volume = close if close in df.columns else df.columns[min(1, len(df.columns) - 1)]
    return open_, high, low, close, volume


def calc_returns(close: pd.Series) -> dict[str, float | None]:
    if close is None or len(close) < 2:
        return {"1d": None, "5d": None, "20d": None, "60d": None}
    close = close.dropna()
    if len(close) < 2:
        return {"1d": None, "5d": None, "20d": None, "60d": None}
    def pct(n: int) -> float | None:
        if len(close) <= n:
            return None
        base = float(close.iloc[-n - 1])
        latest = float(close.iloc[-1])
        if base == 0:
            return None
        return (latest / base - 1) * 100

    return {"1d": pct(1), "5d": pct(5), "20d": pct(20), "60d": pct(60)}


def market_regime(snapshot: dict[str, Snapshot]) -> tuple[float, list[str]]:
    notes: list[str] = []
    score = 0.0

    kospi = snapshot.get("KOSPI")
    kosdaq = snapshot.get("KOSDAQ")
    usdkrw = snapshot.get("USD/KRW")
    us10y = snapshot.get("US 10Y")
    kr3y = snapshot.get("KR 3Y")

    def slope_bonus(snap: Snapshot | None, name: str) -> float:
        if snap is None or snap.raw is None or snap.raw.empty or "Close" not in snap.raw.columns:
            return 0.0
        close = snap.raw["Close"].dropna()
        if len(close) < 60:
            return 0.0
        r20 = calc_returns(close)["20d"]
        r60 = calc_returns(close)["60d"]
        if r20 is None or r60 is None:
            return 0.0
        if r20 > 0 and r60 > 0:
            notes.append(f"{name} 추세 양호")
            return 0.9
        if r20 < 0 and r60 < 0:
            notes.append(f"{name} 추세 약세")
            return -0.9
        return 0.0

    score += slope_bonus(kospi, "코스피")
    score += slope_bonus(kosdaq, "코스닥")

    if usdkrw and usdkrw.change_pct is not None:
        if usdkrw.change_pct > 0:
            score -= 0.5
            notes.append("원화 약세 부담")
        elif usdkrw.change_pct < 0:
            score += 0.3
            notes.append("원화 강세 우호")

    if us10y and us10y.change_pct is not None:
        if us10y.change_pct > 0:
            score -= 0.35
            notes.append("미국 10년물 상승 부담")
        elif us10y.change_pct < 0:
            score += 0.2
            notes.append("미국 10년물 둔화")

    if kr3y and kr3y.change_pct is not None:
        if kr3y.change_pct > 0:
            score -= 0.2
            notes.append("국내 금리 부담")
        elif kr3y.change_pct < 0:
            score += 0.1
            notes.append("국내 금리 완화")

    return score, notes


def relative_strength(stock_close: pd.Series, benchmark_close: pd.Series) -> float | None:
    if len(stock_close) < 21 or len(benchmark_close) < 21:
        return None
    stock_close = stock_close.dropna()
    benchmark_close = benchmark_close.dropna()
    if len(stock_close) < 21 or len(benchmark_close) < 21:
        return None
    s20 = float(stock_close.iloc[-1] / stock_close.iloc[-21] - 1) * 100
    b20 = float(benchmark_close.iloc[-1] / benchmark_close.iloc[-21] - 1) * 100
    return s20 - b20


def stock_signal(
    code: str,
    history: pd.DataFrame,
    market_score: float,
    kospi_close: pd.Series | None,
) -> tuple[str, float, list[str]]:
    if history is None or history.empty:
        return "중립", 50.0, ["데이터가 부족해 중립"]
    _, _, _, close_col, volume_col = find_ohlcv_columns(history)
    close = history[close_col].dropna()
    volume = history[volume_col].dropna() if volume_col in history.columns else pd.Series(dtype=float)
    ret = calc_returns(close)

    score = 50.0
    reasons: list[str] = []

    def add_weight(value: float | None, weight: float, label: str, threshold: float = 0.0) -> None:
        nonlocal score
        if value is None:
            return
        delta = max(min(value, 25.0), -25.0) / 25.0 * weight
        score += delta
        direction = "우호" if value >= threshold else "비우호"
        reasons.append(f"{label} {direction}({value:+.2f}%)")

    add_weight(ret["5d"], 7.5, "5일 추세")
    add_weight(ret["20d"], 12.0, "20일 추세")
    add_weight(ret["60d"], 9.0, "60일 추세")

    if len(close) >= 20:
        ma5 = float(close.tail(5).mean())
        ma20 = float(close.tail(20).mean())
        last = float(close.iloc[-1])
        if last > ma5:
            score += 4.0
            reasons.append("종가가 5일선 위")
        else:
            score -= 3.0
            reasons.append("종가가 5일선 아래")
        if last > ma20:
            score += 6.0
            reasons.append("종가가 20일선 위")
        else:
            score -= 5.0
            reasons.append("종가가 20일선 아래")

    if volume is not None and len(volume) >= 20:
        vol_ratio = float(volume.iloc[-1] / volume.tail(20).mean()) if volume.tail(20).mean() not in (0, np.nan) else None
        if vol_ratio is not None:
            if vol_ratio >= 1.2:
                score += 6.0
                reasons.append(f"거래량 확인({vol_ratio:.2f}x)")
            elif vol_ratio <= 0.85:
                score -= 2.5
                reasons.append(f"거래량 둔화({vol_ratio:.2f}x)")

    if kospi_close is not None and len(close) >= 21 and len(kospi_close) >= 21:
        rs = relative_strength(close, kospi_close)
        if rs is not None:
            score += max(min(rs, 15.0), -15.0) / 15.0 * 10.0
            reasons.append(f"코스피 대비 상대강도 {rs:+.2f}%p")

    if len(close) >= 20:
        recent = close.tail(20)
        vol = float(recent.pct_change().dropna().std() * math.sqrt(252) * 100)
        if vol >= 80:
            score -= 4.0
            reasons.append(f"변동성 높음({vol:.1f}%)")
        elif vol <= 35:
            score += 2.0
            reasons.append(f"변동성 안정({vol:.1f}%)")

    score += market_score * 2.0
    if market_score > 0:
        reasons.append("시장 레짐 우호")
    elif market_score < 0:
        reasons.append("시장 레짐 부담")

    score = float(max(0.0, min(100.0, score)))
    if score >= 60:
        label = "매수"
    elif score <= 40:
        label = "매도"
    else:
        label = "중립"
    return label, score, reasons[:6]


def coach_message(market_score: float, signal: str, stock_score: float, volatility_flag: str) -> str:
    if market_score >= 1.0 and signal == "매수":
        return "추세가 살아있습니다. 추격보다 분할, 손절보다 비중 관리로 갑니다."
    if market_score <= -1.0 and signal == "매도":
        return "방어가 먼저입니다. 현금 비중을 지키고, 역추세 매수는 멈추세요."
    if volatility_flag == "high":
        return "변동성이 큽니다. 시그널이 좋아도 비중은 가볍게, 진입은 나눠서."
    if stock_score >= 50:
        return "기회는 있지만 과열은 아닙니다. 확인 후 진입, 무리한 추격 금지."
    return "오늘은 방어적입니다. 신호가 확실해질 때까지 기다리는 것도 실력입니다."


def render_card(
    title: str,
    snap: Snapshot,
    subtitle: str,
    value_color: str | None = None,
    show_change: bool = True,
) -> None:
    change = snap.change
    change_pct = snap.change_pct
    cls = change_class(change)
    color = value_color or color_for_change(change)
    change_text = "N/A"
    if show_change:
        if change is not None and change_pct is not None:
            change_text = f"{change:+.2f} ({change_pct:+.2f}%)"
        elif change_pct is not None:
            change_text = f"{change_pct:+.2f}%"
        elif change is not None:
            change_text = f"{change:+.2f}"
    source_text = snapshot_source_label(snap)

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{title}</div>
            <div class="metric-name">{subtitle}</div>
            <div class="metric-value" style="color:{color}">{format_snapshot_value(snap)}</div>
            {f'<div class="metric-change-{cls}">{change_text}</div>' if show_change else ''}
            <div class="small-note" style="margin-top:6px;">{html.escape(source_text)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def fear_greed_label(score: float | None) -> tuple[str, str]:
    if score is None:
        return "N/A", "#64748b"
    if score <= 24:
        return "극단 공포", "#dc2626"
    if score <= 44:
        return "공포", "#f97316"
    if score <= 55:
        return "중립", "#6b7280"
    if score <= 74:
        return "탐욕", "#a3e635"
    return "극단 탐욕", "#16a34a"


@st.cache_data(ttl=900, show_spinner=False)
def load_fear_greed_index(refresh_token: int) -> Snapshot | None:
    try:
        response = requests.get("https://api.alternative.me/fng/?limit=1&format=json", headers=NAVER_HEADERS, timeout=12)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") or []
        if not data:
            return None
        item = data[0]
        score = safe_float(item.get("value"))
        classification = clean_text(item.get("value_classification", ""))
        ts = safe_float(item.get("timestamp"))
        asof = pd.to_datetime(ts, unit="s") if ts is not None else pd.Timestamp.now()
        snap = Snapshot(
            key="FNG",
            display_name=classification or "Fear and Greed",
            last_close=score,
            prev_close=None,
            change=None,
            change_pct=None,
            asof=asof,
            raw=None,
            source="Alternative.me",
            unit="score",
            frequency="daily",
            is_fallback=True,
        )
        return apply_snapshot_quality(snap)
    except Exception:
        return None


@st.cache_data(ttl=900, show_spinner=False)
def load_fear_greed_history(refresh_token: int, limit: int = 8) -> dict[str, Any]:
    try:
        response = requests.get(
            f"https://api.alternative.me/fng/?limit={limit}&format=json",
            headers=NAVER_HEADERS,
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") or []
        if not data:
            return {"current": None, "weekly": None, "current_label": None, "weekly_label": None}

        def parse_item(item: dict[str, Any] | None) -> tuple[float | None, str | None]:
            if not isinstance(item, dict):
                return None, None
            score = safe_float(item.get("value"))
            label = clean_text(item.get("value_classification", "")) or None
            return score, label

        current_score, current_label = parse_item(data[0])
        weekly_item = data[min(max(limit - 1, 0), len(data) - 1)] if len(data) > 1 else data[0]
        weekly_score, weekly_label = parse_item(weekly_item)
        return {
            "current": current_score,
            "weekly": weekly_score,
            "current_label": current_label,
            "weekly_label": weekly_label,
        }
    except Exception:
        return {"current": None, "weekly": None, "current_label": None, "weekly_label": None}


def read_text_asset(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def load_briefing_prompt_bundle() -> tuple[str, str, str | None]:
    texts: list[str] = []
    missing: list[str] = []
    for path in BRIEFING_SYSTEM_FILES:
        text = read_text_asset(path)
        if not text:
            missing.append(path.name)
        else:
            texts.append(text)
    if missing:
        return "", "", f"브리핑 프롬프트 파일을 읽지 못했습니다: {', '.join(missing)}"

    schema_text = read_text_asset(OUTPUT_SCHEMA_FILE)
    if not schema_text:
        return "", "", "output_schema.md를 읽지 못했습니다."

    system_text = "\n\n---\n\n".join(texts)
    return system_text, schema_text, None


def extract_openai_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    chunks: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") in {"output_text", "text"}:
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text)
    if chunks:
        return "\n".join(chunks).strip()
    return ""


def validate_briefing_output(text: str, schema_text: str) -> tuple[bool, list[str], str]:
    errors: list[str] = []
    cleaned = text.strip()

    heading_pattern = re.compile(r"^#{2,3}\s+")
    schema_section_count = sum(1 for line in schema_text.splitlines() if heading_pattern.match(line.strip()))
    output_section_count = sum(1 for line in cleaned.splitlines() if heading_pattern.match(line.strip()))
    if output_section_count < min(5, max(schema_section_count, 5)):
        errors.append("섹션 헤더가 5개 이상 필요합니다.")

    for phrase in BRIEFING_BANNED_PHRASES:
        if phrase in cleaned:
            errors.append(f"금지 표현 포함: {phrase}")

    sentences = [line.strip() for line in re.split(r"[\n。.!?]", cleaned) if len(line.strip()) >= 18]
    duplicate_sentences = [sentence for sentence in set(sentences) if sentences.count(sentence) >= 2]
    if duplicate_sentences:
        errors.append("중복 문장 포함")
    unsupported_action_patterns = ["무조건 매수", "확실한 상승", "반드시 상승", "원금 보장"]
    for phrase in unsupported_action_patterns:
        if phrase in cleaned:
            errors.append(f"지원되지 않는 단정 표현 포함: {phrase}")
    if re.search(r"\d+(?:\.\d+)?\s*%", cleaned) and "source" not in cleaned.lower() and "출처" not in cleaned:
        errors.append("숫자/비율의 출처 표시가 부족합니다.")

    if BRIEFING_DISCLAIMER not in cleaned:
        cleaned = cleaned.rstrip() + "\n\n" + BRIEFING_DISCLAIMER

    return len(errors) == 0, errors, cleaned


def save_briefing_text(text: str, ref_date: str) -> Path:
    BRIEFING_DIR.mkdir(parents=True, exist_ok=True)
    safe_date = ref_date.replace("-", "")
    path = BRIEFING_DIR / f"briefing_{safe_date}.txt"
    path.write_text(text, encoding="utf-8")
    return path


def format_briefing_number(value: float | None, digits: int = 2, unit: str = "", signed: bool = False) -> str:
    if value is None:
        return "N/A"
    text = f"{value:+,.{digits}f}" if signed else f"{value:,.{digits}f}"
    return f"{text}{unit}".strip()


def infer_base_rate_status(snap: Snapshot | None) -> str:
    if snap is None or snap.last_close is None:
        return "동결"
    if snap.change is not None:
        if snap.change > 0:
            return "인상"
        if snap.change < 0:
            return "인하"
        return "동결"
    return "동결"


def snapshot_to_context(snap: Snapshot | None) -> dict[str, Any]:
    if snap is None:
        return {"value": None, "source": None, "updated_at": None, "unit": None, "quality_score": 0}
    scored = apply_snapshot_quality(snap)
    return {
        "value": scored.last_close,
        "change": scored.change,
        "change_pct": scored.change_pct,
        "source": scored.source,
        "updated_at": None if scored.asof is None else str(scored.asof),
        "unit": scored.unit,
        "frequency": scored.frequency,
        "quality_score": scored.quality_score,
        "warnings": scored.warnings or [],
        "errors": scored.errors or [],
    }


def build_briefing_user_prompt(
    snapshot: dict[str, Snapshot],
    valid_rows: list[dict[str, Any]],
    refresh_token: int,
    ref_date: str,
) -> tuple[str, list[str]]:
    missing: list[str] = []

    kospi = snapshot.get("KOSPI")
    kosdaq = snapshot.get("KOSDAQ")
    usdkrw = snapshot.get("USD/KRW")
    kr3y = snapshot.get("KR 3Y")

    ecos_df, ecos_error = load_ecos_key_statistics(refresh_token, ECOS_API_KEY)
    ecos_cards, _ = ecos_market_view(ecos_df) if not ecos_df.empty else ([], "")
    ecos_map = {title: snap for title, snap, _ in ecos_cards}
    base_rate_snap = ecos_map.get("기준금리")

    fg_data = load_fear_greed_history(refresh_token)
    fg_current = safe_float(fg_data.get("current"))
    fg_weekly = safe_float(fg_data.get("weekly"))
    fg_label = clean_text(str(fg_data.get("current_label") or "")) or "N/A"

    recent_disclosures = load_recent_disclosures(refresh_token, DART_API_TOKEN, limit=20)
    disclosure_titles: list[str] = []
    if not recent_disclosures.empty:
        for _, row in recent_disclosures.head(5).iterrows():
            corp_name = clean_text(str(row.get("corp_name", "")))
            report_name = clean_text(str(row.get("report_name", "")))
            title = " - ".join(part for part in [corp_name, report_name] if part)
            if title:
                disclosure_titles.append(title)

    if kospi is None or kospi.last_close is None:
        missing.append("코스피")
    if kosdaq is None or kosdaq.last_close is None:
        missing.append("코스닥")
    if usdkrw is None or usdkrw.last_close is None:
        missing.append("원달러 환율")
    if fg_current is None:
        missing.append("공포·탐욕 지수")
    if fg_weekly is None:
        missing.append("공포·탐욕 지수 전주")
    if base_rate_snap is None or base_rate_snap.last_close is None:
        missing.append("기준금리")
    if kr3y is None or kr3y.last_close is None:
        missing.append("국고채 3년")
    if recent_disclosures.empty:
        missing.append("주요 공시")
    if ecos_error:
        missing.append("ECOS 핵심 매크로")

    base_rate_status = infer_base_rate_status(base_rate_snap)
    disclosure_text = " / ".join(disclosure_titles) if disclosure_titles else "없음"
    missing_text = " / ".join(missing) if missing else "없음"
    regime_context = build_market_regime_output(snapshot)
    quality_score, quality_status, _, quality_messages = aggregate_data_quality(snapshot, valid_rows)
    try:
        kill_state = get_kill_switch_state(SIGNAL_LEDGER_DB)
    except Exception:
        kill_state = {"active": False, "reason": "ledger unavailable", "sample_size": 0, "hit_rate": None}
    structured_context = {
        "ref_date": ref_date,
        "data_quality": {
            "score": quality_score,
            "status": quality_status,
            "messages": quality_messages,
        },
        "market": {
            "kospi": snapshot_to_context(kospi),
            "kosdaq": snapshot_to_context(kosdaq),
            "usdkrw": snapshot_to_context(usdkrw),
            "kr3y": snapshot_to_context(kr3y),
            "fear_greed": {
                "value": fg_current,
                "weekly": fg_weekly,
                "classification": fg_label,
                "source": "Alternative.me",
                "unit": "score",
            },
        },
        "regime": {
            "score": regime_context.score,
            "regime": regime_context.regime,
            "cash_range": regime_context.recommended_cash_range,
            "allowed_actions": regime_context.allowed_actions,
            "prohibited_actions": regime_context.prohibited_actions,
        },
        "disclosures": disclosure_titles,
        "signal_outcome": {
            "kill_switch_active": bool(kill_state.get("active")),
            "reason": kill_state.get("reason"),
            "sample_size": kill_state.get("sample_size"),
            "hit_rate": kill_state.get("hit_rate"),
        },
        "missing": missing,
    }

    lines = [
        "[입력 데이터]",
        f"- 코스피: {format_briefing_number(safe_float(kospi.last_close) if kospi else None)} ({format_briefing_number(safe_float(kospi.change_pct) if kospi and kospi.change_pct is not None else None, 2, '%', True)})" if kospi and kospi.last_close is not None else "- 코스피: N/A (N/A)",
        f"- 코스닥: {format_briefing_number(safe_float(kosdaq.last_close) if kosdaq else None)} ({format_briefing_number(safe_float(kosdaq.change_pct) if kosdaq and kosdaq.change_pct is not None else None, 2, '%', True)})" if kosdaq and kosdaq.last_close is not None else "- 코스닥: N/A (N/A)",
        f"- 원달러 환율: {format_briefing_number(safe_float(usdkrw.last_close) if usdkrw else None, 2, '원')} ({format_briefing_number(safe_float(usdkrw.change) if usdkrw and usdkrw.change is not None else None, 2, '원', True)})" if usdkrw and usdkrw.last_close is not None else "- 원달러 환율: N/A (N/A)",
        f"- 공포·탐욕 지수: {format_briefing_number(fg_current, 0)} ({fg_label}) / 전주: {format_briefing_number(fg_weekly, 0)}",
        f"- 기준금리: {format_briefing_number(safe_float(base_rate_snap.last_close) if base_rate_snap else None, 2, '%')} ({base_rate_status})" if base_rate_snap and base_rate_snap.last_close is not None else "- 기준금리: N/A (N/A)",
        f"- 국고채 3년: {format_briefing_number(safe_float(kr3y.last_close) if kr3y else None, 2, '%')}" if kr3y and kr3y.last_close is not None else "- 국고채 3년: N/A",
        f"- 조회 기준일: {ref_date}",
        f"- 주요 공시: {disclosure_text}",
        f"- 신호 성과 경고: {'강등 활성' if kill_state.get('active') else '정상'} ({kill_state.get('reason')})",
        "",
        "[데이터 미수신 항목]",
        f"- {missing_text}",
        "",
        "[검증된 구조화 JSON context]",
        json.dumps(structured_context, ensure_ascii=False, indent=2),
        "",
        '출력 요청: "위 output_schema.md 형식으로 오늘의 시장 브리핑을 작성하라"',
    ]

    return "\n".join(lines), missing


def call_openai_briefing(system_text: str, user_text: str) -> str:
    if not OPENAI_API_KEY or OPENAI_API_KEY == "YOUR_API_KEY":
        raise RuntimeError("OPENAI_API_KEY가 .env 파일에 설정되어 있지 않습니다.")

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_BRIEFING_MODEL,
        "instructions": system_text,
        "input": user_text,
        "max_output_tokens": 1400,
    }
    response = requests.post(OPENAI_RESPONSES_URL, headers=headers, json=payload, timeout=90)
    if response.status_code >= 400:
        try:
            error_payload = response.json()
            message = error_payload.get("error", {}).get("message") or error_payload.get("message") or response.text
        except Exception:
            message = response.text
        raise RuntimeError(f"OpenAI API 오류: {message}")

    payload_json = response.json()
    text = extract_openai_text(payload_json)
    if not text:
        raise RuntimeError("OpenAI 응답에서 텍스트를 찾지 못했습니다.")
    return text


def render_gpt_briefing_section(
    snapshot: dict[str, Snapshot],
    valid_rows: list[dict[str, Any]],
    code_to_name: dict[str, str],
    ref_date: str,
    last_refresh: str,
    refresh_token: int,
) -> None:
    st.markdown('<div class="section-title">GPT 시장 브리핑</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="small-note">브리핑 생성 버튼을 누르면 시스템 프롬프트와 지식 파일을 읽어 오늘의 시장 브리핑을 생성합니다. 검증에 실패하면 재생성 버튼으로 다시 시도할 수 있습니다.</div>',
        unsafe_allow_html=True,
    )

    context_signature = f"{refresh_token}:{ref_date}"
    if "briefing_text" not in st.session_state:
        st.session_state.briefing_text = ""
    if "briefing_error" not in st.session_state:
        st.session_state.briefing_error = ""
    if "briefing_status" not in st.session_state:
        st.session_state.briefing_status = ""
    if "briefing_context_signature" not in st.session_state:
        st.session_state.briefing_context_signature = ""
    if "briefing_last_saved_path" not in st.session_state:
        st.session_state.briefing_last_saved_path = ""

    system_text, schema_text, prompt_error = load_briefing_prompt_bundle()
    button_label = "브리핑 재생성" if st.session_state.briefing_text else "브리핑 생성"

    cols = st.columns([1, 1, 2])
    with cols[0]:
        generate_clicked = st.button(button_label, key="generate_briefing_button", use_container_width=True)
    with cols[1]:
        st.caption(f"조회 기준일: {ref_date}")
    with cols[2]:
        st.caption(f"마지막 조회 시각: {last_refresh}")

    if prompt_error:
        st.error(prompt_error)

    if generate_clicked and not prompt_error:
        with st.spinner("분석 중..."):
            try:
                user_text, missing_items = build_briefing_user_prompt(snapshot, valid_rows, refresh_token, ref_date)
                if missing_items:
                    st.caption("브리핑 입력에서 누락 감지: " + " / ".join(missing_items))
                raw_text = call_openai_briefing(system_text, user_text)
                ok, errors, cleaned_text = validate_briefing_output(raw_text, schema_text)
                if not ok:
                    st.session_state.briefing_status = "failed"
                    st.session_state.briefing_error = " / ".join(errors)
                    st.warning("브리핑 검증 실패: " + " / ".join(errors))
                else:
                    saved_path = save_briefing_text(cleaned_text, ref_date)
                    st.session_state.briefing_status = "success"
                    st.session_state.briefing_error = ""
                    st.session_state.briefing_text = cleaned_text
                    st.session_state.briefing_context_signature = context_signature
                    st.session_state.briefing_last_saved_path = str(saved_path)
                    st.caption(f"저장 완료: {saved_path}")
            except Exception as exc:
                st.session_state.briefing_status = "failed"
                st.session_state.briefing_error = str(exc)
                st.warning(f"브리핑 생성 실패: {exc}")

    if st.session_state.briefing_text:
        if st.session_state.briefing_context_signature and st.session_state.briefing_context_signature != context_signature:
            st.warning("저장된 브리핑은 이전 조회 기준입니다. 최신 데이터로 다시 생성하는 것이 좋습니다.")
        st.info(st.session_state.briefing_text)
        if st.session_state.briefing_last_saved_path:
            st.caption(f"저장 파일: {st.session_state.briefing_last_saved_path}")
        if st.session_state.briefing_error:
            st.warning(f"최근 브리핑 상태: {st.session_state.briefing_error}")
    elif st.session_state.briefing_error:
        st.warning(f"최근 브리핑 상태: {st.session_state.briefing_error}")


def _ecos_payload_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    if "RESULT" in payload:
        return []

    container: Any = payload.get("KeyStatisticList", payload)
    if isinstance(container, dict):
        rows = container.get("row")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    if isinstance(container, list):
        return [row for row in container if isinstance(row, dict)]

    for value in payload.values():
        if isinstance(value, dict):
            rows = value.get("row")
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            return [row for row in value if isinstance(row, dict)]

    return []


def _ecos_text_blob(df: pd.DataFrame) -> pd.Series:
    text_cols = [
        col
        for col in df.columns
        if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col])
    ]
    if not text_cols:
        return pd.Series([""] * len(df), index=df.index)
    return df[text_cols].fillna("").astype(str).agg(" ".join, axis=1).str.lower()


def _ecos_value_from_row(row: pd.Series) -> float | None:
    for col in ["DATA_VALUE", "VALUE", "STAT_VALUE", "ITEM_VALUE", "CURRENT_VALUE"]:
        if col in row.index:
            value = parse_float_text(str(row.get(col, "")))
            if value is not None:
                return value
    return None


def _ecos_time_from_row(row: pd.Series) -> str:
    for col in ["TIME", "TIME_NAME", "BASE_DATE", "DATE", "PERIOD"]:
        if col in row.index:
            value = clean_text(str(row.get(col, "")))
            if value:
                return value
    return ""


def _ecos_unit_from_row(row: pd.Series) -> str:
    for col in ["UNIT_NAME", "UNIT", "UNIT_NM"]:
        if col in row.index:
            value = clean_text(str(row.get(col, "")))
            if value:
                return value
    return ""


def _ecos_prev_from_row_pair(latest: pd.Series, previous: pd.Series | None) -> float | None:
    prev_candidates = ["PREV_DATA_VALUE", "PREV_VALUE", "BEFORE_DATA_VALUE", "DATA_VALUE_PREV"]
    for col in prev_candidates:
        if col in latest.index:
            value = parse_float_text(str(latest.get(col, "")))
            if value is not None:
                return value
    if previous is not None:
        return _ecos_value_from_row(previous)
    return None


def _ecos_best_match(df: pd.DataFrame, keywords: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    blob = _ecos_text_blob(df)
    mask = pd.Series(False, index=df.index)
    for keyword in keywords:
        mask = mask | blob.str.contains(re.escape(keyword.lower()), na=False)
    matched = df[mask].copy()
    if matched.empty:
        return matched
    if "_row_order" in matched.columns:
        matched = matched.sort_values("_row_order", ascending=False)
    return matched


@st.cache_data(ttl=1800, show_spinner=False)
def load_ecos_key_statistics(refresh_token: int, ecos_key: str) -> tuple[pd.DataFrame, str | None]:
    if not ecos_key or ecos_key == "YOUR_ECOS_KEY":
        return pd.DataFrame(), "ECOS API ?? ???? ?????. `.env`? `ECOS_API_KEY`? ?? ?? ?????."

    try:
        url = f"{ECOS_API_URL}/{ecos_key}/json/kr/1/100/"
        response = requests.get(url, headers=NAVER_HEADERS, timeout=12)
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, dict) and "RESULT" in payload:
            result = payload.get("RESULT") or {}
            message = clean_text(result.get("MESSAGE", "ECOS ?? ??"))
            return pd.DataFrame(), f"ECOS ?? ??: {message}"

        rows = _ecos_payload_rows(payload)
        if not rows:
            return pd.DataFrame(), "ECOS ??? ???? ????."

        df = pd.json_normalize(rows)
        df.columns = [str(col).strip() for col in df.columns]
        df["_row_order"] = range(len(df))
        return df, None
    except Exception as exc:
        return pd.DataFrame(), f"ECOS ?? ??: {exc}"


def ecos_metric_snapshot(df: pd.DataFrame, title: str, keywords: list[str], subtitle_prefix: str = "") -> Snapshot:
    if df is None or df.empty:
        return apply_snapshot_quality(Snapshot(title, title, None, None, None, None, None, None, source="BOK ECOS", unit="unknown", frequency="daily", is_fallback=False))

    matched = _ecos_best_match(df, keywords)
    if matched.empty:
        return apply_snapshot_quality(Snapshot(title, title, None, None, None, None, None, df, source="BOK ECOS", unit="unknown", frequency="daily", is_fallback=False))

    latest = matched.iloc[0]
    previous = matched.iloc[1] if len(matched) > 1 else None

    value = _ecos_value_from_row(latest)
    prev_value = _ecos_prev_from_row_pair(latest, previous)
    change = None if value is None or prev_value is None else value - prev_value
    change_pct = None if value is None or prev_value in (None, 0) else (change / prev_value) * 100
    display_name = subtitle_prefix if subtitle_prefix else title
    unit = _ecos_unit_from_row(latest) or "unknown"

    return apply_snapshot_quality(Snapshot(
        key=title,
        display_name=display_name,
        last_close=value,
        prev_close=prev_value,
        change=change,
        change_pct=change_pct,
        asof=pd.Timestamp.now(),
        raw=matched,
        source="BOK ECOS",
        unit=unit,
        frequency="daily",
        is_fallback=False,
    ))


def format_ecos_value(value: float | None, unit: str) -> str:
    if value is None:
        return "N/A"
    if unit == "%":
        return f"{value:.2f} %"
    if abs(value) >= 100:
        return f"{value:,.2f} {unit}".strip()
    return f"{value:.2f} {unit}".strip()


def render_ecos_card(title: str, snap: Snapshot, subtitle: str, unit: str) -> None:
    change_pct = snap.change_pct
    change_text = "직전 수치 없음"
    change_class_name = "flat"
    if change_pct is not None:
        change_text = f"직전 수치 대비 {change_pct:+.2f}%"
        change_class_name = change_class(change_pct)

    value_text = format_ecos_value(safe_float(snap.last_close), unit)
    value_color = color_for_change(snap.change if snap.change is not None else snap.change_pct)
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{title}</div>
            <div class="metric-name">{subtitle}</div>
            <div class="metric-value" style="color:{value_color}">{value_text}</div>
            <div class="metric-change-{change_class_name}">{change_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def ecos_market_view(df: pd.DataFrame) -> tuple[list[tuple[str, Snapshot, str]], str]:
    specs = [
        ("기준금리", ["기준금리", "base rate", "policy rate", "call rate"], "한국은행"),
        ("GDP", ["gdp", "국내총생산", "실질gdp"], "성장"),
        ("CPI", ["cpi", "소비자물가지수", "consumer price"], "물가"),
        ("M2", ["m2", "광의통화"], "유동성"),
        ("무역수지", ["무역수지", "경상수지", "trade balance", "trade surplus"], "대외수지"),
    ]

    cards: list[tuple[str, Snapshot, str]] = []
    summary_bits: list[str] = []
    for title, keywords, subtitle_prefix in specs:
        snap = ecos_metric_snapshot(df, title, keywords, subtitle_prefix)
        if snap.last_close is not None:
            latest_row = snap.raw.iloc[0] if snap.raw is not None and not snap.raw.empty else None
            unit_text = _ecos_unit_from_row(latest_row) if latest_row is not None else ""
            time_text = _ecos_time_from_row(latest_row) if latest_row is not None else ""
            subtitle = "최신 수치"
            if time_text:
                subtitle = time_text
            elif subtitle_prefix:
                subtitle = subtitle_prefix
            cards.append((title, snap, subtitle))
            if snap.last_close is not None:
                value_text = f"{snap.last_close:,.2f}" if abs(float(snap.last_close)) >= 1 else f"{snap.last_close:.4f}"
                summary_bits.append(f"{title} {value_text}{(' ' + unit_text) if unit_text else ''}")
        else:
            cards.append((title, snap, "데이터 없음"))

    if not summary_bits:
        summary = "ECOS 최신 값을 불러왔습니다."
    else:
        summary = " / ".join(summary_bits[:3])
    return cards, summary


def ecos_expert_commentary(cards: list[tuple[str, Snapshot, str]]) -> str:
    snap_map = {title: snap for title, snap, _ in cards}

    def value(title: str) -> float | None:
        snap = snap_map.get(title)
        return None if snap is None else safe_float(snap.last_close)

    rate = value("기준금리")
    gdp = value("GDP")
    cpi = value("CPI")
    m2 = value("M2")
    external = value("무역수지")

    rate_view = "통화정책은 중립적" if rate is None else (
        "금리 부담이 높은 편" if rate >= 3.0 else
        "금리 부담이 완화된 편" if rate <= 2.0 else
        "금리 부담이 과도하지도, 느슨하지도 않은 구간"
    )
    inflation_view = "물가 흐름을 확인할 수 없습니다." if cpi is None else (
        "물가 압력이 아직 높아 긴 호흡의 공격적 매수는 신중해야 합니다." if cpi >= 118 else
        "물가 압력이 크게 완화되지는 않았지만, 시장이 감내 가능한 구간입니다." if cpi >= 110 else
        "물가 측면에서는 우호적인 편입니다."
    )
    liquidity_view = "유동성 신호를 확인할 수 없습니다." if m2 is None else (
        "유동성은 풍부해 종목 장세가 붙기 쉬운 환경입니다." if m2 >= 4_000_000 else
        "유동성은 나쁘지 않지만, 레버리지보다 선별이 중요합니다." if m2 >= 3_500_000 else
        "유동성은 다소 타이트해 방어적인 운용이 유리합니다."
    )
    growth_view = "성장 모멘텀을 확인할 수 없습니다." if gdp is None else (
        "성장 모멘텀이 살아 있어 실적주와 경기민감주가 힘을 받을 가능성이 있습니다." if gdp >= 90 else
        "성장은 무난하지만, 추세가 강하게 이어지는 국면은 아닙니다."
    )
    external_view = "대외수지 신호를 확인할 수 없습니다." if external is None else (
        "대외수지가 견조해 원화와 위험자산에 완충 역할을 할 수 있습니다." if external >= 0 else
        "대외수지가 약해 환율과 외국인 수급 변동성에 주의가 필요합니다."
    )

    if rate is None and gdp is None and cpi is None and m2 is None and external is None:
        return "ECOS 핵심 지표를 불러왔지만 해석 가능한 값이 충분하지 않습니다."

    combined = " ".join([rate_view, growth_view, inflation_view, liquidity_view, external_view]).strip()
    if rate is not None and cpi is not None and m2 is not None:
        if rate >= 3.0 and cpi >= 118 and m2 >= 4_000_000:
            stance = "이 조합이면 지수 추격매수보다 현금 일부를 남긴 선별 분할매수가 유리합니다."
        elif rate <= 2.0 and cpi < 110 and m2 >= 4_000_000:
            stance = "이 조합이면 위험선호가 살아 있어 주도주 중심의 공격적 분할매수가 유리합니다."
        else:
            stance = "지금은 공격과 방어를 반반 섞되, 강한 실적과 수급이 겹치는 종목만 고르는 편이 좋습니다."
    else:
        stance = "현재는 거시 방향이 완전히 한쪽으로 기울지 않아, 종목별 차별화 대응이 더 중요합니다."

    return f"{combined} {stance}"


def render_ecos_cards(refresh_token: int) -> None:
    ecos_df, ecos_error = load_ecos_key_statistics(refresh_token, ECOS_API_KEY)
    st.markdown('<div class="section-title">한국은행 ECOS 핵심 매크로</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="small-note">기준금리, GDP, CPI, M2, 무역수지를 한 번에 캐싱해 두고, 지금 시장의 거시 압력을 빠르게 읽습니다.</div>',
        unsafe_allow_html=True,
    )
    if ecos_error:
        st.error(ecos_error)
    if ecos_df.empty:
        st.info("ECOS 핵심 지표를 표시할 수 없습니다.")
        return

    cards, summary = ecos_market_view(ecos_df)
    cols = st.columns(5)
    for col, (title, snap, subtitle) in zip(cols, cards):
        with col:
            latest_row = snap.raw.iloc[0] if snap.raw is not None and not snap.raw.empty else None
            unit_text = _ecos_unit_from_row(latest_row) if latest_row is not None else ""
            render_ecos_card(title, snap, subtitle, unit_text)
    st.caption(f"거시 해석: {ecos_expert_commentary(cards)}")


def fear_greed_zone(score: float | None) -> tuple[str, str, str]:
    if score is None:
        return "N/A", "#64748b", "지수 데이터를 불러오지 못했습니다."
    if score <= 24:
        return "극단 공포", "#dc2626", "공포가 매우 큰 구간입니다. 분할 접근이 유리하고, 추격 매수보다 최우량 종목 위주로 소액 진입이 낫습니다."
    if score <= 44:
        return "공포", "#f97316", "공포 우위 구간입니다. 공격적 베팅보다 선별적 분할 매수가 유리합니다."
    if score <= 55:
        return "중립", "#6b7280", "중립 구간입니다. 방향성 확인 전까지는 비중을 크게 늘리지 않는 편이 좋습니다."
    if score <= 74:
        return "탐욕", "#a3e635", "탐욕 우위 구간입니다. 추격매수는 불리하고, 좋은 종목은 보유하되 신규 진입은 신중해야 합니다."
    return "극단 탐욕", "#16a34a", "과열 구간입니다. 비중 축소와 차익 실현이 승률을 높입니다."


def plot_fear_greed_bar(score: float | None, label: str, color: str) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(11, 1.9))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 1)
    ax.barh(0.5, 100, color="#e5e7eb", height=0.28, edgecolor="none")

    if score is not None:
        ax.barh(0.5, score, color=color, height=0.28, edgecolor="none")
        ax.scatter([score], [0.5], s=120, color=color, edgecolors="white", linewidths=1.2, zorder=5)
        ax.text(score, 0.88, f"{score:.0f}", ha="center", va="bottom", fontsize=11, weight="bold", color=color)

    bands = [
        (0, 24, "#dc2626", "극단 공포"),
        (25, 44, "#f97316", "공포"),
        (45, 55, "#6b7280", "중립"),
        (56, 74, "#a3e635", "탐욕"),
        (75, 100, "#16a34a", "극단 탐욕"),
    ]
    for start, end, band_color, text in bands:
        ax.axvspan(start, end, color=band_color, alpha=0.06)
        ax.text((start + end) / 2, 0.14, text, ha="center", va="center", fontsize=8.5, color="#334155")

    ax.text(0, 1.08, "공포·탐욕 지수", ha="left", va="bottom", fontsize=13, weight="bold")
    ax.text(100, 1.08, label, ha="right", va="bottom", fontsize=11, weight="bold", color=color)
    ax.set_yticks([])
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.tick_params(axis="x", labelsize=9)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.tight_layout()
    return fig


def render_stock_preview(name: str, code: str, snap: Snapshot, button_key: str, insight: dict[str, Any] | None = None) -> bool:
    change = snap.change
    change_pct = snap.change_pct
    color = color_for_change(change)
    change_text = "N/A"
    if change is not None and change_pct is not None:
        change_text = f"{change:+.2f} ({change_pct:+.2f}%)"
    elif change_pct is not None:
        change_text = f"{change_pct:+.2f}%"
    elif change is not None:
        change_text = f"{change:+.2f}"
    action = insight.get("action") if insight else None
    plan = insight.get("risk_plan") if insight else None
    disc = insight.get("disclosure_risk") if insight else None
    leadership = safe_float(insight.get("leadership_score")) if insight else None
    action_text = action_label_ko(action.action if isinstance(action, ActionDecision) else "Watch Only")
    action_score = action.score if isinstance(action, ActionDecision) else 50
    expected_edge = action.expected_edge if isinstance(action, ActionDecision) else None
    qrr = action.quality_adjusted_rr if isinstance(action, ActionDecision) else None
    max_pos = action.max_position_pct if isinstance(action, ActionDecision) else 0.0
    rr = safe_float(plan.get("rr")) if isinstance(plan, dict) else None
    disclosure_text = severity_label_ko(disc.get("severity") if isinstance(disc, dict) else "Low")
    exec_plan = insight.get("execution_plan") if insight else None
    exec_quality = getattr(exec_plan, "execution_quality_score", None)

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{code}</div>
            <div class="metric-name">{name}</div>
            <div class="metric-value" style="color:{color}">{format_price(snap.last_close)}</div>
            <div class="metric-change-{change_class(change)}">{change_text}</div>
            <div class="small-note" style="margin-top:8px; line-height:1.45;">
                판단: <b>{html.escape(action_text)}</b> / {action_score}점<br/>
                주도력: {"N/A" if leadership is None else f"{leadership:.0f}"} · 기대값: {"N/A" if expected_edge is None else f"{expected_edge:+.2f}%"}<br/>
                손익비: {"N/A" if rr is None else f"{rr:.2f}x"} / 품질조정 {"N/A" if qrr is None else f"{qrr:.2f}x"}<br/>
                공시위험: {html.escape(str(disclosure_text))} · 체결품질: {"N/A" if exec_quality is None else f"{exec_quality:.0f}"}<br/>
                최대비중: {max_pos * 100:.1f}%
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return st.button("상세 보기", key=button_key, use_container_width=True)


def render_signal_box(name: str, signal: str, score: float, reasons: list[str]) -> None:
    signal_class = {
        "매수": "signal-buy",
        "중립": "signal-neutral",
        "매도": "signal-sell",
    }.get(signal, "signal-neutral")
    reasons_html = "".join(f"<div class='small-note'>- {reason}</div>" for reason in reasons)
    st.markdown(
        f"""
        <div class="signal-box">
            <div class="section-title" style="margin-top:0;">객관적 판단: <span class="{signal_class}">{signal}</span> ({score:.0f}/100)</div>
            <div class="small-note">{name}</div>
            {reasons_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_return_figure(rows: list[dict[str, Any]], active_code: str | None) -> tuple[plt.Figure, str | None]:
    if not rows:
        fig, ax = plt.subplots(figsize=(10, 2))
        ax.axis("off")
        ax.text(0.5, 0.5, "표시할 종목이 없습니다.", ha="center", va="center", fontsize=12)
        return fig, None

    df = pd.DataFrame(rows).sort_values("return_pct", ascending=True).reset_index(drop=True)
    colors = ["#dc2626" if v >= 0 else "#2563eb" for v in df["return_pct"]]
    labels = [
        f"{name} ({code})" if code != active_code else f"▶ {name} ({code})"
        for name, code in zip(df["name"], df["code"])
    ]

    fig, ax = plt.subplots(figsize=(11, max(3.4, 0.42 * len(df) + 1.0)))
    y = np.arange(len(df))
    ax.barh(y, df["return_pct"], color=colors, alpha=0.9, height=0.65)
    ax.axvline(0, color="#94a3b8", linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlabel("당일 수익률(%)", fontsize=10)
    ax.set_title("종목 당일 수익률 비교", fontsize=13, weight="bold")
    ax.grid(axis="x", linestyle="--", alpha=0.25)
    ax.set_axisbelow(True)

    for idx, value in enumerate(df["return_pct"]):
        ax.text(value + (0.15 if value >= 0 else -0.15), idx, f"{value:+.2f}%", va="center", ha="left" if value >= 0 else "right", fontsize=9)

    fig.tight_layout()
    return fig, df.iloc[-1]["code"] if len(df) else None


def plot_candlestick_with_volume(df: pd.DataFrame, title: str) -> plt.Figure:
    open_c, high_c, low_c, close_c, vol_c = find_ohlcv_columns(df)
    data = df.tail(60).copy()
    data = data[[open_c, high_c, low_c, close_c, vol_c]].dropna()
    if data.empty:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.axis("off")
        ax.text(0.5, 0.5, "최근 60거래일 데이터가 부족합니다.", ha="center", va="center", fontsize=12)
        return fig

    dates = mdates.date2num(pd.to_datetime(data.index).to_pydatetime())
    fig = plt.figure(figsize=(13, 7))
    gs = fig.add_gridspec(4, 1, height_ratios=[3, 0.05, 1.25, 0.2], hspace=0.06)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[2], sharex=ax1)

    width = 0.6
    for i, (_, row) in enumerate(data.iterrows()):
        o = float(row[open_c])
        h = float(row[high_c])
        l = float(row[low_c])
        c = float(row[close_c])
        v = "#dc2626" if c >= o else "#2563eb"
        ax1.vlines(dates[i], l, h, color=v, linewidth=1.1, alpha=0.9)
        body_low = min(o, c)
        body_height = max(abs(c - o), 0.01)
        ax1.add_patch(
            plt.Rectangle(
                (dates[i] - width / 2, body_low),
                width,
                body_height,
                facecolor=v,
                edgecolor=v,
                alpha=0.75,
            )
        )
        ax2.bar(dates[i], float(row[vol_c]), color=v, width=0.6, alpha=0.7)

    ax1.set_title(title, fontsize=13, weight="bold", loc="left")
    ax1.grid(True, axis="y", linestyle="--", alpha=0.25)
    ax1.set_ylabel("가격", fontsize=10)
    ax2.set_ylabel("거래량", fontsize=10)
    ax2.grid(True, axis="y", linestyle="--", alpha=0.25)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax2.tick_params(axis="x", rotation=0)
    plt.setp(ax1.get_xticklabels(), visible=False)
    fig.tight_layout()
    return fig


def summarize_stock(code: str, name: str, history: pd.DataFrame, kospi_close: pd.Series | None, market_score: float) -> tuple[str, float, list[str], str]:
    if history.empty:
        return "중립", 50.0, ["데이터 없음"], "low"
    _, _, _, close_c, volume_c = find_ohlcv_columns(history)
    close = history[close_c].dropna()
    vol = history[volume_c].dropna() if volume_c in history.columns else pd.Series(dtype=float)
    signal, score, reasons = stock_signal(code, history, market_score, kospi_close)
    volatility_flag = "low"
    if len(close) >= 20:
        ret20 = close.pct_change().dropna().tail(20)
        vol_ann = float(ret20.std() * math.sqrt(252) * 100) if not ret20.empty else 0.0
        volatility_flag = "high" if vol_ann >= 80 else "low"
        reasons.append(f"연환산 변동성 {vol_ann:.1f}%")
    if len(vol) >= 20:
        ratio = float(vol.iloc[-1] / vol.tail(20).mean())
        reasons.append(f"거래량 비율 {ratio:.2f}x")
    return signal, score, reasons, volatility_flag


def classify_disclosure(report_name: str) -> tuple[str, str, int]:
    text = report_name.lower()

    negative_patterns = [
        ("횡령", 3),
        ("배임", 3),
        ("영업정지", 3),
        ("관리종목", 3),
        ("상장폐지", 3),
        ("부도", 3),
        ("소송", 2),
        ("가압류", 2),
        ("해지", 2),
        ("감자", 3),
        ("유상증자", 2),
        ("cb발행", 2),
        ("bw발행", 2),
        ("전환사채", 2),
        ("자본잠식", 3),
        ("적자", 1),
    ]
    positive_patterns = [
        ("수주", 3),
        ("공급계약", 3),
        ("낙찰", 3),
        ("매출", 2),
        ("영업이익", 2),
        ("당기순이익", 2),
        ("흑자", 3),
        ("자사주", 2),
        ("배당", 2),
        ("무상증자", 3),
        ("합병", 2),
        ("분할", 1),
        ("신제품", 1),
        ("계약체결", 2),
    ]

    score = 0
    matched: list[str] = []

    for keyword, weight in positive_patterns:
        if keyword in text:
            score += weight
            matched.append(keyword)

    for keyword, weight in negative_patterns:
        if keyword in text:
            score -= weight
            matched.append(keyword)

    if score >= 2:
        return "호재", ", ".join(matched[:3]) or "긍정 신호", score
    if score <= -2:
        return "악재", ", ".join(matched[:3]) or "부정 신호", score
    return "중립", ", ".join(matched[:3]) or "특이 신호 없음", score


def clamp(value: float, low: float, high: float) -> float:
    return float(max(low, min(high, value)))


def signed_pct_text(value: float | None) -> str:
    return "N/A" if value is None else f"{value:+.2f}%"


def insight_color(value: float | None, positive_is_good: bool = True) -> str:
    if value is None or abs(value) < 1e-9:
        return "#64748b"
    is_good = value > 0 if positive_is_good else value < 0
    return "#dc2626" if is_good else "#2563eb"


def pressure_state(score: float) -> tuple[str, str, str]:
    if score >= 68:
        return "공격 우위", "#dc2626", "강한 종목은 눌림에서 비중을 늘리고, 약한 종목은 교체 후보로 봅니다."
    if score >= 56:
        return "선별 매수", "#ef4444", "상승 탄력이 있는 종목만 고르고, 추격보다 가격 구간을 기다립니다."
    if score >= 44:
        return "중립", "#64748b", "지수 방향보다 종목별 상대강도와 거래량 확인이 더 중요합니다."
    if score >= 32:
        return "방어 우위", "#2563eb", "신규 진입은 줄이고, 기존 보유 종목은 손절 기준을 먼저 확인합니다."
    return "위험 회피", "#1d4ed8", "현금 비중과 손실 제한이 우선입니다. 반등 확인 전 선진입은 피합니다."


def build_market_pressure(snapshot: dict[str, Snapshot]) -> tuple[float, list[dict[str, Any]], str, str, str]:
    score = 50.0
    rows: list[dict[str, Any]] = []

    def add_row(label: str, raw_value: float | None, contribution: float, text: str, positive_is_good: bool = True) -> None:
        nonlocal score
        score += contribution
        rows.append(
            {
                "label": label,
                "raw": raw_value,
                "text": text,
                "contribution": contribution,
                "color": insight_color(contribution, positive_is_good=True),
                "bar": clamp(abs(contribution) / 16.0 * 100.0, 4.0, 100.0),
            }
        )

    kospi_pct = snapshot.get("KOSPI").change_pct if snapshot.get("KOSPI") else None
    kosdaq_pct = snapshot.get("KOSDAQ").change_pct if snapshot.get("KOSDAQ") else None
    usd_pct = snapshot.get("USD/KRW").change_pct if snapshot.get("USD/KRW") else None
    us10y_pct = snapshot.get("US 10Y").change_pct if snapshot.get("US 10Y") else None
    kr3y_pct = snapshot.get("KR 3Y").change_pct if snapshot.get("KR 3Y") else None
    fng = safe_float(snapshot.get("FNG").last_close) if snapshot.get("FNG") else None

    if kospi_pct is not None:
        add_row("코스피", kospi_pct, clamp(kospi_pct / 2.5 * 16.0, -16.0, 16.0), signed_pct_text(kospi_pct))
    else:
        add_row("코스피", None, 0.0, "N/A")

    if kosdaq_pct is not None:
        add_row("코스닥", kosdaq_pct, clamp(kosdaq_pct / 3.0 * 14.0, -14.0, 14.0), signed_pct_text(kosdaq_pct))
    else:
        add_row("코스닥", None, 0.0, "N/A")

    if usd_pct is not None:
        add_row("환율", usd_pct, clamp(-usd_pct / 1.0 * 12.0, -12.0, 12.0), signed_pct_text(usd_pct), positive_is_good=False)
    else:
        add_row("환율", None, 0.0, "N/A", positive_is_good=False)

    rate_pct = None
    if us10y_pct is not None and kr3y_pct is not None:
        rate_pct = (us10y_pct + kr3y_pct) / 2.0
    elif us10y_pct is not None:
        rate_pct = us10y_pct
    elif kr3y_pct is not None:
        rate_pct = kr3y_pct
    if rate_pct is not None:
        add_row("금리", rate_pct, clamp(-rate_pct / 1.5 * 8.0, -8.0, 8.0), signed_pct_text(rate_pct), positive_is_good=False)
    else:
        add_row("금리", None, 0.0, "N/A", positive_is_good=False)

    if fng is not None:
        add_row("심리", fng, clamp((fng - 50.0) / 50.0 * 10.0, -10.0, 10.0), f"{fng:.0f}/100")
    else:
        add_row("심리", None, 0.0, "N/A")

    score = clamp(score, 0.0, 100.0)
    label, color, thesis = pressure_state(score)
    return score, rows, label, color, thesis


def render_market_pressure(snapshot: dict[str, Snapshot]) -> None:
    score, rows, label, color, thesis = build_market_pressure(snapshot)
    pin_left = clamp(score, 0.0, 100.0)
    row_html = []
    for row in rows:
        bar_color = row["color"]
        row_html.append(
            f"""
            <div class="signal-row">
                <div class="row-label">{html.escape(str(row["label"]))}</div>
                <div class="mini-track"><div class="mini-fill" style="width:{row["bar"]:.1f}%; background:{bar_color};"></div></div>
                <div class="row-value" style="color:{bar_color};">{html.escape(str(row["text"]))}</div>
            </div>
            """
        )
    st.html(
        f"""
        <div class="insight-panel">
            <div class="insight-head">
                <div>
                    <div class="insight-kicker">1. 시장 압력</div>
                    <div class="insight-title">한국장 압력판</div>
                </div>
                <div class="insight-badge" style="background:{color};">{label}</div>
            </div>
            <div class="pressure-score"><strong>{score:.0f}</strong><span>/100</span></div>
            <div class="meter-track"><div class="meter-pin" style="left:calc({pin_left:.1f}% - 1.5px);"></div></div>
            {''.join(row_html)}
            <div class="thesis">{html.escape(thesis)}</div>
        </div>
        """
    )


def aggregate_data_quality(snapshot: dict[str, Snapshot], valid_rows: list[dict[str, Any]]) -> tuple[int, str, str, list[str]]:
    keys = ["KOSPI", "KOSDAQ", "USD/KRW", "US 10Y", "KR 3Y", "FNG", *[row["code"] for row in valid_rows[:8]]]
    scores: list[int] = []
    messages: list[str] = []
    for key in dict.fromkeys(keys):
        snap = snapshot.get(key)
        if snap is None:
            continue
        scored = apply_snapshot_quality(snap)
        scores.append(scored.quality_score)
        for msg in (scored.errors or []) + (scored.warnings or []):
            label = scored.display_name or key
            messages.append(f"{label}: {msg}")
    score = int(round(sum(scores) / len(scores))) if scores else 0
    status, color = quality_level(score)
    if not messages:
        messages = ["표시 중인 핵심 데이터는 품질 검사를 통과했습니다."]
    return score, status, color, list(dict.fromkeys(messages))[:5]


def render_data_quality_banner(snapshot: dict[str, Snapshot], valid_rows: list[dict[str, Any]]) -> None:
    score, status, color, messages = aggregate_data_quality(snapshot, valid_rows)
    warning_html = "".join(f"<div>{idx}. {html.escape(message)}</div>" for idx, message in enumerate(messages, 1))
    st.html(
        f"""
        <div class="quality-banner">
            <div class="quality-top">
                <div>
                    <div class="insight-kicker">데이터 출처 점검</div>
                    <div class="quality-score">데이터 품질 {score}/100</div>
                </div>
                <div class="quality-status" style="background:{color};">{html.escape(status)}</div>
            </div>
            <div class="quality-warnings">{warning_html}</div>
        </div>
        """
    )


def build_market_regime_output(snapshot: dict[str, Snapshot]) -> MarketRegimeOutput:
    pressure_score, rows, label, _, _ = build_market_pressure(snapshot)
    components: dict[str, int] = {}
    drivers: list[str] = []
    for row in rows:
        contribution = safe_float(row.get("contribution")) or 0.0
        component_score = int(round(clamp(50.0 + contribution * 3.0, 0.0, 100.0)))
        components[str(row["label"])] = component_score
        if abs(contribution) >= 4:
            direction = "우호" if contribution > 0 else "부담"
            drivers.append(f"{row['label']} {direction}({row['text']})")

    score = int(round(pressure_score))
    if score <= 24:
        regime = "Extreme Risk-Off"
        cash_range = (55, 80)
        max_new_exposure = 0.20
        allowed = ["현금 확보", "손절선 점검", "주도주만 소액 관찰"]
        prohibited = ["급락주 물타기", "거래량 없는 반등 추격", "공시 미확인 신규진입"]
    elif score <= 44:
        regime = "Risk-Off"
        cash_range = (40, 65)
        max_new_exposure = 0.35
        allowed = ["주도주 1차 분할", "손익비 2.5x 이상만 검토", "방어 섹터 점검"]
        prohibited = ["전 종목 동시 매수", "손절선 없는 진입", "고변동 종목 과대비중"]
    elif score <= 64:
        regime = "Neutral"
        cash_range = (20, 50)
        max_new_exposure = 0.60
        allowed = ["종목별 선별", "리더십 상위 눌림 매수", "공시 리스크 확인"]
        prohibited = ["무차별 추격", "손익비 2.0x 미만 진입", "섹터 과집중"]
    elif score <= 79:
        regime = "Risk-On"
        cash_range = (10, 35)
        max_new_exposure = 0.80
        allowed = ["주도주 추세추종", "상위 랭킹 분할", "수익 보호선 상향"]
        prohibited = ["손절 완화", "과열권 신규 몰빵", "품질 낮은 데이터 기반 진입"]
    else:
        regime = "Euphoria"
        cash_range = (15, 45)
        max_new_exposure = 0.45
        allowed = ["이익 보호", "목표가 근접 종목 축소", "현금 회수 준비"]
        prohibited = ["신규 추격매수", "레버리지 확대", "리스크 한도 초과"]

    confidence = int(round(clamp((sum(1 for row in rows if row.get("raw") is not None) / max(len(rows), 1)) * 100, 35, 95)))
    return MarketRegimeOutput(score, regime, cash_range, max_new_exposure, allowed, prohibited, drivers[:5] or [label], confidence, components)


def render_action_console(regime: MarketRegimeOutput) -> None:
    do_html = "".join(f"<div>{idx}. {html.escape(item)}</div>" for idx, item in enumerate(regime.allowed_actions[:3], 1))
    dont_html = "".join(f"<div>{idx}. {html.escape(item)}</div>" for idx, item in enumerate(regime.prohibited_actions[:3], 1))
    st.html(
        f"""
        <div class="action-console">
            <div class="action-panel">
                <strong>오늘의 행동 · {html.escape(regime_label_ko(regime.regime))} / {regime.score}점</strong>
                {do_html}
            </div>
            <div class="action-panel">
                <strong>오늘 금지 · 현금 권장 {regime.recommended_cash_range[0]}~{regime.recommended_cash_range[1]}%</strong>
                {dont_html}
            </div>
        </div>
        """
    )


def disclosure_severity(report_name: str) -> tuple[str, int, str]:
    text = clean_text(report_name).lower()
    critical = ["횡령", "배임", "상장폐지", "감사의견거절", "의견거절", "부도", "자본잠식"]
    high = ["감자", "유상증자", "전환사채", "cb", "bw", "영업정지", "소송", "관리종목"]
    medium = ["최대주주", "불성실", "단기차입", "담보제공", "해지"]
    positive = ["자사주", "소각", "배당", "공급계약", "수주", "흑자전환"]
    if any(keyword in text for keyword in critical):
        return "Critical", 100, "치명적 공시 리스크"
    if any(keyword in text for keyword in high):
        return "High", 25, "신규매수 금지 수준"
    if any(keyword in text for keyword in medium):
        return "Medium", 8, "비중 제한 필요"
    if any(keyword in text for keyword in positive):
        return "Low", -2, "긍정/중립 이벤트"
    return "Low", 0, "특이 리스크 낮음"


def disclosure_risk_for_stock(code: str, name: str, disclosures: pd.DataFrame) -> dict[str, Any]:
    if disclosures is None or disclosures.empty:
        return {"severity": "Low", "penalty": 0, "count": 0, "summary": "최근 중요 공시 없음"}
    mask = pd.Series(False, index=disclosures.index)
    if "stock_code" in disclosures.columns:
        mask = mask | disclosures["stock_code"].astype(str).str.zfill(6).eq(code)
    if "corp_name" in disclosures.columns:
        mask = mask | disclosures["corp_name"].astype(str).str.contains(re.escape(name), na=False)
    subset = disclosures[mask].head(20)
    if subset.empty:
        return {"severity": "Low", "penalty": 0, "count": 0, "summary": "최근 중요 공시 없음"}
    best = {"severity": "Low", "penalty": 0, "count": len(subset), "summary": "특이 리스크 낮음"}
    severity_rank = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}
    for _, row in subset.iterrows():
        severity, penalty, reason = disclosure_severity(str(row.get("report_name", "")))
        if severity_rank[severity] > severity_rank[best["severity"]]:
            best = {
                "severity": severity,
                "penalty": penalty,
                "count": len(subset),
                "summary": f"{clean_text(str(row.get('report_name', '')))} · {reason}",
            }
    return best


def expected_edge_from_plan(plan: dict[str, Any], leadership_score: float, regime: MarketRegimeOutput, disclosure_risk: dict[str, Any]) -> tuple[float | None, float | None, float]:
    risk_pct = safe_float(plan.get("risk_pct"))
    upside_pct = safe_float(plan.get("upside_pct"))
    raw_rr = safe_float(plan.get("rr"))
    if risk_pct is None or upside_pct is None or raw_rr is None or risk_pct <= 0:
        return None, None, 35.0
    p_win = clamp(0.42 + (leadership_score - 50.0) / 160.0 + (raw_rr - 1.0) / 20.0 + (regime.score - 50.0) / 400.0, 0.20, 0.72)
    cost = RISK_DEFAULTS["trading_cost_pct"] + RISK_DEFAULTS["slippage_pct"]
    expected_edge = p_win * upside_pct - (1.0 - p_win) * risk_pct - cost
    regime_factor = 0.55 if regime.regime == "Extreme Risk-Off" else 0.75 if regime.regime == "Risk-Off" else 1.0 if regime.regime == "Neutral" else 1.08
    event_factor = 0.0 if disclosure_risk["severity"] == "Critical" else 0.55 if disclosure_risk["severity"] == "High" else 0.82 if disclosure_risk["severity"] == "Medium" else 1.0
    confidence = clamp((leadership_score * 0.45 + regime.confidence * 0.25 + 60 * 0.30), 20, 90)
    quality_adjusted_rr = raw_rr * (confidence / 100.0) * regime_factor * event_factor
    return expected_edge, quality_adjusted_rr, confidence


def action_label(score: float) -> str:
    if score >= 85:
        return "Strong Buy"
    if score >= 75:
        return "Buy on Pullback"
    if score >= 65:
        return "Accumulate Small"
    if score >= 55:
        return "Hold / Watch"
    if score >= 45:
        return "Watch Only"
    if score >= 35:
        return "Trim"
    return "Sell / Avoid"


def build_action_decision(
    leadership_score: float,
    plan: dict[str, Any],
    regime: MarketRegimeOutput,
    data_quality: int,
    disclosure_risk: dict[str, Any],
    execution_cost_bps: float | None = None,
    kill_switch_active: bool = False,
) -> ActionDecision:
    expected_edge, quality_adjusted_rr, confidence = expected_edge_from_plan(plan, leadership_score, regime, disclosure_risk)
    execution_cost_pct = safe_float(execution_cost_bps)
    if execution_cost_pct is not None:
        execution_cost_pct = execution_cost_pct / 100.0
        if expected_edge is not None:
            expected_edge -= execution_cost_pct
        if quality_adjusted_rr is not None:
            quality_adjusted_rr *= clamp(1.0 - execution_cost_pct / 5.0, 0.45, 1.0)
    raw_rr = safe_float(plan.get("rr"))
    blockers: list[str] = []
    if data_quality < 70:
        blockers.append("데이터 품질 낮음")
    if disclosure_risk["severity"] in {"High", "Critical"}:
        blockers.append(f"공시 리스크 {severity_label_ko(disclosure_risk['severity'])}")
    if execution_cost_pct is not None and expected_edge is not None and expected_edge <= 0:
        blockers.append("체결비용 반영 후 기대값 부족")
    if raw_rr is None or raw_rr < RISK_DEFAULTS["min_raw_rr"]:
        blockers.append("기본 손익비 미달")
    if quality_adjusted_rr is None or quality_adjusted_rr < RISK_DEFAULTS["min_quality_adjusted_rr"]:
        blockers.append("품질조정 손익비 미달")
    if expected_edge is None or expected_edge <= 0:
        blockers.append("기대값 음수/불명확")
    if regime.regime == "Extreme Risk-Off" and (raw_rr is None or raw_rr < RISK_DEFAULTS["extreme_risk_off_min_rr"]):
        blockers.append("극단 방어장 예외 조건 미달")
    if kill_switch_active:
        blockers.append("성과 저하 kill-switch")

    edge_score = 50 if expected_edge is None else clamp(50 + expected_edge * 12, 0, 100)
    rr_score = 50 if quality_adjusted_rr is None else clamp(quality_adjusted_rr / 3.0 * 100, 0, 100)
    event_penalty = safe_float(disclosure_risk.get("penalty")) or 0.0
    score = (
        regime.score * 0.15
        + leadership_score * 0.20
        + edge_score * 0.20
        + confidence * 0.15
        + rr_score * 0.15
        + 60 * 0.10
        + data_quality * 0.05
        - event_penalty
        - len(blockers) * 4
    )
    if blockers:
        score = min(score, 64)
    if kill_switch_active:
        score = min(score, 54)
    score = int(round(clamp(score, 0, 100)))

    risk_pct = safe_float(plan.get("risk_pct"))
    max_position = RISK_DEFAULTS["max_position_pct"]
    if risk_pct is not None and risk_pct > 0:
        max_position = min(max_position, RISK_DEFAULTS["risk_per_trade_pct"] / (risk_pct / 100.0))
    max_position = min(max_position, regime.max_new_exposure)
    if regime.regime == "Extreme Risk-Off":
        max_position *= 0.35
    elif regime.regime == "Risk-Off":
        max_position *= 0.60
    if blockers:
        max_position = 0.0 if disclosure_risk["severity"] in {"High", "Critical"} else min(max_position, 0.03)
    if kill_switch_active:
        max_position = min(max_position, 0.02)

    reasons = [
        f"시장 국면 {regime_label_ko(regime.regime)} {regime.score}점",
        f"주도력 {leadership_score:.0f}점",
        f"기대값 {'N/A' if expected_edge is None else f'{expected_edge:+.2f}%'}",
        f"품질조정 손익비 {'N/A' if quality_adjusted_rr is None else f'{quality_adjusted_rr:.2f}x'}",
    ]
    if execution_cost_bps is not None:
        reasons.append(f"체결비용 {execution_cost_bps:.1f}bp 반영")
    return ActionDecision(action_label(score), score, expected_edge, quality_adjusted_rr, max_position, reasons, blockers)


def snapshot_quality_for_stock(code: str, name: str, history: pd.DataFrame) -> int:
    if history is None or history.empty:
        return 35
    _, _, _, close_c, _ = find_ohlcv_columns(history)
    close = history[close_c].dropna() if close_c in history.columns else pd.Series(dtype=float)
    latest = safe_float(close.iloc[-1]) if not close.empty else None
    prev = safe_float(close.iloc[-2]) if len(close) >= 2 else None
    change = None if latest is None or prev is None else latest - prev
    change_pct = None if latest is None or prev in (None, 0) or change is None else change / prev * 100
    snap = apply_snapshot_quality(
        Snapshot(
            key=code,
            display_name=name,
            last_close=latest,
            prev_close=prev,
            change=change,
            change_pct=change_pct,
            asof=last_trading_ts(history),
            raw=history,
            source="FinanceDataReader",
            unit="KRW",
            frequency="historical",
            is_fallback=True,
        )
    )
    return snap.quality_score


def build_watchlist_insights(
    valid_rows: list[dict[str, Any]],
    refresh_token: int,
    kospi_close: pd.Series | None,
    market_score: float,
    regime_output: MarketRegimeOutput | None = None,
    disclosures: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if regime_output is None:
        regime_output = MarketRegimeOutput(int(clamp(50 + market_score * 8, 0, 100)), "Neutral", (20, 50), 0.60, [], [], [], 60, {})
    if disclosures is None:
        disclosures = load_recent_disclosures(refresh_token, DART_API_TOKEN, limit=150)
    try:
        kill_state = get_kill_switch_state(SIGNAL_LEDGER_DB)
        kill_active = bool(kill_state.get("active"))
    except Exception:
        kill_active = False
    for item in valid_rows[:15]:
        code = str(item["code"])
        name = str(item["name"])
        hist = load_symbol_history(code, refresh_token, periods=240)
        disc_risk = disclosure_risk_for_stock(code, name, disclosures)
        if hist.empty:
            empty_plan = risk_plan_for_stock(code, name, hist)
            exec_plan = build_execution_plan(hist, target_order_value=5_000_000, market_regime=regime_output.regime)
            decision = build_action_decision(50.0, empty_plan, regime_output, 40, disc_risk, exec_plan.total_execution_cost_bps, kill_active)
            rows.append(
                {
                    "code": code,
                    "name": name,
                    "signal": decision.action,
                    "score": 50.0,
                    "r1": None,
                    "r5": None,
                    "r20": None,
                    "rs": None,
                    "vol_ratio": None,
                    "history": hist,
                    "risk_plan": empty_plan,
                    "disclosure_risk": disc_risk,
                    "execution_plan": exec_plan,
                    "action": decision,
                }
            )
            continue

        _, _, _, close_c, volume_c = find_ohlcv_columns(hist)
        close = hist[close_c].dropna()
        volume = hist[volume_c].dropna() if volume_c in hist.columns else pd.Series(dtype=float)
        returns = calc_returns(close)
        signal, score, _ = stock_signal(code, hist, market_score, kospi_close)
        rs = relative_strength(close, kospi_close) if kospi_close is not None else None
        vol_ratio = None
        if len(volume) >= 20:
            avg20 = float(volume.tail(20).mean())
            if avg20 > 0:
                vol_ratio = float(volume.iloc[-1] / avg20)
        plan = risk_plan_for_stock(code, name, hist)
        exec_plan = build_execution_plan(hist, target_order_value=5_000_000, market_regime=regime_output.regime)
        snap_score = snapshot_quality_for_stock(code, name, hist)
        decision = build_action_decision(score, plan, regime_output, snap_score, disc_risk, exec_plan.total_execution_cost_bps, kill_active)
        rows.append(
            {
                "code": code,
                "name": name,
                "signal": decision.action,
                "score": decision.score,
                "leadership_score": score,
                "r1": returns["1d"],
                "r5": returns["5d"],
                "r20": returns["20d"],
                "rs": rs,
                "vol_ratio": vol_ratio,
                "history": hist,
                "risk_plan": plan,
                "disclosure_risk": disc_risk,
                "execution_plan": exec_plan,
                "action": decision,
            }
        )
    return sorted(rows, key=lambda row: (row["score"], row["rs"] if row["rs"] is not None else -999.0), reverse=True)


def render_watchlist_ranking(rows: list[dict[str, Any]]) -> None:
    visible = rows[:7]
    rank_html = [
        """
        <div class="rank-row" style="border-top:0; padding-top:0;">
            <div class="rank-header">#</div>
            <div class="rank-header">종목</div>
            <div class="rank-header">판단</div>
            <div class="rank-header">당일</div>
            <div class="rank-header">기대값</div>
            <div class="rank-header">최대비중</div>
        </div>
        """
    ]
    if not visible:
        rank_html.append('<div class="thesis">표시할 관심 종목 데이터가 없습니다.</div>')
    for idx, row in enumerate(visible, 1):
        score = safe_float(row.get("score")) or 0.0
        score_color = "#dc2626" if score >= 65 else "#2563eb" if score <= 44 else "#64748b"
        r1 = safe_float(row.get("r1"))
        action = row.get("action")
        expected_edge = action.expected_edge if isinstance(action, ActionDecision) else None
        max_position = action.max_position_pct if isinstance(action, ActionDecision) else 0.0
        blockers = action.blockers if isinstance(action, ActionDecision) else []
        blocker_text = " · 차단 " + str(len(blockers)) if blockers else ""
        action_text = action_label_ko(str(row.get("signal")))
        rank_html.append(
            f"""
            <div class="rank-row">
                <div class="row-label">{idx}</div>
                <div class="rank-name"><strong>{html.escape(str(row["name"]))}</strong><span>{html.escape(str(row["code"]))} · 주도 {safe_float(row.get("leadership_score")) or 0:.0f}{html.escape(blocker_text)}</span></div>
                <div class="row-value" style="color:{score_color};">{html.escape(action_text)}<br>{score:.0f}점</div>
                <div class="row-value" style="color:{insight_color(r1)};">{signed_pct_text(r1)}</div>
                <div class="row-value" style="color:{insight_color(expected_edge)};">{"N/A" if expected_edge is None else f"{expected_edge:+.2f}%"}</div>
                <div class="row-value">{max_position * 100:.1f}%</div>
            </div>
            """
        )

    thesis = "상위 종목일수록 추세, 상대강도, 거래량이 동시에 우위입니다."
    if visible:
        leader = visible[0]
        thesis = f"현재 관심목록 최상위는 {leader['name']}입니다. 점수는 {safe_float(leader['score']) or 0:.0f}점이며, 추격보다 가격 구간 확인이 우선입니다."
    st.html(
        f"""
        <div class="insight-panel">
            <div class="insight-head">
                <div>
                    <div class="insight-kicker">2. 주도주</div>
                    <div class="insight-title">관심종목 우선순위</div>
                </div>
                <div class="insight-badge" style="background:#0f766e;">상대강도</div>
            </div>
            {''.join(rank_html)}
            <div class="thesis">{html.escape(thesis)}</div>
        </div>
        """
    )


def risk_plan_for_stock(code: str, name: str, history: pd.DataFrame) -> dict[str, Any]:
    empty = {
        "code": code,
        "name": name,
        "latest": None,
        "entry_low": None,
        "entry_high": None,
        "stop": None,
        "resistance": None,
        "risk_pct": None,
        "upside_pct": None,
        "rr": None,
        "label": "데이터 부족",
        "color": "#64748b",
        "thesis": "가격 구간을 계산할 데이터가 부족합니다.",
    }
    if history is None or history.empty:
        return empty

    open_c, high_c, low_c, close_c, _ = find_ohlcv_columns(history)
    data = history[[open_c, high_c, low_c, close_c]].dropna().tail(160)
    if len(data) < 20:
        return empty

    close = data[close_c].astype(float)
    high = data[high_c].astype(float)
    low = data[low_c].astype(float)
    latest = float(close.iloc[-1])
    prev_close = close.shift(1)
    true_range = pd.concat([(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = float(true_range.tail(14).mean()) if len(true_range.dropna()) >= 5 else latest * 0.03
    support20 = float(low.tail(20).min())
    resistance20 = float(high.tail(20).max())
    resistance60 = float(high.tail(min(60, len(high))).max())
    resistance120 = float(high.tail(min(120, len(high))).max())
    resistance = max(resistance20, resistance60, resistance120)
    stop = max(0.0, support20 - atr * 0.35)
    entry_low = max(stop, latest - atr * 0.55)
    entry_high = latest + atr * 0.15
    risk_pct = None if latest <= 0 or stop <= 0 or stop >= latest else (latest - stop) / latest * 100
    upside_pct = None if latest <= 0 else (resistance / latest - 1) * 100
    rr = None
    if risk_pct not in (None, 0) and upside_pct is not None:
        rr = upside_pct / risk_pct

    if rr is not None and rr >= 1.7 and upside_pct is not None and upside_pct > 0:
        label, color = "손익비 우위", "#dc2626"
        thesis = "상단 여지가 위험폭보다 큽니다. 진입은 구간 하단에서 나눠 보는 편이 유리합니다."
    elif rr is not None and rr < 0.8:
        label, color = "손익비 열위", "#2563eb"
        thesis = "상승 여지보다 손실 폭이 큽니다. 매수보다 관망 또는 가격 재조정 확인이 먼저입니다."
    else:
        label, color = "구간 확인", "#64748b"
        thesis = "방향은 열려 있지만 우위가 압도적이지 않습니다. 돌파나 눌림 확인이 필요합니다."

    return {
        "code": code,
        "name": name,
        "latest": latest,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop": stop,
        "resistance": resistance,
        "risk_pct": risk_pct,
        "upside_pct": upside_pct,
        "rr": rr,
        "label": label,
        "color": color,
        "thesis": thesis,
    }


def render_risk_plan(active_code: str | None, code_to_name: dict[str, str], refresh_token: int, action: ActionDecision | None = None) -> None:
    if active_code is None:
        plan = risk_plan_for_stock("", "선택 종목", pd.DataFrame())
    else:
        active_name = code_to_name.get(active_code, STOCK_UNIVERSE_NAME_HINTS.get(active_code, active_code))
        plan = risk_plan_for_stock(active_code, active_name, load_symbol_history(active_code, refresh_token, periods=240))

    value_rows = [
        ("현재가", format_price(plan["latest"])),
        ("진입 구간", "N/A" if plan["entry_low"] is None or plan["entry_high"] is None else f"{format_price(plan['entry_low'])} ~ {format_price(plan['entry_high'])}"),
        ("손절 기준", format_price(plan["stop"])),
        ("상단 기준", format_price(plan["resistance"])),
        ("위험폭", "N/A" if plan["risk_pct"] is None else f"{plan['risk_pct']:.2f}%"),
        ("상승 여지", "N/A" if plan["upside_pct"] is None else f"{plan['upside_pct']:+.2f}%"),
        ("손익비", "N/A" if plan["rr"] is None else f"{plan['rr']:.2f}x"),
        ("기대값", "N/A" if action is None or action.expected_edge is None else f"{action.expected_edge:+.2f}%"),
        ("품질조정 R/R", "N/A" if action is None or action.quality_adjusted_rr is None else f"{action.quality_adjusted_rr:.2f}x"),
        ("최대 비중", "N/A" if action is None else f"{action.max_position_pct * 100:.1f}%"),
    ]
    row_html = "".join(
        f"""
        <div class="risk-row">
            <div class="row-label">{html.escape(label)}</div>
            <div class="row-value">{html.escape(value)}</div>
        </div>
        """
        for label, value in value_rows
    )
    title = f"{plan['name']} · {plan['code']}" if plan["code"] else plan["name"]
    st.html(
        f"""
        <div class="insight-panel">
            <div class="insight-head">
                <div>
                    <div class="insight-kicker">3. 손익비</div>
                    <div class="insight-title">{html.escape(title)}</div>
                </div>
                <div class="insight-badge" style="background:{plan['color']};">{html.escape(action_label_ko(action.action) if action else plan['label'])}</div>
            </div>
            {row_html}
            <div class="thesis">{html.escape(plan["thesis"])}</div>
        </div>
        """
    )


def _format_bps(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.1f}bp"


def _format_krw(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:,.0f}원"


def render_execution_card(exec_plan: Any, expected_edge: float | None = None) -> None:
    warning_lines = []
    if getattr(exec_plan, "unavailable_fields", None):
        warning_lines.append("unavailable: " + ", ".join(exec_plan.unavailable_fields[:4]))
    if getattr(exec_plan, "warnings", None):
        warning_lines.extend(exec_plan.warnings[:3])
    if should_block_for_execution(exec_plan, expected_edge):
        warning_lines.append("체결비용 대비 기대값이 부족해 신규 진입 제한")
    warnings_html = "".join(f"<div>{idx}. {html.escape(str(text))}</div>" for idx, text in enumerate(warning_lines, 1)) or "<div>특이 경고 없음</div>"
    row_html = "".join(
        f"""
        <div class="risk-row">
            <div class="row-label">{html.escape(label)}</div>
            <div class="row-value">{html.escape(value)}</div>
        </div>
        """
        for label, value in [
            ("체결품질", f"{getattr(exec_plan, 'execution_quality_score', 0):.0f}/100"),
            ("유동성", f"{getattr(exec_plan, 'liquidity_score', 0):.0f}/100"),
            ("총 비용", _format_bps(getattr(exec_plan, "total_execution_cost_bps", None))),
            ("슬리피지", _format_bps(getattr(exec_plan, "estimated_slippage_bps", None))),
            ("시장충격", _format_bps(getattr(exec_plan, "estimated_market_impact_bps", None))),
            ("무충격 한도", _format_krw(getattr(exec_plan, "max_order_value_without_impact", None))),
            ("주문 방식", str(getattr(exec_plan, "recommended_order_style", "대기"))),
            ("분할 수", str(getattr(exec_plan, "recommended_slices", 0))),
        ]
    )
    quality = safe_float(getattr(exec_plan, "execution_quality_score", 0)) or 0
    color = "#dc2626" if quality >= 70 else "#64748b" if quality >= 40 else "#2563eb"
    st.html(
        f"""
        <div class="insight-panel">
            <div class="insight-head">
                <div>
                    <div class="insight-kicker">체결 품질</div>
                    <div class="insight-title">Execution Quality</div>
                </div>
                <div class="insight-badge" style="background:{color};">{quality:.0f}점</div>
            </div>
            {row_html}
            <div class="thesis">{warnings_html}</div>
        </div>
        """
    )


def render_exit_plan_card(exit_plan: Any) -> None:
    row_html = "".join(
        f"""
        <div class="risk-row">
            <div class="row-label">{html.escape(label)}</div>
            <div class="row-value">{html.escape(value)}</div>
        </div>
        """
        for label, value in [
            ("초기 손절", format_price(getattr(exit_plan, "initial_stop", None))),
            ("Hard stop", format_price(getattr(exit_plan, "hard_stop", None))),
            ("Trailing", format_price(getattr(exit_plan, "trailing_stop", None))),
            ("1차 익절", format_price(getattr(exit_plan, "first_take_profit", None))),
            ("2차 익절", format_price(getattr(exit_plan, "second_take_profit", None))),
            ("시간 손절", str(getattr(exit_plan, "time_stop_date", "unavailable"))),
            ("Runner", f"{getattr(exit_plan, 'runner_position_pct', 0) * 100:.0f}%"),
            ("신뢰도", f"{getattr(exit_plan, 'exit_confidence', 0):.0f}/100"),
        ]
    )
    invalidation = getattr(exit_plan, "invalidation_rules", []) or []
    warnings = getattr(exit_plan, "warnings", []) or []
    thesis = " / ".join([*invalidation[:2], *warnings[:2]]) or "현재 청산 규칙은 정상 계산되었습니다."
    status = str(getattr(exit_plan, "status", "계산 불가"))
    color = "#dc2626" if "수익" in status or "러너" in status else "#64748b" if "위험" in status else "#2563eb"
    st.html(
        f"""
        <div class="insight-panel">
            <div class="insight-head">
                <div>
                    <div class="insight-kicker">청산 계획</div>
                    <div class="insight-title">Dynamic Exit Plan</div>
                </div>
                <div class="insight-badge" style="background:{color};">{html.escape(status)}</div>
            </div>
            {row_html}
            <div class="thesis">{html.escape(thesis)}</div>
        </div>
        """
    )


def render_investment_insight_panels(
    snapshot: dict[str, Snapshot],
    valid_rows: list[dict[str, Any]],
    code_to_name: dict[str, str],
    refresh_token: int,
    market_score: float,
    kospi_close: pd.Series | None,
    regime_output: MarketRegimeOutput | None = None,
) -> list[dict[str, Any]]:
    codes_in_order = [row["code"] for row in valid_rows]
    active_code = st.session_state.manual_active_code if st.session_state.manual_active_code in codes_in_order else (codes_in_order[0] if codes_in_order else None)
    if regime_output is None:
        regime_output = MarketRegimeOutput(int(clamp(50 + market_score * 8, 0, 100)), "Neutral", (20, 50), 0.60, [], [], [], 60, {})
    rank_rows = build_watchlist_insights(valid_rows, refresh_token, kospi_close, market_score, regime_output)
    active_action = None
    for row in rank_rows:
        if row["code"] == active_code and isinstance(row.get("action"), ActionDecision):
            active_action = row["action"]
            break
    st.markdown('<div class="section-title">투자 판단 핵심 3항목</div>', unsafe_allow_html=True)
    col_pressure, col_rank, col_risk = st.columns([1.05, 1.45, 1.05])
    with col_pressure:
        render_market_pressure(snapshot)
    with col_rank:
        render_watchlist_ranking(rank_rows)
    with col_risk:
        render_risk_plan(active_code, code_to_name, refresh_token, active_action)
    return rank_rows


def parse_portfolio_text(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    if not text.strip():
        return [], []
    errors: list[str] = []
    try:
        df = pd.read_csv(io.StringIO(text.strip()))
    except Exception as exc:
        return [], [f"CSV 파싱 실패: {exc}"]
    required = {"code", "qty", "avg_price"}
    missing = required - set(df.columns)
    if missing:
        return [], [f"필수 컬럼 누락: {', '.join(sorted(missing))}"]
    rows: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        code = re.sub(r"\D", "", str(row.get("code", ""))).zfill(6)
        qty = safe_float(row.get("qty"))
        avg_price = safe_float(row.get("avg_price"))
        if len(code) != 6 or qty is None or avg_price is None:
            errors.append(f"{idx + 1}행: code/qty/avg_price 확인 필요")
            continue
        rows.append(
            {
                "code": code,
                "qty": qty,
                "avg_price": avg_price,
                "sector": clean_text(str(row.get("sector", "미분류"))),
            }
        )
    return rows, errors


def render_portfolio_section(
    snapshot: dict[str, Snapshot],
    code_to_name: dict[str, str],
    refresh_token: int,
    last_refresh: str,
) -> None:
    st.markdown('<div class="section-title">Portfolio Command Center</div>', unsafe_allow_html=True)
    total_assets = safe_float(st.session_state.get("portfolio_total_assets")) or 100_000_000.0
    cash = safe_float(st.session_state.get("portfolio_cash")) or 0.0
    holdings_text = str(st.session_state.get("portfolio_holdings_text", ""))
    holdings, errors = parse_portfolio_text(holdings_text)
    regime = build_market_regime_output(snapshot)

    if errors:
        for err in errors:
            st.warning(err)
    cash_pct = cash / total_assets * 100 if total_assets > 0 else 0.0
    cols = st.columns(4)
    cols[0].metric("총자산", f"{total_assets:,.0f}원")
    cols[1].metric("현금", f"{cash:,.0f}원")
    cols[2].metric("현금비중", f"{cash_pct:.1f}%")
    cols[3].metric("시장 국면", f"{regime_label_ko(regime.regime)} / {regime.score}")
    st.caption(f"마지막 조회 시각: {last_refresh}")

    if not holdings:
        st.info("사이드바의 보유종목 CSV에 `code,qty,avg_price,sector` 형식으로 입력하면 포트폴리오 리스크가 계산됩니다.")
        st.code("code,qty,avg_price,sector\n005930,10,75000,반도체\n034020,5,25000,원전", language="text")
        return

    table_rows: list[str] = []
    exit_rows: list[tuple[int, str]] = []
    sector_exposure: dict[str, float] = {}
    portfolio_value = cash
    for holding in holdings:
        code = holding["code"]
        name = code_to_name.get(code, STOCK_UNIVERSE_NAME_HINTS.get(code, code))
        hist = load_symbol_history(code, refresh_token, periods=240)
        plan = risk_plan_for_stock(code, name, hist)
        exit_plan = build_exit_plan(plan, hist)
        latest = safe_float(plan.get("latest")) or safe_float(snapshot.get(code).last_close if snapshot.get(code) else None) or holding["avg_price"]
        value = latest * holding["qty"]
        pnl = (latest / holding["avg_price"] - 1) * 100 if holding["avg_price"] else None
        stop = safe_float(plan.get("stop"))
        loss_at_stop = max((latest - stop) * holding["qty"], 0) if stop is not None else None
        loss_pct_assets = loss_at_stop / total_assets * 100 if loss_at_stop is not None and total_assets > 0 else None
        sector = holding["sector"] or "미분류"
        sector_exposure[sector] = sector_exposure.get(sector, 0.0) + value
        portfolio_value += value
        table_rows.append(
            f"""
            <tr>
                <td>{html.escape(name)}<br><span class="row-sub">{code}</span></td>
                <td>{holding['qty']:,.0f}</td>
                <td>{latest:,.0f}</td>
                <td style="color:{insight_color(pnl)};">{"N/A" if pnl is None else f"{pnl:+.2f}%"}</td>
                <td>{format_price(stop)}</td>
                <td>{"N/A" if loss_pct_assets is None else f"{loss_pct_assets:.2f}%"}</td>
                <td>{html.escape(sector)}</td>
            </tr>
            """
        )
        priority = 0
        if "위험" in exit_plan.status or exit_plan.exit_confidence < 45:
            priority += 2
        if loss_pct_assets is not None and loss_pct_assets > RISK_DEFAULTS["risk_per_trade_pct"] * 100:
            priority += 2
        if exit_plan.warnings:
            priority += 1
        exit_rows.append(
            (
                priority,
                f"""
                <tr>
                    <td>{html.escape(name)}<br><span class="row-sub">{code}</span></td>
                    <td>{html.escape(exit_plan.status)}</td>
                    <td>{format_price(exit_plan.hard_stop)}</td>
                    <td>{format_price(exit_plan.first_take_profit)}</td>
                    <td>{exit_plan.runner_position_pct * 100:.0f}%</td>
                    <td>{exit_plan.exit_confidence:.0f}</td>
                </tr>
                """,
            )
        )

    max_sector = max((value / total_assets * 100 for value in sector_exposure.values()), default=0.0) if total_assets > 0 else 0.0
    if cash_pct < regime.recommended_cash_range[0]:
        st.warning(f"현재 현금비중 {cash_pct:.1f}%는 권장 하단 {regime.recommended_cash_range[0]}%보다 낮습니다.")
    if max_sector > RISK_DEFAULTS["max_sector_pct"] * 100:
        st.warning(f"단일 섹터 노출 {max_sector:.1f}%가 기본 한도 {RISK_DEFAULTS['max_sector_pct'] * 100:.0f}%를 초과합니다.")

    st.html(
        f"""
        <table class="command-table">
            <thead>
                <tr><th>종목</th><th>수량</th><th>현재가</th><th>손익률</th><th>손절</th><th>손절시 총자산 손실</th><th>섹터</th></tr>
            </thead>
            <tbody>{''.join(table_rows)}</tbody>
        </table>
        """
    )
    st.markdown('<div class="section-title">청산 우선순위</div>', unsafe_allow_html=True)
    sorted_exit_rows = [row for _, row in sorted(exit_rows, key=lambda item: item[0], reverse=True)]
    st.html(
        f"""
        <table class="command-table">
            <thead>
                <tr><th>종목</th><th>상태</th><th>Hard stop</th><th>1차 익절</th><th>Runner</th><th>신뢰도</th></tr>
            </thead>
            <tbody>{''.join(sorted_exit_rows)}</tbody>
        </table>
        """
    )
    st.caption(f"추정 포트폴리오 평가금액: {portfolio_value:,.0f}원")


def render_settings_section() -> None:
    st.markdown('<div class="section-title">Settings</div>', unsafe_allow_html=True)
    st.write("현재 v1 기본 리스크 설정입니다. 사이드바에서 총자산, 현금, 거래비용, 슬리피지, 보유 CSV를 조정할 수 있습니다.")
    settings_rows = "".join(
        f"<tr><td>{html.escape(key)}</td><td>{value}</td></tr>"
        for key, value in RISK_DEFAULTS.items()
    )
    st.html(
        f"""
        <table class="command-table">
            <thead><tr><th>항목</th><th>값</th></tr></thead>
            <tbody>{settings_rows}</tbody>
        </table>
        """
    )


def append_code_to_sidebar(code: str) -> None:
    current = str(
        st.session_state.get(
            "pending_sidebar_codes_text",
            st.session_state.get("sidebar_codes_text", "\n".join(DEFAULT_CODES)),
        )
    )
    codes, _ = parse_code_input(current)
    if code not in codes:
        codes.append(code)
    st.session_state.pending_sidebar_codes_text = "\n".join(codes[:15])
    st.session_state.pending_sidebar_message = f"{code} 관심종목 추가 완료"


def _candidate_display_rows(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(candidates, 1):
        rows.append(
            {
                "순위": idx,
                "종목": f"{item.get('name')} ({item.get('code')})",
                "시장": item.get("market"),
                "분류": item.get("category"),
                "발굴점수": item.get("discovery_score"),
                "주도력": item.get("leadership_score"),
                "기대값": "unavailable" if item.get("expected_edge") is None else f"{item.get('expected_edge'):+.2f}%",
                "손익비": "unavailable" if item.get("risk_reward_ratio") is None else f"{item.get('risk_reward_ratio'):.2f}x",
                "트리거": "unavailable" if item.get("trigger_price") is None else f"{item.get('trigger_price'):,.0f}",
                "손절": "unavailable" if item.get("stop_price") is None else f"{item.get('stop_price'):,.0f}",
                "최대비중": f"{float(item.get('max_position_pct') or 0) * 100:.1f}%",
                "신뢰도": item.get("confidence"),
            }
        )
    return rows


def render_alpha_discovery_summary(refresh_token: int) -> None:
    requested = bool(st.session_state.get("discovery_scan_requested", False))
    if not requested:
        st.info("Alpha Discovery는 버튼 실행 후 Dashboard 요약에 표시됩니다.")
        return
    max_symbols = int(st.session_state.get("discovery_max_symbols", 220))
    candidates, warnings, total, scanned = run_alpha_discovery_scan(refresh_token, max_symbols)
    if not candidates:
        st.warning("스캔 결과가 없습니다. 데이터 품질 또는 네트워크 상태를 확인하세요.")
        return
    top = candidates[0]
    st.html(
        f"""
        <div class="insight-panel">
            <div class="insight-head">
                <div>
                    <div class="insight-kicker">Alpha Discovery</div>
                    <div class="insight-title">{html.escape(str(top.get('name')))} ({html.escape(str(top.get('code')))}): {html.escape(str(top.get('category')))}</div>
                </div>
                <div class="insight-badge" style="background:#0f766e;">{float(top.get('discovery_score') or 0):.0f}점</div>
            </div>
            <div class="thesis">전체 {total:,}개 중 {scanned:,}개 스캔. 상위 후보는 관심종목에 추가해 상세 손익비와 체결 품질을 확인하세요.</div>
        </div>
        """
    )
    if warnings:
        st.caption(" / ".join(warnings[:2]))


def render_dashboard_extension_summary(
    snapshot: dict[str, Snapshot],
    valid_rows: list[dict[str, Any]],
    code_to_name: dict[str, str],
    refresh_token: int,
    regime_output: MarketRegimeOutput,
) -> None:
    st.markdown('<div class="section-title">고도화 모듈 요약</div>', unsafe_allow_html=True)
    cols = st.columns([1.15, 1, 1, 1])
    with cols[0]:
        render_alpha_discovery_summary(refresh_token)

    active_code = st.session_state.manual_active_code if st.session_state.manual_active_code in [row["code"] for row in valid_rows] else (valid_rows[0]["code"] if valid_rows else None)
    if active_code:
        active_name = code_to_name.get(active_code, STOCK_UNIVERSE_NAME_HINTS.get(active_code, active_code))
        active_hist = load_symbol_history(active_code, refresh_token, periods=240)
        plan = risk_plan_for_stock(active_code, active_name, active_hist)
        exec_plan = build_execution_plan(active_hist, target_order_value=5_000_000, market_regime=regime_output.regime)
        exit_plan = build_exit_plan(plan, active_hist, market_regime=regime_output.regime)
    else:
        exec_plan = build_execution_plan(pd.DataFrame(), target_order_value=0)
        exit_plan = build_exit_plan({}, pd.DataFrame())

    with cols[1]:
        st.metric("체결 품질", f"{exec_plan.execution_quality_score:.0f}/100", exec_plan.recommended_order_style)
        if exec_plan.warnings:
            st.caption(exec_plan.warnings[0])
    with cols[2]:
        st.metric("청산 상태", exit_plan.status, f"신뢰도 {exit_plan.exit_confidence:.0f}")
        if exit_plan.invalidation_rules:
            st.caption(exit_plan.invalidation_rules[0])
    with cols[3]:
        try:
            kill_state = get_kill_switch_state(SIGNAL_LEDGER_DB)
        except Exception as exc:
            kill_state = {"active": False, "reason": f"ledger unavailable: {exc}", "sample_size": 0, "hit_rate": None}
        st.metric("신호 성과", "강등" if kill_state.get("active") else "정상", f"표본 {kill_state.get('sample_size')}")
        st.caption(str(kill_state.get("reason")))


def render_alpha_discovery_section(refresh_token: int) -> None:
    st.markdown('<div class="section-title">Alpha Discovery</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="small-note">KOSPI/KOSDAQ 전체 유니버스에서 상대강도, 52주 고점 근접, 거래대금 급증, 눌림목, 급락장 생존주, 매수 금지 후보를 캐시형으로 탐색합니다.</div>',
        unsafe_allow_html=True,
    )
    max_symbols = st.slider(
        "스캔 종목 수",
        min_value=50,
        max_value=1000,
        value=int(st.session_state.get("discovery_max_symbols", 220)),
        step=50,
        help="전체시장 스캔은 시간이 걸릴 수 있어 v1에서는 캐시 기반으로 점진 실행합니다.",
    )
    st.session_state.discovery_max_symbols = max_symbols
    col_run, col_clear = st.columns([1, 1])
    with col_run:
        if st.button("전체시장 스캔 실행", use_container_width=True):
            st.session_state.discovery_scan_requested = True
            run_alpha_discovery_scan.clear()
    with col_clear:
        if st.button("스캔 캐시 유지/결과 보기", use_container_width=True):
            st.session_state.discovery_scan_requested = True

    if not st.session_state.get("discovery_scan_requested", False):
        st.info("버튼을 누르면 스캔을 시작합니다. 기존 대시보드 로딩은 스캔과 분리되어 있습니다.")
        return

    with st.spinner("전체시장 후보를 스캔 중입니다. 처음 실행은 시간이 걸릴 수 있습니다."):
        candidates, warnings, total, scanned = run_alpha_discovery_scan(refresh_token, max_symbols)
    st.caption(f"상장 유니버스 {total:,}개 중 {scanned:,}개 스캔 · 상위 {len(candidates)}개 표시")
    if warnings:
        st.warning(" / ".join(warnings[:5]))
    if not candidates:
        st.error("표시할 후보가 없습니다. 데이터 공급자 상태를 확인하세요.")
        return

    st.dataframe(pd.DataFrame(_candidate_display_rows(candidates)), hide_index=True, use_container_width=True)
    st.markdown('<div class="section-title">관심종목에 추가</div>', unsafe_allow_html=True)
    add_cols = st.columns(min(5, len(candidates)))
    for col, item in zip(add_cols, candidates[:5]):
        with col:
            code = str(item.get("code"))
            if st.button(f"{item.get('name')} 추가", key=f"add_discovery_{code}", use_container_width=True):
                append_code_to_sidebar(code)
                st.success(f"{item.get('name')} ({code})를 관심종목 입력에 추가했습니다.")
                st.rerun()

    with st.expander("상위 후보 근거"):
        for item in candidates[:10]:
            positives = " / ".join(item.get("positive_reasons") or ["근거 unavailable"])
            negatives = " / ".join(item.get("negative_reasons") or ["부정 근거 없음"])
            st.markdown(f"**{item.get('name')} ({item.get('code')})** · {item.get('category')} · {item.get('discovery_score'):.0f}점")
            st.caption(f"우호: {positives}")
            st.caption(f"주의: {negatives}")


def render_signal_outcome_section(
    snapshot: dict[str, Snapshot],
    valid_rows: list[dict[str, Any]],
    code_to_name: dict[str, str],
    refresh_token: int,
) -> None:
    st.markdown('<div class="section-title">Signal Outcome Ledger</div>', unsafe_allow_html=True)
    init_db(SIGNAL_LEDGER_DB)
    kill_state = get_kill_switch_state(SIGNAL_LEDGER_DB)
    metric_cols = st.columns(4)
    metric_cols[0].metric("Kill-switch", "강등" if kill_state.get("active") else "정상")
    metric_cols[1].metric("성과 표본", str(kill_state.get("sample_size")))
    metric_cols[2].metric("적중률", "N/A" if kill_state.get("hit_rate") is None else f"{kill_state.get('hit_rate') * 100:.1f}%")
    metric_cols[3].metric("상태", str(kill_state.get("reason")))

    market_score, _ = market_regime(snapshot)
    regime_output = build_market_regime_output(snapshot)
    kospi_snap = snapshot.get("KOSPI")
    kospi_close = kospi_snap.raw["Close"] if kospi_snap and kospi_snap.raw is not None and "Close" in kospi_snap.raw.columns else None
    leadership_rows = build_watchlist_insights(valid_rows, refresh_token, kospi_close, market_score, regime_output)

    if st.button("현재 관심종목 신호 저장", use_container_width=True):
        saved = 0
        for row in leadership_rows:
            action = row.get("action")
            plan = row.get("risk_plan") or {}
            if not isinstance(action, ActionDecision):
                continue
            record = create_signal_record(
                code=str(row["code"]),
                name=str(row["name"]),
                action=action.action,
                score=action.score,
                confidence=safe_float(action.score) or 50,
                market_regime=regime_output.regime,
                leadership_score=safe_float(row.get("leadership_score")),
                expected_edge=safe_float(action.expected_edge),
                risk_reward_ratio=safe_float(plan.get("rr")),
                position_size_recommendation=safe_float(action.max_position_pct) or 0.0,
                data_quality_score=snapshot_quality_for_stock(str(row["code"]), str(row["name"]), row.get("history", pd.DataFrame())),
                reasons_positive=action.reasons,
                reasons_negative=action.blockers,
                source_snapshot_id=datetime.now().strftime("%Y%m%d%H%M%S"),
            )
            store_signal(SIGNAL_LEDGER_DB, record)
            saved += 1
        st.success(f"{saved}개 신호를 SQLite ledger에 저장했습니다.")

    if st.button("저장 신호 사후성과 업데이트", use_container_width=True):
        updated = 0
        recent = list_recent_signals(SIGNAL_LEDGER_DB, limit=80)
        benchmark_hist = load_symbol_history("KS11", refresh_token, periods=160)
        for raw in recent:
            try:
                generated_at = pd.Timestamp(raw["generated_at"]).normalize()
            except Exception:
                generated_at = pd.Timestamp.today().normalize()
            hist = load_symbol_history(str(raw["code"]), refresh_token, periods=160)
            if hist.empty:
                continue
            after = hist[hist.index >= generated_at]
            if len(after) < 2:
                continue
            name = str(raw.get("name", raw["code"]))
            plan = risk_plan_for_stock(str(raw["code"]), name, hist)
            record = SignalRecord(
                signal_id=str(raw["signal_id"]),
                generated_at=str(raw["generated_at"]),
                code=str(raw["code"]),
                name=name,
                action=str(raw["action"]),
                score=float(raw["score"]),
                confidence=float(raw["confidence"]),
                market_regime=str(raw["market_regime"]),
                leadership_score=safe_float(raw.get("leadership_score")),
                expected_edge=safe_float(raw.get("expected_edge")),
                risk_reward_ratio=safe_float(raw.get("risk_reward_ratio")),
                position_size_recommendation=safe_float(raw.get("position_size_recommendation")) or 0.0,
                data_quality_score=safe_float(raw.get("data_quality_score")),
                reasons_positive=[],
                reasons_negative=[],
                source_snapshot_id=raw.get("source_snapshot_id"),
            )
            for horizon in (1, 5, 20, 60):
                outcome = compute_forward_outcome(
                    record,
                    after,
                    horizon_days=horizon,
                    benchmark_after_signal=benchmark_hist[benchmark_hist.index >= generated_at] if not benchmark_hist.empty else None,
                    target_price=safe_float(plan.get("resistance")),
                    stop_price=safe_float(plan.get("stop")),
                )
                store_outcome(SIGNAL_LEDGER_DB, outcome)
                updated += 1
        st.success(f"{updated}개 사후성과 레코드를 업데이트했습니다.")

    recent = list_recent_signals(SIGNAL_LEDGER_DB, limit=30)
    if not recent:
        st.info("아직 저장된 live signal이 없습니다.")
        return
    display_rows = []
    for raw in recent:
        display_rows.append(
            {
                "시간": raw.get("generated_at"),
                "종목": f"{raw.get('name')} ({raw.get('code')})",
                "판단": action_label_ko(str(raw.get("action"))),
                "점수": raw.get("score"),
                "신뢰도": raw.get("confidence"),
                "국면": regime_label_ko(str(raw.get("market_regime"))),
                "기대값": "N/A" if raw.get("expected_edge") is None else f"{raw.get('expected_edge'):+.2f}%",
                "손익비": "N/A" if raw.get("risk_reward_ratio") is None else f"{raw.get('risk_reward_ratio'):.2f}x",
            }
        )
    st.dataframe(pd.DataFrame(display_rows), hide_index=True, use_container_width=True)


def render_stocks_section(
    snapshot: dict[str, Snapshot],
    valid_rows: list[dict[str, Any]],
    code_to_name: dict[str, str],
    refresh_token: int,
    last_refresh: str,
) -> None:
    st.markdown('<div class="section-title">종목 판단표</div>', unsafe_allow_html=True)
    market_score, _ = market_regime(snapshot)
    regime_output = build_market_regime_output(snapshot)
    kospi_snap = snapshot.get("KOSPI")
    kospi_close = kospi_snap.raw["Close"] if kospi_snap and kospi_snap.raw is not None and "Close" in kospi_snap.raw.columns else None
    leadership_rows = build_watchlist_insights(valid_rows, refresh_token, kospi_close, market_score, regime_output)
    render_watchlist_ranking(leadership_rows)

    if not valid_rows:
        st.info("사이드바에 종목코드를 입력하면 종목 상세가 표시됩니다.")
        return
    options = [row["code"] for row in valid_rows]
    active_code = st.session_state.manual_active_code if st.session_state.manual_active_code in options else options[0]
    selected_code = st.selectbox(
        "종목 상세 선택",
        options=options,
        index=options.index(active_code),
        format_func=lambda code: f"{code} {code_to_name.get(code, STOCK_UNIVERSE_NAME_HINTS.get(code, code))}",
        key="stocks_detail_selector",
    )
    st.session_state.manual_active_code = selected_code
    active_name = code_to_name.get(selected_code, STOCK_UNIVERSE_NAME_HINTS.get(selected_code, selected_code))
    active_hist = load_symbol_history(selected_code, refresh_token, periods=240)
    selected_row = next((row for row in leadership_rows if row["code"] == selected_code), None)
    action = selected_row.get("action") if selected_row and isinstance(selected_row.get("action"), ActionDecision) else None
    plan = risk_plan_for_stock(selected_code, active_name, active_hist)
    target_order_value = max((safe_float(st.session_state.get("portfolio_total_assets")) or 100_000_000.0) * (action.max_position_pct if action else 0.03), 1_000_000.0)
    exec_plan = selected_row.get("execution_plan") if selected_row and selected_row.get("execution_plan") is not None else build_execution_plan(
        active_hist,
        target_order_value=target_order_value,
        expected_edge_pct=action.expected_edge if action else None,
        market_regime=regime_output.regime,
    )
    disc_risk = selected_row.get("disclosure_risk") if selected_row and isinstance(selected_row.get("disclosure_risk"), dict) else {"severity": "Low"}
    exit_plan = build_exit_plan(
        plan,
        active_hist,
        leadership_score=safe_float(selected_row.get("leadership_score")) if selected_row else None,
        market_regime=regime_output.regime,
        catalyst_risk=str(disc_risk.get("severity", "Low")),
    )
    cols = st.columns([1, 1])
    with cols[0]:
        render_risk_plan(selected_code, code_to_name, refresh_token, action)
    with cols[1]:
        if action:
            reason_html = "".join(f"<div>{idx}. {html.escape(reason)}</div>" for idx, reason in enumerate(action.reasons + action.blockers, 1))
            st.html(
                f"""
                <div class="insight-panel">
                    <div class="insight-head">
                        <div>
                            <div class="insight-kicker">투자 판단</div>
                            <div class="insight-title">{html.escape(active_name)}</div>
                        </div>
                        <div class="insight-badge" style="background:{'#dc2626' if action.score >= 65 else '#2563eb' if action.score < 45 else '#64748b'};">{html.escape(action_label_ko(action.action))} / {action.score}점</div>
                    </div>
                    {reason_html}
                    <div class="thesis">무효화 조건: 손절 기준 {format_price(plan.get('stop'))} 이탈 또는 공시 리스크 High 이상 발생.</div>
                </div>
                """
            )
    trade_cols = st.columns([1, 1])
    with trade_cols[0]:
        render_execution_card(exec_plan, action.expected_edge if action else None)
    with trade_cols[1]:
        render_exit_plan_card(exit_plan)
    if active_hist.empty:
        st.warning("선택한 종목의 가격 데이터를 가져오지 못했습니다.")
    else:
        st.pyplot(plot_candlestick_with_volume(active_hist, f"{active_name} ({selected_code})"), clear_figure=True)
    st.caption(f"마지막 조회 시각: {last_refresh}")


def render_dashboard_section(
    snapshot: dict[str, Snapshot],
    valid_rows: list[dict[str, Any]],
    code_to_name: dict[str, str],
    ref_date: str,
    last_refresh: str,
    refresh_token: int,
) -> None:
    st.markdown(f"**기준일:** `{ref_date}`  |  **마지막 조회:** `{last_refresh}`")

    metric_specs = [
        ("KOSPI", "코스피", "현재 지수"),
        ("KOSDAQ", "코스닥", "현재 지수"),
        ("USD/KRW", "USD/KRW", "원·달러 환율"),
        ("US 10Y", "미국 국채 10년물", "금리"),
        ("KR 3Y", "한국 국고채 3년물", "금리"),
    ]
    cols = st.columns(5)
    for col, (key, title, subtitle) in zip(cols, metric_specs):
        with col:
            render_card(title, snapshot.get(key, Snapshot(key, title, None, None, None, None, None, None)), subtitle)

    market_score, market_notes = market_regime(snapshot)
    regime_output = build_market_regime_output(snapshot)
    render_action_console(regime_output)
    kospi_snap = snapshot.get("KOSPI")
    kospi_close = kospi_snap.raw["Close"] if kospi_snap and kospi_snap.raw is not None and "Close" in kospi_snap.raw.columns else None
    leadership_rows = render_investment_insight_panels(snapshot, valid_rows, code_to_name, refresh_token, market_score, kospi_close, regime_output)
    leadership_map = {row["code"]: row for row in leadership_rows}
    render_dashboard_extension_summary(snapshot, valid_rows, code_to_name, refresh_token, regime_output)

    fg_snap = snapshot.get("FNG", Snapshot("FNG", "Fear and Greed", None, None, None, None, None, None))
    fg_score = safe_float(fg_snap.last_close)
    fg_label, fg_color, fg_advice = fear_greed_zone(fg_score)
    fg_score_text = "N/A" if fg_score is None else f"{fg_score:.0f}"

    st.markdown('<div class="section-title">공포·탐욕 지수</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="small-note">0에 가까울수록 공포, 100에 가까울수록 탐욕입니다. 극단 구간에서는 추세 추종보다 리스크 관리가 우선입니다.</div>',
        unsafe_allow_html=True,
    )
    fg_cols = st.columns([1.35, 1])
    with fg_cols[0]:
        st.pyplot(plot_fear_greed_bar(fg_score, fg_label, fg_color), clear_figure=True)
    with fg_cols[1]:
        position_text = (
            '분할매수와 방어적 대응' if fg_score is not None and fg_score <= 44 else
            '중립 유지와 선택적 매수' if fg_score is not None and fg_score <= 55 else
            '분할익절과 종목 선별'
        )
        st.markdown(
            f"""
            <div class="signal-box" style="height: 100%; display:flex; flex-direction:column; justify-content:center;">
                <div class="section-title" style="margin-top:0;">시장 심리</div>
                <div style="font-size:1.5rem; font-weight:900; color:{fg_color}; margin-bottom:6px;">{fg_label}</div>
                <div style="font-size:1.1rem; font-weight:800; margin-bottom:8px;">{fg_score_text}</div>
                <div class="small-note" style="font-size:0.92rem; line-height:1.55;">
                    {fg_advice}<br/>
                    {fg_advice}<br/>
                    이 구간에서는 <b>{position_text}</b>이 유리합니다.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    render_ecos_cards(refresh_token)

    st.markdown('<div class="section-title">주요 종목 카드</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="small-note">아래 카드를 클릭하면 상세 차트가 즉시 바뀝니다. 당일 수익률과 추세를 함께 보고 종목을 고르세요.</div>',
        unsafe_allow_html=True,
    )
    preview_rows = valid_rows[:15]
    for row_idx in range(0, len(preview_rows), 5):
        cols_preview = st.columns(min(5, len(preview_rows) - row_idx))
        for col, row in zip(cols_preview, preview_rows[row_idx : row_idx + 5]):
            with col:
                snap = snapshot.get(row["code"], Snapshot(row["code"], row["name"], None, None, None, None, None, None))
                if render_stock_preview(row["name"], row["code"], snap, f"btn_preview_{row['code']}", leadership_map.get(row["code"])):
                    st.session_state.manual_active_code = row["code"]
                    st.session_state.active_code = row["code"]
                    st.rerun()

    st.markdown('<div class="section-title">종목 당일 수익률 비교</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="small-note">현재 선택 종목과 비교해서 어떤 종목이 더 강한지 한눈에 보이도록 배치했습니다. 막대 클릭 대신 카드 클릭과 드롭다운을 함께 사용하세요.</div>',
        unsafe_allow_html=True,
    )

    rows: list[dict[str, Any]] = []
    codes_in_order = [row["code"] for row in valid_rows]
    names_in_order = [row["name"] for row in valid_rows]
    for code, name in zip(codes_in_order, names_in_order):
        hist = load_symbol_history(code, refresh_token, periods=80)
        if hist.empty:
            continue
        _, _, _, close_c, _ = find_ohlcv_columns(hist)
        close = hist[close_c].dropna()
        if len(close) < 2:
            continue
        latest_ret = (float(close.iloc[-1]) / float(close.iloc[-2]) - 1) * 100
        rows.append({"code": code, "name": name, "return_pct": latest_ret, "history": hist})

    active_code = st.session_state.manual_active_code if st.session_state.manual_active_code in codes_in_order else (rows[0]["code"] if rows else None)
    if active_code is not None and active_code not in codes_in_order and codes_in_order:
        active_code = codes_in_order[0]
    if active_code is not None:
        st.session_state.active_code = active_code

    fig_returns, _ = build_return_figure(rows, active_code)
    st.pyplot(fig_returns, clear_figure=True)

    selected_symbol = st.selectbox(
        "상세 차트 종목 선택",
        options=[row["code"] for row in rows] if rows else codes_in_order,
        index=([row["code"] for row in rows].index(active_code) if rows and active_code in [row["code"] for row in rows] else 0),
        format_func=lambda code: f"{code} {code_to_name.get(code, STOCK_UNIVERSE_NAME_HINTS.get(code, code))}",
        key="detail_selector",
    )
    st.session_state.manual_active_code = selected_symbol
    st.session_state.active_code = selected_symbol

    st.markdown('<div class="section-title">오늘의 메탈 코치</div>', unsafe_allow_html=True)

    if active_code is None:
        st.info("상세 차트를 표시할 종목이 없습니다.")
        st.stop()

    active_name = code_to_name.get(active_code, STOCK_UNIVERSE_NAME_HINTS.get(active_code, active_code))
    active_hist = load_symbol_history(active_code, refresh_token, periods=240)
    signal, stock_score, reasons, volatility_flag = summarize_stock(active_code, active_name, active_hist, kospi_close, market_score)

    render_signal_box(active_name, signal, stock_score, reasons)

    coach = coach_message(market_score, signal, stock_score, volatility_flag)
    st.info(coach)
    if market_notes:
        st.caption("시장 해석: " + " / ".join(market_notes[:3]))

    st.markdown('<div class="section-title">최근 60거래일 캔들 + 거래량</div>', unsafe_allow_html=True)
    if active_hist.empty:
        st.warning("선택한 종목의 가격 데이터를 가져오지 못했습니다.")
    else:
        fig_candle = plot_candlestick_with_volume(active_hist, f"{active_name} ({active_code})")
        st.pyplot(fig_candle, clear_figure=True)

        _, _, _, close_c, volume_c = find_ohlcv_columns(active_hist)
        close = active_hist[close_c].dropna()
        volume = active_hist[volume_c].dropna() if volume_c in active_hist.columns else pd.Series(dtype=float)
        r = calc_returns(close)
        latest_close = safe_float(close.iloc[-1]) if not close.empty else None
        latest_volume = safe_float(volume.iloc[-1]) if not volume.empty else None
        avg_volume_20 = safe_float(volume.tail(20).mean()) if not volume.empty else None
        vol_ratio = None if latest_volume is None or avg_volume_20 in (None, 0) else latest_volume / avg_volume_20

        summary_cols = st.columns(4)
        with summary_cols[0]:
            st.metric("최근 종가", format_price(latest_close))
        with summary_cols[1]:
            st.metric("5일 수익률", format_pct(r["5d"]))
        with summary_cols[2]:
            st.metric("20일 수익률", format_pct(r["20d"]))
        with summary_cols[3]:
            st.metric("거래량 비율", "N/A" if vol_ratio is None else f"{vol_ratio:.2f}x")

    st.markdown("---")
    st.markdown("**출처: FinanceDataReader**")
    st.caption(f"마지막 조회 시각: {last_refresh}")
    render_data_quality_banner(snapshot, valid_rows)

def render_disclosure_section(
    valid_rows: list[dict[str, Any]],
    code_to_name: dict[str, str],
    refresh_token: int,
    last_refresh: str,
) -> None:
    st.markdown('<div class="section-title">공시정보</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="small-note">DART 최근공시를 불러와 관심 종목 중심으로 보여주고, 각 공시에 호재 / 중립 / 악재 라벨을 자동으로 붙입니다.</div>',
        unsafe_allow_html=True,
    )

    dart_df = load_recent_disclosures(refresh_token, DART_API_TOKEN)
    if dart_df.empty:
        st.warning("공시 정보를 불러오지 못했습니다.")
        st.caption(f"마지막 조회 시각: {last_refresh}")
        return

    watch_names = {row["name"] for row in valid_rows}
    watch_codes = {row["code"] for row in valid_rows}
    with st.form("disclosure_search_form", clear_on_submit=False):
        filter_watchlist = st.checkbox("관심 종목만 보기", value=True, key="disclosure_watchlist_only")
        query = st.text_input(
            "회사명 또는 보고서명 검색",
            placeholder="예: 삼성전자, 자기주식, 증권신고서",
            key="disclosure_query",
        )
        limit = st.slider("표시 개수", min_value=5, max_value=40, value=15, step=5, key="disclosure_limit")
        search_submit = st.form_submit_button("검색")

    if "disclosure_query_applied" not in st.session_state:
        st.session_state.disclosure_query_applied = ""

    if search_submit:
        st.session_state.disclosure_query_applied = query.strip()
    applied_query = st.session_state.disclosure_query_applied
    applied_watchlist = filter_watchlist

    filtered = dart_df.copy()
    if applied_watchlist:
        name_mask = filtered["corp_name"].isin(watch_names)
        code_mask = filtered["stock_code"].isin(watch_codes) if "stock_code" in filtered.columns else False
        filtered = filtered[name_mask | code_mask]
    if applied_query:
        q = applied_query.strip()
        mask = (
            filtered["corp_name"].str.contains(q, case=False, na=False)
            | filtered["report_name"].str.contains(q, case=False, na=False)
            | filtered["submitter"].str.contains(q, case=False, na=False)
            | filtered["note"].str.contains(q, case=False, na=False)
            | filtered["stock_code"].str.contains(q, case=False, na=False)
        )
        filtered = filtered[mask]
        if filtered.empty and applied_watchlist:
            fallback_mask = (
                dart_df["corp_name"].str.contains(q, case=False, na=False)
                | dart_df["report_name"].str.contains(q, case=False, na=False)
                | dart_df["submitter"].str.contains(q, case=False, na=False)
                | dart_df["note"].str.contains(q, case=False, na=False)
                | dart_df["stock_code"].str.contains(q, case=False, na=False)
            )
            fallback = dart_df[fallback_mask].copy()
            if not fallback.empty:
                filtered = fallback
                st.info("관심 종목 필터에서 결과가 없어 전체 DART 공시에서 다시 검색했습니다.")

    summary_cols = st.columns(4)
    with summary_cols[0]:
        st.metric("전체 공시", f"{len(dart_df):,}")
    with summary_cols[1]:
        st.metric("표시 중", f"{len(filtered):,}")
    with summary_cols[2]:
        st.metric("관심 종목", f"{len(watch_names):,}")
    with summary_cols[3]:
        st.metric("분석 상태", "자동 분류")
    st.caption(f"DART API 상태: {'연결됨' if DART_API_KEY else '미설정'}")

    st.caption(f"마지막 조회 시각: {last_refresh}")
    if applied_query:
        st.caption(f"검색어 적용됨: {applied_query}")
    if filtered.empty:
        st.info("조건에 맞는 공시가 없습니다.")
        return

    display_df = filtered.head(limit).copy()
    display_df[["label", "label_reason", "label_score"]] = display_df["report_name"].apply(
        lambda value: pd.Series(classify_disclosure(value))
    )

    st.markdown(
        """
        <style>
            .disclosure-card {
                background: rgba(255, 255, 255, 0.96);
                border: 1px solid rgba(148, 163, 184, 0.28);
                border-radius: 16px;
                padding: 14px 16px;
                margin-bottom: 12px;
                color: #0f172a !important;
                box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
            }
            .disclosure-card * {
                color: inherit;
            }
            .disclosure-title {
                font-weight: 800;
                font-size: 1.02rem;
                margin: 2px 0 6px 0;
                color: #0f172a !important;
            }
            .disclosure-company {
                font-weight: 800;
                color: #111827 !important;
            }
            .disclosure-meta {
                color: #475569 !important;
                font-size: 0.86rem;
                margin-top: 4px;
            }
            .disclosure-card a {
                color: #1d4ed8 !important;
                font-weight: 700;
                text-decoration: none;
            }
            .disclosure-card a:hover {
                text-decoration: underline;
            }
            .badge {
                display: inline-block;
                padding: 3px 10px;
                border-radius: 999px;
                font-size: 0.78rem;
                font-weight: 800;
                margin-right: 6px;
            }
            .badge-good { background: rgba(220, 38, 38, 0.12); color: #b91c1c; }
            .badge-mid { background: rgba(100, 116, 139, 0.12); color: #475569; }
            .badge-bad { background: rgba(37, 99, 235, 0.12); color: #1d4ed8; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    for _, row in display_df.iterrows():
        badge_class = {
            "호재": "badge-good",
            "중립": "badge-mid",
            "악재": "badge-bad",
        }.get(row["label"], "badge-mid")

        st.markdown(
            f"""
            <div class="disclosure-card">
                <div>
                    <span class="badge {badge_class}">{row['label']} · 점수 {int(row['label_score']):+d}</span>
                    <span class="disclosure-company">{row['corp_name']}</span>
                </div>
                <div class="disclosure-title">{row['report_name']}</div>
                <div class="disclosure-meta">{row['date']} {row['time']} · 제출인: {row['submitter']}{f" · {row['note']}" if row['note'] else ""}</div>
                <div class="disclosure-meta">분류 근거: {row['label_reason']}</div>
                {f'<div style="margin-top:8px;"><a href="{row["report_url"]}" target="_blank" rel="noopener noreferrer">원문 보기</a></div>' if row["report_url"] else ""}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_disclosure_section(
    valid_rows: list[dict[str, Any]],
    code_to_name: dict[str, str],
    refresh_token: int,
    last_refresh: str,
) -> None:
    st.markdown('<div class="section-title">공시정보</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="small-note">DART API로 공시를 가져와 관심 종목 중심으로 보여주고, 각 공시에 호재 / 중립 / 악재 라벨을 자동으로 붙입니다.</div>',
        unsafe_allow_html=True,
    )

    dart_df = load_recent_disclosures(refresh_token, DART_API_TOKEN)
    watch_names = {row["name"] for row in valid_rows}
    watch_codes = {row["code"] for row in valid_rows}

    if "disclosure_query_applied" not in st.session_state:
        st.session_state.disclosure_query_applied = ""

    with st.form("disclosure_search_form", clear_on_submit=False):
        filter_watchlist = st.checkbox("관심 종목만 보기", value=True, key="disclosure_watchlist_only")
        query = st.text_input(
            "회사명 또는 보고서명 검색",
            placeholder="예: 삼성전자, 자기주식, 증권신고서",
            key="disclosure_query",
        )
        limit = st.slider("표시 개수", min_value=5, max_value=40, value=15, step=5, key="disclosure_limit")
        search_submit = st.form_submit_button("검색")

    if search_submit:
        st.session_state.disclosure_query_applied = query.strip()

    applied_query = st.session_state.disclosure_query_applied.strip()
    applied_watchlist = filter_watchlist

    summary_cols = st.columns(4)
    with summary_cols[0]:
        st.metric("전체 공시", f"{len(dart_df):,}")

    filtered = dart_df.copy()
    if applied_watchlist and not filtered.empty:
        name_mask = filtered["corp_name"].isin(watch_names)
        code_mask = filtered["stock_code"].isin(watch_codes) if "stock_code" in filtered.columns else False
        filtered = filtered[name_mask | code_mask]

    if applied_query and not filtered.empty:
        q = applied_query
        search_mask = (
            filtered["corp_name"].str.contains(q, case=False, na=False)
            | filtered["report_name"].str.contains(q, case=False, na=False)
            | filtered["submitter"].str.contains(q, case=False, na=False)
            | filtered["note"].str.contains(q, case=False, na=False)
            | filtered["stock_code"].str.contains(q, case=False, na=False)
        )
        filtered = filtered[search_mask]
        if filtered.empty and applied_watchlist:
            fallback_mask = (
                dart_df["corp_name"].str.contains(q, case=False, na=False)
                | dart_df["report_name"].str.contains(q, case=False, na=False)
                | dart_df["submitter"].str.contains(q, case=False, na=False)
                | dart_df["note"].str.contains(q, case=False, na=False)
                | dart_df["stock_code"].str.contains(q, case=False, na=False)
            )
            fallback = dart_df[fallback_mask].copy()
            if not fallback.empty:
                filtered = fallback
                st.info("관심 종목 필터에서 결과가 없어 전체 DART 공시에서 다시 검색했습니다.")

    with summary_cols[1]:
        st.metric("표시 중", f"{len(filtered):,}")
    with summary_cols[2]:
        st.metric("관심 종목", f"{len(watch_names):,}")
    with summary_cols[3]:
        st.metric("분석 상태", "자동 분류")

    api_state = "YOUR_API_KEY" if DART_API_KEY == "YOUR_API_KEY" else "연결됨"
    st.caption(f"DART API 상태: {api_state}")
    st.caption(f"마지막 조회 시각: {last_refresh}")
    if applied_query:
        st.caption(f"검색어 적용됨: {applied_query}")

    if dart_df.empty:
        st.info("오늘 공시가 없습니다.")
        return

    if filtered.empty:
        if applied_query or not applied_watchlist:
            st.info("조건에 맞는 공시가 없습니다.")
        else:
            st.info("오늘 공시가 없습니다.")
        return

    display_df = filtered.head(limit).copy()
    display_df[["label", "label_reason", "label_score"]] = display_df["report_name"].apply(
        lambda value: pd.Series(classify_disclosure(value))
    )

    st.markdown(
        """
        <style>
            .disclosure-card {
                background: rgba(255, 255, 255, 0.96);
                border: 1px solid rgba(148, 163, 184, 0.28);
                border-radius: 16px;
                padding: 14px 16px;
                margin-bottom: 12px;
                color: #0f172a !important;
                box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
            }
            .disclosure-card * { color: inherit; }
            .disclosure-title {
                font-weight: 800;
                font-size: 1.02rem;
                margin: 2px 0 6px 0;
                color: #0f172a !important;
            }
            .disclosure-company {
                font-weight: 800;
                color: #111827 !important;
            }
            .disclosure-meta {
                color: #475569 !important;
                font-size: 0.86rem;
                margin-top: 4px;
            }
            .disclosure-card a {
                color: #1d4ed8 !important;
                font-weight: 700;
                text-decoration: none;
            }
            .disclosure-card a:hover { text-decoration: underline; }
            .badge {
                display: inline-block;
                padding: 3px 10px;
                border-radius: 999px;
                font-size: 0.78rem;
                font-weight: 800;
                margin-right: 6px;
            }
            .badge-good { background: rgba(220, 38, 38, 0.12); color: #b91c1c; }
            .badge-mid { background: rgba(100, 116, 139, 0.12); color: #475569; }
            .badge-bad { background: rgba(37, 99, 235, 0.12); color: #1d4ed8; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    for _, row in display_df.iterrows():
        badge_class = {"호재": "badge-good", "중립": "badge-mid", "악재": "badge-bad"}.get(row["label"], "badge-mid")
        report_url = row["report_url"]
        report_link = f'<div style="margin-top:8px;"><a href="{report_url}" target="_blank" rel="noopener noreferrer">원문 보기</a></div>' if report_url else ""
        note_text = f" · {row['note']}" if row["note"] else ""
        st.markdown(
            f"""
            <div class="disclosure-card">
                <div>
                    <span class="badge {badge_class}">{row['label']} · 점수 {int(row['label_score']):+d}</span>
                    <span class="disclosure-company">{row['corp_name']}</span>
                </div>
                <div class="disclosure-title">{row['report_name']}</div>
                <div class="disclosure-meta">{row['date']} {row['time']} · 제출인: {row['submitter']}{note_text}</div>
                <div class="disclosure-meta">분류 근거: {row['label_reason']}</div>
                {report_link}
            </div>
            """,
            unsafe_allow_html=True,
        )


def stock_signal(
    code: str,
    history: pd.DataFrame,
    market_score: float,
    kospi_close: pd.Series | None,
) -> tuple[str, float, list[str]]:
    if history is None or history.empty:
        return "중립", 50.0, ["데이터가 부족해 중립"]

    _, _, _, close_col, volume_col = find_ohlcv_columns(history)
    close = history[close_col].dropna()
    volume = history[volume_col].dropna() if volume_col in history.columns else pd.Series(dtype=float)
    ret = calc_returns(close)

    if len(close) < 10:
        return "중립", 50.0, ["추세를 판단하기에 데이터가 부족합니다"]

    score = 50.0
    reasons: list[str] = []

    def add(value: float | None, weight: float, cap: float, label: str) -> None:
        nonlocal score
        if value is None:
            return
        clipped = max(min(value, cap), -cap)
        score += clipped / cap * weight
        direction = "우호" if value >= 0 else "비우호"
        reasons.append(f"{label} {direction}({value:+.2f}%)")

    def log_trend_slope(window: int) -> float | None:
        if len(close) < window:
            return None
        segment = np.log(close.tail(window).astype(float).values)
        x = np.arange(len(segment), dtype=float)
        slope = float(np.polyfit(x, segment, 1)[0])
        return slope * 100.0

    def gap_vs_ma(window: int) -> float | None:
        if len(close) < window:
            return None
        ma = float(close.tail(window).mean())
        if ma == 0:
            return None
        last = float(close.iloc[-1])
        return (last / ma - 1) * 100

    add(ret["5d"], 7.0, 18.0, "5일 추세")
    add(ret["20d"], 12.0, 25.0, "20일 추세")
    add(ret["60d"], 10.0, 35.0, "60일 추세")
    add(log_trend_slope(10), 6.0, 1.2, "10일 기울기")
    add(log_trend_slope(20), 6.0, 1.0, "20일 기울기")
    add(log_trend_slope(60), 4.0, 0.8, "60일 기울기")

    gap5 = gap_vs_ma(5)
    gap20 = gap_vs_ma(20)
    gap60 = gap_vs_ma(60)
    if gap5 is not None:
        score += max(min(gap5, 6.0), -6.0) / 6.0 * 3.0
        reasons.append(f"5일선 대비 {gap5:+.2f}%")
    if gap20 is not None:
        score += max(min(gap20, 10.0), -10.0) / 10.0 * 5.0
        reasons.append(f"20일선 대비 {gap20:+.2f}%")
    if gap60 is not None:
        score += max(min(gap60, 15.0), -15.0) / 15.0 * 4.0
        reasons.append(f"60일선 대비 {gap60:+.2f}%")

    if volume is not None and len(volume) >= 20:
        avg20 = float(volume.tail(20).mean())
        latest_vol = float(volume.iloc[-1])
        if avg20 > 0:
            vol_ratio = latest_vol / avg20
            if vol_ratio >= 1.5:
                score += 5.0
                reasons.append(f"거래량 강세({vol_ratio:.2f}x)")
            elif vol_ratio >= 1.1:
                score += 2.5
                reasons.append(f"거래량 확인({vol_ratio:.2f}x)")
            elif vol_ratio <= 0.75:
                score -= 3.0
                reasons.append(f"거래량 둔화({vol_ratio:.2f}x)")

    if kospi_close is not None and len(close) >= 21 and len(kospi_close) >= 21:
        rs = relative_strength(close, kospi_close)
        if rs is not None:
            rs_clipped = max(min(rs, 15.0), -15.0)
            score += rs_clipped / 15.0 * 12.0
            reasons.append(f"코스피 대비 상대강도 {rs:+.2f}%p")

    if len(close) >= 20:
        recent = close.tail(20)
        vol_ann = float(recent.pct_change().dropna().std() * math.sqrt(252) * 100)
        if vol_ann >= 90:
            score -= 6.0
            reasons.append(f"변동성 과열({vol_ann:.1f}%)")
        elif vol_ann <= 30:
            score += 2.5
            reasons.append(f"변동성 안정({vol_ann:.1f}%)")

        if len(recent) >= 2 and float(recent.iloc[-2]) != 0:
            one_day = float(recent.iloc[-1] / recent.iloc[-2] - 1) * 100
            if one_day > 6:
                score -= 2.0
                reasons.append(f"단기 과열({one_day:+.2f}%)")
            elif one_day < -6:
                score -= 1.0
                reasons.append(f"급락 충격({one_day:+.2f}%)")

    score += market_score * 2.5
    if market_score > 0.75:
        reasons.append("시장 레짐 우호")
    elif market_score < -0.75:
        reasons.append("시장 레짐 비우호")

    if gap20 is not None and gap20 > 8 and ret["5d"] is not None and ret["5d"] < 0:
        score -= 4.0
        reasons.append("상승 후 되돌림 경계")

    if ret["20d"] is not None and ret["60d"] is not None and ret["20d"] > 0 and ret["60d"] > 0:
        score += 2.0
        reasons.append("추세 일관성 양호")
    elif ret["20d"] is not None and ret["60d"] is not None and ret["20d"] < 0 and ret["60d"] < 0:
        score -= 2.5
        reasons.append("하락 추세 일관성")

    score = float(max(0.0, min(100.0, score)))
    if score >= 68:
        label = "매수"
    elif score <= 32:
        label = "매도"
    else:
        label = "중립"
    return label, score, reasons[:8]


def coach_message(market_score: float, signal: str, stock_score: float, volatility_flag: str) -> str:
    if stock_score >= 68 and market_score >= 0:
        return "승률 우위 구간입니다. 추격보다 분할 진입이 유리하고, 비중은 1차/2차로 나눠서 관리하세요."
    if stock_score >= 68 and market_score < 0:
        return "종목은 강하지만 시장이 받쳐주지 않습니다. 작은 비중의 분할만 허용하고 손절 규칙을 더 엄격하게 두세요."
    if stock_score <= 32:
        return "우위가 약합니다. 오늘은 현금 비중을 지키고, 반등 확인 전까지는 기다리는 쪽이 승률이 높습니다."
    if volatility_flag == "high":
        return "변동성이 과합니다. 맞추려 하지 말고, 진입은 늦추고 비중은 줄이세요."
    if market_score <= -1.0:
        return "시장 레짐이 좋지 않습니다. 보수적으로 보고, 새로운 포지션은 최소화하세요."
    return "시그널은 중립입니다. 방향성 확인 전까지는 관망이 가장 좋은 포지션입니다."


def summarize_stock(code: str, name: str, history: pd.DataFrame, kospi_close: pd.Series | None, market_score: float) -> tuple[str, float, list[str], str]:
    if history.empty:
        return "중립", 50.0, ["데이터가 부족합니다"], "low"
    _, _, _, close_c, volume_c = find_ohlcv_columns(history)
    close = history[close_c].dropna()
    vol = history[volume_c].dropna() if volume_c in history.columns else pd.Series(dtype=float)
    signal, score, reasons = stock_signal(code, history, market_score, kospi_close)
    volatility_flag = "low"
    if len(close) >= 20:
        ret20 = close.pct_change().dropna().tail(20)
        vol_ann = float(ret20.std() * math.sqrt(252) * 100) if not ret20.empty else 0.0
        volatility_flag = "high" if vol_ann >= 80 else "low"
        reasons.append(f"연환산 변동성 {vol_ann:.1f}%")
    if len(vol) >= 20:
        ratio = float(vol.iloc[-1] / vol.tail(20).mean())
        reasons.append(f"거래량 비중 {ratio:.2f}x")
    return signal, score, reasons, volatility_flag


def main() -> None:
    st.markdown('<div class="hero-title">세계 수준의 금융 대시보드</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">코스피, 코스닥, 환율, 금리, 관심 종목을 한 화면에서 보고 오늘의 매수/중립/매도 판단과 행동 원칙까지 바로 확인합니다.</div>',
        unsafe_allow_html=True,
    )

    if fdr is None:
        st.error(
            "FinanceDataReader를 불러오지 못했습니다. 로컬 환경에 `FinanceDataReader`와 `streamlit`를 설치한 뒤 실행해주세요."
        )
        st.stop()

    if "refresh_token" not in st.session_state:
        st.session_state.refresh_token = 0
    if "active_code" not in st.session_state:
        st.session_state.active_code = DEFAULT_CODES[0]
    if "manual_active_code" not in st.session_state:
        st.session_state.manual_active_code = DEFAULT_CODES[0]
    if "sidebar_codes_text" not in st.session_state:
        st.session_state.sidebar_codes_text = "\n".join(DEFAULT_CODES)
    if "pending_sidebar_codes_text" in st.session_state:
        st.session_state.sidebar_codes_text = st.session_state.pending_sidebar_codes_text
        del st.session_state.pending_sidebar_codes_text
    if "discovery_scan_requested" not in st.session_state:
        st.session_state.discovery_scan_requested = False

    with st.sidebar:
        st.header("종목 입력")
        st.caption("쉼표 또는 줄바꿈으로 종목코드를 입력하세요. 최대 15개까지 지원합니다.")
        if "pending_sidebar_message" in st.session_state:
            st.success(st.session_state.pending_sidebar_message)
            del st.session_state.pending_sidebar_message
        code_text = st.text_area("종목 코드", key="sidebar_codes_text", height=220)

        st.header("포트폴리오")
        st.session_state.portfolio_total_assets = st.number_input(
            "총자산",
            min_value=0.0,
            value=float(st.session_state.get("portfolio_total_assets", 100_000_000.0)),
            step=1_000_000.0,
            format="%.0f",
        )
        st.session_state.portfolio_cash = st.number_input(
            "현금",
            min_value=0.0,
            value=float(st.session_state.get("portfolio_cash", 50_000_000.0)),
            step=1_000_000.0,
            format="%.0f",
        )
        st.session_state.portfolio_holdings_text = st.text_area(
            "보유종목 CSV",
            value=str(st.session_state.get("portfolio_holdings_text", "")),
            height=120,
            placeholder="code,qty,avg_price,sector\n005930,10,75000,반도체",
        )

        with st.expander("리스크/비용 설정"):
            RISK_DEFAULTS["risk_per_trade_pct"] = st.slider("1회 거래 최대 손실(%)", 0.05, 2.0, float(RISK_DEFAULTS["risk_per_trade_pct"] * 100), 0.05) / 100
            RISK_DEFAULTS["max_position_pct"] = st.slider("단일 종목 최대 비중(%)", 1.0, 30.0, float(RISK_DEFAULTS["max_position_pct"] * 100), 0.5) / 100
            RISK_DEFAULTS["trading_cost_pct"] = st.slider("왕복 거래비용/세금(%)", 0.0, 2.0, float(RISK_DEFAULTS["trading_cost_pct"]), 0.05)
            RISK_DEFAULTS["slippage_pct"] = st.slider("슬리피지(%)", 0.0, 2.0, float(RISK_DEFAULTS["slippage_pct"]), 0.05)

        refresh_clicked = st.button("데이터 새로고침", use_container_width=True)
        if refresh_clicked:
            st.session_state.refresh_token += 1
            st.rerun()

    codes, invalid_tokens = parse_code_input(code_text)
    if len(codes) > 15:
        st.warning("종목은 최대 15개까지만 보여줍니다. 앞의 15개만 사용합니다.")
        codes = codes[:15]

    listing = load_listing_cache(st.session_state.refresh_token)
    code_to_name = dict(zip(listing.get("Code", pd.Series(dtype=str)), listing.get("Name", pd.Series(dtype=str))))

    valid_rows: list[dict[str, Any]] = []
    invalid_codes: list[str] = []
    for code in codes:
        if code in code_to_name:
            valid_rows.append({"code": code, "name": str(code_to_name.get(code, code))})
        elif code in STOCK_UNIVERSE_NAME_HINTS:
            valid_rows.append({"code": code, "name": STOCK_UNIVERSE_NAME_HINTS[code]})
        else:
            invalid_codes.append(code)

    if invalid_tokens:
        st.warning(f"형식이 맞지 않는 입력은 제외했습니다: {', '.join(invalid_tokens)}")
    if invalid_codes:
        st.warning(f"KRX에서 찾지 못한 코드가 있습니다: {', '.join(invalid_codes)}")
    if not valid_rows:
        st.info("사이드바에 유효한 종목코드를 입력하면 차트가 표시됩니다.")
        valid_rows = [{"code": code, "name": STOCK_UNIVERSE_NAME_HINTS.get(code, code)} for code in DEFAULT_CODES[:5]]

    watch_codes = tuple(row["code"] for row in valid_rows)
    snapshot = load_market_snapshot(st.session_state.refresh_token, watch_codes)
    ref_date_candidates = [snap.asof for snap in snapshot.values() if snap.asof is not None]
    ref_date = max(ref_date_candidates).strftime("%Y-%m-%d") if ref_date_candidates else datetime.now().strftime("%Y-%m-%d")
    last_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tabs = st.tabs(["Dashboard", "Portfolio", "Stocks", "Alpha Discovery", "Disclosures", "Macro", "Briefing", "Signal Outcome", "Settings"])
    with tabs[0]:
        render_dashboard_section(snapshot, valid_rows, code_to_name, ref_date, last_refresh, st.session_state.refresh_token)
    with tabs[1]:
        render_portfolio_section(snapshot, code_to_name, st.session_state.refresh_token, last_refresh)
    with tabs[2]:
        render_stocks_section(snapshot, valid_rows, code_to_name, st.session_state.refresh_token, last_refresh)
    with tabs[3]:
        render_alpha_discovery_section(st.session_state.refresh_token)
    with tabs[4]:
        render_disclosure_section(valid_rows, code_to_name, st.session_state.refresh_token, last_refresh)
    with tabs[5]:
        render_ecos_cards(st.session_state.refresh_token)
    with tabs[6]:
        render_gpt_briefing_section(snapshot, valid_rows, code_to_name, ref_date, last_refresh, st.session_state.refresh_token)
    with tabs[7]:
        render_signal_outcome_section(snapshot, valid_rows, code_to_name, st.session_state.refresh_token)
    with tabs[8]:
        render_settings_section()


if __name__ == "__main__":
    main()
