from __future__ import annotations


KOREA_MODULE_VISUAL_REGISTRY: tuple[dict[str, str], ...] = (
    {"key": "investmentAlgorithm", "label": "투자검토 알고리즘", "group": "Decision"},
    {"key": "factorHeatmap", "label": "팩터 히트맵", "group": "Evidence"},
    {"key": "supplyDemandRadar", "label": "수급 레이더", "group": "Evidence"},
    {"key": "disclosureRadar", "label": "공시·이벤트 레이더", "group": "Events"},
    {"key": "valueUpRadar", "label": "밸류업 레이더", "group": "Events"},
    {"key": "backtestAccuracy", "label": "예측 정확도·백테스트", "group": "Validation"},
    {"key": "portfolioReviewQueue", "label": "포트폴리오 검토 큐", "group": "Workflow"},
    {"key": "advancedModuleSummary", "label": "고도화 모듈 요약", "group": "Operations"},
    {"key": "fearGreedIndex", "label": "공포·탐욕 지수", "group": "Decision"},
    {"key": "candleVolumeChart", "label": "최근 60거래일 캔들 + 거래량", "group": "Price"},
    {"key": "decisionFlow", "label": "의사결정 흐름", "group": "Decision OS"},
    {"key": "signalConflictMatrix", "label": "신호 충돌 매트릭스", "group": "Decision OS"},
    {"key": "positionSizingRiskBudget", "label": "포지션 리스크 예산", "group": "Decision OS"},
    {"key": "scenarioStressTest", "label": "시나리오 스트레스 테스트", "group": "Decision OS"},
    {"key": "investmentThesisTracker", "label": "투자 가설 트래커", "group": "Decision OS"},
    {"key": "catalystEventCalendar", "label": "촉매·이벤트 캘린더", "group": "Decision OS"},
    {"key": "predictionCalibration", "label": "예측 검증·캘리브레이션", "group": "Decision OS"},
    {"key": "riskAlertRules", "label": "리스크 알림 규칙", "group": "Decision OS"},
    {"key": "similarCaseLibrary", "label": "유사 사례 라이브러리", "group": "Decision OS"},
    {"key": "postReviewNotebook", "label": "사후 리뷰 노트", "group": "Decision OS"},
)

KOREA_DASHBOARD_TOKENS = {
    "surface_page": "#070b1a",
    "surface_card": "rgba(15, 23, 42, 0.92)",
    "surface_elevated": "rgba(24, 31, 52, 0.96)",
    "surface_hover": "rgba(49, 46, 129, 0.30)",
    "surface_selected": "rgba(88, 28, 135, 0.38)",
    "border_default": "rgba(196, 181, 253, 0.24)",
    "border_strong": "rgba(216, 180, 254, 0.42)",
    "border_selected": "rgba(167, 139, 250, 0.95)",
    "text_primary": "#f8fafc",
    "text_secondary": "#dbeafe",
    "text_muted": "#cbd5e1",
    "text_subtle": "#a8b5cf",
    "positive": "#34d399",
    "positive_soft": "rgba(16, 185, 129, 0.16)",
    "risk": "#fb7185",
    "risk_soft": "rgba(244, 63, 94, 0.16)",
    "caution": "#fbbf24",
    "caution_soft": "rgba(245, 158, 11, 0.17)",
    "info": "#38bdf8",
    "info_soft": "rgba(56, 189, 248, 0.16)",
    "purple": "#a78bfa",
    "purple_soft": "rgba(139, 92, 246, 0.18)",
}

