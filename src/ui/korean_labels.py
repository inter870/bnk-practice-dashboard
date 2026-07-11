from __future__ import annotations

import re
from typing import Any, Iterable


MODULE_TITLES = {
    "Portfolio Risk Cockpit": "포트폴리오 리스크 관제실",
    "Data Trust & Source Panel": "데이터 신뢰도·출처 패널",
    "Market Regime & Macro Radar": "시장 국면·매크로 레이더",
    "KRW / Rates / FX Dashboard": "원화·금리·환율 대시보드",
    "Valuation & Relative Cheapness Panel": "밸류에이션·상대 저평가 패널",
    "Fundamental Quality Panel": "펀더멘털 품질 패널",
    "DART Disclosure Catalyst Panel": "DART 공시·촉매 패널",
    "Smart Money Flow & Short Pressure Panel": "수급·공매도 압력 패널",
    "Forward Alpha Ranking Panel": "미래 알파 후보 랭킹",
    "Portfolio Optimizer & Alert Center": "포트폴리오 최적화·알림 센터",
}

STATUS_LABELS = {
    "ready": "사용 가능",
    "stale": "업데이트 필요",
    "empty": "데이터 없음",
    "error": "오류",
    "loading": "불러오는 중",
    "available": "연결됨",
    "partial": "일부 연결",
    "missing": "누락",
    "mock": "데모 데이터",
    "compliant": "시점 기준 충족",
    "review_required": "검토 필요",
    "fresh": "최신",
}

SEVERITY_LABELS = {
    "info": "정보",
    "warning": "주의",
    "critical": "긴급",
    "positive": "긍정",
    "negative": "부정",
    "neutral": "중립",
}

SIGNAL_LABELS = {
    "tailwind": "순풍",
    "headwind": "역풍",
    "neutral": "중립",
    "missing": "데이터 부족",
    "supportive": "우호적",
    "pressure": "부담",
    "cheap": "저평가",
    "fair": "적정",
    "expensive": "고평가",
    "mixed": "혼재",
    "top_quality": "품질 우수",
    "improving": "개선",
    "watch": "관찰",
    "deteriorating": "악화",
    "accumulation": "누적 매수",
    "distribution": "분산 매도",
    "fragile": "취약",
}

RATING_LABELS = {
    "STRONG_BUY_CANDIDATE": "강력 매수 후보",
    "BUY_CANDIDATE": "매수 후보",
    "WATCH": "관심",
    "HOLD": "보유",
    "AVOID": "제외 검토",
    "HIGH_RISK_EXCLUDE": "고위험 제외",
}

ACTION_LABELS = {
    "BUY": "매수 후보",
    "ADD": "비중 확대",
    "HOLD": "보유",
    "TRIM": "일부 축소",
    "SELL": "매도 검토",
    "AVOID": "제외 검토",
    "EXCLUDE": "투자 제외",
}

ASSET_CLASS_LABELS = {
    "stocks": "주식",
    "bonds": "채권",
    "mutualFunds": "펀드",
    "cash": "현금",
    "crypto": "가상자산",
    "alternatives": "대체투자",
    "Cash": "현금",
    "Unknown": "미분류",
    "Unclassified": "미분류",
}

DART_CATEGORY_LABELS = {
    "share_buyback": "자사주 매입",
    "treasury_stock_cancellation": "자사주 소각",
    "dividend_increase": "배당 확대",
    "large_contract": "대형 계약",
    "earnings_improvement": "실적 개선",
    "value_up_plan": "밸류업 계획",
    "strategic_partnership": "전략적 제휴",
    "regulatory_approval": "규제 승인",
    "paid_in_capital_increase": "유상증자",
    "cb_bw_eb_issuance": "CB/BW/EB 발행",
    "dilution_risk": "희석 위험",
    "audit_issue": "감사 이슈",
    "litigation": "소송",
    "embezzlement_breach_of_trust": "횡령·배임",
    "trading_halt": "거래정지",
    "administrative_issue": "관리종목 이슈",
    "delisting_risk": "상장폐지 위험",
    "earnings_shock": "실적 쇼크",
    "other": "수동 검토",
}

