from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from typing import Any


@dataclass(frozen=True)
class CostPolicy:
    policy_id: str
    market: str
    product: str
    effective_from: date
    effective_to: date | None = None
    currency: str = "KRW"
    commission_bps: float = 0.0
    taxes_and_fees_bps: float = 0.0
    spread_bps: float = 0.0
    slippage_bps: float = 0.0
    market_impact_bps: float = 0.0

    @property
    def total_round_trip_bps(self) -> float:
        values = (
            self.commission_bps,
            self.taxes_and_fees_bps,
            self.spread_bps,
            self.slippage_bps,
            self.market_impact_bps,
        )
        return sum(max(0.0, float(value)) for value in values if math.isfinite(float(value)))


def legacy_cost_policy(trading_cost_pct: Any, slippage_pct: Any) -> CostPolicy:
    def pct_to_bps(value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, number * 100.0) if math.isfinite(number) else 0.0

    return CostPolicy(
        policy_id="legacy-dashboard-cost-v1",
        market="KRX",
        product="equity",
        effective_from=date(1970, 1, 1),
        commission_bps=pct_to_bps(trading_cost_pct),
        slippage_bps=pct_to_bps(slippage_pct),
    )


def calculate_net_expected_edge(
    gross_expected_return_pct: Any,
    benchmark_expected_return_pct: Any,
    policy: CostPolicy,
) -> float | None:
    try:
        gross = float(gross_expected_return_pct)
        benchmark = float(benchmark_expected_return_pct)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(gross) or not math.isfinite(benchmark):
        return None
    return gross - benchmark - policy.total_round_trip_bps / 100.0
