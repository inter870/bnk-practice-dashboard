from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class CompoundingAssumptions:
    initial_capital: float
    target_capital: float
    months: int
    expected_monthly_return: float
    monthly_volatility: float
    leverage: float = 1.0
    monthly_cost: float = 0.0
    maximum_allowed_drawdown: float = 0.30
    simulations: int = 5_000
    seed: int = 20260713


@dataclass(frozen=True)
class CompoundingResult:
    required_monthly_return: float
    required_annual_return: float
    target_probability: float
    ruin_probability: float
    drawdown_limit_probability: float
    expected_max_drawdown: float
    terminal_percentiles: dict[int, float]
    feasibility_grade: str
    seed: int
    warnings: tuple[str, ...]


def required_monthly_return(initial_capital: float, target_capital: float, months: int) -> float:
    if initial_capital <= 0 or target_capital <= 0 or months <= 0:
        raise ValueError("capital and months must be positive")
    return (target_capital / initial_capital) ** (1.0 / months) - 1.0


def analyze_compounding(values: CompoundingAssumptions) -> CompoundingResult:
    required = required_monthly_return(values.initial_capital, values.target_capital, values.months)
    if values.simulations <= 0 or values.monthly_volatility < 0 or values.leverage < 0:
        raise ValueError("invalid simulation assumptions")
    rng = np.random.default_rng(values.seed)
    returns = rng.normal(values.expected_monthly_return, values.monthly_volatility, (values.simulations, values.months))
    returns = returns * values.leverage - max(0.0, values.monthly_cost)
    returns = np.maximum(returns, -1.0)
    wealth = np.empty((values.simulations, values.months + 1), dtype=float)
    wealth[:, 0] = values.initial_capital
    for month in range(values.months):
        wealth[:, month + 1] = wealth[:, month] * (1.0 + returns[:, month])
    peaks = np.maximum.accumulate(wealth, axis=1)
    drawdowns = np.divide(wealth - peaks, peaks, out=np.zeros_like(wealth), where=peaks > 0)
    max_drawdowns = np.min(drawdowns, axis=1)
    terminal = wealth[:, -1]
    target_probability = float(np.mean(terminal >= values.target_capital))
    ruin_probability = float(np.mean(terminal <= 0))
    limit_probability = float(np.mean(max_drawdowns <= -abs(values.maximum_allowed_drawdown)))
    percentiles = {int(level): float(value) for level, value in zip((5, 25, 50, 75, 95), np.percentile(terminal, [5, 25, 50, 75, 95]))}
    if target_probability >= 0.50 and limit_probability <= 0.20:
        grade = "검토 가능"
    elif target_probability >= 0.10:
        grade = "매우 공격적"
    else:
        grade = "현실성 매우 낮음"
    warnings: list[str] = ["모형 추정치이며 수익 보장이 아닙니다."]
    if required > 1.0:
        warnings.append("월복리 100% 초과가 필요해 파산·유동성 위험이 극단적입니다.")
    return CompoundingResult(
        required_monthly_return=required,
        required_annual_return=(1.0 + required) ** 12 - 1.0,
        target_probability=target_probability,
        ruin_probability=ruin_probability,
        drawdown_limit_probability=limit_probability,
        expected_max_drawdown=float(np.mean(max_drawdowns)),
        terminal_percentiles=percentiles,
        feasibility_grade=grade,
        seed=values.seed,
        warnings=tuple(warnings),
    )
