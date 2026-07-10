from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


ModuleKey = Literal[
    "investmentAlgorithm",
    "factorHeatmap",
    "supplyDemandRadar",
    "disclosureRadar",
    "valueUpRadar",
    "backtestAccuracy",
    "portfolioReviewQueue",
    "advancedModuleSummary",
    "fearGreedIndex",
    "candleVolumeChart",
    "decisionFlow",
    "signalConflictMatrix",
    "positionSizingRiskBudget",
    "scenarioStressTest",
    "investmentThesisTracker",
    "catalystEventCalendar",
    "predictionCalibration",
    "riskAlertRules",
    "similarCaseLibrary",
    "postReviewNotebook",
]

MetricKey = Literal[
    "totalScore",
    "recommendationGrade",
    "confidence",
    "expectedReturn3M",
    "downsideRisk",
    "momentumScore",
    "valueScore",
    "qualityScore",
    "earningsScore",
    "supplyDemandScore",
    "disclosureScore",
    "valueUpScore",
    "liquidityScore",
    "riskScore",
    "foreignNetBuy",
    "institutionNetBuy",
    "pensionNetBuy",
    "shortSellRisk",
    "pbr",
    "roe",
    "dividendYield",
    "cagr",
    "excessReturn",
    "mdd",
    "sharpe",
    "precisionAt10",
    "rankIC",
    "fearGreed",
    "decisionStage",
    "conflictCount",
    "positionBudget",
    "scenarioImpact",
    "thesisStatus",
    "catalystRisk",
    "calibrationHitRate",
    "riskAlert",
    "similarCaseWinRate",
    "postReviewRMultiple",
]

FactorKey = Literal[
    "momentum",
    "value",
    "quality",
    "earnings",
    "supplyDemand",
    "disclosure",
    "valueUp",
    "liquidity",
    "risk",
]


MODULE_LABELS: dict[str, str] = {
    "investmentAlgorithm": "투자검토 알고리즘",
    "factorHeatmap": "팩터 히트맵",
    "supplyDemandRadar": "수급 레이더",
    "disclosureRadar": "공시·이벤트 레이더",
    "valueUpRadar": "밸류업 레이더",
    "backtestAccuracy": "예측 정확도·백테스트",
    "portfolioReviewQueue": "포트폴리오 검토 큐",
    "advancedModuleSummary": "고도화 모듈 요약",
    "fearGreedIndex": "공포·탐욕 지수",
    "candleVolumeChart": "최근 60거래일 캔들 + 거래량",
    "decisionFlow": "의사결정 흐름",
    "signalConflictMatrix": "신호 충돌 매트릭스",
    "positionSizingRiskBudget": "포지션 리스크 예산",
    "scenarioStressTest": "시나리오 스트레스 테스트",
    "investmentThesisTracker": "투자 가설 트래커",
    "catalystEventCalendar": "촉매·이벤트 캘린더",
    "predictionCalibration": "예측 검증·캘리브레이션",
    "riskAlertRules": "리스크 알림 규칙",
    "similarCaseLibrary": "유사 사례 라이브러리",
    "postReviewNotebook": "사후 리뷰 노트",
}

MODULE_IDS: dict[str, str] = {
    key: key.replace("Risk", "-risk").replace("Test", "-test").replace("Matrix", "-matrix")
    for key in MODULE_LABELS
}
MODULE_IDS.update(
    {
        "investmentAlgorithm": "investment-algorithm",
        "factorHeatmap": "factor-heatmap",
        "supplyDemandRadar": "supply-demand-radar",
        "disclosureRadar": "disclosure-radar",
        "valueUpRadar": "value-up-radar",
        "backtestAccuracy": "backtest-accuracy",
        "portfolioReviewQueue": "portfolio-review-queue",
        "advancedModuleSummary": "advanced-module-summary",
        "fearGreedIndex": "fear-greed-index",
        "candleVolumeChart": "candle-volume-chart",
        "decisionFlow": "decision-flow",
        "signalConflictMatrix": "signal-conflict-matrix",
        "positionSizingRiskBudget": "position-sizing-risk-budget",
        "scenarioStressTest": "scenario-stress-test",
        "investmentThesisTracker": "investment-thesis-tracker",
        "catalystEventCalendar": "catalyst-event-calendar",
        "predictionCalibration": "prediction-calibration",
        "riskAlertRules": "risk-alert-rules",
        "similarCaseLibrary": "similar-case-library",
        "postReviewNotebook": "post-review-notebook",
    }
)

