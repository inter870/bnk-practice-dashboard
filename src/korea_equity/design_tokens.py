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
    "surface_page": "#05070D",
    "surface_card": "#0B1020",
    "surface_elevated": "#172033",
    "surface_hover": "rgba(49, 46, 129, 0.30)",
    "surface_selected": "rgba(88, 28, 135, 0.38)",
    "border_default": "rgba(148, 163, 184, 0.28)",
    "border_strong": "rgba(216, 180, 254, 0.42)",
    "border_selected": "rgba(167, 139, 250, 0.95)",
    "text_primary": "#F8FAFC",
    "text_secondary": "#E5E7EB",
    "text_muted": "#CBD5E1",
    "text_subtle": "#94A3B8",
    "positive": "#4ADE80",
    "positive_soft": "rgba(16, 185, 129, 0.16)",
    "risk": "#FB7185",
    "risk_soft": "rgba(244, 63, 94, 0.16)",
    "market_up": "#FF4D4F",
    "market_up_soft": "rgba(255, 77, 79, 0.12)",
    "market_down": "#3B82F6",
    "market_down_soft": "rgba(59, 130, 246, 0.12)",
    "market_flat": "#CBD5E1",
    "risk_critical": "#F97316",
    "risk_critical_soft": "rgba(249, 115, 22, 0.14)",
    "caution": "#FCD34D",
    "caution_soft": "rgba(245, 158, 11, 0.17)",
    "info": "#38BDF8",
    "info_soft": "rgba(56, 189, 248, 0.16)",
    "purple": "#A78BFA",
    "purple_soft": "rgba(139, 92, 246, 0.18)",
}