TEXT_LABELS = {
    "Total Portfolio Value": "총 포트폴리오 가치",
    "Portfolio data": "포트폴리오 데이터",
    "Market price data": "시장가격 데이터",
    "Valuation data": "밸류에이션 데이터",
    "Financial statement data": "재무제표 데이터",
    "DART disclosure data": "DART 공시 데이터",
    "Macro data": "매크로 데이터",
    "FX/rates data": "환율·금리 데이터",
    "Investor flow data": "투자자 수급 데이터",
    "Short-selling data": "공매도 데이터",
    "Cash Ratio": "현금 비중",
    "Largest Single Holding": "최대 단일 종목",
    "Top 10 Concentration": "상위 10개 집중도",
    "Volatility Proxy": "변동성 추정치",
    "Max Drawdown Proxy": "최대 낙폭 추정치",
    "Capital Risk Gates": "자본 투입 전 리스크 점검",
    "before adding capital": "추가 자금 투입 전 확인",
    "Allocation Map": "배분 지도",
    "asset / market / sector / currency": "자산군 / 시장 / 섹터 / 통화",
    "Asset": "자산군",
    "Sector": "섹터",
    "Currency": "통화",
    "Top Holdings": "상위 보유종목",
    "top risk drivers": "주요 리스크 기여 종목",
    "Risk Alerts": "리스크 알림",
    "review gates": "검토 기준",
    "Checklist": "점검 목록",
    "explainable checks": "근거 기반 점검",
    "No order execution": "주문 실행 없음",
    "No order API": "주문 API 없음",
    "No auto trading": "자동매매 없음",
    "No recommendation": "추천 아님",
    "Context only": "맥락 정보",
    "Review candidates only": "검토 후보만",
    "Feature layer": "특징 데이터",
    "Refresh & Trust": "갱신·신뢰도",
    "metadata contract": "메타데이터 기준",
    "Latest refresh": "최근 갱신",
    "API key warnings": "API 키 경고",
    "Data Gaps": "데이터 공백",
    "stale / missing": "오래됨 / 누락",
    "Stale warnings": "오래된 데이터 경고",
    "Missing modules": "누락 모듈",
    "Point-in-Time Gate": "시점 기준 점검",
    "anti look-ahead": "미래 데이터 차단",
    "Compliance status": "준수 상태",
    "Source Coverage Table": "데이터 출처 커버리지",
    "Regime Score": "시장 국면 점수",
    "risk-on / risk-off": "위험선호 / 위험회피",
    "Macro Heatmap": "매크로 히트맵",
    "tailwinds / headwinds": "순풍 / 역풍",
    "Recent Changes": "최근 변화",
    "what moved": "변화 요인",
    "Sector Tailwind Table": "섹터 순풍·역풍 표",
    "context only, no stock recommendation": "맥락 정보이며 종목 추천 아님",
    "Shock Indicators": "충격 지표",
    "FX / rates": "환율 / 금리",
    "Portfolio KRW impact": "포트폴리오 원화 영향",
    "FX & Rates Board": "환율·금리 보드",
    "source-aware indicators": "출처 확인 지표",
    "Portfolio & Sector Impact": "포트폴리오·섹터 영향",
    "interpretation": "해석",
    "KRW weakness impact": "원화 약세 영향",
    "USD asset translation": "달러 자산 환산 효과",
    "Exporter tailwind/headwind": "수출주 환율 순풍·역풍",
    "Growth stock rate pressure": "성장주 금리 부담",
    "Bank / insurance sensitivity": "은행·보험 금리 민감도",
    "Korea rate proxy": "한국 금리 추정",
    "U.S. 10Y rate proxy": "미국 10년물 금리 추정",
    "KOSPI momentum": "KOSPI 모멘텀",
    "KOSDAQ momentum": "KOSDAQ 모멘텀",
    "Market Valuation Summary": "시장 밸류에이션 요약",
    "relative cheapness": "상대 저평가",
    "Market percentile": "시장 분위",
    "Cheap / expensive count": "저평가 / 고평가 수",
    "Cheapest Quality Candidates": "품질 대비 저평가 후보",
    "placeholder for future alpha ranking": "향후 알파 랭킹 입력값",
    "Expensive / Overheated List": "고평가·과열 목록",
    "review risk": "리스크 점검",
    "Sector Valuation Heatmap": "섹터 밸류에이션 히트맵",
    "sector-relative": "섹터 대비",
    "Valuation Percentile Table": "밸류에이션 분위 표",
    "PER / PBR / history": "PER / PBR / 과거 대비",
    "Quality Score": "품질 점수",
    "durability composite": "지속성 종합",
    "Average quality": "평균 품질",
    "Point-in-time rule": "시점 기준 규칙",
    "Top Quality Stocks": "품질 상위 종목",
    "durability": "내구성",
    "Deteriorating Quality": "품질 악화 종목",
    "Cheap Quality Stocks": "저평가 고품질 종목",
    "quality + valuation context": "품질 + 밸류에이션 맥락",
    "Accounting Red Flags": "회계 위험 신호",
    "accrual / cash flow / leverage": "발생액 / 현금흐름 / 레버리지",
    "FCF Conversion Ranking": "FCF 전환율 순위",
    "cash conversion": "현금 전환",
    "ROIC Versus Valuation": "ROIC 대비 밸류에이션",
    "chart-style table": "차트형 표",
    "Source filing": "공시 원문",
    "Catalyst Overview": "촉매 요약",
    "point-in-time DART": "시점 기준 DART",
    "Tracked disclosures": "추적 공시",
    "Latest High-Materiality": "최근 고중요도 공시",
    "materiality score": "중요도 점수",
    "Positive Catalysts": "긍정 촉매",
    "shareholder return / growth": "주주환원 / 성장",
    "Negative Risk List": "부정 리스크 목록",
    "Dilution Watchlist": "희석 위험 관찰목록",
    "capital increase / CB / BW / EB": "증자 / CB / BW / EB",
    "Shareholder Return": "주주환원",
    "buyback / cancellation / dividend / value-up": "자사주 / 소각 / 배당 / 밸류업",
    "Event Timeline": "이벤트 타임라인",
    "recent receipts": "최근 접수",
    "Flow / Short Overview": "수급·공매도 요약",
    "KRX microstructure": "KRX 수급 구조",
    "Tracked names": "추적 종목",
    "Execution safety": "실행 안전성",
    "Foreign Accumulation": "외국인 누적 매수",
    "5D / 20D / 60D flow": "5일 / 20일 / 60일 수급",
    "Institution Accumulation": "기관 누적 매수",
    "institution / pension / program": "기관 / 연기금 / 프로그램",
    "Retail Crowding": "개인 쏠림",
    "individual net buy pressure": "개인 순매수 압력",
    "Short Squeeze Candidates": "숏스퀴즈 후보",
    "short pressure + positive flow": "공매도 압력 + 긍정 수급",
    "Fragile Long Candidates": "취약 롱 후보",
    "distribution + short + liquidity": "분산 매도 + 공매도 + 유동성",
    "Distribution Risk List": "매도 압력 위험 목록",
    "foreign/institution sell + retail buy": "외국인·기관 매도 + 개인 매수",
    "Sector Flow Heatmap": "섹터 수급 히트맵",
    "foreign / institution / retail / short / liquidity": "외국인 / 기관 / 개인 / 공매도 / 유동성",
    "BaselineRuleScore": "기본 규칙 점수",
    "Ranked stocks": "평가 종목",
    "Model discipline": "모델 원칙",
    "Top Forward Alpha Rows": "상위 미래 알파 후보",
    "explainable ranking": "설명 가능한 랭킹",
    "High-Risk Exclusions": "고위험 제외 종목",
    "override wins over score": "점수보다 위험 차단 우선",
    "Watchlist": "관심 목록",
    "needs confirmation": "확인 필요",
    "Feature Components": "특징 점수 분해",
    "score decomposition": "점수 구성",
    "Optimizer Summary": "최적화 요약",
    "long-only / no leverage": "롱온리 / 레버리지 없음",
    "Recommendations": "검토 항목",
    "Risk constraints": "리스크 제약",
    "Current vs Target Weights": "현재 비중 vs 목표 비중",
    "review actions only": "검토용 액션만",
    "Rejected Candidates": "제외 후보",
    "risk gates": "리스크 기준",
    "Alert Center": "알림 센터",
    "monitoring rules": "모니터링 규칙",
    "Stress Scenario Table": "스트레스 시나리오 표",
    "risk proxy": "리스크 추정",
    "Explanation Drawer": "설명 패널",
    "constraint logic": "제약 로직",
    "How targets are created": "목표 비중 산출 방식",
}

