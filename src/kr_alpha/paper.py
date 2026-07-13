from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from .domain import ensure_aware


@dataclass(frozen=True)
class PaperOrderRequest:
    idempotency_key: str
    instrument_id: str
    side: str
    quantity: float
    decision_time: datetime
    model_version: str
    config_hash: str

    def __post_init__(self) -> None:
        ensure_aware(self.decision_time, "decision_time")


@dataclass(frozen=True)
class PaperFill:
    order_id: str
    instrument_id: str
    side: str
    requested_quantity: float
    filled_quantity: float
    fill_price: float
    fee: float
    filled_at: datetime
    status: str


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    event_at: datetime
    idempotency_key: str
    details: Mapping[str, str]


class PaperBroker:
    def __init__(self, *, starting_cash: float = 100_000_000.0, max_adv_participation: float = 0.10):
        self.cash = float(starting_cash)
        self.max_adv_participation = float(max_adv_participation)
        self.positions: dict[str, float] = {}
        self._fills: dict[str, PaperFill] = {}
        self.audit_log: list[AuditEvent] = []

    def submit(
        self,
        request: PaperOrderRequest,
        *,
        next_tradable_time: datetime,
        price: float,
        available_volume: float,
        fee_bps: float,
    ) -> PaperFill:
        ensure_aware(next_tradable_time, "next_tradable_time")
        if request.idempotency_key in self._fills:
            return self._fills[request.idempotency_key]
        if next_tradable_time <= request.decision_time:
            raise ValueError("fill time must be after decision time")
        if request.side not in {"BUY", "SELL"} or request.quantity <= 0 or price <= 0:
            raise ValueError("invalid paper order")
        max_quantity = max(0.0, available_volume * self.max_adv_participation)
        filled_quantity = min(request.quantity, max_quantity)
        notional = filled_quantity * price
        fee = notional * max(0.0, fee_bps) / 10_000.0
        if request.side == "BUY":
            affordable = max(0.0, self.cash / (price * (1.0 + max(0.0, fee_bps) / 10_000.0)))
            filled_quantity = min(filled_quantity, affordable)
            notional = filled_quantity * price
            fee = notional * max(0.0, fee_bps) / 10_000.0
            self.cash -= notional + fee
            self.positions[request.instrument_id] = self.positions.get(request.instrument_id, 0.0) + filled_quantity
        else:
            held = self.positions.get(request.instrument_id, 0.0)
            filled_quantity = min(filled_quantity, held)
            notional = filled_quantity * price
            fee = notional * max(0.0, fee_bps) / 10_000.0
            self.cash += notional - fee
            self.positions[request.instrument_id] = held - filled_quantity
        status = "FILLED" if filled_quantity >= request.quantity else ("PARTIAL" if filled_quantity > 0 else "UNFILLED")
        fill = PaperFill(
            request.idempotency_key,
            request.instrument_id,
            request.side,
            request.quantity,
            filled_quantity,
            price,
            fee,
            next_tradable_time,
            status,
        )
        self._fills[request.idempotency_key] = fill
        self.audit_log.append(
            AuditEvent(
                "paper_fill",
                next_tradable_time,
                request.idempotency_key,
                {"model_version": request.model_version, "config_hash": request.config_hash, "status": status},
            )
        )
        return fill
