from __future__ import annotations

from dataclasses import dataclass, field
from math import floor, isfinite
from statistics import mean
from typing import Any


@dataclass(frozen=True)
class KoreaDecisionStage:
    id: str
    title: str
    status: str
    score: float | None = None
    confidence: float | None = None
    primary_evidence: tuple[str, ...] = field(default_factory=tuple)
    candidate_action: str = "관찰"
    blocking_reason: str | None = None
    related_modules: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class KoreaSignalConflict:
    id: str
    signal: str
    direction: str
    strength: float | None = None
    evidence: str = ""
    conflict_with: str | None = None
    severity: str = "medium"
    related_modules: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class KoreaPositionSizingResult:
    code: str | None
    name: str | None
    status: str
    entry_price: float | None = None
    stop_price: float | None = None
    max_loss_pct: float | None = None
    max_position_weight: float | None = None
    max_position_value: float | None = None
    max_quantity: int | None = None
    risk_budget_amount: float | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    confidence: float | None = None
    action_label: str = "관찰"


@dataclass(frozen=True)
class KoreaScenarioResult:
    id: str
    label: str
    status: str
    impact_pct: float | None = None
    evidence: tuple[str, ...] = field(default_factory=tuple)
    candidate_action: str = "관찰"
    confidence: float | None = None
    related_modules: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class KoreaInvestmentThesis:
    id: str
    code: str | None
    name: str | None
    status: str
    core_view: str
    supporting_evidence: tuple[str, ...] = field(default_factory=tuple)
    invalidation_rules: tuple[str, ...] = field(default_factory=tuple)
    next_review: str = "다음 데이터 업데이트 후"
    confidence: float | None = None


@dataclass(frozen=True)
class KoreaCatalystEvent:
    id: str
    date: str
    code: str | None
    title: str
    severity: str
    expected_effect: str
    status: str = "예정/관찰"
    related_modules: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class KoreaCalibrationMetrics:
    status: str
    precision_at_10: float | None = None
    rank_ic: float | None = None
    hit_ratio: float | None = None
    win_rate: float | None = None
    confidence_adjustment: str = "검증 필요"
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class KoreaRiskAlertRule:
    id: str
    title: str
    status: str
    trigger: str
    current_value: str
    candidate_action: str
    severity: str = "medium"
    related_modules: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class KoreaSimilarCaseSummary:
    id: str
    label: str
    sample_size: int
    win_rate: float | None = None
    average_forward_return: float | None = None
    max_drawdown: float | None = None
    evidence: tuple[str, ...] = field(default_factory=tuple)
    confidence: float | None = None


@dataclass(frozen=True)
class KoreaPostReviewOutcome:
    id: str
    code: str | None
    status: str
    realized_r_multiple: float | None = None
    forward_return_20d: float | None = None
    drift_status: str = "기록 대기"
    lessons: tuple[str, ...] = field(default_factory=tuple)
    next_action: str = "사후 성과가 누적되면 검증에 반영"


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _pct_text(value: Any) -> str:
    number = _finite(value)
    return "N/A" if number is None else f"{number * 100:+.1f}%"


def _score_text(value: Any) -> str:
    number = _finite(value)
    return "N/A" if number is None else f"{number:.0f}점"


def _top_score(scores: list[Any]) -> Any | None:
    return scores[0] if scores else None


def _risk_tone(score: Any) -> str:
    flags = list(getattr(score, "risk_flags", []) or [])
    if not score:
        return "unavailable"
    if flags or (getattr(score, "downside_risk", 0) or 0) < -0.18:
        return "주의"
    return "정상"


