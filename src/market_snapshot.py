from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Snapshot:
    """Serializable market snapshot shared across Streamlit reruns."""

    key: str
    display_name: str
    last_close: float | None
    prev_close: float | None
    change: float | None
    change_pct: float | None
    asof: Any
    raw: Any = None
    source: str = "unknown"
    unit: str = "unknown"
    frequency: str = "unknown"
    quality_score: int = 0
    warnings: list[str] | None = None
    errors: list[str] | None = None
    is_fallback: bool = True