KOREA_DASHBOARD_VISIBILITY_CSS = """
<style>
:root {
    --korea-bg: #070b1a;
    --korea-card: rgba(15, 23, 42, 0.92);
    --korea-card-2: rgba(24, 31, 52, 0.96);
    --korea-hover: rgba(49, 46, 129, 0.30);
    --korea-selected: rgba(88, 28, 135, 0.38);
    --korea-border: rgba(196, 181, 253, 0.24);
    --korea-border-strong: rgba(216, 180, 254, 0.42);
    --korea-focus: rgba(167, 139, 250, 0.95);
    --korea-text: #f8fafc;
    --korea-text-2: #dbeafe;
    --korea-muted: #cbd5e1;
    --korea-subtle: #a8b5cf;
    --korea-positive: #34d399;
    --korea-risk: #fb7185;
    --korea-caution: #fbbf24;
    --korea-info: #38bdf8;
    --korea-purple: #a78bfa;
}
html,
body,
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.block-container {
    max-width: 100vw !important;
    overflow-x: hidden !important;
}
.stApp {
    background:
        radial-gradient(circle at 8% 0%, rgba(139, 92, 246, 0.20), transparent 24%),
        radial-gradient(circle at 88% 12%, rgba(14, 165, 233, 0.11), transparent 23%),
        linear-gradient(135deg, #070b1a 0%, #0f172a 54%, #1e1236 100%) !important;
}
[data-testid="stHeader"] {
    background: rgba(7, 11, 26, 0.72) !important;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #090e1b, #0f172a) !important;
}
.portfolio-shell.korea-shell,
.portfolio-shell.korea-shell.korea-os-theme {
    background:
        radial-gradient(circle at 8% 0%, rgba(139, 92, 246, 0.26), transparent 24%),
        radial-gradient(circle at 88% 12%, rgba(14, 165, 233, 0.16), transparent 23%),
        linear-gradient(135deg, #070b1a 0%, #111827 52%, #1e1236 100%);
    border-color: var(--korea-border) !important;
    color: var(--korea-text) !important;
    max-width: 100% !important;
    overflow-x: hidden !important;
}
.portfolio-title,
.hero-title,
.korea-module-title strong,
.korea-card-title,
.korea-os-card-title {
    color: var(--korea-text) !important;
    letter-spacing: 0 !important;
}
.portfolio-subtitle,
.small-note,
.korea-card-subtitle,
.korea-evidence,
.korea-explain-muted,
.korea-context-meta {
    color: var(--korea-muted) !important;
    line-height: 1.55 !important;
}
.korea-card,
.korea-os-card,
.korea-context-bar,
.korea-explanation-panel,
.fear-greed-panel,
.korea-decision-card,
.korea-module-health-card,
.korea-os-thesis,
.korea-info-callout,
.korea-safety-callout {
    background: linear-gradient(180deg, rgba(24,31,52,.96), rgba(15,23,42,.94)) !important;
    border: 1px solid var(--korea-border) !important;
    border-radius: 14px !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.055), 0 16px 36px rgba(2,6,23,.24) !important;
    color: var(--korea-text) !important;
}
.korea-module-title,
.korea-os-section-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 14px;
    border-radius: 14px;
    padding: 15px 16px;
    margin: 24px 0 12px;
    background: linear-gradient(180deg, rgba(24,31,52,.94), rgba(15,23,42,.76));
    border: 1px solid rgba(196,181,253,.18);
}
.korea-module-title strong {
    display: block;
    font-size: clamp(18px, 1.4vw, 21px) !important;
    font-weight: 820 !important;
    line-height: 1.2 !important;
}
.korea-module-title span {
    display: block;
    margin-top: 5px;
    color: var(--korea-muted) !important;
    font-size: 13.5px !important;
    line-height: 1.5 !important;
}
.korea-filter-summary {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin: 10px 0 12px;
    padding: 11px 12px;
    color: #bae6fd;
    background: linear-gradient(180deg, rgba(56,189,248,.12), rgba(139,92,246,.08));
    border: 1px solid rgba(56,189,248,.22);
    border-radius: 12px;
}
.korea-filter-chip {
    display: inline-flex;
    align-items: center;
    min-height: 28px;
    border-radius: 999px;
    padding: 5px 10px;
    color: var(--korea-muted);
    background: rgba(15,23,42,.62);
    border: 1px solid rgba(148,163,184,.16);
    font-size: 12px;
    font-weight: 700;
}
.korea-table-wrap,
.korea-os-table-wrap {
    width: 100% !important;
    max-width: 100% !important;
    overflow-x: auto !important;
    overflow-y: hidden !important;
    border-radius: 13px !important;
    border: 1px solid rgba(196,181,253,.16) !important;
    -webkit-overflow-scrolling: touch;
}
.korea-table,
.korea-os-table {
    width: 100% !important;
    min-width: 720px !important;
    border-collapse: separate !important;
    border-spacing: 0 !important;
    color: var(--korea-text) !important;
    font-size: 13px !important;
    line-height: 1.42 !important;
}
.korea-table th,
.korea-os-table th {
    position: sticky;
    top: 0;
    z-index: 3;
    padding: 11px 12px !important;
    color: var(--korea-muted) !important;
    background: rgba(15,23,42,.98) !important;
    border-bottom: 1px solid rgba(196,181,253,.18) !important;
    font-size: 12.2px !important;
    font-weight: 780 !important;
    text-align: left;
    white-space: nowrap;
}
.korea-table td,
.korea-os-table td {
    padding: 10px 12px !important;
    color: var(--korea-text) !important;
    background: rgba(15,23,42,.56) !important;
    border-bottom: 1px solid rgba(148,163,184,.13) !important;
    vertical-align: middle !important;
}
.korea-table tbody tr:nth-child(even) td,
.korea-os-table tbody tr:nth-child(even) td {
    background: rgba(24,31,52,.55) !important;
}
.korea-table tbody tr:hover td,
.korea-os-table tbody tr:hover td {
    background: rgba(49,46,129,.34) !important;
}
.korea-table td:first-child,
.korea-table th:first-child,
.korea-os-table td:first-child,
.korea-os-table th:first-child {
    position: sticky;
    left: 0;
    z-index: 2;
}
.korea-table th:first-child,
.korea-os-table th:first-child {
    z-index: 4;
}
.korea-table td:first-child,
.korea-os-table td:first-child {
    background: rgba(15,23,42,.98) !important;
}
.korea-table .muted,
.korea-stock-cell span,
.korea-card .muted {
    display: block;
    margin-top: 3px;
    color: var(--korea-subtle) !important;
    font-size: 12px !important;
    font-weight: 560 !important;
}
.korea-stock-cell {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 116px;
}
.korea-stock-cell strong,
.korea-table td:first-child strong {
    color: var(--korea-text) !important;
    font-size: 13.5px !important;
    font-weight: 780 !important;
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
    font-weight: 780 !important;
    line-height: 1.05 !important;
    white-space: nowrap;
    letter-spacing: 0 !important;
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
    color: #fff !important;
    font-weight: 850 !important;
    box-shadow: inset 0 1px 0 rgba(253,253,255,.16);
}
.korea-heat strong,
.korea-os-heatmap-cell strong {
    color: inherit !important;
    font-size: 15px !important;
    font-weight: 880 !important;
}
.korea-heat small,
.korea-os-heatmap-cell small {
    color: rgba(255,255,255,.92) !important;
    font-size: 11.3px !important;
    font-weight: 760 !important;
}
.heatmap-risk { background: linear-gradient(180deg, rgba(244,63,94,.90), rgba(127,29,29,.84)) !important; }
.heatmap-weak { background: linear-gradient(180deg, rgba(245,158,11,.90), rgba(120,53,15,.84)) !important; color: #fff7ed !important; }
.heatmap-neutral { background: linear-gradient(180deg, rgba(71,85,105,.92), rgba(51,65,85,.86)) !important; }
.heatmap-good { background: linear-gradient(180deg, rgba(56,189,248,.86), rgba(30,64,175,.82)) !important; }
.heatmap-strong { background: linear-gradient(180deg, rgba(34,197,94,.86), rgba(88,28,135,.80)) !important; }
.heatmap-empty { background: rgba(85,98,118,.80) !important; }
.korea-flow-pos { color: #86efac !important; font-weight: 780; }
.korea-flow-neg { color: #fda4af !important; font-weight: 780; }
.korea-flow-flat { color: var(--korea-muted) !important; font-weight: 720; }
.korea-score-hero {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 14px;
    align-items: center;
}
.korea-score-hero strong,
.fear-greed-value strong {
    color: #fff !important;
    font-variant-numeric: tabular-nums;
    font-weight: 950 !important;
}
.fear-greed-value {
    display: flex;
    align-items: baseline;
    gap: 8px;
    color: #fff;
}
.fear-greed-value strong {
    font-size: 2.45rem;
    line-height: 1;
}
.fear-greed-segments {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 4px;
    margin: 12px 0 8px;
}
.fear-greed-segments span {
    min-height: 11px;
    border-radius: 999px;
    opacity: .78;
}
.fg-extreme-fear { background: #ef4444; }
.fg-fear { background: #f97316; }
.fg-neutral { background: #64748b; }
.fg-greed { background: #a3e635; }
.fg-extreme-greed { background: #22c55e; }
.stButton > button {
    border-radius: 10px !important;
    min-height: 38px;
    border: 1px solid rgba(196,181,253,.22) !important;
    background: rgba(30,41,59,.72) !important;
    color: var(--korea-text) !important;
    font-weight: 850 !important;
    letter-spacing: 0 !important;
}
.stButton > button:hover {
    border-color: rgba(167,139,250,.82) !important;
    background: rgba(76,29,149,.38) !important;
    color: #fff !important;
}
.stButton > button:focus {
    outline: 2px solid rgba(167,139,250,.95) !important;
    outline-offset: 2px;
}
.stDataFrame,
.stTable {
    max-width: 100% !important;
    overflow-x: auto !important;
}
@media (max-width: 900px) {
    .korea-decision-card,
    .korea-module-health-grid,
    .korea-os-grid,
    .korea-os-metrics {
        grid-template-columns: 1fr !important;
    }
    .korea-hero-metrics {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    }
    .korea-module-title,
    .korea-os-section-header {
        flex-direction: column;
        align-items: stretch;
    }
}
@media (max-width: 560px) {
    .block-container {
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
    }
    .korea-card,
    .korea-context-bar,
    .korea-explanation-panel,
    .fear-greed-panel {
        padding: 13px !important;
    }
    .korea-table,
    .korea-os-table {
        min-width: 680px !important;
        font-size: 12.5px !important;
    }
    .korea-hero-metrics,
    .fear-greed-segments {
        grid-template-columns: 1fr !important;
    }
    .korea-score-hero strong {
        font-size: 2.7rem !important;
    }
}
</style>
"""