def buildDecisionFlow(scores: list[Any], market_status: Any, backtest: Any | None = None) -> list[KoreaDecisionStage]:
    top = _top_score(scores)
    if top is None:
        return [
            KoreaDecisionStage(
                id="no-data",
                title="후보 데이터 확인",
                status="데이터 부족",
                blocking_reason="한국 주식 후보 점수가 없습니다.",
                candidate_action="데이터 업데이트 필요",
                related_modules=("investmentAlgorithm",),
            )
        ]

    regime = str(getattr(market_status, "regime", "neutral") or "neutral")
    regime_score = _finite(getattr(market_status, "regime_score", None))
    score = _finite(getattr(top, "total_score", None))
    confidence = _finite(getattr(top, "confidence", None))
    downside = _finite(getattr(top, "downside_risk", None))
    precision = _finite(getattr(backtest, "precision_at_top10", None)) if backtest is not None else None
    stages = [
        KoreaDecisionStage(
            id="market-gate",
            title="1. 시장 국면",
            status="통과" if regime not in {"panic", "risk_off"} else "보수 검토",
            score=regime_score,
            confidence=confidence,
            primary_evidence=tuple(str(item) for item in getattr(market_status, "reason", [])[:3]),
            candidate_action="공격 비중 제한" if regime in {"panic", "risk_off"} else "정상 검토",
            related_modules=("fearGreedIndex", "riskAlertRules"),
        ),
        KoreaDecisionStage(
            id="candidate-quality",
            title="2. 후보 품질",
            status="통과" if (score or 0) >= 60 else "보류",
            score=score,
            confidence=confidence,
            primary_evidence=tuple(list(getattr(top, "positive_reasons", []) or [])[:3]),
            candidate_action="근거 확인" if (score or 0) >= 60 else "관찰",
            blocking_reason=None if (score or 0) >= 60 else "총점이 낮아 우선순위가 낮습니다.",
            related_modules=("factorHeatmap", "investmentAlgorithm"),
        ),
        KoreaDecisionStage(
            id="risk-gate",
            title="3. 리스크 게이트",
            status=_risk_tone(top),
            score=None if downside is None else 100 + downside * 100,
            confidence=confidence,
            primary_evidence=tuple(list(getattr(top, "negative_reasons", []) or [])[:3]),
            candidate_action="손절 기준 먼저 확인" if _risk_tone(top) != "정상" else "정상 검토",
            blocking_reason="리스크 플래그 존재" if getattr(top, "risk_flags", None) else None,
            related_modules=("positionSizingRiskBudget", "riskAlertRules"),
        ),
        KoreaDecisionStage(
            id="validation-gate",
            title="4. 검증 신뢰도",
            status="통과" if precision is None or precision >= 0.5 else "검증 약함",
            score=None if precision is None else precision * 100,
            confidence=confidence,
            primary_evidence=(f"Precision@10 {_pct_text(precision)}", f"Rank IC {_score_text(getattr(backtest, 'factor_rank_ic', None))}"),
            candidate_action="신뢰도 낮춰 해석" if precision is not None and precision < 0.5 else "정상 검토",
            related_modules=("predictionCalibration", "backtestAccuracy"),
        ),
        KoreaDecisionStage(
            id="decision-summary",
            title="5. 결론",
            status="검토 후보" if (score or 0) >= 60 and _risk_tone(top) != "unavailable" else "관찰",
            score=score,
            confidence=confidence,
            primary_evidence=(f"{getattr(top, 'name', '')} {getattr(top, 'code', '')}", f"기대수익 3M {_pct_text(getattr(top, 'expected_return_3m', None))}", f"하방위험 {_pct_text(downside)}"),
            candidate_action="비중 보강 검토" if (score or 0) >= 70 and _risk_tone(top) == "정상" else "관찰 또는 분할 검토",
            related_modules=("investmentThesisTracker", "postReviewNotebook"),
        ),
    ]
    return stages