EXACT_SENTENCES = {
    "NEUTRAL": "중립",
    "HIGH_FX_PRESSURE": "환율 압력 높음",
    "ELEVATED_FX_PRESSURE": "환율 압력 상승",
    "HIGH_RATE_PRESSURE": "금리 압력 높음",
    "ELEVATED_RATE_PRESSURE": "금리 압력 상승",
    "No allocation data.": "배분 데이터가 없습니다.",
    "No holdings data.": "보유종목 데이터가 없습니다.",
    "No major alert": "중요 알림 없음",
    "Current thresholds do not flag concentration, cash, or liquidity warnings.": "현재 기준에서는 집중도, 현금, 유동성 경고가 없습니다.",
    "Portfolio risk data is being prepared.": "포트폴리오 리스크 데이터를 준비 중입니다.",
    "Portfolio risk calculation failed.": "포트폴리오 리스크 계산에 실패했습니다.",
    "Enter holdings CSV in the sidebar to calculate risk concentration.": "사이드바에 보유종목 CSV를 입력하면 리스크 집중도를 계산합니다.",
    "No source coverage rows": "출처 커버리지 행 없음",
    "Metadata adapters did not return source coverage.": "메타데이터 어댑터가 출처 커버리지를 반환하지 않았습니다.",
    "No additional note.": "추가 메모 없음",
    "All rows include source, endpoint, as_of_date, available_at, fetched_at, confidence, stale, and missing flags.": "모든 행은 출처, 엔드포인트, 기준일, 이용 가능 시각, 수집 시각, 신뢰도, 오래됨, 누락 여부를 포함합니다.",
    "Only key names are shown. Secret values are never rendered.": "키 이름만 표시하며 비밀값은 화면에 표시하지 않습니다.",
    "DART and macro data must use receipt_date, available_at, or fetched_at before analytics consume them.": "DART와 매크로 데이터는 분석에 쓰기 전 접수일, 이용 가능 시각, 수집 시각을 확인해야 합니다.",
    "This is a metadata review gate, not a trading signal.": "이는 메타데이터 점검 기준이며 매매 신호가 아닙니다.",
    "No macro indicators available.": "매크로 지표가 없습니다.",
    "No sector tailwind data available.": "섹터 순풍·역풍 데이터가 없습니다.",
    "No recent macro change": "최근 매크로 변화 없음",
    "No indicator changed enough to flag a recent move.": "최근 변화로 표시할 만큼 크게 움직인 지표가 없습니다.",
    "Market regime data is being prepared.": "시장 국면 데이터를 준비 중입니다.",
    "Market regime calculation failed.": "시장 국면 계산에 실패했습니다.",
    "Connect market or macro sources to calculate the regime radar.": "시장 또는 매크로 출처를 연결하면 국면 레이더를 계산합니다.",
    "No FX/rates indicators available.": "환율·금리 지표가 없습니다.",
    "No interpretation rows available.": "해석 행이 없습니다.",
    "KRW/rates/FX data is being prepared.": "원화·금리·환율 데이터를 준비 중입니다.",
    "KRW/rates/FX calculation failed.": "원화·금리·환율 계산에 실패했습니다.",
    "Connect FX or rates sources to calculate this dashboard.": "환율 또는 금리 출처를 연결하면 이 대시보드를 계산합니다.",
    "USD/KRW pressure and one-day move.": "USD/KRW 압력과 1일 변화를 반영합니다.",
    "Korea and U.S. rate pressure for equity valuations.": "한국과 미국 금리가 주식 밸류에이션에 주는 부담을 봅니다.",
    "Estimated only when non-KRW holdings exist.": "원화 외 자산이 있을 때만 추정합니다.",
    "No row satisfies the current valuation and quality filter.": "현재 밸류에이션·품질 필터를 만족하는 행이 없습니다.",
    "No sector valuation data available.": "섹터 밸류에이션 데이터가 없습니다.",
    "No valuation percentile rows available.": "밸류에이션 분위 행이 없습니다.",
    "Valuation data is being prepared.": "밸류에이션 데이터를 준비 중입니다.",
    "Valuation calculation failed.": "밸류에이션 계산에 실패했습니다.",
    "Connect KRX/OpenDART valuation sources to calculate this panel.": "KRX/OpenDART 밸류에이션 출처를 연결하면 이 패널을 계산합니다.",
    "Lower percentile means cheaper versus history.": "분위가 낮을수록 과거 대비 저평가입니다.",
    "No buy/sell recommendation is generated.": "매수·매도 추천을 생성하지 않습니다.",
    "No company meets this quality bucket.": "이 품질 구간에 해당하는 기업이 없습니다.",
    "No FCF conversion data available.": "FCF 전환율 데이터가 없습니다.",
    "No ROIC versus valuation points available.": "ROIC 대비 밸류에이션 데이터가 없습니다.",
    "Fundamental quality data is being prepared.": "펀더멘털 품질 데이터를 준비 중입니다.",
    "Fundamental quality calculation failed.": "펀더멘털 품질 계산에 실패했습니다.",
    "Connect OpenDART financial statements with available_at timestamps.": "available_at 시각이 포함된 OpenDART 재무제표를 연결하세요.",
    "Profitability, cash-flow quality, balance sheet, growth, and accounting risk.": "수익성, 현금흐름 품질, 재무 안전성, 성장성, 회계 위험을 반영합니다.",
    "Uses available_at / receipt_date only.": "available_at / receipt_date 기준만 사용합니다.",
    "Fiscal period end date is not treated as data availability.": "회계기간 종료일을 데이터 이용 가능일로 보지 않습니다.",
    "No matching DART disclosure event is available.": "조건에 맞는 DART 공시 이벤트가 없습니다.",
    "No event timeline available.": "이벤트 타임라인이 없습니다.",
    "DART catalyst events are being prepared.": "DART 촉매 이벤트를 준비 중입니다.",
    "DART catalyst calculation failed.": "DART 촉매 계산에 실패했습니다.",
    "Connect OpenDART list/detail events with receipt_date or available_at timestamps.": "receipt_date 또는 available_at 시각이 포함된 OpenDART 목록/상세 이벤트를 연결하세요.",
    "Future filings are excluded from catalyst features.": "미래 공시는 촉매 특징에서 제외됩니다.",
    "No matching flow or short-pressure item is available.": "조건에 맞는 수급·공매도 압력 항목이 없습니다.",
    "No sector flow data available.": "섹터 수급 데이터가 없습니다.",
    "Investor flow and short-pressure data is being prepared.": "투자자 수급과 공매도 압력 데이터를 준비 중입니다.",
    "Flow and short-pressure calculation failed.": "수급·공매도 압력 계산에 실패했습니다.",
    "Connect KRX investor flow, short-selling, and liquidity data.": "KRX 투자자 수급, 공매도, 유동성 데이터를 연결하세요.",
    "No order execution or deterministic trade instruction.": "주문 실행이나 확정적 매매 지시는 없습니다.",
    "Use as features for future alpha ranking and risk review.": "향후 알파 랭킹과 리스크 검토의 특징값으로 사용합니다.",
    "No matching forward alpha row is available.": "조건에 맞는 미래 알파 행이 없습니다.",
    "No component rows available.": "구성 점수 행이 없습니다.",
    "Forward alpha feature stack is being prepared.": "미래 알파 특징 묶음을 준비 중입니다.",
    "Forward alpha ranking calculation failed.": "미래 알파 랭킹 계산에 실패했습니다.",
    "Connect valuation, quality, DART, flow, macro, liquidity, and freshness features.": "밸류에이션, 품질, DART, 수급, 매크로, 유동성, 신선도 특징을 연결하세요.",
    "No historical return chasing. No automatic trading.": "과거 수익률 추종이 아니며 자동매매도 없습니다.",
    "No optimizer row is available.": "최적화 행이 없습니다.",
    "No active portfolio alerts.": "활성 포트폴리오 알림이 없습니다.",
    "No stress scenarios available.": "스트레스 시나리오가 없습니다.",
    "Portfolio optimizer and alert rules are being prepared.": "포트폴리오 최적화와 알림 규칙을 준비 중입니다.",
    "Portfolio optimizer calculation failed.": "포트폴리오 최적화 계산에 실패했습니다.",
    "Connect holdings and Forward Alpha Ranking output.": "보유종목과 미래 알파 랭킹 결과를 연결하세요.",
    "ForwardAlphaScore and ConfidenceScore set initial target weight; liquidity, sector caps, cash buffer, and severe risk flags cap or exclude positions.": "미래 알파 점수와 신뢰도가 초기 목표 비중을 정하고, 유동성·섹터 한도·현금 버퍼·중대 위험 플래그가 비중을 제한하거나 제외합니다.",
    "Actions are portfolio review labels only. No automatic order execution is implemented.": "액션은 포트폴리오 검토 라벨일 뿐이며 자동 주문 실행은 구현되어 있지 않습니다.",
    "Check ownership, concentration, liquidity, cash buffer, and data freshness before adding capital.": "추가 자금 투입 전 보유 구성, 집중도, 유동성, 현금 버퍼, 데이터 신선도를 점검합니다.",
    "Source coverage is visible for portfolio, market, filings, macro, FX/rates, flow, and short pressure data.": "포트폴리오, 시장가격, 공시, 매크로, 환율·금리, 수급, 공매도 데이터의 출처 커버리지를 표시합니다.",
    "DART disclosure catalysts and risks are classified using point-in-time receipt_date / available_at.": "DART 공시 촉매와 위험은 시점 기준 receipt_date / available_at으로 분류합니다.",
    "Investor flow, liquidity, and short-pressure features are ready for future alpha ranking.": "수급, 유동성, 공매도 압력 특징값을 향후 알파 랭킹에 사용할 수 있습니다.",
    "BaselineRuleScore ranks forward alpha candidates from economically meaningful features. No automatic trading is implemented.": "기본 규칙 점수는 경제적으로 의미 있는 특징으로 미래 알파 후보를 정렬합니다. 자동매매는 없습니다.",
    "Risk-controlled target weights and monitoring alerts are ready. No automatic order execution is implemented.": "리스크 제어 목표 비중과 모니터링 알림을 표시합니다. 자동 주문 실행은 없습니다.",
    "No holdings source is connected.": "보유종목 출처가 연결되어 있지 않습니다.",
    "No valuation source is available.": "사용 가능한 밸류에이션 출처가 없습니다.",
    "No financial statement source is available.": "사용 가능한 재무제표 출처가 없습니다.",
    "No investor flow, short-selling, or liquidity data is available.": "사용 가능한 수급·공매도·유동성 데이터가 없습니다.",
    "A weaker KRW may support export revenue translation but can pressure foreign outflows and input costs.": "원화 약세는 수출 매출 환산에 우호적일 수 있지만 외국인 자금 유출과 원가 부담을 높일 수 있습니다.",
    "Estimated portfolio KRW translation impact is N/A without non-KRW holdings.": "원화 외 통화 보유자산이 없어 포트폴리오 환산 효과를 계산할 수 없습니다.",
    "FX is a context input only; revenue mix, hedging, and input costs must be checked separately.": "환율은 맥락 지표이며 매출 통화 구성, 환헤지, 원재료 비용을 별도로 확인해야 합니다.",
    "Higher discount rates can pressure valuation multiples for growth stocks.": "할인율 상승은 성장주의 밸류에이션 배수에 부담을 줄 수 있습니다.",
    "Rate level can help financial margins, but curve shape and credit risk decide the final effect.": "금리 수준은 금융업 마진에 우호적일 수 있지만 최종 영향은 장단기 금리차와 신용위험에 달려 있습니다.",
    "Domestic demand / importers": "내수주·수입주",
    "Export translation tailwind": "수출 매출 환산 순풍",
    "KRW assets": "원화 자산",
    "USD assets after KRW rebound": "원화 반등 시 달러 자산",
    "Domestic stocks": "내수주",
    "Exporters losing FX tailwind": "환율 순풍이 약해지는 수출주",
    "Long-duration growth": "장기 성장주",
    "Banks if curve compresses": "장단기 금리차 축소 시 은행",
    "Borrowers / duration assets": "차입기업·장기 듀레이션 자산",
    "Net-interest-margin beneficiaries": "순이자마진 수혜 금융주",
    "No current source snapshot is available.": "현재 사용할 수 있는 출처 스냅샷이 없습니다.",
    "One or more snapshots are stale.": "하나 이상의 스냅샷이 오래되었습니다.",
    "Valuation adapter is not connected in this module.": "이 모듈에는 밸류에이션 어댑터가 연결되어 있지 않습니다.",
    "Macro release availability must be stored before backtests use it.": "백테스트에 쓰기 전 매크로 발표 이용 가능 시각을 저장해야 합니다.",
    "Investor flow source is not connected yet.": "투자자 수급 출처가 아직 연결되지 않았습니다.",
    "Short-selling source is not connected yet.": "공매도 출처가 아직 연결되지 않았습니다.",
    "No DART disclosure events are available.": "DART 공시 이벤트가 없습니다.",
    "No point-in-time DART disclosures are available for the selected cutoff.": "선택 기준시점에 사용할 수 있는 DART 공시가 없습니다.",
    "No point-in-time feature rows are available for ranking.": "시점 기준을 충족하는 랭킹 특징 데이터가 없습니다.",
    "Optimizer excludes or avoids severe-risk candidates before assigning target weights.": "최적화는 목표 비중 산정 전에 중대 위험 후보를 제외하거나 회피 처리합니다.",
    "Mock holdings and optimizer outputs are shown until real portfolio holdings are connected.": "실제 보유종목 연결 전까지 데모 보유종목과 최적화 결과를 표시합니다.",
}

