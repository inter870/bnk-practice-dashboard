from __future__ import annotations

import math
from typing import Any


GRADE_LABELS = {
    "STRONG_REVIEW": "강한 검토 후보",
    "BUY_REVIEW": "비중 보강 검토",
    "WATCHLIST": "관찰 후보",
    "NEUTRAL": "중립",
    "CAUTION": "주의",
    "EXCLUDE": "제외 후보",
}

MARKET_LABELS = {
    "KOSPI": "코스피",
    "KOSDAQ": "코스닥",
    "KONEX": "코넥스",
    "ETF": "ETF",
    "ETN": "ETN",
}

RISK_LABELS = {
    "low": "낮음",
    "medium": "주의",
    "high": "높음",
    "severe": "심각",
}


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def safeDisplay(value: Any, fallback: str = "-") -> str:
    if value is None:
        return fallback
    if isinstance(value, (float, int)) and not math.isfinite(float(value)):
        return fallback
    text = str(value)
    return fallback if not text.strip() or text.strip().lower() in {"nan", "inf", "-inf", "none", "<na>", "nat"} else text


def formatKoreanLargeNumber(value: Any) -> str:
    number = _finite(value)
    if number is None:
        return "-"
    sign = "-" if number < 0 else ""
    number = abs(number)
    if number >= 1_0000_0000_0000:
        return f"{sign}{number / 1_0000_0000_0000:,.1f}조"
    if number >= 1_0000_0000:
        return f"{sign}{number / 1_0000_0000:,.1f}억"
    if number >= 1_0000:
        return f"{sign}{number / 1_0000:,.1f}만"
    return f"{sign}{number:,.0f}"


def formatKRW(value: Any) -> str:
    text = formatKoreanLargeNumber(value)
    return "-" if text == "-" else f"{text}원"


def formatVolume(value: Any) -> str:
    text = formatKoreanLargeNumber(value)
    return "-" if text == "-" else f"{text}주"


def formatTradingValue(value: Any) -> str:
    return formatKRW(value)


def formatPercent(value: Any, signed: bool = False, digits: int = 1) -> str:
    number = _finite(value)
    if number is None:
        return "-"
    prefix = "+" if signed and number > 0 else ""
    return f"{prefix}{number * 100:.{digits}f}%"


def formatSignedPercent(value: Any, digits: int = 1) -> str:
    return formatPercent(value, signed=True, digits=digits)


def formatScore(value: Any) -> str:
    number = _finite(value)
    return "-" if number is None else f"{number:.0f}"


def formatKoreaTicker(code: str) -> str:
    digits = "".join(ch for ch in str(code) if ch.isdigit())
    return digits.zfill(6) if digits else str(code)


def formatMarketLabel(market: str) -> str:
    return MARKET_LABELS.get(str(market), str(market))


def formatRecommendationGrade(grade: str) -> str:
    return GRADE_LABELS.get(str(grade), str(grade))


def formatConfidence(value: Any) -> str:
    return formatPercent(value, digits=0)


def formatRiskBadge(risk: Any) -> str:
    return RISK_LABELS.get(str(risk or "").lower(), safeDisplay(risk))


def formatDate(value: Any) -> str:
    text = safeDisplay(value)
    if text == "-":
        return text
    return text[:10] if len(text) >= 10 else text


def fearGreedBand(score: Any) -> dict[str, str]:
    number = _finite(score)
    if number is None:
        return {
            "label": "N/A",
            "tone": "muted",
            "color": "#94a3b8",
            "advice": "데이터가 부족합니다. 시장 심리 지표가 확인될 때까지 보수적으로 해석합니다.",
        }
    if number <= 24:
        return {
            "label": "극단 공포",
            "tone": "danger",
            "color": "#ef4444",
            "advice": "공포가 매우 큰 구간입니다. 분할 접근과 손실 제한이 우선입니다.",
        }
    if number <= 44:
        return {
            "label": "공포",
            "tone": "warning",
            "color": "#f97316",
            "advice": "공포 우위 구간입니다. 공격적 추격보다 가격 확인과 분할 검토가 유리합니다.",
        }
    if number <= 55:
        return {
            "label": "중립",
            "tone": "muted",
            "color": "#94a3b8",
            "advice": "중립 구간입니다. 방향이 확인되기 전까지 비중을 크게 늘리지 않습니다.",
        }
    if number <= 74:
        return {
            "label": "탐욕",
            "tone": "positive",
            "color": "#a3e635",
            "advice": "탐욕 우위 구간입니다. 신규 진입은 신중히 검토하고 보유 종목 리스크를 점검합니다.",
        }
    return {
        "label": "극단 탐욕",
        "tone": "positive",
        "color": "#22c55e",
        "advice": "과열 구간입니다. 차익 실현과 비중 축소 후보를 점검합니다.",
    }


def heatmapBucket(score: Any) -> dict[str, str]:
    number = _finite(score)
    if number is None:
        return {"label": "N/A", "class": "heatmap-empty", "color": "#94a3b8"}
    if number >= 75:
        return {"label": "강함", "class": "heatmap-strong", "color": "#22c55e"}
    if number >= 60:
        return {"label": "양호", "class": "heatmap-good", "color": "#38bdf8"}
    if number >= 45:
        return {"label": "보통", "class": "heatmap-neutral", "color": "#a78bfa"}
    if number >= 30:
        return {"label": "약함", "class": "heatmap-weak", "color": "#f59e0b"}
    return {"label": "취약", "class": "heatmap-risk", "color": "#ef4444"}


def candleSummaryText(close: Any, return_5d: Any, return_20d: Any, volume_ratio: Any) -> str:
    close_text = formatKRW(close)
    r5_text = formatPercent(return_5d, signed=True)
    r20_text = formatPercent(return_20d, signed=True)
    ratio = _finite(volume_ratio)
    ratio_text = "-" if ratio is None else f"{ratio:.2f}x"
    return f"최근 종가 {close_text} · 5일 {r5_text} · 20일 {r20_text} · 거래량 {ratio_text}"