METRIC_LABELS: dict[str, str] = {
    "totalScore": "총점",
    "recommendationGrade": "등급",
    "confidence": "신뢰도",
    "expectedReturn3M": "3개월 기대수익",
    "downsideRisk": "하방위험",
    "momentumScore": "모멘텀",
    "valueScore": "밸류",
    "qualityScore": "퀄리티",
    "earningsScore": "실적",
    "supplyDemandScore": "수급",
    "disclosureScore": "공시",
    "valueUpScore": "밸류업",
    "liquidityScore": "유동성",
    "riskScore": "리스크",
    "foreignNetBuy": "외국인 순매수",
    "institutionNetBuy": "기관 순매수",
    "pensionNetBuy": "연기금 순매수",
    "shortSellRisk": "공매도 부담",
    "pbr": "PBR",
    "roe": "ROE",
    "dividendYield": "배당수익률",
    "cagr": "CAGR",
    "excessReturn": "초과수익",
    "mdd": "MDD",
    "sharpe": "Sharpe",
    "precisionAt10": "Precision@10",
    "rankIC": "Rank IC",
    "fearGreed": "공포·탐욕",
    "decisionStage": "검토 단계",
    "conflictCount": "충돌 신호",
    "positionBudget": "리스크 예산",
    "scenarioImpact": "시나리오 영향",
    "thesisStatus": "가설 상태",
    "catalystRisk": "이벤트 위험",
    "calibrationHitRate": "검증 적중률",
    "riskAlert": "리스크 알림",
    "similarCaseWinRate": "유사 사례 승률",
    "postReviewRMultiple": "사후 R 배수",
}

FACTOR_LABELS: dict[str, str] = {
    "momentum": "모멘텀",
    "value": "밸류",
    "quality": "퀄리티",
    "earnings": "실적",
    "supplyDemand": "수급",
    "disclosure": "공시",
    "valueUp": "밸류업",
    "liquidity": "유동성",
    "risk": "리스크",
}

FACTOR_TO_METRIC: dict[str, str] = {
    "momentum": "momentumScore",
    "value": "valueScore",
    "quality": "qualityScore",
    "earnings": "earningsScore",
    "supplyDemand": "supplyDemandScore",
    "disclosure": "disclosureScore",
    "valueUp": "valueUpScore",
    "liquidity": "liquidityScore",
    "risk": "riskScore",
}

FACTOR_ALIAS_TO_KEY: dict[str, str] = {
    "모멘텀": "momentum",
    "momentum": "momentum",
    "밸류": "value",
    "value": "value",
    "퀄리티": "quality",
    "quality": "quality",
    "실적": "earnings",
    "earnings": "earnings",
    "수급": "supplyDemand",
    "supply": "supplyDemand",
    "supplyDemand": "supplyDemand",
    "공시": "disclosure",
    "disclosure": "disclosure",
    "밸류업": "valueUp",
    "valueUp": "valueUp",
    "유동성": "liquidity",
    "liquidity": "liquidity",
    "리스크": "risk",
    "risk": "risk",
}

