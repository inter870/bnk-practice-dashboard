from __future__ import annotations

from datetime import date, timedelta
import math

from .models import (
    KoreaDisclosureEvent,
    KoreaFundamentalSnapshot,
    KoreaMarketStatus,
    KoreaPricePoint,
    KoreaSupplyDemandPoint,
    KoreaTicker,
)


_TODAY = date.today()

_UNIVERSE_SEED = [
    ("005930", "삼성전자", "KOSPI", "반도체", "메모리/세트", 72_000, 430_000_000_000_000, 16.5, 1.35, 0.082, 0.31, 0.145, 0.020, 18_500_000_000_000, ["반도체", "AI"], True, 0.20),
    ("000660", "SK하이닉스", "KOSPI", "반도체", "메모리", 196_000, 145_000_000_000_000, 22.0, 2.15, 0.108, 0.46, 0.205, 0.006, 9_300_000_000_000, ["HBM", "AI"], False, 0.32),
    ("005380", "현대차", "KOSPI", "자동차", "완성차", 268_000, 56_000_000_000_000, 6.2, 0.72, 0.118, 0.78, 0.087, 0.043, 8_100_000_000_000, ["주주환원", "수출"], True, 0.18),
    ("000270", "기아", "KOSPI", "자동차", "완성차", 119_000, 47_000_000_000_000, 5.8, 0.86, 0.142, 0.65, 0.104, 0.048, 7_600_000_000_000, ["주주환원", "수출"], True, 0.15),
    ("035420", "NAVER", "KOSPI", "인터넷", "플랫폼", 198_000, 32_000_000_000_000, 21.5, 1.25, 0.071, 0.36, 0.156, 0.007, 1_900_000_000_000, ["AI", "플랫폼"], False, -0.02),
    ("035720", "카카오", "KOSPI", "인터넷", "플랫폼", 46_000, 20_000_000_000_000, 38.0, 1.15, 0.038, 0.42, 0.069, 0.001, 480_000_000_000, ["플랫폼"], False, -0.15),
    ("373220", "LG에너지솔루션", "KOSPI", "2차전지", "배터리", 338_000, 79_000_000_000_000, 54.0, 3.35, 0.047, 0.63, 0.061, 0.000, 1_100_000_000_000, ["2차전지"], False, -0.10),
    ("207940", "삼성바이오로직스", "KOSPI", "바이오", "CMO", 938_000, 66_000_000_000_000, 62.0, 5.55, 0.087, 0.31, 0.328, 0.000, 1_400_000_000_000, ["바이오"], False, 0.05),
    ("068270", "셀트리온", "KOSPI", "바이오", "바이오시밀러", 184_000, 40_000_000_000_000, 43.0, 2.05, 0.061, 0.24, 0.245, 0.002, 900_000_000_000, ["바이오"], False, 0.07),
    ("005490", "POSCO홀딩스", "KOSPI", "철강", "지주/소재", 392_000, 33_000_000_000_000, 17.0, 0.63, 0.041, 0.44, 0.072, 0.027, 4_400_000_000_000, ["철강", "2차전지소재"], True, 0.02),
    ("105560", "KB금융", "KOSPI", "금융", "은행지주", 89_000, 35_000_000_000_000, 6.4, 0.52, 0.091, 0.92, 0.000, 0.061, 5_100_000_000_000, ["밸류업", "배당"], True, 0.26),
    ("055550", "신한지주", "KOSPI", "금융", "은행지주", 57_000, 29_000_000_000_000, 6.8, 0.49, 0.083, 0.88, 0.000, 0.058, 4_700_000_000_000, ["밸류업", "배당"], True, 0.22),
    ("012450", "한화에어로스페이스", "KOSPI", "방산", "방위산업", 294_000, 15_000_000_000_000, 18.0, 2.25, 0.133, 0.74, 0.124, 0.006, 1_250_000_000_000, ["방산", "수출"], False, 0.30),
    ("329180", "HD현대중공업", "KOSPI", "조선", "조선", 158_000, 14_000_000_000_000, 28.0, 2.10, 0.075, 0.82, 0.081, 0.000, 980_000_000_000, ["조선", "수출"], False, 0.25),
    ("267260", "HD현대일렉트릭", "KOSPI", "전력기기", "전력인프라", 315_000, 11_000_000_000_000, 25.0, 5.10, 0.246, 0.58, 0.171, 0.004, 820_000_000_000, ["전력기기", "AI전력"], False, 0.34),
    ("086790", "하나금융지주", "KOSPI", "금융", "은행지주", 66_000, 17_000_000_000_000, 5.9, 0.46, 0.087, 0.91, 0.000, 0.064, 4_000_000_000_000, ["밸류업", "배당"], True, 0.24),
    ("028260", "삼성물산", "KOSPI", "지주/건설", "복합", 166_000, 30_000_000_000_000, 12.0, 0.82, 0.063, 0.29, 0.049, 0.021, 1_600_000_000_000, ["밸류업", "지주"], True, 0.10),
    ("006400", "삼성SDI", "KOSPI", "2차전지", "배터리", 281_000, 19_000_000_000_000, 31.0, 1.05, 0.043, 0.38, 0.066, 0.003, 820_000_000_000, ["2차전지"], False, -0.12),
    ("051910", "LG화학", "KOSPI", "화학", "화학/배터리소재", 337_000, 23_000_000_000_000, 24.0, 0.86, 0.037, 0.54, 0.041, 0.006, 650_000_000_000, ["화학", "2차전지소재"], False, -0.08),
    ("096770", "SK이노베이션", "KOSPI", "에너지", "정유/배터리", 126_000, 12_000_000_000_000, 18.5, 0.59, 0.031, 1.20, 0.035, 0.000, 420_000_000_000, ["정유", "배터리"], False, -0.18),
    ("034020", "두산에너빌리티", "KOSPI", "에너지", "원전/발전", 29_800, 19_000_000_000_000, 28.5, 2.05, 0.055, 0.98, 0.071, 0.000, 720_000_000_000, ["원전", "에너지"], False, 0.16),
    ("196170", "알테오젠", "KOSDAQ", "바이오", "플랫폼기술", 285_000, 15_000_000_000_000, 76.0, 18.0, 0.128, 0.21, 0.183, 0.000, 260_000_000_000, ["바이오", "기술수출"], False, 0.21),
    ("247540", "에코프로비엠", "KOSDAQ", "2차전지", "양극재", 154_000, 15_000_000_000_000, 48.0, 4.30, 0.066, 0.72, 0.082, 0.000, 330_000_000_000, ["2차전지"], False, -0.14),
]


