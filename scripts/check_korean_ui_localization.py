from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

UI_FILES = (
    ROOT / "app.py",
    ROOT / "src" / "institutional" / "ui.py",
)

VISIBLE_ENGLISH_PATTERNS = (
    re.compile(r"<strong>\s*Portfolio Risk Cockpit\s*</strong>"),
    re.compile(r"<strong>\s*Data Trust & Source Panel\s*</strong>"),
    re.compile(r"<strong>\s*Market Regime & Macro Radar\s*</strong>"),
    re.compile(r"<strong>\s*KRW / Rates / FX Dashboard\s*</strong>"),
    re.compile(r"<strong>\s*Valuation & Relative Cheapness Panel\s*</strong>"),
    re.compile(r"<strong>\s*Fundamental Quality Panel\s*</strong>"),
    re.compile(r"<strong>\s*DART Disclosure Catalyst Panel\s*</strong>"),
    re.compile(r"<strong>\s*Smart Money Flow & Short Pressure Panel\s*</strong>"),
    re.compile(r"<strong>\s*Forward Alpha Ranking Panel\s*</strong>"),
    re.compile(r"<strong>\s*Portfolio Optimizer & Alert Center\s*</strong>"),
    re.compile(r"st\.tabs\(\[\s*[\"']Dashboard[\"']"),
    re.compile(r"section-title\">Portfolio Command Center<"),
    re.compile(r"section-title\">Signal Outcome Ledger<"),
    re.compile(r"section-title\">Settings<"),
    re.compile(r"section-title\">Stocks<"),
    re.compile(r"source\s+\{html\.escape"),
    re.compile(r"as_of\s+\{html\.escape"),
    re.compile(r"fetched\s+\{html\.escape"),
)


def audit_files(paths: tuple[Path, ...] = UI_FILES) -> list[str]:
    failures: list[str] = []
    for path in paths:
        if not path.exists():
            failures.append(f"{path.relative_to(ROOT)}: file missing")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern in VISIBLE_ENGLISH_PATTERNS:
                if pattern.search(line):
                    failures.append(f"{path.relative_to(ROOT)}:{line_number}: visible English UI pattern: {line.strip()}")
                    break
    return failures


def main() -> int:
    failures = audit_files()
    if failures:
        for failure in failures:
            print(failure)
        print(f"Korean UI localization audit failed: {len(failures)} issue(s).")
        return 1
    print("Korean UI localization audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
