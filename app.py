from __future__ import annotations

from dataclasses import dataclass
import hashlib
import html
import importlib
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

from src.config.env import (
    check_required_secrets,
    get_dart_api_key,
    get_ecos_api_key,
    get_secret,
    load_environment,
    sanitize_secret_text,
)
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
from src.korea_equity.formatting import (
    candleSummaryText as korea_candle_summary_text,
    fearGreedBand as korea_fear_greed_band,
    formatConfidence as korea_format_confidence,
    formatDirection as korea_format_direction,
    formatKRW as korea_format_krw,
    formatMarketLabel as korea_format_market_label,
    formatPercent as korea_format_percent,
    formatRegime as korea_format_regime,
    formatRecommendationGrade as korea_format_grade,
    formatSeverity as korea_format_severity,
    formatScore as korea_format_score,
    formatTradingValue as korea_format_trading_value,
    formatVolume as korea_format_volume,
    heatmapBucket as korea_heatmap_bucket,
    normalizeNegativeZero as korea_normalize_negative_zero,
)
from src.korea_equity.models import (
    KoreaMarketStatus,
)
from src.korea_equity.service import (
    getKoreaDashboardData,
    getKoreaPriceHistory,
    getKoreaSupplyDemand,
)
from src.korea_equity.explanations import explanation_for_factor, get_metric_explanation
from src.korea_equity.design_tokens import KOREA_DASHBOARD_VISIBILITY_CSS, KOREA_MODULE_VISUAL_REGISTRY
from src.korea_equity.interaction import (
    FACTOR_TO_METRIC,
    MODULE_DEFAULT_METRIC,
    MODULE_IDS,
    SelectedContext,
    formatFactorLabel,
    formatMetricLabel,
    formatModuleLabel,
    merge_context,
    parse_query_context,
    related_modules_for_metric,
    safe_external_url,
    serialize_query_context,
)
from src.institutional import (
    PortfolioRiskThresholds,
    build_data_trust_source_panel,
    build_dart_disclosure_catalyst_panel,
    build_forward_alpha_ranking_panel,
    build_fundamental_quality_panel,
    build_krw_rates_fx_dashboard,
    build_market_regime_macro_radar,
    build_portfolio_optimizer_alert_center,
    build_portfolio_risk_cockpit,
    build_smart_money_flow_short_pressure_panel,
    build_valuation_relative_cheapness_panel,
    dart_disclosure_catalyst_panel_html,
    data_trust_source_panel_html,
    forward_alpha_ranking_panel_html,
    fundamental_quality_panel_html,
    krw_rates_fx_dashboard_html,
    market_regime_macro_radar_html,
    portfolio_optimizer_alert_center_html,
    portfolio_risk_cockpit_html,
    smart_money_flow_short_pressure_panel_html,
    valuation_relative_cheapness_panel_html,
)
from src.ui.korea_os_theme import inject_korea_os_theme
from src.ui.korean_market_colors import getChartSeriesColor, getKoreanMarketColorToken
import src.institutional.market_regime as institutional_market_regime_module
import src.institutional.ui as institutional_ui_module
import src.ui.korea_os_theme as korea_os_theme_module


institutional_market_regime_module = importlib.reload(institutional_market_regime_module)
institutional_ui_module = importlib.reload(institutional_ui_module)
korea_os_theme_module = importlib.reload(korea_os_theme_module)
build_market_regime_macro_radar = institutional_market_regime_module.build_market_regime_macro_radar
dart_disclosure_catalyst_panel_html = institutional_ui_module.dart_disclosure_catalyst_panel_html
data_trust_source_panel_html = institutional_ui_module.data_trust_source_panel_html
forward_alpha_ranking_panel_html = institutional_ui_module.forward_alpha_ranking_panel_html
fundamental_quality_panel_html = institutional_ui_module.fundamental_quality_panel_html
krw_rates_fx_dashboard_html = institutional_ui_module.krw_rates_fx_dashboard_html
market_regime_macro_radar_html = institutional_ui_module.market_regime_macro_radar_html
portfolio_optimizer_alert_center_html = institutional_ui_module.portfolio_optimizer_alert_center_html
portfolio_risk_cockpit_html = institutional_ui_module.portfolio_risk_cockpit_html
smart_money_flow_short_pressure_panel_html = institutional_ui_module.smart_money_flow_short_pressure_panel_html
valuation_relative_cheapness_panel_html = institutional_ui_module.valuation_relative_cheapness_panel_html
inject_korea_os_theme = korea_os_theme_module.inject_korea_os_theme


NAVER_HEADERS = {"User-Agent": "Mozilla/5.0"}
DART_RECENT_URL = "https://dart.fss.or.kr/dsac001/mainAll.do"
DART_LIST_API_URL = "https://opendart.fss.or.kr/api/list.json"


ENV_LOAD_RESULT = load_environment()


def config_value(key: str, default: str = "") -> str:
    value = get_secret(key, required=False)
    return value if value not in (None, "") else default


HTTP_VERIFY_SSL = config_value("BNK_VERIFY_SSL", "false").strip().lower() in {"1", "true", "yes", "on"}


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


DART_API_KEY = get_dart_api_key() or ""
DART_API_TOKEN = hashlib.sha256(DART_API_KEY.encode("utf-8")).hexdigest()[:12] if DART_API_KEY else "no-key"
ECOS_API_KEY = get_ecos_api_key() or ""
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
BRIEFING_DISCLAIMER = "본 브리핑은 투자 의사결정 보조 자료이며, 매수·매도 지시나 수익 보장을 의미하지 않습니다."
BRIEFING_BANNED_PHRASES = ["무조건 매수", "수익 보장", "확정 수익"]


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
    page_title="Stance Stock Strategy",
    page_icon="SS",
    layout="wide",
    initial_sidebar_state="expanded",
)