def buildSignalConflictMatrix(score: Any | None) -> list[KoreaSignalConflict]:
    if score is None:
        return [
            KoreaSignalConflict(
                id="no-score",
                signal="후보 점수",
                direction="neutral",
                evidence="선택된 후보가 없어 충돌 신호를 계산할 수 없습니다.",
                severity="low",
            )
        ]
    factors = getattr(score, "factor_scores", None)
    rows: list[KoreaSignalConflict] = []
    factor_values = {
        "모멘텀": getattr(factors, "momentum", None) if factors else None,
        "밸류": getattr(factors, "value", None) if factors else None,
        "퀄리티": getattr(factors, "quality", None) if factors else None,
        "수급": getattr(factors, "supply_demand", None) if factors else None,
        "공시": getattr(factors, "event_catalyst", None) if factors else None,
        "유동성": getattr(factors, "liquidity", None) if factors else None,
        "리스크": getattr(factors, "risk", None) if factors else None,
    }
    positives = [label for label, value in factor_values.items() if (_finite(value) or 0) >= 65]
    negatives = [label for label, value in factor_values.items() if value is not None and (_finite(value) or 0) <= 42]
    for label, value in factor_values.items():
        number = _finite(value)
        if number is None:
            continue
        direction = "positive" if number >= 65 else "negative" if number <= 42 else "neutral"
        conflict = ", ".join(negatives if direction == "positive" else positives) or None
        rows.append(
            KoreaSignalConflict(
                id=f"factor-{label}",
                signal=label,
                direction=direction,
                strength=number,
                evidence=f"{label} 점수 {number:.0f}점",
                conflict_with=conflict,
                severity="high" if direction == "negative" and label in {"리스크", "유동성", "공시"} else "medium",
                related_modules=("factorHeatmap", "signalConflictMatrix"),
            )
        )
    if getattr(score, "risk_flags", None):
        rows.append(
            KoreaSignalConflict(
                id="risk-flags",
                signal="리스크 플래그",
                direction="negative",
                strength=80,
                evidence=", ".join(getattr(score, "risk_flags", [])[:3]),
                conflict_with=", ".join(positives) or None,
                severity="high",
                related_modules=("riskAlertRules", "portfolioReviewQueue"),
            )
        )
    return rows


def calculatePositionSizingRiskBudget(
    score: Any | None,
    market_status: Any | None = None,
    portfolio: dict[str, Any] | None = None,
    total_equity: float = 100_000_000,
    risk_per_trade_pct: float = 0.0025,
) -> KoreaPositionSizingResult:
    if score is None:
        return KoreaPositionSizingResult(None, None, "데이터 부족", warnings=("선택된 후보가 없습니다.",), action_label="데이터 업데이트 필요")
    entry = _finite(getattr(score, "target_review_range_low", None)) or _finite(getattr(score, "stop_review_price", None))
    stop = _finite(getattr(score, "stop_review_price", None)) or _finite(getattr(score, "invalidation_price", None))
    max_weight = _finite(getattr(score, "max_suggested_weight", None)) or 0.08
    confidence = _finite(getattr(score, "confidence", None))
    warnings: list[str] = []
    if entry is None or stop is None or entry <= stop:
        return KoreaPositionSizingResult(
            getattr(score, "code", None),
            getattr(score, "name", None),
            "검증 필요",
            entry_price=entry,
            stop_price=stop,
            max_position_weight=max_weight,
            warnings=("진입 기준가와 손절 기준가가 불충분합니다.",),
            confidence=confidence,
            action_label="관찰",
        )
    regime = str(getattr(market_status, "regime", "neutral") if market_status is not None else "neutral")
    risk_budget = total_equity * risk_per_trade_pct
    if regime in {"risk_off", "panic"}:
        risk_budget *= 0.6 if regime == "risk_off" else 0.35
        warnings.append("시장 국면 haircut 적용")
    risk_per_share = max(entry - stop, 1)
    quantity_by_risk = floor(risk_budget / risk_per_share)
    quantity_by_weight = floor(total_equity * max_weight / entry)
    quantity = max(0, min(quantity_by_risk, quantity_by_weight))
    max_value = quantity * entry
    if getattr(score, "risk_flags", None):
        warnings.append("리스크 플래그 존재")
    return KoreaPositionSizingResult(
        getattr(score, "code", None),
        getattr(score, "name", None),
        "사용 가능" if quantity > 0 else "검증 필요",
        entry_price=entry,
        stop_price=stop,
        max_loss_pct=(entry - stop) / entry,
        max_position_weight=max_value / total_equity if total_equity else None,
        max_position_value=max_value,
        max_quantity=quantity,
        risk_budget_amount=risk_budget,
        warnings=tuple(warnings),
        confidence=confidence,
        action_label="비중 한도 내 검토" if quantity > 0 else "관찰",
    )