def _business_dates(length: int) -> list[date]:
    current = _TODAY
    rows: list[date] = []
    while len(rows) < length:
        if current.weekday() < 5:
            rows.append(current)
        current -= timedelta(days=1)
    return list(reversed(rows))


def _generate_price_history(code: str, base_price: float, market_cap: float, flow_bias: float, length: int = 260) -> list[KoreaPricePoint]:
    dates = _business_dates(length)
    seed = sum(ord(ch) for ch in code)
    start = base_price * (0.72 + (seed % 17) / 100)
    points: list[KoreaPricePoint] = []
    benchmark = 2500.0
    for idx, day in enumerate(dates):
        trend = 1 + idx * (0.0009 + flow_bias * 0.00045)
        cycle = math.sin((idx + seed % 19) / 12.0) * (0.035 + abs(flow_bias) * 0.015)
        drawdown = -0.10 if 82 <= idx <= 104 and seed % 3 == 0 else -0.055 if 172 <= idx <= 188 else 0.0
        close = max(500.0, start * trend * (1 + cycle + drawdown))
        open_price = close * (1 + math.sin(idx / 7.0) * 0.006)
        high = max(open_price, close) * (1.012 + (seed % 5) * 0.001)
        low = min(open_price, close) * (0.988 - (seed % 4) * 0.001)
        volume = max(20_000, (market_cap / close) * (0.002 + (seed % 9) * 0.00018) * (1 + abs(math.sin(idx / 8.0)) * 0.35))
        benchmark = benchmark * (1 + 0.00032 + math.sin(idx / 20.0) * 0.0007)
        points.append(
            KoreaPricePoint(
                date=day.isoformat(),
                open=round(open_price, 2),
                high=round(high, 2),
                low=round(low, 2),
                close=round(close, 2),
                volume=round(volume, 0),
                trading_value=round(volume * close, 0),
                market_cap=market_cap,
                shares_outstanding=round(market_cap / base_price, 0),
                foreign_ownership_rate=round(0.12 + (seed % 35) / 100 + flow_bias * 0.04, 4),
                benchmark_close=round(benchmark, 2),
            )
        )
    return points