CUSTOM_CSS = """
<style>
    :root {
        --stance-bg: #05070D;
        --stance-card-bg: #0B1020;
        --stance-card-bg-soft: #111827;
        --stance-surface-elevated: #172033;
        --stance-text-primary: #F8FAFC;
        --stance-text-secondary: #E5E7EB;
        --stance-text-tertiary: #CBD5E1;
        --stance-text-muted: #94A3B8;
        --stance-text-disabled: #64748B;
        --stance-border-subtle: rgba(148, 163, 184, 0.18);
        --stance-border-default: rgba(148, 163, 184, 0.28);
        --stance-focus-ring: #38BDF8;
        --stance-positive: #4ADE80;
        --stance-negative: #FB7185;
        --stance-warning: #FCD34D;
        --stance-info: #38BDF8;
        --stance-neutral: #CBD5E1;
        --kos-market-up: #FF4D4F;
        --kos-market-down: #3B82F6;
        --kos-market-flat: #CBD5E1;
        --kos-market-up-soft-bg: rgba(255, 77, 79, 0.12);
        --kos-market-down-soft-bg: rgba(59, 130, 246, 0.12);
        --kos-risk-critical: #F97316;
    }
    html,
    body {
        width: 100%;
        max-width: 100%;
        overflow-x: hidden;
        overscroll-behavior-x: none;
    }
    *,
    *::before,
    *::after {
        box-sizing: border-box;
    }
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(139, 92, 246, 0.14), transparent 28%),
            radial-gradient(circle at top right, rgba(56, 189, 248, 0.09), transparent 24%),
            linear-gradient(180deg, var(--stance-bg) 0%, var(--stance-card-bg) 100%);
        font-family: "Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans KR", "NanumGothic", sans-serif;
        color: var(--stance-text-primary);
        width: 100%;
        max-width: 100vw;
        overflow-x: hidden;
        overscroll-behavior-x: none;
    }
    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2rem;
        max-width: 100%;
        overflow-x: hidden;
    }
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    [data-testid="stVerticalBlock"],
    [data-testid="stHorizontalBlock"],
    [data-testid="column"],
    .element-container {
        max-width: 100%;
        min-width: 0;
    }
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"] {
        overflow-x: clip;
    }
    [data-testid="stDataFrame"],
    [data-testid="stTable"],
    [data-testid="stImage"],
    [data-testid="stPyplot"],
    iframe,
    canvas,
    svg {
        max-width: 100%;
    }
    .stApp input::placeholder,
    .stApp textarea::placeholder,
    .stApp input::-webkit-input-placeholder,
    .stApp textarea::-webkit-input-placeholder {
        color: var(--stance-text-muted) !important;
        opacity: 1 !important;
    }
    .stApp a,
    .stApp a:visited,
    .portfolio-intelligence-shell a,
    .portfolio-intelligence-shell a:visited,
    .pi-card a,
    .pi-card a:visited,
    .korea-card a,
    .korea-card a:visited,
    .korea-os-card a,
    .korea-os-card a:visited {
        color: var(--stance-info) !important;
        text-decoration-color: rgba(56, 189, 248, 0.55) !important;
    }
    .stApp a:hover,
    .portfolio-intelligence-shell a:hover,
    .pi-card a:hover,
    .korea-card a:hover,
    .korea-os-card a:hover {
        color: #BAE6FD !important;
        text-decoration-color: #BAE6FD !important;
    }
    .stApp [role="radiogroup"] label *,
    .stApp [role="radiogroup"] p,
    .stApp [data-testid="stRadio"] p,
    .stApp [data-testid="stRadio"] span {
        color: var(--stance-text-tertiary) !important;
    }
    .stApp [role="radiogroup"] label:has(input:checked) *,
    .stApp [role="radiogroup"] label:has(input:checked) p,
    .stApp [role="radiogroup"] label:has(input:checked) span {
        color: var(--stance-text-primary) !important;
    }
    .hero-title {
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin-bottom: 0.2rem;
        color: var(--stance-text-primary);
    }
    .hero-subtitle {
        color: var(--stance-text-tertiary);
        margin-bottom: 1rem;
        font-size: 0.96rem;
    }
    .metric-card {
        border-radius: 18px;
        padding: 16px 16px 14px 16px;
        background: linear-gradient(180deg, rgba(17, 24, 39, 0.96), rgba(11, 16, 32, 0.94));
        border: 1px solid var(--stance-border-default);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 16px 38px rgba(2, 6, 23, 0.26);
        min-height: 120px;
    }
    .metric-label {
        font-size: 0.84rem;
        color: var(--stance-text-secondary);
        font-weight: 700;
        margin-bottom: 6px;
    }
    .metric-name {
        font-size: 1.04rem;
        color: var(--stance-text-primary);
        font-weight: 800;
        line-height: 1.25;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 1.55rem;
        font-weight: 900;
        color: var(--stance-text-primary);
        line-height: 1.1;
    }
    .metric-change-pos {
        color: var(--kos-market-up);
        font-weight: 700;
        margin-top: 8px;
    }
    .metric-change-neg {
        color: var(--kos-market-down);
        font-weight: 700;
        margin-top: 8px;
    }
    .metric-change-flat {
        color: var(--stance-neutral);
        font-weight: 700;
        margin-top: 8px;
    }
    .section-title {
        margin-top: 0.8rem;
        margin-bottom: 0.4rem;
        color: var(--stance-text-primary);
        font-size: 1.15rem;
        font-weight: 800;
    }
    .small-note {
        color: var(--stance-text-tertiary);
        font-size: 0.85rem;
    }
    .signal-box {
        border-radius: 18px;
        background: linear-gradient(180deg, rgba(17, 24, 39, 0.96), rgba(11, 16, 32, 0.94));
        border: 1px solid var(--stance-border-default);
        padding: 14px 16px;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 16px 38px rgba(2, 6, 23, 0.26);
    }
    .signal-buy { color: var(--kos-market-up); font-weight: 900; }
    .signal-neutral { color: var(--stance-neutral); font-weight: 900; }
    .signal-sell { color: var(--kos-market-down); font-weight: 900; }
    .insight-grid {
        display: grid;
        grid-template-columns: 1.05fr 1.45fr 1.05fr;
        gap: 12px;
        margin: 0.8rem 0 1rem 0;
    }
    .insight-panel {
        border-radius: 8px;
        padding: 14px 14px 12px 14px;
        background: linear-gradient(180deg, rgba(17, 24, 39, 0.96), rgba(11, 16, 32, 0.94));
        border: 1px solid var(--stance-border-default);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 16px 38px rgba(2, 6, 23, 0.26);
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
        color: var(--stance-text-primary);
        font-size: 0.98rem;
        font-weight: 900;
        line-height: 1.2;
    }
    .insight-kicker {
        color: var(--stance-text-muted);
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
        color: var(--stance-text-primary);
        font-size: 2.25rem;
        font-weight: 950;
        line-height: 1;
    }
    .pressure-score span {
        color: var(--stance-text-tertiary);
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
        background: var(--stance-text-primary);
        box-shadow: 0 0 0 2px var(--stance-card-bg);
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
        color: var(--stance-text-secondary);
        font-size: 0.82rem;
        font-weight: 850;
        white-space: nowrap;
    }
    .row-sub {
        color: var(--stance-text-muted);
        font-size: 0.74rem;
        font-weight: 700;
    }
    .row-value {
        color: var(--stance-text-primary);
        font-size: 0.8rem;
        font-weight: 900;
        text-align: right;
        white-space: nowrap;
    }
    .mini-track {
        height: 7px;
        border-radius: 999px;
        background: rgba(148, 163, 184, 0.24);
        overflow: hidden;
    }
    .mini-fill {
        height: 100%;
        border-radius: 999px;
    }
    .rank-header {
        color: var(--stance-text-muted);
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
        color: var(--stance-text-primary);
        font-size: 0.86rem;
        font-weight: 900;
    }
    .rank-name span {
        color: var(--stance-text-muted);
        font-size: 0.74rem;
        font-weight: 800;
    }
    .thesis {
        margin-top: 10px;
        padding: 10px;
        border-radius: 8px;
        background: rgba(23, 32, 51, 0.82);
        border: 1px solid var(--stance-border-subtle);
        color: var(--stance-text-secondary);
        font-size: 0.84rem;
        font-weight: 750;
        line-height: 1.45;
    }
    .quality-banner {
        border-radius: 8px;
        padding: 12px 14px;
        background: linear-gradient(180deg, rgba(17, 24, 39, 0.96), rgba(11, 16, 32, 0.94));
        border: 1px solid var(--stance-border-default);
        margin: 0.6rem 0 1rem 0;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 16px 38px rgba(2, 6, 23, 0.26);
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
        color: var(--stance-text-primary);
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
        color: var(--stance-text-tertiary);
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
        background: linear-gradient(180deg, rgba(17, 24, 39, 0.96), rgba(11, 16, 32, 0.94));
        border: 1px solid var(--stance-border-default);
    }
    .action-panel strong {
        display: block;
        color: var(--stance-text-primary);
        font-size: 0.95rem;
        margin-bottom: 6px;
    }
    .action-panel div {
        color: var(--stance-text-secondary);
        font-size: 0.84rem;
        font-weight: 760;
        line-height: 1.5;
        margin: 3px 0;
    }
    .command-table {
        width: 100%;
        max-width: 100%;
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
        color: var(--stance-text-muted);
        font-weight: 900;
    }
    .command-table td {
        color: var(--stance-text-primary);
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
        background: rgba(148, 163, 184, 0.16);
        color: var(--stance-text-tertiary);
        font-size: 0.78rem;
        margin-right: 6px;
        margin-bottom: 6px;
    }
    .decision-report {
        border-radius: 8px;
        background: linear-gradient(180deg, rgba(17, 24, 39, 0.96), rgba(11, 16, 32, 0.94));
        border: 1px solid var(--stance-border-default);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 16px 38px rgba(2, 6, 23, 0.26);
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
        color: var(--stance-text-primary);
        font-size: 1.04rem;
        font-weight: 950;
        line-height: 1.25;
    }
    .decision-conclusion {
        color: var(--stance-text-primary);
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
        background: rgba(23, 32, 51, 0.82);
        border: 1px solid var(--stance-border-subtle);
        padding: 10px;
        min-height: 76px;
    }
    .decision-tile small {
        display: block;
        color: var(--stance-text-muted);
        font-size: 0.74rem;
        font-weight: 850;
        margin-bottom: 5px;
    }
    .decision-tile strong {
        display: block;
        color: var(--stance-text-primary);
        font-size: 0.92rem;
        font-weight: 950;
        line-height: 1.35;
    }
    .decision-tile span {
        display: block;
        color: var(--stance-text-tertiary);
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
        html,
        body,
        .stApp {
            width: 100% !important;
            max-width: 100% !important;
            overflow-x: hidden !important;
            overscroll-behavior-x: none;
        }
        .block-container {
            max-width: 100vw !important;
            padding-left: 0.75rem;
            padding-right: 0.75rem;
            overflow-x: hidden !important;
        }
        [data-testid="stMain"],
        [data-testid="stMainBlockContainer"],
        [data-testid="stVerticalBlock"],
        [data-testid="stHorizontalBlock"],
        [data-testid="column"],
        .element-container {
            width: 100% !important;
            max-width: 100% !important;
            min-width: 0 !important;
            overflow-x: hidden;
        }
        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: 0.75rem !important;
        }
        [data-testid="column"] {
            flex: 1 1 100% !important;
        }
        .metric-card,
        .signal-box,
        .decision-report,
        .insight-panel,
        .quality-banner,
        .action-panel {
            width: 100%;
            max-width: 100%;
        }
        .signal-row {
            grid-template-columns: 54px minmax(0, 1fr) 48px;
            gap: 6px;
        }
        .rank-row {
            grid-template-columns: 24px minmax(86px, 1fr) 42px 46px 50px 42px;
            gap: 5px;
        }
        .rank-header {
            font-size: 0.66rem;
        }
        .row-value {
            font-size: 0.7rem;
        }
        .row-label {
            font-size: 0.76rem;
        }
        .command-table {
            display: block;
            max-width: 100%;
            overflow-x: auto;
            overscroll-behavior-x: contain;
            -webkit-overflow-scrolling: touch;
        }
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
        width: 100%;
        max-width: 100%;
        overflow-x: hidden;
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
    .portfolio-intelligence-shell {
        border-radius: 18px;
        padding: 18px;
        margin: 1rem 0 1.2rem 0;
        background:
            radial-gradient(circle at 6% 0%, rgba(139, 92, 246, 0.28), transparent 26%),
            radial-gradient(circle at 94% 12%, rgba(56, 189, 248, 0.12), transparent 24%),
            linear-gradient(135deg, #080b16 0%, #0b1020 54%, #111827 100%);
        border: 1px solid rgba(167, 139, 250, 0.30);
        box-shadow: 0 22px 52px rgba(2, 6, 23, 0.30);
        color: #f8fafc;
        width: 100%;
        max-width: 100%;
        overflow-x: hidden;
    }
    .portfolio-intelligence-title {
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        gap: 12px;
        margin-bottom: 14px;
    }
    .portfolio-intelligence-title strong {
        display: block;
        color: #f8fafc;
        font-size: 1.22rem;
        font-weight: 900;
        line-height: 1.15;
    }
    .portfolio-intelligence-title span {
        display: block;
        color: #cbd5e1;
        font-size: 0.84rem;
        font-weight: 650;
        line-height: 1.45;
        margin-top: 4px;
    }
    .portfolio-intelligence-grid {
        display: grid;
        grid-template-columns: minmax(220px, 1fr) minmax(300px, 1.35fr) minmax(230px, 1fr);
        gap: 14px;
        align-items: stretch;
    }
    .pi-card {
        min-height: 252px;
        border-radius: 16px;
        padding: 0;
        background: linear-gradient(180deg, rgba(22, 32, 51, 0.98), rgba(17, 24, 39, 0.96));
        border: 1px solid rgba(148, 163, 184, 0.22);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), 0 16px 36px rgba(2, 6, 23, 0.24);
        overflow: hidden;
        color: #f8fafc;
    }
    .pi-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        padding: 14px 16px;
        background: linear-gradient(135deg, rgba(33, 20, 61, 0.98), rgba(59, 42, 122, 0.94));
        border-bottom: 1px solid rgba(167, 139, 250, 0.26);
    }
    .pi-card-header strong {
        color: #ffffff;
        font-size: 0.98rem;
        font-weight: 900;
        letter-spacing: 0;
    }
    .pi-card-header span {
        color: #d8b4fe;
        font-size: 0.78rem;
        font-weight: 750;
    }
    .pi-card-body {
        padding: 16px;
    }
    .pi-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 27px;
        border-radius: 999px;
        padding: 5px 10px;
        border: 1px solid rgba(148, 163, 184, 0.25);
        background: rgba(100, 116, 139, 0.18);
        color: #e2e8f0;
        font-size: 0.76rem;
        font-weight: 850;
        white-space: nowrap;
    }
    .pi-badge.risk {
        background: rgba(239, 68, 68, 0.14);
        border-color: rgba(248, 113, 113, 0.35);
        color: #fecaca;
    }
    .pi-badge.warn {
        background: rgba(245, 158, 11, 0.14);
        border-color: rgba(251, 191, 36, 0.35);
        color: #fde68a;
    }
    .pi-badge.good {
        background: rgba(34, 197, 94, 0.14);
        border-color: rgba(74, 222, 128, 0.34);
        color: #bbf7d0;
    }
    .pi-badge.market-up,
    .pi-badge.market-badge-up {
        background: var(--kos-market-up-soft-bg);
        border-color: rgba(255, 77, 79, 0.40);
        color: #ffe4e6;
    }
    .pi-badge.market-down,
    .pi-badge.market-badge-down {
        background: var(--kos-market-down-soft-bg);
        border-color: rgba(59, 130, 246, 0.40);
        color: #dbeafe;
    }
    .pi-badge.market-flat,
    .pi-badge.market-neutral,
    .pi-badge.market-badge-flat {
        background: rgba(203, 213, 225, 0.10);
        border-color: rgba(203, 213, 225, 0.28);
        color: #cbd5e1;
    }
    .pi-badge.risk-critical {
        background: rgba(249, 115, 22, 0.14);
        border-color: rgba(249, 115, 22, 0.40);
        color: #ffedd5;
    }
    .pi-badge.info {
        background: rgba(56, 189, 248, 0.14);
        border-color: rgba(56, 189, 248, 0.35);
        color: #bae6fd;
    }
    .pi-health-score {
        display: flex;
        align-items: baseline;
        gap: 8px;
        margin: 2px 0 12px 0;
    }
    .pi-health-score strong {
        color: #ffffff;
        font-size: 2.75rem;
        font-weight: 950;
        line-height: 0.95;
        font-variant-numeric: tabular-nums;
    }
    .pi-health-score span {
        color: #cbd5e1;
        font-size: 1rem;
        font-weight: 800;
    }
    .pi-progress {
        height: 11px;
        border-radius: 999px;
        background: rgba(148, 163, 184, 0.28);
        overflow: hidden;
        box-shadow: inset 0 1px 2px rgba(0,0,0,0.35);
        margin: 10px 0 14px 0;
    }
    .pi-progress-fill {
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #ef4444, #f97316);
        min-width: 2%;
    }
    .pi-reason-list {
        display: grid;
        gap: 8px;
        margin-top: 12px;
    }
    .pi-reason {
        display: flex;
        align-items: flex-start;
        gap: 8px;
        color: #cbd5e1;
        font-size: 0.84rem;
        font-weight: 700;
        line-height: 1.45;
    }
    .pi-dot {
        flex: 0 0 auto;
        width: 8px;
        height: 8px;
        border-radius: 999px;
        margin-top: 6px;
        background: #f87171;
        box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.13);
    }
    .pi-allocation-row {
        display: grid;
        grid-template-columns: 58px minmax(86px, 1fr) minmax(116px, auto);
        gap: 10px;
        align-items: center;
        min-height: 38px;
        padding: 9px 0;
        border-bottom: 1px solid rgba(148, 163, 184, 0.14);
    }
    .pi-allocation-row:last-child {
        border-bottom: 0;
    }
    .pi-asset-label {
        color: #f8fafc;
        font-size: 0.86rem;
        font-weight: 850;
        white-space: nowrap;
    }
    .pi-allocation-track {
        position: relative;
        height: 10px;
        border-radius: 999px;
        background: rgba(148, 163, 184, 0.28);
        overflow: hidden;
    }
    .pi-allocation-fill {
        height: 100%;
        border-radius: 999px;
        min-width: 2px;
    }
    .pi-allocation-value {
        text-align: right;
        color: #f8fafc;
        font-size: 0.82rem;
        font-weight: 850;
        white-space: nowrap;
        font-variant-numeric: tabular-nums;
    }
    .pi-allocation-value small {
        color: #94a3b8;
        font-size: 0.75rem;
        font-weight: 760;
    }
    .macro-heatmap-compact {
        display: grid;
        gap: 7px;
        width: 100%;
        min-width: 0;
    }
    .macro-heatmap-header,
    .macro-heatmap-row {
        display: grid;
        grid-template-columns: minmax(150px, 1.25fr) minmax(96px, 0.7fr) 78px minmax(110px, 0.75fr);
        align-items: center;
        gap: 10px;
    }
    .macro-heatmap-header {
        padding: 0 10px 5px 10px;
        color: #94a3b8;
        font-size: 0.72rem;
        font-weight: 900;
        line-height: 1.2;
    }
    .macro-heatmap-header > div:last-child {
        text-align: right;
    }
    .macro-heatmap-row {
        min-height: 48px;
        padding: 9px 10px;
        border-radius: 12px;
        background: rgba(15, 23, 42, 0.58);
        border: 1px solid rgba(148, 163, 184, 0.18);
        box-shadow: inset 3px 0 0 rgba(56, 189, 248, 0.46);
    }
    .macro-heatmap-row.good {
        box-shadow: inset 3px 0 0 rgba(74, 222, 128, 0.72);
        background: linear-gradient(90deg, rgba(34, 197, 94, 0.10), rgba(15, 23, 42, 0.58) 36%);
    }
    .macro-heatmap-row.warn {
        box-shadow: inset 3px 0 0 rgba(251, 191, 36, 0.78);
        background: linear-gradient(90deg, rgba(245, 158, 11, 0.10), rgba(15, 23, 42, 0.58) 36%);
    }
    .macro-heatmap-row.risk {
        box-shadow: inset 3px 0 0 rgba(251, 113, 133, 0.78);
        background: linear-gradient(90deg, rgba(244, 63, 94, 0.10), rgba(15, 23, 42, 0.58) 36%);
    }
    .macro-heatmap-main {
        display: grid;
        gap: 3px;
        min-width: 0;
    }
    .macro-heatmap-main strong {
        color: #f8fafc;
        font-size: 0.9rem;
        font-weight: 950;
        line-height: 1.18;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .macro-heatmap-main span {
        color: #94a3b8;
        font-size: 0.73rem;
        font-weight: 780;
        line-height: 1.25;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .macro-source-badge {
        display: inline-flex;
        align-items: center;
        min-height: 18px;
        padding: 2px 6px;
        border-radius: 999px;
        margin-left: 4px;
        border: 1px solid rgba(251, 191, 36, 0.34);
        background: rgba(245, 158, 11, 0.14);
        color: #fde68a;
        font-size: 0.68rem;
        font-weight: 900;
        vertical-align: middle;
    }
    .macro-heatmap-score {
        display: grid;
        grid-template-columns: minmax(44px, 1fr) 30px;
        gap: 7px;
        align-items: center;
        min-width: 0;
    }
    .macro-score-track {
        height: 7px;
        border-radius: 999px;
        background: rgba(148, 163, 184, 0.22);
        overflow: hidden;
    }
    .macro-score-fill {
        height: 100%;
        border-radius: 999px;
        min-width: 3px;
        background: linear-gradient(90deg, #38bdf8, #a78bfa);
    }
    .macro-heatmap-score span {
        color: #cbd5e1;
        font-size: 0.74rem;
        font-weight: 900;
        text-align: right;
        font-variant-numeric: tabular-nums;
    }
    .macro-heatmap-signal {
        display: flex;
        justify-content: center;
        min-width: 0;
    }
    .macro-heatmap-signal .pi-badge {
        min-height: 24px;
        padding: 4px 8px;
        font-size: 0.72rem;
    }
    .macro-heatmap-value {
        display: grid;
        gap: 2px;
        justify-items: end;
        min-width: 0;
        text-align: right;
    }
    .macro-heatmap-value strong {
        color: #f8fafc;
        font-size: 0.92rem;
        font-weight: 950;
        line-height: 1.1;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
    }
    .macro-heatmap-value span {
        color: #cbd5e1;
        font-size: 0.73rem;
        font-weight: 820;
        line-height: 1.15;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
    }
    .pi-rebalance-list {
        display: grid;
        gap: 10px;
    }
    .pi-rebalance-item {
        border-radius: 13px;
        padding: 12px;
        background: rgba(15, 23, 42, 0.54);
        border: 1px solid rgba(148, 163, 184, 0.18);
    }
    .pi-rebalance-top,
    .pi-rebalance-bottom {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 12px;
    }
    .pi-rebalance-asset {
        color: #f8fafc;
        font-size: 0.95rem;
        font-weight: 900;
        line-height: 1.25;
    }
    .pi-rebalance-reason {
        color: #cbd5e1;
        font-size: 0.8rem;
        font-weight: 700;
        line-height: 1.45;
        margin-top: 7px;
    }
    .pi-rebalance-amount {
        color: #ffffff;
        font-size: 1.02rem;
        font-weight: 950;
        text-align: right;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
    }
    .pi-rebalance-impact {
        color: #94a3b8;
        font-size: 0.76rem;
        font-weight: 700;
        line-height: 1.35;
        margin-top: 4px;
    }
    .pi-detail-grid {
        display: grid;
        grid-template-columns: repeat(12, minmax(0, 1fr));
        gap: 14px;
        margin: 14px 0;
        align-items: stretch;
    }
    .pi-risk-card {
        grid-column: span 5;
    }
    .pi-concentration-card {
        grid-column: span 3;
    }
    .pi-insight-card {
        grid-column: span 4;
    }
    .pi-signals-card {
        grid-column: span 12;
        min-height: auto;
    }
    .pi-card-subtitle {
        color: #cbd5e1;
        font-size: 0.78rem;
        font-weight: 720;
        line-height: 1.4;
        margin-top: -2px;
        margin-bottom: 13px;
    }
    .pi-metric-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
    }
    .pi-metric-tile {
        border-radius: 13px;
        padding: 12px;
        background: rgba(15, 23, 42, 0.58);
        border: 1px solid rgba(148, 163, 184, 0.18);
        min-height: 94px;
    }
    .pi-metric-label {
        color: #cbd5e1;
        font-size: 0.76rem;
        font-weight: 820;
        line-height: 1.2;
    }
    .pi-metric-value {
        color: #ffffff;
        font-size: 1.34rem;
        font-weight: 950;
        line-height: 1.05;
        margin-top: 7px;
        font-variant-numeric: tabular-nums;
    }
    .pi-metric-helper {
        color: #94a3b8;
        font-size: 0.72rem;
        font-weight: 720;
        line-height: 1.32;
        margin-top: 6px;
    }
    .pi-tone-good .pi-metric-value,
    .pi-value-good {
        color: var(--kos-market-up);
    }
    .pi-tone-risk .pi-metric-value,
    .pi-value-risk {
        color: var(--kos-market-down);
    }
    .pi-tone-warn .pi-metric-value,
    .pi-value-warn {
        color: #fde68a;
    }
    .pi-tone-info .pi-metric-value,
    .pi-value-info {
        color: #bae6fd;
    }
    .pi-benchmark-strip {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        margin-top: 12px;
        border-radius: 13px;
        padding: 12px 13px;
        background: rgba(34, 197, 94, 0.10);
        border: 1px solid rgba(74, 222, 128, 0.24);
    }
    .pi-benchmark-strip span {
        color: #cbd5e1;
        font-size: 0.78rem;
        font-weight: 780;
        line-height: 1.35;
    }
    .pi-benchmark-strip strong {
        color: var(--kos-market-up);
        font-size: 1.12rem;
        font-weight: 950;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
    }
    .pi-holding-list,
    .pi-signal-list,
    .pi-insight-stack {
        display: grid;
        gap: 10px;
    }
    .pi-holding-row {
        display: grid;
        grid-template-columns: 24px minmax(68px, 1fr) minmax(64px, 1.2fr) 56px;
        gap: 9px;
        align-items: center;
        padding: 8px 0;
        border-bottom: 1px solid rgba(148, 163, 184, 0.14);
    }
    .pi-holding-row:last-child {
        border-bottom: 0;
    }
    .pi-holding-rank {
        width: 22px;
        height: 22px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 999px;
        color: #ddd6fe;
        background: rgba(139, 92, 246, 0.16);
        border: 1px solid rgba(167, 139, 250, 0.24);
        font-size: 0.72rem;
        font-weight: 900;
    }
    .pi-holding-symbol {
        color: #ffffff;
        font-size: 0.82rem;
        font-weight: 920;
        line-height: 1.15;
    }
    .pi-holding-name {
        color: #94a3b8;
        font-size: 0.68rem;
        font-weight: 720;
        line-height: 1.25;
        margin-top: 2px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .pi-holding-track {
        height: 9px;
        border-radius: 999px;
        background: rgba(148, 163, 184, 0.26);
        overflow: hidden;
    }
    .pi-holding-fill {
        height: 100%;
        border-radius: 999px;
        min-width: 2px;
    }
    .pi-holding-weight {
        color: #f8fafc;
        font-size: 0.78rem;
        font-weight: 900;
        text-align: right;
        font-variant-numeric: tabular-nums;
    }
    .pi-concentration-footer {
        margin-top: 10px;
        border-radius: 12px;
        padding: 10px;
        color: #cbd5e1;
        background: rgba(239, 68, 68, 0.09);
        border: 1px solid rgba(248, 113, 113, 0.20);
        font-size: 0.76rem;
        font-weight: 740;
        line-height: 1.45;
    }
    .pi-signal-header,
    .pi-signal-row {
        display: grid;
        grid-template-columns: minmax(98px, 0.85fr) minmax(150px, 1.2fr) 82px minmax(178px, 1fr);
        gap: 12px;
        align-items: center;
    }
    .pi-signal-header {
        color: #94a3b8;
        font-size: 0.72rem;
        font-weight: 850;
        padding: 0 11px 3px 11px;
    }
    .pi-signal-row {
        border-radius: 13px;
        padding: 10px 11px;
        background: rgba(15, 23, 42, 0.44);
        border: 1px solid rgba(148, 163, 184, 0.14);
    }
    .pi-signal-code {
        color: #ffffff;
        font-size: 0.88rem;
        font-weight: 930;
        font-variant-numeric: tabular-nums;
    }
    .pi-signal-name {
        color: #cbd5e1;
        font-size: 0.8rem;
        font-weight: 760;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .pi-signal-change {
        text-align: right;
        font-size: 0.86rem;
        font-weight: 930;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
    }
    .pi-signal-badge {
        justify-self: start;
        max-width: 100%;
        color: #cbd5e1;
        background: rgba(100, 116, 139, 0.18);
        border: 1px solid rgba(148, 163, 184, 0.24);
        border-radius: 999px;
        padding: 5px 10px;
        font-size: 0.76rem;
        font-weight: 820;
        line-height: 1.25;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .pi-insight-block {
        border-radius: 13px;
        padding: 12px;
        background: rgba(15, 23, 42, 0.52);
        border: 1px solid rgba(148, 163, 184, 0.16);
    }
    .pi-insight-label {
        color: #d8b4fe;
        font-size: 0.72rem;
        font-weight: 900;
        line-height: 1.2;
        margin-bottom: 7px;
    }
    .pi-insight-text {
        color: #f8fafc;
        font-size: 0.88rem;
        font-weight: 820;
        line-height: 1.5;
    }
    .pi-insight-text.muted {
        color: #cbd5e1;
        font-size: 0.8rem;
        font-weight: 730;
    }
    .pi-insight-block.action {
        background: rgba(245, 158, 11, 0.11);
        border-color: rgba(251, 191, 36, 0.25);
    }
    @media (max-width: 900px) {
        .portfolio-intelligence-shell {
            padding: 14px;
        }
        .portfolio-intelligence-title {
            align-items: flex-start;
            flex-direction: column;
        }
        .pi-card {
            min-height: auto;
        }
        .portfolio-intelligence-grid {
            grid-template-columns: 1fr;
        }
        .pi-detail-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .pi-risk-card,
        .pi-concentration-card,
        .pi-insight-card,
        .pi-signals-card {
            grid-column: span 2;
        }
    }
    @media (max-width: 560px) {
        .portfolio-intelligence-shell {
            border-radius: 14px;
            padding: 12px;
        }
        .pi-card-header,
        .pi-card-body {
            padding: 13px;
        }
        .pi-allocation-row {
            grid-template-columns: 48px minmax(72px, 1fr);
        }
        .pi-allocation-value {
            grid-column: 1 / -1;
            text-align: left;
        }
        .macro-heatmap-header {
            display: none;
        }
        .macro-heatmap-row {
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 8px 10px;
            align-items: start;
        }
        .macro-heatmap-main {
            grid-column: 1 / 2;
        }
        .macro-heatmap-score {
            grid-column: 1 / 2;
            grid-template-columns: minmax(80px, 1fr) 30px;
            max-width: 180px;
        }
        .macro-heatmap-signal {
            grid-column: 2 / 3;
            grid-row: 1 / 2;
            justify-content: flex-end;
        }
        .macro-heatmap-value {
            grid-column: 2 / 3;
            grid-row: 2 / 3;
        }
        .pi-rebalance-top,
        .pi-rebalance-bottom {
            flex-direction: column;
            align-items: stretch;
        }
        .pi-rebalance-amount {
            text-align: left;
        }
        .pi-detail-grid {
            grid-template-columns: 1fr;
        }
        .pi-risk-card,
        .pi-concentration-card,
        .pi-insight-card,
        .pi-signals-card {
            grid-column: 1 / -1;
        }
        .pi-metric-grid {
            grid-template-columns: 1fr;
        }
        .pi-benchmark-strip {
            align-items: flex-start;
            flex-direction: column;
        }
        .pi-holding-row {
            grid-template-columns: 24px minmax(70px, 1fr) 56px;
        }
        .pi-holding-track {
            grid-column: 2 / -1;
        }
        .pi-signal-header {
            display: none;
        }
        .pi-signal-row {
            grid-template-columns: 1fr auto;
            gap: 7px 10px;
        }
        .pi-signal-name,
        .pi-signal-badge {
            grid-column: 1 / -1;
        }
        .pi-signal-change {
            text-align: right;
        }
    }
    .watchlist-strip {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        max-width: 100%;
        overscroll-behavior-x: contain;
        -webkit-overflow-scrolling: touch;
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
    .korea-os-shell {
        border-radius: 18px;
        padding: 18px;
        margin: 18px 0;
        background:
            radial-gradient(circle at 8% 0%, rgba(139, 92, 246, 0.32), transparent 25%),
            radial-gradient(circle at 92% 10%, rgba(56, 189, 248, 0.14), transparent 24%),
            linear-gradient(135deg, #080b16 0%, #0b1020 54%, #111827 100%);
        border: 1px solid rgba(167, 139, 250, 0.34);
        box-shadow: 0 22px 52px rgba(2, 6, 23, 0.28);
        color: #f8fafc;
        overflow-x: hidden;
    }
    .korea-os-hero {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 14px;
        padding-bottom: 14px;
        border-bottom: 1px solid rgba(196, 181, 253, 0.18);
        margin-bottom: 14px;
    }
    .korea-os-hero strong {
        display: block;
        color: #ffffff;
        font-size: 1.34rem;
        font-weight: 950;
        line-height: 1.15;
    }
    .korea-os-hero span {
        display: block;
        color: #cbd5e1;
        font-size: 0.86rem;
        font-weight: 720;
        line-height: 1.5;
        margin-top: 5px;
    }
    .korea-os-nav {
        display: flex;
        flex-wrap: wrap;
        gap: 7px;
        margin: 0 0 15px 0;
    }
    .korea-os-nav a {
        text-decoration: none;
        color: #ddd6fe;
        border-radius: 999px;
        padding: 5px 9px;
        font-size: 0.72rem;
        font-weight: 850;
        background: rgba(88, 28, 135, 0.34);
        border: 1px solid rgba(196, 181, 253, 0.22);
    }
    .korea-os-grid {
        display: grid;
        grid-template-columns: repeat(12, minmax(0, 1fr));
        gap: 14px;
        align-items: stretch;
    }
    .korea-os-span-4 { grid-column: span 4; }
    .korea-os-span-5 { grid-column: span 5; }
    .korea-os-span-6 { grid-column: span 6; }
    .korea-os-span-7 { grid-column: span 7; }
    .korea-os-span-8 { grid-column: span 8; }
    .korea-os-span-12 { grid-column: span 12; }
    .korea-os-card {
        min-height: 100%;
        border-radius: 15px;
        background: linear-gradient(180deg, rgba(24, 31, 52, 0.98), rgba(15, 23, 42, 0.95));
        border: 1px solid rgba(148, 163, 184, 0.22);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), 0 14px 34px rgba(2, 6, 23, 0.22);
        overflow: hidden;
    }
    .korea-os-card-head {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 12px;
        padding: 14px 16px;
        background: linear-gradient(135deg, rgba(33, 20, 61, 0.96), rgba(59, 42, 122, 0.88));
        border-bottom: 1px solid rgba(167, 139, 250, 0.25);
    }
    .korea-os-card-title {
        color: #ffffff;
        font-size: 0.98rem;
        font-weight: 950;
        line-height: 1.2;
    }
    .korea-os-card-desc {
        color: #cbd5e1;
        font-size: 0.76rem;
        font-weight: 720;
        line-height: 1.45;
        margin-top: 4px;
    }
    .korea-os-card-body {
        padding: 14px;
    }
    .korea-os-step-row {
        display: grid;
        grid-template-columns: 36px minmax(106px, 0.86fr) 92px 64px minmax(112px, 0.9fr) minmax(180px, 1.35fr);
        gap: 10px;
        align-items: center;
        padding: 11px 0;
        border-bottom: 1px solid rgba(148, 163, 184, 0.14);
    }
    .korea-os-step-row:last-child {
        border-bottom: 0;
    }
    .korea-os-step-num {
        width: 28px;
        height: 28px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 999px;
        color: #ddd6fe;
        font-size: 0.78rem;
        font-weight: 950;
        background: rgba(139, 92, 246, 0.20);
        border: 1px solid rgba(167, 139, 250, 0.28);
    }
    .korea-os-label {
        color: #f8fafc;
        font-size: 0.84rem;
        font-weight: 900;
        line-height: 1.25;
    }
    .korea-os-muted {
        color: #94a3b8;
        font-size: 0.73rem;
        font-weight: 720;
        line-height: 1.38;
        margin-top: 3px;
    }
    .korea-os-score {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 48px;
        border-radius: 999px;
        padding: 5px 9px;
        color: #ffffff;
        background: rgba(139, 92, 246, 0.18);
        border: 1px solid rgba(167, 139, 250, 0.24);
        font-size: 0.8rem;
        font-weight: 950;
        font-variant-numeric: tabular-nums;
    }
    .korea-os-reason {
        color: #cbd5e1;
        font-size: 0.78rem;
        font-weight: 730;
        line-height: 1.42;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .korea-os-metrics {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
    }
    .korea-os-metrics.three {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .korea-os-metric {
        border-radius: 13px;
        padding: 12px;
        background: rgba(15, 23, 42, 0.52);
        border: 1px solid rgba(148, 163, 184, 0.17);
        min-height: 86px;
    }
    .korea-os-metric small {
        display: block;
        color: #cbd5e1;
        font-size: 0.74rem;
        font-weight: 850;
    }
    .korea-os-metric strong {
        display: block;
        color: #ffffff;
        font-size: 1.12rem;
        font-weight: 950;
        line-height: 1.1;
        margin-top: 8px;
        font-variant-numeric: tabular-nums;
    }
    .korea-os-callout {
        margin-top: 11px;
        border-radius: 13px;
        padding: 11px 12px;
        background: rgba(245, 158, 11, 0.10);
        border: 1px solid rgba(251, 191, 36, 0.22);
        color: #fde68a;
        font-size: 0.8rem;
        font-weight: 780;
        line-height: 1.45;
    }
    .korea-os-thesis-grid {
        display: grid;
        gap: 10px;
    }
    .korea-os-thesis {
        border-radius: 13px;
        padding: 12px;
        background: rgba(15, 23, 42, 0.52);
        border: 1px solid rgba(148, 163, 184, 0.16);
    }
    .korea-os-thesis b {
        display: block;
        color: #d8b4fe;
        font-size: 0.76rem;
        margin-bottom: 7px;
    }
    .korea-os-thesis span {
        color: #f8fafc;
        font-size: 0.82rem;
        font-weight: 760;
        line-height: 1.5;
    }
    .korea-os-scenario-row,
    .korea-os-alert-row,
    .korea-os-review-row {
        display: grid;
        grid-template-columns: minmax(130px, 1fr) 92px 76px minmax(120px, 1fr) minmax(170px, 1.2fr);
        gap: 10px;
        align-items: center;
        padding: 10px 0;
        border-bottom: 1px solid rgba(148, 163, 184, 0.14);
    }
    .korea-os-scenario-row:last-child,
    .korea-os-alert-row:last-child,
    .korea-os-review-row:last-child {
        border-bottom: 0;
    }
    .korea-os-mini-table .korea-table {
        min-width: 620px;
    }
    .korea-safety-callout {
        border-radius: 13px;
        padding: 12px 13px;
        margin-top: 12px;
        color: #e2e8f0;
        background: rgba(56, 189, 248, 0.10);
        border: 1px solid rgba(56, 189, 248, 0.24);
        font-size: 0.8rem;
        font-weight: 760;
        line-height: 1.45;
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
    .korea-context-bar,
    .korea-explanation-panel {
        border-radius: 12px;
        padding: 12px 14px;
        margin: 10px 0;
        background: rgba(15, 23, 42, 0.92);
        border: 1px solid rgba(196, 181, 253, 0.24);
        color: #e2e8f0;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04), 0 12px 28px rgba(2, 6, 23, 0.2);
    }
    .korea-context-bar strong,
    .korea-explanation-panel strong {
        color: #ffffff;
        font-weight: 950;
    }
    .korea-context-meta,
    .korea-explain-muted {
        color: #cbd5e1;
        font-size: 0.8rem;
        font-weight: 720;
        line-height: 1.5;
    }
    .korea-selected-card {
        outline: 2px solid rgba(167, 139, 250, 0.8);
        box-shadow: 0 0 0 4px rgba(167, 139, 250, 0.12);
    }
    .korea-mini-link {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 4px 9px;
        margin: 3px 4px 3px 0;
        background: rgba(88, 28, 135, 0.58);
        color: #e9d5ff;
        border: 1px solid rgba(196, 181, 253, 0.24);
        font-size: 0.72rem;
        font-weight: 850;
    }
    .korea-row-card {
        border-radius: 10px;
        padding: 10px;
        margin: 7px 0;
        background: rgba(30, 41, 59, 0.58);
        border: 1px solid rgba(196, 181, 253, 0.13);
    }
    .korea-row-card.selected {
        border-color: rgba(167, 139, 250, 0.88);
        background: rgba(76, 29, 149, 0.34);
    }
    .korea-table-wrap {
        width: 100%;
        max-width: 100%;
        max-height: 620px;
        overflow-x: auto;
        overflow-y: auto;
        overscroll-behavior-x: contain;
        -webkit-overflow-scrolling: touch;
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
    .korea-table td.num,
    .korea-table th.num {
        text-align: right;
        font-variant-numeric: tabular-nums;
    }
    .korea-table td.text {
        text-align: left;
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
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
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
    .heatmap-strong { background: rgba(255, 77, 79, 0.90); }
    .heatmap-good { background: rgba(255, 122, 122, 0.82); }
    .heatmap-neutral { background: rgba(139, 92, 246, 0.72); }
    .heatmap-weak { background: rgba(245, 158, 11, 0.88); }
    .heatmap-risk { background: rgba(59, 130, 246, 0.88); }
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
        .korea-os-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .korea-os-span-4,
        .korea-os-span-5,
        .korea-os-span-6,
        .korea-os-span-7,
        .korea-os-span-8,
        .korea-os-span-12 {
            grid-column: span 2;
        }
        .korea-os-step-row,
        .korea-os-scenario-row,
        .korea-os-alert-row,
        .korea-os-review-row {
            grid-template-columns: 36px minmax(120px, 1fr) minmax(90px, auto);
        }
        .korea-os-step-row > :nth-child(n+4),
        .korea-os-scenario-row > :nth-child(n+4),
        .korea-os-alert-row > :nth-child(n+4),
        .korea-os-review-row > :nth-child(n+4) {
            grid-column: 2 / -1;
        }
        .korea-module-meta {
            white-space: normal;
        }
    }
    @media (max-width: 560px) {
        .portfolio-shell,
        .portfolio-card,
        .portfolio-head,
        .korea-card,
        .fear-greed-panel {
            width: 100%;
            max-width: 100%;
        }
        .portfolio-shell.korea-shell {
            padding: 12px;
            border-radius: 12px;
        }
        .korea-metric-grid {
            grid-template-columns: 1fr;
        }
        .korea-os-shell {
            padding: 12px;
            border-radius: 14px;
        }
        .korea-os-hero {
            flex-direction: column;
        }
        .korea-os-grid {
            grid-template-columns: 1fr;
        }
        .korea-os-span-4,
        .korea-os-span-5,
        .korea-os-span-6,
        .korea-os-span-7,
        .korea-os-span-8,
        .korea-os-span-12 {
            grid-column: 1 / -1;
        }
        .korea-os-metrics,
        .korea-os-metrics.three {
            grid-template-columns: 1fr;
        }
        .korea-table {
            min-width: 640px;
        }
    }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
st.markdown(KOREA_DASHBOARD_VISIBILITY_CSS, unsafe_allow_html=True)
inject_korea_os_theme()


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
    source = SOURCE_LABELS.get(snap.source, snap.source or "출처 미상")
    score = snap.quality_score if snap.quality_score else 0
    return f"{source} · 품질 {score}"


SOURCE_LABELS = {
    "KIS Open API": "KIS 공식 실시간",
    "Naver Finance": "네이버 금융 장중 스냅샷",
    "Naver": "네이버 금융 장중 스냅샷",
    "FinanceDataReader": "FDR 최근 종가",
    "Alternative.me": "Alternative.me",
    "BOK ECOS": "한국은행 ECOS",
    "FRED": "FRED",
}

CURRENT_MARKET_FREQUENCIES = {"near_realtime", "realtime_official", "intraday"}
CURRENT_MARKET_SOURCES = {"KIS Open API", "Naver Finance", "Naver"}
CORE_CURRENT_KEYS = {"KOSPI", "KOSDAQ", "USD/KRW", "KR 3Y"}
SNAPSHOT_VALUE_RANGES: dict[str, tuple[float, float]] = {
    "KOSPI": (1000.0, 10000.0),
    "KOSDAQ": (300.0, 2500.0),
    "USD/KRW": (700.0, 2500.0),
    "KR 3Y": (0.0, 15.0),
    "US 10Y": (0.0, 15.0),
}


def snapshot_is_current_source(snap: Snapshot | None) -> bool:
    if snap is None:
        return False
    return snap.frequency in CURRENT_MARKET_FREQUENCIES and snap.source in CURRENT_MARKET_SOURCES


def snapshot_value_is_plausible(key: str, snap: Snapshot | None) -> bool:
    if snap is None:
        return False
    value = safe_float(snap.last_close)
    if value is None:
        return False
    low, high = SNAPSHOT_VALUE_RANGES.get(key, (0.0, float("inf")))
    return low <= value <= high


def snapshot_asof_label(snap: Snapshot | None) -> str:
    if snap is None or snap.asof is None:
        return "기준시각 확인 불가"
    try:
        stamp = pd.Timestamp(snap.asof)
        if snapshot_is_current_source(snap):
            return stamp.strftime("%m.%d %H:%M")
        return stamp.strftime("%Y.%m.%d")
    except Exception:
        return "기준시각 확인 불가"


def snapshot_metric_subtitle(snap: Snapshot | None, default_subtitle: str) -> str:
    if snap is None:
        return default_subtitle
    if snap.key in {"KOSPI", "KOSDAQ"} and not snapshot_is_current_source(snap):
        return "최근 종가"
    if snap.key == "USD/KRW" and not snapshot_is_current_source(snap):
        return "최근 환율"
    if snap.key in {"KR 3Y", "US 10Y"} and not snapshot_is_current_source(snap):
        return "최근 수치"
    return default_subtitle


def append_snapshot_warning(snap: Snapshot, message: str) -> Snapshot:
    warnings = list(snap.warnings or [])
    if message not in warnings:
        warnings.append(message)
    snap.warnings = warnings
    return snap


def prefer_current_market_snapshot(key: str, fallback_snap: Snapshot | None, live_snap: Snapshot | None) -> Snapshot | None:
    if snapshot_is_current_source(live_snap) and snapshot_value_is_plausible(key, live_snap):
        return live_snap
    if fallback_snap is not None:
        if key in CORE_CURRENT_KEYS:
            append_snapshot_warning(fallback_snap, "장중 현재가 소스 연결 실패: 최근 종가/최근 수치 기준")
            fallback_snap.quality_score = min(fallback_snap.quality_score or 0, 76)
        return fallback_snap
    return live_snap


def snapshot_source_label(snap: Snapshot) -> str:
    source = SOURCE_LABELS.get(snap.source, snap.source or "출처 미상")
    score = snap.quality_score if snap.quality_score else 0
    parts = [source]
    if snap.key in CORE_CURRENT_KEYS and not snapshot_is_current_source(snap):
        parts.append("실시간 아님")
    parts.append(snapshot_asof_label(snap))
    parts.append(f"품질 {score}")
    return " · ".join(part for part in parts if part)


ACTION_LABELS_KO = {
    "Strong Buy": "강한 검토 후보",
    "Buy on Pullback": "눌림목 검토",
    "Accumulate Small": "소액 분할 검토",
    "Hold / Watch": "보유·관찰",
    "Watch Only": "관찰만",
    "Trim": "비중 축소 검토",
    "Sell / Avoid": "회피",
}


def action_label_ko(action: str | None) -> str:
    return ACTION_LABELS_KO.get(action or "", action or "관찰")


SEVERITY_LABELS_KO = {
    "Low": "낮음",
    "Medium": "주의",
    "High": "높음",
    "Critical": "심각",
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
    return "사용 불가", "#2563eb"


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
            warnings.append("단기 데이터 시점 지연")
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
        errors.append("가격 수치 결측")
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
            warnings.append("전일 대비 등락률 차이")

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
            return None, f"KIS token 응답 오류: {message}"
        token = payload.get("access_token")
        if not token:
            return None, "KIS token 응답에 access_token 없음"
        return str(token), None
    except Exception as exc:
        return None, f"KIS token 요청 실패: {exc}"


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


@st.cache_data(ttl=20, show_spinner=False)
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
        fallback_snap = data.get(name)
        live_snap = live_data.get(name)
        preferred_snap = prefer_current_market_snapshot(name, fallback_snap, live_snap)
        if preferred_snap is None:
            continue
        if preferred_snap is live_snap:
            data[name] = apply_snapshot_quality(
                Snapshot(
                    key=name,
                    display_name=live_snap.display_name,
                    last_close=live_snap.last_close,
                    prev_close=live_snap.prev_close if live_snap.prev_close is not None else (fallback_snap.prev_close if fallback_snap else None),
                    change=live_snap.change if live_snap.change is not None else (fallback_snap.change if fallback_snap else None),
                    change_pct=live_snap.change_pct if live_snap.change_pct is not None else (fallback_snap.change_pct if fallback_snap else None),
                    asof=live_snap.asof,
                    raw=fallback_snap.raw if fallback_snap else live_snap.raw,
                    source=live_snap.source,
                    unit=live_snap.unit,
                    frequency=live_snap.frequency,
                    is_fallback=live_snap.is_fallback,
                )
            )
        else:
            data[name] = preferred_snap

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
    score = 0.0
    notes: list[str] = []
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
            notes.append(f"{name} trend positive")
            return 0.9
        if r20 < 0 and r60 < 0:
            notes.append(f"{name} trend negative")
            return -0.9
        return 0.0

    score += slope_bonus(kospi, "KOSPI")
    score += slope_bonus(kosdaq, "KOSDAQ")

    if usdkrw and usdkrw.change_pct is not None:
        if usdkrw.change_pct > 0:
            score -= 0.5
            notes.append("USD/KRW rising pressure")
        elif usdkrw.change_pct < 0:
            score += 0.3
            notes.append("USD/KRW easing")

    if us10y and us10y.change_pct is not None:
        if us10y.change_pct > 0:
            score -= 0.35
            notes.append("US 10Y yield pressure")
        elif us10y.change_pct < 0:
            score += 0.2
            notes.append("US 10Y yield easing")

    if kr3y and kr3y.change_pct is not None:
        if kr3y.change_pct > 0:
            score -= 0.2
            notes.append("KR 3Y yield pressure")
        elif kr3y.change_pct < 0:
            score += 0.1
            notes.append("KR 3Y yield easing")

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
        return "Neutral", 50.0, ["가격 데이터 없음"]
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
        direction = "positive" if value >= threshold else "negative"
        reasons.append(f"{label} {direction}({value:+.2f}%)")

    add_weight(ret["5d"], 7.5, "5D trend")
    add_weight(ret["20d"], 12.0, "20D trend")
    add_weight(ret["60d"], 9.0, "60D trend")

    if len(close) >= 20:
        ma5 = float(close.tail(5).mean())
        ma20 = float(close.tail(20).mean())
        last = float(close.iloc[-1])
        if last > ma5:
            score += 4.0
            reasons.append("close above 5D average")
        else:
            score -= 3.0
            reasons.append("close below 5D average")
        if last > ma20:
            score += 6.0
            reasons.append("close above 20D average")
        else:
            score -= 5.0
            reasons.append("close below 20D average")

    if volume is not None and len(volume) >= 20:
        vol_avg = volume.tail(20).mean()
        vol_ratio = float(volume.iloc[-1] / vol_avg) if vol_avg not in (0, np.nan) else None
        if vol_ratio is not None:
            if vol_ratio >= 1.2:
                score += 6.0
                reasons.append(f"volume confirmation({vol_ratio:.2f}x)")
            elif vol_ratio <= 0.85:
                score -= 2.5
                reasons.append(f"volume weak({vol_ratio:.2f}x)")

    if kospi_close is not None and len(close) >= 21 and len(kospi_close) >= 21:
        rs = relative_strength(close, kospi_close)
        if rs is not None:
            score += max(min(rs, 15.0), -15.0) / 15.0 * 10.0
            reasons.append(f"relative strength vs KOSPI {rs:+.2f}%p")

    if len(close) >= 20:
        recent = close.tail(20)
        vol = float(recent.pct_change().dropna().std() * math.sqrt(252) * 100)
        if vol >= 80:
            score -= 4.0
            reasons.append(f"high volatility({vol:.1f}%)")
        elif vol <= 35:
            score += 2.0
            reasons.append(f"stable volatility({vol:.1f}%)")

    score += market_score * 2.0
    if market_score > 0:
        reasons.append("market pressure positive")
    elif market_score < 0:
        reasons.append("market pressure negative")

    score = float(max(0.0, min(100.0, score)))
    if score >= 60:
        label = "Buy"
    elif score <= 40:
        label = "Sell"
    else:
        label = "Neutral"
    return label, score, reasons[:6]
def coach_message(market_score: float, signal: str, stock_score: float, volatility_flag: str) -> str:
    if market_score >= 1.0 and signal == "Buy":
        return "Trend is supportive. Prefer staged review with clear risk limits."
    if market_score <= -1.0 and signal == "Sell":
        return "Defense comes first. Keep cash and review exits before new exposure."
    if volatility_flag == "high":
        return "Volatility is elevated. Reduce size and keep stop rules strict."
    if stock_score >= 50:
        return "The setup is acceptable, but wait for price and disclosure confirmation."
    return "Market and stock signals are weak. Observation is preferable."
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
    subtitle = snapshot_metric_subtitle(snap, subtitle)
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
        return "", "", f"브리핑 시스템 파일을 찾을 수 없습니다: {', '.join(missing)}"

    schema_text = read_text_asset(OUTPUT_SCHEMA_FILE)
    if not schema_text:
        return "", "", "output_schema.md를 찾을 수 없습니다."

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
            errors.append(f"지원되지 않는 확정 표현 포함: {phrase}")
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
        return "N/A"
    if snap.change is not None:
        if snap.change > 0:
            return "상승"
        if snap.change < 0:
            return "하락"
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
        missing.append("KOSPI")
    if kosdaq is None or kosdaq.last_close is None:
        missing.append("KOSDAQ")
    if usdkrw is None or usdkrw.last_close is None:
        missing.append("USD/KRW")
    if fg_current is None:
        missing.append("fear_greed")
    if fg_weekly is None:
        missing.append("fear_greed_weekly")
    if base_rate_snap is None or base_rate_snap.last_close is None:
        missing.append("base_rate")
    if kr3y is None or kr3y.last_close is None:
        missing.append("KR 3Y")
    if recent_disclosures.empty:
        missing.append("recent_disclosures")
    if ecos_error:
        missing.append("ECOS error")

    base_rate_status = infer_base_rate_status(base_rate_snap)
    disclosure_text = " / ".join(disclosure_titles) if disclosure_titles else "N/A"
    missing_text = " / ".join(missing) if missing else "none"
    regime_context = build_market_regime_output(snapshot)
    quality_score, quality_status, _, quality_messages = aggregate_data_quality(snapshot, valid_rows)
    try:
        kill_state = get_kill_switch_state(SIGNAL_LEDGER_DB)
    except Exception:
        kill_state = {"active": False, "reason": "신호 원장 사용 불가", "sample_size": 0, "hit_rate": None}

    structured_context = {
        "ref_date": ref_date,
        "data_quality": {"score": quality_score, "status": quality_status, "messages": quality_messages},
        "market": {
            "kospi": snapshot_to_context(kospi),
            "kosdaq": snapshot_to_context(kosdaq),
            "usdkrw": snapshot_to_context(usdkrw),
            "kr3y": snapshot_to_context(kr3y),
            "fear_greed": {"value": fg_current, "weekly": fg_weekly, "classification": fg_label, "source": "Alternative.me", "unit": "score"},
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
        "[input data]",
        f"- KOSPI: {format_briefing_number(safe_float(kospi.last_close) if kospi else None)} ({format_briefing_number(safe_float(kospi.change_pct) if kospi and kospi.change_pct is not None else None, 2, '%', True)})" if kospi and kospi.last_close is not None else "- KOSPI: N/A (N/A)",
        f"- KOSDAQ: {format_briefing_number(safe_float(kosdaq.last_close) if kosdaq else None)} ({format_briefing_number(safe_float(kosdaq.change_pct) if kosdaq and kosdaq.change_pct is not None else None, 2, '%', True)})" if kosdaq and kosdaq.last_close is not None else "- KOSDAQ: N/A (N/A)",
        f"- USD/KRW: {format_briefing_number(safe_float(usdkrw.last_close) if usdkrw else None, 2, '원')} ({format_briefing_number(safe_float(usdkrw.change) if usdkrw and usdkrw.change is not None else None, 2, '원', True)})" if usdkrw and usdkrw.last_close is not None else "- USD/KRW: N/A (N/A)",
        f"- Fear/Greed: {format_briefing_number(fg_current, 0)} ({fg_label}) / weekly: {format_briefing_number(fg_weekly, 0)}",
        f"- Base rate: {format_briefing_number(safe_float(base_rate_snap.last_close) if base_rate_snap else None, 2, '%')} ({base_rate_status})" if base_rate_snap and base_rate_snap.last_close is not None else "- Base rate: N/A (N/A)",
        f"- KR 3Y: {format_briefing_number(safe_float(kr3y.last_close) if kr3y else None, 2, '%')}" if kr3y and kr3y.last_close is not None else "- KR 3Y: N/A",
        f"- Reference date: {ref_date}",
        f"- Recent disclosures: {disclosure_text}",
        f"- Signal outcome warning: {'active' if kill_state.get('active') else 'normal'} ({kill_state.get('reason')})",
        "",
        "[missing items]",
        f"- {missing_text}",
        "",
        "[validated JSON context]",
        json.dumps(structured_context, ensure_ascii=False, indent=2),
        "",
        "Output request: write today market briefing using output_schema.md format.",
    ]
    return "\n".join(lines), missing


def call_openai_briefing(system_text: str, user_text: str) -> str:
    if not OPENAI_API_KEY or OPENAI_API_KEY == "YOUR_API_KEY":
        raise RuntimeError("OPENAI_API_KEY가 .env 또는 Streamlit Secrets에 설정되어 있지 않습니다.")

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
        '<div class="small-note">브리핑 생성 버튼을 누르면 구조화된 데이터 컨텍스트와 지침 파일을 읽어 오늘의 시장 브리핑을 생성합니다. 검증에 실패하면 저장하지 않고 사유를 표시합니다.</div>',
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
        st.caption(f"마지막 조회: {last_refresh}")

    if prompt_error:
        st.error(prompt_error)

    if generate_clicked and not prompt_error:
        with st.spinner("생성 중..."):
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
    if not ecos_key:
        return pd.DataFrame(), "ECOS API 키가 설정되지 않았습니다. ENV_FILE_PATH, Streamlit Secrets 또는 서버 환경변수를 확인하세요."

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
        return pd.DataFrame(), "ECOS API 호출 실패: " + sanitize_secret_text(str(exc))


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
    change_text = "전기 대비 N/A"
    change_class_name = "flat"
    if change_pct is not None:
        change_text = f"전기 대비 {change_pct:+.2f}%"
        change_class_name = change_class(change_pct)

    value_text = format_ecos_value(safe_float(snap.last_close), unit)
    value_color = color_for_change(snap.change if snap.change is not None else snap.change_pct)
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{html.escape(title)}</div>
            <div class="metric-name">{html.escape(subtitle)}</div>
            <div class="metric-value" style="color:{value_color}">{html.escape(value_text)}</div>
            <div class="metric-change-{change_class_name}">{html.escape(change_text)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def ecos_market_view(df: pd.DataFrame) -> tuple[list[tuple[str, Snapshot, str]], str]:
    specs = [
        ("기준금리", ["기준금리", "base rate", "policy rate", "call rate"], "한국은행"),
        ("GDP", ["gdp", "국내총생산", "실질gdp"], "성장"),
        ("CPI", ["cpi", "소비자물가", "consumer price"], "물가"),
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
            subtitle = time_text or subtitle_prefix or "최신 수치"
            cards.append((title, snap, subtitle))
            value_text = f"{snap.last_close:,.2f}" if abs(float(snap.last_close)) >= 1 else f"{snap.last_close:.4f}"
            summary_bits.append(f"{title} {value_text}{(' ' + unit_text) if unit_text else ''}")
        else:
            cards.append((title, snap, "데이터 없음"))

    summary = " / ".join(summary_bits[:3]) if summary_bits else "ECOS 최신 값을 불러오지 못했습니다."
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

    if rate is None and gdp is None and cpi is None and m2 is None and external is None:
        return "ECOS 핵심 지표를 불러왔지만 해석 가능한 값이 충분하지 않습니다."

    views: list[str] = []
    if rate is not None:
        views.append("금리 부담 높음" if rate >= 3.0 else "금리 부담 완화" if rate <= 2.0 else "금리 중립")
    if cpi is not None:
        views.append("물가 압력 높음" if cpi >= 118 else "물가 중립")
    if m2 is not None:
        views.append("유동성 풍부" if m2 >= 4_000_000 else "유동성 보통")
    if gdp is not None:
        views.append("성장 모멘텀 확인" if gdp >= 90 else "성장 모멘텀 점검")
    if external is not None:
        views.append("대외수지 양호" if external >= 0 else "대외수지 약세")
    return " / ".join(views)


def render_ecos_cards(refresh_token: int) -> None:
    ecos_df, ecos_error = load_ecos_key_statistics(refresh_token, ECOS_API_KEY)
    st.markdown('<div class="section-title">한국은행 ECOS 핵심 매크로</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="small-note">기준금리, GDP, CPI, M2, 무역수지를 한 번에 캐싱해 현재 시장의 거시 압력을 빠르게 읽습니다.</div>',
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
    fig, ax = plt.subplots(figsize=(11, 2.15))
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#0f172a")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 1)
    ax.barh(0.5, 100, color="#334155", height=0.30, edgecolor="none", alpha=0.86)

    if score is not None:
        safe_score = max(0, min(100, float(score)))
        ax.barh(0.5, safe_score, color=color, height=0.28, edgecolor="none")
        ax.scatter([safe_score], [0.5], s=120, color=color, edgecolors="#f8fafc", linewidths=1.2, zorder=5)
        ax.text(safe_score, 0.90, f"{safe_score:.0f}", ha="center", va="bottom", fontsize=12, weight="bold", color=color)

    bands = [
        (0, 24, "#dc2626", "극단 공포"),
        (25, 44, "#f97316", "공포"),
        (45, 55, "#6b7280", "중립"),
        (56, 74, "#a3e635", "탐욕"),
        (75, 100, "#16a34a", "극단 탐욕"),
    ]
    for band_start, band_end, band_color, text_label in bands:
        ax.axvspan(band_start, band_end, color=band_color, alpha=0.10)
        ax.text((band_start + band_end) / 2, 0.12, text_label, ha="center", va="center", fontsize=8.8, color="#dbeafe")

    ax.text(0, 1.08, "공포·탐욕 지수", ha="left", va="bottom", fontsize=13, weight="bold", color="#f8fafc")
    ax.text(100, 1.08, label, ha="right", va="bottom", fontsize=11, weight="bold", color=color)
    ax.set_yticks([])
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.tick_params(axis="x", labelsize=9.5, colors="#dbeafe")
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.tight_layout()
    return fig


def render_stock_preview(name: str, code: str, snap: Snapshot, button_key: str, insight: dict[str, Any] | None = None) -> bool:
    change = snap.change
    change_pct = snap.change_pct
    color = color_for_change(change if change is not None else change_pct)
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
            <div class="metric-label">{html.escape(code)}</div>
            <div class="metric-name">{html.escape(name)}</div>
            <div class="metric-value" style="color:{color}">{html.escape(format_price(snap.last_close))}</div>
            <div class="metric-change-{change_class(change if change is not None else change_pct)}">{html.escape(change_text)}</div>
            <div class="small-note" style="margin-top:8px; line-height:1.45;">
                행동 후보: <b>{html.escape(action_text)}</b> / {action_score:.0f}점<br/>
                주도력 {"N/A" if leadership is None else f"{leadership:.0f}점"} · 기대값 {"N/A" if expected_edge is None else f"{expected_edge:+.2f}%"}<br/>
                손익비 {"N/A" if rr is None else f"{rr:.2f}x"} · 품질조정 {"N/A" if qrr is None else f"{qrr:.2f}x"}<br/>
                공시 위험: {html.escape(str(disclosure_text))} · 실행 품질: {"N/A" if exec_quality is None else f"{exec_quality:.0f}점"}<br/>
                최대 검토 비중: {max_pos * 100:.1f}%
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return st.button("종목 상세 보기", key=button_key, use_container_width=True)


def render_signal_box(name: str, signal: str, score: float, reasons: list[str]) -> None:
    normalized = str(signal).lower()
    if any(token in normalized for token in ["buy", "매수", "보강"]):
        signal_class = "signal-buy"
        display_signal = "비중 보강 검토"
    elif any(token in normalized for token in ["sell", "매도", "축소", "avoid"]):
        signal_class = "signal-sell"
        display_signal = "비중 축소 검토"
    else:
        signal_class = "signal-neutral"
        display_signal = "관찰"

    reasons_html = "".join(f"<div class='small-note'>- {html.escape(str(reason))}</div>" for reason in reasons[:5])
    st.markdown(
        f"""
        <div class="signal-box">
            <div class="section-title" style="margin-top:0;">종목 신호: <span class="{signal_class}">{display_signal}</span> ({score:.0f}/100)</div>
            <div class="small-note">{html.escape(name)}</div>
            {reasons_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_return_figure(rows: list[dict[str, Any]], active_code: str | None) -> tuple[plt.Figure, str | None]:
    if not rows:
        fig, ax = plt.subplots(figsize=(10, 2))
        fig.patch.set_facecolor("#0f172a")
        ax.set_facecolor("#0f172a")
        ax.axis("off")
        ax.text(0.5, 0.5, "표시할 수익률 데이터가 없습니다.", ha="center", va="center", fontsize=12, color="#cbd5e1")
        return fig, None

    df = pd.DataFrame(rows).sort_values("return_pct", ascending=True).reset_index(drop=True)
    colors = ["#dc2626" if v >= 0 else "#2563eb" for v in df["return_pct"]]
    labels = [
        f"{name} ({code})" if code != active_code else f"선택됨 · {name} ({code})"
        for name, code in zip(df["name"], df["code"])
    ]

    fig, ax = plt.subplots(figsize=(11, max(3.4, 0.42 * len(df) + 1.0)))
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#0f172a")
    y = np.arange(len(df))
    ax.barh(y, df["return_pct"], color=colors, alpha=0.9, height=0.65)
    ax.axvline(0, color="#94a3b8", linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10, color="#cbd5e1")
    ax.set_xlabel("기간 수익률(%)", fontsize=10, color="#cbd5e1")
    ax.set_title("관심종목 기간 수익률 비교", fontsize=13, weight="bold", color="#f8fafc")
    ax.grid(axis="x", linestyle="--", alpha=0.25, color="#94a3b8")
    ax.set_axisbelow(True)

    for idx, value in enumerate(df["return_pct"]):
        ax.text(value + (0.15 if value >= 0 else -0.15), idx, f"{value:+.2f}%", va="center", ha="left" if value >= 0 else "right", fontsize=9, color="#f8fafc")

    for spine in ax.spines.values():
        spine.set_color("#334155")
    fig.tight_layout()
    return fig, df.iloc[-1]["code"] if len(df) else None


def plot_candlestick_with_volume(df: pd.DataFrame, title: str) -> plt.Figure:
    open_c, high_c, low_c, close_c, vol_c = find_ohlcv_columns(df)
    data = df.copy()
    data = data[[open_c, high_c, low_c, close_c, vol_c]].dropna()
    if data.empty:
        fig, ax = plt.subplots(figsize=(10, 4))
        fig.patch.set_facecolor("#0f172a")
        ax.set_facecolor("#0f172a")
        ax.axis("off")
        ax.text(0.5, 0.5, "선택 범위의 가격·거래량 데이터가 부족합니다.", ha="center", va="center", fontsize=12, color="#cbd5e1")
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
        candle_color = "#ef4444" if c >= o else "#60a5fa"
        ax1.vlines(dates[i], l, h, color=candle_color, linewidth=1.25, alpha=0.96)
        body_low = min(o, c)
        body_height = max(abs(c - o), 0.01)
        ax1.add_patch(
            plt.Rectangle(
                (dates[i] - width / 2, body_low),
                width,
                body_height,
                facecolor=candle_color,
                edgecolor=candle_color,
                alpha=0.88,
            )
        )
        ax2.bar(dates[i], float(row[vol_c]), color=candle_color, width=0.62, alpha=0.76)

    ax1.set_title(title, fontsize=14, weight="bold", loc="left", color="#f8fafc")
    ax1.grid(True, axis="y", linestyle="--", alpha=0.22, color="#94a3b8")
    ax1.set_ylabel("가격", fontsize=10.5, color="#dbeafe")
    ax2.set_ylabel("거래량", fontsize=10.5, color="#dbeafe")
    ax2.grid(True, axis="y", linestyle="--", alpha=0.20, color="#94a3b8")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax1.tick_params(axis="y", colors="#dbeafe", labelsize=9.5)
    ax2.tick_params(axis="x", rotation=0, colors="#dbeafe", labelsize=9)
    ax2.tick_params(axis="y", colors="#dbeafe", labelsize=9)
    for spine in [*ax1.spines.values(), *ax2.spines.values()]:
        spine.set_color("#475569")
    plt.setp(ax1.get_xticklabels(), visible=False)
    fig.tight_layout()
    return fig


def summarize_stock(code: str, name: str, history: pd.DataFrame, kospi_close: pd.Series | None, market_score: float) -> tuple[str, float, list[str], str]:
    if history.empty:
        return "관찰", 50.0, ["가격 데이터 부족"], "low"
    _, _, _, close_c, volume_c = find_ohlcv_columns(history)
    close = history[close_c].dropna()
    vol = history[volume_c].dropna() if volume_c in history.columns else pd.Series(dtype=float)
    signal, score, reasons = stock_signal(code, history, market_score, kospi_close)
    volatility_flag = "low"
    if len(close) >= 20:
        ret20 = close.pct_change().dropna().tail(20)
        vol_ann = float(ret20.std() * math.sqrt(252) * 100) if not ret20.empty else 0.0
        volatility_flag = "high" if vol_ann >= 80 else "low"
        reasons.append(f"20일 연율 변동성 {vol_ann:.1f}%")
    if len(vol) >= 20:
        ratio = float(vol.iloc[-1] / vol.tail(20).mean()) if float(vol.tail(20).mean()) else 0.0
        reasons.append(f"거래량 pace {ratio:.2f}x")
    return signal, score, reasons, volatility_flag


def classify_disclosure(report_name: str) -> tuple[str, str, int]:
    text = str(report_name or "").lower()

    negative_patterns = [
        ("유상증자", 3),
        ("감자", 3),
        ("횡령", 3),
        ("배임", 3),
        ("감사의견", 3),
        ("상장폐지", 3),
        ("소송", 2),
        ("전환사채", 2),
        ("cb", 2),
        ("bw", 2),
        ("불성실", 2),
    ]
    positive_patterns = [
        ("자사주", 2),
        ("배당", 2),
        ("수주", 2),
        ("공급계약", 2),
        ("무상증자", 1),
        ("실적", 1),
    ]
    for pattern, severity in negative_patterns:
        if pattern in text:
            return "위험", "#f97316", severity
    for pattern, severity in positive_patterns:
        if pattern in text:
            return "긍정", getChartSeriesColor("up"), severity
    return "중립", "#94a3b8", 0


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
        return "위험 선호", "#dc2626", "시장 온도는 우호적입니다. 다만 추격보다 손절 기준과 분할 진입 조건을 먼저 확인합니다."
    if score >= 56:
        return "선별 매수", "#ef4444", "시장 여건은 양호하나 환율·금리·수급 중 일부 부담이 남아 있습니다. 강한 종목만 검토합니다."
    if score >= 44:
        return "중립", "#64748b", "방향성이 뚜렷하지 않습니다. 현금과 보유 포지션 점검을 병행합니다."
    if score >= 32:
        return "리스크 관리", "#2563eb", "지수·환율·금리 부담이 커졌습니다. 신규 비중 확대보다 손실 제한이 우선입니다."
    return "강한 위험 회피", "#1d4ed8", "현금 비중과 방어 전략이 우선입니다. 반등 확인 전 선진입은 피합니다."


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
                "color": insight_color(contribution, positive_is_good=positive_is_good),
                "bar": clamp(abs(contribution) / 16.0 * 100.0, 4.0, 100.0),
            }
        )

    kospi_pct = snapshot.get("KOSPI").change_pct if snapshot.get("KOSPI") else None
    kosdaq_pct = snapshot.get("KOSDAQ").change_pct if snapshot.get("KOSDAQ") else None
    usd_pct = snapshot.get("USD/KRW").change_pct if snapshot.get("USD/KRW") else None
    us10y_pct = snapshot.get("US 10Y").change_pct if snapshot.get("US 10Y") else None
    kr3y_pct = snapshot.get("KR 3Y").change_pct if snapshot.get("KR 3Y") else None
    fng = safe_float(snapshot.get("FNG").last_close) if snapshot.get("FNG") else None

    add_row("코스피", kospi_pct, clamp((kospi_pct or 0.0) / 2.5 * 16.0, -16.0, 16.0), signed_pct_text(kospi_pct))
    add_row("코스닥", kosdaq_pct, clamp((kosdaq_pct or 0.0) / 3.0 * 14.0, -14.0, 14.0), signed_pct_text(kosdaq_pct))
    add_row("환율", usd_pct, clamp(-(usd_pct or 0.0) / 1.0 * 12.0, -12.0, 12.0), signed_pct_text(usd_pct), positive_is_good=False)

    rate_pct = None
    if us10y_pct is not None and kr3y_pct is not None:
        rate_pct = (us10y_pct + kr3y_pct) / 2.0
    elif us10y_pct is not None:
        rate_pct = us10y_pct
    elif kr3y_pct is not None:
        rate_pct = kr3y_pct
    add_row("금리", rate_pct, clamp(-(rate_pct or 0.0) / 1.5 * 8.0, -8.0, 8.0), signed_pct_text(rate_pct), positive_is_good=False)
    add_row("심리", fng, clamp(((fng if fng is not None else 50.0) - 50.0) / 50.0 * 10.0, -10.0, 10.0), "N/A" if fng is None else f"{fng:.0f}/100")

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
                    <div class="insight-kicker">Market Pressure</div>
                    <div class="insight-title">한국시장 압력 점수</div>
                </div>
                <div class="insight-badge" style="background:{color};">{html.escape(label)}</div>
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
        messages = ["표시 가능한 데이터 품질 경고가 없습니다."]
    return score, status, color, list(dict.fromkeys(messages))[:5]


