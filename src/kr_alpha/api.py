from __future__ import annotations

from datetime import datetime

from .config import KRAlphaConfig, validate_config
from .service import KRAlphaOverview, build_overview


def get_kr_alpha_overview(decision_time: datetime, config: KRAlphaConfig) -> KRAlphaOverview:
    errors = validate_config(config)
    if errors:
        raise ValueError("invalid KR Alpha config: " + ", ".join(errors))
    return build_overview(decision_time, config)


def get_kr_alpha_health(config: KRAlphaConfig) -> dict[str, object]:
    errors = validate_config(config)
    return {
        "status": "ready" if not errors else "error",
        "data_mode": config.data_mode,
        "live_order_transport": False,
        "config_hash": config.config_hash,
        "errors": list(errors),
    }
