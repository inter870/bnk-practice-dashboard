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
from src.portfolio import (
    calculateAllocationDrift,
    calculateAnnualizedVolatility,
    calculateBenchmarkRelativeReturn,
    calculateBeta,
    calculateCAGR,
    calculateConcentrationRisk,
    calculateDrawdownSeries,
    calculateMaxDrawdown,
    calculatePeriodReturns,
    calculateSharpeRatio,
    format_currency as portfolio_format_currency,
    format_percent as portfolio_format_percent,
    generatePortfolioInsightSummary,
    generateRebalanceSuggestions,
    generateWatchlistSignals,
    getBenchmarkSeries,
    getHoldings,
    getPortfolioSnapshots,
    getPortfolioSummary,
    getWatchlist,
)
from src.korea_equity import (
    KoreaMarketStatus,
    candleSummaryText as korea_candle_summary_text,
    fearGreedBand as korea_fear_greed_band,
    formatConfidence as korea_format_confidence,
    formatKRW as korea_format_krw,
    formatMarketLabel as korea_format_market_label,
    formatPercent as korea_format_percent,
    formatRecommendationGrade as korea_format_grade,
    formatScore as korea_format_score,
    formatTradingValue as korea_format_trading_value,
    formatVolume as korea_format_volume,
    getKoreaDashboardData,
    getKoreaPriceHistory,
    getKoreaSupplyDemand,
    heatmapBucket as korea_heatmap_bucket,
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


def load_env_file(env_path: str = ".env") -> dict[str, str]:
    path = os.path.join(os.path.dirname(__file__), env_path)
    if not os.path.exists(path):
        return {}

    values: dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value:
                    values[key] = value
                    os.environ[key] = value
    except Exception:
        return values
    return values


ENV_FILE_VALUES = load_env_file()


def config_value(key: str, default: str = "") -> str:
    file_value = ENV_FILE_VALUES.get(key)
    if file_value not in (None, ""):
        return str(file_value).strip()
    env_value = os.getenv(key)
    if env_value not in (None, ""):
        return str(env_value).strip()
    try:
        if key in st.secrets:
            value = st.secrets[key]
            if value not in (None, ""):
                return str(value).strip()
    except Exception:
        pass
    return default


DART_API_KEY = config_value("DART_API_KEY", "YOUR_API_KEY")
DART_API_TOKEN = hashlib.sha256(DART_API_KEY.encode("utf-8")).hexdigest()[:12] if DART_API_KEY else "no-key"
ECOS_API_KEY = config_value("ECOS_API_KEY", "YOUR_ECOS_KEY")
ECOS_API_URL = "https://ecos.bok.or.kr/api/KeyStatisticList"
OPENAI_API_KEY = config_value("OPENAI_API_KEY", "")
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_BRIEFING_MODEL = "gpt-5.5"
KIS_APP_KEY = config_value("KIS_APP_KEY", "")
KIS_APP_SECRET = config_value("KIS_APP_SECRET", "")
KIS_BASE_URL = config_value("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443").rstrip("/")
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
    .decision-report {
        border-radius: 8px;
        background: #ffffff;
        border: 1px solid rgba(15, 23, 42, 0.12);
        box-shadow: 0 12px 30px rgba(15, 23, 42, 0.07);
        padding: 15px 16px;
        margin: 0.7rem 0 1rem 0;
    }
    .decision-head {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: flex-start;
        border-bottom: 1px solid rgba(148, 163, 184, 0.22);
        padding-bottom: 10px;
        margin-bottom: 10px;
    }
    .decision-title {
        color: #0f172a;
        font-size: 1.04rem;
        font-weight: 950;
        line-height: 1.25;
    }
    .decision-conclusion {
        color: #0f172a;
        font-size: 1.14rem;
        font-weight: 950;
        line-height: 1.45;
        margin: 8px 0 10px 0;
    }
    .decision-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 8px;
        margin-top: 10px;
    }
    .decision-tile {
        border-radius: 8px;
        background: #f8fafc;
        border: 1px solid rgba(148, 163, 184, 0.22);
        padding: 10px;
        min-height: 76px;
    }
    .decision-tile small {
        display: block;
        color: #64748b;
        font-size: 0.74rem;
        font-weight: 850;
        margin-bottom: 5px;
    }
    .decision-tile strong {
        display: block;
        color: #0f172a;
        font-size: 0.92rem;
        font-weight: 950;
        line-height: 1.35;
    }
    .decision-tile span {
        display: block;
        color: #475569;
        font-size: 0.78rem;
        font-weight: 760;
        line-height: 1.35;
        margin-top: 4px;
    }
    @media (max-width: 900px) {
        .decision-head {
            flex-direction: column;
        }
        .decision-grid {
            grid-template-columns: 1fr 1fr;
        }
    }
    @media (max-width: 560px) {
        .decision-grid {
            grid-template-columns: 1fr;
        }
        .decision-conclusion {
            font-size: 1rem;
        }
    }
    .portfolio-shell {
        border-radius: 16px;
        padding: 16px;
        margin: 1rem 0 1.1rem 0;
        background:
            radial-gradient(circle at 8% 0%, rgba(168, 85, 247, 0.34), transparent 24%),
            radial-gradient(circle at 88% 18%, rgba(79, 70, 229, 0.28), transparent 24%),
            linear-gradient(135deg, #070b1a 0%, #111827 48%, #1e1236 100%);
        border: 1px solid rgba(196, 181, 253, 0.22);
        box-shadow: 0 18px 42px rgba(15, 23, 42, 0.22);
    }
    .portfolio-shell .section-title,
    .portfolio-shell .small-note {
        color: #f8fafc;
    }
    .portfolio-head {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 12px;
        margin-bottom: 12px;
        padding: 18px;
        border-radius: 14px;
        background:
            linear-gradient(135deg, rgba(15, 23, 42, 0.98) 0%, rgba(30, 18, 54, 0.98) 58%, rgba(49, 46, 129, 0.92) 100%);
        border: 1px solid rgba(196, 181, 253, 0.28);
        box-shadow: 0 18px 42px rgba(15, 23, 42, 0.18);
    }
    .portfolio-eyebrow {
        color: #c4b5fd;
        font-size: 0.76rem;
        font-weight: 900;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .portfolio-title {
        color: #ffffff;
        font-size: 1.25rem;
        font-weight: 950;
        line-height: 1.2;
    }
    .portfolio-subtitle {
        color: #cbd5e1;
        font-size: 0.84rem;
        font-weight: 700;
        line-height: 1.45;
        margin-top: 4px;
    }
    .portfolio-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
        margin-top: 10px;
    }
    .portfolio-grid-wide {
        display: grid;
        grid-template-columns: 1.15fr 1fr;
        gap: 10px;
        margin-top: 10px;
    }
    .portfolio-card {
        border-radius: 12px;
        padding: 13px;
        min-height: 150px;
        background: rgba(15, 23, 42, 0.78);
        border: 1px solid rgba(196, 181, 253, 0.18);
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
    }
    .portfolio-card-title {
        color: #e9d5ff;
        font-size: 0.8rem;
        font-weight: 900;
        margin-bottom: 8px;
    }
    .portfolio-card-value {
        color: #ffffff;
        font-size: 1.55rem;
        font-weight: 950;
        line-height: 1.1;
    }
    .portfolio-card-sub {
        color: #cbd5e1;
        font-size: 0.78rem;
        font-weight: 720;
        line-height: 1.45;
        margin-top: 7px;
    }
    .portfolio-progress {
        height: 9px;
        border-radius: 999px;
        background: rgba(148, 163, 184, 0.22);
        overflow: hidden;
        margin: 10px 0 8px 0;
    }
    .portfolio-progress-fill {
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #8b5cf6, #22d3ee);
    }
    .portfolio-row {
        display: grid;
        grid-template-columns: minmax(82px, 1fr) 62px 62px 78px;
        gap: 8px;
        align-items: center;
        border-top: 1px solid rgba(148, 163, 184, 0.16);
        padding: 7px 0;
        color: #e2e8f0;
        font-size: 0.78rem;
        font-weight: 760;
    }
    .portfolio-pill {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 999px;
        padding: 3px 8px;
        color: #ffffff;
        background: rgba(139, 92, 246, 0.72);
        font-size: 0.72rem;
        font-weight: 900;
        white-space: nowrap;
    }
    .portfolio-list-item {
        border-top: 1px solid rgba(148, 163, 184, 0.16);
        padding: 8px 0;
        color: #e2e8f0;
        font-size: 0.79rem;
        font-weight: 760;
        line-height: 1.45;
    }
    .portfolio-list-item strong {
        color: #ffffff;
        font-weight: 950;
    }
    .watchlist-strip {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        padding-bottom: 3px;
        margin-top: 8px;
    }
    .watch-chip {
        min-width: 142px;
        border-radius: 10px;
        padding: 9px 10px;
        background: rgba(30, 41, 59, 0.72);
        border: 1px solid rgba(196, 181, 253, 0.14);
        color: #e2e8f0;
    }
    .watch-chip strong {
        color: #ffffff;
        font-size: 0.86rem;
        display: block;
    }
    .portfolio-shell.korea-shell {
        padding: 18px;
    }
    .korea-module-title {
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        gap: 12px;
        margin: 16px 0 8px 0;
    }
    .korea-module-title strong {
        color: #f8fafc;
        font-size: 1.02rem;
        font-weight: 950;
        line-height: 1.25;
    }
    .korea-module-title span {
        display: block;
        color: #cbd5e1;
        font-size: 0.78rem;
        font-weight: 720;
        line-height: 1.45;
        margin-top: 3px;
    }
    .korea-module-meta {
        color: #c4b5fd;
        font-size: 0.74rem;
        font-weight: 900;
        white-space: nowrap;
    }
    .korea-card {
        border-radius: 12px;
        padding: 14px;
        min-height: 150px;
        background: rgba(15, 23, 42, 0.82);
        border: 1px solid rgba(196, 181, 253, 0.18);
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04), 0 10px 26px rgba(2, 6, 23, 0.18);
        overflow: hidden;
    }
    .korea-card.compact {
        min-height: unset;
    }
    .korea-card-head {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 10px;
        margin-bottom: 10px;
    }
    .korea-card-title {
        color: #e9d5ff;
        font-size: 0.82rem;
        font-weight: 950;
        line-height: 1.25;
    }
    .korea-card-subtitle {
        color: #cbd5e1;
        font-size: 0.76rem;
        font-weight: 720;
        line-height: 1.45;
        margin-top: 3px;
    }
    .korea-score {
        color: #ffffff;
        font-size: 1.72rem;
        font-weight: 950;
        line-height: 1;
    }
    .korea-metric-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 8px;
        margin: 10px 0;
    }
    .korea-metric {
        border-radius: 10px;
        padding: 9px 10px;
        background: rgba(30, 41, 59, 0.72);
        border: 1px solid rgba(196, 181, 253, 0.12);
    }
    .korea-metric small {
        display: block;
        color: #94a3b8;
        font-size: 0.7rem;
        font-weight: 850;
        margin-bottom: 4px;
    }
    .korea-metric strong {
        display: block;
        color: #f8fafc;
        font-size: 0.92rem;
        font-weight: 950;
        line-height: 1.25;
    }
    .korea-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 999px;
        padding: 4px 9px;
        color: #ffffff;
        background: rgba(139, 92, 246, 0.72);
        font-size: 0.72rem;
        font-weight: 950;
        white-space: nowrap;
    }
    .korea-badge.good { background: rgba(34, 197, 94, 0.82); }
    .korea-badge.info { background: rgba(56, 189, 248, 0.72); }
    .korea-badge.warn { background: rgba(245, 158, 11, 0.86); }
    .korea-badge.risk { background: rgba(239, 68, 68, 0.86); }
    .korea-badge.muted { background: rgba(100, 116, 139, 0.82); }
    .korea-table-wrap {
        width: 100%;
        overflow-x: auto;
        border-radius: 12px;
        border: 1px solid rgba(196, 181, 253, 0.14);
    }
    .korea-table {
        width: 100%;
        min-width: 820px;
        border-collapse: collapse;
        color: #e2e8f0;
        font-size: 0.78rem;
    }
    .korea-table th,
    .korea-table td {
        padding: 9px 10px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.14);
        text-align: right;
        vertical-align: top;
        white-space: nowrap;
    }
    .korea-table th:first-child,
    .korea-table td:first-child {
        text-align: left;
        position: sticky;
        left: 0;
        background: rgba(15, 23, 42, 0.98);
        z-index: 1;
    }
    .korea-table th {
        color: #c4b5fd;
        font-size: 0.72rem;
        font-weight: 950;
        letter-spacing: 0.01em;
        background: rgba(30, 41, 59, 0.72);
    }
    .korea-table td {
        color: #e2e8f0;
        font-weight: 760;
    }
    .korea-table td .muted {
        display: block;
        color: #94a3b8;
        font-size: 0.7rem;
        margin-top: 2px;
    }
    .korea-evidence {
        color: #cbd5e1;
        font-size: 0.77rem;
        font-weight: 720;
        line-height: 1.48;
        white-space: normal;
        min-width: 210px;
    }
    .korea-empty {
        border-radius: 12px;
        padding: 14px;
        background: rgba(30, 41, 59, 0.58);
        border: 1px dashed rgba(196, 181, 253, 0.22);
        color: #cbd5e1;
        font-size: 0.82rem;
        font-weight: 760;
        line-height: 1.5;
    }
    .korea-factor-cell {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 58px;
        border-radius: 999px;
        padding: 3px 8px;
        color: #ffffff;
        font-size: 0.72rem;
        font-weight: 950;
    }
    .heatmap-strong { background: rgba(34, 197, 94, 0.86); }
    .heatmap-good { background: rgba(56, 189, 248, 0.78); }
    .heatmap-neutral { background: rgba(139, 92, 246, 0.72); }
    .heatmap-weak { background: rgba(245, 158, 11, 0.88); }
    .heatmap-risk { background: rgba(239, 68, 68, 0.88); }
    .heatmap-empty { background: rgba(100, 116, 139, 0.82); }
    .fear-greed-panel {
        border-radius: 14px;
        padding: 14px;
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(30, 18, 54, 0.96));
        border: 1px solid rgba(196, 181, 253, 0.2);
        min-height: 100%;
    }
    .fear-greed-panel .section-title {
        color: #f8fafc;
    }
    .fear-greed-panel .small-note {
        color: #cbd5e1;
    }
    @media (max-width: 1100px) {
        .portfolio-grid,
        .portfolio-grid-wide {
            grid-template-columns: 1fr;
        }
        .korea-metric-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .korea-module-title {
            flex-direction: column;
            align-items: flex-start;
        }
        .korea-module-meta {
            white-space: normal;
        }
    }
    @media (max-width: 560px) {
        .portfolio-shell.korea-shell {
            padding: 12px;
            border-radius: 12px;
        }
        .korea-metric-grid {
            grid-template-columns: 1fr;
        }
        .korea-table {
            min-width: 720px;
        }
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
    "KIS Open API": "KIS 공식 현재가",
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


def kis_enabled() -> bool:
    return bool(KIS_APP_KEY and KIS_APP_SECRET and KIS_BASE_URL)


@st.cache_data(ttl=60 * 60, show_spinner=False)
def get_kis_access_token(refresh_token: int) -> tuple[str | None, str | None]:
    if not kis_enabled():
        return None, "KIS_APP_KEY/KIS_APP_SECRET 미설정"
    try:
        response = requests.post(
            f"{KIS_BASE_URL}/oauth2/tokenP",
            headers={"content-type": "application/json"},
            json={
                "grant_type": "client_credentials",
                "appkey": KIS_APP_KEY,
                "appsecret": KIS_APP_SECRET,
            },
            timeout=12,
        )
        payload = response.json() if response.content else {}
        if response.status_code >= 400:
            message = payload.get("msg1") or payload.get("error_description") or response.reason
            return None, f"KIS token 실패: {message}"
        token = payload.get("access_token")
        if not token:
            return None, "KIS token 응답에 access_token 없음"
        return str(token), None
    except Exception as exc:
        return None, f"KIS token 예외: {exc}"


def fetch_kis_stock_snapshot(code: str, display_name: str, refresh_token: int) -> Snapshot | None:
    token, token_error = get_kis_access_token(refresh_token)
    if not token:
        return None
    try:
        response = requests.get(
            f"{KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price",
            headers={
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {token}",
                "appkey": KIS_APP_KEY,
                "appsecret": KIS_APP_SECRET,
                "tr_id": "FHKST01010100",
                "custtype": "P",
            },
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": code,
            },
            timeout=8,
        )
        payload = response.json() if response.content else {}
        if response.status_code >= 400 or payload.get("rt_cd") not in (None, "0"):
            return None
        output = payload.get("output") or {}
        last_close = safe_float(output.get("stck_prpr"))
        change = safe_float(output.get("prdy_vrss"))
        change_pct = safe_float(output.get("prdy_ctrt"))
        prev_close = safe_float(output.get("stck_sdpr"))
        sign = str(output.get("prdy_vrss_sign", "")).strip()
        if change is not None and sign in {"4", "5"}:
            change = -abs(change)
        elif change is not None and sign in {"1", "2"}:
            change = abs(change)
        if prev_close in (None, 0) and last_close is not None and change is not None:
            prev_close = last_close - change
        if change_pct is None and prev_close not in (None, 0) and change is not None:
            change_pct = change / prev_close * 100
        if last_close is None:
            return None
        snap = make_snapshot(
            code,
            display_name,
            last_close,
            prev_close,
            change,
            change_pct,
            source="KIS Open API",
            unit="KRW",
            frequency="realtime_official",
            is_fallback=False,
        )
        snap.raw = pd.DataFrame([output])
        return snap
    except Exception:
        return None