def render_data_quality_banner(snapshot: dict[str, Snapshot], valid_rows: list[dict[str, Any]]) -> None:
    score, status, color, messages = aggregate_data_quality(snapshot, valid_rows)
    warning_html = "".join(f"<div>{idx}. {html.escape(message)}</div>" for idx, message in enumerate(messages, 1))
    st.html(
        f"""
        <div class="quality-banner">
            <div class="quality-top">
                <div>
                    <div class="insight-kicker">Data Integrity</div>
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
        allowed = ["현금 비중 확대", "손실 제한", "보유 종목 방어 점검"]
        prohibited = ["추격 매수", "레버리지 확대", "손절 없는 신규 진입"]
    elif score <= 44:
        regime = "Risk-Off"
        cash_range = (40, 65)
        max_new_exposure = 0.35
        allowed = ["소액 분할 검토", "손익비 2.5x 이상만 검토", "약한 종목 축소 검토"]
        prohibited = ["근거 없는 신규 진입", "과도한 집중", "손실 확대 방치"]
    elif score <= 64:
        regime = "Neutral"
        cash_range = (20, 50)
        max_new_exposure = 0.60
        allowed = ["주도주 선별", "가격 구간 확인", "리스크 플래그 점검"]
        prohibited = ["전 종목 동시 확대", "손익비 2.0x 미만 진입", "데이터 부족 종목 추격"]
    elif score <= 79:
        regime = "Risk-On"
        cash_range = (10, 35)
        max_new_exposure = 0.80
        allowed = ["주도주 눌림목 검토", "부분 비중 보강", "수익 보호 기준 설정"]
        prohibited = ["목표가 없는 추격", "공시 리스크 무시", "단일 종목 과집중"]
    else:
        regime = "Euphoric"
        cash_range = (15, 40)
        max_new_exposure = 0.55
        allowed = ["보유 수익 보호", "리밸런싱 검토", "신규 진입 엄격화"]
        prohibited = ["고점 추격", "과열주 무리한 비중 확대", "현금 0% 운용"]

    confidence = int(round(clamp(sum(components.values()) / len(components), 0, 100))) if components else 0
    if not drivers:
        drivers = [f"시장 압력 {label}"]
    return MarketRegimeOutput(score, regime, cash_range, max_new_exposure, allowed, prohibited, drivers[:4], confidence, components)


def render_action_console(regime: MarketRegimeOutput) -> None:
    allowed = "".join(f"<li>{html.escape(item)}</li>" for item in regime.allowed_actions[:4])
    prohibited = "".join(f"<li>{html.escape(item)}</li>" for item in regime.prohibited_actions[:4])
    st.html(
        f"""
        <div class="action-console">
            <div>
                <div class="insight-kicker">오늘의 운용 범위</div>
                <div class="section-title" style="margin-top:0;">{html.escape(regime_label_ko(regime.regime))} · 현금 {regime.recommended_cash_range[0]}~{regime.recommended_cash_range[1]}%</div>
                <div class="small-note">신규 노출 한도 {regime.max_new_exposure * 100:.0f}% · 신뢰도 {regime.confidence}/100</div>
            </div>
            <div class="action-columns">
                <div><strong>검토 가능</strong><ul>{allowed}</ul></div>
                <div><strong>금지 행동</strong><ul>{prohibited}</ul></div>
            </div>
        </div>
        """
    )


def _compact_text(items: list[str], fallback: str = "표시할 내용 없음", limit: int = 2) -> str:
    clean_items = [str(item) for item in items if str(item).strip()]
    return " · ".join(clean_items[:limit]) if clean_items else fallback


def _portfolio_stance(regime: MarketRegimeOutput, leader_action: ActionDecision | None, exec_quality: float | None) -> tuple[str, str, str]:
    action_score = leader_action.score if leader_action else 50
    blockers = len(leader_action.blockers) if leader_action else 0
    if regime.score <= 35 or blockers >= 2:
        return (
            "리스크 관리 우선",
            "시장 압력 또는 종목 리스크가 높습니다. 신규 비중 확대보다 손실 제한과 현금 관리가 우선입니다.",
            "#2563eb",
        )
    if action_score >= 72 and (exec_quality is None or exec_quality >= 50):
        return (
            "선별 비중 보강 검토",
            "시장과 종목 신호가 비교적 정렬되어 있습니다. 가격 구간, 손절 기준, 공시 리스크를 확인한 뒤 분할 검토합니다.",
            "#dc2626",
        )
    if regime.score >= 65:
        return (
            "주도주 관찰",
            "시장 환경은 우호적입니다. 다만 기대값과 손익비가 확인된 종목만 검토합니다.",
            "#ef4444",
        )
    return (
        "중립 관찰",
        "결정적 우위가 충분하지 않습니다. 포지션은 유지하되 새로운 노출은 근거가 쌓일 때만 검토합니다.",
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
    leader_signal = action_label_ko(leader_action.action) if leader_action else "관찰"
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
        kill_state = {"active": False, "reason": "신호 원장 사용 불가", "sample_size": 0}

    stance, conclusion, stance_color = _portfolio_stance(regime, leader_action, exec_quality)
    if kill_state.get("active"):
        stance = "검증 보류"
        stance_color = "#2563eb"
        conclusion = "최근 신호 성과 저하가 감지되어 신규 신호 신뢰도를 낮춥니다. 보유 위험 점검과 사후 검증이 우선입니다."

    market_tile = f"{regime_label_ko(regime.regime)} · {regime.score}점"
    cash_tile = f"{regime.recommended_cash_range[0]}~{regime.recommended_cash_range[1]}%"
    leader_tile = f"{leader_name} ({leader_code})"
    edge_text = "N/A" if expected_edge is None else f"{expected_edge:+.2f}%"
    rr_text = "N/A" if rr is None else f"{rr:.2f}x"
    exec_text = "N/A" if exec_quality is None else f"{exec_quality:.0f}/100"
    stop_text = format_price(active_plan.get("stop"))
    tp_text = format_price(getattr(exit_plan, "first_take_profit", None))
    invalidation = _compact_text(getattr(exit_plan, "invalidation_rules", []), "손절·무효화 기준 확인 필요", 2)
    drivers = _compact_text(regime.primary_drivers, "시장 압력 중립", 3)
    data_msg = _compact_text(quality_messages, quality_status, 2)
    blocker_text = _compact_text(leader_action.blockers if leader_action else [], "차단 요인 없음", 2)

    st.html(
        f"""
        <div class="decision-report">
            <div class="decision-head">
                <div>
                    <div class="insight-kicker">Executive Decision Report</div>
                    <div class="decision-title">오늘의 투자 판단 요약</div>
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
                    <small>관심 우선 후보</small>
                    <strong>{html.escape(leader_tile)}</strong>
                    <span>{html.escape(leader_signal)} · {html.escape(leader_score_text)} · 최대 검토 {max_position * 100:.1f}%</span>
                </div>
                <div class="decision-tile">
                    <small>수익/비용</small>
                    <strong>기대값 {html.escape(edge_text)} · 손익비 {html.escape(rr_text)}</strong>
                    <span>실행 품질 {html.escape(exec_text)} · {html.escape(blocker_text)}</span>
                </div>
                <div class="decision-tile">
                    <small>리스크 기준</small>
                    <strong>손절 {html.escape(stop_text)} · 1차 목표 {html.escape(tp_text)}</strong>
                    <span>{html.escape(invalidation)}</span>
                </div>
            </div>
            <div class="thesis">데이터 품질 {quality_score}/100 · {html.escape(quality_status)} · {html.escape(data_msg)}</div>
        </div>
        """
    )



def disclosure_severity(report_name: str) -> tuple[str, int, str]:
    text = clean_text(report_name).lower()
    critical = ["감자", "상장폐지", "횡령", "배임", "감사의견", "거절", "부적정"]
    high = ["유상증자", "전환사채", "신주인수권", "cb", "bw", "소송", "불성실", "관리종목"]
    medium = ["최대주주", "담보제공", "정정", "조회공시", "투자주의"]
    positive = ["자사주", "배당", "수주", "공급계약", "무상증자", "실적개선"]
    if any(keyword in text for keyword in critical):
        return "Critical", 100, "신규 검토 차단이 필요한 중대 공시"
    if any(keyword in text for keyword in high):
        return "High", 25, "신규 비중 확대 전 확인이 필요한 공시"
    if any(keyword in text for keyword in medium):
        return "Medium", 8, "리스크 확인이 필요한 공시"
    if any(keyword in text for keyword in positive):
        return "Low", -2, "긍정 또는 중립 가능성이 있는 공시"
    return "Low", 0, "특이 위험 공시 없음"


def disclosure_risk_for_stock(code: str, name: str, disclosures: pd.DataFrame) -> dict[str, Any]:
    if disclosures is None or disclosures.empty:
        return {"severity": "Low", "penalty": 0, "count": 0, "summary": "최근 연결 공시 없음"}
    mask = pd.Series(False, index=disclosures.index)
    if "stock_code" in disclosures.columns:
        mask = mask | disclosures["stock_code"].astype(str).str.zfill(6).eq(code)
    if "corp_name" in disclosures.columns and name:
        mask = mask | disclosures["corp_name"].astype(str).str.contains(re.escape(name), na=False)
    subset = disclosures[mask].head(20)
    if subset.empty:
        return {"severity": "Low", "penalty": 0, "count": 0, "summary": "최근 연결 공시 없음"}
    best = {"severity": "Low", "penalty": 0, "count": len(subset), "summary": "특이 위험 공시 없음"}
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
    severity = str(disclosure_risk.get("severity", "Low"))
    event_factor = 0.0 if severity == "Critical" else 0.55 if severity == "High" else 0.82 if severity == "Medium" else 1.0
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
    severity = str(disclosure_risk.get("severity", "Low"))
    if data_quality < 70:
        blockers.append("데이터 품질 낮음")
    if severity in {"High", "Critical"}:
        blockers.append(f"공시 위험 {severity_label_ko(severity)}")
    if execution_cost_pct is not None and expected_edge is not None and expected_edge <= 0:
        blockers.append("실행 비용 반영 후 기대값 부족")
    if raw_rr is None or raw_rr < RISK_DEFAULTS["min_raw_rr"]:
        blockers.append("기본 손익비 부족")
    if quality_adjusted_rr is None or quality_adjusted_rr < RISK_DEFAULTS["min_quality_adjusted_rr"]:
        blockers.append("품질조정 손익비 부족")
    if expected_edge is None or expected_edge <= 0:
        blockers.append("기대값 검증 필요")
    if regime.regime == "Extreme Risk-Off" and (raw_rr is None or raw_rr < RISK_DEFAULTS["extreme_risk_off_min_rr"]):
        blockers.append("극단 리스크오프 기준 미달")
    if kill_switch_active:
        blockers.append("신호 성과 kill-switch")

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
    if severity == "Critical":
        score = min(score, 25)
    if kill_switch_active:
        score = min(score, 45)
    score = int(round(clamp(score, 0, 100)))

    if blockers:
        if severity == "Critical" or score < 35:
            label = "Sell / Avoid"
        elif score < 55:
            label = "Watch Only"
        else:
            label = "Hold / Watch"
    else:
        label = action_label(score)

    base_max = min(regime.max_new_exposure, RISK_DEFAULTS["max_position_pct"])
    if raw_rr is not None and raw_rr >= 3:
        base_max *= 1.15
    if severity in {"Medium", "High"}:
        base_max *= 0.55
    if severity == "Critical" or kill_switch_active:
        base_max = 0.0
    max_position_pct = clamp(base_max, 0.0, RISK_DEFAULTS["max_position_pct"])

    reasons = [
        f"시장 국면 {regime_label_ko(regime.regime)}({regime.score}점)",
        f"주도력 {leadership_score:.0f}점",
        f"데이터 품질 {data_quality}점",
    ]
    if expected_edge is not None:
        reasons.append(f"기대값 {expected_edge:+.2f}%")
    if quality_adjusted_rr is not None:
        reasons.append(f"품질조정 손익비 {quality_adjusted_rr:.2f}x")

    return ActionDecision(label, score, expected_edge, quality_adjusted_rr, max_position_pct, reasons, blockers)


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
            <div class="rank-header">행동 후보</div>
            <div class="rank-header">1일</div>
            <div class="rank-header">기대값</div>
            <div class="rank-header">최대 비중</div>
        </div>
        """
    ]
    if not visible:
        rank_html.append('<div class="thesis">표시할 관심종목 데이터가 없습니다.</div>')
    for idx, row in enumerate(visible, 1):
        score = safe_float(row.get("score")) or 0.0
        score_color = "#dc2626" if score >= 65 else "#2563eb" if score <= 44 else "#64748b"
        r1 = safe_float(row.get("r1"))
        action = row.get("action")
        expected_edge = action.expected_edge if isinstance(action, ActionDecision) else None
        max_position = action.max_position_pct if isinstance(action, ActionDecision) else 0.0
        blockers = action.blockers if isinstance(action, ActionDecision) else []
        blocker_text = f" · 차단 {len(blockers)}" if blockers else ""
        action_text = action_label_ko(str(row.get("signal")))
        leader_score = safe_float(row.get("leadership_score")) or 0.0
        rank_html.append(
            f"""
            <div class="rank-row">
                <div class="row-label">{idx}</div>
                <div class="rank-name"><strong>{html.escape(str(row["name"]))}</strong><span>{html.escape(str(row["code"]))} · 주도력 {leader_score:.0f}{html.escape(blocker_text)}</span></div>
                <div class="row-value" style="color:{score_color};">{html.escape(action_text)}<br>{score:.0f}점</div>
                <div class="row-value" style="color:{insight_color(r1)};">{signed_pct_text(r1)}</div>
                <div class="row-value" style="color:{insight_color(expected_edge)};">{"N/A" if expected_edge is None else f"{expected_edge:+.2f}%"}</div>
                <div class="row-value">{max_position * 100:.1f}%</div>
            </div>
            """
        )

    thesis = "관심종목은 점수, 기대값, 공시 위험, 실행 비용을 함께 본 검토 우선순위입니다."
    if visible:
        leader = visible[0]
        thesis = f"현재 최상위 검토 후보는 {leader['name']}입니다. 점수는 {safe_float(leader['score']) or 0:.0f}점이며, 추격보다 가격 구간 확인이 우선입니다."
    st.html(
        f"""
        <div class="insight-panel">
            <div class="insight-head">
                <div>
                    <div class="insight-kicker">Watchlist Priority</div>
                    <div class="insight-title">관심종목 우선순위</div>
                </div>
                <div class="insight-badge" style="background:#0f766e;">검토 후보</div>
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
        "thesis": "가격 데이터가 부족해 손절·목표·손익비를 계산할 수 없습니다.",
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
        label, color = "손익비 양호", "#dc2626"
        thesis = "목표 대비 손절폭이 비교적 작습니다. 다만 진입 가격과 무효화 기준 확인이 먼저입니다."
    elif rr is not None and rr < 0.8:
        label, color = "손익비 부족", "#2563eb"
        thesis = "기대 상승 여력보다 하방 위험이 큽니다. 신규 검토보다 관찰 또는 리스크 축소가 우선입니다."
    else:
        label, color = "가격 구간 확인", "#64748b"
        thesis = "손익비가 중립 구간입니다. 거래량, 추세, 공시 리스크를 함께 확인합니다."

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
        plan = risk_plan_for_stock("", "선택 종목 없음", pd.DataFrame())
    else:
        active_name = code_to_name.get(active_code, STOCK_UNIVERSE_NAME_HINTS.get(active_code, active_code))
        plan = risk_plan_for_stock(active_code, active_name, load_symbol_history(active_code, refresh_token, periods=240))

    value_rows = [
        ("현재가", format_price(plan["latest"])),
        ("검토 가격대", "N/A" if plan["entry_low"] is None or plan["entry_high"] is None else f"{format_price(plan['entry_low'])} ~ {format_price(plan['entry_high'])}"),
        ("손절 기준", format_price(plan["stop"])),
        ("저항/목표", format_price(plan["resistance"])),
        ("하방위험", "N/A" if plan["risk_pct"] is None else f"{plan['risk_pct']:.2f}%"),
        ("상승여력", "N/A" if plan["upside_pct"] is None else f"{plan['upside_pct']:+.2f}%"),
        ("손익비", "N/A" if plan["rr"] is None else f"{plan['rr']:.2f}x"),
        ("기대값", "N/A" if action is None or action.expected_edge is None else f"{action.expected_edge:+.2f}%"),
        ("품질조정 R/R", "N/A" if action is None or action.quality_adjusted_rr is None else f"{action.quality_adjusted_rr:.2f}x"),
        ("최대 검토 비중", "N/A" if action is None else f"{action.max_position_pct * 100:.1f}%"),
    ]
    row_html = "".join(
        f"""
        <div class="signal-row">
            <div class="row-label">{html.escape(label)}</div>
            <div class="row-value">{html.escape(value)}</div>
        </div>
        """
        for label, value in value_rows
    )
    st.html(
        f"""
        <div class="insight-panel">
            <div class="insight-head">
                <div>
                    <div class="insight-kicker">손익비</div>
                    <div class="insight-title">손익비와 포지션 기준</div>
                </div>
                <div class="insight-badge" style="background:{plan["color"]};">{html.escape(plan["label"])}</div>
            </div>
            {row_html}
            <div class="thesis">{html.escape(plan["thesis"])}</div>
        </div>
        """
    )



def _format_bps(value: float | None) -> str:
    return "데이터 없음" if value is None else f"{value:.1f}bp"


def _format_krw(value: float | None) -> str:
    return "데이터 없음" if value is None else f"{value:,.0f}원"


def render_execution_card(exec_plan: Any, expected_edge: float | None = None) -> None:
    warning_lines: list[str] = []
    if getattr(exec_plan, "unavailable_fields", None):
        warning_lines.append("데이터 없음: " + ", ".join(exec_plan.unavailable_fields[:4]))
    if getattr(exec_plan, "warnings", None):
        warning_lines.extend(exec_plan.warnings[:3])
    if should_block_for_execution(exec_plan, expected_edge):
        warning_lines.append("실행 비용 또는 유동성 때문에 신규 검토를 보류합니다.")
    warnings_html = "".join(f"<div>{idx}. {html.escape(str(text))}</div>" for idx, text in enumerate(warning_lines, 1)) or "<div>주요 실행 경고 없음</div>"
    row_html = "".join(
        f"""
        <div class="risk-row">
            <div class="row-label">{html.escape(label)}</div>
            <div class="row-value">{html.escape(value)}</div>
        </div>
        """
        for label, value in [
            ("실행 품질", f"{getattr(exec_plan, 'execution_quality_score', 0):.0f}/100"),
            ("유동성", f"{getattr(exec_plan, 'liquidity_score', 0):.0f}/100"),
            ("총 예상 비용", _format_bps(getattr(exec_plan, "total_execution_cost_bps", None))),
            ("슬리피지", _format_bps(getattr(exec_plan, "estimated_slippage_bps", None))),
            ("시장충격", _format_bps(getattr(exec_plan, "estimated_market_impact_bps", None))),
            ("영향 적은 주문금액", _format_krw(getattr(exec_plan, "max_order_value_without_impact", None))),
            ("권장 주문 방식", str(getattr(exec_plan, "recommended_order_style", "보류"))),
            ("분할 횟수", str(getattr(exec_plan, "recommended_slices", 0))),
        ]
    )
    quality = safe_float(getattr(exec_plan, "execution_quality_score", 0)) or 0
    color = "#dc2626" if quality >= 70 else "#64748b" if quality >= 40 else "#2563eb"
    st.html(
        f"""
        <div class="insight-panel">
            <div class="insight-head">
                <div>
                    <div class="insight-kicker">실행 품질</div>
                    <div class="insight-title">실행 품질</div>
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
            ("최종 손절", format_price(getattr(exit_plan, "hard_stop", None))),
            ("트레일링", format_price(getattr(exit_plan, "trailing_stop", None))),
            ("1차 목표", format_price(getattr(exit_plan, "first_take_profit", None))),
            ("2차 목표", format_price(getattr(exit_plan, "second_take_profit", None))),
            ("시간 손절", str(getattr(exit_plan, "time_stop_date", "데이터 없음"))),
            ("잔여 러너", f"{getattr(exit_plan, 'runner_position_pct', 0) * 100:.0f}%"),
            ("신뢰도", f"{getattr(exit_plan, 'exit_confidence', 0):.0f}/100"),
        ]
    )
    invalidation = getattr(exit_plan, "invalidation_rules", []) or []
    warnings = getattr(exit_plan, "warnings", []) or []
    thesis = " / ".join([*invalidation[:2], *warnings[:2]]) or "현재 기준에서는 청산 규칙을 계속 점검합니다."
    status = str(getattr(exit_plan, "status", "점검 필요"))
    color = "#dc2626" if "수익" in status or "보호" in status else "#64748b" if "관찰" in status else "#2563eb"
    st.html(
        f"""
        <div class="insight-panel">
            <div class="insight-head">
                <div>
                    <div class="insight-kicker">동적 청산 계획</div>
                    <div class="insight-title">청산 계획</div>
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
    st.markdown('<div class="section-title">핵심 판단 3요소</div>', unsafe_allow_html=True)
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
        reasons.append(f"목표 비중 이탈 {max_abs_drift * 100:.1f}%p")
    elif max_abs_drift > 0.05:
        score -= 10
        reasons.append(f"목표 비중 이탈 {max_abs_drift * 100:.1f}%p")
    elif max_abs_drift > 0.03:
        score -= 5
        reasons.append(f"비중 점검 {max_abs_drift * 100:.1f}%p")
    if annualized_volatility is not None and annualized_volatility > 0.25:
        score -= 15
        reasons.append("변동성 높음")
    elif annualized_volatility is not None and annualized_volatility > 0.18:
        score -= 8
        reasons.append("변동성 점검")
    if max_drawdown is not None and max_drawdown < -0.20:
        score -= 20
        reasons.append("최대 낙폭 확대")
    elif max_drawdown is not None and max_drawdown < -0.10:
        score -= 10
        reasons.append("낙폭 점검")
    if sharpe_ratio is not None and sharpe_ratio < 0.5:
        score -= 15
        reasons.append("위험 대비 수익 낮음")
    elif sharpe_ratio is not None and sharpe_ratio < 1.0:
        score -= 7
        reasons.append("샤프비율 보통")
    if concentration.get("level") == "High":
        score -= 15
        reasons.append("집중도 높음")
    elif concentration.get("level") == "Medium":
        score -= 7
        reasons.append("집중도 점검")
    if cash_weight < 0.02 or cash_weight > 0.30:
        score -= 6
        reasons.append("현금 비중 점검")
    score = int(max(0, min(100, round(score))))
    if score >= 80:
        return score, "우수", reasons[:3] or ["주요 리스크 균형 양호"], "#22c55e"
    if score >= 60:
        return score, "관찰", reasons[:3] or ["일부 항목 점검"], "#a78bfa"
    if score >= 40:
        return score, "주의", reasons[:3] or ["리스크 관리 필요"], "#f59e0b"
    return score, "고위험", reasons[:3] or ["포트폴리오 방어 우선"], "#ef4444"


def _largest_drift_observation(drift: dict[str, dict[str, Any]]) -> dict[str, str] | None:
    if not drift:
        return None
    asset_class, row = max(drift.items(), key=lambda item: abs(safe_float(item[1].get("drift")) or 0.0))
    value = safe_float(row.get("drift")) or 0.0
    label = ASSET_CLASS_LABELS.get(asset_class, asset_class)
    status = "초과" if value > 0 else "부족" if value < 0 else "목표 근접"
    return {"assetClass": label, "status": status, "text": f"{label} {abs(value) * 100:.1f}%p {status}"}


def _dark_chart_style(ax: plt.Axes) -> None:
    ax.set_facecolor("#0f172a")
    ax.grid(True, linestyle="--", alpha=0.18, color="#94a3b8")
    ax.tick_params(axis="x", colors="#cbd5e1")
    ax.tick_params(axis="y", colors="#cbd5e1")
    for spine in ax.spines.values():
        spine.set_color("#334155")


def plot_portfolio_value_chart(points: list[Any], benchmark_points: list[Any]) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10, 3.2))
    fig.patch.set_facecolor("#0f172a")
    _dark_chart_style(ax)
    if not points:
        ax.axis("off")
        ax.text(0.5, 0.5, "포트폴리오 시계열 데이터가 없습니다.", ha="center", va="center", color="#cbd5e1")
        return fig
    dates = [_portfolio_point_date(point) for point in points]
    values = [_portfolio_point_value(point) for point in points]
    ax.plot(dates, values, color="#a78bfa", linewidth=2.2, label="포트폴리오")
    if benchmark_points:
        bench_dates = [_portfolio_point_date(point) for point in benchmark_points]
        bench_values = [_portfolio_point_value(point) for point in benchmark_points]
        ax.plot(bench_dates, bench_values, color="#38bdf8", linewidth=1.6, label="벤치마크", alpha=0.85)
    ax.set_title("포트폴리오 vs 벤치마크", color="#f8fafc", loc="left", fontsize=12, weight="bold")
    ax.legend(facecolor="#111827", edgecolor="#334155", labelcolor="#e5e7eb")
    fig.autofmt_xdate(rotation=0)
    fig.tight_layout()
    return fig


def plot_portfolio_drawdown_chart(drawdowns: list[dict[str, Any]]) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10, 2.8))
    fig.patch.set_facecolor("#0f172a")
    _dark_chart_style(ax)
    if not drawdowns:
        ax.axis("off")
        ax.text(0.5, 0.5, "드로다운 데이터가 없습니다.", ha="center", va="center", color="#cbd5e1")
        return fig
    dates = [pd.Timestamp(row.get("date")) for row in drawdowns]
    values = [safe_float(row.get("drawdown")) or 0.0 for row in drawdowns]
    ax.fill_between(dates, values, 0, color="#2563eb", alpha=0.35)
    ax.plot(dates, values, color="#60a5fa", linewidth=1.8)
    ax.set_title("드로다운", color="#f8fafc", loc="left", fontsize=12, weight="bold")
    ax.yaxis.set_major_formatter(lambda value, _: f"{value * 100:.0f}%")
    fig.autofmt_xdate(rotation=0)
    fig.tight_layout()
    return fig


def portfolio_health_card_html(score: int, label: str, reasons: list[str], color: str) -> str:
    score = int(max(0, min(100, score)))
    label_tone = "risk" if score < 40 else "warn" if score < 60 else "info" if score < 80 else "good"
    reason_html = "".join(
        f"<div class='pi-reason'><span class='pi-dot'></span><span>{html.escape(reason)}</span></div>"
        for reason in reasons[:3]
    )
    return f"""
        <div class="pi-card">
            <div class="pi-card-header">
                <strong>포트폴리오 건강도</strong>
                <span class="pi-badge {label_tone}">{html.escape(label)}</span>
            </div>
            <div class="pi-card-body">
                <div class="pi-health-score"><strong>{score}</strong><span>/100</span></div>
                <div class="pi-progress" aria-label="포트폴리오 건강도 {score}점">
                    <div class="pi-progress-fill" style="width:{score}%; background:linear-gradient(90deg, {html.escape(color)}, #f97316);"></div>
                </div>
                <div class="pi-reason-list">{reason_html or "<div class='pi-reason'><span class='pi-dot'></span><span>포트폴리오 방어 우선</span></div>"}</div>
            </div>
        </div>
        """


def render_portfolio_health_card(score: int, label: str, reasons: list[str], color: str) -> None:
    st.html(portfolio_health_card_html(score, label, reasons, color))


def allocation_drift_card_html(drift: dict[str, dict[str, Any]]) -> str:
    rows = []
    for asset_class, row in drift.items():
        current = safe_float(row.get("currentWeight")) or 0.0
        target = safe_float(row.get("targetWeight")) or 0.0
        delta = safe_float(row.get("drift")) or 0.0
        status = str(row.get("status", "On target"))
        status_ko = "초과" if status == "Overweight" else "부족" if status == "Underweight" else "목표 근접"
        color = "#ef4444" if delta > 0.03 else "#38bdf8" if delta < -0.03 else "#8b5cf6"
        badge_tone = "risk" if delta > 0.03 else "info" if delta < -0.03 else "good"
        drift_text = f"{delta * 100:+.1f}%p" if abs(delta) >= 0.005 else "근접"
        rows.append(
            f"""
            <div class="pi-allocation-row">
                <div class="pi-asset-label">{html.escape(ASSET_CLASS_LABELS.get(asset_class, asset_class))}</div>
                <div class="pi-allocation-track" aria-label="{html.escape(ASSET_CLASS_LABELS.get(asset_class, asset_class))} 현재 비중 {current * 100:.1f}%">
                    <div class="pi-allocation-fill" style="width:{max(2, min(100, current * 100)):.1f}%; background:{color};"></div>
                </div>
                <div class="pi-allocation-value">
                    {current * 100:.1f}% <small>/ {target * 100:.1f}%</small>
                    <span class="pi-badge {badge_tone}" style="margin-left:6px;">{html.escape(status_ko)} {html.escape(drift_text)}</span>
                </div>
            </div>
            """
        )
    return f"""
        <div class="pi-card">
            <div class="pi-card-header">
                <strong>배분 이탈</strong>
                <span class="pi-badge info">현재 vs 목표</span>
            </div>
            <div class="pi-card-body">
                {''.join(rows) if rows else '<div class="thesis">배분 데이터가 없습니다.</div>'}
            </div>
        </div>
        """


def render_allocation_drift_card(drift: dict[str, dict[str, Any]]) -> None:
    st.html(allocation_drift_card_html(drift))


def rebalance_candidates_card_html(suggestions: list[dict[str, Any]]) -> str:
    if not suggestions:
        body = '<div class="pi-rebalance-item"><div class="pi-rebalance-top"><div class="pi-rebalance-asset">목표 근접</div><span class="pi-badge good">검토 유지</span></div><div class="pi-rebalance-reason">목표 비중 대비 큰 이탈이 없어 리밸런싱 후보가 없습니다.</div></div>'
    else:
        body = "".join(
            f"""
            <div class="pi-rebalance-item">
                <div class="pi-rebalance-top">
                    <div class="pi-rebalance-asset">{html.escape(ASSET_CLASS_LABELS.get(str(item.get("assetClass")), str(item.get("assetClass"))))}</div>
                    <span class="pi-badge {'warn' if safe_float(item.get("drift")) and safe_float(item.get("drift")) > 0 else 'info'}">{html.escape(str(item.get("action", "")))}</span>
                </div>
                <div class="pi-rebalance-reason">{html.escape(str(item.get("reason", "")))}</div>
                <div class="pi-rebalance-bottom" style="margin-top:9px;">
                    <div class="pi-rebalance-impact">{html.escape(str(item.get("impact", "목표 배분과 변동성 균형을 점검합니다.")))}</div>
                    <div class="pi-rebalance-amount">{html.escape(portfolio_format_currency(item.get("suggestedAmount")))}</div>
                </div>
            </div>
            """
            for item in suggestions[:5]
        )
    return f"""
        <div class="pi-card">
            <div class="pi-card-header">
                <strong>리밸런싱 후보</strong>
                <span class="pi-badge warn">주문 아님</span>
            </div>
            <div class="pi-card-body">
                <div class="pi-rebalance-list">{body}</div>
            </div>
        </div>
        """


def render_rebalance_candidates_card(suggestions: list[dict[str, Any]]) -> None:
    st.html(rebalance_candidates_card_html(suggestions))


def _pi_metric_tile_html(label: str, value: str, helper: str, tone: str) -> str:
    tone_class = "pi-tone-good" if tone == "good" else "pi-tone-risk" if tone == "risk" else "pi-tone-warn" if tone == "warn" else "pi-tone-info"
    return f"""
        <div class="pi-metric-tile {tone_class}" role="group" aria-label="{html.escape(label)} {html.escape(value)}">
            <div class="pi-metric-label">{html.escape(label)}</div>
            <div class="pi-metric-value">{html.escape(value)}</div>
            <div class="pi-metric-helper">{html.escape(helper)}</div>
        </div>
    """


def risk_return_panel_html(metrics: dict[str, Any], benchmark_excess: Any = None) -> str:
    volatility = safe_float(metrics.get("volatility"))
    sharpe = safe_float(metrics.get("sharpe"))
    max_drawdown = safe_float(metrics.get("maxDrawdown"))
    beta = safe_float(metrics.get("beta"))
    period_return = safe_float(metrics.get("periodReturn"))
    cagr = safe_float(metrics.get("cagr"))
    benchmark_value = portfolio_format_percent(benchmark_excess, signed=True)
    benchmark_tone = "pi-value-good" if (safe_float(benchmark_excess) or 0) > 0 else "pi-value-risk" if (safe_float(benchmark_excess) or 0) < 0 else "pi-value-info"
    metric_specs = [
        ("CAGR", portfolio_format_percent(cagr), "연복리 성장률", "good" if cagr is not None and cagr > 0.06 else "info"),
        ("기간 수익률", portfolio_format_percent(period_return, signed=True), "선택 기간 누적", "good" if period_return is not None and period_return > 0 else "risk" if period_return is not None and period_return < 0 else "info"),
        ("연율 변동성", portfolio_format_percent(volatility), "변동성 높음" if volatility is not None and volatility >= 0.25 else "변동성 점검", "risk" if volatility is not None and volatility >= 0.40 else "warn" if volatility is not None and volatility >= 0.25 else "info"),
        ("Sharpe", "N/A" if sharpe is None else f"{sharpe:.2f}", "위험 대비 효율 낮음" if sharpe is not None and sharpe < 0.5 else "위험조정 효율", "warn" if sharpe is None or sharpe < 0.5 else "good"),
        ("최대 낙폭", portfolio_format_percent(max_drawdown), "고점 대비 낙폭", "risk" if max_drawdown is not None and max_drawdown < -0.10 else "info"),
        ("Beta", "N/A" if beta is None else f"{beta:.2f}", "시장 민감도 높음" if beta is not None and beta > 1.2 else "시장 민감도", "warn" if beta is not None and beta > 1.2 else "info"),
    ]
    tiles = "".join(_pi_metric_tile_html(label, value, helper, tone) for label, value, helper, tone in metric_specs)
    return f"""
        <div class="pi-card pi-risk-card">
            <div class="pi-card-header">
                <strong>리스크·수익</strong>
                <span class="pi-badge info">검토 지표</span>
            </div>
            <div class="pi-card-body">
                <div class="pi-card-subtitle">수익률·변동성·위험조정 효율</div>
                <div class="pi-metric-grid">{tiles}</div>
                <div class="pi-benchmark-strip">
                    <span>벤치마크 대비 기간 초과수익</span>
                    <strong class="{benchmark_tone}">{html.escape(benchmark_value)}</strong>
                </div>
            </div>
        </div>
    """


def render_risk_return_panel(metrics: dict[str, Any], benchmark_excess: Any = None) -> None:
    st.html(risk_return_panel_html(metrics, benchmark_excess))


def _insight_value(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def insight_engine_card_html(insights: list[dict[str, str]], metrics: dict[str, Any] | None = None) -> str:
    metrics = metrics or {}
    observation = ""
    candidate_action = ""
    why_text = ""
    for item in insights:
        text = _insight_value(item, "observation")
        if "위험 대비 수익 효율" in text:
            observation = text
            why_text = _insight_value(item, "whyItMatters", "why")
        if "오늘의 실행 후보" in text:
            candidate_action = text
    if not observation and insights:
        observation = _insight_value(insights[0], "observation") or "검토 가능한 인사이트가 없습니다."
        why_text = _insight_value(insights[0], "whyItMatters", "why")
    if not candidate_action:
        for item in insights:
            candidate = _insight_value(item, "candidateAction", "candidate")
            if candidate:
                candidate_action = candidate
                break
    if not candidate_action:
        candidate_action = "오늘의 실행 후보는 리밸런싱과 위험 축소 관점에서 선별됩니다."

    sharpe_value = safe_float(metrics.get("sharpe"))
    beta_value = safe_float(metrics.get("beta"))
    sharpe_text = "N/A" if sharpe_value is None else f"{sharpe_value:.2f}"
    beta_text = "N/A" if beta_value is None else f"{beta_value:.2f}"
    evidence = [
        f"Sharpe {sharpe_text}",
        f"연율 변동성 {portfolio_format_percent(metrics.get('volatility'))}",
        f"Beta {beta_text}",
    ]
    if why_text:
        evidence.append(why_text)
    return f"""
        <div class="pi-card pi-insight-card">
            <div class="pi-card-header">
                <strong>인사이트 엔진</strong>
                <span class="pi-badge info">규칙 기반</span>
            </div>
            <div class="pi-card-body">
                <div class="pi-insight-stack">
                    <div class="pi-insight-block">
                        <div class="pi-insight-label">관찰</div>
                        <div class="pi-insight-text">{html.escape(observation)}</div>
                    </div>
                    <div class="pi-insight-block">
                        <div class="pi-insight-label">근거</div>
                        <div class="pi-insight-text muted">{html.escape(' · '.join(evidence))}</div>
                    </div>
                    <div class="pi-insight-block action">
                        <div class="pi-insight-label">후보 행동</div>
                        <div class="pi-insight-text">{html.escape(candidate_action)}</div>
                    </div>
                </div>
            </div>
        </div>
    """


def render_insight_engine_card(insights: list[dict[str, str]], metrics: dict[str, Any] | None = None) -> None:
    st.html(insight_engine_card_html(insights, metrics))


def concentration_card_html(holdings: list[Any], concentration: dict[str, Any]) -> str:
    top = sorted(holdings or [], key=lambda h: (safe_float(getattr(h, "quantity", 0)) or 0) * (safe_float(getattr(h, "current_price", 0)) or 0), reverse=True)[:5]
    total = sum((safe_float(getattr(h, "quantity", 0)) or 0) * (safe_float(getattr(h, "current_price", 0)) or 0) for h in holdings or [])
    rows = []
    for idx, h in enumerate(top, 1):
        value = (safe_float(getattr(h, "quantity", 0)) or 0) * (safe_float(getattr(h, "current_price", 0)) or 0)
        weight = value / total if total > 0 else 0.0
        color = "#ef4444" if weight >= 0.20 else "#f59e0b" if weight >= 0.10 else "#8b5cf6"
        rows.append(
            f"""
            <div class="pi-holding-row">
                <div class="pi-holding-rank">{idx}</div>
                <div>
                    <div class="pi-holding-symbol">{html.escape(str(getattr(h, "symbol", "")))}</div>
                    <div class="pi-holding-name">{html.escape(str(getattr(h, "name", "")))}</div>
                </div>
                <div class="pi-holding-track" aria-label="{html.escape(str(getattr(h, "symbol", "")))} 비중 {weight * 100:.1f}%">
                    <div class="pi-holding-fill" style="width:{max(2, min(100, weight * 100)):.1f}%; background:{color};"></div>
                </div>
                <div class="pi-holding-weight">{weight * 100:.1f}%</div>
            </div>
            """
        )
    level = str(concentration.get("level", "Low"))
    level_tone = "risk" if level == "High" else "warn" if level == "Medium" else "good"
    top_weight = portfolio_format_percent(concentration.get("topHoldingWeight"))
    hhi = "N/A" if concentration.get("herfindahlIndex") is None else f"{concentration.get('herfindahlIndex'):.3f}"
    return f"""
        <div class="pi-card pi-concentration-card">
            <div class="pi-card-header">
                <strong>집중도 위험</strong>
                <span class="pi-badge {level_tone}">{html.escape(level)}</span>
            </div>
            <div class="pi-card-body">
                <div class="pi-holding-list">{''.join(rows) if rows else '<div class="thesis">보유종목 데이터가 없습니다.</div>'}</div>
                <div class="pi-concentration-footer">
                    상위 비중 {html.escape(top_weight)} · HHI {html.escape(hhi)}<br/>
                    상위 보유 비중과 HHI 기준 집중도 점검 필요
                </div>
            </div>
        </div>
    """


def render_concentration_card(holdings: list[Any], concentration: dict[str, Any]) -> None:
    st.html(concentration_card_html(holdings, concentration))


def _holding_stock_signals(holdings: list[Any], snapshot: dict[str, Snapshot]) -> list[Any]:
    items = []
    for holding in holdings[:8]:
        symbol = str(getattr(holding, "symbol", ""))
        snap = snapshot.get(symbol)
        price = safe_float(getattr(snap, "last_close", None)) or safe_float(getattr(holding, "current_price", None)) or 0.0
        change_pct = safe_float(getattr(snap, "change_pct", None)) or 0.0
        items.append(
            {
                "symbol": symbol,
                "name": str(getattr(holding, "name", symbol)),
                "currentPrice": price,
                "changePercent": change_pct / 100 if abs(change_pct) > 1 else change_pct,
                "movingAverage20": None,
                "movingAverage60": None,
                "movingAverage200": None,
                "fiftyTwoWeekHigh": None,
                "fiftyTwoWeekLow": None,
                "volatility": None,
            }
        )
    return items


def watchlist_signals_card_html(signals: list[dict[str, Any]]) -> str:
    rows = []
    for item in signals[:6]:
        raw_reasons = item.get("signals") or item.get("reasons") or []
        reasons = " / ".join(str(reason) for reason in raw_reasons[:2]) if raw_reasons else "뚜렷한 우위 신호 없음"
        change = safe_float(item.get("changePercent"))
        tone_class = "pi-value-good" if change is not None and change > 0 else "pi-value-risk" if change is not None and change < 0 else "pi-value-info"
        rows.append(
            f"""
            <div class="pi-signal-row">
                <div class="pi-signal-code">{html.escape(str(item.get("symbol", "")))}</div>
                <div class="pi-signal-name">{html.escape(str(item.get("name", "")))}</div>
                <div class="pi-signal-change {tone_class}">{portfolio_format_percent(change, signed=True)}</div>
                <div class="pi-signal-badge" title="{html.escape(reasons)}">{html.escape(reasons)}</div>
            </div>
            """
        )
    return f"""
        <div class="pi-card pi-signals-card">
            <div class="pi-card-header">
                <strong>보유/관심 신호</strong>
                <span class="pi-badge info">추세 확인</span>
            </div>
            <div class="pi-card-body">
                <div class="pi-signal-header">
                    <span>코드</span>
                    <span>종목</span>
                    <span style="text-align:right;">변화율</span>
                    <span>신호</span>
                </div>
                <div class="pi-signal-list">{''.join(rows) if rows else '<div class="thesis">신호 데이터가 없습니다.</div>'}</div>
            </div>
        </div>
    """


def render_watchlist_signals_card(signals: list[dict[str, Any]]) -> None:
    st.html(watchlist_signals_card_html(signals))


def render_portfolio_risk_cockpit_section(
    snapshot: dict[str, Snapshot],
    code_to_name: dict[str, str],
    refresh_token: int,
) -> None:
    holdings_text = str(st.session_state.get("portfolio_holdings_text", ""))
    parsed_rows, parse_errors = parse_portfolio_text(holdings_text)
    using_mock = not parsed_rows
    holdings = getHoldings(parsed_rows, snapshot, code_to_name)
    total_assets = None if using_mock else safe_float(st.session_state.get("portfolio_total_assets"))
    cash = None if using_mock else safe_float(st.session_state.get("portfolio_cash"))
    thresholds = PortfolioRiskThresholds(
        single_stock_weight=float(RISK_DEFAULTS.get("max_position_pct", 0.10) or 0.10),
        sector_weight=float(RISK_DEFAULTS.get("max_sector_pct", 0.30) or 0.30),
        cash_min_weight=0.03,
    )
    state = build_portfolio_risk_cockpit(
        holdings,
        total_assets=total_assets,
        cash=cash,
        snapshots=snapshot,
        price_series=getPortfolioSnapshots(),
        thresholds=thresholds,
        allow_mock=True,
        source_label="Mock portfolio data" if using_mock else "Sidebar portfolio input",
    )
    if parse_errors:
        st.warning("포트폴리오 리스크 관제실 입력 확인: " + " / ".join(parse_errors[:2]))
    st.html(portfolio_risk_cockpit_html(state))


def render_data_trust_source_panel_section(
    snapshot: dict[str, Snapshot],
    code_to_name: dict[str, str],
    refresh_token: int,
) -> None:
    flag_value = os.getenv("STANCE_ENABLE_DATA_TRUST", "1").strip().lower()
    if flag_value in {"0", "false", "no", "off"}:
        return

    holdings_text = str(st.session_state.get("portfolio_holdings_text", ""))
    parsed_rows, _ = parse_portfolio_text(holdings_text)
    using_mock = not parsed_rows
    required_secret_status = check_required_secrets()
    dart_present = bool(required_secret_status["dart"]["present"])
    ecos_present = bool(required_secret_status["ecos"]["present"])
    api_key_status = {
        "DART_API_KEY": dart_present,
        "OPENDART_API_KEY": dart_present,
        "OPEN_DART_API_KEY": dart_present,
        "ECOS_API_KEY": ecos_present,
        "ECOS_AUTH_KEY": ecos_present,
        "BOK_ECOS_API_KEY": ecos_present,
        "BANK_OF_KOREA_API_KEY": ecos_present,
        "OPENAI_API_KEY": bool(OPENAI_API_KEY),
        "KIS_APP_KEY": bool(KIS_APP_KEY),
        "KIS_APP_SECRET": bool(KIS_APP_SECRET),
        "PUBLIC_DATA_API_KEY": bool(config_value("PUBLIC_DATA_API_KEY", "")),
        "KOSIS_API_KEY": bool(config_value("KOSIS_API_KEY", "")),
        "FRED_API_KEY": bool(config_value("FRED_API_KEY", "")),
    }
    state = build_data_trust_source_panel(
        snapshots=snapshot,
        portfolio_holding_count=len(parsed_rows),
        using_mock_portfolio=using_mock,
        api_key_status=api_key_status,
    )
    st.html(data_trust_source_panel_html(state))


def render_market_regime_macro_radar_section(
    snapshot: dict[str, Snapshot],
    code_to_name: dict[str, str],
    refresh_token: int,
) -> None:
    flag_value = os.getenv("STANCE_ENABLE_MARKET_REGIME_RADAR", "1").strip().lower()
    if flag_value in {"0", "false", "no", "off"}:
        return
    show_mock_value = config_value("SHOW_MOCK_DATA", config_value("DEMO_MODE", "false")).strip().lower()
    show_mock_macro = show_mock_value in {"1", "true", "yes", "on"}
    state = build_market_regime_macro_radar(snapshots=snapshot, allow_mock=show_mock_macro)
    st.html(market_regime_macro_radar_html(state))


def render_krw_rates_fx_dashboard_section(
    snapshot: dict[str, Snapshot],
    code_to_name: dict[str, str],
    refresh_token: int,
) -> None:
    flag_value = os.getenv("STANCE_ENABLE_KRW_RATES_FX", "1").strip().lower()
    if flag_value in {"0", "false", "no", "off"}:
        return
    holdings_text = str(st.session_state.get("portfolio_holdings_text", ""))
    parsed_rows, _ = parse_portfolio_text(holdings_text)
    holdings = getHoldings(parsed_rows, snapshot, code_to_name)
    state = build_krw_rates_fx_dashboard(snapshots=snapshot, holdings=holdings, allow_mock=True)
    st.html(krw_rates_fx_dashboard_html(state))


def render_valuation_relative_cheapness_panel_section(
    snapshot: dict[str, Snapshot],
    code_to_name: dict[str, str],
    refresh_token: int,
) -> None:
    flag_value = os.getenv("STANCE_ENABLE_VALUATION_PANEL", "1").strip().lower()
    if flag_value in {"0", "false", "no", "off"}:
        return
    state = build_valuation_relative_cheapness_panel(allow_mock=True)
    st.html(valuation_relative_cheapness_panel_html(state))


def render_fundamental_quality_panel_section(
    snapshot: dict[str, Snapshot],
    code_to_name: dict[str, str],
    refresh_token: int,
) -> None:
    flag_value = os.getenv("STANCE_ENABLE_FUNDAMENTAL_QUALITY", "1").strip().lower()
    if flag_value in {"0", "false", "no", "off"}:
        return
    state = build_fundamental_quality_panel(allow_mock=True)
    st.html(fundamental_quality_panel_html(state))


def render_dart_disclosure_catalyst_panel_section(
    snapshot: dict[str, Snapshot],
    code_to_name: dict[str, str],
    refresh_token: int,
) -> None:
    flag_value = os.getenv("STANCE_ENABLE_DART_CATALYSTS", "1").strip().lower()
    if flag_value in {"0", "false", "no", "off"}:
        return
    state = build_dart_disclosure_catalyst_panel(allow_mock=True)
    st.html(dart_disclosure_catalyst_panel_html(state))


def render_smart_money_flow_short_pressure_panel_section(
    snapshot: dict[str, Snapshot],
    code_to_name: dict[str, str],
    refresh_token: int,
) -> None:
    flag_value = os.getenv("STANCE_ENABLE_FLOW_SHORT_PRESSURE", "1").strip().lower()
    if flag_value in {"0", "false", "no", "off"}:
        return
    state = build_smart_money_flow_short_pressure_panel(allow_mock=True)
    st.html(smart_money_flow_short_pressure_panel_html(state))


def render_forward_alpha_ranking_panel_section(
    snapshot: dict[str, Snapshot],
    code_to_name: dict[str, str],
    refresh_token: int,
) -> None:
    flag_value = os.getenv("STANCE_ENABLE_FORWARD_ALPHA_RANKING", "1").strip().lower()
    if flag_value in {"0", "false", "no", "off"}:
        return
    state = build_forward_alpha_ranking_panel(allow_mock=True)
    st.html(forward_alpha_ranking_panel_html(state))


def render_portfolio_optimizer_alert_center_section(
    snapshot: dict[str, Snapshot],
    code_to_name: dict[str, str],
    refresh_token: int,
) -> None:
    flag_value = os.getenv("STANCE_ENABLE_PORTFOLIO_OPTIMIZER", "1").strip().lower()
    if flag_value in {"0", "false", "no", "off"}:
        return
    state = build_portfolio_optimizer_alert_center(allow_mock=True)
    st.html(portfolio_optimizer_alert_center_html(state))


def render_portfolio_intelligence_section(
    snapshot: dict[str, Snapshot],
    code_to_name: dict[str, str],
    refresh_token: int,
) -> None:
    holdings_text = str(st.session_state.get("portfolio_holdings_text", ""))
    parsed_rows, parse_errors = parse_portfolio_text(holdings_text)
    holdings = getHoldings(parsed_rows, snapshot, code_to_name)
    summary = getPortfolioSummary(holdings)
    current_allocation = summary.get("allocation", {})
    target_allocation = summary.get("targetAllocation", [])
    total_value = safe_float(summary.get("totalValue")) or 0.0
    drift = calculateAllocationDrift(current_allocation, target_allocation)
    suggestions = generateRebalanceSuggestions(current_allocation, target_allocation, total_value, {"threshold": 0.03, "minimum_trade_amount": 100_000})

    range_key = st.radio(
        "포트폴리오 기간",
        ["1M", "3M", "YTD", "1Y", "3Y", "All"],
        horizontal=True,
        index=5,
        key="portfolio_intelligence_range_label",
    )
    points = getPortfolioSnapshots()
    filtered_points = _filter_price_points(points, range_key)
    benchmark_points = _filter_price_points(getBenchmarkSeries(), range_key)
    returns = calculatePeriodReturns(filtered_points)
    cagr = calculateCAGR(filtered_points)
    volatility = calculateAnnualizedVolatility(returns)
    sharpe = calculateSharpeRatio(cagr, volatility, 0.03)
    max_drawdown = calculateMaxDrawdown(filtered_points)
    relative_return = calculateBenchmarkRelativeReturn(filtered_points, benchmark_points) if benchmark_points else None
    beta = calculateBeta(returns, calculatePeriodReturns(benchmark_points)) if benchmark_points else None
    concentration = calculateConcentrationRisk(holdings)

    cash_weight = safe_float(current_allocation.get("cash", {}).get("weight")) if isinstance(current_allocation.get("cash"), dict) else None
    cash_weight = cash_weight if cash_weight is not None else 0.0
    health_score, health_label, health_reasons, health_color = _portfolio_health_score(drift, volatility, max_drawdown, sharpe, concentration, cash_weight)
    insights = generatePortfolioInsightSummary(
        {
            "drift": drift,
            "maxDrawdown": max_drawdown,
            "sharpeRatio": sharpe,
            "rebalanceSuggestions": suggestions,
            "concentration": concentration,
        }
    )
    watchlist_items = _holding_stock_signals(holdings, snapshot) or getWatchlist()
    watchlist_signals = generateWatchlistSignals(watchlist_items)

    parse_notice = ""
    if parse_errors:
        parse_notice = f"<span class='pi-badge warn'>{html.escape('입력 확인: ' + ' / '.join(parse_errors[:2]))}</span>"
    st.html(
        f"""
        <section class="portfolio-intelligence-shell" aria-label="포트폴리오 인텔리전스">
            <div class="portfolio-intelligence-title">
                <div>
                    <strong>포트폴리오 인텔리전스</strong>
                    <span>위험, 배분 이탈, 리밸런싱 후보를 한 화면에서 점검합니다.</span>
                </div>
                <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                    {parse_notice}
                    <span class="pi-badge info">의사결정 보조</span>
                </div>
            </div>
            <div class="portfolio-intelligence-grid">
                {portfolio_health_card_html(health_score, health_label, health_reasons, health_color)}
                {allocation_drift_card_html(drift)}
                {rebalance_candidates_card_html(suggestions)}
            </div>
        </section>
        """
    )

    portfolio_metrics = {
        "cagr": cagr,
        "periodReturn": _series_return(filtered_points),
        "volatility": volatility,
        "sharpe": sharpe,
        "maxDrawdown": max_drawdown,
        "beta": beta,
    }
    st.html(
        f"""
        <section class="portfolio-intelligence-shell" aria-label="포트폴리오 인텔리전스 상세">
            <div class="portfolio-intelligence-title">
                <div>
                    <strong>리스크·신호·인사이트</strong>
                    <span>수익·위험·집중도·보유 신호를 검토 후보 관점으로 정리합니다.</span>
                </div>
                <span class="pi-badge warn">리스크 확인</span>
            </div>
            <div class="pi-detail-grid">
                {risk_return_panel_html(portfolio_metrics, relative_return)}
                {concentration_card_html(holdings, concentration)}
                {insight_engine_card_html(insights, portfolio_metrics)}
                {watchlist_signals_card_html(watchlist_signals)}
            </div>
        </section>
        """
    )

    col_chart_a, col_chart_b = st.columns([1.1, 1.0])
    with col_chart_a:
        st.pyplot(plot_portfolio_value_chart(filtered_points, benchmark_points), clear_figure=True)
    with col_chart_b:
        st.pyplot(plot_portfolio_drawdown_chart(calculateDrawdownSeries(filtered_points)), clear_figure=True)


def _korea_grade_color(grade: str) -> str:
    return {
        "STRONG_REVIEW": getChartSeriesColor("up"),
        "BUY_REVIEW": getChartSeriesColor("up"),
        "WATCHLIST": "#38bdf8",
        "NEUTRAL": "#94a3b8",
        "CAUTION": getChartSeriesColor("warning", context="risk"),
        "EXCLUDE": getChartSeriesColor("critical", context="risk"),
    }.get(str(grade), "#94a3b8")


def _korea_latest_price(code: str) -> float | None:
    history = getKoreaPriceHistory(code)
    if not history:
        return None
    return safe_float(getattr(history[-1], "close", None))


def _korea_factor_items(score: Any) -> list[tuple[str, str, float]]:
    factors = getattr(score, "factor_scores", None)
    if factors is None:
        return []
    return [
        ("모멘텀", "momentum", float(getattr(factors, "momentum", 0) or 0)),
        ("밸류", "value", float(getattr(factors, "value", 0) or 0)),
        ("퀄리티", "quality", float(getattr(factors, "quality", 0) or 0)),
        ("실적", "earnings", float(getattr(factors, "earnings_revision", 0) or 0)),
        ("수급", "supplyDemand", float(getattr(factors, "supply_demand", 0) or 0)),
        ("공시", "disclosure", float(getattr(factors, "event_catalyst", 0) or 0)),
        ("밸류업", "valueUp", float(getattr(factors, "value_up", 0) or 0)),
        ("유동성", "liquidity", float(getattr(factors, "liquidity", 0) or 0)),
        ("리스크", "risk", float(getattr(factors, "risk", 0) or 0)),
    ]


def _korea_factor_dict(score: Any) -> dict[str, float]:
    return {label: value for label, _, value in _korea_factor_items(score)}


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
        source=", ".join(source_bits) if source_bits else "스냅샷 없음",
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
    color = getKoreanMarketColorToken(number)
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


class _HtmlCell(str):
    pass


def _korea_widget_key(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in (prefix,) + parts)
    return "korea_" + hashlib.md5(raw.encode("utf-8")).hexdigest()


def _korea_display_label(text: Any) -> str:
    raw = str(text or "").strip()
    lower = raw.lower()
    mapped = {
        "positive": korea_format_direction(raw),
        "neutral": korea_format_direction(raw),
        "negative": korea_format_direction(raw),
        "mixed": korea_format_direction(raw),
        "low": korea_format_severity(raw),
        "medium": korea_format_severity(raw),
        "high": korea_format_severity(raw),
        "critical": korea_format_severity(raw),
        "panic": korea_format_regime(raw),
        "risk_off": korea_format_regime(raw),
        "risk_on": korea_format_regime(raw),
        "active": "활성",
        "waiting": "대기",
        "pending": "대기",
        "normal": "정상",
        "no data": "데이터 부족",
        "mock data": "Mock data",
    }.get(lower)
    return mapped if mapped is not None else (raw or "-")


def _korea_tone_for_value(value: Any, default: str = "muted") -> str:
    raw = str(value or "").strip().lower()
    if raw in {"positive", "통과", "정상", "사용 가능", "검토 후보", "강한 검토 후보", "low"}:
        return "good"
    if raw in {"negative", "high", "critical", "panic", "방어 우선", "활성", "제외 후보", "리스크 관리"}:
        return "risk"
    if raw in {"medium", "주의", "보수 검토", "검증 중", "기록 대기", "대기"}:
        return "warn"
    if raw in {"neutral", "mixed", "중립", "관찰 후보", "비중 보강 검토", "낮음"}:
        return "info"
    return default


def _korea_badge(text: str, tone: str = "muted") -> _HtmlCell:
    label = _korea_display_label(text)
    resolved_tone = tone if tone != "auto" else _korea_tone_for_value(text)
    return _HtmlCell(f'<span class="korea-badge {html.escape(resolved_tone)}">{html.escape(label)}</span>')


def _korea_evidence(text: str) -> _HtmlCell:
    return _HtmlCell(f'<span class="korea-evidence">{html.escape(str(text or "-"))}</span>')


def _korea_stock_cell(name: Any, code: Any = "", meta: Any = "") -> _HtmlCell:
    meta_bits = [str(bit) for bit in [code, meta] if str(bit or "").strip()]
    meta_text = " · ".join(meta_bits)
    meta_html = f"<span>{html.escape(meta_text)}</span>" if meta_text else ""
    return _HtmlCell(
        f'<span class="korea-stock-cell"><strong>{html.escape(str(name or "-"))}</strong>{meta_html}</span>'
    )


def _korea_factor_cell(value: Any) -> _HtmlCell:
    bucket = korea_heatmap_bucket(value)
    number = safe_float(value)
    score = "-" if number is None else f"{number:.0f}"
    return _HtmlCell(
        f'<span class="korea-heat korea-os-heatmap-cell {html.escape(bucket["class"])}"><strong>{score}</strong><small>{html.escape(bucket["label"])}</small></span>'
    )


def _safe_sharpe_text(value: Any) -> str:
    number = safe_float(value)
    if number is None:
        return "-"
    number = korea_normalize_negative_zero(number) or 0.0
    return f"{number:.2f}"


def _korea_percent_text(value: Any, signed: bool = False, digits: int = 1) -> str:
    return korea_format_percent(korea_normalize_negative_zero(value), signed=signed, digits=digits)


def _korea_module_title(title: str, subtitle: str = "", meta: str = "") -> None:
    st.markdown(
        f"""
        <div class="korea-module-title korea-os-section-header">
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
        "good": f"color:{getChartSeriesColor('up')};",
        "info": "color:#38bdf8;",
        "warn": "color:#f59e0b;",
        "risk": f"color:{getChartSeriesColor('down')};",
    }.get(tone, "")
    return f"""
    <div class="korea-metric">
        <small>{html.escape(label)}</small>
        <strong style="{tone_style}">{html.escape(str(value))}</strong>
    </div>
    """