PHRASE_REPLACEMENTS = (
    ("risk alert(s) require review before adding more capital.", "개 리스크 알림을 추가 자금 투입 전 검토해야 합니다."),
    ("missing source(s)", "개 출처 누락"),
    ("missing API key group(s).", "개 API 키 그룹 누락."),
    ("stale source(s) need refresh.", "개 오래된 출처는 갱신이 필요합니다."),
    ("Mock OpenDART disclosure catalysts are shown until real DART event adapters are connected.", "실제 DART 이벤트 어댑터 연결 전까지 OpenDART 데모 공시 촉매를 표시합니다."),
    ("Some disclosure rows are missing source filing references; manual verification is required.", "일부 공시 행에 원문 참조가 없어 수동 확인이 필요합니다."),
    ("Mock KRX investor flow and short-selling context is shown until real adapters are connected.", "실제 어댑터 연결 전까지 KRX 수급·공매도 데모 맥락을 표시합니다."),
    ("Some flow or short-selling fields are missing; rankings use available fields only.", "일부 수급·공매도 항목이 누락되어 사용 가능한 필드만 반영합니다."),
    ("Mock feature-stack alpha ranking is shown until real KRX/OpenDART/macro adapters are connected.", "실제 KRX/OpenDART/매크로 어댑터 연결 전까지 데모 특징 기반 알파 랭킹을 표시합니다."),
    ("High-risk override is active; severe risk rows cannot receive Buy candidate ratings.", "고위험 차단 규칙이 활성화되어 중대 위험 행은 매수 후보 등급을 받을 수 없습니다."),
    ("Fundamental quality scores are ready for later ranking modules. No buy/sell recommendation is generated.", "펀더멘털 품질 점수는 후속 랭킹 모듈 입력값입니다. 매수·매도 추천은 생성하지 않습니다."),
    ("Mock OpenDART-style financial quality data is shown until real financial statement adapters are connected.", "실제 재무제표 어댑터 연결 전까지 OpenDART 형식의 데모 재무 품질 데이터를 표시합니다."),
    ("Some financial statement fields are missing; quality scores use available point-in-time data only.", "일부 재무제표 필드가 누락되어 사용 가능한 시점 기준 데이터만 품질 점수에 반영합니다."),
    ("Mock KRX/OpenDART valuation context is shown until real valuation adapters are connected.", "실제 밸류에이션 어댑터 연결 전까지 KRX/OpenDART 데모 밸류에이션 맥락을 표시합니다."),
    ("Some valuation fields are missing; percentile and relative rankings use available data only.", "일부 밸류에이션 필드가 누락되어 사용 가능한 데이터만 분위와 상대 순위에 반영합니다."),
    ("Valuation context is ready for future alpha ranking. No buy/sell recommendation is generated.", "밸류에이션 맥락은 향후 알파 랭킹 입력값입니다. 매수·매도 추천은 생성하지 않습니다."),
    ("Required feature panels are not available.", "필수 특징 패널을 사용할 수 없습니다."),
    ("Forward alpha ranking requires valuation, quality, DART catalyst, flow/short, macro, liquidity, and freshness features.", "미래 알파 랭킹에는 밸류에이션, 품질, DART 촉매, 수급·공매도, 매크로, 유동성, 신선도 특징이 필요합니다."),
    ("FX", "환율"),
    ("rates", "금리"),
    ("with score", "점수"),
    ("Labels:", "라벨:"),
)