def runScenarioStressTests(score: Any | None, market_status: Any | None = None) -> list[KoreaScenarioResult]:
    if score is None:
        return [KoreaScenarioResult("no-data", "시나리오", "데이터 부족", evidence=("선택된 후보가 없습니다.",))]
    base = _finite(getattr(score, "expected_return_3m", None))
    confidence = _finite(getattr(score, "confidence", None))
    downside = abs(_finite(getattr(score, "downside_risk", None)) or 0.08)
    scenarios = [
        ("usdkrwShock", "USD/KRW 급등", -0.35 * downside, "환율 부담 확대"),
        ("rateShock", "국고채 금리 상승", -0.28 * downside, "할인율 부담 확대"),
        ("kospiDrawdown", "KOSPI -7% 충격", -0.70 * downside, "시장 베타 충격"),
        ("liquidityDryUp", "거래대금 위축", -0.40 * downside, "체결·청산 리스크 확대"),
    ]
    rows: list[KoreaScenarioResult] = []
    for scenario_id, label, shock, reason in scenarios:
        impact = None if base is None else base + shock
        status = "방어 우선" if impact is not None and impact < 0 else "검토 가능"
        rows.append(
            KoreaScenarioResult(
                id=scenario_id,
                label=label,
                status=status,
                impact_pct=impact,
                evidence=(reason, f"기본 기대수익 {_pct_text(base)}"),
                candidate_action="비중 축소 검토" if status == "방어 우선" else "분할 검토",
                confidence=confidence,
                related_modules=("scenarioStressTest", "positionSizingRiskBudget", "riskAlertRules"),
            )
        )
    return rows


def buildInvestmentThesisTracker(score: Any | None, conflicts: list[KoreaSignalConflict] | None = None, disclosures: list[Any] | None = None) -> list[KoreaInvestmentThesis]:
    if score is None:
        return [KoreaInvestmentThesis("no-data", None, None, "데이터 부족", "선택된 후보가 없습니다.")]
    negative_conflicts = [row.signal for row in conflicts or [] if row.direction == "negative"]
    status = "검증 중" if not negative_conflicts else "반증 조건 확인"
    return [
        KoreaInvestmentThesis(
            id=f"thesis-{getattr(score, 'code', 'unknown')}",
            code=getattr(score, "code", None),
            name=getattr(score, "name", None),
            status=status,
            core_view=f"{getattr(score, 'name', '선택 종목')}은 총점 {_score_text(getattr(score, 'total_score', None))}, 신뢰도 {_pct_text(getattr(score, 'confidence', None))} 기준의 검토 후보입니다.",
            supporting_evidence=tuple(list(getattr(score, "positive_reasons", []) or [])[:4]),
            invalidation_rules=tuple(
                item
                for item in [
                    f"손절 검토가 {getattr(score, 'stop_review_price', None):,.0f}원 아래로 이탈" if _finite(getattr(score, "stop_review_price", None)) else None,
                    "중요 부정 공시 발생",
                    "수급 점수 45점 이하로 하락",
                ]
                if item
            ),
            next_review="공시·수급·가격 데이터 갱신 후",
            confidence=_finite(getattr(score, "confidence", None)),
        )
    ]