def _korea_metric_card_html(label: str, value: str, tone: str = "", detail: str = "") -> str:
    tone_class = {
        "good": "tone-good",
        "info": "tone-info",
        "warn": "tone-warn",
        "risk": "tone-risk",
    }.get(tone, "")
    detail_html = f"<span>{html.escape(detail)}</span>" if detail else ""
    return f"""
    <div class="korea-metric-card">
        <small>{html.escape(label)}</small>
        <strong class="{tone_class}">{html.escape(str(value))}</strong>
        {detail_html}
    </div>
    """


def _korea_flow_cell(value: Any) -> _HtmlCell:
    number = safe_float(value)
    if number is None:
        return _HtmlCell('<span class="korea-flow-flat">-</span>')
    css_class = "korea-flow-pos" if number > 0 else "korea-flow-neg" if number < 0 else "korea-flow-flat"
    return _HtmlCell(f'<span class="{css_class}">{html.escape(korea_format_trading_value(number))}</span>')


def _korea_flow_signal(value: Any, positive: str, negative: str, neutral: str = "중립") -> _HtmlCell:
    number = safe_float(value)
    if number is None or abs(number) < 1:
        return _korea_badge(neutral, "muted")
    return _korea_badge(positive if number > 0 else negative, "good" if number > 0 else "warn")


