from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DASHBOARD_UI_FILES = (
    ROOT / "app.py",
    ROOT / "src" / "ui" / "korea_os_theme.py",
    ROOT / "src" / "korea_equity" / "design_tokens.py",
    ROOT / "src" / "institutional" / "ui.py",
)

FORBIDDEN_PATTERNS = (
    re.compile(r"\btext-black\b", re.IGNORECASE),
    re.compile(r"\btext-gray-900\b", re.IGNORECASE),
    re.compile(r"\btext-slate-900\b", re.IGNORECASE),
    re.compile(r"\btext-neutral-900\b", re.IGNORECASE),
    re.compile(r"\btext-zinc-900\b", re.IGNORECASE),
    re.compile(r"color\s*:\s*black\b", re.IGNORECASE),
    re.compile(r"color\s*:\s*#000(?:000)?\b", re.IGNORECASE),
    re.compile(r'fill\s*=\s*["\']black["\']', re.IGNORECASE),
    re.compile(r'stroke\s*=\s*["\']black["\']', re.IGNORECASE),
)


def audit_files(paths: tuple[Path, ...] = DASHBOARD_UI_FILES) -> list[str]:
    failures: list[str] = []
    for path in paths:
        if not path.exists():
            failures.append(f"{path.relative_to(ROOT)}: file missing")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern in FORBIDDEN_PATTERNS:
                if pattern.search(line):
                    rel = path.relative_to(ROOT)
                    failures.append(f"{rel}:{line_number}: forbidden dark-dashboard style: {line.strip()}")
                    break
    return failures


def main() -> int:
    failures = audit_files()
    if failures:
        for failure in failures:
            print(failure)
        print(f"Dark dashboard readability audit failed: {len(failures)} issue(s).")
        return 1
    print("Dark dashboard readability audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