KOREA_DASHBOARD_VISIBILITY_CSS = """
<style>
:root {
    --korea-bg: #05070D;
    --korea-card: #0B1020;
    --korea-card-2: #172033;
    --korea-hover: rgba(49, 46, 129, 0.30);
    --korea-selected: rgba(88, 28, 135, 0.38);
    --korea-border: rgba(148, 163, 184, 0.28);
    --korea-border-strong: rgba(216, 180, 254, 0.42);
    --korea-focus: rgba(167, 139, 250, 0.95);
    --korea-text: #F8FAFC;
    --korea-text-2: #E5E7EB;
    --korea-muted: #CBD5E1;
    --korea-subtle: #94A3B8;
    --korea-positive: #4ADE80;
    --korea-risk: #FB7185;
    --korea-market-up: #FF4D4F;
    --korea-market-up-soft: rgba(255, 77, 79, 0.12);
    --korea-market-down: #3B82F6;
    --korea-market-down-soft: rgba(59, 130, 246, 0.12);
    --korea-market-flat: #CBD5E1;
    --korea-risk-critical: #F97316;
    --korea-caution: #FCD34D;
    --korea-info: #38BDF8;
    --korea-purple: #A78BFA;
}
.portfolio-shell.korea-shell {
    background:
        radial-gradient(circle at 8% 0%, rgba(139, 92, 246, 0.28), transparent 24%),
        radial-gradient(circle at 88% 12%, rgba(14, 165, 233, 0.16), transparent 23%),
        linear-gradient(135deg, #070b1a 0%, #111827 52%, #1e1236 100%);
    border-color: var(--korea-border);
}
.korea-module-title {
    padding-top: 4px;
    margin: 22px 0 10px 0;
}
.korea-module-title strong {
    color: var(--korea-text);
    font-size: 1.08rem;
    letter-spacing: 0;
}
.korea-module-title span,
.korea-card-subtitle,
.korea-context-meta,
.korea-explain-muted,
.korea-evidence {
    color: var(--korea-muted);
}
.korea-module-meta {
    padding: 5px 10px;
    border-radius: 999px;
    background: rgba(139, 92, 246, 0.16);
    border: 1px solid rgba(196, 181, 253, 0.22);
    color: #ddd6fe;
}
.korea-card,
.korea-context-bar,
.korea-explanation-panel,
.fear-greed-panel {
    border-radius: 14px;
    background: linear-gradient(180deg, rgba(24, 31, 52, 0.98), rgba(15, 23, 42, 0.94));
    border: 1px solid var(--korea-border);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), 0 14px 34px rgba(2,6,23,0.26);
}
.korea-card {
    padding: 16px;
}
.korea-card.compact {
    padding: 14px;
}
.korea-card-head {
    padding-bottom: 10px;
    border-bottom: 1px solid rgba(196, 181, 253, 0.12);
}
.korea-card-title {
    color: #f5f3ff;
    font-size: 0.96rem;
    letter-spacing: 0;
}
.korea-score {
    color: var(--korea-text);
    font-size: 2rem;
    font-variant-numeric: tabular-nums;
}
.korea-badge {
    min-height: 25px;
    padding: 5px 10px;
    border: 1px solid rgba(255,255,255,0.10);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.10);
    font-size: 0.75rem;
    letter-spacing: 0;
}
.korea-badge.good { background: rgba(16, 185, 129, 0.22); color: #a7f3d0; border-color: rgba(52, 211, 153, 0.32); }
.korea-badge.info { background: rgba(56, 189, 248, 0.20); color: #bae6fd; border-color: rgba(56, 189, 248, 0.34); }
.korea-badge.warn { background: rgba(245, 158, 11, 0.22); color: #fde68a; border-color: rgba(251, 191, 36, 0.34); }
.korea-badge.risk { background: rgba(244, 63, 94, 0.22); color: #fecdd3; border-color: rgba(251, 113, 133, 0.36); }
.korea-badge.muted { background: rgba(100, 116, 139, 0.28); color: #e2e8f0; border-color: rgba(148, 163, 184, 0.28); }
.korea-table-wrap {
    border-color: rgba(196, 181, 253, 0.22);
    background: rgba(2, 6, 23, 0.20);
}
.korea-table {
    font-size: 0.82rem;
    font-variant-numeric: tabular-nums;
}
.korea-table th,
.korea-table td {
    padding: 11px 12px;
    border-bottom-color: rgba(148, 163, 184, 0.18);
}
.korea-table th {
    position: sticky;
    top: 0;
    color: #ddd6fe;
    font-size: 0.76rem;
    background: rgba(30, 41, 59, 0.96);
    z-index: 2;
}
.korea-table tbody tr:hover td {
    background: rgba(49, 46, 129, 0.20);
}
.korea-table td {
    color: #edf2ff;
}
.korea-table td .muted {
    color: #b6c3d7;
    font-size: 0.74rem;
}
.korea-evidence {
    font-size: 0.8rem;
    min-width: 240px;
}
.korea-empty {
    color: #dbeafe;
    border-color: rgba(196, 181, 253, 0.28);
    background: rgba(30, 41, 59, 0.66);
}
.korea-heat {
    display: inline-flex;
    flex-direction: row;
    align-items: center;
    justify-content: center;
    gap: 5px;
    min-width: 70px;
    min-height: 34px;
    border-radius: 10px;
    padding: 6px 8px;
    color: #fff;
    font-weight: 950;
    line-height: 1.05;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.12);
}
.korea-heat small {
    margin-top: 0;
    font-size: 0.68rem;
    color: rgba(255,255,255,0.90);
}
.heatmap-strong { background: linear-gradient(180deg, rgba(255,77,79,.96), rgba(159,18,57,.86)); }
.heatmap-good { background: linear-gradient(180deg, rgba(255,122,122,.92), rgba(190,18,60,.82)); }
.heatmap-neutral { background: linear-gradient(180deg, rgba(139,92,246,.88), rgba(109,40,217,.78)); }
.heatmap-weak { background: linear-gradient(180deg, rgba(245,158,11,.96), rgba(217,119,6,.84)); color: var(--stance-card-bg-soft); }
.heatmap-risk { background: linear-gradient(180deg, rgba(59,130,246,.96), rgba(30,64,175,.86)); }
.heatmap-empty { background: rgba(100,116,139,.86); }
.korea-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 0 0 10px 0;
}
.korea-legend span,
.korea-mini-link {
    min-height: 27px;
    font-size: 0.75rem;
    color: #f5f3ff;
    background: rgba(88, 28, 135, 0.48);
    border-color: rgba(196, 181, 253, 0.28);
}
.korea-selected-card,
.korea-row-card.selected {
    outline: 2px solid var(--korea-focus);
    box-shadow: 0 0 0 4px rgba(167,139,250,0.14), 0 18px 42px rgba(2,6,23,0.24);
}
.korea-decision-card {
    display: grid;
    grid-template-columns: minmax(170px, 0.86fr) minmax(260px, 1.6fr);
    gap: 14px;
    margin: 12px 0;
    border-radius: 14px;
    padding: 16px;
    background: linear-gradient(135deg, rgba(76, 29, 149, 0.40), rgba(15, 23, 42, 0.94));
    border: 1px solid var(--korea-border-strong);
}
.korea-score-hero {
    display: flex;
    flex-direction: column;
    justify-content: center;
    border-radius: 12px;
    padding: 14px;
    background: rgba(2, 6, 23, 0.28);
}
.korea-score-hero strong {
    font-size: 3.25rem;
    line-height: 0.95;
    color: #fff;
    font-weight: 950;
    font-variant-numeric: tabular-nums;
}
.korea-score-hero span {
    color: var(--korea-muted);
    font-weight: 850;
}
.korea-hero-metrics {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 8px;
}
.korea-metric-card,
.korea-metric {
    border-radius: 11px;
    padding: 10px 11px;
    background: rgba(30, 41, 59, 0.72);
    border: 1px solid rgba(196, 181, 253, 0.16);
}
.korea-metric-card small,
.korea-metric small {
    color: #cbd5e1;
    font-size: 0.75rem;
    font-weight: 850;
}
.korea-metric-card strong,
.korea-metric strong {
    color: #fff;
    font-size: 1.02rem;
    font-variant-numeric: tabular-nums;
}
.tone-good,
.market-up,
.market-return-positive { color: var(--korea-market-up) !important; }
.tone-risk,
.market-down,
.market-return-negative { color: var(--korea-market-down) !important; }
.tone-warn { color: var(--korea-caution) !important; }
.tone-info { color: var(--korea-info) !important; }
.risk-critical { color: var(--korea-risk-critical) !important; }
.risk-warning { color: var(--korea-caution) !important; }
.korea-flow-pos { color: var(--korea-market-up); font-weight: 900; }
.korea-flow-neg { color: var(--korea-market-down); font-weight: 900; }
.korea-flow-flat { color: var(--korea-muted); font-weight: 850; }
.korea-module-health-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
    margin-top: 10px;
}
.korea-module-health {
    border-radius: 12px;
    padding: 12px;
    background: rgba(30, 41, 59, 0.68);
    border: 1px solid rgba(196, 181, 253, 0.17);
}
.korea-module-health strong {
    display: block;
    color: #f8fafc;
    font-size: 0.86rem;
    margin-bottom: 5px;
}
.korea-module-health span {
    color: var(--korea-muted);
    font-size: 0.76rem;
    line-height: 1.45;
}
.fear-greed-gauge {
    border-radius: 14px;
    padding: 15px;
    margin-bottom: 10px;
    background: linear-gradient(180deg, rgba(24,31,52,.96), rgba(15,23,42,.94));
    border: 1px solid rgba(196,181,253,.22);
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
    font-weight: 950;
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
    opacity: .72;
}
.fg-extreme-fear { background: #ef4444; }
.fg-fear { background: #f97316; }
.fg-neutral { background: #64748b; }
.fg-greed { background: #a3e635; }
.fg-extreme-greed { background: #22c55e; }
.stButton > button {
    border-radius: 10px;
    min-height: 38px;
    border: 1px solid rgba(196,181,253,.22);
    background: rgba(30, 41, 59, 0.72);
    color: #f8fafc;
    font-weight: 850;
}
.stButton > button:hover {
    border-color: rgba(167,139,250,.82);
    background: rgba(76, 29, 149, 0.38);
    color: #fff;
}
.stButton > button:focus {
    outline: 2px solid rgba(167,139,250,.95);
    outline-offset: 2px;
}
@media (max-width: 900px) {
    .korea-decision-card,
    .korea-module-health-grid {
        grid-template-columns: 1fr;
    }
    .korea-hero-metrics {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}
@media (max-width: 560px) {
    .korea-card,
    .korea-context-bar,
    .korea-explanation-panel,
    .fear-greed-panel {
        padding: 13px;
    }
    .korea-table {
        min-width: 760px;
        font-size: 0.8rem;
    }
    .korea-hero-metrics,
    .fear-greed-segments {
        grid-template-columns: 1fr;
    }
    .korea-score-hero strong {
        font-size: 2.7rem;
    }
}
</style>
"""
