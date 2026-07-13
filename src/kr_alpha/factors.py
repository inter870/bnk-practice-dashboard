from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Mapping, Sequence

import numpy as np

from .domain import FactorValue, FixtureStock, finite
from .fixtures import FACTOR_NAMES


@dataclass(frozen=True)
class FactorSpec:
    name: str
    label_ko: str
    hypothesis: str
    direction: int
    prior_weight: float
    holding_days: int
    cost_sensitivity: str
    disable_reason: str


FACTOR_SPECS: tuple[FactorSpec, ...] = (
    FactorSpec("earnings_surprise_pead", "실적 서프라이즈·PEAD", "공개 후 이익 충격의 지연 반영", 1, 0.12, 20, "중간", "실적·공개시각 없음"),
    FactorSpec("near_52w_high", "52주 신고가 근접", "강한 수요와 정보 확산", 1, 0.08, 20, "중간", "조정가격 이력 부족"),
    FactorSpec("earnings_revision", "실적 추정치 변화", "전망 상향의 점진적 가격 반영", 1, 0.09, 20, "낮음", "PIT 컨센서스 없음"),
    FactorSpec("quality_fscore", "품질·F-score", "수익성과 재무건전성의 지속성", 1, 0.09, 60, "낮음", "PIT 재무제표 없음"),
    FactorSpec("value", "가치", "동일 업종 대비 낮은 가격", 1, 0.08, 60, "낮음", "밸류에이션 없음"),
    FactorSpec("shareholder_yield", "주주환원·밸류업", "현금 환원과 소각의 장기 재평가", 1, 0.07, 60, "낮음", "공시 근거 없음"),
    FactorSpec("medium_momentum", "중기 모멘텀", "7~12개월 추세 지속", 1, 0.10, 20, "중간", "가격 이력 부족"),
    FactorSpec("short_reversal", "단기 반전", "3~5일 과잉반응의 되돌림", 1, 0.05, 5, "높음", "단기 가격 이력 부족"),
    FactorSpec("investor_flow", "외국인·기관 수급", "지속적인 정보거래 수요", 1, 0.09, 20, "중간", "투자자별 수급 없음"),
    FactorSpec("short_borrow", "공매도·대차", "혼잡·차입비용을 반영한 취약성 역수", 1, 0.05, 10, "높음", "공매도·대차 데이터 없음"),
    FactorSpec("low_vol_beta", "저변동성·저베타", "하방 변동성 통제", 1, 0.06, 60, "낮음", "수익률 이력 부족"),
    FactorSpec("liquidity_impact", "유동성·시장충격", "체결 가능성과 비용 후 알파", 1, 0.05, 10, "높음", "거래대금 없음"),
    FactorSpec("index_rebalance", "지수 편입·편출", "기계적 수급 이벤트", 1, 0.03, 5, "높음", "지수 이벤트 없음"),
    FactorSpec("policy_disclosure", "정책·공시 이벤트", "공개된 촉매의 재평가", 1, 0.04, 20, "높음", "이벤트 시각 없음"),
)


def winsorize(values: Sequence[float], lower: float = 0.05, upper: float = 0.95) -> list[float]:
    if not values:
        return []
    array = np.asarray(values, dtype=float)
    low, high = np.quantile(array, [lower, upper])
    return [float(value) for value in np.clip(array, low, high)]


def robust_zscores(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    array = np.asarray(values, dtype=float)
    median = float(np.median(array))
    mad = float(np.median(np.abs(array - median)))
    scale = 1.4826 * mad
    if scale <= 1e-12:
        scale = float(np.std(array))
    if scale <= 1e-12:
        return [0.0] * len(values)
    return [float(np.clip((value - median) / scale, -3.0, 3.0)) for value in array]


def percentile_ranks(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    array = np.asarray(values, dtype=float)
    if len(array) == 1:
        return [0.5]
    order = np.argsort(np.argsort(array, kind="mergesort"), kind="mergesort")
    return [float(rank / (len(array) - 1)) for rank in order]


def _eligible_value(stock: FixtureStock, factor_name: str, decision_time: datetime) -> tuple[float | None, datetime | None]:
    rows = [row for row in stock.observations if row.field == factor_name and row.eligible_at(decision_time)]
    if not rows:
        return None, None
    row = max(rows, key=lambda item: item.available_at)
    return finite(row.value), row.available_at


def calculate_factor_panel(stocks: Sequence[FixtureStock], decision_time: datetime) -> dict[str, tuple[FactorValue, ...]]:
    result: dict[str, list[FactorValue]] = {stock.security.instrument_id: [] for stock in stocks}
    for spec in FACTOR_SPECS:
        eligible: list[tuple[FixtureStock, float, datetime]] = []
        missing: list[FixtureStock] = []
        for stock in stocks:
            value, available_at = _eligible_value(stock, spec.name, decision_time)
            if value is None or available_at is None:
                missing.append(stock)
            else:
                eligible.append((stock, value * spec.direction, available_at))
        raw = [item[1] for item in eligible]
        clipped = winsorize(raw)
        neutralized = list(clipped)
        for group_key in ("sector", "size_bucket"):
            groups: dict[str, list[int]] = {}
            for index, (stock, _, _) in enumerate(eligible):
                groups.setdefault(str(getattr(stock.security, group_key)), []).append(index)
            for indices in groups.values():
                if len(indices) < 2:
                    continue
                mean = sum(neutralized[index] for index in indices) / len(indices)
                for index in indices:
                    neutralized[index] -= mean * 0.5
        zscores = robust_zscores(neutralized)
        percentiles = percentile_ranks(neutralized)
        for index, (stock, value, available_at) in enumerate(eligible):
            result[stock.security.instrument_id].append(
                FactorValue(
                    instrument_id=stock.security.instrument_id,
                    factor_name=spec.name,
                    raw_value=value,
                    winsorized_value=clipped[index],
                    neutralized_value=neutralized[index],
                    z_score=zscores[index],
                    percentile=percentiles[index],
                    confidence=1.0,
                    available_at=available_at,
                    reason_code=f"factor_ready:{spec.name}",
                )
            )
        for stock in missing:
            result[stock.security.instrument_id].append(
                FactorValue(
                    instrument_id=stock.security.instrument_id,
                    factor_name=spec.name,
                    raw_value=None,
                    winsorized_value=None,
                    neutralized_value=None,
                    z_score=None,
                    percentile=None,
                    confidence=0.0,
                    available_at=decision_time,
                    reason_code=f"factor_unavailable:{spec.name}",
                )
            )
    return {key: tuple(values) for key, values in result.items()}


def prior_weights() -> dict[str, float]:
    total = sum(spec.prior_weight for spec in FACTOR_SPECS)
    return {spec.name: spec.prior_weight / total for spec in FACTOR_SPECS}


def factor_spec(name: str) -> FactorSpec:
    for spec in FACTOR_SPECS:
        if spec.name == name:
            return spec
    raise KeyError(name)


assert tuple(spec.name for spec in FACTOR_SPECS) == FACTOR_NAMES