@st.cache_data(ttl=5, show_spinner=False)
def load_kis_stock_snapshots(refresh_token: int, watch_codes: tuple[str, ...], names: tuple[str, ...]) -> dict[str, Snapshot]:
    if not kis_enabled() or not watch_codes:
        return {}
    result: dict[str, Snapshot] = {}
    for code, name in zip(watch_codes[:30], names[:30]):
        snap = fetch_kis_stock_snapshot(str(code).zfill(6), str(name), refresh_token)
        if snap is not None:
            result[snap.key] = snap
    return result


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
    snapshot_names: list[str] = []
    for code in snapshot_codes:
        row = listing.loc[listing["Code"] == code]
        display_name = row["Name"].iloc[0] if not row.empty else STOCK_UNIVERSE_NAME_HINTS.get(code, code)
        snapshot_names.append(str(display_name))
        build_snapshot(code, [code])
        snap = data.get(code)
        if snap is not None:
            snap.display_name = display_name
            snap.key = code

    kis_data = load_kis_stock_snapshots(refresh_token, tuple(snapshot_codes), tuple(snapshot_names))
    for code, kis_snap in kis_data.items():
        fallback_snap = data.get(code)
        data[code] = apply_snapshot_quality(
            Snapshot(
                key=code,
                display_name=kis_snap.display_name,
                last_close=kis_snap.last_close,
                prev_close=kis_snap.prev_close if kis_snap.prev_close is not None else (fallback_snap.prev_close if fallback_snap else None),
                change=kis_snap.change if kis_snap.change is not None else (fallback_snap.change if fallback_snap else None),
                change_pct=kis_snap.change_pct if kis_snap.change_pct is not None else (fallback_snap.change_pct if fallback_snap else None),
                asof=kis_snap.asof,
                raw=fallback_snap.raw if fallback_snap is not None else kis_snap.raw,
                source=kis_snap.source,
                unit=kis_snap.unit,
                frequency=kis_snap.frequency,
                is_fallback=False,
            )
        )

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
    band = korea_fear_greed_band(score)
    return band["label"], band["color"], band["advice"]