def _generate_supply_demand(code: str, flow_bias: float, length: int = 80) -> list[KoreaSupplyDemandPoint]:
    dates = _business_dates(length)
    seed = sum(ord(ch) for ch in code)
    rows: list[KoreaSupplyDemandPoint] = []
    for idx, day in enumerate(dates):
        cycle = math.sin((idx + seed % 13) / 6.0)
        foreign = (flow_bias * 1_400_000_000) + cycle * 550_000_000
        institution = (flow_bias * 900_000_000) + math.cos(idx / 8.0) * 420_000_000
        pension = (flow_bias * 420_000_000) + math.sin(idx / 11.0) * 190_000_000
        rows.append(
            KoreaSupplyDemandPoint(
                date=day.isoformat(),
                code=code,
                individual_net_buy=round(-(foreign + institution) * 0.65, 0),
                foreign_net_buy=round(foreign, 0),
                institution_net_buy=round(institution, 0),
                pension_net_buy=round(pension, 0),
                program_net_buy=round(foreign * 0.28, 0),
                short_sell_value=round(max(0, 220_000_000 - flow_bias * 80_000_000 + abs(cycle) * 110_000_000), 0),
                short_balance=round(max(0.001, 0.012 - flow_bias * 0.006 + abs(cycle) * 0.004), 4),
                short_balance_ratio=round(max(0.001, 0.018 - flow_bias * 0.007 + abs(cycle) * 0.006), 4),
                foreign_ownership_rate=round(0.16 + flow_bias * 0.05 + cycle * 0.01, 4),
            )
        )
    return rows


KOREA_UNIVERSE = [
    KoreaTicker(code, name, market, sector, industry, tags, fiscal_month=12)
    for code, name, market, sector, industry, _, _, _, _, _, _, _, _, _, tags, _, _ in _UNIVERSE_SEED
]

PRICE_HISTORY = {
    code: _generate_price_history(code, base_price, market_cap, flow_bias)
    for code, _, _, _, _, base_price, market_cap, _, _, _, _, _, _, _, _, _, flow_bias in _UNIVERSE_SEED
}

FUNDAMENTALS = {
    code: KoreaFundamentalSnapshot(
        code=code,
        date=_TODAY.isoformat(),
        fiscal_year=_TODAY.year - 1,
        fiscal_quarter="FY",
        revenue=market_cap * 0.42,
        operating_profit=market_cap * operating_margin * 0.18,
        net_income=market_cap * max(roe, 0.01) * 0.11,
        assets=market_cap * 1.9,
        equity=market_cap * 1.2,
        debt=market_cap * debt_to_equity,
        operating_cash_flow=free_cash_flow * 1.35,
        free_cash_flow=free_cash_flow,
        eps=base_price / max(per, 1),
        bps=base_price / max(pbr, 0.1),
        dps=base_price * dividend_yield,
        per=per,
        pbr=pbr,
        roe=roe,
        operating_margin=operating_margin,
        debt_to_equity=debt_to_equity,
        dividend_yield=dividend_yield,
        payout_ratio=min(0.8, dividend_yield / max(roe, 0.01)),
    )
    for code, _, _, _, _, base_price, market_cap, per, pbr, roe, debt_to_equity, operating_margin, dividend_yield, free_cash_flow, _, _, _ in _UNIVERSE_SEED
}

