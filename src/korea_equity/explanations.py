from __future__ import annotations

from dataclasses import dataclass, field

from .interaction import FACTOR_TO_METRIC, METRIC_LABELS, related_modules_for_metric


@dataclass(frozen=True)
class MetricExplanation:
    key: str
    label: str
    definition: str
    formula: str = "-"
    interpretation: str = "-"
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    relatedModules: tuple[str, ...] = field(default_factory=tuple)


def _explanation(
    key: str,
    definition: str,
    formula: str,
    interpretation: str,
    assumptions: tuple[str, ...] = (),
) -> MetricExplanation:
    return MetricExplanation(
        key=key,
        label=METRIC_LABELS.get(key, key),
        definition=definition,
        formula=formula,
        interpretation=interpretation,
        assumptions=assumptions,
        relatedModules=related_modules_for_metric(key),
    )


METRIC_EXPLANATIONS: dict[str, MetricExplanation] = {
    "totalScore": _explanation(
        "totalScore",
        "한국 주식 검토 후보의 종합 점수입니다.",
        "모멘텀, 밸류, 퀄리티, 실적, 수급, 공시, 밸류업, 유동성 점수를 가중합한 뒤 리스크 감점을 반영합니다.",
        "점수가 높을수록 검토 우선순위가 높지만, 신뢰도와 리스크 플래그를 함께 확인해야 합니다.",
        ("점수는 주문 지시가 아니라 검토 우선순위입니다.",),
    ),
    "recommendationGrade": _explanation(
        "recommendationGrade",
        "총점, 신뢰도, 리스크 플래그를 함께 반영한 검토 등급입니다.",
        "총점 구간과 신뢰도 기준을 먼저 적용하고, 공시·유동성·거래정지 위험이 있으면 하향 조정합니다.",
        "등급은 확정 매수/매도 신호가 아니라 추가 확인 순서입니다.",
    ),
    "confidence": _explanation(
        "confidence",
        "데이터 신선도, 팩터 일치도, 시장 국면, 백테스트 안정성을 반영한 신호 신뢰도입니다.",
        "데이터 품질 + 팩터 일치도 + 검증 안정성 - 리스크 결측 감점",
        "낮은 신뢰도에서는 가격 구간, 공시, 수급 확인이 우선입니다.",
    ),
    "expectedReturn3M": _explanation(
        "expectedReturn3M",
        "향후 3개월을 기준으로 한 규칙 기반 기대수익 추정치입니다.",
        "종합 점수, 변동성, 시장 국면, 상대강도, 비용 가정을 반영한 비보장 추정값",
        "기대수익은 확정 수익이 아니며 하방위험과 손익비를 함께 봐야 합니다.",
        ("예측 기간은 3개월입니다.", "검증 전 추정값은 낮은 confidence로 취급합니다."),
    ),
    "downsideRisk": _explanation(
        "downsideRisk",
        "변동성, 최대낙폭, ATR, 공시·수급 리스크를 반영한 하방 시나리오입니다.",
        "최근 가격 변동성 + 최대낙폭 + 이벤트/수급 리스크 감점",
        "기대수익 대비 감수할 손실 구간이 큰 경우 비중과 손절 기준 확인이 우선입니다.",
    ),
    "momentumScore": _explanation("momentumScore", "상대강도와 이동평균 위치를 반영합니다.", "20/60/120/200일 수익률과 벤치마크 대비 상대강도", "거래량 없는 상승은 신뢰도가 낮을 수 있습니다."),
    "valueScore": _explanation("valueScore", "PER, PBR, 배당수익률 등 밸류에이션 매력을 반영합니다.", "업종 대비 PER/PBR + 배당수익률 + 저평가 보정", "저평가만으로 반등이 보장되지는 않습니다."),
    "qualityScore": _explanation("qualityScore", "ROE, 마진, 부채비율, 현금흐름 안정성을 반영합니다.", "ROE/마진/재무 안정성 점수 합산", "퀄리티가 높을수록 하방 방어력이 개선됩니다."),
    "earningsScore": _explanation("earningsScore", "실적 추세와 이익 개선 가능성을 반영합니다.", "영업이익 변화 + 매출 안정성 + 실적 이벤트", "실적 이벤트 전후에는 변동성이 커질 수 있습니다."),
    "supplyDemandScore": _explanation("supplyDemandScore", "외국인, 기관, 연기금 수급과 공매도 부담을 반영합니다.", "20/60거래일 누적 순매수 + 거래대금 변화 - 공매도 부담", "단기 수급은 빠르게 바뀔 수 있어 가격 확인이 필요합니다."),
    "disclosureScore": _explanation("disclosureScore", "DART/KIND 공시 이벤트의 방향과 중요도를 반영합니다.", "이벤트 중요도 x 감성 방향 - 고위험 공시 감점", "High/Critical 공시가 있으면 신규 검토보다 리스크 확인이 우선입니다."),
    "valueUpScore": _explanation("valueUpScore", "저PBR, ROE 개선, 배당, 자사주, 기업가치 제고 가능성을 반영합니다.", "저평가 + 주주환원 + 퀄리티 + 관련 공시", "정책·공시 촉매가 함께 확인될수록 신뢰도가 높아집니다."),
    "liquidityScore": _explanation("liquidityScore", "거래대금과 체결 가능성을 반영합니다.", "최근 거래대금/거래량 기반 유동성 점수", "유동성이 낮으면 좋은 신호도 실제 진입·청산 리스크가 커집니다."),
    "riskScore": _explanation("riskScore", "변동성, 낙폭, 공시, 유동성, 수급 부담을 반영한 위험 점수입니다.", "가격 리스크 + 이벤트 리스크 + 수급/유동성 리스크", "리스크 점수는 공격보다 생존과 비중 관리 판단에 사용합니다."),
    "foreignNetBuy": _explanation("foreignNetBuy", "외국인 누적 순매수 금액입니다.", "최근 20거래일 외국인 순매수 합계", "외국인 수급이 강하면 추세 지속 가능성을 보조합니다."),
    "institutionNetBuy": _explanation("institutionNetBuy", "기관 누적 순매수 금액입니다.", "최근 20거래일 기관 순매수 합계", "기관 수급은 중기 추세의 보조 근거로 봅니다."),
    "pensionNetBuy": _explanation("pensionNetBuy", "연기금 누적 순매수 금액입니다.", "최근 20~40거래일 연기금 순매수 합계", "연기금 수급은 방어적 수급 안정성을 보조합니다."),
    "shortSellRisk": _explanation("shortSellRisk", "공매도 잔고와 가격 모멘텀을 결합한 부담 지표입니다.", "공매도 잔고율 + 상승 모멘텀", "부담이 높으면 변동성 확대에 유의합니다."),
    "pbr": _explanation("pbr", "주가순자산비율입니다.", "시가총액 / 순자산", "저PBR은 밸류업 후보의 기초 조건이지만 단독 근거는 아닙니다."),
    "roe": _explanation("roe", "자기자본이익률입니다.", "순이익 / 자기자본", "ROE가 높고 유지될수록 밸류 재평가 가능성이 커집니다."),
    "dividendYield": _explanation("dividendYield", "주가 대비 배당수익률입니다.", "주당배당금 / 주가", "배당 매력은 하방 방어와 주주환원 판단에 활용합니다."),
    "cagr": _explanation("cagr", "백테스트 기간의 연평균 복리 수익률입니다.", "(종료 가치 / 시작 가치)^(1 / 연수) - 1", "MDD와 Sharpe를 함께 확인해야 합니다."),
    "excessReturn": _explanation("excessReturn", "전략 수익률에서 벤치마크 수익률을 뺀 값입니다.", "전략 수익률 - 벤치마크 수익률", "양수여도 반복 가능성이 검증되어야 합니다."),
    "mdd": _explanation("mdd", "기간 중 고점 대비 최대 낙폭입니다.", "min(현재 가치 / 이전 최고 가치 - 1)", "생존 리스크를 보여주는 핵심 지표입니다."),
    "sharpe": _explanation("sharpe", "변동성 대비 초과수익을 보는 위험조정 수익률입니다.", "(연수익률 - 무위험수익률) / 연환산 변동성", "낮은 Sharpe는 수익보다 변동성 부담이 크다는 뜻입니다."),
    "precisionAt10": _explanation("precisionAt10", "상위 10개 후보 중 실제 성과가 양호했던 비율입니다.", "성과 기준 충족 상위 후보 수 / 10", "후보 랭킹의 실전 적중률을 평가합니다."),
    "rankIC": _explanation("rankIC", "점수 순위와 이후 성과 순위의 상관입니다.", "Spearman rank correlation(score rank, forward return rank)", "양수이고 안정적일수록 모델 순위가 의미 있습니다."),
    "fearGreed": _explanation("fearGreed", "시장 심리와 위험 선호도를 0~100으로 표시합니다.", "시장 가격 추세, 변동성, 수급 압력을 규칙 기반으로 조합", "극단 구간에서는 추세 추종보다 리스크 관리가 우선입니다."),
    "decisionStage": _explanation("decisionStage", "시장, 종목, 리스크, 타이밍, 포트폴리오 적합도를 순서대로 통과시키는 검토 흐름입니다.", "각 단계 점수와 차단 사유를 순차 평가", "어느 단계에서 보류되는지 확인해 다음 검토 행동을 정합니다."),
    "conflictCount": _explanation("conflictCount", "긍정 신호와 부정 신호가 서로 충돌하는 정도입니다.", "강한 긍정/부정 팩터 수와 심각도 합산", "충돌이 크면 추격보다 근거 재확인이 우선입니다."),
    "positionBudget": _explanation("positionBudget", "손절 기준과 총자산 리스크 한도를 반영한 최대 검토 비중입니다.", "거래당 허용손실 / 주당 위험금액, 단일 종목 최대비중과 유동성 제한 적용", "수량 계산은 주문 지시가 아니라 리스크 상한 검토용입니다."),
    "scenarioImpact": _explanation("scenarioImpact", "환율·금리·지수·유동성 충격 시 기대값이 어떻게 흔들리는지 보는 스트레스 결과입니다.", "기본 기대수익 + 시나리오별 충격 계수", "시나리오가 취약하면 비중 보강보다 방어 계획이 우선입니다."),
    "thesisStatus": _explanation("thesisStatus", "투자 가설이 아직 유효한지 추적하는 상태입니다.", "핵심 근거, 반증 조건, 확인 예정 이벤트를 묶어 평가", "가설이 깨지면 점수보다 리스크 관리가 우선입니다."),
    "catalystRisk": _explanation("catalystRisk", "공시, 실적, 정책, 이벤트가 종목 판단에 미칠 위험입니다.", "이벤트 중요도와 감성 방향, 예정일 기준 분류", "중요 이벤트 전후에는 변동성과 갭 리스크를 반영합니다."),
    "calibrationHitRate": _explanation("calibrationHitRate", "과거 검증에서 모델 신호가 실제 성과로 이어진 정도입니다.", "Precision@10, Rank IC, hit ratio, win rate 조합", "검증 지표가 약하면 confidence를 낮춰 해석합니다."),
    "riskAlert": _explanation("riskAlert", "가격, 공시, 수급, 시장 국면에서 즉시 확인해야 할 위험 조건입니다.", "규칙별 트리거 조건과 현재 상태 비교", "활성화된 알림은 신규 검토를 보류하거나 비중을 낮추는 근거입니다."),
    "similarCaseWinRate": _explanation("similarCaseWinRate", "현재 종목과 비슷한 과거 후보군의 성과 요약입니다.", "업종, 점수, 변동성, 리스크 플래그가 유사한 사례 집계", "샘플이 적으면 참고 자료로만 봅니다."),
    "postReviewRMultiple": _explanation("postReviewRMultiple", "검토 이후 결과를 R 배수로 기록하는 사후 평가 지표입니다.", "실현/가상 손익 / 최초 위험금액", "반복적으로 약한 신호 유형은 kill-switch 후보가 됩니다."),
}


def get_metric_explanation(metric_key: str | None) -> MetricExplanation | None:
    if not metric_key:
        return None
    return METRIC_EXPLANATIONS.get(metric_key)


def explanation_for_factor(factor_key: str | None) -> MetricExplanation | None:
    if not factor_key:
        return None
    return get_metric_explanation(FACTOR_TO_METRIC.get(factor_key))


def required_metric_keys() -> tuple[str, ...]:
    return tuple(METRIC_EXPLANATIONS.keys())


def metric_label(metric_key: str | None) -> str:
    return METRIC_LABELS.get(str(metric_key), "-")