def plot_fear_greed_bar(score: float | None, label: str, color: str) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(11, 1.9))
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#0f172a")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 1)
    ax.barh(0.5, 100, color="#334155", height=0.28, edgecolor="none", alpha=0.82)

    if score is not None:
        ax.barh(0.5, score, color=color, height=0.28, edgecolor="none")
        ax.scatter([score], [0.5], s=120, color=color, edgecolors="#f8fafc", linewidths=1.2, zorder=5)
        ax.text(score, 0.88, f"{score:.0f}", ha="center", va="bottom", fontsize=11, weight="bold", color=color)

    bands = [
        (0, 24, "#dc2626", "극단 공포"),
        (25, 44, "#f97316", "공포"),
        (45, 55, "#6b7280", "중립"),
        (56, 74, "#a3e635", "탐욕"),
        (75, 100, "#16a34a", "극단 탐욕"),
    ]
    for start, end, band_color, text in bands:
        ax.axvspan(start, end, color=band_color, alpha=0.10)
        ax.text((start + end) / 2, 0.14, text, ha="center", va="center", fontsize=8.5, color="#cbd5e1")

    ax.text(0, 1.08, "공포·탐욕 지수", ha="left", va="bottom", fontsize=13, weight="bold", color="#f8fafc")
    ax.text(100, 1.08, label, ha="right", va="bottom", fontsize=11, weight="bold", color=color)
    ax.set_yticks([])
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.tick_params(axis="x", labelsize=9, colors="#cbd5e1")
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
    display_signal = {
        "매수": "검토 우위",
        "중립": "관찰",
        "매도": "리스크 관리",
    }.get(signal, signal)
    reasons_html = "".join(f"<div class='small-note'>- {reason}</div>" for reason in reasons)
    st.markdown(
        f"""
        <div class="signal-box">
            <div class="section-title" style="margin-top:0;">객관적 판단: <span class="{signal_class}">{display_signal}</span> ({score:.0f}/100)</div>
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
        fig.patch.set_facecolor("#0f172a")
        ax.set_facecolor("#0f172a")
        ax.axis("off")
        ax.text(0.5, 0.5, "최근 60거래일 데이터가 부족합니다.", ha="center", va="center", fontsize=12, color="#cbd5e1")
        return fig

    dates = mdates.date2num(pd.to_datetime(data.index).to_pydatetime())
    fig = plt.figure(figsize=(13, 7))
    fig.patch.set_facecolor("#0f172a")
    gs = fig.add_gridspec(4, 1, height_ratios=[3, 0.05, 1.25, 0.2], hspace=0.06)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[2], sharex=ax1)
    ax1.set_facecolor("#0f172a")
    ax2.set_facecolor("#0f172a")

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

    ax1.set_title(title, fontsize=13, weight="bold", loc="left", color="#f8fafc")
    ax1.grid(True, axis="y", linestyle="--", alpha=0.18, color="#94a3b8")
    ax1.set_ylabel("가격", fontsize=10, color="#cbd5e1")
    ax2.set_ylabel("거래량", fontsize=10, color="#cbd5e1")
    ax2.grid(True, axis="y", linestyle="--", alpha=0.18, color="#94a3b8")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax1.tick_params(axis="y", colors="#cbd5e1")
    ax2.tick_params(axis="x", rotation=0, colors="#cbd5e1")
    ax2.tick_params(axis="y", colors="#cbd5e1")
    for spine in [*ax1.spines.values(), *ax2.spines.values()]:
        spine.set_color("#334155")
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


def _compact_text(items: list[str], fallback: str = "특이사항 없음", limit: int = 2) -> str:
    cleaned = [clean_text(str(item)) for item in items if clean_text(str(item))]
    return " / ".join(cleaned[:limit]) if cleaned else fallback


def _portfolio_stance(regime: MarketRegimeOutput, leader_action: ActionDecision | None, exec_quality: float | None) -> tuple[str, str, str]:
    action_score = leader_action.score if isinstance(leader_action, ActionDecision) else 0
    if regime.score <= 34:
        return (
            "방어 우선",
            "현금과 손실 제한이 최우선입니다. 신규 진입은 중단하거나 최상위 종목만 아주 작게 관찰합니다.",
            "#2563eb",
        )
    if regime.score <= 44:
        return (
            "선별 방어",
            "시장 압력이 남아 있습니다. 추격 매수보다 현금 비중 유지와 손절 기준 점검이 우선입니다.",
            "#64748b",
        )
    if action_score >= 65 and (exec_quality is None or exec_quality >= 45):
        return (
            "선별 매수 가능",
            "시장과 종목 조건이 일부 맞습니다. 최상위 종목만 가격 구간과 체결비용을 확인한 뒤 분할 접근합니다.",
            "#dc2626",
        )
    if regime.score >= 65:
        return (
            "공격 준비",
            "시장 환경은 우호적입니다. 다만 종목별 손익비와 체결 품질이 확인된 후보만 비중을 싣습니다.",
            "#dc2626",
        )
    return (
        "관망 우위",
        "기회는 있지만 우위가 압도적이지 않습니다. 오늘은 랭킹 상위와 무효화 조건을 확인하는 날입니다.",
        "#64748b",
    )


def render_executive_decision_report(
    snapshot: dict[str, Snapshot],
    valid_rows: list[dict[str, Any]],
    code_to_name: dict[str, str],
    refresh_token: int,
    regime: MarketRegimeOutput,
    leadership_rows: list[dict[str, Any]],
) -> None:
    quality_score, quality_status, quality_color, quality_messages = aggregate_data_quality(snapshot, valid_rows)
    leader = leadership_rows[0] if leadership_rows else None
    leader_action = leader.get("action") if leader and isinstance(leader.get("action"), ActionDecision) else None
    leader_plan = leader.get("risk_plan") if leader and isinstance(leader.get("risk_plan"), dict) else {}
    leader_exec = leader.get("execution_plan") if leader else None
    exec_quality = safe_float(getattr(leader_exec, "execution_quality_score", None))
    leader_name = str(leader.get("name")) if leader else "후보 없음"
    leader_code = str(leader.get("code")) if leader else "-"
    leader_signal = action_label_ko(leader_action.action) if leader_action else "관찰만"
    leader_score = leader_action.score if leader_action else safe_float(leader.get("score") if leader else None)
    leader_score_text = "N/A" if leader_score is None else f"{leader_score:.0f}점"
    rr = safe_float(leader_plan.get("rr")) if leader_plan else None
    expected_edge = safe_float(leader_action.expected_edge) if leader_action else None
    max_position = safe_float(leader_action.max_position_pct) if leader_action else 0.0

    active_code = st.session_state.manual_active_code if st.session_state.manual_active_code in [row["code"] for row in valid_rows] else (leader_code if leader else None)
    active_name = code_to_name.get(active_code, STOCK_UNIVERSE_NAME_HINTS.get(active_code, active_code)) if active_code else "선택 종목 없음"
    active_hist = load_symbol_history(active_code, refresh_token, periods=240) if active_code else pd.DataFrame()
    active_plan = risk_plan_for_stock(active_code or "", active_name, active_hist)
    exit_plan = build_exit_plan(active_plan, active_hist, market_regime=regime.regime)

    try:
        kill_state = get_kill_switch_state(SIGNAL_LEDGER_DB)
    except Exception:
        kill_state = {"active": False, "reason": "ledger unavailable", "sample_size": 0}

    stance, conclusion, stance_color = _portfolio_stance(regime, leader_action, exec_quality)
    if kill_state.get("active"):
        stance = "신호 강등"
        stance_color = "#2563eb"
        conclusion = "최근 저장 신호 성과가 악화되었습니다. 신규 매수 판단은 자동으로 낮춰 보고, 검증된 후보만 소액으로 제한합니다."

    market_tile = f"{regime_label_ko(regime.regime)} · {regime.score}점"
    cash_tile = f"{regime.recommended_cash_range[0]}~{regime.recommended_cash_range[1]}%"
    leader_tile = f"{leader_name} ({leader_code})"
    edge_text = "N/A" if expected_edge is None else f"{expected_edge:+.2f}%"
    rr_text = "N/A" if rr is None else f"{rr:.2f}x"
    exec_text = "N/A" if exec_quality is None else f"{exec_quality:.0f}/100"
    stop_text = format_price(active_plan.get("stop"))
    tp_text = format_price(getattr(exit_plan, "first_take_profit", None))
    invalidation = _compact_text(getattr(exit_plan, "invalidation_rules", []), "손절 기준과 공시 리스크 확인", 2)
    drivers = _compact_text(regime.primary_drivers, "시장 압력 중립", 3)
    data_msg = _compact_text(quality_messages, quality_status, 2)
    blocker_text = _compact_text(leader_action.blockers if leader_action else [], "차단 조건 없음", 2)

    st.html(
        f"""
        <div class="decision-report">
            <div class="decision-head">
                <div>
                    <div class="insight-kicker">Executive Decision Report</div>
                    <div class="decision-title">오늘의 투자 결론</div>
                </div>
                <div class="insight-badge" style="background:{stance_color};">{html.escape(stance)}</div>
            </div>
            <div class="decision-conclusion">{html.escape(conclusion)}</div>
            <div class="decision-grid">
                <div class="decision-tile">
                    <small>시장 국면</small>
                    <strong>{html.escape(market_tile)}</strong>
                    <span>현금 권장 {html.escape(cash_tile)} · {html.escape(drivers)}</span>
                </div>
                <div class="decision-tile">
                    <small>최상위 후보</small>
                    <strong>{html.escape(leader_tile)}</strong>
                    <span>{html.escape(leader_signal)} · {html.escape(leader_score_text)} · 최대 {max_position * 100:.1f}%</span>
                </div>
                <div class="decision-tile">
                    <small>수익/비용</small>
                    <strong>기대값 {html.escape(edge_text)} · 손익비 {html.escape(rr_text)}</strong>
                    <span>체결 품질 {html.escape(exec_text)} · {html.escape(blocker_text)}</span>
                </div>
                <div class="decision-tile">
                    <small>무효화/청산</small>
                    <strong>손절 {html.escape(stop_text)} · 1차익절 {html.escape(tp_text)}</strong>
                    <span>{html.escape(invalidation)}</span>
                </div>
            </div>
            <div class="thesis">데이터 품질 {quality_score}/100 · {html.escape(quality_status)} · {html.escape(data_msg)}</div>
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
    render_executive_decision_report(snapshot, valid_rows, code_to_name, refresh_token, regime_output, rank_rows)
    render_portfolio_intelligence_section(snapshot, code_to_name, refresh_token)
    render_korea_alpha_section(snapshot, refresh_token)
    st.markdown('<div class="section-title">투자 판단 핵심 3항목</div>', unsafe_allow_html=True)
    col_pressure, col_rank, col_risk = st.columns([1.05, 1.45, 1.05])
    with col_pressure:
        render_market_pressure(snapshot)
    with col_rank:
        render_watchlist_ranking(rank_rows)
    with col_risk:
        render_risk_plan(active_code, code_to_name, refresh_token, active_action)
    return rank_rows


ASSET_CLASS_LABELS = {
    "stocks": "주식",
    "bonds": "채권",
    "mutualFunds": "펀드",
    "cash": "현금",
    "crypto": "가상자산",
    "alternatives": "대체자산",
}


def _portfolio_point_date(point: Any) -> pd.Timestamp:
    raw = getattr(point, "date", None)
    if raw is None and isinstance(point, dict):
        raw = point.get("date")
    try:
        return pd.Timestamp(str(raw))
    except Exception:
        return pd.Timestamp.min


def _portfolio_point_value(point: Any, benchmark: bool = False) -> float | None:
    if benchmark:
        raw = getattr(point, "benchmark_value", None)
        if raw is None and isinstance(point, dict):
            raw = point.get("benchmarkValue", point.get("benchmark_value"))
    else:
        raw = getattr(point, "value", None)
        if raw is None and isinstance(point, dict):
            raw = point.get("value")
    return safe_float(raw)


def _filter_price_points(points: list[Any], range_key: str) -> list[Any]:
    clean = sorted([point for point in points if _portfolio_point_value(point) is not None], key=_portfolio_point_date)
    if not clean or range_key == "All":
        return clean
    latest = _portfolio_point_date(clean[-1])
    if range_key == "1M":
        cutoff = latest - pd.DateOffset(months=1)
    elif range_key == "3M":
        cutoff = latest - pd.DateOffset(months=3)
    elif range_key == "YTD":
        cutoff = pd.Timestamp(year=latest.year, month=1, day=1)
    elif range_key == "1Y":
        cutoff = latest - pd.DateOffset(years=1)
    elif range_key == "3Y":
        cutoff = latest - pd.DateOffset(years=3)
    else:
        cutoff = pd.Timestamp.min
    filtered = [point for point in clean if _portfolio_point_date(point) >= cutoff]
    return filtered if len(filtered) >= 2 else clean[-2:]


def _scale_price_points(points: list[Any], latest_value: float) -> list[dict[str, Any]]:
    clean = sorted(points, key=_portfolio_point_date)
    if not clean:
        return []
    last = _portfolio_point_value(clean[-1])
    if last in (None, 0):
        return [{"date": str(getattr(point, "date", "")), "value": _portfolio_point_value(point) or 0.0} for point in clean]
    scale = latest_value / last
    return [
        {
            "date": str(getattr(point, "date", "")),
            "value": (_portfolio_point_value(point) or 0.0) * scale,
            "benchmarkValue": _portfolio_point_value(point, benchmark=True),
        }
        for point in clean
    ]


def _series_return(points: list[Any]) -> float | None:
    clean = sorted(points, key=_portfolio_point_date)
    if len(clean) < 2:
        return None
    start = _portfolio_point_value(clean[0])
    end = _portfolio_point_value(clean[-1])
    if start in (None, 0) or end is None:
        return None
    return end / start - 1.0


def _portfolio_health_score(
    drift: dict[str, dict[str, Any]],
    annualized_volatility: float | None,
    max_drawdown: float | None,
    sharpe_ratio: float | None,
    concentration: dict[str, Any],
    cash_weight: float,
) -> tuple[int, str, list[str], str]:
    score = 100
    reasons: list[str] = []
    max_abs_drift = max((abs(safe_float(row.get("drift")) or 0.0) for row in drift.values()), default=0.0)
    if max_abs_drift > 0.10:
        score -= 20
        reasons.append(f"배분 이탈 {max_abs_drift * 100:.1f}%p")
    elif max_abs_drift > 0.05:
        score -= 10
        reasons.append(f"배분 이탈 {max_abs_drift * 100:.1f}%p")
    elif max_abs_drift > 0.03:
        score -= 5
        reasons.append(f"배분 점검 {max_abs_drift * 100:.1f}%p")
    if annualized_volatility is not None and annualized_volatility > 0.25:
        score -= 15
        reasons.append("변동성 높음")
    elif annualized_volatility is not None and annualized_volatility > 0.18:
        score -= 8
        reasons.append("변동성 주의")
    if max_drawdown is not None and max_drawdown < -0.20:
        score -= 20
        reasons.append("낙폭 위험 확대")
    elif max_drawdown is not None and max_drawdown < -0.10:
        score -= 10
        reasons.append("낙폭 점검")
    if sharpe_ratio is not None and sharpe_ratio < 0.5:
        score -= 15
        reasons.append("위험 대비 효율 낮음")
    elif sharpe_ratio is not None and sharpe_ratio < 1.0:
        score -= 7
        reasons.append("샤프비율 보통")
    if concentration.get("level") == "High":
        score -= 15
        reasons.append("집중도 높음")
    elif concentration.get("level") == "Medium":
        score -= 7
        reasons.append("집중도 보통")
    if cash_weight < 0.02 or cash_weight > 0.30:
        score -= 6
        reasons.append("현금 비중 점검")
    score = int(max(0, min(100, round(score))))
    if score >= 80:
        return score, "우수", reasons[:3] or ["리스크 균형 양호"], "#22c55e"
    if score >= 60:
        return score, "관찰", reasons[:3] or ["일부 지표 점검"], "#a78bfa"
    if score >= 40:
        return score, "주의", reasons[:3] or ["방어적 점검 필요"], "#f59e0b"
    return score, "고위험", reasons[:3] or ["위험 관리 우선"], "#ef4444"


def _largest_drift_observation(drift: dict[str, dict[str, Any]]) -> dict[str, str] | None:
    if not drift:
        return None
    asset_class, row = max(drift.items(), key=lambda item: abs(safe_float(item[1].get("drift")) or 0.0))
    value = safe_float(row.get("drift")) or 0.0
    label = ASSET_CLASS_LABELS.get(asset_class, asset_class)
    direction = "초과" if value > 0 else "부족"
    return {"observation": f"{label} 비중이 목표 대비 {abs(value) * 100:.1f}%p {direction}입니다."}


def _dark_chart_style(ax: plt.Axes) -> None:
    ax.set_facecolor("#0f172a")
    ax.figure.set_facecolor("#0f172a")
    ax.tick_params(colors="#cbd5e1", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.grid(True, color="#334155", alpha=0.35, linewidth=0.7)


def plot_portfolio_value_chart(points: list[Any], benchmark_points: list[Any]) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8.4, 3.1))
    _dark_chart_style(ax)
    dates = [_portfolio_point_date(point) for point in points]
    values = [_portfolio_point_value(point) for point in points]
    ax.plot(dates, values, color="#a78bfa", linewidth=2.4, label="포트폴리오")
    if benchmark_points:
        bench_dates = [_portfolio_point_date(point) for point in benchmark_points]
        bench_values = [_portfolio_point_value(point) for point in benchmark_points]
        if values and bench_values and values[0] and bench_values[0]:
            normalized = [value / bench_values[0] * values[0] for value in bench_values]
            ax.plot(bench_dates, normalized, color="#22d3ee", linewidth=1.8, alpha=0.82, label="KOSPI 벤치마크")
    ax.set_title("포트폴리오 vs 벤치마크", color="#ffffff", fontsize=11, fontweight="bold")
    ax.yaxis.set_major_formatter(lambda value, _: f"{value / 1_000_000:.0f}M")
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=7))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.legend(facecolor="#111827", edgecolor="#334155", labelcolor="#e2e8f0", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def plot_portfolio_drawdown_chart(drawdowns: list[dict[str, Any]]) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8.4, 2.7))
    _dark_chart_style(ax)
    dates = [pd.Timestamp(row["date"]) for row in drawdowns]
    values = [float(row["drawdown"]) * 100 for row in drawdowns]
    ax.fill_between(dates, values, 0, color="#7c3aed", alpha=0.35)
    ax.plot(dates, values, color="#c4b5fd", linewidth=2)
    if values:
        min_idx = values.index(min(values))
        ax.scatter([dates[min_idx]], [values[min_idx]], color="#f97316", s=28, zorder=3)
        ax.annotate(f"MDD {values[min_idx]:.1f}%", (dates[min_idx], values[min_idx]), color="#fed7aa", fontsize=8)
    ax.set_title("고점 대비 낙폭", color="#ffffff", fontsize=11, fontweight="bold")
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:.0f}%")
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=7))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def render_portfolio_health_card(score: int, label: str, reasons: list[str], color: str) -> None:
    reason_html = "".join(f"<div class='portfolio-list-item'>{html.escape(reason)}</div>" for reason in reasons[:3])
    st.html(
        f"""
        <div class="portfolio-card">
            <div class="portfolio-card-title">포트폴리오 건강도</div>
            <div class="portfolio-card-value" style="color:{color};">{score}</div>
            <div class="portfolio-progress"><div class="portfolio-progress-fill" style="width:{score}%; background:{color};"></div></div>
            <div class="portfolio-pill">{html.escape(label)}</div>
            <div class="portfolio-card-sub">배분 이탈, 변동성, 낙폭, 샤프비율, 집중도, 현금 비중을 100점에서 감점합니다.</div>
            {reason_html}
        </div>
        """
    )