def _lookup(mapping: dict[str, str], value: Any) -> str:
    text = "" if value is None else str(value)
    return mapping.get(text, mapping.get(text.lower(), text))


def module_title(value: Any) -> str:
    return _lookup(MODULE_TITLES, value)


def status_label(value: Any) -> str:
    return _lookup(STATUS_LABELS, value)


def severity_label(value: Any) -> str:
    return _lookup(SEVERITY_LABELS, value)


def signal_label(value: Any) -> str:
    return _lookup(SIGNAL_LABELS, value)


def rating_label(value: Any) -> str:
    return _lookup(RATING_LABELS, value)


def action_label(value: Any) -> str:
    return _lookup(ACTION_LABELS, value)


STOCK_NAME_LABELS = {
    "Samsung Electronics": "삼성전자",
    "SK hynix": "SK하이닉스",
    "KB Financial": "KB금융",
    "NAVER": "네이버",
    "HMM": "HMM",
    "Doosan Enerbility": "두산에너빌리티",
}

SECTOR_LABELS = {
    "Semiconductors": "반도체",
    "Banks / Insurance": "은행·보험",
    "Internet / Growth": "인터넷·성장주",
    "Industrials": "산업재",
    "Materials / Industrials": "소재·산업재",
    "Semiconductor": "반도체",
    "Defensives": "경기방어주",
    "Autos / Exporters": "자동차·수출주",
    "Autos·Exporters": "자동차·수출주",
}