def _korea_module_health_html(module_key: str, active: bool, contribution: str, updated_at: str = "-") -> str:
    status = "active" if active else "no data"
    tone = "good" if active else "muted"
    return f"""
    <div class="korea-module-health">
        <strong>{html.escape(formatModuleLabel(module_key))}</strong>
        <div>{_korea_badge('사용 가능' if active else '데이터 부족', tone)}</div>
        <span>{html.escape(contribution)}<br/>업데이트: {html.escape(updated_at or '-')}</span>
    </div>
    """


def _fear_greed_segment_label(score: float | None) -> str:
    if score is None:
        return "데이터 부족"
    if score <= 20:
        return "0-20 극단적 공포"
    if score <= 40:
        return "21-40 공포"
    if score <= 60:
        return "41-60 중립"
    if score <= 80:
        return "61-80 탐욕"
    return "81-100 극단적 탐욕"


def render_fear_greed_visibility_gauge(score: float | None, label: str, color: str, advice: str) -> None:
    score_text = "N/A" if score is None else f"{max(0, min(100, score)):.0f}"
    impact_note = (
        "데이터 확인 전까지 보수적으로 해석합니다."
        if score is None
        else "공포 구간: 리스크 관리 우선"
        if score <= 40
        else "탐욕 구간: 과열 주의"
        if score >= 61
        else "중립 구간: 선별 검토"
    )
    st.html(
        f"""
        <div class="fear-greed-gauge">
            <div class="fear-greed-value">
                <strong style="color:{html.escape(color)};">{html.escape(score_text)}</strong>
                <span>/100 · {html.escape(label)} · {html.escape(_fear_greed_segment_label(score))}</span>
            </div>
            <div class="fear-greed-segments" aria-label="공포 탐욕 구간">
                <span class="fg-extreme-fear" title="0-20 극단적 공포"></span>
                <span class="fg-fear" title="21-40 공포"></span>
                <span class="fg-neutral" title="41-60 중립"></span>
                <span class="fg-greed" title="61-80 탐욕"></span>
                <span class="fg-extreme-greed" title="81-100 극단적 탐욕"></span>
            </div>
            <div class="korea-card-subtitle">0에 가까울수록 공포, 100에 가까울수록 탐욕입니다. 극단 구간에서는 추세 추종보다 리스크 관리가 우선입니다.</div>
            <div class="korea-card-subtitle" style="margin-top:7px;"><b>{html.escape(impact_note)}</b> · {html.escape(advice)}</div>
        </div>
        """
    )


def _korea_table_html(rows: list[dict[str, Any]], columns: list[str] | None = None) -> str:
    if not rows:
        return _korea_empty_html("표시할 데이터가 없습니다.", "데이터 공급원 또는 필터 조건을 확인하세요.")
    columns = columns or list(rows[0].keys())
    header = "".join(f"<th>{html.escape(str(col))}</th>" for col in columns)
    body_rows: list[str] = []
    for row in rows:
        cells = []
        for col in columns:
            value = row.get(col, "-")
            css = "text"
            if any(token in str(col) for token in ["점수", "수익", "위험", "비중", "금액", "수량", "승률", "성과", "낙폭", "CAGR", "MDD", "Sharpe", "Rank", "IC", "P@10", "20D", "외국인", "기관", "연기금", "합산", "중요도", "신뢰도"]):
                css = "num"
            if isinstance(value, _HtmlCell):
                cells.append(f'<td class="{css}">{value}</td>')
            else:
                cells.append(f'<td class="{css}">{html.escape(str(value))}</td>')
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    return f"""
    <div class="korea-table-wrap korea-os-table-wrap">
        <table class="korea-table korea-os-table"><thead><tr>{header}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>
    </div>
    """