def render_allocation_drift_card(drift: dict[str, dict[str, Any]]) -> None:
    rows = []
    for asset_class in ["stocks", "bonds", "mutualFunds", "cash"]:
        row = drift.get(asset_class, {"currentWeight": 0.0, "targetWeight": 0.0, "drift": 0.0, "status": "On target"})
        current = safe_float(row.get("currentWeight")) or 0.0
        target = safe_float(row.get("targetWeight")) or 0.0
        delta = safe_float(row.get("drift")) or 0.0
        status = str(row.get("status"))
        status_ko = "초과" if status == "Overweight" else "부족" if status == "Underweight" else "적정"
        rows.append(
            f"""
            <div class="portfolio-row">
                <div>{html.escape(ASSET_CLASS_LABELS.get(asset_class, asset_class))}</div>
                <div>{current * 100:.1f}%</div>
                <div>{target * 100:.1f}%</div>
                <div><span class="portfolio-pill">{status_ko} {delta * 100:+.1f}%p</span></div>
            </div>
            """
        )
    st.html(
        f"""
        <div class="portfolio-card">
            <div class="portfolio-card-title">목표 비중 대비 이탈</div>
            <div class="portfolio-card-sub">현재 / 목표 / 이탈</div>
            {''.join(rows)}
        </div>
        """
    )


def render_rebalance_candidates_card(suggestions: list[dict[str, Any]]) -> None:
    if suggestions:
        items = []
        for item in suggestions[:4]:
            asset = ASSET_CLASS_LABELS.get(str(item.get("assetClass")), str(item.get("assetClass")))
            items.append(
                f"""
                <div class="portfolio-list-item">
                    <strong>{html.escape(asset)} · {html.escape(str(item.get("action")))}</strong><br/>
                    {portfolio_format_currency(item.get("suggestedAmount"))} · {html.escape(str(item.get("reason")))}
                    <br/><span style="color:#c4b5fd;">{html.escape(str(item.get("impact")))}</span>
                </div>
                """
            )
        body = "".join(items)
    else:
        body = '<div class="portfolio-list-item"><strong>큰 리밸런싱 후보 없음</strong><br/>목표 비중 대비 3%p 이상 이탈한 자산군이 없습니다.</div>'
    st.html(
        f"""
        <div class="portfolio-card">
            <div class="portfolio-card-title">리밸런싱 검토 후보</div>
            {body}
        </div>
        """
    )


def render_risk_return_panel(metrics: dict[str, Any]) -> None:
    rows = [
        ("연평균 성장률(CAGR)", portfolio_format_percent(metrics.get("cagr"))),
        ("기간 수익률", portfolio_format_percent(metrics.get("periodReturn"), signed=True)),
        ("연환산 변동성", portfolio_format_percent(metrics.get("volatility"))),
        ("샤프 비율", "N/A" if metrics.get("sharpeRatio") is None else f"{metrics.get('sharpeRatio'):.2f}"),
        ("최대 낙폭", portfolio_format_percent(metrics.get("maxDrawdown"))),
        ("KOSPI 대비 베타", "N/A" if metrics.get("beta") is None else f"{metrics.get('beta'):.2f}"),
    ]
    warning = []
    if (metrics.get("sharpeRatio") is not None) and metrics["sharpeRatio"] < 0.5:
        warning.append("샤프 0.5 미만")
    if (metrics.get("maxDrawdown") is not None) and metrics["maxDrawdown"] < -0.20:
        warning.append("최대낙폭 -20% 초과")
    if (metrics.get("volatility") is not None) and metrics["volatility"] > 0.25:
        warning.append("변동성 25% 초과")
    body = "".join(
        f"<div class='portfolio-row' style='grid-template-columns:1fr 1fr;'><div>{html.escape(label)}</div><div style='text-align:right;'>{html.escape(value)}</div></div>"
        for label, value in rows
    )
    warn_html = "".join(f"<span class='portfolio-pill' style='background:#f97316;'>{html.escape(item)}</span> " for item in warning) or "<span class='portfolio-pill'>정상 범위</span>"
    st.html(
        f"""
        <div class="portfolio-card">
            <div class="portfolio-card-title">위험·수익 패널</div>
            {body}
            <div class="portfolio-card-sub">{warn_html}</div>
        </div>
        """
    )


def render_insight_engine_card(insights: list[dict[str, str]]) -> None:
    body = "".join(
        f"""
        <div class="portfolio-list-item">
            <strong>{idx}. {html.escape(item.get("observation", ""))}</strong><br/>
            {html.escape(item.get("why", ""))}<br/>
            <span style="color:#c4b5fd;">후보 행동: {html.escape(item.get("candidate", ""))}</span>
        </div>
        """
        for idx, item in enumerate(insights[:3], 1)
    )
    st.html(
        f"""
        <div class="portfolio-card">
            <div class="portfolio-card-title">인사이트 엔진</div>
            {body}
            <div class="portfolio-card-sub">확정 추천이 아니라 투명한 규칙 기반 검토 항목입니다.</div>
        </div>
        """
    )