RELATED_MODULES: dict[str, tuple[str, ...]] = {
    "totalScore": ("factorHeatmap", "supplyDemandRadar", "disclosureRadar", "valueUpRadar", "backtestAccuracy", "decisionFlow"),
    "recommendationGrade": ("portfolioReviewQueue", "backtestAccuracy", "fearGreedIndex", "decisionFlow"),
    "confidence": ("backtestAccuracy", "factorHeatmap", "predictionCalibration"),
    "expectedReturn3M": ("candleVolumeChart", "backtestAccuracy", "scenarioStressTest"),
    "downsideRisk": ("candleVolumeChart", "portfolioReviewQueue", "supplyDemandRadar", "disclosureRadar", "positionSizingRiskBudget"),
    "momentumScore": ("factorHeatmap", "candleVolumeChart", "signalConflictMatrix"),
    "valueScore": ("factorHeatmap", "valueUpRadar"),
    "qualityScore": ("factorHeatmap", "valueUpRadar"),
    "earningsScore": ("factorHeatmap", "disclosureRadar", "catalystEventCalendar"),
    "supplyDemandScore": ("supplyDemandRadar", "candleVolumeChart", "signalConflictMatrix"),
    "disclosureScore": ("disclosureRadar", "factorHeatmap", "riskAlertRules"),
    "valueUpScore": ("valueUpRadar", "disclosureRadar", "factorHeatmap"),
    "liquidityScore": ("supplyDemandRadar", "candleVolumeChart", "positionSizingRiskBudget"),
    "riskScore": ("portfolioReviewQueue", "disclosureRadar", "riskAlertRules"),
    "foreignNetBuy": ("supplyDemandRadar", "candleVolumeChart"),
    "institutionNetBuy": ("supplyDemandRadar", "candleVolumeChart"),
    "pensionNetBuy": ("supplyDemandRadar", "candleVolumeChart"),
    "shortSellRisk": ("supplyDemandRadar", "portfolioReviewQueue", "riskAlertRules"),
    "pbr": ("valueUpRadar", "factorHeatmap"),
    "roe": ("valueUpRadar", "factorHeatmap"),
    "dividendYield": ("valueUpRadar", "disclosureRadar"),
    "cagr": ("backtestAccuracy", "predictionCalibration"),
    "excessReturn": ("backtestAccuracy", "similarCaseLibrary"),
    "mdd": ("backtestAccuracy", "candleVolumeChart", "portfolioReviewQueue"),
    "sharpe": ("backtestAccuracy", "predictionCalibration"),
    "precisionAt10": ("backtestAccuracy", "predictionCalibration"),
    "rankIC": ("backtestAccuracy", "predictionCalibration"),
    "fearGreed": ("fearGreedIndex", "decisionFlow", "riskAlertRules"),
    "decisionStage": ("decisionFlow", "portfolioReviewQueue", "riskAlertRules"),
    "conflictCount": ("signalConflictMatrix", "decisionFlow", "investmentThesisTracker"),
    "positionBudget": ("positionSizingRiskBudget", "portfolioReviewQueue", "scenarioStressTest"),
    "scenarioImpact": ("scenarioStressTest", "riskAlertRules", "positionSizingRiskBudget"),
    "thesisStatus": ("investmentThesisTracker", "catalystEventCalendar", "postReviewNotebook"),
    "catalystRisk": ("catalystEventCalendar", "disclosureRadar", "riskAlertRules"),
    "calibrationHitRate": ("predictionCalibration", "backtestAccuracy"),
    "riskAlert": ("riskAlertRules", "portfolioReviewQueue", "scenarioStressTest"),
    "similarCaseWinRate": ("similarCaseLibrary", "backtestAccuracy"),
    "postReviewRMultiple": ("postReviewNotebook", "predictionCalibration"),
}

MODULE_DEFAULT_METRIC: dict[str, str] = {
    "investmentAlgorithm": "totalScore",
    "factorHeatmap": "totalScore",
    "supplyDemandRadar": "supplyDemandScore",
    "disclosureRadar": "disclosureScore",
    "valueUpRadar": "valueUpScore",
    "backtestAccuracy": "cagr",
    "portfolioReviewQueue": "riskScore",
    "advancedModuleSummary": "totalScore",
    "fearGreedIndex": "fearGreed",
    "candleVolumeChart": "expectedReturn3M",
    "decisionFlow": "decisionStage",
    "signalConflictMatrix": "conflictCount",
    "positionSizingRiskBudget": "positionBudget",
    "scenarioStressTest": "scenarioImpact",
    "investmentThesisTracker": "thesisStatus",
    "catalystEventCalendar": "catalystRisk",
    "predictionCalibration": "calibrationHitRate",
    "riskAlertRules": "riskAlert",
    "similarCaseLibrary": "similarCaseWinRate",
    "postReviewNotebook": "postReviewRMultiple",
}


@dataclass(frozen=True)
class SelectedContext:
    selectedStockCode: str | None = None
    selectedStockName: str | None = None
    selectedDate: str | None = None
    selectedDateRange: str | None = None
    selectedDateStart: str | None = None
    selectedDateEnd: str | None = None
    selectedMarket: str | None = None
    selectedSector: str | None = None
    selectedMetric: str | None = None
    selectedFactor: str | None = None
    selectedModule: str | None = None
    selectedDisclosureId: str | None = None
    selectedQueueItemId: str | None = None
    selectedBacktestMetric: str | None = None
    selectedFearGreedBand: str | None = None
    selectedScenarioId: str | None = None
    selectedThesisId: str | None = None
    selectedRiskRule: str | None = None
    sourceModule: str | None = None


