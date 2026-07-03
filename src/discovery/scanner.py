from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Any

import pandas as pd

from src.common import average_traded_value, calc_returns, clamp, find_ohlcv_columns, latest_close, safe_float


HistoryLoader = Callable[[str], pd.DataFrame]


@dataclass
class DiscoveryCandidate:
    code: str
    name: str
    market: str
    category: str
    discovery_score: float
    leadership_score: float | None
    expected_edge: float | None
    risk_reward_ratio: float | None
    quality_adjusted_rr: float | None
    trigger_price: float | None
    stop_price: float | None
    max_position_pct: float
    confidence: float
    positive_reasons: list[str] = field(default_factory=list)
    negative_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _column(df: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    if df is None or df.empty:
        return None
    lowered = {str(col).lower(): str(col) for col in df.columns}
    for candidate in candidates:
        found = lowered.get(candidate.lower())
        if found:
            return found
    return None


def is_excluded_security(row: pd.Series) -> tuple[bool, str | None]:
    name = _text(row.get("Name", row.get("name", "")))
    market = _text(row.get("Market", row.get("market", ""))).upper()
    kind = " ".join(_text(row.get(col, "")) for col in row.index)
    upper = f"{name} {market} {kind}".upper()
    patterns = ["ETF", "ETN", "SPAC", "스팩", "리츠", "선박투자", "인프라"]
    if any(pattern in upper for pattern in patterns):
        return True, "ETF/ETN/SPAC/특수상품 제외"
    if name.endswith("우") or "우B" in name or "우선주" in kind:
        return True, "우선주 제외"
    if any(flag in kind for flag in ["관리종목", "거래정지", "정리매매"]):
        return True, "관리/정지 종목 제외"
    return False, None


def build_universe(listing: pd.DataFrame) -> tuple[list[dict[str, str]], list[str]]:
    warnings: list[str] = []
    if listing is None or listing.empty:
        return [], ["상장 종목 리스트를 불러오지 못했습니다."]

    code_c = _column(listing, ("Code", "Symbol", "code"))
    name_c = _column(listing, ("Name", "name"))
    market_c = _column(listing, ("Market", "Dept", "market"))
    if code_c is None or name_c is None:
        return [], ["상장 리스트에 Code/Name 컬럼이 없습니다."]
    if market_c is None:
        warnings.append("시장 구분 컬럼이 없어 market=unknown으로 표시합니다.")

    rows: list[dict[str, str]] = []
    excluded = 0
    for _, row in listing.iterrows():
        code = "".join(ch for ch in _text(row.get(code_c)) if ch.isdigit()).zfill(6)
        name = _text(row.get(name_c))
        market = _text(row.get(market_c)) if market_c else "unknown"
        if len(code) != 6 or not name:
            continue
        skip, _ = is_excluded_security(row)
        if skip:
            excluded += 1
            continue
        rows.append({"code": code, "name": name, "market": market or "unknown"})

    if excluded:
        warnings.append(f"ETF/ETN/SPAC/우선주 등 {excluded}개 제외")
    return rows, warnings


def _relative_strength(close: pd.Series, benchmark_close: pd.Series | None) -> float | None:
    if benchmark_close is None:
        return None
    close = close.dropna()
    benchmark_close = benchmark_close.dropna()
    if len(close) < 21 or len(benchmark_close) < 21:
        return None
    stock_r = safe_float(close.iloc[-1] / close.iloc[-21] - 1.0)
    bench_r = safe_float(benchmark_close.iloc[-1] / benchmark_close.iloc[-21] - 1.0)
    if stock_r is None or bench_r is None:
        return None
    return (stock_r - bench_r) * 100.0


def score_candidate(
    code: str,
    name: str,
    market: str,
    history: pd.DataFrame,
    benchmark_close: pd.Series | None = None,
    market_regime_score: float = 50.0,
) -> DiscoveryCandidate | None:
    warnings: list[str] = []
    if history is None or history.empty:
        return DiscoveryCandidate(code, name, market, "데이터 없음", 0, None, None, None, None, None, None, 0, 10, [], ["가격 데이터 unavailable"], ["가격 데이터 unavailable"])

    _, high_c, low_c, close_c, volume_c = find_ohlcv_columns(history)
    if close_c not in history.columns:
        return None
    data = history.dropna(subset=[close_c]).tail(260)
    if len(data) < 60:
        return DiscoveryCandidate(code, name, market, "데이터 부족", 20, None, None, None, None, latest_close(history), None, 0, 25, [], ["60거래일 미만"], ["충분한 가격 이력 없음"])

    close = data[close_c].astype(float)
    high = data[high_c].astype(float) if high_c in data.columns else close
    low = data[low_c].astype(float) if low_c in data.columns else close
    volume = data[volume_c].astype(float) if volume_c in data.columns else pd.Series(dtype=float)
    latest = safe_float(close.iloc[-1])
    if latest in (None, 0):
        return None

    returns = calc_returns(close)
    r20 = returns["20d"]
    r60 = returns["60d"]
    rs = _relative_strength(close, benchmark_close)
    ma20 = safe_float(close.tail(20).mean())
    ma60 = safe_float(close.tail(60).mean())
    high_252 = safe_float(high.tail(min(252, len(high))).max())
    low_20 = safe_float(low.tail(20).min())
    adv20 = average_traded_value(data, 20)
    vol_ratio = None
    if len(volume) >= 20:
        avg20 = safe_float(volume.tail(20).mean())
        latest_vol = safe_float(volume.iloc[-1])
        if avg20 not in (None, 0) and latest_vol is not None:
            vol_ratio = latest_vol / avg20

    positive: list[str] = []
    negative: list[str] = []
    score = 50.0
    categories: list[tuple[str, float]] = []

    if rs is not None:
        score += clamp(rs, -15, 15) * 1.25
        if rs >= 6:
            categories.append(("20일 상대강도 리더", 18))
            positive.append(f"코스피 대비 20일 상대강도 {rs:+.2f}%p")
        elif rs <= -6:
            negative.append(f"상대강도 열위 {rs:+.2f}%p")
    else:
        warnings.append("벤치마크 상대강도 unavailable")

    if r20 is not None:
        score += clamp(r20, -20, 20) * 0.55
        if r20 > 0:
            positive.append(f"20일 수익률 {r20:+.2f}%")
        else:
            negative.append(f"20일 수익률 {r20:+.2f}%")
    if r60 is not None and r60 > 0:
        score += min(r60, 30) * 0.25
        positive.append(f"60일 추세 {r60:+.2f}%")

    if high_252 and high_252 > 0:
        high_gap = (latest / high_252 - 1.0) * 100.0
        if high_gap >= -5:
            categories.append(("52주 신고가 근접", 14))
            score += 8
            positive.append(f"52주 고점까지 {abs(high_gap):.2f}%")

    if vol_ratio is not None:
        if vol_ratio >= 1.8:
            categories.append(("거래대금 급증", 12))
            score += 7
            positive.append(f"거래량 {vol_ratio:.2f}x")
        elif vol_ratio < 0.55:
            score -= 7
            negative.append(f"거래량 부족 {vol_ratio:.2f}x")
    else:
        warnings.append("거래량 pace unavailable")

    if ma20 and ma60:
        gap20 = (latest / ma20 - 1.0) * 100.0
        gap60 = (latest / ma60 - 1.0) * 100.0
        if gap60 > 0 and -7 <= gap20 <= 2 and r60 is not None and r60 > 0:
            categories.append(("상승추세 눌림목", 10))
            score += 6
            positive.append("60일선 위 눌림목")
        if gap60 < -8:
            score -= 9
            negative.append("60일선 하회")

    bench_r20 = None
    if benchmark_close is not None and len(benchmark_close.dropna()) >= 21:
        bench_r20 = calc_returns(benchmark_close.dropna())["20d"]
    if bench_r20 is not None and bench_r20 < 0 and r20 is not None and r20 > bench_r20 + 5:
        categories.append(("급락장 생존주", 11))
        score += 6
        positive.append("시장 약세 대비 방어")

    if adv20 is not None:
        if adv20 < 300_000_000:
            score -= 18
            negative.append("거래대금 부족")
        elif adv20 >= 5_000_000_000:
            score += 5
            positive.append("유동성 양호")
    else:
        warnings.append("거래대금 unavailable")

    stop = None
    rr = None
    qrr = None
    expected_edge = None
    if low_20 and latest > low_20:
        stop = low_20
        risk_pct = (latest - stop) / latest * 100.0
        upside_pct = ((high_252 or latest) / latest - 1.0) * 100.0
        if risk_pct > 0:
            rr = upside_pct / risk_pct
            confidence_base = 0.35 + max(score, 0) / 200.0
            expected_edge = confidence_base * upside_pct - (1.0 - confidence_base) * risk_pct - 0.5
            qrr = rr * clamp(score / 100.0, 0.25, 0.95)
            if rr >= 1.8:
                positive.append(f"손익비 {rr:.2f}x")
            elif rr < 0.8:
                negative.append(f"손익비 부족 {rr:.2f}x")
                score -= 10

    avoid = False
    if adv20 is not None and adv20 < 300_000_000:
        avoid = True
    if r20 is not None and r60 is not None and r20 < 0 and r60 < 0:
        avoid = True
    if rr is not None and rr < 0.6:
        avoid = True

    if avoid:
        category = "매수 금지 후보"
        score = min(score, 39)
    elif categories:
        category = sorted(categories, key=lambda item: item[1], reverse=True)[0][0]
    else:
        category = "관찰 후보"

    confidence = clamp(45 + (10 if rs is not None else -8) + (10 if adv20 is not None else -8) + min(len(positive) * 3, 15) - len(warnings) * 5, 15, 90)
    max_position = 0.0 if category == "매수 금지 후보" else clamp((score - 45) / 55 * 0.10, 0.0, 0.10)
    if market_regime_score < 45:
        max_position *= 0.6

    return DiscoveryCandidate(
        code=code,
        name=name,
        market=market,
        category=category,
        discovery_score=round(clamp(score, 0, 100), 2),
        leadership_score=None if rs is None else round(clamp(50 + rs * 2, 0, 100), 2),
        expected_edge=None if expected_edge is None else round(expected_edge, 2),
        risk_reward_ratio=None if rr is None else round(rr, 2),
        quality_adjusted_rr=None if qrr is None else round(qrr, 2),
        trigger_price=latest,
        stop_price=stop,
        max_position_pct=round(max_position, 4),
        confidence=round(confidence, 2),
        positive_reasons=positive[:5],
        negative_reasons=negative[:5],
        warnings=warnings[:5],
    )


def scan_universe(
    universe: list[dict[str, str]],
    history_loader: HistoryLoader,
    benchmark_close: pd.Series | None = None,
    *,
    market_regime_score: float = 50.0,
    limit: int = 20,
) -> tuple[list[DiscoveryCandidate], list[str]]:
    warnings: list[str] = []
    if not universe:
        return [], ["스캔할 유니버스가 없습니다."]

    candidates: list[DiscoveryCandidate] = []
    for item in universe:
        code = item.get("code", "")
        try:
            hist = history_loader(code)
        except Exception:
            warnings.append(f"{code}: 가격 데이터 로딩 실패")
            continue
        candidate = score_candidate(code, item.get("name", code), item.get("market", "unknown"), hist, benchmark_close, market_regime_score)
        if candidate is not None:
            candidates.append(candidate)

    ranked = sorted(candidates, key=lambda row: (row.discovery_score, row.confidence), reverse=True)
    return ranked[:limit], warnings[:20]