def buildCatalystCalendar(score: Any | None, disclosures: list[Any]) -> list[KoreaCatalystEvent]:
    rows: list[KoreaCatalystEvent] = []
    code = getattr(score, "code", None) if score is not None else None
    for event in disclosures or []:
        if code and getattr(event, "code", None) not in {code, None, ""}:
            continue
        sentiment = str(getattr(event, "sentiment", "neutral") or "neutral")
        severity = "high" if sentiment == "negative" or (_finite(getattr(event, "importance", None)) or 0) >= 75 else "medium"
        effect = "긍정 촉매" if sentiment == "positive" else "리스크 점검" if sentiment == "negative" else "중립 이벤트"
        rows.append(
            KoreaCatalystEvent(
                id=str(getattr(event, "id", f"event-{len(rows)}")),
                date=str(getattr(event, "date", "")),
                code=getattr(event, "code", None),
                title=str(getattr(event, "title", "") or getattr(event, "summary", "") or "공시 이벤트"),
                severity=severity,
                expected_effect=effect,
                status="확인 필요",
                related_modules=("disclosureRadar", "riskAlertRules"),
            )
        )
    if not rows:
        rows.append(
            KoreaCatalystEvent(
                id="scheduled-review",
                date="다음 영업일",
                code=code,
                title="가격·수급 데이터 정기 점검",
                severity="low",
                expected_effect="신호 유지 여부 확인",
                status="예정",
                related_modules=("investmentThesisTracker",),
            )
        )
    return rows[:8]


def calculatePredictionCalibration(backtest: Any | None) -> KoreaCalibrationMetrics:
    if backtest is None:
        return KoreaCalibrationMetrics("데이터 부족", warnings=("백테스트 결과가 없습니다.",))
    precision = _finite(getattr(backtest, "precision_at_top10", None))
    rank_ic = _finite(getattr(backtest, "factor_rank_ic", None))
    hit_ratio = _finite(getattr(backtest, "hit_ratio", None))
    win_rate = _finite(getattr(backtest, "win_rate", None))
    warnings: list[str] = []
    if precision is not None and precision < 0.5:
        warnings.append("상위 후보 적중률 약함")
    if rank_ic is not None and rank_ic < 0:
        warnings.append("순위 예측력이 불안정")
    status = "사용 가능" if not warnings else "검증 주의"
    adjustment = "정상 confidence" if not warnings else "confidence 보수 적용"
    return KoreaCalibrationMetrics(status, precision, rank_ic, hit_ratio, win_rate, adjustment, tuple(warnings))


def buildRiskAlertRules(score: Any | None, market_status: Any | None, conflicts: list[KoreaSignalConflict] | None = None) -> list[KoreaRiskAlertRule]:
    rows: list[KoreaRiskAlertRule] = []
    if market_status is not None:
        regime = str(getattr(market_status, "regime", "neutral") or "neutral")
        rows.append(
            KoreaRiskAlertRule(
                id="market-regime",
                title="시장 위험회피 국면",
                status="활성" if regime in {"risk_off", "panic"} else "대기",
                trigger="regime in risk_off/panic",
                current_value=regime,
                candidate_action="신규 검토 보류 또는 비중 축소" if regime in {"risk_off", "panic"} else "정상 감시",
                severity="high" if regime == "panic" else "medium",
                related_modules=("fearGreedIndex", "decisionFlow"),
            )
        )
    if score is not None:
        downside = _finite(getattr(score, "downside_risk", None))
        rows.append(
            KoreaRiskAlertRule(
                id="downside-risk",
                title="하방위험 확대",
                status="활성" if downside is not None and downside < -0.15 else "대기",
                trigger="downsideRisk < -15%",
                current_value=_pct_text(downside),
                candidate_action="손절 기준 재확인" if downside is not None and downside < -0.15 else "정상 감시",
                severity="high" if downside is not None and downside < -0.22 else "medium",
                related_modules=("positionSizingRiskBudget", "candleVolumeChart"),
            )
        )
        flags = list(getattr(score, "risk_flags", []) or [])
        rows.append(
            KoreaRiskAlertRule(
                id="risk-flags",
                title="리스크 플래그",
                status="활성" if flags else "대기",
                trigger="risk_flags not empty",
                current_value=", ".join(flags[:3]) if flags else "없음",
                candidate_action="신규 검토 보류" if flags else "정상 감시",
                severity="high" if flags else "low",
                related_modules=("disclosureRadar", "portfolioReviewQueue"),
            )
        )
    return rows