def init_korea_interaction_state() -> SelectedContext:
    if "korea_context" not in st.session_state:
        try:
            st.session_state.korea_context = parse_query_context(st.query_params)
        except Exception:
            st.session_state.korea_context = SelectedContext()
    context = st.session_state.get("korea_context")
    if not isinstance(context, SelectedContext):
        context = SelectedContext()
        st.session_state.korea_context = context
    else:
        field_names = tuple(SelectedContext.__dataclass_fields__.keys())
        if any(not hasattr(context, name) for name in field_names):
            context = SelectedContext(**{name: getattr(context, name, None) for name in field_names})
            st.session_state.korea_context = context
    return context


def _sync_korea_query_params(context: SelectedContext) -> None:
    try:
        query = serialize_query_context(context)
        st.query_params.clear()
        for key, value in query.items():
            st.query_params[key] = value
    except Exception:
        pass


def update_korea_context(rerun: bool = True, **updates: Any) -> SelectedContext:
    current = init_korea_interaction_state()
    context = merge_context(current, **updates)
    st.session_state.korea_context = context
    _sync_korea_query_params(context)
    if rerun:
        st.rerun()
    return context


def _selected_context() -> SelectedContext:
    return init_korea_interaction_state()


def render_module_anchor(module_key: str) -> None:
    anchor = MODULE_IDS.get(module_key)
    if anchor:
        st.markdown(f'<span id="{html.escape(anchor)}"></span>', unsafe_allow_html=True)


def _module_link_label(module_key: str) -> str:
    label = formatModuleLabel(module_key)
    return label if label != "-" else str(module_key)


def _render_related_module_buttons(module_keys: tuple[str, ...] | list[str], key_prefix: str) -> None:
    valid_modules = [module for module in module_keys if module in MODULE_IDS]
    if not valid_modules:
        return
    st.caption("관련 모듈 바로가기")
    cols = st.columns(min(4, len(valid_modules)))
    for idx, module_key in enumerate(valid_modules):
        with cols[idx % len(cols)]:
            if st.button(_module_link_label(module_key), key=_korea_widget_key(key_prefix, "module", module_key, idx), use_container_width=True):
                update_korea_context(selectedModule=module_key, selectedMetric=MODULE_DEFAULT_METRIC.get(module_key), sourceModule=module_key)


def render_korea_context_bar(key_scope: str = "") -> None:
    context = _selected_context()
    active = any(
        [
            context.selectedStockCode,
            context.selectedMetric,
            context.selectedFactor,
            context.selectedModule,
            context.selectedDate,
            context.selectedDisclosureId,
            context.selectedQueueItemId,
            context.selectedScenarioId,
            context.selectedThesisId,
            context.selectedRiskRule,
        ]
    )
    if not active:
        st.html(
            """
            <div class="korea-context-bar">
                <strong>연결 인텔리전스</strong>
                <div class="korea-context-meta">종목, 점수, 팩터, 공시, 시나리오를 선택하면 정의·공식·관련 근거가 연결됩니다.</div>
            </div>
            """
        )
        return
    parts = []
    if context.selectedStockCode:
        stock = context.selectedStockCode if not context.selectedStockName else f"{context.selectedStockName} ({context.selectedStockCode})"
        parts.append(f"종목 {stock}")
    if context.selectedModule:
        parts.append(f"모듈 {formatModuleLabel(context.selectedModule)}")
    if context.selectedMetric:
        parts.append(f"지표 {formatMetricLabel(context.selectedMetric)}")
    if context.selectedFactor:
        parts.append(f"팩터 {formatFactorLabel(context.selectedFactor)}")
    if context.selectedScenarioId:
        parts.append(f"시나리오 {context.selectedScenarioId}")
    if context.selectedThesisId:
        parts.append(f"가설 {context.selectedThesisId}")
    if context.selectedRiskRule:
        parts.append(f"알림 {context.selectedRiskRule}")
    st.html(
        f"""
        <div class="korea-context-bar korea-selected-card">
            <strong>선택됨</strong>
            <div class="korea-context-meta">{html.escape(' · '.join(parts))}</div>
        </div>
        """
    )
    if st.button("선택 해제", key=_korea_widget_key("korea_context_clear", key_scope)):
        st.session_state.korea_context = SelectedContext()
        _sync_korea_query_params(st.session_state.korea_context)
        st.rerun()


def render_explanation_panel(extra_evidence: list[str] | None = None, key_scope: str = "") -> None:
    context = _selected_context()
    explanation = explanation_for_factor(context.selectedFactor) if context.selectedFactor else None
    if explanation is None:
        explanation = get_metric_explanation(context.selectedMetric)
    if explanation is None and context.selectedModule:
        explanation = get_metric_explanation(MODULE_DEFAULT_METRIC.get(context.selectedModule))
    if explanation is None:
        return
    related = explanation.relatedModules or related_modules_for_metric(explanation.key)
    assumptions = "".join(f"<li>{html.escape(item)}</li>" for item in explanation.assumptions)
    evidence = "".join(f"<li>{html.escape(item)}</li>" for item in (extra_evidence or []) if item)
    related_html = "".join(f'<span class="korea-mini-link">{html.escape(formatModuleLabel(module))}</span>' for module in related if module in MODULE_IDS)
    value = ""
    if context.selectedMetric:
        value = f"<div class='korea-explain-muted'>선택 지표: {html.escape(formatMetricLabel(context.selectedMetric))}</div>"
    if context.selectedFactor:
        value += f"<div class='korea-explain-muted'>선택 팩터: {html.escape(formatFactorLabel(context.selectedFactor))}</div>"
    st.html(
        f"""
        <div class="korea-explanation-panel">
            <strong>{html.escape(explanation.label)}</strong>
            {value}
            <div class="korea-explain-muted" style="margin-top:8px;"><b>정의</b><br/>{html.escape(explanation.definition)}</div>
            <div class="korea-explain-muted" style="margin-top:8px;"><b>공식/방식</b><br/>{html.escape(explanation.formula)}</div>
            <div class="korea-explain-muted" style="margin-top:8px;"><b>해석</b><br/>{html.escape(explanation.interpretation)}</div>
            {f'<div class="korea-explain-muted" style="margin-top:8px;"><b>가정</b><ul>{assumptions}</ul></div>' if assumptions else ''}
            {f'<div class="korea-explain-muted" style="margin-top:8px;"><b>선택 근거</b><ul>{evidence}</ul></div>' if evidence else ''}
            <div style="margin-top:10px;">{related_html}</div>
        </div>
        """
    )
    _render_related_module_buttons(tuple(related), _korea_widget_key("related", key_scope, explanation.key, context.selectedStockCode))


def render_explainable_metric_button(label: str, value: str, metric_key: str, module_key: str, stock_code: str | None = None, stock_name: str | None = None, tone: str = "", help_text: str | None = None, key_scope: str = "") -> None:
    selected = _selected_context()
    is_selected = selected.selectedMetric == metric_key and (stock_code is None or selected.selectedStockCode == stock_code)
    button_label = f"{'선택됨 · ' if is_selected else ''}{label}: {value}"
    if st.button(button_label, key=_korea_widget_key("metric", key_scope, module_key, stock_code, metric_key, label), use_container_width=True, help=help_text or f"{label} 정의와 근거를 봅니다."):
        update_korea_context(selectedStockCode=stock_code or selected.selectedStockCode, selectedStockName=stock_name or selected.selectedStockName, selectedMetric=metric_key, selectedModule=module_key, sourceModule=module_key)


def render_linked_stock_button(code: str, name: str, module_key: str, suffix: str = "") -> None:
    context = _selected_context()
    selected = context.selectedStockCode == code
    label = f"{'선택됨 · ' if selected else ''}{name} ({code})"
    if suffix:
        label = f"{label} · {suffix}"
    if st.button(label, key=_korea_widget_key("stock", module_key, code, suffix), use_container_width=True):
        update_korea_context(selectedStockCode=code, selectedStockName=name, selectedModule=module_key, sourceModule=module_key)


def render_linked_factor_button(factor_label: str, factor_key: str, score_value: Any, module_key: str, stock_code: str | None = None, stock_name: str | None = None, key_scope: str = "") -> None:
    bucket = korea_heatmap_bucket(score_value)
    number = safe_float(score_value)
    score_text = "-" if number is None else f"{number:.0f}"
    context = _selected_context()
    selected = context.selectedFactor == factor_key and (stock_code is None or context.selectedStockCode == stock_code)
    label = f"{'선택됨 · ' if selected else ''}{factor_label} {score_text} · {bucket['label']}"
    if st.button(label, key=_korea_widget_key("factor", key_scope, module_key, stock_code, factor_key), use_container_width=True):
        update_korea_context(selectedStockCode=stock_code or context.selectedStockCode, selectedStockName=stock_name or context.selectedStockName, selectedFactor=factor_key, selectedMetric=FACTOR_TO_METRIC.get(factor_key), selectedModule=module_key, sourceModule=module_key)


def render_korea_market_regime_card(market_status: Any) -> None:
    regime_label = {"risk_on": "위험 선호", "neutral": "중립", "risk_off": "위험 회피", "panic": "패닉", "recovery": "회복"}.get(str(getattr(market_status, "regime", "neutral")), str(getattr(market_status, "regime", "neutral")))
    score = max(0.0, min(100.0, safe_float(getattr(market_status, "regime_score", None)) or 50.0))
    reasons = "".join(f"<div class='portfolio-list-item'>{html.escape(str(reason))}</div>" for reason in getattr(market_status, "reason", [])[:4])
    kospi_text = _format_market_number(getattr(market_status, "kospi_close", None), 2)
    kosdaq_text = _format_market_number(getattr(market_status, "kosdaq_close", None), 2)
    usd_text = _format_market_number(getattr(market_status, "usd_krw", None), 2)
    kr3y_text = _format_market_number(getattr(market_status, "bond_yield_3y", None), 2, "%")
    live_label = "현재 데이터" if getattr(market_status, "is_live", False) else "지연/보조 데이터"
    source_text = f"{live_label} · {getattr(market_status, 'updated_at', '-') or '-'}"
    st.html(f"""
        <div class="korea-card">
            <div class="korea-card-head"><div><div class="korea-card-title">한국시장 국면</div><div class="korea-card-subtitle">지수, 환율, 금리와 장기 추세를 함께 반영한 시장 환경 점수</div></div><span class="korea-badge {_korea_grade_badge_class('NEUTRAL')}">{html.escape(regime_label)}</span></div>
            <div class="korea-score">{score:.0f}/100</div><div class="portfolio-progress"><div class="portfolio-progress-fill" style="width:{score:.0f}%;"></div></div>
            <div class="portfolio-card-sub">KOSPI {kospi_text} {_format_market_return(getattr(market_status, "kospi_return_1d", None))} · KOSDAQ {kosdaq_text} {_format_market_return(getattr(market_status, "kosdaq_return_1d", None))}<br/>USD/KRW {usd_text} · 국고채3Y {kr3y_text}<br/>데이터 기준: {html.escape(source_text)}</div>{reasons}
        </div>
    """)


def render_korea_top_candidates_card(candidates: list[Any]) -> None:
    rows = []
    for idx, score in enumerate(candidates[:6], 1):
        grade = str(getattr(score, "recommendation_grade", "NEUTRAL"))
        color = _korea_grade_color(grade)
        reasons = " / ".join(getattr(score, "positive_reasons", [])[:2])
        rows.append(f"""
            <div class="portfolio-list-item"><strong>{idx}. {html.escape(getattr(score, "name", ""))}</strong><span style="float:right; color:{color}; font-weight:900;">{getattr(score, "total_score", 0):.0f}</span><br/>{html.escape(getattr(score, "code", ""))} · {html.escape(korea_format_grade(grade))} · 초과수익 {html.escape(korea_format_percent(getattr(score, "expected_excess_return_3m", None), signed=True))}<br/><span style="color:#c4b5fd;">{html.escape(reasons)}</span></div>
        """)
    st.html(f"""
        <div class="korea-card"><div class="korea-card-head"><div><div class="korea-card-title">한국주식 알파 후보</div><div class="korea-card-subtitle">점수와 신뢰도를 함께 확인하는 검토 후보 목록</div></div><span class="korea-badge info">상위 {len(candidates[:6])}개</span></div>{''.join(rows) if rows else _korea_empty_html('표시할 후보가 없습니다.', '필터 조건을 낮추거나 데이터를 갱신하세요.')}</div>
    """)


def render_korea_risk_control_panel(data: dict[str, Any]) -> None:
    summary = data.get("riskSummary", {})
    alerts = "".join(f"<div class='portfolio-list-item'>{html.escape(str(item))}</div>" for item in summary.get("risk_alerts", [])[:4])
    avg_conf = summary.get("avg_confidence")
    st.html(f"""
        <div class="korea-card"><div class="korea-card-head"><div><div class="korea-card-title">리스크 관리</div><div class="korea-card-subtitle">신규 검토 전 확인해야 할 위험 플래그</div></div><span class="korea-badge {'risk' if summary.get('high_risk_count', 0) else 'good'}">{summary.get("high_risk_count", 0)}건</span></div><div class="korea-score">{summary.get("high_risk_count", 0)}</div><div class="portfolio-card-sub">리스크 플래그 후보 수 · 평균 신뢰도 {html.escape(korea_format_confidence(avg_conf))}</div>{alerts if alerts else _korea_empty_html('중대한 리스크 플래그가 없습니다.', '단, 공시와 유동성은 계속 확인해야 합니다.')}</div>
    """)


def render_korea_recommendation_table(scores: list[Any]) -> None:
    render_module_anchor("investmentAlgorithm")
    _korea_module_title("투자검토 알고리즘", "확정 매수·매도가 아니라 점수, 신뢰도, 기대수익, 하방위험을 함께 보는 검토 후보 표입니다.", f"{len(scores)}개 표시")
    if scores:
        context = _selected_context()
        active_score = next((row for row in scores if getattr(row, "code", "") == context.selectedStockCode), scores[0])
        active_code = str(getattr(active_score, "code", "") or "")
        active_name = str(getattr(active_score, "name", "") or active_code)
        active_grade = str(getattr(active_score, "recommendation_grade", "NEUTRAL") or "NEUTRAL")
        active_score_value = safe_float(getattr(active_score, "total_score", None)) or 0.0
        active_confidence = safe_float(getattr(active_score, "confidence", None))
        expected_return = safe_float(getattr(active_score, "expected_return_3m", None))
        downside_risk = safe_float(getattr(active_score, "downside_risk", None))
        positive_preview = " / ".join(list(getattr(active_score, "positive_reasons", []) or [])[:2]) or "긍정 근거 데이터 부족"
        negative_preview = " / ".join(list(getattr(active_score, "negative_reasons", []) or [])[:2]) or "뚜렷한 반대 근거 없음"
        risk_preview = ", ".join(list(getattr(active_score, "risk_flags", []) or [])[:2]) or "주요 리스크 플래그 없음"
        stock_cols = st.columns(min(4, len(scores[:4])))
        for idx, score in enumerate(scores[:4]):
            with stock_cols[idx % len(stock_cols)]:
                render_linked_stock_button(str(getattr(score, "code", "") or ""), str(getattr(score, "name", "") or getattr(score, "code", "")), "investmentAlgorithm", korea_format_score(getattr(score, "total_score", None)))
        st.html(
            f"""
            <div class="korea-decision-card">
                <div class="korea-score-hero">
                    <span>{html.escape(active_name)} ({html.escape(active_code)})</span>
                    <strong>{active_score_value:.0f}</strong>
                    <span>/100 · 총점</span>
                    <div class="portfolio-progress" aria-label="총점 진행률"><div class="portfolio-progress-fill" style="width:{max(0, min(100, active_score_value)):.0f}%;"></div></div>
                    {_korea_badge(korea_format_grade(active_grade), _korea_grade_badge_class(active_grade))}
                </div>
                <div>
                    <div class="korea-card-head" style="border-bottom:0; margin-bottom:8px;">
                        <div>
                            <div class="korea-card-title">한국주식 팩터·수급·공시·리스크 기반 검토 결과</div>
                            <div class="korea-card-subtitle">확정 지시가 아니라 검토 우선순위입니다. 점수와 하방위험을 함께 확인합니다.</div>
                        </div>
                    </div>
                    <div class="korea-hero-metrics">
                        {_korea_metric_card_html("신뢰도", korea_format_confidence(active_confidence), "warn", "중립·검증 필요")}
                        {_korea_metric_card_html("3M 기대수익", korea_format_percent(expected_return, signed=True), "good" if (expected_return or 0) > 0 else "muted", "비용 전 추정")}
                        {_korea_metric_card_html("하방위험", korea_format_percent(downside_risk), "risk", "손실 제한 기준")}
                        {_korea_metric_card_html("검토비중", korea_format_percent(getattr(active_score, "suggested_weight", None)), "info", "상한 확인")}
                    </div>
                    <div class="thesis" style="background:rgba(2,6,23,.24); border-color:rgba(196,181,253,.18); color:#dbeafe;">
                        <b>긍정 근거</b> {html.escape(positive_preview)}<br/>
                        <b>반대 근거</b> {html.escape(negative_preview)}<br/>
                        <b>리스크 확인</b> {html.escape(risk_preview)}
                    </div>
                </div>
            </div>
            """
        )
        metric_cols = st.columns(5)
        metric_specs = [
            ("총점", korea_format_score(getattr(active_score, "total_score", None)), "totalScore"),
            ("등급", korea_format_grade(str(getattr(active_score, "recommendation_grade", ""))), "recommendationGrade"),
            ("신뢰도", korea_format_confidence(getattr(active_score, "confidence", None)), "confidence"),
            ("3M 기대수익", korea_format_percent(getattr(active_score, "expected_return_3m", None), signed=True), "expectedReturn3M"),
            ("하방위험", korea_format_percent(getattr(active_score, "downside_risk", None)), "downsideRisk"),
        ]
        for col, (label, value, metric_key) in zip(metric_cols, metric_specs):
            with col:
                render_explainable_metric_button(label, value, metric_key, "investmentAlgorithm", active_code, active_name, key_scope="algo")
    rows = []
    for score in scores:
        latest = _korea_latest_price(getattr(score, "code", ""))
        grade = str(getattr(score, "recommendation_grade", ""))
        evidence = " / ".join(list(getattr(score, "positive_reasons", []) or [])[:2] + list(getattr(score, "negative_reasons", []) or [])[:1])
        rows.append({"종목": _korea_stock_cell(getattr(score, "name", ""), getattr(score, "code", ""), korea_format_market_label(getattr(score, "market", ""))), "검토상태": _korea_badge(korea_format_grade(grade), _korea_grade_badge_class(grade)), "총점": korea_format_score(getattr(score, "total_score", None)), "신뢰도": korea_format_confidence(getattr(score, "confidence", None)), "현재가": korea_format_krw(latest), "3M 기대": korea_format_percent(getattr(score, "expected_return_3m", None), signed=True), "하방위험": korea_format_percent(getattr(score, "downside_risk", None)), "검토비중": korea_format_percent(getattr(score, "suggested_weight", None)), "근거": _korea_evidence(evidence)})
    st.html(f'<div class="korea-card compact">{_korea_table_html(rows)}</div>')


def render_korea_signal_breakdown(scores: list[Any]) -> None:
    if not scores:
        st.html(f'<div class="korea-card compact">{_korea_empty_html("선택 종목 상세 근거가 없습니다.")}</div>')
        return
    context = _selected_context()
    score = next((row for row in scores if getattr(row, "code", "") == context.selectedStockCode), scores[0])
    positives = "".join(f"<div class='portfolio-list-item'>{html.escape(str(item))}</div>" for item in getattr(score, "positive_reasons", [])[:5])
    negatives = "".join(f"<div class='portfolio-list-item'>{html.escape(str(item))}</div>" for item in getattr(score, "negative_reasons", [])[:5])
    st.html(f"""
        <div class="korea-card compact"><div class="korea-card-head"><div><div class="korea-card-title">선택 종목 상세 근거</div><div class="korea-card-subtitle">{html.escape(getattr(score, 'name', ''))} ({html.escape(getattr(score, 'code', ''))}) · 데이터 기준 {html.escape(str(getattr(score, 'last_updated', '-') or '-'))}</div></div><span class="korea-badge {_korea_grade_badge_class(str(getattr(score, 'recommendation_grade', 'NEUTRAL')))}">{html.escape(korea_format_grade(str(getattr(score, 'recommendation_grade', 'NEUTRAL'))))}</span></div><div class="korea-card-title" style="margin-top:12px;">긍정 근거</div>{positives or _korea_empty_html('긍정 근거 부족')}<div class="korea-card-title" style="margin-top:12px;">반대 근거·리스크</div>{negatives or _korea_empty_html('주요 리스크 없음')}</div>
    """)


def render_korea_factor_heatmap(scores: list[Any]) -> None:
    render_module_anchor("factorHeatmap")
    _korea_module_title("팩터 히트맵", "종목별 강점과 약점을 같은 색상 기준으로 비교합니다.")
    st.html(
        """
        <div class="korea-legend" aria-label="팩터 히트맵 범례">
            <span>취약 0-29</span><span>약함 30-44</span><span>보통 45-59</span><span>양호 60-74</span><span>강함 75+</span>
        </div>
        """
    )
    with st.expander("팩터 설명 연결", expanded=False):
        for score in scores[:4]:
            code = str(getattr(score, "code", "") or "")
            name = str(getattr(score, "name", "") or code)
            render_linked_stock_button(code, name, "factorHeatmap", korea_format_score(getattr(score, "total_score", None)))
            cols = st.columns(3)
            for idx, (label, factor_key, value) in enumerate(_korea_factor_items(score)):
                with cols[idx % 3]:
                    render_linked_factor_button(label, factor_key, value, "factorHeatmap", code, name, key_scope="heat")
    rows = []
    for score in scores[:10]:
        row = {"종목": _korea_stock_cell(getattr(score, "name", ""), getattr(score, "code", ""))}
        for label, _, value in _korea_factor_items(score):
            row[label] = _korea_factor_cell(value)
        rows.append(row)
    st.html(f'<div class="korea-card compact">{_korea_table_html(rows)}</div>')


def render_korea_supply_demand_radar(scores: list[Any]) -> None:
    render_module_anchor("supplyDemandRadar")
    _korea_module_title("수급 레이더", "최근 20거래일 외국인·기관·연기금 순매수 흐름을 평가합니다.")
    rows = []
    for score in scores[:8]:
        code = str(getattr(score, "code", "") or "")
        supply = getKoreaSupplyDemand(code)
        last_20 = supply[-20:]
        foreign = sum(safe_float(getattr(row, "foreign_net_buy", 0)) or 0 for row in last_20)
        institution = sum(safe_float(getattr(row, "institution_net_buy", 0)) or 0 for row in last_20)
        pension = sum(safe_float(getattr(row, "pension_net_buy", 0)) or 0 for row in last_20)
        total = foreign + institution + pension
        signal = "외국인·기관 합산 순매수" if total > 0 else "수급 약화"
        rows.append({
            "종목": _korea_stock_cell(getattr(score, "name", ""), code),
            "외국인 20D": _korea_flow_cell(foreign),
            "기관 20D": _korea_flow_cell(institution),
            "연기금 20D": _korea_flow_cell(pension),
            "합산": _korea_flow_cell(total),
            "신호": _korea_flow_signal(total, signal, "수급 약화"),
            "해석": _korea_evidence("20거래일 누적 기준 · 순매수는 가격 지지 근거, 순매도는 추격 제한 근거"),
        })
    st.html(f'<div class="korea-card compact">{_korea_table_html(rows)}</div>')


def render_korea_disclosure_radar(disclosures: list[Any]) -> None:
    render_module_anchor("disclosureRadar")
    _korea_module_title("공시·이벤트 레이더", "공시 리스크와 촉매를 신규 검토 전에 먼저 확인합니다.")
    rows = []
    buttons: list[tuple[str, str, str, str]] = []
    context = _selected_context()
    for event in disclosures[:8]:
        event_id = str(getattr(event, "id", "") or f"{getattr(event, 'code', '')}-{getattr(event, 'date', '')}")
        code = str(getattr(event, "code", "") or "")
        title = str(getattr(event, "title", "") or getattr(event, "summary", "") or "공시 이벤트")
        sentiment = str(getattr(event, "sentiment", "") or "neutral")
        tone = "good" if sentiment == "positive" else "risk" if sentiment == "negative" else "muted"
        buttons.append((event_id, code, title, str(getattr(event, "date", "-"))))
        rows.append({
            "일자": getattr(event, "date", ""),
            "종목": code,
            "분류": _korea_badge(getattr(event, "category", "") or "event", "info"),
            "감성": _korea_badge(sentiment, tone),
            "중요도": _HtmlCell(f"<span class='korea-os-score'>{safe_float(getattr(event, 'importance', None)) or 0:.0f}</span>"),
            "요약": _korea_evidence(getattr(event, "summary", "") or title),
        })
        if context.selectedDisclosureId == event_id:
            url = safe_external_url(getattr(event, "url", None))
            st.html(f"<div class='korea-explanation-panel'><strong>{html.escape(title)}</strong><div class='korea-explain-muted'>일자 {html.escape(str(getattr(event, 'date', '-') or '-'))} · 종목 {html.escape(code)} · 중요도 {safe_float(getattr(event, 'importance', None)) or 0:.0f}</div><div class='korea-explain-muted' style='margin-top:8px;'>분류 {html.escape(str(getattr(event, 'category', '-') or '-'))} · 감성 {html.escape(_korea_display_label(sentiment))}</div></div>")
            if url:
                st.link_button("원문 보기", url, use_container_width=True)
    st.html(f'<div class="korea-card compact">{_korea_table_html(rows)}</div>')
    with st.expander("공시 이벤트 연결", expanded=False):
        for event_id, code, title, date_text in buttons:
            if st.button(f"{date_text} · {code} · {title[:32]}", key=_korea_widget_key("disclosure", event_id), use_container_width=True):
                update_korea_context(selectedStockCode=code, selectedDisclosureId=event_id, selectedMetric="disclosureScore", selectedModule="disclosureRadar", sourceModule="disclosureRadar")


def render_korea_value_up_radar(candidates: list[Any]) -> None:
    render_module_anchor("valueUpRadar")
    _korea_module_title("밸류업 레이더", "저평가, 주주환원, 재무 안정성을 함께 보는 정책 수혜 후보입니다.")
    st.html("<div class='korea-safety-callout' style='margin-bottom:10px;'>저평가 신호는 수익성 개선과 주주환원 확인 시 신뢰도가 높아집니다.</div>")
    rows = []
    for score in candidates[:8]:
        factors = _korea_factor_dict(score)
        rows.append({"종목": _korea_stock_cell(getattr(score, "name", ""), getattr(score, "code", "")), "밸류업": _korea_factor_cell(factors.get("밸류업")), "밸류": _korea_factor_cell(factors.get("밸류")), "퀄리티": _korea_factor_cell(factors.get("퀄리티")), "검토비중": korea_format_percent(getattr(score, "suggested_weight", None)), "근거": _korea_evidence(" / ".join(getattr(score, "positive_reasons", [])[:2]))})
    st.html(f'<div class="korea-card compact">{_korea_table_html(rows)}</div>')


def render_korea_backtest_accuracy_panel(backtest: Any) -> None:
    render_module_anchor("backtestAccuracy")
    _korea_module_title("예측 정확도·백테스트", "룰 기반 추정 성과입니다. 미래 수익을 보장하지 않으며 비용·슬리피지·세금 가정을 함께 봅니다.")
    metric_specs = [("CAGR", _korea_percent_text(getattr(backtest, "cagr", None)), "cagr"), ("초과수익", _korea_percent_text(getattr(backtest, "excess_return", None), signed=True), "excessReturn"), ("MDD", _korea_percent_text(getattr(backtest, "max_drawdown", None)), "mdd"), ("Sharpe", _safe_sharpe_text(getattr(backtest, "sharpe_ratio", None)), "sharpe"), ("P@10", _korea_percent_text(getattr(backtest, "precision_at_top10", None)), "precisionAt10"), ("Rank IC", _safe_sharpe_text(getattr(backtest, "factor_rank_ic", None)), "rankIC")]
    with st.expander("백테스트 지표 설명", expanded=False):
        metric_cols = st.columns(3)
        for idx, (label, value, metric_key) in enumerate(metric_specs):
            with metric_cols[idx % 3]:
                render_explainable_metric_button(label, value, metric_key, "backtestAccuracy", key_scope="backtest")
    metric_html = "".join(_korea_metric_html(label, value, "warn" if label == "MDD" else "good" if label in {"CAGR", "초과수익"} else "") for label, value, _ in metric_specs)
    notes = "".join(f"<span class='korea-badge muted' style='margin:4px 5px 0 0;'>{html.escape(str(note))}</span>" for note in getattr(backtest, "notes", [])[:3])
    subtitle = f"{getattr(backtest, 'strategy_name', '')} · {getattr(backtest, 'start_date', '')}~{getattr(backtest, 'end_date', '')}"
    meta = (
        f"검증 기간 {getattr(backtest, 'start_date', '-') or '-'}~{getattr(backtest, 'end_date', '-') or '-'} · "
        f"유니버스 {getattr(backtest, 'universe', '한국 관심종목') or '한국 관심종목'} · "
        f"거래비용 가정 포함"
    )
    st.html(f'<div class="korea-card compact"><div class="korea-card-title">{html.escape(subtitle)}</div><div class="korea-card-subtitle">{html.escape(meta)}</div><div class="korea-metric-grid">{metric_html}</div><div class="korea-safety-callout">{notes}<br/>과거 신호는 미래 성과를 보장하지 않습니다.</div></div>')