def render_concentration_card(holdings: list[Any], concentration: dict[str, Any]) -> None:
    total = sum((safe_float(getattr(item, "quantity", 0)) or 0.0) * (safe_float(getattr(item, "current_price", 0)) or 0.0) for item in holdings)
    ranked = sorted(
        holdings,
        key=lambda item: (safe_float(getattr(item, "quantity", 0)) or 0.0) * (safe_float(getattr(item, "current_price", 0)) or 0.0),
        reverse=True,
    )
    rows = []
    for item in ranked[:5]:
        value = (safe_float(getattr(item, "quantity", 0)) or 0.0) * (safe_float(getattr(item, "current_price", 0)) or 0.0)
        weight = 0.0 if total <= 0 else value / total
        rows.append(
            f"""
            <div class="portfolio-list-item">
                <strong>{html.escape(getattr(item, "name", ""))}</strong> · {html.escape(getattr(item, "symbol", ""))}
                <span style="float:right;">{weight * 100:.1f}%</span>
            </div>
            """
        )
    color = "#ef4444" if concentration.get("level") == "High" else "#f59e0b" if concentration.get("level") == "Medium" else "#22c55e"
    st.html(
        f"""
        <div class="portfolio-card">
            <div class="portfolio-card-title">집중도 리스크</div>
            <div class="portfolio-pill" style="background:{color};">{html.escape({'Low': '낮음', 'Medium': '주의', 'High': '높음'}.get(str(concentration.get("level")), str(concentration.get("level"))))}</div>
            <div class="portfolio-card-sub">{html.escape(str(concentration.get("reason")))}</div>
            {''.join(rows)}
        </div>
        """
    )


