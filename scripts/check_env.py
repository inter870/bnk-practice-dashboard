from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config.env import check_required_secrets, describe_secret_status, load_environment  # noqa: E402


def _line(label: str, status: dict[str, object]) -> str:
    present = "present" if status.get("present") else "missing"
    name = status.get("name") or "none"
    source = status.get("source") or "none"
    return f"{label}: {present} | key_name={name} | source={source} | value={'masked' if status.get('present') else 'missing'}"


def main() -> int:
    result = load_environment()
    required = check_required_secrets()
    status = describe_secret_status()

    print("Environment secret check")
    print(f"project_root: {result.project_root}")
    print(f"streamlit_secrets_loaded: {result.streamlit_secrets_loaded}")
    if result.loaded_files:
        print("loaded_secret_files:")
        for source in result.loaded_files:
            print(f"  - {source}")
    else:
        print("loaded_secret_files: none")

    print(_line("DART/OpenDART", status["dart"]))
    print(_line("BOK ECOS", status["ecos"]))
    print(_line("OpenAI", status["openai"]))

    if not required["ok"]:
        print("missing_required_groups:")
        for group in required["missing"]:
            print(f"  - {group}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
