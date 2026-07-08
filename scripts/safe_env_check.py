from __future__ import annotations

import argparse
import configparser
import json
import os
import platform
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse


TOKEN_ENV_NAMES = [
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "GITHUB_PAT",
    "CODEX_GITHUB_TOKEN",
    "OPENAI_API_KEY",
]

REPO_ENV_NAMES = ["GITHUB_REPOSITORY", "GH_REPO", "REPO"]


def _present(name: str) -> bool:
    try:
        return bool(os.environ.get(name))
    except Exception:
        return False


def _safe_env_presence() -> dict[str, bool]:
    return {name: _present(name) for name in TOKEN_ENV_NAMES}


def _token_like_env_names() -> list[str]:
    names: list[str] = []
    pattern = re.compile(r"(token|secret|api[_-]?key|credential|(^|[_-])pat($|[_-]))", re.IGNORECASE)
    try:
        for name in os.environ:
            if pattern.search(str(name)):
                names.append(str(name))
    except Exception:
        return []
    return sorted(set(names))


def _repo_from_url(url: str) -> str | None:
    value = (url or "").strip()
    if not value:
        return None
    if value.startswith("git@github.com:"):
        value = value.split(":", 1)[1]
    else:
        parsed = urlparse(value)
        if parsed.netloc.lower() != "github.com":
            return None
        value = parsed.path.lstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    if re.fullmatch(r"[^/\s]+/[^/\s]+", value):
        return value
    return None


def _repo_from_git_config(root: Path) -> str | None:
    config_path = root / ".git" / "config"
    if not config_path.exists():
        return None
    parser = configparser.ConfigParser()
    try:
        parser.read(config_path, encoding="utf-8")
    except Exception:
        return None
    for section in parser.sections():
        if section.startswith('remote "') and parser.has_option(section, "url"):
            repo = _repo_from_url(parser.get(section, "url", fallback=""))
            if repo:
                return repo
    return None


def _repo_from_env() -> str | None:
    for name in REPO_ENV_NAMES:
        value = os.environ.get(name, "").strip()
        if re.fullmatch(r"[^/\s]+/[^/\s]+", value):
            return value
    return None


def collect(root: Path | None = None) -> dict[str, object]:
    cwd = (root or Path.cwd()).resolve()
    repo_env = _repo_from_env()
    repo_git = _repo_from_git_config(cwd)
    return {
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "cwd": str(cwd),
        "git_cli": shutil.which("git"),
        "gh_cli": shutil.which("gh"),
        "token_env": _safe_env_presence(),
        "token_like_env_names_present": _token_like_env_names(),
        "repo": repo_env or repo_git,
        "repo_sources": {
            "env": repo_env,
            "git_config": repo_git,
        },
    }


def _print_text(report: dict[str, object]) -> None:
    print("Safe environment check")
    print(f"python: {report['python']}")
    print(f"platform: {report['platform']}")
    print(f"cwd: {report['cwd']}")
    print(f"git_cli: {'present' if report['git_cli'] else 'missing'}")
    print(f"gh_cli: {'present' if report['gh_cli'] else 'missing'}")
    print(f"repo: {report.get('repo') or 'unknown'}")
    print("token env presence:")
    for name, present in (report["token_env"] or {}).items():  # type: ignore[union-attr]
        print(f"  {name}: {'present' if present else 'missing'}")
    token_like = report.get("token_like_env_names_present") or []
    if token_like:
        print("token-like env names present:")
        for name in token_like:
            print(f"  {name}: present")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safely report local publish environment without printing secrets.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)
    report = collect()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