def _holding_stock_signals(
    holdings: list[Any],
    snapshot: dict[str, Snapshot],
    refresh_token: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for holding in holdings:
        asset_class = str(getattr(holding, "asset_class", "stocks"))
        raw_symbol = str(getattr(holding, "symbol", "")).strip()
        if asset_class != "stocks" or not re.fullmatch(r"\d{6}", raw_symbol):
            continue
        code = raw_symbol
        if code in seen:
            continue
        seen.add(code)

        name = str(getattr(holding, "name", code))
        snap = snapshot.get(code)
        latest = safe_float(getattr(snap, "last_close", None) if snap is not None else None)
        change_pct = safe_float(getattr(snap, "change_pct", None) if snap is not None else None)
        history = load_symbol_history(code, refresh_token, periods=260)
        signals: list[str] = []

        if not history.empty:
            _, _, _, close_col, _ = find_ohlcv_columns(history)
            closes = pd.to_numeric(history[close_col], errors="coerce").dropna()
            if not closes.empty:
                history_latest = safe_float(closes.iloc[-1])
                latest = latest if latest is not None else history_latest
                if change_pct is None and len(closes) >= 2 and safe_float(closes.iloc[-2]) not in (None, 0):
                    prev = float(closes.iloc[-2])
                    change_pct = (float(closes.iloc[-1]) / prev - 1) * 100
                if latest is not None:
                    for window in (20, 60, 200):
                        if len(closes) >= window:
                            ma = safe_float(closes.tail(window).mean())
                            if ma not in (None, 0):
                                signals.append(f"{window}일선 {'상회' if latest >= ma else '하회'}")
                    if len(closes) >= 60:
                        high_52w = safe_float(closes.tail(min(252, len(closes))).max())
                        if high_52w not in (None, 0):
                            drawdown = (latest / high_52w - 1) * 100
                            if drawdown >= -3:
                                signals.append("52주 고점 근접")
                            elif drawdown <= -20:
                                signals.append(f"고점 대비 {drawdown:.1f}%")
                    returns = closes.pct_change().dropna()
                    if len(returns) >= 20:
                        volatility = safe_float(returns.tail(60).std() * math.sqrt(252) * 100)
                        if volatility is not None and volatility >= 45:
                            signals.append(f"변동성 높음 {volatility:.0f}%")

        if latest is None:
            latest = safe_float(getattr(holding, "current_price", None))
        if change_pct is None:
            average_cost = safe_float(getattr(holding, "average_cost", None))
            if latest is not None and average_cost not in (None, 0):
                change_pct = (latest / average_cost - 1) * 100
                signals.append("평단 대비 수익률")

        rows.append(
            {
                "code": code,
                "name": name,
                "latest": latest,
                "change_pct": change_pct,
                "signals": signals[:3] or ["추세 데이터 부족"],
            }
        )
    return rows[:8]


def render_watchlist_signals_card(
    holdings: list[Any],
    snapshot: dict[str, Snapshot],
    refresh_token: int,
) -> None:
    signals = _holding_stock_signals(holdings, snapshot, refresh_token)
    chips = []
    for item in signals:
        change = safe_float(item.get("change_pct"))
        color = "#22c55e" if (change or 0.0) >= 0 else "#60a5fa"
        change_text = "N/A" if change is None else f"{change:+.2f}%"
        price_text = "N/A" if item.get("latest") is None else f"{float(item.get('latest')):,.0f}원"
        chips.append(
            f"""
            <div class="watch-chip">
                <strong>{html.escape(str(item.get("name")))}</strong>
                <div style="font-size:0.72rem; color:#cbd5e1;">{html.escape(str(item.get("code")))} · {html.escape(price_text)}</div>
                <div style="color:{color}; font-weight:900;">{html.escape(change_text)}</div>
                <div style="font-size:0.74rem; line-height:1.35;">{html.escape(" / ".join(item.get("signals", [])[:2]))}</div>
            </div>
            """
        )
    if not chips:
        chips.append(
            """
            <div class="portfolio-list-item">
                <strong>보유종목 신호 없음</strong><br/>
                사이드바 보유종목 CSV에 6자리 종목코드를 입력하면 해당 종목의 추세 신호가 표시됩니다.
            </div>
            """
        )
    st.html(
        f"""
        <div class="portfolio-card" style="min-height:unset;">
            <div class="portfolio-card-title">보유종목 신호</div>
            <div class="watchlist-strip">{''.join(chips)}</div>
        </div>
        """
    )


def render_portfolio_intelligence_section(
    snapshot: dict[str, Snapshot],
    code_to_name: dict[str, str],
    refresh_token: int,
) -> None:
    holdings_text = str(st.session_state.get("portfolio_holdings_text", ""))
    parsed_rows, parse_errors = parse_portfolio_text(holdings_text)
    holdings = getHoldings(parsed_rows, snapshot, code_to_name)
    summary = getPortfolioSummary(holdings)
    total_value = safe_float(summary.get("totalValue")) or 0.0
    allocation = summary.get("allocation", {})
    target_allocation = summary.get("targetAllocation", [])
    drift = calculateAllocationDrift(allocation, target_allocation)
    suggestions = generateRebalanceSuggestions(allocation, target_allocation, total_value, {"threshold": 0.03, "minimum_trade_amount": 100_000})
    base_points = _scale_price_points(getPortfolioSnapshots(), total_value if total_value > 0 else 1.0)

    st.markdown('<div class="portfolio-shell">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="portfolio-head">
            <div>
                <div class="portfolio-eyebrow">Portfolio Intelligence</div>
                <div class="portfolio-title">리스크, 배분, 리밸런싱을 한 번에 보는 투자 의사결정 보드</div>
                <div class="portfolio-subtitle">주문 기능이 아닌 검토 후보와 위험 경고만 제공합니다. 입력 보유종목이 없으면 데모 포트폴리오로 표시됩니다.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    range_options = {
        "1개월": "1M",
        "3개월": "3M",
        "연초 이후": "YTD",
        "1년": "1Y",
        "3년": "3Y",
        "전체": "All",
    }
    range_label = st.radio(
        "포트폴리오 인텔리전스 기간",
        list(range_options.keys()),
        index=5,
        horizontal=True,
        key="portfolio_intelligence_range_label",
        label_visibility="collapsed",
    )
    range_key = range_options[range_label]
    if parse_errors:
        st.caption("포트폴리오 CSV 일부 행 제외: " + " / ".join(parse_errors[:2]))

    filtered_points = _filter_price_points(base_points, range_key)
    benchmark_points = _filter_price_points(getBenchmarkSeries(), range_key)
    returns = calculatePeriodReturns(filtered_points)
    benchmark_returns = calculatePeriodReturns(benchmark_points)
    cagr = calculateCAGR(filtered_points)
    volatility = calculateAnnualizedVolatility(returns)
    sharpe = calculateSharpeRatio(cagr, volatility, 0.025)
    max_drawdown = calculateMaxDrawdown(filtered_points)
    beta = calculateBeta(returns, benchmark_returns)
    relative_return = calculateBenchmarkRelativeReturn(filtered_points, benchmark_points)
    concentration = calculateConcentrationRisk(holdings)
    cash_weight = safe_float(allocation.get("cash", {}).get("weight") if isinstance(allocation.get("cash"), dict) else allocation.get("cash")) or 0.0
    health_score, health_label, health_reasons, health_color = _portfolio_health_score(drift, volatility, max_drawdown, sharpe, concentration, cash_weight)
    metrics = {
        "cagr": cagr,
        "periodReturn": _series_return(filtered_points),
        "volatility": volatility,
        "sharpeRatio": sharpe,
        "maxDrawdown": max_drawdown,
        "beta": beta,
        "relativeReturn": relative_return,
        "largestDrift": _largest_drift_observation(drift),
        "rebalanceSuggestions": suggestions,
    }
    insights = generatePortfolioInsightSummary(metrics)

    top_cols = st.columns([1, 1.15, 1])
    with top_cols[0]:
        render_portfolio_health_card(health_score, health_label, health_reasons, health_color)
    with top_cols[1]:
        render_allocation_drift_card(drift)
    with top_cols[2]:
        render_rebalance_candidates_card(suggestions)

    mid_cols = st.columns([1, 1])
    with mid_cols[0]:
        render_risk_return_panel(metrics)
    with mid_cols[1]:
        render_insight_engine_card(insights)

    chart_cols = st.columns([1.2, 1])
    with chart_cols[0]:
        st.pyplot(plot_portfolio_value_chart(filtered_points, benchmark_points), clear_figure=True)
    with chart_cols[1]:
        st.pyplot(plot_portfolio_drawdown_chart(calculateDrawdownSeries(filtered_points)), clear_figure=True)
        st.caption(f"벤치마크 초과수익: {portfolio_format_percent(relative_return, signed=True)}")

    bottom_cols = st.columns([1, 1])
    with bottom_cols[0]:
        render_concentration_card(holdings, concentration)
    with bottom_cols[1]:
        render_watchlist_signals_card(holdings, snapshot, refresh_token)
    st.markdown("</div>", unsafe_allow_html=True)


def _korea_grade_color(grade: str) -> str:
    return {
        "STRONG_REVIEW": "#22c55e",
        "BUY_REVIEW": "#a78bfa",
        "WATCHLIST": "#38bdf8",
        "NEUTRAL": "#94a3b8",
        "CAUTION": "#f59e0b",
        "EXCLUDE": "#ef4444",
    }.get(str(grade), "#94a3b8")


def _korea_latest_price(code: str) -> float | None:
    history = getKoreaPriceHistory(code)
    if not history:
        return None
    return safe_float(getattr(history[-1], "close", None))


def _korea_factor_dict(score: Any) -> dict[str, float]:
    factors = getattr(score, "factor_scores", None)
    if factors is None:
        return {}
    return {
        "모멘텀": float(getattr(factors, "momentum", 0) or 0),
        "밸류": float(getattr(factors, "value", 0) or 0),
        "퀄리티": float(getattr(factors, "quality", 0) or 0),
        "실적": float(getattr(factors, "earnings_revision", 0) or 0),
        "수급": float(getattr(factors, "supply_demand", 0) or 0),
        "공시": float(getattr(factors, "event_catalyst", 0) or 0),
        "밸류업": float(getattr(factors, "value_up", 0) or 0),
        "유동성": float(getattr(factors, "liquidity", 0) or 0),
        "리스크": float(getattr(factors, "risk", 0) or 0),
    }


def _snapshot_last_close(snapshot: dict[str, Snapshot], key: str) -> float | None:
    snap = snapshot.get(key)
    return safe_float(snap.last_close) if snap is not None else None


def _snapshot_return_decimal(snapshot: dict[str, Snapshot], key: str) -> float | None:
    snap = snapshot.get(key)
    change_pct = safe_float(snap.change_pct) if snap is not None else None
    return None if change_pct is None else change_pct / 100


def _snapshot_above_ma(snapshot: dict[str, Snapshot], key: str, window: int = 200) -> bool | None:
    snap = snapshot.get(key)
    if snap is None or snap.raw is None or not isinstance(snap.raw, pd.DataFrame) or snap.raw.empty:
        return None
    try:
        _, _, _, close_col, _ = find_ohlcv_columns(snap.raw)
        closes = pd.to_numeric(snap.raw[close_col], errors="coerce").dropna()
        if len(closes) < window:
            return None
        latest = safe_float(snap.last_close) or safe_float(closes.iloc[-1])
        ma = safe_float(closes.tail(window).mean())
        return None if latest is None or ma is None else latest >= ma
    except Exception:
        return None


def _snapshot_volatility_proxy(snapshot: dict[str, Snapshot], key: str = "KOSPI") -> float | None:
    snap = snapshot.get(key)
    if snap is None or snap.raw is None or not isinstance(snap.raw, pd.DataFrame) or snap.raw.empty:
        return None
    try:
        _, _, _, close_col, _ = find_ohlcv_columns(snap.raw)
        closes = pd.to_numeric(snap.raw[close_col], errors="coerce").dropna()
        returns = closes.pct_change().dropna().tail(60)
        if len(returns) < 20:
            return None
        return safe_float(returns.std() * math.sqrt(252))
    except Exception:
        return None


def build_live_korea_market_status(snapshot: dict[str, Snapshot]) -> KoreaMarketStatus:
    regime_output = build_market_regime_output(snapshot)
    regime_map = {
        "Extreme Risk-Off": "panic",
        "Risk-Off": "risk_off",
        "Neutral": "neutral",
        "Risk-On": "risk_on",
        "Euphoria": "risk_on",
    }
    kospi = snapshot.get("KOSPI")
    kosdaq = snapshot.get("KOSDAQ")
    usdkrw = snapshot.get("USD/KRW")
    kr3y = snapshot.get("KR 3Y")

    reasons: list[str] = []
    kospi_return = _snapshot_return_decimal(snapshot, "KOSPI")
    kosdaq_return = _snapshot_return_decimal(snapshot, "KOSDAQ")
    usd_return = _snapshot_return_decimal(snapshot, "USD/KRW")
    kr3y_change = safe_float(kr3y.change) if kr3y is not None else None
    kospi_above = _snapshot_above_ma(snapshot, "KOSPI")
    kosdaq_above = _snapshot_above_ma(snapshot, "KOSDAQ")

    if kospi_return is not None:
        reasons.append(f"코스피 1일 등락률 {kospi_return * 100:+.2f}%")
    if kosdaq_return is not None:
        reasons.append(f"코스닥 1일 등락률 {kosdaq_return * 100:+.2f}%")
    if kospi_above is not None:
        reasons.append("코스피는 200일선 위" if kospi_above else "코스피는 200일선 아래")
    if kosdaq_above is not None:
        reasons.append("코스닥은 200일선 위" if kosdaq_above else "코스닥은 200일선 아래")
    if usd_return is not None:
        reasons.append(f"USD/KRW 1일 등락률 {usd_return * 100:+.2f}%")
    if kr3y_change is not None:
        reasons.append(f"국고채 3년 변화 {kr3y_change:+.2f}%p")
    if not reasons:
        reasons = list(regime_output.key_drivers[:3])

    source_bits = []
    for label, snap in [("KOSPI", kospi), ("KOSDAQ", kosdaq), ("USD/KRW", usdkrw), ("KR 3Y", kr3y)]:
        if snap is not None:
            source_bits.append(f"{label}:{snap.source or 'unknown'}")
    asof_values = [snap.asof for snap in [kospi, kosdaq, usdkrw, kr3y] if snap is not None and snap.asof is not None]
    updated_at = max(asof_values).strftime("%Y-%m-%d %H:%M:%S") if asof_values else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    is_live = any(
        snap is not None and str(snap.frequency).lower() in {"near_realtime", "realtime_official"}
        for snap in [kospi, kosdaq, usdkrw, kr3y]
    )

    return KoreaMarketStatus(
        date=updated_at[:10],
        kospi_close=_snapshot_last_close(snapshot, "KOSPI"),
        kosdaq_close=_snapshot_last_close(snapshot, "KOSDAQ"),
        kospi_return_1d=kospi_return,
        kosdaq_return_1d=kosdaq_return,
        kospi_above_ma200=kospi_above,
        kosdaq_above_ma200=kosdaq_above,
        market_breadth=None,
        advance_decline_ratio=None,
        new_high_new_low_ratio=None,
        turnover_trend=None,
        usd_krw=_snapshot_last_close(snapshot, "USD/KRW"),
        bond_yield_3y=_snapshot_last_close(snapshot, "KR 3Y"),
        volatility_proxy=_snapshot_volatility_proxy(snapshot),
        regime=regime_map.get(regime_output.regime, "neutral"),
        regime_score=regime_output.score,
        reason=reasons[:6],
        source=", ".join(source_bits) if source_bits else "snapshot unavailable",
        updated_at=updated_at,
        is_live=is_live,
    )


def _format_market_number(value: float | None, digits: int = 2, suffix: str = "") -> str:
    number = safe_float(value)
    if number is None:
        return "N/A"
    return f"{number:,.{digits}f}{suffix}"


def _format_market_return(value: float | None) -> str:
    number = safe_float(value)
    if number is None:
        return ""
    color = "#22c55e" if number >= 0 else "#60a5fa"
    return f"<span style='color:{color}; font-weight:900;'>({number * 100:+.2f}%)</span>"


def _korea_grade_badge_class(grade: str) -> str:
    return {
        "STRONG_REVIEW": "good",
        "BUY_REVIEW": "info",
        "WATCHLIST": "info",
        "NEUTRAL": "muted",
        "CAUTION": "warn",
        "EXCLUDE": "risk",
    }.get(str(grade), "muted")


def _korea_action_label(grade: str) -> str:
    if grade in {"STRONG_REVIEW", "BUY_REVIEW", "WATCHLIST"}:
        return "검토 후보"
    if grade in {"CAUTION", "EXCLUDE"}:
        return "리스크 관리"
    return "관찰"


def _korea_module_title(title: str, subtitle: str = "", meta: str = "") -> None:
    st.markdown(
        f"""
        <div class="korea-module-title">
            <div>
                <strong>{html.escape(title)}</strong>
                {f'<span>{html.escape(subtitle)}</span>' if subtitle else ''}
            </div>
            {f'<div class="korea-module-meta">{html.escape(meta)}</div>' if meta else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _korea_empty_html(message: str, detail: str = "") -> str:
    detail_html = f"<br/><span>{html.escape(detail)}</span>" if detail else ""
    return f'<div class="korea-empty">{html.escape(message)}{detail_html}</div>'


def _korea_metric_html(label: str, value: str, tone: str = "") -> str:
    tone_style = {
        "good": "color:#22c55e;",
        "info": "color:#38bdf8;",
        "warn": "color:#f59e0b;",
        "risk": "color:#f87171;",
    }.get(tone, "")
    return f"""
    <div class="korea-metric">
        <small>{html.escape(label)}</small>
        <strong style="{tone_style}">{html.escape(value)}</strong>
    </div>
    """


def _korea_table_html(rows: list[dict[str, Any]], columns: list[str] | None = None) -> str:
    if not rows:
        return _korea_empty_html("표시할 데이터가 없습니다.", "데이터 공급자 또는 필터 조건을 확인하세요.")
    columns = columns or list(rows[0].keys())
    header = "".join(f"<th>{html.escape(str(col))}</th>" for col in columns)
    body_rows: list[str] = []
    for row in rows:
        cells = []
        for col in columns:
            value = row.get(col, "-")
            cells.append(f"<td>{value if isinstance(value, _HtmlCell) else html.escape(str(value))}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    return f"""
    <div class="korea-table-wrap">
        <table class="korea-table">
            <thead><tr>{header}</tr></thead>
            <tbody>{''.join(body_rows)}</tbody>
        </table>
    </div>
    """


class _HtmlCell(str):
    pass


def _korea_badge(text: str, tone: str = "muted") -> _HtmlCell:
    return _HtmlCell(f'<span class="korea-badge {html.escape(tone)}">{html.escape(text)}</span>')


def _korea_evidence(text: str) -> _HtmlCell:
    return _HtmlCell(f'<div class="korea-evidence">{html.escape(text or "-")}</div>')


def _korea_factor_cell(value: Any) -> _HtmlCell:
    bucket = korea_heatmap_bucket(value)
    number = safe_float(value)
    score_text = "-" if number is None else f"{number:.0f}"
    label = bucket["label"]
    css_class = bucket["class"]
    return _HtmlCell(f'<span class="korea-factor-cell {html.escape(css_class)}">{score_text} · {html.escape(label)}</span>')


def _safe_sharpe_text(value: Any) -> str:
    number = safe_float(value)
    return "-" if number is None else f"{number:.2f}"


def render_korea_market_regime_card(market_status: Any) -> None:
    regime_label = {
        "risk_on": "위험 선호",
        "neutral": "중립",
        "risk_off": "위험 회피",
        "panic": "패닉",
        "recovery": "회복",
    }.get(str(getattr(market_status, "regime", "neutral")), str(getattr(market_status, "regime", "neutral")))
    score = max(0.0, min(100.0, safe_float(getattr(market_status, "regime_score", None)) or 50.0))
    reasons = "".join(f"<div class='portfolio-list-item'>{html.escape(str(reason))}</div>" for reason in getattr(market_status, "reason", [])[:4])
    kospi_text = _format_market_number(getattr(market_status, "kospi_close", None), 2)
    kosdaq_text = _format_market_number(getattr(market_status, "kosdaq_close", None), 2)
    usd_text = _format_market_number(getattr(market_status, "usd_krw", None), 2)
    kr3y_text = _format_market_number(getattr(market_status, "bond_yield_3y", None), 2, "%")
    live_label = "현재 스냅샷" if getattr(market_status, "is_live", False) else "지연/보조 스냅샷"
    source_text = f"{live_label} · {getattr(market_status, 'updated_at', '-') or '-'}"
    st.html(
        f"""
        <div class="korea-card">
            <div class="korea-card-head">
                <div>
                    <div class="korea-card-title">한국시장 국면</div>
                    <div class="korea-card-subtitle">지수, 환율, 금리와 장기 추세를 함께 반영한 시장 환경 점수</div>
                </div>
                <span class="korea-badge {_korea_grade_badge_class('NEUTRAL')}">{html.escape(regime_label)}</span>
            </div>
            <div class="korea-score">{score:.0f}/100</div>
            <div class="portfolio-progress"><div class="portfolio-progress-fill" style="width:{score:.0f}%;"></div></div>
            <div class="portfolio-card-sub">
                KOSPI {kospi_text} {_format_market_return(getattr(market_status, "kospi_return_1d", None))} ·
                KOSDAQ {kosdaq_text} {_format_market_return(getattr(market_status, "kosdaq_return_1d", None))}<br/>
                USD/KRW {usd_text} · 국고채 3년 {kr3y_text}<br/>
                데이터 기준: {html.escape(source_text)}
            </div>
            {reasons}
        </div>
        """
    )


def render_korea_top_candidates_card(candidates: list[Any]) -> None:
    rows = []
    for idx, score in enumerate(candidates[:6], 1):
        grade = str(getattr(score, "recommendation_grade", "NEUTRAL"))
        color = _korea_grade_color(grade)
        rows.append(
            f"""
            <div class="portfolio-list-item">
                <strong>{idx}. {html.escape(getattr(score, "name", ""))}</strong>
                <span style="float:right; color:{color}; font-weight:900;">{getattr(score, "total_score", 0):.0f}</span><br/>
                {html.escape(getattr(score, "code", ""))} · {html.escape(korea_format_grade(grade))} ·
                초과수익 {html.escape(korea_format_percent(getattr(score, "expected_excess_return_3m", None), signed=True))}
                <br/><span style="color:#c4b5fd;">{html.escape(' / '.join(getattr(score, "positive_reasons", [])[:2]))}</span>
            </div>
            """
        )
    st.html(
        f"""
        <div class="korea-card">
            <div class="korea-card-head">
                <div>
                    <div class="korea-card-title">한국주식 알파 후보</div>
                    <div class="korea-card-subtitle">점수와 신뢰도를 함께 확인하는 검토 후보 목록</div>
                </div>
                <span class="korea-badge info">상위 {len(candidates[:6])}개</span>
            </div>
            {''.join(rows) if rows else _korea_empty_html('표시할 후보가 없습니다.', '필터 조건을 낮추거나 데이터 갱신을 확인하세요.')}
        </div>
        """
    )


def render_korea_risk_control_panel(data: dict[str, Any]) -> None:
    summary = data.get("riskSummary", {})
    alerts = "".join(f"<div class='portfolio-list-item'>{html.escape(str(item))}</div>" for item in summary.get("risk_alerts", [])[:4])
    avg_conf = summary.get("avg_confidence")
    st.html(
        f"""
        <div class="korea-card">
            <div class="korea-card-head">
                <div>
                    <div class="korea-card-title">리스크 관리</div>
                    <div class="korea-card-subtitle">신규 검토 전 확인해야 할 위험 플래그</div>
                </div>
                <span class="korea-badge {'risk' if summary.get('high_risk_count', 0) else 'good'}">{summary.get("high_risk_count", 0)}건</span>
            </div>
            <div class="korea-score">{summary.get("high_risk_count", 0)}</div>
            <div class="portfolio-card-sub">리스크 플래그 후보 수 · 평균 신뢰도 {html.escape(korea_format_confidence(avg_conf))}</div>
            {alerts if alerts else _korea_empty_html('중대한 리스크 플래그가 없습니다.', '단, 공시와 유동성은 계속 확인해야 합니다.')}
        </div>
        """
    )


def render_korea_recommendation_table(scores: list[Any]) -> None:
    table_rows = []
    for score in scores:
        latest = _korea_latest_price(getattr(score, "code", ""))
        grade = str(getattr(score, "recommendation_grade", ""))
        evidence = " / ".join(
            list(getattr(score, "positive_reasons", []) or [])[:2]
            + list(getattr(score, "negative_reasons", []) or [])[:1]
        )
        table_rows.append(
            {
                "종목": _HtmlCell(
                    f"{html.escape(getattr(score, 'name', ''))}"
                    f"<span class='muted'>{html.escape(getattr(score, 'code', ''))} · {html.escape(korea_format_market_label(getattr(score, 'market', '')))} · {html.escape(str(getattr(score, 'sector', '-') or '-'))}</span>"
                ),
                "검토 상태": _korea_badge(korea_format_grade(grade), _korea_grade_badge_class(grade)),
                "총점": korea_format_score(getattr(score, "total_score", None)),
                "신뢰도": korea_format_confidence(getattr(score, "confidence", None)),
                "현재가": korea_format_krw(latest),
                "상승확률 1M": korea_format_percent(getattr(score, "probability_outperform_1m", None)),
                "기대수익 3M": korea_format_percent(getattr(score, "expected_return_3m", None), signed=True),
                "초과수익 3M": korea_format_percent(getattr(score, "expected_excess_return_3m", None), signed=True),
                "하방위험": korea_format_percent(getattr(score, "downside_risk", None)),
                "제안비중": korea_format_percent(getattr(score, "suggested_weight", None)),
                "감시/무효화": _HtmlCell(
                    f"{html.escape(korea_format_krw(getattr(score, 'stop_review_price', None)))}"
                    f"<span class='muted'>무효화 {html.escape(korea_format_krw(getattr(score, 'invalidation_price', None)))}</span>"
                ),
                "근거": _korea_evidence(evidence or "근거 데이터 부족"),
                "데이터": _HtmlCell(
                    f"{html.escape(str(getattr(score, 'last_updated', '-') or '-'))}"
                    f"<span class='muted'>{html.escape(str(getattr(score, 'model_version', '-') or '-'))}</span>"
                ),
            }
        )
    _korea_module_title(
        "투자검토 알고리즘",
        "확정 매수·매도가 아니라 점수, 신뢰도, 기대수익, 하방위험을 함께 보는 검토 후보 표입니다.",
        f"{len(table_rows)}개 표시",
    )
    st.html(
        f"""
        <div class="korea-card compact">
            {_korea_table_html(table_rows)}
        </div>
        """
    )


def render_korea_signal_breakdown(scores: list[Any]) -> None:
    if not scores:
        st.html(
            f"""
            <div class="korea-card compact">
                {_korea_empty_html("상세 근거를 표시할 후보가 없습니다.", "필터 조건을 확인하세요.")}
            </div>
            """
        )
        return
    labels = [f"{getattr(score, 'code', '')} {getattr(score, 'name', '')}" for score in scores]
    selected = st.selectbox("알고리즘 판단 근거", labels, key="korea_signal_breakdown_select")
    score = scores[labels.index(selected)]
    factors = _korea_factor_dict(score)
    grade = str(getattr(score, "recommendation_grade", ""))
    metric_html = "".join(
        [
            _korea_metric_html("총점", korea_format_score(getattr(score, "total_score", None))),
            _korea_metric_html("등급", korea_format_grade(grade), _korea_grade_badge_class(grade)),
            _korea_metric_html("신뢰도", korea_format_confidence(getattr(score, "confidence", None))),
            _korea_metric_html("3M 기대수익", korea_format_percent(getattr(score, "expected_return_3m", None), signed=True)),
            _korea_metric_html("하방위험", korea_format_percent(getattr(score, "downside_risk", None)), "warn"),
        ]
    )
    factor_rows = [{"팩터": key, "점수": _korea_factor_cell(value)} for key, value in factors.items()]
    positive = "".join(f"<div class='portfolio-list-item'>{html.escape(str(reason))}</div>" for reason in getattr(score, "positive_reasons", [])[:6])
    negatives = list(getattr(score, "negative_reasons", []) or []) + list(getattr(score, "risk_flags", []) or [])
    negative = "".join(f"<div class='portfolio-list-item'>{html.escape(str(reason))}</div>" for reason in negatives[:6])
    st.html(
        f"""
        <div class="korea-card compact">
            <div class="korea-card-head">
                <div>
                    <div class="korea-card-title">선택 종목 상세 근거</div>
                    <div class="korea-card-subtitle">{html.escape(getattr(score, 'name', ''))} ({html.escape(getattr(score, 'code', ''))}) · 데이터 기준 {html.escape(str(getattr(score, 'last_updated', '-') or '-'))}</div>
                </div>
                <span class="korea-badge {_korea_grade_badge_class(grade)}">{html.escape(_korea_action_label(grade))}</span>
            </div>
            <div class="korea-metric-grid">{metric_html}</div>
            {_korea_table_html(factor_rows, ["팩터", "점수"])}
            <div class="portfolio-grid-wide">
                <div>
                    <div class="korea-card-title" style="margin-top:12px;">긍정 근거</div>
                    {positive if positive else _korea_empty_html("긍정 근거 데이터가 부족합니다.")}
                </div>
                <div>
                    <div class="korea-card-title" style="margin-top:12px;">반대 근거·리스크</div>
                    {negative if negative else _korea_empty_html("중대한 반대 근거가 없습니다.")}
                </div>
            </div>
        </div>
        """
    )


def render_korea_factor_heatmap(scores: list[Any]) -> None:
    rows = []
    for score in scores[:12]:
        factors = _korea_factor_dict(score)
        rows.append(
            {
                "종목": _HtmlCell(f"{html.escape(getattr(score, 'name', ''))}<span class='muted'>{html.escape(getattr(score, 'code', ''))}</span>"),
                "총점": _korea_factor_cell(getattr(score, "total_score", None)),
                **{key: _korea_factor_cell(value) for key, value in factors.items()},
            }
        )
    _korea_module_title("팩터 히트맵", "강함/양호/보통/약함/취약 구간을 같은 색상 규칙으로 표시합니다.", f"{len(rows)}개")
    st.html(
        f"""
        <div class="korea-card compact">
            {_korea_table_html(rows)}
        </div>
        """
    )


def render_korea_supply_demand_radar(scores: list[Any]) -> None:
    rows = []
    for score in scores[:8]:
        supply = getKoreaSupplyDemand(getattr(score, "code", ""))
        last_20 = supply[-20:]
        foreign = sum(safe_float(getattr(row, "foreign_net_buy", 0)) or 0 for row in last_20)
        institution = sum(safe_float(getattr(row, "institution_net_buy", 0)) or 0 for row in last_20)
        pension = sum(safe_float(getattr(row, "pension_net_buy", 0)) or 0 for row in last_20)
        flow_total = foreign + institution + pension
        signal = "수급 개선" if flow_total > 0 else "수급 약화"
        rows.append(
            {
                "종목": _HtmlCell(f"{html.escape(getattr(score, 'name', ''))}<span class='muted'>{html.escape(getattr(score, 'code', ''))}</span>"),
                "외국인 20D": korea_format_trading_value(foreign),
                "기관 20D": korea_format_trading_value(institution),
                "연기금 20D": korea_format_trading_value(pension),
                "합산": korea_format_trading_value(flow_total),
                "신호": _korea_badge(signal, "good" if flow_total > 0 else "warn"),
            }
        )
    _korea_module_title("수급 레이더", "최근 20거래일 외국인·기관·연기금 순매수 흐름을 점검합니다.")
    st.html(
        f"""
        <div class="korea-card compact">
            {_korea_table_html(rows)}
        </div>
        """
    )


def render_korea_disclosure_radar(disclosures: list[Any]) -> None:
    rows = []
    for event in disclosures[:8]:
        sentiment = str(getattr(event, "sentiment", "") or "")
        tone = "good" if sentiment == "positive" else "risk" if sentiment == "negative" else "muted"
        rows.append(
            {
                "일자": getattr(event, "date", ""),
                "종목": getattr(event, "code", ""),
                "분류": getattr(event, "category", ""),
                "감성": _korea_badge(sentiment or "neutral", tone),
                "중요도": f"{getattr(event, 'importance', 0):.0f}",
                "요약": _korea_evidence(getattr(event, "summary", "") or getattr(event, "title", "")),
            }
        )
    _korea_module_title("공시·이벤트 레이더", "공시 리스크와 촉매를 신규 검토 전에 먼저 확인합니다.")
    st.html(
        f"""
        <div class="korea-card compact">
            {_korea_table_html(rows)}
        </div>
        """
    )


def render_korea_value_up_radar(candidates: list[Any]) -> None:
    rows = []
    for score in candidates[:8]:
        factors = _korea_factor_dict(score)
        rows.append(
            {
                "종목": _HtmlCell(f"{html.escape(getattr(score, 'name', ''))}<span class='muted'>{html.escape(getattr(score, 'code', ''))}</span>"),
                "밸류업": _korea_factor_cell(factors.get("밸류업")),
                "밸류": _korea_factor_cell(factors.get("밸류")),
                "퀄리티": _korea_factor_cell(factors.get("퀄리티")),
                "제안비중": korea_format_percent(getattr(score, "suggested_weight", None)),
                "근거": _korea_evidence(" / ".join(getattr(score, "positive_reasons", [])[:2])),
            }
        )
    _korea_module_title("밸류업 레이더", "저평가, 주주환원, 재무 품질을 함께 보는 정책 수혜 후보입니다.")
    st.html(
        f"""
        <div class="korea-card compact">
            {_korea_table_html(rows)}
        </div>
        """
    )


def render_korea_backtest_accuracy_panel(backtest: Any) -> None:
    _korea_module_title(
        "예측 정확도·백테스트",
        "룰 기반 추정 성과입니다. 미래 수익을 보장하지 않으며 비용·슬리피지·세금 가정을 함께 봅니다.",
    )
    metric_html = "".join(
        [
            _korea_metric_html("CAGR", korea_format_percent(getattr(backtest, "cagr", None))),
            _korea_metric_html("초과수익", korea_format_percent(getattr(backtest, "excess_return", None), signed=True)),
            _korea_metric_html("MDD", korea_format_percent(getattr(backtest, "max_drawdown", None)), "warn"),
            _korea_metric_html("Sharpe", _safe_sharpe_text(getattr(backtest, "sharpe_ratio", None))),
            _korea_metric_html("Hit Ratio", korea_format_percent(getattr(backtest, "hit_ratio", None))),
            _korea_metric_html("P@10", korea_format_percent(getattr(backtest, "precision_at_top10", None))),
        ]
    )
    notes = "".join(f"<div class='portfolio-list-item'>{html.escape(str(note))}</div>" for note in getattr(backtest, "notes", [])[:3])
    subtitle = (
        f"{getattr(backtest, 'strategy_name', '')} · {getattr(backtest, 'start_date', '')}~{getattr(backtest, 'end_date', '')} · "
        f"비용 {korea_format_percent(getattr(backtest, 'transaction_cost_assumption', None))}, "
        f"슬리피지 {korea_format_percent(getattr(backtest, 'slippage_assumption', None))}, "
        f"세금 {korea_format_percent(getattr(backtest, 'tax_assumption', None))}"
    )
    st.html(
        f"""
        <div class="korea-card compact">
            <div class="korea-card-subtitle">{html.escape(subtitle)}</div>
            <div class="korea-metric-grid">{metric_html}</div>
            {notes if notes else _korea_empty_html("백테스트 메모가 없습니다.")}
        </div>
        """
    )


def render_korea_portfolio_action_queue(scores: list[Any]) -> None:
    rows = []
    for score in scores[:10]:
        grade = getattr(score, "recommendation_grade", "NEUTRAL")
        rows.append(
            {
                "검토": _korea_badge(_korea_action_label(str(grade)), _korea_grade_badge_class(str(grade))),
                "종목": _HtmlCell(f"{html.escape(getattr(score, 'name', ''))}<span class='muted'>{html.escape(getattr(score, 'code', ''))}</span>"),
                "등급": korea_format_grade(grade),
                "점수": korea_format_score(getattr(score, "total_score", None)),
                "신뢰도": korea_format_confidence(getattr(score, "confidence", None)),
                "최대비중": korea_format_percent(getattr(score, "max_suggested_weight", None)),
                "리스크": _korea_evidence(", ".join(getattr(score, "risk_flags", [])[:2]) or "중대 플래그 없음"),
            }
        )
    _korea_module_title("포트폴리오 검토 큐", "관심종목을 검토, 관찰, 리스크 관리 후보로 나눠 다음 점검 순서를 보여줍니다.")
    st.html(
        f"""
        <div class="korea-card compact">
            {_korea_table_html(rows)}
        </div>
        """
    )


def render_korea_alpha_section(snapshot: dict[str, Snapshot], refresh_token: int) -> None:
    st.markdown('<div class="portfolio-shell korea-shell">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="portfolio-head">
            <div>
                <div class="portfolio-eyebrow">Korea Alpha Engine</div>
                <div class="portfolio-title">한국 주식 초과수익 후보와 리스크를 한 번에 보는 알고리즘 보드</div>
                <div class="portfolio-subtitle">주문 실행이 아닌 검토 후보 보드입니다. 모든 판단에는 점수, 신뢰도, 기대수익 범위, 하방위험, 근거, 데이터 기준일과 모델 버전을 함께 표시합니다.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("한국 알파 필터", expanded=False):
        market_filter = st.multiselect("시장", ["KOSPI", "KOSDAQ", "ETF"], default=["KOSPI", "KOSDAQ"], key=f"korea_market_filter_{refresh_token}")
        min_score = st.slider("최소 점수", 0, 100, 0, 5, key=f"korea_min_score_{refresh_token}")
        grade_filter = st.multiselect(
            "등급",
            ["STRONG_REVIEW", "BUY_REVIEW", "WATCHLIST", "NEUTRAL", "CAUTION", "EXCLUDE"],
            default=["STRONG_REVIEW", "BUY_REVIEW", "WATCHLIST", "NEUTRAL", "CAUTION", "EXCLUDE"],
            format_func=korea_format_grade,
            key=f"korea_grade_filter_{refresh_token}",
        )
    live_market_status = build_live_korea_market_status(snapshot)
    data = getKoreaDashboardData({"markets": market_filter, "limit": 12, "market_status": live_market_status})
    all_scores = [
        score
        for score in data.get("scores", [])
        if getattr(score, "total_score", 0) >= min_score and getattr(score, "recommendation_grade", "") in grade_filter
    ]
    all_scores = sorted(all_scores, key=lambda row: getattr(row, "total_score", 0), reverse=True)
    data["topCandidates"] = all_scores[:12]
    top_cols = st.columns([1, 1.25, 1])
    with top_cols[0]:
        render_korea_market_regime_card(data["marketStatus"])
    with top_cols[1]:
        render_korea_top_candidates_card(data["topCandidates"])
    with top_cols[2]:
        render_korea_risk_control_panel(data)
    render_korea_recommendation_table(all_scores)
    render_korea_signal_breakdown(all_scores)
    heat_col, flow_col = st.columns([1.2, 1])
    with heat_col:
        render_korea_factor_heatmap(all_scores)
    with flow_col:
        render_korea_supply_demand_radar(all_scores)
    disc_col, value_col = st.columns([1, 1])
    with disc_col:
        render_korea_disclosure_radar(data.get("disclosures", []))
    with value_col:
        render_korea_value_up_radar(data.get("valueUpCandidates", []))
    render_korea_backtest_accuracy_panel(data["backtest"])
    render_korea_portfolio_action_queue(all_scores)
    st.caption("Mock mode: KRX/DART/KIND 실시간 어댑터가 붙기 전까지는 데모 데이터 기반입니다. 실제 매수·매도 주문 기능은 제공하지 않습니다.")
    st.markdown("</div>", unsafe_allow_html=True)


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
    kis_status = "활성" if kis_enabled() else "비활성 - KIS_APP_KEY/KIS_APP_SECRET 필요"
    st.info(f"KIS 공식 현재가 연동: {kis_status}")
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
        warning_text = exec_plan.warnings[0] if exec_plan.warnings else "유동성·비용 조건을 계속 확인합니다."
        st.html(
            f"""
            <div class="korea-card compact">
                <div class="korea-card-title">체결 품질</div>
                <div class="korea-score">{exec_plan.execution_quality_score:.0f}/100</div>
                <div class="portfolio-card-sub">{html.escape(exec_plan.recommended_order_style)}<br/>{html.escape(warning_text)}</div>
            </div>
            """
        )
    with cols[2]:
        rule_text = exit_plan.invalidation_rules[0] if exit_plan.invalidation_rules else "손절·시간 손절 규칙을 유지합니다."
        st.html(
            f"""
            <div class="korea-card compact">
                <div class="korea-card-title">청산 상태</div>
                <div class="korea-score" style="font-size:1.16rem;">{html.escape(exit_plan.status)}</div>
                <div class="portfolio-card-sub">신뢰도 {exit_plan.exit_confidence:.0f}<br/>{html.escape(rule_text)}</div>
            </div>
            """
        )
    with cols[3]:
        try:
            kill_state = get_kill_switch_state(SIGNAL_LEDGER_DB)
        except Exception as exc:
            kill_state = {"active": False, "reason": f"ledger unavailable: {exc}", "sample_size": 0, "hit_rate": None}
        state_text = "강등" if kill_state.get("active") else "정상"
        tone = "warn" if kill_state.get("active") else "good"
        st.html(
            f"""
            <div class="korea-card compact">
                <div class="korea-card-title">신호 성과</div>
                <span class="korea-badge {tone}">{html.escape(state_text)}</span>
                <div class="portfolio-card-sub">표본 {html.escape(str(kill_state.get('sample_size')))}<br/>{html.escape(str(kill_state.get("reason")))}</div>
            </div>
            """
        )


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
            <div class="fear-greed-panel" style="height: 100%; display:flex; flex-direction:column; justify-content:center;">
                <div class="section-title" style="margin-top:0;">시장 심리</div>
                <div style="font-size:1.5rem; font-weight:900; color:{fg_color}; margin-bottom:6px;">{fg_label}</div>
                <div style="font-size:1.1rem; font-weight:800; margin-bottom:8px;">{fg_score_text}</div>
                <div class="small-note" style="font-size:0.92rem; line-height:1.55;">
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

    st.markdown('<div class="section-title">오늘의 멘탈 코치</div>', unsafe_allow_html=True)

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
        st.caption(
            korea_candle_summary_text(
                latest_close,
                None if r["5d"] is None else r["5d"] / 100,
                None if r["20d"] is None else r["20d"] / 100,
                vol_ratio,
            )
        )

        summary_cols = st.columns(4)
        with summary_cols[0]:
            st.metric("최근 종가", format_price(latest_close))
        with summary_cols[1]:
            st.metric("5일 수익률", format_pct(r["5d"]))
        with summary_cols[2]:
            st.metric("20일 수익률", format_pct(r["20d"]))
        with summary_cols[3]:
            st.metric("거래량", korea_format_volume(latest_volume), "N/A" if vol_ratio is None else f"20일 평균 대비 {vol_ratio:.2f}x")

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