def _first(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return str(value[0]) if value else None
    return str(value)


def normalize_stock_code(value: Any) -> str | None:
    raw = _first(value)
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return None
    return digits.zfill(6)[-6:]


def normalize_module_key(value: Any) -> str | None:
    raw = _first(value)
    return raw if raw in MODULE_LABELS else None


def normalize_metric_key(value: Any) -> str | None:
    raw = _first(value)
    return raw if raw in METRIC_LABELS else None


def normalize_factor_key(value: Any) -> str | None:
    raw = _first(value)
    if not raw:
        return None
    return FACTOR_ALIAS_TO_KEY.get(raw)


def parse_query_context(params: Any) -> SelectedContext:
    def get(key: str) -> Any:
        try:
            if hasattr(params, "get_all"):
                values = params.get_all(key)
                return values[0] if values else None
            return params.get(key)
        except Exception:
            return None

    module = normalize_module_key(get("module"))
    factor = normalize_factor_key(get("factor"))
    metric = normalize_metric_key(get("metric"))
    if metric is None and factor is not None:
        metric = FACTOR_TO_METRIC.get(factor)
    return SelectedContext(
        selectedStockCode=normalize_stock_code(get("stock")),
        selectedDate=_first(get("date")),
        selectedDateRange=_first(get("range")),
        selectedDateStart=_first(get("start")),
        selectedDateEnd=_first(get("end")),
        selectedMarket=_first(get("market")),
        selectedSector=_first(get("sector")),
        selectedMetric=metric,
        selectedFactor=factor,
        selectedModule=module,
        selectedDisclosureId=_first(get("event")),
        selectedQueueItemId=_first(get("queue")),
        selectedBacktestMetric=_first(get("backtest")),
        selectedFearGreedBand=_first(get("fearGreedBand")),
        selectedScenarioId=_first(get("scenario")),
        selectedThesisId=_first(get("thesis")),
        selectedRiskRule=_first(get("riskRule")),
        sourceModule=module,
    )


def serialize_query_context(context: SelectedContext) -> dict[str, str]:
    query: dict[str, str] = {}
    if context.selectedStockCode:
        query["stock"] = context.selectedStockCode
    if context.selectedModule and context.selectedModule in MODULE_LABELS:
        query["module"] = context.selectedModule
    if context.selectedMetric and context.selectedMetric in METRIC_LABELS:
        query["metric"] = context.selectedMetric
    if context.selectedFactor and context.selectedFactor in FACTOR_LABELS:
        query["factor"] = context.selectedFactor
    if context.selectedDate:
        query["date"] = context.selectedDate
    if context.selectedDateRange:
        query["range"] = context.selectedDateRange
    if context.selectedDateStart:
        query["start"] = context.selectedDateStart
    if context.selectedDateEnd:
        query["end"] = context.selectedDateEnd
    if context.selectedMarket:
        query["market"] = context.selectedMarket
    if context.selectedSector:
        query["sector"] = context.selectedSector
    if context.selectedDisclosureId:
        query["event"] = context.selectedDisclosureId
    if context.selectedQueueItemId:
        query["queue"] = context.selectedQueueItemId
    if context.selectedScenarioId:
        query["scenario"] = context.selectedScenarioId
    if context.selectedThesisId:
        query["thesis"] = context.selectedThesisId
    if context.selectedRiskRule:
        query["riskRule"] = context.selectedRiskRule
    return query


CONTEXT_QUERY_KEYS = frozenset(
    {
        "stock",
        "module",
        "metric",
        "factor",
        "date",
        "range",
        "start",
        "end",
        "market",
        "sector",
        "event",
        "queue",
        "backtest",
        "fearGreedBand",
        "scenario",
        "thesis",
        "riskRule",
    }
)


def merge_context(context: SelectedContext, **updates: Any) -> SelectedContext:
    values = {key: getattr(context, key, None) for key in SelectedContext.__dataclass_fields__}
    values.update({key: value for key, value in updates.items() if key in values})
    return SelectedContext(**values)


def related_modules_for_metric(metric_key: str | None) -> tuple[str, ...]:
    if not metric_key:
        return ()
    return RELATED_MODULES.get(metric_key, ())


def formatModuleLabel(module_key: str | None) -> str:
    return MODULE_LABELS.get(str(module_key), "-")


def formatMetricLabel(metric_key: str | None) -> str:
    return METRIC_LABELS.get(str(metric_key), "-")


def formatFactorLabel(factor_key: str | None) -> str:
    return FACTOR_LABELS.get(str(factor_key), "-")


def safe_external_url(value: Any) -> str | None:
    raw = _first(value)
    if not raw:
        return None
    cleaned = raw.strip()
    if cleaned.startswith(("https://", "http://")):
        return cleaned
    return None
