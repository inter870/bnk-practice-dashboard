from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any, Literal, Mapping


DataMode = Literal["fixture", "paper", "live"]


@dataclass(frozen=True)
class RiskLimits:
    max_position_weight: float = 0.07
    max_event_position_weight: float = 0.03
    max_sector_weight: float = 0.30
    max_kosdaq_position_weight: float = 0.05
    minimum_cash_weight: float = 0.05
    maximum_adv_participation: float = 0.10
    maximum_days_to_exit: float = 5.0
    turnover_budget: float = 0.30
    target_volatility: float = 0.15
    daily_loss_hard: float = -0.025
    weekly_loss_hard: float = -0.05
    drawdown_warning: float = -0.08
    drawdown_deleverage: float = -0.12
    drawdown_stop_new_entries: float = -0.15


@dataclass(frozen=True)
class AggressiveSleeveConfig:
    enabled: bool = False
    paper_only: bool = True
    max_total_nav: float = 0.05
    max_position_nav: float = 0.01
    max_open_positions: int = 5
    max_holding_days: int = 10


@dataclass(frozen=True)
class TransactionCostConfig:
    policy_id: str = "kr-alpha-fixture-cost-v1"
    commission_bps: float = 4.0
    taxes_and_fees_bps: float = 18.0
    spread_bps: float = 8.0
    volatility_slippage_bps: float = 10.0
    market_impact_coefficient: float = 12.0

    @property
    def base_round_trip_bps(self) -> float:
        return sum(
            max(0.0, value)
            for value in (
                self.commission_bps,
                self.taxes_and_fees_bps,
                self.spread_bps,
                self.volatility_slippage_bps,
            )
        )


@dataclass(frozen=True)
class KRAlphaConfig:
    enabled: bool = False
    data_mode: DataMode = "fixture"
    timezone: str = "Asia/Seoul"
    base_currency: str = "KRW"
    model_version: str = "kr-alpha-baseline-v1"
    factor_version: str = "kr-alpha-factor-v1"
    score_version: str = "kr-alpha-score-v1"
    fixture_seed: int = 20260713
    risk: RiskLimits = field(default_factory=RiskLimits)
    aggressive_sleeve: AggressiveSleeveConfig = field(default_factory=AggressiveSleeveConfig)
    transaction_costs: TransactionCostConfig = field(default_factory=TransactionCostConfig)

    @property
    def config_hash(self) -> str:
        payload = json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _boolean(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def config_from_mapping(values: Mapping[str, Any]) -> KRAlphaConfig:
    mode = str(values.get("KR_ALPHA_DATA_MODE", "fixture")).strip().lower()
    if mode not in {"fixture", "paper", "live"}:
        mode = "fixture"
    return KRAlphaConfig(
        enabled=_boolean(values.get("KR_ALPHA_ENABLED"), False),
        data_mode=mode,  # type: ignore[arg-type]
        timezone=str(values.get("KR_ALPHA_TIMEZONE") or "Asia/Seoul"),
        base_currency=str(values.get("KR_ALPHA_BASE_CURRENCY") or "KRW"),
    )


def validate_config(config: KRAlphaConfig) -> tuple[str, ...]:
    errors: list[str] = []
    if config.data_mode not in {"fixture", "paper", "live"}:
        errors.append("invalid_data_mode")
    for name in (
        "max_position_weight", "max_event_position_weight", "max_sector_weight",
        "max_kosdaq_position_weight", "minimum_cash_weight", "maximum_adv_participation",
        "turnover_budget", "target_volatility",
    ):
        value = float(getattr(config.risk, name))
        if not 0.0 <= value <= 1.0:
            errors.append(f"risk_limit_out_of_range:{name}")
    if config.aggressive_sleeve.enabled and not config.aggressive_sleeve.paper_only:
        errors.append("aggressive_sleeve_must_be_paper_only")
    if config.transaction_costs.base_round_trip_bps < 0:
        errors.append("negative_transaction_cost")
    return tuple(errors)