def render_korea_portfolio_action_queue(scores: list[Any]) -> None:
    render_module_anchor("portfolioReviewQueue")
    _korea_module_title("포트폴리오 검토 큐", "관심종목을 검토, 관찰, 리스크 관리 후보로 나눈 다음 확인 순서를 보여줍니다.")
    rows = []
    for score in scores[:10]:
        grade = getattr(score, "recommendation_grade", "NEUTRAL")
        rows.append({"검토": _korea_badge(_korea_action_label(str(grade)), _korea_grade_badge_class(str(grade))), "종목": _korea_stock_cell(getattr(score, "name", ""), getattr(score, "code", "")), "등급": _korea_badge(korea_format_grade(grade), _korea_grade_badge_class(str(grade))), "점수": korea_format_score(getattr(score, "total_score", None)), "신뢰도": korea_format_confidence(getattr(score, "confidence", None)), "최대비중": korea_format_percent(getattr(score, "max_suggested_weight", None)), "리스크": _korea_badge(", ".join(getattr(score, "risk_flags", [])[:2]) or "중요 플래그 없음", "good")})
    st.html(f'<div class="korea-card compact">{_korea_table_html(rows)}<div class="korea-safety-callout">Mock mode: 공식 실시간 주문 기능은 제공하지 않습니다. 실제 매매 전 원천 데이터와 공시를 반드시 재확인하세요.</div></div>')


def render_korea_advanced_module_summary(data: dict[str, Any], scores: list[Any]) -> None:
    render_module_anchor("advancedModuleSummary")
    modules = [("investmentAlgorithm", bool(scores), "점수·등급·신뢰도·기대수익·하방위험"), ("factorHeatmap", bool(scores), "팩터별 강약과 관련 근거"), ("supplyDemandRadar", bool(scores), "외국인·기관·연기금 수급"), ("disclosureRadar", bool(data.get("disclosures")), "공시·이벤트 리스크"), ("valueUpRadar", bool(data.get("valueUpCandidates")), "저PBR·주주환원·밸류업"), ("backtestAccuracy", bool(data.get("backtest")), "성과 검증과 신뢰도 근거"), ("portfolioReviewQueue", bool(scores), "비중·관찰·리스크 점검"), ("decisionFlow", bool(data.get("investmentOS")), "검토 단계를 한 흐름으로 연결"), ("signalConflictMatrix", bool(data.get("investmentOS")), "긍정/부정 신호 충돌"), ("positionSizingRiskBudget", bool(data.get("investmentOS")), "손절 기준 기반 리스크 예산")]
    _korea_module_title("고도화 모듈 요약", "각 모듈이 어떤 근거를 제공하는지 보고 바로 이동합니다.", f"{len(modules)}개 모듈")
    cols = st.columns(3)
    for idx, (module_key, active, description) in enumerate(modules):
        with cols[idx % 3]:
            if st.button(f"{formatModuleLabel(module_key)} · {'사용 가능' if active else '데이터 부족'}", key=_korea_widget_key("module_summary", module_key), use_container_width=True, help=description):
                update_korea_context(selectedModule=module_key, selectedMetric=MODULE_DEFAULT_METRIC.get(module_key), sourceModule="advancedModuleSummary")
    module_status = {module_key: (active, description) for module_key, active, description in modules}
    registry_cards = []
    for item in KOREA_MODULE_VISUAL_REGISTRY:
        module_key = item["key"]
        if module_key not in MODULE_IDS:
            continue
        active, description = module_status.get(module_key, (bool(data.get("investmentOS")) if item["group"] == "Decision OS" else False, item["group"]))
        registry_cards.append(_korea_module_health_html(module_key, active, description, str(data.get("generatedAt", "-") or "-")))
    st.html(f'<div class="korea-card compact"><div class="korea-module-health-grid">{"".join(registry_cards)}</div></div>')


def _korea_os_card_html(title: str, subtitle: str, body: str, module_key: str, span: int = 6, badge: str = "") -> str:
    anchor = MODULE_IDS.get(module_key, module_key)
    badge_html = _korea_badge(badge, "auto") if badge else ""
    return f"""
    <article id="{html.escape(anchor)}" class="korea-os-card korea-os-span-{span}" aria-label="{html.escape(title)}">
        <div class="korea-os-card-head">
            <div>
                <div class="korea-os-card-title">{html.escape(title)}</div>
                <div class="korea-os-card-desc">{html.escape(subtitle)}</div>
            </div>
            {badge_html}
        </div>
        <div class="korea-os-card-body">{body}</div>
    </article>
    """


def _korea_os_metric_html(label: str, value: str, tone: str = "", detail: str = "") -> str:
    tone_class = {
        "good": "tone-good",
        "info": "tone-info",
        "warn": "tone-warn",
        "risk": "tone-risk",
    }.get(tone, "")
    detail_html = f"<div class='korea-os-muted'>{html.escape(detail)}</div>" if detail else ""
    return f"""
    <div class="korea-os-metric">
        <small>{html.escape(label)}</small>
        <strong class="{tone_class}">{html.escape(str(value))}</strong>
        {detail_html}
    </div>
    """


def _korea_os_direction_badge(direction: Any) -> _HtmlCell:
    raw = str(direction or "neutral")
    tone = "good" if raw == "positive" else "risk" if raw == "negative" else "warn" if raw == "mixed" else "info"
    return _korea_badge(raw, tone)


def korea_decision_flow_html(os_data: dict[str, Any]) -> str:
    rows = []
    for idx, item in enumerate(os_data.get("decisionFlow", []), 1):
        evidence = " / ".join(getattr(item, "primary_evidence", [])[:2]) or getattr(item, "blocking_reason", "") or "-"
        status = str(getattr(item, "status", "-") or "-")
        action = str(getattr(item, "candidate_action", "관찰") or "관찰")
        rows.append(
            f"""
            <div class="korea-os-step-row">
                <div class="korea-os-step-num">{idx}</div>
                <div>
                    <div class="korea-os-label">{html.escape(str(getattr(item, "title", "-") or "-"))}</div>
                    <div class="korea-os-muted">{html.escape(str(getattr(item, "id", "") or ""))}</div>
                </div>
                <div>{_korea_badge(status, _korea_tone_for_value(status, "warn"))}</div>
                <div><span class="korea-os-score">{html.escape(korea_format_score(getattr(item, "score", None)))}</span></div>
                <div>{_korea_badge(action, _korea_tone_for_value(action, "info"))}</div>
                <div class="korea-os-reason" title="{html.escape(evidence)}">{html.escape(evidence)}</div>
            </div>
            """
        )
    body = "".join(rows) if rows else _korea_empty_html("의사결정 흐름 데이터가 없습니다.")
    return _korea_os_card_html("의사결정 흐름", "시장→후보→리스크→검증→결론 순서로 보류 사유를 확인합니다.", body, "decisionFlow", 7, "검토 흐름")


def korea_signal_conflict_matrix_html(os_data: dict[str, Any]) -> str:
    rows = []
    for item in os_data.get("signalConflicts", []):
        conflict = getattr(item, "conflict_with", None) or "-"
        if isinstance(conflict, (list, tuple)):
            conflict_text = " / ".join(str(v) for v in conflict[:2])
            if len(conflict) > 2:
                conflict_text += f" +{len(conflict) - 2}"
        else:
            conflict_text = str(conflict)
        strength = safe_float(getattr(item, "strength", None))
        bar_width = 0 if strength is None else max(2, min(100, strength))
        strength_cell = _HtmlCell(
            f"<span class='korea-os-score'>{html.escape(korea_format_score(strength))}</span>"
            f"<div class='portfolio-progress' style='height:6px; margin:6px 0 0;'><div class='portfolio-progress-fill' style='width:{bar_width:.0f}%;'></div></div>"
        )
        rows.append({
            "신호": getattr(item, "signal", "-"),
            "방향": _korea_os_direction_badge(getattr(item, "direction", "neutral")),
            "강도": strength_cell,
            "충돌": _korea_badge(conflict_text, "muted") if conflict_text != "-" else _HtmlCell("<span class='korea-os-muted'>-</span>"),
            "근거": _korea_evidence(getattr(item, "evidence", "")),
        })
    body = f"<div class='korea-os-mini-table'>{_korea_table_html(rows)}</div>"
    return _korea_os_card_html("신호 충돌 매트릭스", "좋은 신호와 나쁜 신호가 동시에 있는지 분리해서 봅니다.", body, "signalConflictMatrix", 5, "긍정/중립/부정")


def korea_position_sizing_budget_html(os_data: dict[str, Any]) -> str:
    item = os_data.get("positionSizing")
    if item is None:
        body = _korea_empty_html("포지션 리스크 예산 데이터가 없습니다.")
        return _korea_os_card_html("포지션 리스크 예산", "손절 기준과 총자산 리스크 한도로 최대 검토 수량을 계산합니다.", body, "positionSizingRiskBudget", 6)
    status = str(getattr(item, "status", "-") or "-")
    body = f"""
        <div style="margin-bottom:10px;">{_korea_badge(status, _korea_tone_for_value(status, "good"))}</div>
        <div class="korea-os-metrics">
            {_korea_os_metric_html("진입 기준", korea_format_krw(getattr(item, "entry_price", None)), "info")}
            {_korea_os_metric_html("손절 기준", korea_format_krw(getattr(item, "stop_price", None)), "risk")}
            {_korea_os_metric_html("허용손실", _korea_percent_text(getattr(item, "max_loss_pct", None)), "warn")}
            {_korea_os_metric_html("최대금액", korea_format_krw(getattr(item, "max_position_value", None)), "info")}
            {_korea_os_metric_html("최대수량", str(getattr(item, "max_quantity", "-") if getattr(item, "max_quantity", None) is not None else "-"), "good")}
            {_korea_os_metric_html("신뢰도", korea_format_confidence(getattr(item, "confidence", None)), "warn")}
        </div>
        <div class="korea-os-callout">{html.escape(str(getattr(item, "action_label", "비중 한도 내 검토") or "비중 한도 내 검토"))}</div>
    """
    return _korea_os_card_html("포지션 리스크 예산", "손절 기준과 총자산 리스크 한도로 최대 검토 수량을 계산합니다.", body, "positionSizingRiskBudget", 6, status)


def korea_thesis_tracker_html(os_data: dict[str, Any]) -> str:
    blocks = []
    for item in os_data.get("theses", []):
        name = f"{getattr(item, 'name', '-') or '-'} {getattr(item, 'code', '') or ''}".strip()
        status = str(getattr(item, "status", "-") or "-")
        invalidation = " / ".join(getattr(item, "invalidation_rules", [])[:2]) or "-"
        blocks.append(
            f"""
            <div class="korea-os-thesis-grid">
                <div style="display:flex; justify-content:space-between; gap:10px; align-items:center; margin-bottom:10px;">
                    <div class="korea-os-label">{html.escape(name)}</div>
                    {_korea_badge(status, _korea_tone_for_value(status, "warn"))}
                </div>
                <div class="korea-os-thesis"><b>핵심 가설</b><span>{html.escape(str(getattr(item, "core_view", "") or "-"))}</span></div>
                <div class="korea-os-thesis"><b>무효화 조건</b><span>{html.escape(invalidation)}</span></div>
                <div class="korea-os-thesis"><b>다음 점검</b><span>{html.escape(str(getattr(item, "next_review", "-") or "-"))}</span></div>
            </div>
            """
        )
    body = "".join(blocks) if blocks else _korea_empty_html("투자 가설 데이터가 없습니다.")
    return _korea_os_card_html("투자 가설 트래커", "가설, 근거, 반증 조건을 한 카드에서 추적합니다.", body, "investmentThesisTracker", 6, "검증 중")


def korea_prediction_calibration_html(os_data: dict[str, Any]) -> str:
    item = os_data.get("calibration")
    if item is None:
        body = _korea_empty_html("예측 검증 데이터가 없습니다.")
        return _korea_os_card_html("예측 검증·캘리브레이션", "모델 점수가 실제 성과로 이어졌는지 확인하고 confidence를 보수적으로 조정합니다.", body, "predictionCalibration", 4)
    status = str(getattr(item, "status", "-") or "-")
    adjustment = str(getattr(item, "confidence_adjustment", "-") or "-")
    body = f"""
        <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:10px;">{_korea_badge(status, _korea_tone_for_value(status, "good"))}{_korea_badge(adjustment, "info")}</div>
        <div class="korea-os-metrics">
            {_korea_os_metric_html("P@10", _korea_percent_text(getattr(item, "precision_at_10", None)), "good")}
            {_korea_os_metric_html("Rank IC", _safe_sharpe_text(getattr(item, "rank_ic", None)), "good")}
            {_korea_os_metric_html("Hit Ratio", _korea_percent_text(getattr(item, "hit_ratio", None)), "info")}
            {_korea_os_metric_html("Win Rate", _korea_percent_text(getattr(item, "win_rate", None)), "good")}
        </div>
    """
    return _korea_os_card_html("예측 검증·캘리브레이션", "모델 점수가 실제 성과로 이어졌는지 확인하고 confidence를 보수적으로 조정합니다.", body, "predictionCalibration", 4, status)


def korea_similar_case_library_html(os_data: dict[str, Any]) -> str:
    rows = []
    for item in os_data.get("similarCases", []):
        sample = int(safe_float(getattr(item, "sample_size", 0)) or 0)
        rows.append({
            "유형": getattr(item, "label", "-"),
            "표본": _korea_badge("표본 작음" if sample <= 3 else f"표본 {sample}", "warn" if sample <= 3 else "info"),
            "승률": _HtmlCell(f"<span class='tone-good'>{html.escape(_korea_percent_text(getattr(item, 'win_rate', None)))}</span>"),
            "평균성과": _HtmlCell(f"<span class='tone-good'>{html.escape(_korea_percent_text(getattr(item, 'average_forward_return', None), signed=True))}</span>"),
            "최대낙폭": _HtmlCell(f"<span class='tone-risk'>{html.escape(_korea_percent_text(getattr(item, 'max_drawdown', None)))}</span>"),
            "근거": _korea_evidence(" / ".join(getattr(item, "evidence", [])[:2])),
        })
    body = f"<div class='korea-os-mini-table'>{_korea_table_html(rows)}</div>"
    return _korea_os_card_html("유사 사례 라이브러리", "비슷한 섹터·점수·리스크 후보의 성과를 참고 자료로 봅니다.", body, "similarCaseLibrary", 4, "참고 자료")


def korea_risk_alert_rules_html(os_data: dict[str, Any]) -> str:
    rows = []
    for item in os_data.get("riskAlerts", []):
        status = str(getattr(item, "status", "-") or "-")
        current = str(getattr(item, "current_value", "-") or "-")
        rows.append(
            f"""
            <div class="korea-os-alert-row">
                <div><div class="korea-os-label">{html.escape(str(getattr(item, "title", "-") or "-"))}</div><div class="korea-os-muted">{html.escape(str(getattr(item, "id", "") or ""))}</div></div>
                <div>{_korea_badge(status, _korea_tone_for_value(status, "muted"))}</div>
                <div>{_korea_badge(current, _korea_tone_for_value(current, "muted"))}</div>
                <div class="korea-os-muted"><code>{html.escape(str(getattr(item, "trigger", "-") or "-"))}</code></div>
                <div class="korea-os-reason">{html.escape(str(getattr(item, "candidate_action", "관찰") or "관찰"))}</div>
            </div>
            """
        )
    body = "".join(rows) if rows else _korea_empty_html("리스크 알림 데이터가 없습니다.")
    return _korea_os_card_html("리스크 알림 규칙", "시장·가격·공시·수급 위험이 켜졌는지 확인합니다.", body, "riskAlertRules", 4, "알림")


def korea_scenario_stress_tests_html(os_data: dict[str, Any]) -> str:
    rows = []
    for item in os_data.get("scenarios", []):
        impact = safe_float(getattr(item, "impact_pct", None))
        evidence = " / ".join(getattr(item, "evidence", [])[:2]) or "-"
        status = str(getattr(item, "status", "-") or "-")
        rows.append(
            f"""
            <div class="korea-os-scenario-row">
                <div class="korea-os-label">{html.escape(str(getattr(item, "label", "-") or "-"))}</div>
                <div>{_korea_badge(status, _korea_tone_for_value(status, "risk"))}</div>
                <div><span class="korea-os-score tone-risk">{html.escape(_korea_percent_text(impact, signed=True))}</span></div>
                <div>{_korea_badge(getattr(item, "candidate_action", "관찰"), "warn")}</div>
                <div class="korea-os-reason" title="{html.escape(evidence)}">{html.escape(evidence)}</div>
            </div>
            """
        )
    body = "".join(rows) if rows else _korea_empty_html("시나리오 데이터가 없습니다.")
    return _korea_os_card_html("시나리오 스트레스 테스트", "환율·금리·지수·유동성 충격에서 기대값이 어떻게 흔들리는지 봅니다.", body, "scenarioStressTest", 8, "방어 확인")


def korea_catalyst_calendar_html(os_data: dict[str, Any]) -> str:
    rows = []
    for item in os_data.get("catalysts", []):
        severity = getattr(item, "severity", "-")
        rows.append({
            "일자": getattr(item, "date", "-"),
            "종목": getattr(item, "code", "-") or "-",
            "이벤트": _korea_evidence(getattr(item, "title", "")),
            "심각도": _korea_badge(severity, _korea_tone_for_value(severity, "muted")),
            "영향": _korea_evidence(getattr(item, "expected_effect", "-")),
        })
    body = f"<div class='korea-os-mini-table'>{_korea_table_html(rows)}</div>"
    return _korea_os_card_html("촉매·이벤트 캘린더", "공시, 실적, 정책 이벤트를 검토 흐름에 연결합니다.", body, "catalystEventCalendar", 4, "이벤트")


def korea_post_review_notebook_html(os_data: dict[str, Any]) -> str:
    rows = []
    for item in os_data.get("postReview", []):
        r_multiple = safe_float(getattr(item, "realized_r_multiple", None))
        rows.append({
            "종목": getattr(item, "code", "-") or "-",
            "상태": _korea_badge(getattr(item, "status", "-"), "warn"),
            "R배수": _HtmlCell(f"<span class='{'tone-risk' if (r_multiple or 0) < 0 else 'tone-good'}'>{html.escape(_safe_sharpe_text(r_multiple))}</span>"),
            "20D 성과": _korea_percent_text(getattr(item, "forward_return_20d", None), signed=True),
            "드리프트": _korea_evidence(getattr(item, "drift_status", "-")),
            "다음": _korea_evidence(getattr(item, "next_action", "-")),
        })
    body = f"<div class='korea-os-mini-table'>{_korea_table_html(rows)}</div>"
    return _korea_os_card_html("사후 리뷰 노트", "검토 후 성과를 누적해 약한 신호 유형을 줄입니다.", body, "postReviewNotebook", 12, "기록 대기")


def render_korea_decision_flow(os_data: dict[str, Any]) -> None:
    st.html(korea_decision_flow_html(os_data))


def render_korea_signal_conflict_matrix(os_data: dict[str, Any]) -> None:
    st.html(korea_signal_conflict_matrix_html(os_data))


def render_korea_position_sizing_budget(os_data: dict[str, Any]) -> None:
    st.html(korea_position_sizing_budget_html(os_data))


def render_korea_scenario_stress_tests(os_data: dict[str, Any]) -> None:
    st.html(korea_scenario_stress_tests_html(os_data))


def render_korea_thesis_tracker(os_data: dict[str, Any]) -> None:
    st.html(korea_thesis_tracker_html(os_data))


def render_korea_catalyst_calendar(os_data: dict[str, Any]) -> None:
    st.html(korea_catalyst_calendar_html(os_data))


def render_korea_prediction_calibration(os_data: dict[str, Any]) -> None:
    st.html(korea_prediction_calibration_html(os_data))


def render_korea_risk_alert_rules(os_data: dict[str, Any]) -> None:
    st.html(korea_risk_alert_rules_html(os_data))


def render_korea_similar_case_library(os_data: dict[str, Any]) -> None:
    st.html(korea_similar_case_library_html(os_data))


def render_korea_post_review_notebook(os_data: dict[str, Any]) -> None:
    st.html(korea_post_review_notebook_html(os_data))


def render_korea_investment_os_section(os_data: dict[str, Any]) -> None:
    nav_items = [
        ("decisionFlow", "흐름"),
        ("signalConflictMatrix", "충돌"),
        ("positionSizingRiskBudget", "리스크"),
        ("investmentThesisTracker", "가설"),
        ("predictionCalibration", "검증"),
        ("scenarioStressTest", "시나리오"),
        ("catalystEventCalendar", "이벤트"),
        ("riskAlertRules", "알림"),
        ("postReviewNotebook", "리뷰"),
        ("investmentAlgorithm", "알고리즘"),
        ("factorHeatmap", "히트맵"),
        ("supplyDemandRadar", "수급"),
        ("disclosureRadar", "공시"),
        ("valueUpRadar", "밸류업"),
        ("backtestAccuracy", "백테스트"),
        ("portfolioReviewQueue", "큐"),
    ]
    nav_html = "".join(
        f'<a href="#{html.escape(MODULE_IDS.get(module, module))}">{html.escape(label)}</a>'
        for module, label in nav_items
    )
    if not os_data:
        st.html(
            f"""
            <section class="korea-os-shell">
                <div class="korea-os-hero"><div><strong>Korea Investment OS v2</strong><span>검토 흐름, 충돌, 리스크 예산, 시나리오, 가설, 촉매, 검증, 리뷰를 연결한 의사결정 보드입니다.</span></div>{_korea_badge("주문 기능 없음", "muted")}</div>
                {_korea_empty_html("Investment OS 데이터가 없습니다.", "한국 알파 데이터가 준비되면 자동으로 표시됩니다.")}
            </section>
            """
        )
        return
    body = "\n".join(
        [
            korea_decision_flow_html(os_data),
            korea_signal_conflict_matrix_html(os_data),
            korea_position_sizing_budget_html(os_data),
            korea_thesis_tracker_html(os_data),
            korea_prediction_calibration_html(os_data),
            korea_similar_case_library_html(os_data),
            korea_risk_alert_rules_html(os_data),
            korea_scenario_stress_tests_html(os_data),
            korea_catalyst_calendar_html(os_data),
            korea_post_review_notebook_html(os_data),
        ]
    )
    st.html(
        f"""
        <section class="korea-os-shell" aria-label="Korea Investment OS v2">
            <div class="korea-os-hero">
                <div>
                    <strong>Korea Investment OS v2</strong>
                    <span>검토 흐름, 충돌, 리스크 예산, 시나리오, 가설, 촉매, 검증, 리뷰를 연결한 의사결정 보드입니다.</span>
                </div>
                {_korea_badge("주문 기능 없음", "muted")}
            </div>
            <nav class="korea-os-nav" aria-label="Korea Investment OS v2 module navigation">{nav_html}</nav>
            <div class="korea-os-grid">{body}</div>
        </section>
        """
    )