def findSimilarCaseSummaries(scores: list[Any], selected_score: Any | None = None) -> list[KoreaSimilarCaseSummary]:
    rows = list(scores or [])
    if selected_score is None:
        selected_score = _top_score(rows)
    if selected_score is None or not rows:
        return [KoreaSimilarCaseSummary("no-data", "유사 사례 없음", 0, evidence=("후보 데이터가 부족합니다.",), confidence=0.0)]
    sector = getattr(selected_score, "sector", None)
    peers = [row for row in rows if getattr(row, "sector", None) == sector and row is not selected_score]
    if not peers:
        peers = [row for row in rows if row is not selected_score][:5]
    returns = [_finite(getattr(row, "expected_excess_return_3m", None)) for row in peers]
    clean_returns = [value for value in returns if value is not None]
    win_rate = None if not clean_returns else sum(1 for value in clean_returns if value > 0) / len(clean_returns)
    avg_return = None if not clean_returns else mean(clean_returns)
    drawdowns = [_finite(getattr(row, "downside_risk", None)) for row in peers]
    clean_dd = [value for value in drawdowns if value is not None]
    return [
        KoreaSimilarCaseSummary(
            id=f"sector-{sector or 'all'}",
            label=f"{sector or '전체'} 유사 후보",
            sample_size=len(peers),
            win_rate=win_rate,
            average_forward_return=avg_return,
            max_drawdown=min(clean_dd) if clean_dd else None,
            evidence=tuple(f"{getattr(row, 'name', '')} {_score_text(getattr(row, 'total_score', None))}" for row in peers[:4]),
            confidence=min(0.75, 0.25 + len(peers) * 0.08),
        )
    ]


def buildPostReviewNotebook(score: Any | None, backtest: Any | None = None) -> list[KoreaPostReviewOutcome]:
    if score is None:
        return [KoreaPostReviewOutcome("no-data", None, "기록 대기", lessons=("선택된 후보가 없습니다.",))]
    expected = _finite(getattr(score, "expected_return_3m", None))
    downside = abs(_finite(getattr(score, "downside_risk", None)) or 0)
    r_multiple = None if not expected or downside <= 0 else expected / downside
    lessons = [
        "검토 시점의 총점·신뢰도·하방위험을 저장합니다.",
        "20/60거래일 후 실제 성과를 비교해 약한 신호 유형을 줄입니다.",
    ]
    if backtest is not None and (_finite(getattr(backtest, "precision_at_top10", None)) or 0) < 0.5:
        lessons.append("상위 후보 적중률이 약하면 신호 confidence를 낮춥니다.")
    return [
        KoreaPostReviewOutcome(
            id=f"review-{getattr(score, 'code', 'unknown')}",
            code=getattr(score, "code", None),
            status="기록 대기",
            realized_r_multiple=r_multiple,
            forward_return_20d=None,
            drift_status="사후 데이터 대기",
            lessons=tuple(lessons),
            next_action="신호 저장 후 20/60거래일 성과 업데이트",
        )
    ]


def buildKoreaInvestmentOS(
    scores: list[Any],
    market_status: Any | None = None,
    backtest: Any | None = None,
    disclosures: list[Any] | None = None,
    value_up_candidates: list[Any] | None = None,
    risk_summary: dict[str, Any] | None = None,
    portfolio: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = list(scores or [])
    top = _top_score(rows)
    conflicts = buildSignalConflictMatrix(top)
    return {
        "selectedScore": top,
        "decisionFlow": buildDecisionFlow(rows, market_status, backtest),
        "signalConflicts": conflicts,
        "positionSizing": calculatePositionSizingRiskBudget(top, market_status, portfolio),
        "scenarios": runScenarioStressTests(top, market_status),
        "theses": buildInvestmentThesisTracker(top, conflicts, disclosures or []),
        "catalysts": buildCatalystCalendar(top, disclosures or []),
        "calibration": calculatePredictionCalibration(backtest),
        "riskAlerts": buildRiskAlertRules(top, market_status, conflicts),
        "similarCases": findSimilarCaseSummaries(rows, top),
        "postReview": buildPostReviewNotebook(top, backtest),
        "meta": {
            "version": "korea-investment-os-v2",
            "mode": "decision_support",
            "safe_language": "candidate_actions_only",
        },
    }
