from __future__ import annotations

from datetime import datetime
from typing import Protocol, TypeVar

from .domain import FixtureStock, Security


T = TypeVar("T")


class SecurityMasterProvider(Protocol):
    name: str
    version: str

    def securities(self, decision_time: datetime) -> tuple[Security, ...]: ...


class KRAlphaDataProvider(Protocol):
    name: str
    version: str
    mode: str

    def snapshot(self, decision_time: datetime) -> tuple[FixtureStock, ...]: ...


class BrokerOrderProvider(Protocol):
    name: str
    version: str

    def health(self) -> bool: ...

    def submit_order(self, *args: object, **kwargs: object) -> object: ...


class DisabledBrokerOrderProvider:
    name = "disabled"
    version = "1"

    def health(self) -> bool:
        return False

    def submit_order(self, *args: object, **kwargs: object) -> object:
        raise RuntimeError("live order submission is not implemented")
