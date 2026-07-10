from __future__ import annotations

import streamlit as st


KOREA_OS_CSS = """
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
    --kos-market-up-strong: #FF1F3D;
    --kos-market-up-soft-bg: rgba(255, 77, 79, 0.12);
    --kos-market-up-border: rgba(255, 77, 79, 0.40);
    --kos-market-down: #3B82F6;
    --kos-market-down-strong: #2563EB;
    --kos-market-down-soft-bg: rgba(59, 130, 246, 0.12);
    --kos-market-down-border: rgba(59, 130, 246, 0.40);
    --kos-market-flat: #CBD5E1;
    --kos-market-flat-soft-bg: rgba(203, 213, 225, 0.10);
    --kos-market-neutral: #94A3B8;
    --kos-risk-critical: #F97316;
    --kos-risk-critical-bg: rgba(249, 115, 22, 0.14);
    --kos-risk-critical-border: rgba(249, 115, 22, 0.40);
    --kos-risk-warning: #FCD34D;
    --kos-risk-warning-bg: rgba(252, 211, 77, 0.14);
    --kos-risk-warning-border: rgba(252, 211, 77, 0.38);
    --kos-system-error: #FB7185;
    --kos-page-bg: var(--stance-bg);
    --kos-section-bg: var(--stance-card-bg);
    --kos-card-bg: var(--stance-card-bg);
    --kos-card-bg-soft: var(--stance-card-bg-soft);
    --kos-card-bg-elevated: var(--stance-surface-elevated);
    --kos-table-header-bg: #18243A;
    --kos-table-row-bg: rgba(15, 23, 42, 0.72);
    --kos-table-row-alt-bg: rgba(20, 30, 49, 0.58);
    --kos-table-row-hover-bg: rgba(139, 92, 246, 0.10);
    --kos-selected-bg: rgba(139, 92, 246, 0.16);
    --kos-border-subtle: var(--stance-border-subtle);
    --kos-border-default: var(--stance-border-default);
    --kos-border-strong: rgba(167, 139, 250, 0.46);
    --kos-focus-ring: var(--stance-focus-ring);
    --kos-text-hero: var(--stance-text-primary);
    --kos-text-primary: var(--stance-text-primary);
    --kos-text-secondary: var(--stance-text-secondary);
    --kos-text-tertiary: var(--stance-text-tertiary);
    --kos-text-muted: var(--stance-text-muted);
    --kos-text-disabled: var(--stance-text-disabled);
    --kos-text-on-accent: #FDFDFF;
    --kos-accent: #8B5CF6;
    --kos-accent-2: #A78BFA;
    --kos-accent-3: var(--stance-info);
    --kos-positive: var(--stance-positive);
    --kos-positive-text: #A7F3D0;
    --kos-positive-bg: rgba(16, 185, 129, 0.14);
    --kos-negative: var(--stance-negative);
    --kos-negative-text: #FDA4AF;
    --kos-negative-bg: rgba(244, 63, 94, 0.14);
    --kos-warning: var(--stance-warning);
    --kos-warning-text: #FDE68A;
    --kos-warning-bg: rgba(245, 158, 11, 0.14);
    --kos-neutral-text: var(--stance-neutral);
    --kos-neutral-bg: rgba(148, 163, 184, 0.14);
    --kos-info-text: #BAE6FD;
    --kos-info-bg: rgba(56, 189, 248, 0.14);
    --kos-font: Pretendard, Inter, "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    --kos-font-num: Inter, "SF Pro Display", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    --kos-font-code: "Roboto Mono", "SFMono-Regular", Consolas, monospace;
}

html,
body,
.stApp,
[data-testid="stAppViewContainer"] {
    font-family: var(--kos-font) !important;
    color: var(--stance-text-primary) !important;
    overflow-x: hidden;
}

.stApp {
    background: var(--stance-bg) !important;
}

[data-testid="stHeader"] {
    background: rgba(7, 10, 19, 0.72) !important;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #090E1B, #0F172A) !important;
    color: var(--kos-text-primary) !important;
}

[data-testid="stSidebar"] *,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p {
    color: var(--kos-text-secondary) !important;
    font-family: var(--kos-font) !important;
}

.stApp h1,
.stApp h2,
.stApp h3,
.stApp h4 {
    color: var(--kos-text-hero) !important;
    font-family: var(--kos-font) !important;
    letter-spacing: -0.02em;
    line-height: 1.18;
}

.stApp [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stMarkdownContainer"] li,
.stApp [data-testid="stMarkdownContainer"] span {
    color: inherit;
    font-family: var(--kos-font) !important;
}

.stApp,
.stApp p,
.stApp li,
.stApp span,
.stApp div {
    color-scheme: dark;
}

.stApp p,
.stApp li,
.stApp span,
.stApp div,
.stApp button,
.stApp label,
.portfolio-intelligence-shell,
.portfolio-intelligence-shell *,
.korea-card,
.korea-card *,
.command-table,
.command-table *,
.korea-table,
.korea-table * {
    word-break: keep-all;
    overflow-wrap: anywhere;
}

.stApp [data-testid="stSidebarCollapseButton"] [class*="material"],
.stApp [data-testid="collapsedControl"] [class*="material"],
.stApp [data-testid="stSidebarCollapseButton"] span[aria-hidden="true"],
.stApp [data-testid="collapsedControl"] span[aria-hidden="true"],
.stApp [data-testid="stIconMaterial"] {
    font-size: 0 !important;
    line-height: 0 !important;
    width: 28px !important;
    height: 28px !important;
    overflow: hidden !important;
}

.stApp [data-testid="stIconMaterial"] {
    display: none !important;
}

.stApp span:has(> [data-testid="stIconMaterial"])::before {
    content: "›";
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    min-width: 18px;
    height: 18px;
    color: var(--stance-text-primary);
    font-size: 18px;
    line-height: 1;
}

.stApp [data-testid="stSidebarCollapseButton"] [class*="material"]::before,
.stApp [data-testid="collapsedControl"] [class*="material"]::before,
.stApp [data-testid="stSidebarCollapseButton"] span[aria-hidden="true"]::before,
.stApp [data-testid="collapsedControl"] span[aria-hidden="true"]::before,
.stApp [data-testid="stIconMaterial"]::before {
    content: "‹";
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    color: var(--stance-text-primary);
    font-size: 22px;
    line-height: 1;
}

.portfolio-intelligence-shell .pi-card-header {
    align-items: flex-start !important;
    min-width: 0 !important;
}

.portfolio-intelligence-shell .pi-card-header strong,
.portfolio-intelligence-shell .pi-card-header span,
.portfolio-intelligence-shell .portfolio-intelligence-title strong,
.portfolio-intelligence-shell .portfolio-intelligence-title span,
.portfolio-intelligence-shell .pi-rebalance-asset,
.portfolio-intelligence-shell .pi-rebalance-reason,
.portfolio-intelligence-shell .pi-rebalance-impact,
.portfolio-intelligence-shell .pi-asset-label,
.portfolio-intelligence-shell .pi-signal-row > div,
.portfolio-intelligence-shell .pi-allocation-value {
    min-width: 0 !important;
    white-space: normal !important;
    line-height: 1.45 !important;
}

.portfolio-intelligence-shell .pi-badge {
    min-width: 0 !important;
    max-width: 100% !important;
    white-space: normal !important;
    text-align: center !important;
    padding: 5px 9px !important;
    line-height: 1.25 !important;
}

.portfolio-intelligence-shell .pi-badge.market-up,
.portfolio-intelligence-shell .pi-badge.market-badge-up {
    color: #FFE4E6 !important;
    background: var(--kos-market-up-soft-bg) !important;
    border-color: var(--kos-market-up-border) !important;
}

.portfolio-intelligence-shell .pi-badge.market-down,
.portfolio-intelligence-shell .pi-badge.market-badge-down {
    color: #DBEAFE !important;
    background: var(--kos-market-down-soft-bg) !important;
    border-color: var(--kos-market-down-border) !important;
}

.portfolio-intelligence-shell .pi-badge.market-flat,
.portfolio-intelligence-shell .pi-badge.market-neutral,
.portfolio-intelligence-shell .pi-badge.market-badge-flat {
    color: var(--kos-market-flat) !important;
    background: var(--kos-market-flat-soft-bg) !important;
    border-color: rgba(203, 213, 225, 0.28) !important;
}

.portfolio-intelligence-shell .pi-badge.risk-critical {
    color: #FFEDD5 !important;
    background: var(--kos-risk-critical-bg) !important;
    border-color: var(--kos-risk-critical-border) !important;
}

.portfolio-intelligence-shell .pi-badge.risk-warning {
    color: #FEF3C7 !important;
    background: var(--kos-risk-warning-bg) !important;
    border-color: var(--kos-risk-warning-border) !important;
}

.portfolio-intelligence-shell .pi-signal-row,
.portfolio-intelligence-shell .pi-allocation-row,
.portfolio-intelligence-shell .pi-rebalance-item {
    min-width: 0 !important;
    max-width: 100% !important;
    overflow: hidden !important;
}

.stApp .hero-title,
.stApp .section-title,
.stApp .metric-name,
.stApp .metric-value,
.stApp .insight-title,
.stApp .pressure-score strong,
.stApp .row-value,
.stApp .rank-name strong,
.stApp .quality-score,
.stApp .action-panel strong,
.stApp .command-table td,
.stApp .decision-title,
.stApp .decision-conclusion,
.stApp .decision-tile strong {
    color: var(--stance-text-primary) !important;
}

.stApp .hero-subtitle,
.stApp .metric-label,
.stApp .row-label,
.stApp .thesis,
.stApp .action-panel div,
.stApp .decision-tile span,
.stApp .command-table th {
    color: var(--stance-text-secondary) !important;
}

.stApp .small-note,
.stApp .metric-change-flat,
.stApp .insight-kicker,
.stApp .pressure-score span,
.stApp .row-sub,
.stApp .rank-header,
.stApp .rank-name span,
.stApp .quality-warnings,
.stApp .meta-pill,
.stApp .decision-tile small {
    color: var(--stance-text-tertiary) !important;
}

.stApp .metric-card,
.stApp .signal-box,
.stApp .insight-panel,
.stApp .quality-banner,
.stApp .action-panel,
.stApp .decision-report {
    background: linear-gradient(180deg, rgba(17, 24, 39, 0.96), rgba(11, 16, 32, 0.94)) !important;
    border: 1px solid var(--stance-border-default) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 16px 38px rgba(2, 6, 23, 0.26) !important;
    color: var(--stance-text-primary) !important;
}

.stApp .decision-tile,
.stApp .thesis,
.stApp .meta-pill {
    background: rgba(23, 32, 51, 0.82) !important;
    border-color: var(--stance-border-subtle) !important;
}

.stApp .mini-track,
.stApp .meter-track {
    background: rgba(148, 163, 184, 0.24) !important;
}

.stApp .meter-pin {
    background: var(--stance-text-primary) !important;
    box-shadow: 0 0 0 2px var(--stance-card-bg) !important;
}

.stApp .metric-change-pos,
.stApp .signal-buy {
    color: var(--kos-market-up) !important;
}

.stApp .metric-change-neg,
.stApp .signal-sell {
    color: var(--kos-market-down) !important;
}

.stApp .signal-neutral {
    color: var(--stance-neutral) !important;
}

.stApp .pi-tone-good .pi-metric-value,
.stApp .pi-value-good {
    color: var(--kos-market-up) !important;
}

.stApp .pi-tone-risk .pi-metric-value,
.stApp .pi-value-risk {
    color: var(--kos-market-down) !important;
}

.stApp [data-testid="stTabs"] [role="tablist"] {
    gap: 6px;
    border-bottom: 1px solid var(--stance-border-subtle);
}

.stApp [data-testid="stTabs"] button {
    color: var(--stance-text-tertiary) !important;
    border-radius: 10px 10px 0 0;
}

.stApp [data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--stance-text-primary) !important;
    border-bottom-color: var(--stance-focus-ring) !important;
}

.stApp [data-testid="stAlert"],
.stApp [data-testid="stNotification"],
.stApp [data-testid="stStatusWidget"] {
    background: rgba(17, 24, 39, 0.94) !important;
    border-color: var(--stance-border-default) !important;
    color: var(--stance-text-primary) !important;
}

.stApp [data-testid="stAlert"] *,
.stApp [data-testid="stNotification"] *,
.stApp [data-testid="stStatusWidget"] * {
    color: inherit !important;
}

.stApp [data-baseweb="popover"],
.stApp [data-baseweb="menu"],
.stApp [role="listbox"],
.stApp [role="option"] {
    background: var(--stance-surface-elevated) !important;
    color: var(--stance-text-primary) !important;
    border-color: var(--stance-border-default) !important;
}

.stApp [role="option"]:hover,
.stApp [role="option"][aria-selected="true"] {
    background: rgba(56, 189, 248, 0.12) !important;
    color: var(--stance-text-primary) !important;
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

.stApp input,
.stApp textarea,
.stApp select,
.stApp [data-baseweb] {
    font-family: var(--kos-font) !important;
}

.stApp label,
.stApp [data-testid="stWidgetLabel"],
.stApp [data-testid="stWidgetLabel"] *,
.stApp [data-baseweb="select"] *,
.stApp [data-baseweb="tag"] *,
.stApp [data-baseweb="slider"] * {
    color: var(--kos-text-secondary) !important;
    font-weight: 650 !important;
}

.stApp input,
.stApp textarea,
.stApp [data-baseweb="select"] > div,
.stApp [data-baseweb="base-input"] {
    background: rgba(15, 23, 42, 0.82) !important;
    color: var(--kos-text-primary) !important;
    border-color: var(--kos-border-default) !important;
    box-shadow: none !important;
}

.stApp input::placeholder,
.stApp textarea::placeholder,
.stApp [data-baseweb="base-input"] input::placeholder,
.stApp [data-baseweb="base-input"] textarea::placeholder {
    color: var(--stance-text-muted) !important;
    opacity: 1 !important;
}

.stApp input::-webkit-input-placeholder,
.stApp textarea::-webkit-input-placeholder {
    color: var(--stance-text-muted) !important;
    opacity: 1 !important;
}

.stApp input::-moz-placeholder,
.stApp textarea::-moz-placeholder {
    color: var(--stance-text-muted) !important;
    opacity: 1 !important;
}

.stApp input:-ms-input-placeholder,
.stApp textarea:-ms-input-placeholder {
    color: var(--stance-text-muted) !important;
    opacity: 1 !important;
}

.stApp input:focus,
.stApp textarea:focus,
.stApp button:focus,
.stApp [data-baseweb="select"] > div:focus-within {
    outline: 2px solid var(--kos-focus-ring) !important;
    outline-offset: 2px;
}

.stApp [data-testid="stExpander"] {
    border: 1px solid var(--kos-border-default) !important;
    border-radius: 14px !important;
    background: linear-gradient(180deg, rgba(19, 30, 49, 0.94), rgba(10, 16, 32, 0.86)) !important;
    overflow: hidden;
}

.stApp [data-testid="stExpander"] summary,
.stApp [data-testid="stExpander"] summary * {
    color: var(--kos-text-primary) !important;
    font-weight: 760 !important;
    letter-spacing: -0.01em;
}

.stApp .stButton > button,
.stApp button[kind="secondary"],
.stApp button[kind="primary"] {
    border-radius: 10px !important;
    min-height: 38px;
    border: 1px solid var(--kos-border-default) !important;
    background: linear-gradient(180deg, rgba(23, 34, 56, 0.96), rgba(16, 24, 39, 0.92)) !important;
    color: var(--kos-text-primary) !important;
    font-weight: 760 !important;
    letter-spacing: -0.01em;
}

.stApp .stButton > button:hover,
.stApp button[kind="secondary"]:hover,
.stApp button[kind="primary"]:hover {
    border-color: var(--kos-border-strong) !important;
    background: linear-gradient(180deg, rgba(47, 39, 93, 0.96), rgba(24, 31, 52, 0.94)) !important;
    color: var(--kos-text-hero) !important;
}

.stApp [data-testid="stMetric"] {
    border: 1px solid var(--kos-border-subtle);
    border-radius: 12px;
    background: rgba(16, 24, 39, 0.72);
    padding: 11px 12px;
}

.stApp [data-testid="stMetricLabel"] *,
.stApp [data-testid="stMetricDelta"] * {
    color: var(--kos-text-tertiary) !important;
    font-size: 12.5px !important;
    font-weight: 650 !important;
}

.stApp [data-testid="stMetricValue"] * {
    color: var(--kos-text-hero) !important;
    font-family: var(--kos-font-num) !important;
    font-weight: 820 !important;
    font-variant-numeric: tabular-nums;
}

.stApp [data-testid="stDataFrame"],
.stApp .stDataFrame,
.stApp .stTable {
    color: var(--kos-text-primary) !important;
    border: 1px solid var(--kos-border-default) !important;
    border-radius: 12px !important;
    overflow: hidden !important;
    background: rgba(15, 23, 42, 0.72) !important;
}

.stApp [data-testid="stDataFrame"] *,
.stApp .stDataFrame *,
.stApp .stTable * {
    font-family: var(--kos-font) !important;
    color: var(--kos-text-primary);
}

.stApp [role="radiogroup"] {
    gap: 6px;
}

.stApp [data-testid="stCheckbox"] label,
.stApp [data-testid="stRadio"] label,
.stApp [data-testid="stSlider"] label,
.stApp [data-testid="stMultiSelect"] label,
.stApp [data-testid="stSelectbox"] label {
    color: var(--kos-text-secondary) !important;
    font-weight: 680 !important;
}

.stApp [data-testid="stSlider"] [data-testid="stTickBar"] *,
.stApp [data-testid="stSlider"] [data-testid="stThumbValue"] {
    color: var(--kos-text-tertiary) !important;
    font-family: var(--kos-font-num) !important;
    font-weight: 650 !important;
}

.stApp [role="radiogroup"] label {
    border: 1px solid var(--kos-border-default);
    background: rgba(16, 24, 39, 0.72);
    border-radius: 999px;
    min-height: 32px;
    padding: 4px 10px;
}

.stApp [role="radiogroup"] label *,
.stApp [role="radiogroup"] p,
.stApp [data-testid="stRadio"] p,
.stApp [data-testid="stRadio"] span {
    color: var(--stance-text-tertiary) !important;
}

.stApp [role="radiogroup"] label:has(input:checked) {
    border-color: var(--kos-border-strong);
    background: var(--kos-selected-bg);
}

.stApp [role="radiogroup"] label:has(input:checked) *,
.stApp [role="radiogroup"] label:has(input:checked) p,
.stApp [role="radiogroup"] label:has(input:checked) span {
    color: var(--stance-text-primary) !important;
}

.korea-os-theme,
.stApp .korea-os-theme,
[data-testid="stMarkdownContainer"] .korea-os-theme {
    font-family: var(--kos-font) !important;
    color: var(--kos-text-primary);
}

.korea-os-theme *,
.korea-os-shell *,
.korea-card *,
.korea-table *,
.korea-module-title *,
.korea-explanation-panel * {
    box-sizing: border-box;
}

.portfolio-shell.korea-shell,
.portfolio-shell.korea-shell.korea-os-theme {
    background:
        radial-gradient(circle at 8% 0%, rgba(139, 92, 246, 0.18), transparent 24%),
        radial-gradient(circle at 92% 12%, rgba(56, 189, 248, 0.08), transparent 23%),
        linear-gradient(135deg, var(--kos-section-bg), #0E1729 54%, #160F2C) !important;
    color: var(--kos-text-primary) !important;
    border-color: var(--kos-border-default) !important;
}

.korea-os-theme .portfolio-title,
.korea-os-theme .hero-title {
    color: var(--kos-text-hero) !important;
    font-size: clamp(24px, 2.2vw, 30px) !important;
    font-weight: 820 !important;
    line-height: 1.16 !important;
    letter-spacing: -0.02em !important;
}

.korea-os-theme .portfolio-subtitle,
.korea-os-theme .small-note,
.korea-os-theme .portfolio-card-sub,
.korea-os-theme .korea-card-subtitle,
.korea-os-card-desc {
    color: var(--kos-text-secondary) !important;
    font-size: 13.5px !important;
    font-weight: 480 !important;
    line-height: 1.55 !important;
}

.korea-os-theme .korea-module-title,
.korea-os-section-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 14px;
    margin: 24px 0 12px;
    padding: 15px 16px;
    border: 1px solid var(--kos-border-subtle);
    border-radius: 14px;
    background: linear-gradient(180deg, rgba(19, 30, 49, 0.84), rgba(10, 16, 32, 0.58));
}

.korea-os-theme .korea-module-title strong {
    color: var(--kos-text-hero) !important;
    font-size: clamp(18px, 1.4vw, 21px) !important;
    font-weight: 780 !important;
    line-height: 1.2 !important;
    letter-spacing: -0.02em !important;
}

.korea-os-theme .korea-module-title span {
    color: var(--kos-text-secondary) !important;
    display: block;
    margin-top: 5px;
    font-size: 13.5px !important;
    line-height: 1.5;
}

.korea-os-theme .korea-module-meta,
.korea-os-theme .korea-mini-link,
.korea-os-nav a {
    color: var(--kos-info-text) !important;
    background: var(--kos-info-bg) !important;
    border: 1px solid rgba(56, 189, 248, 0.24) !important;
    font-size: 12px !important;
    font-weight: 740 !important;
}

.korea-os-theme .korea-card,
.korea-os-shell,
.korea-os-card,
.korea-explanation-panel,
.korea-context-bar,
.fear-greed-panel {
    color: var(--kos-text-primary) !important;
    background: linear-gradient(180deg, rgba(23, 34, 56, 0.96), rgba(16, 24, 39, 0.94)) !important;
    border: 1px solid var(--kos-border-default) !important;
    border-radius: 14px !important;
    box-shadow: inset 0 1px 0 rgba(248,250,252,0.055), 0 16px 36px rgba(2,6,23,0.24) !important;
}

.korea-context-bar {
    position: relative;
    padding: 13px 15px !important;
    margin: 10px 0 14px !important;
}

.korea-context-bar::before {
    content: "";
    position: absolute;
    inset: 12px auto 12px 0;
    width: 3px;
    border-radius: 999px;
    background: linear-gradient(180deg, var(--kos-accent-2), var(--kos-accent-3));
}

.korea-context-bar strong {
    color: var(--kos-text-hero) !important;
    font-size: 14.5px !important;
    font-weight: 800 !important;
    line-height: 1.2 !important;
}

.korea-os-card {
    padding: 15px !important;
}

.korea-os-card-head,
.korea-card-head {
    border-bottom: 1px solid var(--kos-border-subtle) !important;
    gap: 12px !important;
}

.korea-card-title,
.korea-os-card-title,
.korea-os-label {
    color: var(--kos-text-hero) !important;
    font-size: 15.5px !important;
    font-weight: 760 !important;
    line-height: 1.25 !important;
    letter-spacing: -0.01em !important;
}

.korea-score,
.korea-os-score,
.korea-metric strong,
.korea-metric-card strong,
.korea-os-metric strong {
    color: var(--kos-text-hero) !important;
    font-family: var(--kos-font-num) !important;
    font-variant-numeric: tabular-nums;
    font-weight: 820 !important;
    letter-spacing: -0.01em;
}

.korea-metric small,
.korea-metric-card small,
.korea-os-metric small {
    color: var(--kos-text-tertiary) !important;
    font-size: 12px !important;
    font-weight: 670 !important;
}

.korea-os-muted,
.korea-explain-muted,
.korea-context-meta,
.korea-card-subtitle,
.korea-evidence,
.korea-table td .muted {
    color: var(--kos-text-tertiary) !important;
}

.korea-evidence {
    display: -webkit-box;
    overflow: hidden;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    line-height: 1.45 !important;
    min-width: 220px;
}

.korea-safety-callout,
.korea-os-callout,
.korea-info-callout,
.korea-context-bar,
.korea-filter-summary {
    color: var(--kos-info-text) !important;
    background: linear-gradient(180deg, rgba(56, 189, 248, 0.13), rgba(139, 92, 246, 0.09)) !important;
    border: 1px solid rgba(56, 189, 248, 0.24) !important;
    border-radius: 12px !important;
    padding: 11px 12px !important;
    line-height: 1.55 !important;
    font-size: 13px !important;
    font-weight: 520 !important;
}

.korea-filter-summary {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin: 10px 0 12px;
}

.korea-filter-summary strong {
    color: var(--kos-text-hero);
    font-weight: 780;
    margin-right: 4px;
}

.korea-filter-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    min-height: 28px;
    border-radius: 999px;
    padding: 5px 10px;
    color: var(--kos-text-secondary);
    background: rgba(15, 23, 42, 0.54);
    border: 1px solid var(--kos-border-subtle);
    font-size: 12px;
    font-weight: 680;
}

.korea-badge,
.korea-os-theme .korea-badge {
    display: inline-flex !important;
    align-items: center;
    justify-content: center;
    min-height: 25px;
    border-radius: 999px !important;
    padding: 5px 10px !important;
    font-size: 11.8px !important;
    font-weight: 760 !important;
    line-height: 1.05 !important;
    white-space: nowrap;
    letter-spacing: 0 !important;
}

.korea-badge.good { color: var(--kos-positive-text) !important; background: var(--kos-positive-bg) !important; border-color: rgba(52, 211, 153, 0.34) !important; }
.korea-badge.market-up,
.korea-badge.market-badge-up { color: #FFE4E6 !important; background: var(--kos-market-up-soft-bg) !important; border-color: var(--kos-market-up-border) !important; }
.korea-badge.market-down,
.korea-badge.market-badge-down { color: #DBEAFE !important; background: var(--kos-market-down-soft-bg) !important; border-color: var(--kos-market-down-border) !important; }
.korea-badge.market-flat,
.korea-badge.market-badge-flat { color: var(--kos-market-flat) !important; background: var(--kos-market-flat-soft-bg) !important; border-color: rgba(203, 213, 225, 0.28) !important; }
.korea-badge.risk-critical { color: #FFEDD5 !important; background: var(--kos-risk-critical-bg) !important; border-color: var(--kos-risk-critical-border) !important; }
.korea-badge.risk-warning { color: #FEF3C7 !important; background: var(--kos-risk-warning-bg) !important; border-color: var(--kos-risk-warning-border) !important; }
.korea-badge.info { color: var(--kos-info-text) !important; background: var(--kos-info-bg) !important; border-color: rgba(56, 189, 248, 0.30) !important; }
.korea-badge.warn { color: var(--kos-warning-text) !important; background: var(--kos-warning-bg) !important; border-color: rgba(251, 191, 36, 0.32) !important; }
.korea-badge.risk { color: var(--kos-negative-text) !important; background: var(--kos-negative-bg) !important; border-color: rgba(251, 113, 133, 0.34) !important; }
.korea-badge.muted { color: var(--kos-neutral-text) !important; background: var(--kos-neutral-bg) !important; border-color: rgba(148, 163, 184, 0.26) !important; }

.korea-os-table-wrap,
.korea-table-wrap {
    width: 100%;
    max-width: 100%;
    overflow: auto;
    border-radius: 13px !important;
    border: 1px solid var(--kos-border-subtle) !important;
    background: rgba(7, 10, 19, 0.34) !important;
}

.korea-os-table,
.korea-table {
    width: 100%;
    min-width: 760px;
    border-collapse: separate !important;
    border-spacing: 0 !important;
    font-size: 13px !important;
    line-height: 1.42 !important;
    font-family: var(--kos-font) !important;
    font-variant-numeric: tabular-nums;
}

.korea-os-table th,
.korea-table th {
    position: sticky;
    top: 0;
    z-index: 3;
    padding: 11px 12px !important;
    color: var(--kos-text-secondary) !important;
    background: var(--kos-table-header-bg) !important;
    border-bottom: 1px solid var(--kos-border-default) !important;
    font-size: 12.2px !important;
    font-weight: 760 !important;
    text-align: left;
    white-space: nowrap;
}

.korea-os-table th:first-child,
.korea-table th:first-child,
.korea-os-table td:first-child,
.korea-table td:first-child {
    position: sticky;
    left: 0;
    z-index: 2;
}

.korea-os-table th:first-child,
.korea-table th:first-child {
    z-index: 4;
}

.korea-os-table td:first-child,
.korea-table td:first-child {
    background: rgba(16, 24, 39, 0.98) !important;
}

.korea-os-table td,
.korea-table td {
    padding: 10px 12px !important;
    color: var(--kos-text-primary) !important;
    background: var(--kos-table-row-bg) !important;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15) !important;
    font-size: 13px !important;
    font-weight: 520 !important;
    vertical-align: middle !important;
}

.korea-os-table tbody tr:nth-child(even) td,
.korea-table tbody tr:nth-child(even) td {
    background: var(--kos-table-row-alt-bg) !important;
}

.korea-os-table tbody tr:hover td,
.korea-table tbody tr:hover td {
    background: var(--kos-table-row-hover-bg) !important;
}

.korea-os-table td.num,
.korea-table td.num,
.korea-os-table th.num,
.korea-table th.num {
    text-align: right !important;
    font-family: var(--kos-font-num) !important;
}

.korea-stock-cell {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 112px;
}

.korea-stock-cell strong {
    color: var(--kos-text-primary);
    font-size: 13.5px;
    font-weight: 760;
    line-height: 1.2;
}

.korea-stock-cell span {
    color: var(--kos-text-tertiary);
    font-size: 12px;
    font-weight: 560;
}

.korea-heat,
.korea-os-heatmap-cell {
    display: inline-grid !important;
    grid-template-columns: auto auto;
    align-items: center;
    justify-content: center;
    column-gap: 6px;
    min-width: 78px;
    min-height: 34px;
    border-radius: 10px !important;
    padding: 6px 8px !important;
    color: var(--kos-text-on-accent) !important;
    font-family: var(--kos-font-num) !important;
    font-weight: 830 !important;
    line-height: 1.05 !important;
    box-shadow: inset 0 1px 0 rgba(253,253,255,0.16);
}

.korea-heat strong,
.korea-os-heatmap-cell strong {
    color: inherit !important;
    font-size: 15px !important;
    font-weight: 850 !important;
}

.korea-heat small,
.korea-os-heatmap-cell small {
    color: rgba(253,253,255,0.92) !important;
    font-family: var(--kos-font) !important;
    font-size: 11.3px !important;
    font-weight: 740 !important;
}

.heatmap-risk { background: linear-gradient(180deg, rgba(59, 130, 246, 0.92), rgba(30, 64, 175, 0.86)) !important; }
.heatmap-weak { background: linear-gradient(180deg, rgba(245, 158, 11, 0.90), rgba(120, 53, 15, 0.84)) !important; color: #FFF7ED !important; }
.heatmap-neutral { background: linear-gradient(180deg, rgba(71, 85, 105, 0.92), rgba(51, 65, 85, 0.86)) !important; }
.heatmap-good { background: linear-gradient(180deg, rgba(255, 122, 122, 0.90), rgba(190, 18, 60, 0.82)) !important; }
.heatmap-strong { background: linear-gradient(180deg, rgba(255, 77, 79, 0.94), rgba(159, 18, 57, 0.86)) !important; }
.heatmap-empty { background: rgba(85, 98, 118, 0.80) !important; }

.korea-legend {
    display: flex !important;
    flex-wrap: wrap;
    gap: 8px;
    margin: 0 0 12px 0 !important;
}

.korea-legend span {
    display: inline-flex;
    align-items: center;
    min-height: 29px;
    border-radius: 999px;
    padding: 6px 10px;
    color: var(--kos-text-secondary) !important;
    background: rgba(16, 24, 39, 0.74) !important;
    border: 1px solid var(--kos-border-subtle) !important;
    font-size: 12px;
    font-weight: 720;
}

.tone-good,
.market-up,
.market-return-positive,
.market-delta-positive { color: var(--kos-market-up) !important; }
.tone-risk,
.market-down,
.market-return-negative,
.market-delta-negative { color: var(--kos-market-down) !important; }
.tone-warn { color: var(--kos-warning) !important; }
.tone-info { color: var(--kos-accent-3) !important; }
.risk-critical { color: var(--kos-risk-critical) !important; }
.risk-warning { color: var(--kos-risk-warning) !important; }
.risk-info { color: var(--stance-info) !important; }
.korea-flow-pos { color: var(--kos-market-up) !important; font-family: var(--kos-font-num); font-weight: 760; }
.korea-flow-neg { color: var(--kos-market-down) !important; font-family: var(--kos-font-num); font-weight: 760; }
.korea-flow-flat { color: var(--kos-neutral-text) !important; font-family: var(--kos-font-num); font-weight: 720; }

.korea-os-step-row,
.korea-os-scenario-row,
.korea-os-alert-row,
.korea-os-review-row {
    background: rgba(15, 23, 42, 0.58) !important;
    border: 1px solid var(--kos-border-subtle) !important;
    border-radius: 11px !important;
}

.korea-os-step-num {
    color: var(--kos-text-on-accent) !important;
    background: linear-gradient(180deg, var(--kos-accent-2), var(--kos-accent)) !important;
}

.korea-os-reason {
    color: var(--kos-text-secondary) !important;
    line-height: 1.45 !important;
}

.korea-os-thesis {
    border: 1px solid var(--kos-border-subtle) !important;
    background: rgba(15, 23, 42, 0.58) !important;
}

.korea-os-thesis b {
    color: var(--kos-text-tertiary) !important;
}

.korea-os-thesis span {
    color: var(--kos-text-primary) !important;
}

.korea-os-nav {
    gap: 7px !important;
}

.korea-os-nav a {
    text-decoration: none !important;
}

.korea-os-nav a:hover,
.korea-mini-link:hover {
    color: var(--kos-text-on-accent) !important;
    border-color: var(--kos-border-strong) !important;
    background: rgba(139, 92, 246, 0.22) !important;
}

.korea-card code,
.korea-os-card code {
    color: var(--kos-warning-text) !important;
    background: rgba(2, 6, 23, 0.34);
    border: 1px solid var(--kos-border-subtle);
    border-radius: 6px;
    padding: 2px 5px;
    font-family: var(--kos-font-code);
    font-size: 11.5px;
}

/* Final visual polish: preserve Korean line quality while protecting wide finance data. */
.stApp,
.stApp p,
.stApp li,
.stApp label,
.stApp button,
.stApp input,
.stApp textarea,
.portfolio-intelligence-shell,
.portfolio-intelligence-shell *,
.korea-os-theme,
.korea-os-theme *,
.korea-os-shell,
.korea-os-shell *,
.korea-card,
.korea-card *,
.korea-table,
.korea-table *,
.command-table,
.command-table * {
    line-height: 1.5;
    word-break: keep-all;
    overflow-wrap: normal;
    text-wrap: pretty;
}

.stApp code,
.stApp pre,
.stApp a,
.stApp input,
.stApp textarea,
.stApp [data-baseweb="tag"],
.stApp [data-baseweb="popover"],
.portfolio-intelligence-shell code,
.portfolio-intelligence-shell small,
.portfolio-intelligence-shell .pi-rebalance-impact,
.portfolio-intelligence-shell .pi-signal-code,
.portfolio-intelligence-shell .pi-holding-symbol,
.korea-card code,
.korea-os-card code,
.korea-table td,
.korea-os-table td,
.command-table td,
.korea-context-meta,
.korea-os-muted {
    overflow-wrap: anywhere;
}

.stApp [data-testid="stMarkdownContainer"] p > code {
    display: inline-block;
    max-width: 100%;
    white-space: nowrap !important;
    overflow-x: auto;
    vertical-align: baseline;
    color: var(--kos-info-text) !important;
    background: rgba(15, 23, 42, 0.82) !important;
    border: 1px solid var(--kos-border-subtle);
    border-radius: 6px;
    padding: 1px 5px;
    font-family: var(--kos-font-code) !important;
    font-size: 12px !important;
    line-height: 1.35 !important;
}

.portfolio-intelligence-shell,
.korea-os-shell,
.portfolio-shell.korea-shell,
.korea-card,
.korea-os-card,
.pi-card,
.metric-card,
.insight-panel,
.signal-box {
    min-width: 0;
    max-width: 100%;
}

.portfolio-intelligence-grid,
.pi-detail-grid,
.korea-os-grid,
.korea-metric-grid,
.korea-os-metrics,
.korea-os-metrics.three {
    min-width: 0;
}

.pi-card,
.korea-card,
.korea-os-card {
    display: flex;
    flex-direction: column;
    min-width: 0;
}

.pi-card-body,
.korea-os-card-body,
.korea-card-body {
    flex: 1 1 auto;
    min-width: 0;
    overflow-x: auto;
    overscroll-behavior-x: contain;
    -webkit-overflow-scrolling: touch;
}

.pi-card-header,
.portfolio-intelligence-title,
.korea-os-card-head,
.korea-card-head,
.korea-os-hero,
.korea-module-title,
.korea-os-section-header {
    min-width: 0;
    flex-wrap: wrap;
}

.pi-card-header > *,
.portfolio-intelligence-title > *,
.korea-os-card-head > *,
.korea-card-head > *,
.korea-os-hero > *,
.korea-module-title > *,
.korea-os-section-header > * {
    min-width: 0;
}

.pi-card-header strong,
.portfolio-intelligence-title strong,
.korea-card-title,
.korea-os-card-title,
.korea-os-label,
.korea-module-title strong,
.korea-os-section-header strong {
    line-height: 1.35 !important;
}

.pi-card-header span,
.portfolio-intelligence-title span,
.pi-rebalance-reason,
.pi-rebalance-impact,
.pi-insight-text,
.korea-card-subtitle,
.korea-os-card-desc,
.korea-os-reason,
.korea-os-muted,
.korea-evidence,
.korea-empty {
    line-height: 1.55 !important;
}

.pi-badge,
.pi-signal-badge,
.korea-badge,
.korea-os-score,
.korea-factor-cell,
.korea-mini-link,
.korea-filter-chip,
.korea-legend span {
    align-items: center !important;
    justify-content: center !important;
    min-height: 28px !important;
    padding: 6px 10px !important;
    line-height: 1.25 !important;
    font-size: max(12px, 0.75rem) !important;
    white-space: normal !important;
    text-align: center !important;
}

.pi-rebalance-top,
.pi-rebalance-bottom,
.pi-benchmark-strip {
    min-width: 0;
}

.pi-rebalance-amount,
.pi-metric-value,
.pi-health-score strong,
.pi-holding-weight,
.pi-signal-change,
.metric-value,
.korea-score,
.korea-os-score,
.korea-metric strong,
.korea-os-metric strong,
.korea-table .num,
.korea-os-table .num,
.command-table .num,
.command-table td:nth-child(n+3),
.command-table th:nth-child(n+3) {
    font-family: var(--kos-font-num) !important;
    font-variant-numeric: tabular-nums;
}

.command-table {
    display: block;
    width: 100%;
    max-width: 100%;
    overflow-x: auto;
    overscroll-behavior-x: contain;
    -webkit-overflow-scrolling: touch;
    border-collapse: separate;
    border-spacing: 0;
}

.command-table th,
.command-table td {
    min-width: 96px;
    vertical-align: middle;
}

.command-table th:first-child,
.command-table td:first-child {
    min-width: 136px;
}

.command-table td:nth-child(n+3),
.command-table th:nth-child(n+3),
.korea-table td.num,
.korea-table th.num,
.korea-os-table td.num,
.korea-os-table th.num {
    text-align: right !important;
}

.korea-table-wrap,
.korea-os-table-wrap,
.stApp [data-testid="stDataFrame"],
.stApp [data-testid="stTable"],
.stApp [data-testid="stPyplot"] {
    max-width: 100%;
    overflow-x: auto !important;
    overflow-y: visible;
    overscroll-behavior-x: contain;
    -webkit-overflow-scrolling: touch;
}

.stApp [data-testid="stPyplot"] img,
.stApp [data-testid="stImage"] img,
.stApp canvas,
.stApp svg {
    max-width: 100% !important;
    height: auto !important;
}

.stApp [data-baseweb="popover"],
.stApp [data-baseweb="menu"],
.stApp [role="listbox"],
.stApp [data-testid="stTooltipContent"] {
    z-index: 999999 !important;
    max-width: min(420px, calc(100vw - 24px)) !important;
    overflow-wrap: anywhere !important;
    white-space: normal !important;
}

.stApp [data-baseweb="tooltip"],
.stApp [role="tooltip"] {
    z-index: 1000000 !important;
    max-width: min(420px, calc(100vw - 24px)) !important;
    color: var(--kos-text-primary) !important;
    background: var(--kos-card-bg-elevated) !important;
    border: 1px solid var(--kos-border-default) !important;
    border-radius: 10px !important;
    line-height: 1.5 !important;
    white-space: normal !important;
}

.stApp button,
.stApp [role="button"],
.stApp [data-testid="stButton"] button,
.stApp [data-testid="stDownloadButton"] button,
.stApp [data-testid="baseButton-secondary"],
.stApp [data-testid="baseButton-primary"] {
    min-height: 38px;
    padding: 8px 12px !important;
    line-height: 1.35 !important;
    white-space: normal !important;
    overflow: visible !important;
}

.stApp [data-testid="stTextInput"] input,
.stApp [data-testid="stNumberInput"] input,
.stApp [data-testid="stTextArea"] textarea,
.stApp [data-baseweb="select"] > div {
    min-height: 38px;
    color: var(--kos-text-primary) !important;
    background: rgba(15, 23, 42, 0.82) !important;
    border-color: var(--kos-border-default) !important;
}

.stApp [data-testid="stNumberInput"] button,
.stApp [data-testid="stNumberInput"] [role="button"] {
    min-width: 32px !important;
    color: var(--kos-text-secondary) !important;
    background: rgba(23, 32, 51, 0.96) !important;
    border: 1px solid var(--kos-border-default) !important;
    box-shadow: none !important;
}

.stApp [data-testid="stNumberInput"] button:hover,
.stApp [data-testid="stNumberInput"] [role="button"]:hover {
    color: var(--kos-text-primary) !important;
    background: rgba(56, 189, 248, 0.14) !important;
    border-color: rgba(56, 189, 248, 0.38) !important;
}

.stApp [role="radiogroup"],
.stApp [data-testid="stHorizontalBlock"] {
    min-width: 0;
}

.stApp [role="radiogroup"] {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.stApp [role="radiogroup"] button[data-testid*="segmented_control"] {
    flex: 1 1 110px;
    width: auto !important;
    min-width: 88px;
    min-height: 40px;
    color: var(--stance-text-secondary) !important;
    background: var(--stance-card-bg-soft) !important;
    border: 1px solid var(--stance-border-default) !important;
    border-radius: 8px !important;
    box-shadow: none !important;
}

.stApp [role="radiogroup"] button[data-testid*="segmented_control"] p,
.stApp [role="radiogroup"] button[data-testid*="segmented_control"] span,
.stApp [role="radiogroup"] button[data-testid*="segmented_control"] div {
    color: var(--stance-text-secondary) !important;
    font-weight: 720 !important;
}

.stApp [role="radiogroup"] button[data-testid*="segmented_control"]:hover {
    color: var(--stance-text-primary) !important;
    background: var(--stance-surface-elevated) !important;
    border-color: rgba(167, 139, 250, 0.52) !important;
}

.stApp [role="radiogroup"] button[data-testid="stBaseButton-segmented_controlActive"] {
    color: var(--stance-text-primary) !important;
    background: rgba(139, 92, 246, 0.20) !important;
    border-color: #A78BFA !important;
}

.stApp [role="radiogroup"] button[data-testid="stBaseButton-segmented_controlActive"] p,
.stApp [role="radiogroup"] button[data-testid="stBaseButton-segmented_controlActive"] span,
.stApp [role="radiogroup"] button[data-testid="stBaseButton-segmented_controlActive"] div {
    color: var(--stance-text-primary) !important;
}

.stApp [role="radiogroup"] button[data-testid*="segmented_control"]:focus-visible {
    outline: 2px solid var(--stance-focus-ring) !important;
    outline-offset: 2px !important;
}

.stApp [role="radiogroup"] label {
    min-width: 0;
    max-width: 100%;
    padding: 6px 11px !important;
}

.stance-sr-only {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    padding: 0 !important;
    margin: -1px !important;
    overflow: hidden !important;
    clip: rect(0, 0, 0, 0) !important;
    white-space: nowrap !important;
    border: 0 !important;
}

.st-key-main_view_selector [role="radiogroup"] {
    display: grid !important;
    grid-template-columns: repeat(9, minmax(0, 1fr));
    gap: 8px;
}

.st-key-main_view_selector [role="radiogroup"] button[data-testid*="segmented_control"] {
    width: 100% !important;
    min-width: 0 !important;
}

.st-key-main_view_selector [role="radiogroup"] button[data-testid*="segmented_control"] p,
.st-key-main_view_selector [role="radiogroup"] button[data-testid*="segmented_control"] span {
    overflow-wrap: anywhere;
    word-break: keep-all;
}

@media (max-width: 1280px) {
    .st-key-main_view_selector [role="radiogroup"] {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }
}

@media (max-width: 768px) {
    .stApp [role="radiogroup"] button[data-testid*="segmented_control"] {
        flex: 1 1 calc(33.333% - 8px);
        min-width: 96px;
        padding: 7px 8px !important;
    }
}

@media (max-width: 420px) {
    .stApp [role="radiogroup"] button[data-testid*="segmented_control"] {
        min-width: 92px;
        font-size: 12.5px !important;
    }
}

.stApp [data-testid="stTabs"] [role="tablist"] {
    align-items: stretch !important;
}

.stApp [data-testid="stTabs"] button {
    height: auto !important;
    min-height: 46px !important;
    padding: 9px 12px !important;
    line-height: 1.35 !important;
    align-items: center !important;
    overflow: visible !important;
}

.stApp [data-testid="stTabs"] button p,
.stApp [data-testid="stTabs"] button span {
    line-height: 1.35 !important;
    white-space: normal !important;
}

.stApp [data-testid="stSkeleton"],
.stApp [data-testid="stSpinner"],
.stApp .stSkeleton {
    background: linear-gradient(90deg, rgba(148,163,184,0.16), rgba(248,250,252,0.12), rgba(148,163,184,0.16)) !important;
    border-radius: 10px !important;
    min-height: 16px;
}

.korea-empty,
.pi-rebalance-item,
.stApp [data-testid="stAlert"] {
    color: var(--kos-text-secondary) !important;
}

.portfolio-intelligence-shell .pi-signal-row,
.portfolio-intelligence-shell .pi-allocation-row,
.portfolio-intelligence-shell .pi-rebalance-item {
    overflow: visible !important;
}

@media (max-width: 900px) {
    .korea-os-theme .korea-module-title,
    .korea-os-section-header {
        flex-direction: column;
        align-items: stretch;
    }
    .korea-os-grid,
    .korea-hero-metrics,
    .korea-os-metrics,
    .korea-module-health-grid {
        grid-template-columns: 1fr !important;
    }
}

@media (max-width: 560px) {
    .korea-os-theme .korea-card,
    .korea-os-card,
    .korea-explanation-panel,
    .fear-greed-panel {
        padding: 12px !important;
    }
    .portfolio-intelligence-title,
    .pi-card-header,
    .pi-rebalance-top,
    .pi-rebalance-bottom,
    .korea-os-card-head,
    .korea-card-head,
    .korea-os-hero {
        flex-direction: column !important;
        align-items: stretch !important;
    }
    .portfolio-intelligence-shell .pi-signal-row {
        grid-template-columns: 1fr !important;
        gap: 8px !important;
    }
    .portfolio-intelligence-shell .pi-signal-row > div,
    .portfolio-intelligence-shell .pi-signal-row .pi-signal-name,
    .portfolio-intelligence-shell .pi-signal-row .pi-signal-badge {
        grid-column: 1 / -1 !important;
        text-align: left !important;
        white-space: normal !important;
    }
    .portfolio-intelligence-shell .pi-signal-change {
        text-align: left !important;
    }
    .pi-card-body,
    .korea-os-card-body,
    .korea-card-body {
        padding: 13px !important;
    }
    .korea-os-table,
    .korea-table {
        min-width: 720px;
        font-size: 12.5px !important;
    }
    .korea-evidence {
        min-width: 180px;
    }
}

@media (prefers-reduced-motion: reduce) {
    .korea-os-theme *,
    .korea-os-shell *,
    .korea-card * {
        transition: none !important;
        animation: none !important;
    }
}
</style>
"""


def inject_korea_os_theme() -> None:
    """Inject the final scoped typography/readability layer for Korea OS UI."""
    st.markdown(KOREA_OS_CSS, unsafe_allow_html=True)
