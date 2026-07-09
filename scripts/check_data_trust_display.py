from __future__ import annotations

from datetime import datetime, timezone
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.institutional import build_data_trust_source_panel, data_trust_source_panel_html  # noqa: E402


class _Snapshot:
    def __init__(self, asof: datetime, source: str, quality_score: int, is_fallback: bool = False):
        self.asof = asof
        self.source = source
        self.quality_score = quality_score
        self.is_fallback = is_fallback
        self.frequency = "metadata"
        self.unit = "metadata"
        self.warnings = []
        self.errors = []


FORBIDDEN_VISIBLE_PATTERNS = (
    "필요 키 필요 키 없음",
    "누락 없음",
    "adapter planned",
    "KRX/OpenDART adapter planned",
    "missing keys none",
)

REQUIRED_VISIBLE_TEXT = (
    "연결 예정",
    "표시 불가",
    "키 확인: 어댑터 구현 후 확인",
    "기준일: 해당 없음",
    "수집 시각: 2026.07.08 17:39",
)

RAW_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def _sample_html() -> str:
    now = datetime(2026, 7, 8, 8, 39, 17, tzinfo=timezone.utc)
    snapshots = {
        "KOSPI": _Snapshot(now, "Naver Finance", 88, True),
        "KOSDAQ": _Snapshot(now, "Naver Finance", 88, True),
        "USD/KRW": _Snapshot(now, "BOK ECOS", 86, False),
        "US 10Y": _Snapshot(now, "FRED", 80, False),
        "KR 3Y": _Snapshot(now, "BOK ECOS", 86, False),
    }
    state = build_data_trust_source_panel(
        snapshots=snapshots,
        portfolio_holding_count=1,
        using_mock_portfolio=False,
        api_key_status={
            "OPENDART_API_KEY": True,
            "BOK_ECOS_API_KEY": True,
            "KIS_APP_KEY": True,
            "KIS_APP_SECRET": True,
        },
        now=now,
    )
    return data_trust_source_panel_html(state)


def audit_data_trust_html(html: str) -> list[str]:
    failures: list[str] = []
    for pattern in FORBIDDEN_VISIBLE_PATTERNS:
        if pattern in html:
            failures.append(f"forbidden visible Data Trust text: {pattern}")
    if RAW_ISO_RE.search(html):
        failures.append("raw ISO timestamp is visible in Data Trust UI")
    for text in REQUIRED_VISIBLE_TEXT:
        if text not in html:
            failures.append(f"required Data Trust text missing: {text}")
    return failures


def main() -> int:
    failures = audit_data_trust_html(_sample_html())
    if failures:
        for failure in failures:
            print(failure)
        print(f"Data Trust display audit failed: {len(failures)} issue(s).")
        return 1
    print("Data Trust display audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