SECTOR_ENVIRONMENT_LABELS = {
    "tailwind": {
        "title": "강세 섹터 TOP 3",
        "subtitle": "상승 모멘텀 우위",
        "positive_label": "상승 촉매",
        "negative_label": "하방 리스크",
        "empty_message": "현재 강세 기준을 충족한 섹터가 없습니다.",
    },
    "headwind": {
        "title": "약세 섹터 TOP 3",
        "subtitle": "하방 리스크 우위",
        "positive_label": "상승 촉매",
        "negative_label": "하방 리스크",
        "empty_message": "현재 약세 기준에 해당하는 섹터가 없습니다.",
    },
    "neutral": {
        "title": "중립 섹터 TOP 3",
        "subtitle": "추세 확인 필요",
        "positive_label": "상승 촉매",
        "negative_label": "하방 리스크",
        "empty_message": "현재 중립 구간에 해당하는 섹터가 없습니다.",
    },
}

SECTOR_FACTOR_LABELS = {
    "semi exports": "반도체 수출",
    "export cycle": "업황 사이클",
    "exports": "수출 모멘텀",
    "weak KRW": "원화 약세 수혜",
    "risk appetite": "위험선호 국면",
    "rates": "금리 부담",
    "rate level": "금리 수준",
    "risk-off": "위험회피 국면",
    "risk buffer": "경기 방어력",
    "export demand": "수출 수요",
    "FX pressure": "환율 부담",
    "환율 pressure": "환율 부담",
}

