from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

THEME_FILES = (
    ROOT / "src" / "ui" / "korea_os_theme.py",
    ROOT / "src" / "korea_equity" / "design_tokens.py",
)

HELPER_FILE = ROOT / "src" / "ui" / "korean_market_colors.py"

REQUIRED_TOKENS = (
    "--kos-market-up: #FF4D4F",
    "--kos-market-down: #3B82F6",
    "--korea-market-up: #FF4D4F",
    "--korea-market-down: #3B82F6",
)

REQUIRED_HELPERS = (
    "getKoreanMarketDirection",
    "getKoreanMarketColorToken",
    "getKoreanMarketColorClass",
    "getKoreanMarketBadgeClass",
    "getRiskSeverityColorClass",
    "getRatingColorClass",
    "getFlowColorClass",
    "getReturnColorClass",
    "getChartSeriesColor",
)

CONTEXT_PATTERNS = (
    (
        "metric-change-pos",
        re.compile(r"\.stApp\s+\.metric-change-pos[\s\S]{0,160}var\(--kos-market-up\)", re.MULTILINE),
    ),
    (
        "metric-change-neg",
        re.compile(r"\.stApp\s+\.metric-change-neg[\s\S]{0,160}var\(--kos-market-down\)", re.MULTILINE),
    ),
    (
        "korea-flow-pos",
        re.compile(r"\.korea-flow-pos[\s\S]{0,140}(?:--kos-market-up|--korea-market-up)", re.MULTILINE),
    ),
    (
        "korea-flow-neg",
        re.compile(r"\.korea-flow-neg[\s\S]{0,140}(?:--kos-market-down|--korea-market-down)", re.MULTILINE),
    ),
)


def audit_files(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    theme_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace") for path in THEME_FILES if path.exists()
    )
    helper_text = HELPER_FILE.read_text(encoding="utf-8", errors="replace") if HELPER_FILE.exists() else ""

    for token in REQUIRED_TOKENS:
        if token not in theme_text:
            failures.append(f"missing Korean market color token: {token}")

    for helper in REQUIRED_HELPERS:
        if f"def {helper}" not in helper_text:
            failures.append(f"missing Korean market color helper: {helper}")

    for label, pattern in CONTEXT_PATTERNS:
        if not pattern.search(theme_text):
            failures.append(f"{label} is not mapped to Korean market red/blue tokens")

    if "MARKET_UP = \"#FF4D4F\"" not in helper_text:
        failures.append("MARKET_UP constant must be Korean market red #FF4D4F")
    if "MARKET_DOWN = \"#3B82F6\"" not in helper_text:
        failures.append("MARKET_DOWN constant must be Korean market blue #3B82F6")
    if "RISK_CRITICAL = \"#F97316\"" not in helper_text:
        failures.append("risk critical color must stay separate from market-down blue")

    return failures


def main() -> int:
    failures = audit_files()
    if failures:
        for failure in failures:
            print(failure)
        print(f"Korean market color audit failed: {len(failures)} issue(s).")
        return 1
    print("Korean market color audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
