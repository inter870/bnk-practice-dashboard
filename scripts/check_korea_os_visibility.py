from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
THEME_PATH = ROOT / "src" / "ui" / "korea_os_theme.py"

CRITICAL_FUNCTIONS = [
    "render_korea_recommendation_table",
    "render_korea_factor_heatmap",
    "render_korea_supply_demand_radar",
    "render_korea_disclosure_radar",
    "render_korea_value_up_radar",
    "render_korea_backtest_accuracy_panel",
    "render_korea_portfolio_action_queue",
    "render_korea_advanced_module_summary",
    "render_korea_investment_os_section",
]

RAW_RENDER_PATTERNS = [
    re.compile(r"\bst\.table\s*\("),
    re.compile(r"\bst\.write\s*\(\s*(?:pd\.)?DataFrame", re.IGNORECASE),
    re.compile(r"\bst\.dataframe\s*\("),
]

DARK_TEXT_CLASS_PATTERNS = [
    "text-black",
    "text-gray-900",
    "text-slate-900",
    "text-gray-800",
    "text-slate-800",
]

WARN_PATTERNS = [
    "text-white",
    "color: white",
    "color:#fff",
    "color: #fff",
    "color:#ffffff",
    "color: #ffffff",
]


def read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def function_body(source: str, name: str) -> str:
    start = source.find(f"def {name}")
    if start == -1:
        return ""
    match = re.search(r"\ndef [A-Za-z_][A-Za-z0-9_]*\(", source[start + 1 :])
    if match is None:
        return source[start:]
    return source[start : start + 1 + match.start()]


def add_failure(failures: list[str], message: str) -> None:
    failures.append(f"FAIL: {message}")


def add_warning(warnings: list[str], message: str) -> None:
    warnings.append(f"WARN: {message}")


def main() -> int:
    app_text = read(APP_PATH)
    theme_text = read(THEME_PATH)
    failures: list[str] = []
    warnings: list[str] = []

    if not app_text:
        add_failure(failures, "app.py was not found or could not be read.")
    if not theme_text:
        add_failure(failures, "src/ui/korea_os_theme.py was not found or could not be read.")

    if "from src.ui.korea_os_theme import inject_korea_os_theme" not in app_text:
        add_failure(failures, "Korea OS theme import is missing from app.py.")
    if "inject_korea_os_theme()" not in app_text:
        add_failure(failures, "Korea OS theme is not injected in app.py.")
    if "korea-os-theme" not in app_text:
        add_failure(failures, "Korea OS scoped wrapper class is missing from app.py.")
    if ".korea-os-theme" not in theme_text:
        add_failure(failures, "Korea OS scoped CSS selector is missing from the theme.")
    if "korea-os-table" not in app_text or "korea-os-table" not in theme_text:
        add_failure(failures, "Styled Korea OS table class is missing from app.py or theme CSS.")
    if "korea-os-heatmap-cell" not in app_text or "korea-os-heatmap-cell" not in theme_text:
        add_failure(failures, "Styled Korea OS heatmap cell class is missing from app.py or theme CSS.")
    if "korea-filter-summary" not in app_text or "korea-filter-summary" not in theme_text:
        add_failure(failures, "Styled Korea Alpha filter summary is missing.")

    combined = "\n".join([app_text, theme_text])
    for token in DARK_TEXT_CLASS_PATTERNS:
        if token in combined:
            add_failure(failures, f"Dark text utility '{token}' appears in Korea dashboard files.")
    for token in WARN_PATTERNS:
        if token in combined:
            add_warning(warnings, f"Broad white text token '{token}' appears; verify it is not used for body copy.")

    for name in CRITICAL_FUNCTIONS:
        body = function_body(app_text, name)
        if not body:
            add_warning(warnings, f"Critical function '{name}' was not found.")
            continue
        for pattern in RAW_RENDER_PATTERNS:
            if pattern.search(body):
                add_failure(failures, f"Critical function '{name}' still uses raw Streamlit table/dataframe rendering.")
        if re.search(r"^\s*\|.+\|\s*$", body, flags=re.MULTILINE):
            add_failure(failures, f"Critical function '{name}' appears to contain a raw markdown table.")

    for message in warnings:
        print(message)
    for message in failures:
        print(message)

    if failures:
        print(f"Korea OS visibility guardrail failed: {len(failures)} severe issue(s).")
        return 1
    print("Korea OS visibility guardrail passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