ALPHA_DRIVER_LABELS = {
    "valuation data unavailable": "밸류에이션 데이터 부족",
    "PBR below 1": "PBR 1배 미만",
    "cheap versus history": "과거 대비 저평가",
    "expensive versus history": "과거 대비 고평가",
    "fundamental quality unavailable": "펀더멘털 품질 데이터 부족",
    "high fundamental quality": "펀더멘털 품질 우수",
    "ROIC above quality threshold": "ROIC가 품질 기준 상회",
    "strong FCF conversion": "FCF 전환율 우수",
    "quality deteriorating": "품질 지표 악화",
    "no recent DART catalyst": "최근 DART 촉매 부재",
    "shareholder return / value-up event": "주주환원·밸류업 이벤트",
    "smart money flow unavailable": "수급 데이터 부족",
    "foreign accumulation": "외국인 누적 순매수",
    "institution accumulation": "기관 누적 순매수",
    "short squeeze setup candidate": "숏스퀴즈 가능성 후보",
    "distribution risk elevated": "분산 매도 위험 상승",
    "fragile long structure": "취약한 롱 포지션 구조",
    "macro regime unavailable": "매크로 국면 데이터 부족",
    "sector-specific macro unavailable": "섹터별 매크로 데이터 부족",
    "risk appetite": "위험선호",
    "exports": "수출",
    "semi exports": "반도체 수출",
    "export cycle": "수출 사이클",
    "export demand": "수출 수요",
    "rate level": "금리 수준",
    "stale data risk": "오래된 데이터 위험",
}

RISK_FLAG_LABELS = {
    "severe_accounting_risk": "중대 회계 위험",
    "severe_dilution_risk": "중대 희석 위험",
    "delisting_or_administrative_risk": "상장폐지·관리종목 위험",
    "liquidity_risk": "유동성 위험",
    "stale_data_risk": "오래된 데이터 위험",
    "stale_feature_data": "오래된 특징 데이터",
    "fallback_feature_stack": "보조 특징 데이터 사용",
    "high_risk_override_active": "고위험 차단 규칙 적용",
    "low_cfo_to_net_income": "순이익 대비 영업현금흐름 약함",
    "high_accrual_ratio": "발생주의 비중 높음",
    "negative_fcf_conversion": "FCF 전환율 음수",
    "high_debt_to_equity": "부채비율 부담",
    "low_interest_coverage": "이자보상배율 약함",
    "operating_income_deterioration": "영업이익 악화",
}

CLEAN_DART_CATEGORY_LABELS = {
    "share_buyback": "자사주 매입",
    "treasury_stock_cancellation": "자사주 소각",
    "dividend_increase": "배당 확대",
    "large_contract": "대규모 수주",
    "earnings_improvement": "실적 개선",
    "value_up_plan": "밸류업 계획",
    "strategic_partnership": "전략적 제휴",
    "regulatory_approval": "규제 승인",
    "paid_in_capital_increase": "유상증자",
    "cb_bw_eb_issuance": "CB/BW/EB 발행",
    "dilution_risk": "주식 희석 위험",
    "audit_issue": "감사 이슈",
    "litigation": "소송",
    "embezzlement_breach_of_trust": "횡령·배임",
    "trading_halt": "거래정지",
    "administrative_issue": "관리종목 이슈",
    "delisting_risk": "상장폐지 위험",
    "earnings_shock": "실적 쇼크",
    "other": "기타 공시",
}

MACRO_DRIVER_LABELS = {
    "semi exports": "반도체 수출",
    "export cycle": "수출 사이클",
    "rates": "금리 부담",
    "risk appetite": "위험선호",
    "rate level": "금리 레벨",
    "risk-off": "위험회피",
    "export demand": "수출 수요",
    "FX pressure": "환율 부담",
    "RISK_ON": "위험선호",
    "RISK_OFF": "위험회피",
    "EXPORT_UPCYCLE": "수출 개선",
    "EXPORT_DOWNTURN": "수출 둔화",
    "RATE_PRESSURE": "금리 부담",
    "FX_PRESSURE": "환율 부담",
    "LIQUIDITY_SUPPORT": "유동성 지원",
    "STAGFLATION_RISK": "스태그플레이션 위험",
}


def stock_name_label(value: Any) -> str:
    return _lookup(STOCK_NAME_LABELS, value)