def render_korea_alpha_section(snapshot: dict[str, Snapshot], refresh_token: int) -> None:
    init_korea_interaction_state()
    st.markdown('<div class="portfolio-shell korea-shell korea-os-theme">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="portfolio-head"><div><div class="portfolio-eyebrow">Korea Alpha Engine</div><div class="portfolio-title">한국 주식 초과수익 후보와 리스크를 한 번에 보는 알고리즘 보드</div><div class="portfolio-subtitle">주문 실행이 아닌 검토 후보 보드입니다. 모든 판단은 점수, 신뢰도, 기대수익 범위, 하방위험, 근거, 데이터 기준일과 함께 표시합니다.</div></div></div>
        """,
        unsafe_allow_html=True,
    )
    render_korea_context_bar("korea_alpha")
    render_explanation_panel(key_scope="korea_alpha")
    with st.expander("한국 알파 필터", expanded=False):
        market_filter = st.multiselect("시장", ["KOSPI", "KOSDAQ", "ETF"], default=["KOSPI", "KOSDAQ"], key=f"korea_market_filter_{refresh_token}")
        min_score = st.slider("최소 점수", 0, 100, 0, 5, key=f"korea_min_score_{refresh_token}")
        grade_filter = st.multiselect("등급", ["STRONG_REVIEW", "BUY_REVIEW", "WATCHLIST", "NEUTRAL", "CAUTION", "EXCLUDE"], default=["STRONG_REVIEW", "BUY_REVIEW", "WATCHLIST", "NEUTRAL", "CAUTION", "EXCLUDE"], format_func=korea_format_grade, key=f"korea_grade_filter_{refresh_token}")
    grade_summary = "전체" if len(grade_filter) == 6 else ", ".join(korea_format_grade(item) for item in grade_filter)
    market_summary = ", ".join(market_filter) if market_filter else "선택 없음"
    st.html(
        f"""
        <div class="korea-filter-summary" aria-label="한국 알파 필터 선택 요약">
            <strong>한국 알파 필터</strong>
            <span class="korea-filter-chip">시장: {html.escape(market_summary)}</span>
            <span class="korea-filter-chip">최소 점수: {int(min_score)} / 100</span>
            <span class="korea-filter-chip">등급: {html.escape(grade_summary)}</span>
        </div>
        """
    )
    live_market_status = build_live_korea_market_status(snapshot)
    data = getKoreaDashboardData({"markets": market_filter, "limit": 12, "market_status": live_market_status})
    all_scores = [score for score in data.get("scores", []) if getattr(score, "total_score", 0) >= min_score and getattr(score, "recommendation_grade", "") in grade_filter]
    all_scores = sorted(all_scores, key=lambda row: getattr(row, "total_score", 0), reverse=True)
    data["topCandidates"] = all_scores[:12]
    top_cols = st.columns([1, 1.25, 1])
    with top_cols[0]:
        render_korea_market_regime_card(data["marketStatus"])
    with top_cols[1]:
        render_korea_top_candidates_card(data["topCandidates"])
    with top_cols[2]:
        render_korea_risk_control_panel(data)
    render_korea_advanced_module_summary(data, all_scores)
    render_korea_investment_os_section(data.get("investmentOS", {}))
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
    st.markdown("</div>", unsafe_allow_html=True)


def parse_portfolio_text(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    if not text.strip():
        return [], []
    errors: list[str] = []
    try:
        df = pd.read_csv(io.StringIO(text.strip()))
    except Exception as exc:
        return [], [f"CSV 읽기 오류: {exc}"]
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
            errors.append(f"{idx + 1}행 code/qty/avg_price 확인 필요")
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
    st.markdown('<div class="section-title">포트폴리오 관제센터</div>', unsafe_allow_html=True)
    total_assets = safe_float(st.session_state.get("portfolio_total_assets")) or 100_000_000.0
    cash = safe_float(st.session_state.get("portfolio_cash")) or 0.0
    holdings_text = str(st.session_state.get("portfolio_holdings_text", ""))
    holdings, errors = parse_portfolio_text(holdings_text)
    regime = build_market_regime_output(snapshot)

    for err in errors:
        st.warning(err)

    cash_pct = cash / total_assets * 100 if total_assets > 0 else 0.0
    cols = st.columns(4)
    cols[0].metric("총자산", f"{total_assets:,.0f}원")
    cols[1].metric("현금", f"{cash:,.0f}원")
    cols[2].metric("현금 비중", f"{cash_pct:.1f}%")
    cols[3].metric("시장 국면", f"{regime_label_ko(regime.regime)} / {regime.score}")
    st.caption(f"데이터 기준: {last_refresh}")

    if not holdings:
        st.info("보유종목 CSV를 입력하면 포지션 리스크와 청산 우선순위를 계산합니다. 형식은 `code,qty,avg_price,sector`입니다.")
        st.code("code,qty,avg_price,sector\n005930,10,75000,반도체\n034020,5,25000,에너지", language="text")
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
        st.warning(f"현재 현금 비중 {cash_pct:.1f}%는 권장 하단 {regime.recommended_cash_range[0]}%보다 낮습니다.")
    if max_sector > RISK_DEFAULTS["max_sector_pct"] * 100:
        st.warning(f"섹터 집중도 {max_sector:.1f}%가 기본 한도 {RISK_DEFAULTS['max_sector_pct'] * 100:.0f}%를 넘었습니다.")

    st.html(
        f"""
        <table class="command-table">
            <thead>
                <tr><th>종목</th><th>수량</th><th>현재가</th><th>수익률</th><th>손절</th><th>손절 시 총자산 손실</th><th>섹터</th></tr>
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
                <tr><th>종목</th><th>상태</th><th>Hard stop</th><th>1차 목표</th><th>Runner</th><th>신뢰도</th></tr>
            </thead>
            <tbody>{''.join(sorted_exit_rows)}</tbody>
        </table>
        """
    )
    st.caption(f"현금 포함 추정 포트폴리오 가치: {portfolio_value:,.0f}원")


def render_settings_section() -> None:
    st.markdown('<div class="section-title">설정</div>', unsafe_allow_html=True)
    st.write("핵심 리스크 기본값과 API 연결 상태를 확인합니다. 실제 주문 기능은 제공하지 않습니다.")
    kis_status = "활성" if kis_enabled() else "비활성 - KIS_APP_KEY/KIS_APP_SECRET 필요"
    st.info(f"KIS 공식 현재가 사용 상태: {kis_status}")
    setting_labels = {
        "risk_per_trade_pct": "1회 거래 최대 손실률",
        "max_position_pct": "단일 종목 최대 비중",
        "max_sector_pct": "섹터 최대 비중",
        "min_raw_rr": "최소 기본 손익비",
        "min_quality_adjusted_rr": "최소 품질조정 손익비",
        "extreme_risk_off_min_rr": "극단 위험회피 최소 손익비",
        "trading_cost_pct": "거래 비용·세금",
        "slippage_pct": "슬리피지",
    }
    settings_rows = "".join(
        f"<tr><td>{html.escape(setting_labels.get(str(key), str(key)))}</td><td>{html.escape(str(value))}</td></tr>"
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
    st.session_state.pending_sidebar_message = f"{code} 관심종목에 추가했습니다."


def _candidate_display_rows(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(candidates, 1):
        rows.append(
            {
                "순위": idx,
                "종목": f"{item.get('name')} ({item.get('code')})",
                "시장": item.get("market"),
                "유형": item.get("category"),
                "발굴점수": item.get("discovery_score"),
                "주도력": item.get("leadership_score"),
                "기대값": "데이터 없음" if item.get("expected_edge") is None else f"{item.get('expected_edge'):+.2f}%",
                "손익비": "데이터 없음" if item.get("risk_reward_ratio") is None else f"{item.get('risk_reward_ratio'):.2f}x",
                "트리거": "데이터 없음" if item.get("trigger_price") is None else f"{item.get('trigger_price'):,.0f}",
                "손절": "데이터 없음" if item.get("stop_price") is None else f"{item.get('stop_price'):,.0f}",
                "최대비중": f"{float(item.get('max_position_pct') or 0) * 100:.1f}%",
                "신뢰도": item.get("confidence"),
            }
        )
    return rows


def render_alpha_discovery_summary(refresh_token: int) -> None:
    requested = bool(st.session_state.get("discovery_scan_requested", False))
    if not requested:
        st.info("알파 후보 탐색을 실행하면 대시보드 요약에 상위 후보가 표시됩니다.")
        return
    max_symbols = int(st.session_state.get("discovery_max_symbols", 220))
    candidates, warnings, total, scanned = run_alpha_discovery_scan(refresh_token, max_symbols)
    if not candidates:
        st.warning("상위 후보를 찾지 못했습니다. 데이터 품질 또는 시장 필터를 확인하세요.")
        return
    top = candidates[0]
    st.html(
        f"""
        <div class="insight-panel">
            <div class="insight-head">
                <div>
                    <div class="insight-kicker">알파 후보 탐색</div>
                    <div class="insight-title">{html.escape(str(top.get('name')))} ({html.escape(str(top.get('code')))}): {html.escape(str(top.get('category')))}</div>
                </div>
                <div class="insight-badge" style="background:#0f766e;">{float(top.get('discovery_score') or 0):.0f}점</div>
            </div>
            <div class="thesis">전체 {total:,}개 중 {scanned:,}개를 스캔했습니다. 발굴 후보는 검토용이며 가격, 손익비, 공시 위험을 함께 확인합니다.</div>
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
        warning_text = exec_plan.warnings[0] if exec_plan.warnings else "유동성과 주문 비용을 점검합니다."
        st.html(
            f"""
            <div class="korea-card compact">
                <div class="korea-card-title">실행 품질</div>
                <div class="korea-score">{exec_plan.execution_quality_score:.0f}/100</div>
                <div class="portfolio-card-sub">{html.escape(exec_plan.recommended_order_style)}<br/>{html.escape(warning_text)}</div>
            </div>
            """
        )
    with cols[2]:
        rule_text = exit_plan.invalidation_rules[0] if exit_plan.invalidation_rules else "손절과 시간 손절 규칙을 점검합니다."
        st.html(
            f"""
            <div class="korea-card compact">
                <div class="korea-card-title">청산 계획</div>
                <div class="korea-score" style="font-size:1.16rem;">{html.escape(exit_plan.status)}</div>
                <div class="portfolio-card-sub">신뢰도 {exit_plan.exit_confidence:.0f}<br/>{html.escape(rule_text)}</div>
            </div>
            """
        )
    with cols[3]:
        try:
            kill_state = get_kill_switch_state(SIGNAL_LEDGER_DB)
        except Exception as exc:
            kill_state = {"active": False, "reason": f"신호 원장 사용 불가: {exc}", "sample_size": 0, "hit_rate": None}
        state_text = "활성" if kill_state.get("active") else "정상"
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
    st.markdown('<div class="section-title">알파 후보 탐색</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="small-note">KOSPI/KOSDAQ 후보를 스캔해 상대강도, 신고가 근접, 거래대금, 눌림목, 생존주 조건을 검토합니다. 결과는 매수 지시가 아니라 검토 후보입니다.</div>',
        unsafe_allow_html=True,
    )
    max_symbols = st.slider(
        "스캔 종목 수",
        min_value=50,
        max_value=1000,
        value=int(st.session_state.get("discovery_max_symbols", 220)),
        step=50,
        help="스캔 수가 많을수록 시간이 오래 걸립니다.",
    )
    st.session_state.discovery_max_symbols = max_symbols
    col_run, col_clear = st.columns([1, 1])
    with col_run:
        if st.button("전체시장 스캔 실행", use_container_width=True):
            st.session_state.discovery_scan_requested = True
            run_alpha_discovery_scan.clear()
    with col_clear:
        if st.button("스캔 결과 새로고침", use_container_width=True):
            st.session_state.discovery_scan_requested = True

    if not st.session_state.get("discovery_scan_requested", False):
        st.info("버튼을 누르면 후보 스캔을 시작합니다. 초기 로딩을 막기 위해 수동 실행 방식으로 유지합니다.")
        return

    with st.spinner("전체시장 후보를 스캔하는 중입니다. 종목 수에 따라 시간이 걸릴 수 있습니다."):
        candidates, warnings, total, scanned = run_alpha_discovery_scan(refresh_token, max_symbols)
    st.caption(f"전체 {total:,}개 중 {scanned:,}개 스캔 · 후보 {len(candidates)}개")
    if warnings:
        st.warning(" / ".join(warnings[:5]))
    if not candidates:
        st.error("표시할 후보가 없습니다. 데이터 품질 또는 필터 조건을 확인하세요.")
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
            positives = " / ".join(item.get("positive_reasons") or ["긍정 근거 없음"])
            negatives = " / ".join(item.get("negative_reasons") or ["부정 근거 없음"])
            st.markdown(f"**{item.get('name')} ({item.get('code')})** · {item.get('category')} · {item.get('discovery_score'):.0f}점")
            st.caption(f"긍정: {positives}")
            st.caption(f"주의: {negatives}")


def render_signal_outcome_section(
    snapshot: dict[str, Snapshot],
    valid_rows: list[dict[str, Any]],
    code_to_name: dict[str, str],
    refresh_token: int,
) -> None:
    st.markdown('<div class="section-title">신호 성과 기록</div>', unsafe_allow_html=True)
    init_db(SIGNAL_LEDGER_DB)
    kill_state = get_kill_switch_state(SIGNAL_LEDGER_DB)
    metric_cols = st.columns(4)
    metric_cols[0].metric("킬스위치", "활성" if kill_state.get("active") else "정상")
    metric_cols[1].metric("검증 표본", str(kill_state.get("sample_size")))
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
        for record in list_recent_signals(SIGNAL_LEDGER_DB, limit=50):
            hist = load_symbol_history(record.code, refresh_token, periods=260)
            if hist.empty:
                continue
            outcome = compute_forward_outcome(record, hist)
            if outcome is not None:
                store_outcome(SIGNAL_LEDGER_DB, outcome)
                updated += 1
        st.success(f"{updated}개 신호의 사후 성과를 업데이트했습니다.")

    recent = list_recent_signals(SIGNAL_LEDGER_DB, limit=30)
    if not recent:
        st.info("저장된 신호가 없습니다.")
        return
    rows = [
        {
            "일시": record.generated_at[:19],
            "종목": f"{record.name} ({record.code})",
            "행동 후보": action_label_ko(record.action),
            "점수": record.score,
            "국면": regime_label_ko(record.market_regime),
            "기대값": "N/A" if record.expected_edge is None else f"{record.expected_edge:+.2f}%",
            "손익비": "N/A" if record.risk_reward_ratio is None else f"{record.risk_reward_ratio:.2f}x",
        }
        for record in recent
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)



def render_stocks_section(
    snapshot: dict[str, Snapshot],
    valid_rows: list[dict[str, Any]],
    code_to_name: dict[str, str],
    refresh_token: int,
    last_refresh: str,
) -> None:
    st.markdown('<div class="section-title">종목</div>', unsafe_allow_html=True)
    market_score, _ = market_regime(snapshot)
    regime_output = build_market_regime_output(snapshot)
    kospi_snap = snapshot.get("KOSPI")
    kospi_close = kospi_snap.raw["Close"] if kospi_snap and kospi_snap.raw is not None and "Close" in kospi_snap.raw.columns else None
    leadership_rows = build_watchlist_insights(valid_rows, refresh_token, kospi_close, market_score, regime_output)
    render_watchlist_ranking(leadership_rows)

    if not valid_rows:
        st.info("관심종목을 입력하면 종목 상세 분석이 표시됩니다.")
        return
    options = [row["code"] for row in valid_rows]
    active_code = st.session_state.manual_active_code if st.session_state.manual_active_code in options else options[0]
    selected_code = st.selectbox(
        "상세 종목 선택",
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
                            <div class="insight-kicker">종목 판단</div>
                            <div class="insight-title">{html.escape(active_name)}</div>
                        </div>
                        <div class="insight-badge" style="background:{'#dc2626' if action.score >= 65 else '#2563eb' if action.score < 45 else '#64748b'};">{html.escape(action_label_ko(action.action))} / {action.score}점</div>
                    </div>
                    {reason_html}
                    <div class="thesis">진입 검토 전 손절 기준 {format_price(plan.get('stop'))}, 공시 위험, 실행 비용을 함께 확인합니다.</div>
                </div>
                """
            )
    trade_cols = st.columns([1, 1])
    with trade_cols[0]:
        render_execution_card(exec_plan, action.expected_edge if action else None)
    with trade_cols[1]:
        render_exit_plan_card(exit_plan)
    if active_hist.empty:
        st.warning("선택 종목의 가격 데이터를 불러오지 못했습니다.")
    else:
        st.pyplot(plot_candlestick_with_volume(active_hist, f"{active_name} ({selected_code})"), clear_figure=True)
    st.caption(f"데이터 기준: {last_refresh}")


def render_dashboard_section(
    snapshot: dict[str, Snapshot],
    valid_rows: list[dict[str, Any]],
    code_to_name: dict[str, str],
    ref_date: str,
    last_refresh: str,
    refresh_token: int,
) -> None:
    init_korea_interaction_state()
    st.markdown(f"**기준일** `{ref_date}`  |  **최종 업데이트** `{last_refresh}`")

    metric_specs = [
        ("KOSPI", "코스피", "현재가"),
        ("KOSDAQ", "코스닥", "현재가"),
        ("USD/KRW", "USD/KRW", "환율"),
        ("US 10Y", "미국 국채 10년", "금리"),
        ("KR 3Y", "한국 국고채 3년", "금리"),
    ]
    cols = st.columns(5)
    for col, (key, title, subtitle) in zip(cols, metric_specs):
        with col:
            render_card(title, snapshot.get(key, Snapshot(key, title, None, None, None, None, None, None)), subtitle)

    market_score, market_notes = market_regime(snapshot)
    regime_output = build_market_regime_output(snapshot)
    render_action_console(regime_output)
    render_portfolio_risk_cockpit_section(snapshot, code_to_name, refresh_token)
    render_data_trust_source_panel_section(snapshot, code_to_name, refresh_token)
    render_market_regime_macro_radar_section(snapshot, code_to_name, refresh_token)
    render_krw_rates_fx_dashboard_section(snapshot, code_to_name, refresh_token)
    render_valuation_relative_cheapness_panel_section(snapshot, code_to_name, refresh_token)
    render_fundamental_quality_panel_section(snapshot, code_to_name, refresh_token)
    render_dart_disclosure_catalyst_panel_section(snapshot, code_to_name, refresh_token)
    render_smart_money_flow_short_pressure_panel_section(snapshot, code_to_name, refresh_token)
    render_forward_alpha_ranking_panel_section(snapshot, code_to_name, refresh_token)
    render_portfolio_optimizer_alert_center_section(snapshot, code_to_name, refresh_token)
    render_korea_context_bar("dashboard")
    render_explanation_panel(key_scope="dashboard")
    kospi_snap = snapshot.get("KOSPI")
    kospi_close = kospi_snap.raw["Close"] if kospi_snap and kospi_snap.raw is not None and "Close" in kospi_snap.raw.columns else None
    leadership_rows = render_investment_insight_panels(snapshot, valid_rows, code_to_name, refresh_token, market_score, kospi_close, regime_output)
    leadership_map = {row["code"]: row for row in leadership_rows}
    render_dashboard_extension_summary(snapshot, valid_rows, code_to_name, refresh_token, regime_output)

    fg_snap = snapshot.get("FNG", Snapshot("FNG", "Fear and Greed", None, None, None, None, None, None))
    fg_score = safe_float(fg_snap.last_close)
    fg_label, fg_color, fg_advice = fear_greed_zone(fg_score)
    fg_score_text = "N/A" if fg_score is None else f"{fg_score:.0f}"

    render_module_anchor("fearGreedIndex")
    st.markdown('<div class="section-title">공포·탐욕 지수</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="small-note">0에 가까울수록 공포, 100에 가까울수록 탐욕입니다. 극단 구간에서는 추세 추종보다 리스크 관리가 우선입니다.</div>',
        unsafe_allow_html=True,
    )
    fg_cols = st.columns([1.35, 1])
    with fg_cols[0]:
        render_fear_greed_visibility_gauge(fg_score, fg_label, fg_color, fg_advice)
        st.pyplot(plot_fear_greed_bar(fg_score, fg_label, fg_color), clear_figure=True)
    with fg_cols[1]:
        position_text = (
            "분할과 방어 우선" if fg_score is not None and fg_score <= 44 else
            "중립적 선별 검토" if fg_score is not None and fg_score <= 55 else
            "과열 여부 확인"
        )
        st.markdown(
            f"""
            <div class="fear-greed-panel" style="height: 100%; display:flex; flex-direction:column; justify-content:center;">
                <div class="section-title" style="margin-top:0;">시장 심리</div>
                <div style="font-size:1.5rem; font-weight:900; color:{fg_color}; margin-bottom:6px;">{fg_label}</div>
                <div style="font-size:1.1rem; font-weight:800; margin-bottom:8px;">{fg_score_text}</div>
                <div class="small-note" style="font-size:0.92rem; line-height:1.55;">
                    {fg_advice}<br/>
                    현재 해석: <b>{position_text}</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "공포·탐욕 설명 보기",
            key="fear_greed_explain_button",
            use_container_width=True,
            help="시장 심리 지표가 알고리즘과 리스크 관리에 어떻게 반영되는지 봅니다.",
        ):
            update_korea_context(
                selectedMetric="fearGreed",
                selectedModule="fearGreedIndex",
                selectedFearGreedBand=fg_label,
                sourceModule="fearGreedIndex",
            )

    render_ecos_cards(refresh_token)

    st.markdown('<div class="section-title">주요 종목 카드</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="small-note">관심종목의 현재가, 행동 후보, 기대값, 손익비, 공시 위험, 최대 검토 비중을 한 번에 확인합니다.</div>',
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

    st.markdown('<div class="section-title">종목 수익률 비교</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="small-note">관심종목의 최근 1거래일 수익률을 비교합니다. 선택 종목은 아래 상세 차트와 연결됩니다.</div>',
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

    select_options = [row["code"] for row in rows] if rows else codes_in_order
    selected_symbol = st.selectbox(
        "상세 차트 종목 선택",
        options=select_options,
        index=(select_options.index(active_code) if active_code in select_options else 0),
        format_func=lambda code: f"{code} {code_to_name.get(code, STOCK_UNIVERSE_NAME_HINTS.get(code, code))}",
        key="detail_selector",
    )
    st.session_state.manual_active_code = selected_symbol
    st.session_state.active_code = selected_symbol

    st.markdown('<div class="section-title">종목 상세 차트</div>', unsafe_allow_html=True)

    if active_code is None:
        st.info("상세 차트로 표시할 종목이 없습니다.")
        st.stop()

    active_name = code_to_name.get(active_code, STOCK_UNIVERSE_NAME_HINTS.get(active_code, active_code))
    active_hist = load_symbol_history(active_code, refresh_token, periods=240)
    signal, stock_score, reasons, volatility_flag = summarize_stock(active_code, active_name, active_hist, kospi_close, market_score)

    render_signal_box(active_name, signal, stock_score, reasons)

    coach = coach_message(market_score, signal, stock_score, volatility_flag)
    st.info(coach)
    if market_notes:
        st.caption("시장 해석: " + " / ".join(market_notes[:3]))

    render_module_anchor("candleVolumeChart")
    st.markdown('<div class="section-title">최근 60거래일 캔들 + 거래량</div>', unsafe_allow_html=True)
    if active_hist.empty:
        st.warning("선택 종목의 가격 데이터를 불러오지 못했습니다.")
    else:
        range_label = st.radio(
            "차트 범위",
            ["20D", "60D", "120D", "1Y"],
            index=1,
            horizontal=True,
            key=f"dashboard_candle_range_{active_code}",
        )
        range_count = {"20D": 20, "60D": 60, "120D": 120, "1Y": 240}.get(range_label, 60)
        chart_hist = active_hist.tail(range_count)
        fig_candle = plot_candlestick_with_volume(chart_hist, f"{active_name} ({active_code})")
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
            st.metric("현재가", format_price(latest_close))
        with summary_cols[1]:
            st.metric("5일 수익률", format_pct(r["5d"]))
        with summary_cols[2]:
            st.metric("20일 수익률", format_pct(r["20d"]))
        with summary_cols[3]:
            st.metric("거래량", korea_format_volume(latest_volume), "N/A" if vol_ratio is None else f"20일 평균 대비 {vol_ratio:.2f}x")
        open_c, high_c, low_c, close_c, volume_c = find_ohlcv_columns(chart_hist)
        detail_df = chart_hist[[open_c, high_c, low_c, close_c, volume_c]].dropna()
        if not detail_df.empty:
            date_options = list(range(len(detail_df)))
            selected_idx = st.selectbox(
                "거래일 상세",
                options=date_options,
                index=len(date_options) - 1,
                format_func=lambda idx: detail_df.index[idx].strftime("%Y-%m-%d") if hasattr(detail_df.index[idx], "strftime") else str(detail_df.index[idx])[:10],
                key=f"dashboard_candle_date_{active_code}_{range_label}",
            )
            selected_date_obj = detail_df.index[selected_idx]
            selected_date = selected_date_obj.strftime("%Y-%m-%d") if hasattr(selected_date_obj, "strftime") else str(selected_date_obj)[:10]
            selected_row = detail_df.iloc[selected_idx]
            if st.button("선택 거래일 근거 연결", key=f"dashboard_candle_link_{active_code}_{selected_date}", use_container_width=True):
                update_korea_context(
                    selectedStockCode=active_code,
                    selectedStockName=active_name,
                    selectedDate=selected_date,
                    selectedDateRange=range_label,
                    selectedMetric="expectedReturn3M",
                    selectedModule="candleVolumeChart",
                    sourceModule="candleVolumeChart",
                )
            supply_for_date = next((row for row in getKoreaSupplyDemand(active_code) if str(getattr(row, "date", ""))[:10] == selected_date), None)
            supply_text = "수급 데이터 없음"
            if supply_for_date is not None:
                flow = sum(
                    safe_float(getattr(supply_for_date, field, 0)) or 0
                    for field in ["foreign_net_buy", "institution_net_buy", "pension_net_buy"]
                )
                supply_text = f"외국인+기관+연기금 합산 {korea_format_trading_value(flow)}"
            st.html(
                f"""
                <div class="korea-explanation-panel">
                    <strong>{html.escape(active_name)} {html.escape(selected_date)} OHLCV</strong>
                    <div class="korea-explain-muted">
                        Open {html.escape(format_price(safe_float(selected_row[open_c])))} ·
                        High {html.escape(format_price(safe_float(selected_row[high_c])))} ·
                        Low {html.escape(format_price(safe_float(selected_row[low_c])))} ·
                        Close {html.escape(format_price(safe_float(selected_row[close_c])))} ·
                        Volume {html.escape(korea_format_volume(safe_float(selected_row[volume_c])))}
                    </div>
                    <div class="korea-explain-muted" style="margin-top:8px;">연결 수급: {html.escape(supply_text)}</div>
                    <span class="korea-mini-link">수급 레이더</span><span class="korea-mini-link">리스크 큐</span><span class="korea-mini-link">공시 확인</span>
                </div>
                """
            )

    st.markdown("---")
    st.markdown("**데이터 원천: FinanceDataReader / Naver / 공식 API 설정값**")
    st.caption(f"데이터 기준: {last_refresh}")
    render_data_quality_banner(snapshot, valid_rows)



def render_disclosure_section(
    valid_rows: list[dict[str, Any]],
    code_to_name: dict[str, str],
    refresh_token: int,
    last_refresh: str,
) -> None:
    st.markdown('<div class="section-title">공시·이벤트 리스크</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="small-note">DART 최근 공시를 관심종목과 연결해 유상증자, CB/BW, 감자, 감사의견, 소송 등 리스크를 확인합니다.</div>',
        unsafe_allow_html=True,
    )

    dart_df = load_recent_disclosures(refresh_token, DART_API_TOKEN)
    watch_names = {row["name"] for row in valid_rows}
    watch_codes = {row["code"] for row in valid_rows}

    if "disclosure_query_applied" not in st.session_state:
        st.session_state.disclosure_query_applied = ""

    with st.form("disclosure_search_form", clear_on_submit=False):
        filter_watchlist = st.checkbox("관심종목만 보기", value=True, key="disclosure_watchlist_only")
        query = st.text_input(
            "회사명, 종목코드, 공시명 검색",
            placeholder="예: 두산에너빌리티, 유상증자, 감사의견",
            key="disclosure_query",
        )
        limit = st.slider("표시 개수", min_value=5, max_value=40, value=15, step=5, key="disclosure_limit")
        search_submit = st.form_submit_button("검색")

    if search_submit:
        st.session_state.disclosure_query_applied = query.strip()

    applied_query = st.session_state.disclosure_query_applied.strip()
    applied_watchlist = filter_watchlist

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
                st.info("관심종목에서는 찾지 못해 전체 DART 공시에서 검색했습니다.")

    summary_cols = st.columns(4)
    summary_cols[0].metric("전체 공시", f"{len(dart_df):,}")
    summary_cols[1].metric("표시", f"{len(filtered):,}")
    summary_cols[2].metric("관심종목", f"{len(watch_names):,}")
    summary_cols[3].metric("분류", "규칙 기반")
    api_state = "미설정" if not DART_API_KEY else "연결"
    st.caption(f"DART API 상태: {api_state} · 데이터 기준: {last_refresh}")
    if applied_query:
        st.caption(f"검색어: {applied_query}")

    if dart_df.empty:
        st.info("최근 공시 데이터를 표시할 수 없습니다.")
        return
    if filtered.empty:
        st.info("조건에 맞는 공시가 없습니다.")
        return

    display_df = filtered.head(limit).copy()
    display_df[["label", "label_score", "label_reason"]] = display_df["report_name"].apply(
        lambda value: pd.Series(disclosure_severity(value))
    )

    st.markdown(
        """
        <style>
            .disclosure-card {
                background: linear-gradient(180deg, rgba(17, 24, 39, 0.96), rgba(11, 16, 32, 0.94));
                border: 1px solid var(--stance-border-default, rgba(148, 163, 184, 0.28));
                border-radius: 16px;
                padding: 14px 16px;
                margin-bottom: 12px;
                color: var(--stance-text-primary, #F8FAFC) !important;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 16px 38px rgba(2, 6, 23, 0.26);
            }
            .disclosure-card * { color: inherit; }
            .disclosure-title { font-weight: 800; font-size: 1.02rem; margin: 2px 0 6px 0; color: var(--stance-text-primary, #F8FAFC) !important; }
            .disclosure-company { font-weight: 800; color: var(--stance-text-primary, #F8FAFC) !important; }
            .disclosure-meta { color: var(--stance-text-tertiary, #CBD5E1) !important; font-size: 0.86rem; margin-top: 4px; }
            .disclosure-card a { color: var(--stance-info, #38BDF8) !important; font-weight: 700; text-decoration: none; }
            .disclosure-card a:hover { text-decoration: underline; }
            .badge { display:inline-block; padding:3px 10px; border-radius:999px; font-size:0.78rem; font-weight:800; margin-right:6px; }
            .badge-good { background:rgba(74,222,128,0.16); color:#BBF7D0; border:1px solid rgba(74,222,128,0.28); }
            .badge-mid { background:rgba(148,163,184,0.16); color:#E5E7EB; border:1px solid rgba(148,163,184,0.24); }
            .badge-bad { background:rgba(251,113,133,0.16); color:#FFE4E6; border:1px solid rgba(251,113,133,0.30); }
        </style>
        """,
        unsafe_allow_html=True,
    )

    for _, row in display_df.iterrows():
        severity = str(row["label"])
        badge_class = "badge-bad" if severity in {"High", "Critical"} else "badge-mid" if severity == "Medium" else "badge-good"
        report_url = str(row.get("report_url", "") or "")
        report_link = f'<div style="margin-top:8px;"><a href="{html.escape(report_url)}" target="_blank" rel="noopener noreferrer">원문 보기</a></div>' if report_url else ""
        note_text = f" · {row['note']}" if row.get("note") else ""
        st.markdown(
            f"""
            <div class="disclosure-card">
                <div>
                    <span class="badge {badge_class}">{html.escape(severity)} · 점수 {int(row['label_score']):+d}</span>
                    <span class="disclosure-company">{html.escape(str(row['corp_name']))}</span>
                </div>
                <div class="disclosure-title">{html.escape(str(row['report_name']))}</div>
                <div class="disclosure-meta">{html.escape(str(row['date']))} {html.escape(str(row['time']))} · 제출자 {html.escape(str(row['submitter']))}{html.escape(note_text)}</div>
                <div class="disclosure-meta">분류 근거: {html.escape(str(row['label_reason']))}</div>
                {report_link}
            </div>
            """,
            unsafe_allow_html=True,
        )



def main() -> None:
    st.markdown('<div class="hero-title">Stance Stock Strategy</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">한국 시장, 포트폴리오 리스크, 종목 검토 흐름을 하나로 연결한 투자 의사결정 대시보드입니다.</div>',
        unsafe_allow_html=True,
    )

    if fdr is None:
        st.error("FinanceDataReader를 불러올 수 없습니다. `pip install -r requirements.txt`를 확인하세요.")
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
        st.header("관심종목 입력")
        st.caption("종목코드를 줄바꿈 또는 쉼표로 입력하세요. 최대 15개까지 표시합니다.")
        if "pending_sidebar_message" in st.session_state:
            st.success(st.session_state.pending_sidebar_message)
            del st.session_state.pending_sidebar_message
        code_text = st.text_area("종목코드", key="sidebar_codes_text", height=220)

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
            placeholder="code,qty,avg_price,sector\n005930,10,75000,반도체\n034020,5,25000,에너지",
        )

        with st.expander("리스크 기본값"):
            RISK_DEFAULTS["risk_per_trade_pct"] = st.slider("1회 거래 최대 손실(%)", 0.05, 2.0, float(RISK_DEFAULTS["risk_per_trade_pct"] * 100), 0.05) / 100
            RISK_DEFAULTS["max_position_pct"] = st.slider("단일 종목 최대 비중(%)", 1.0, 30.0, float(RISK_DEFAULTS["max_position_pct"] * 100), 0.5) / 100
            RISK_DEFAULTS["trading_cost_pct"] = st.slider("거래 비용/세금(%)", 0.0, 2.0, float(RISK_DEFAULTS["trading_cost_pct"]), 0.05)
            RISK_DEFAULTS["slippage_pct"] = st.slider("슬리피지(%)", 0.0, 2.0, float(RISK_DEFAULTS["slippage_pct"]), 0.05)

        refresh_clicked = st.button("데이터 새로고침", use_container_width=True)
        if refresh_clicked:
            st.session_state.refresh_token += 1
            st.rerun()

    codes, invalid_tokens = parse_code_input(code_text)
    if len(codes) > 15:
        st.warning("관심종목은 최대 15개까지 표시합니다. 앞의 15개만 사용합니다.")
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
        st.warning(f"인식하지 못한 입력은 제외했습니다: {', '.join(invalid_tokens)}")
    if invalid_codes:
        st.warning(f"KRX 목록에서 찾지 못한 코드는 제외했습니다: {', '.join(invalid_codes)}")
    if not valid_rows:
        st.info("유효한 종목코드가 없어 기본 관심종목을 표시합니다.")
        valid_rows = [{"code": code, "name": STOCK_UNIVERSE_NAME_HINTS.get(code, code)} for code in DEFAULT_CODES[:5]]

    watch_codes = tuple(row["code"] for row in valid_rows)
    snapshot = load_market_snapshot(st.session_state.refresh_token, watch_codes)
    ref_date_candidates = [snap.asof for snap in snapshot.values() if snap.asof is not None]
    ref_date = max(ref_date_candidates).strftime("%Y-%m-%d") if ref_date_candidates else datetime.now().strftime("%Y-%m-%d")
    last_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tabs = st.tabs(["대시보드", "포트폴리오", "종목", "알파 후보 탐색", "공시", "매크로", "브리핑", "신호 성과", "설정"])
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