SUPPLY_DEMAND = {
    code: _generate_supply_demand(code, flow_bias)
    for code, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, flow_bias in _UNIVERSE_SEED
}

DISCLOSURES = {
    "005930": [KoreaDisclosureEvent("dart-005930-1", "005930", _TODAY.isoformat(), "자사주 매입 및 소각 계획", "buyback", "positive", 84, "manual_mock", summary="주주환원 강화")],
    "000660": [KoreaDisclosureEvent("dart-000660-1", "000660", _TODAY.isoformat(), "HBM 공급계약 확대", "major_contract", "positive", 78, "manual_mock", summary="AI 메모리 수요 확인")],
    "035720": [KoreaDisclosureEvent("dart-035720-1", "035720", _TODAY.isoformat(), "비핵심 자산 매각 검토", "other", "neutral", 42, "manual_mock", summary="실적 가시성 확인 필요")],
    "373220": [KoreaDisclosureEvent("dart-373220-1", "373220", _TODAY.isoformat(), "전환사채 관련 오버행 점검", "convertible_bond", "negative", 72, "manual_mock", summary="희석 리스크")],
    "105560": [KoreaDisclosureEvent("dart-105560-1", "105560", _TODAY.isoformat(), "기업가치 제고 계획 공시", "value_up", "positive", 86, "manual_mock", summary="밸류업 정책 수혜")],
    "034020": [KoreaDisclosureEvent("dart-034020-1", "034020", _TODAY.isoformat(), "원전 기자재 수주 모멘텀", "major_contract", "positive", 70, "manual_mock", summary="에너지 인프라 투자 기대")],
}

for ticker in KOREA_UNIVERSE:
    DISCLOSURES.setdefault(ticker.code, [])

VALUE_UP_FLAGS = {
    code: value_up
    for code, _, _, _, _, _, _, _, _, _, _, _, _, _, _, value_up, _ in _UNIVERSE_SEED
}

MARKET_STATUS = KoreaMarketStatus(
    date=_TODAY.isoformat(),
    kospi_close=3180.42,
    kosdaq_close=842.18,
    kospi_return_1d=0.0042,
    kosdaq_return_1d=-0.0031,
    kospi_above_ma200=True,
    kosdaq_above_ma200=False,
    market_breadth=0.54,
    advance_decline_ratio=1.12,
    new_high_new_low_ratio=1.35,
    turnover_trend=0.08,
    usd_krw=1376.2,
    bond_yield_3y=2.91,
    volatility_proxy=0.19,
    regime="neutral",
    regime_score=61,
    reason=["코스피는 장기 추세 위", "코스닥은 상대 약세", "환율 부담으로 공격 비중 제한"],
)


def benchmark_series(benchmark: str = "KOSPI") -> list[KoreaPricePoint]:
    first_code = "005930" if benchmark != "KOSDAQ" else "035720"
    points = PRICE_HISTORY[first_code]
    base = 2500.0 if benchmark != "KOSDAQ" else 780.0
    rows: list[KoreaPricePoint] = []
    for idx, point in enumerate(points):
        close = base * (1 + idx * 0.00038) * (1 + math.sin(idx / 18.0) * 0.025)
        rows.append(
            KoreaPricePoint(
                date=point.date,
                open=close * 0.998,
                high=close * 1.008,
                low=close * 0.992,
                close=round(close, 2),
                volume=1,
                trading_value=1,
            )
        )
    return rows