def sector_label(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return SECTOR_LABELS.get(text, text.replace(" / ", "·"))


def sector_environment_labels(value: Any) -> dict[str, str]:
    """Return display-only labels without changing the internal regime key."""
    key = "" if value is None else str(value).strip().lower()
    return dict(SECTOR_ENVIRONMENT_LABELS.get(key, SECTOR_ENVIRONMENT_LABELS["neutral"]))


def sector_driver_text(values: Iterable[Any] | None, *, role: str) -> str:
    """Normalize sector drivers while preserving the source model semantics."""
    items = [str(item).strip() for item in (values or ()) if str(item).strip()]
    if not items:
        return "제한적" if role == "negative" else "확인되지 않음"

    rendered: list[str] = []
    consumed: set[str] = set()
    item_set = set(items)
    if {"semi exports", "export cycle"}.issubset(item_set):
        rendered.append("반도체 수출·업황 사이클")
        consumed.update({"semi exports", "export cycle"})
    if {"exports", "weak KRW"}.issubset(item_set):
        rendered.append("수출 모멘텀·원화 약세 수혜")
        consumed.update({"exports", "weak KRW"})

    for item in items:
        if item in consumed:
            continue
        translated = SECTOR_FACTOR_LABELS.get(item, alpha_driver_label(item))
        if translated == item and re.search(r"[A-Za-z]", item):
            translated = "확인 필요"
        if translated not in rendered:
            rendered.append(translated)
    return " · ".join(rendered) if rendered else ("제한적" if role == "negative" else "확인되지 않음")


def sector_empty_state(
    value: Any,
    *,
    tailwind_min_score: int,
    headwind_max_score: int,
) -> tuple[str, str]:
    labels = sector_environment_labels(value)
    key = "" if value is None else str(value).strip().lower()
    if key == "tailwind":
        criterion = f"기준: 섹터 환경 점수 {tailwind_min_score}점 이상"
    elif key == "headwind":
        criterion = f"기준: 섹터 환경 점수 {headwind_max_score}점 이하"
    else:
        criterion = f"기준: 섹터 환경 점수 {headwind_max_score + 1}~{tailwind_min_score - 1}점"
    return labels["empty_message"], criterion


def clean_dart_category_label(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return CLEAN_DART_CATEGORY_LABELS.get(text, dart_category_label(text))


def risk_flag_label(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    return RISK_FLAG_LABELS.get(text, ALPHA_DRIVER_LABELS.get(text, text.replace("_", " ")))


def _macro_driver_label(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return MACRO_DRIVER_LABELS.get(text, text.replace("_", " "))


def alpha_driver_label(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    if text in ALPHA_DRIVER_LABELS:
        return ALPHA_DRIVER_LABELS[text]
    if text in RISK_FLAG_LABELS:
        return RISK_FLAG_LABELS[text]
    prefix_map = (
        ("positive DART catalyst:", "긍정 공시 촉매"),
        ("negative DART risk:", "부정 공시 리스크"),
        ("macro tailwind:", "매크로 순풍"),
        ("macro headwind:", "매크로 역풍"),
        ("market regime", "시장 국면"),
    )
    for prefix, label in prefix_map:
        if text.startswith(prefix):
            remainder = text[len(prefix) :].strip()
            if "DART" in prefix:
                remainder = clean_dart_category_label(remainder)
            elif "macro" in prefix or prefix == "market regime":
                remainder = _macro_driver_label(remainder)
            return f"{label}: {remainder}" if remainder else label
    return ko_sentence(text.replace("_", " "))


def asset_class_label(value: Any) -> str:
    return _lookup(ASSET_CLASS_LABELS, value)


def dart_category_label(value: Any) -> str:
    text = "" if value is None else str(value)
    return DART_CATEGORY_LABELS.get(text, text.replace("_", " ").title())


def ui_label(value: Any) -> str:
    text = "" if value is None else str(value)
    return TEXT_LABELS.get(text, text)


def ko_sentence(value: Any) -> str:
    text = "" if value is None else str(value)
    if text in EXACT_SENTENCES:
        return EXACT_SENTENCES[text]
    translated = text
    for source, target in PHRASE_REPLACEMENTS:
        translated = translated.replace(source, target)
    translated = re.sub(
        r"(\d+)\s+risk alert\(s\) require review before adding more capital\.",
        r"\1개 리스크 알림을 추가 자금 투입 전 검토해야 합니다.",
        translated,
    )
    translated = re.sub(
        r"(\d+)\s+missing source\(s\),\s+(\d+)\s+missing API key group\(s\)\.",
        r"\1개 출처와 \2개 API 키 그룹이 누락되었습니다.",
        translated,
    )
    translated = re.sub(
        r"(\d+)\s+stale source\(s\) need refresh\.",
        r"\1개 오래된 출처는 갱신이 필요합니다.",
        translated,
    )
    translated = re.sub(r"(\d+)\s+개", r"\1개", translated)
    return translated


def source_meta_line(meta: Any | None) -> str:
    if meta is None:
        return "출처 N/A · 기준일 N/A · 수집 시각 N/A"
    source = getattr(meta, "source", None) or "N/A"
    as_of = getattr(meta, "as_of_date", None) or "N/A"
    fetched = getattr(meta, "fetched_at", None) or "N/A"
    stale = " · 오래된 데이터" if getattr(meta, "stale_data_flag", False) else ""
    missing = " · 누락 데이터" if getattr(meta, "missing_data_flag", False) else ""
    return f"출처 {source} · 기준일 {as_of} · 수집 시각 {fetched}{stale}{missing}"
