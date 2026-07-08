from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "dist"

EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "deploy_staging",
}

EXCLUDED_FILE_NAMES = {
    ".env",
    "credentials",
    "credentials.json",
    "token",
    "token.json",
}

ALLOWED_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".cfg",
    ".ini",
    ".css",
    ".html",
    ".dockerignore",
    ".gitignore",
}

ALLOWED_NAMES = {
    "Dockerfile",
    "Procfile",
    "requirements.txt",
    "runtime.txt",
    "packages.txt",
    "render.yaml",
}


def _is_secretish(path: Path) -> bool:
    name = path.name.lower()
    if name in EXCLUDED_FILE_NAMES:
        return True
    if name.startswith(".env"):
        return True
    return any(token in name for token in ["secret", "credential", "private_key", "id_rsa"])


def _is_excluded(path: Path, root: Path, extra_excludes: set[str]) -> bool:
    rel = path.relative_to(root)
    rel_posix = rel.as_posix()
    if rel_posix in extra_excludes:
        return True
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return True
    if _is_secretish(path):
        return True
    return False


def _is_allowed(path: Path, root: Path, extra_includes: set[str]) -> bool:
    rel_posix = path.relative_to(root).as_posix()
    if rel_posix in extra_includes:
        return True
    if path.name in ALLOWED_NAMES:
        return True
    if path.suffix.lower() in ALLOWED_SUFFIXES:
        return True
    if rel_posix.startswith(".streamlit/") and path.suffix.lower() in {".toml", ".txt"}:
        return True
    if rel_posix.startswith(".github/") and path.suffix.lower() in {".yml", ".yaml", ".md"}:
        return True
    return False


def collect_files(root: Path, includes: list[str], excludes: list[str]) -> list[Path]:
    extra_includes = {Path(item).as_posix().lstrip("./") for item in includes}
    extra_excludes = {Path(item).as_posix().lstrip("./") for item in excludes}
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _is_excluded(path, root, extra_excludes):
            continue
        if not _is_allowed(path, root, extra_includes):
            continue
        if path.stat().st_size > 20 * 1024 * 1024:
            continue
        files.append(path)
    for item in extra_includes:
        path = root / item
        if path.is_file() and path not in files and not _is_excluded(path, root, extra_excludes):
            files.append(path)
    return sorted(set(files))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _human_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def _git_diff(root: Path) -> str | None:
    if not shutil.which("git"):
        return None
    try:
        result = subprocess.run(
            ["git", "diff", "--", "."],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return None
    if result.returncode != 0:
        return f"git diff failed:\n{result.stderr}"
    return result.stdout


def _app_summary(root: Path) -> str:
    app = root / "app.py"
    if not app.exists():
        return "app.py not found.\n"
    text = app.read_text(encoding="utf-8", errors="replace")
    line_count = text.count("\n") + (1 if text else 0)
    return f"""# app.py Summary

- size: {_human_size(app.stat().st_size)}
- lines: {line_count}
- bundle note: app.py is included as a full file because git may be unavailable.
- connector note: large single-file updates can be unstable; see `docs/app-py-modularization-plan.md`.
"""


def _manual_apply_md(git_diff_included: bool) -> str:
    diff_note = (
        "A unified diff is included as `changes.patch`."
        if git_diff_included
        else "No unified diff was generated because git CLI was unavailable or no base snapshot was available."
    )
    return f"""# Manual Apply Instructions

This bundle is a local-first fallback for publishing when git, GitPython, or GitHub tokens are unavailable.

## Contents
- `files/`: full source files for the current project state.
- `manifest.json`: file inventory, hashes, and metadata.
- `checksums.sha256`: SHA-256 checksums.
- `file_sizes.md`: readable file size report.
- `app_py_summary.md`: large app.py summary.
- `changes.patch`: optional git diff when available.

## Diff Status
{diff_note}

## Manual GitHub Apply
1. Open the target GitHub repository in the browser.
2. Create a new branch such as `codex/manual-publish`.
3. Upload or edit files from `files/` into the matching paths.
4. Do not upload `.env`, tokens, credentials, caches, or `.git`.
5. Open a pull request from the new branch.

## Local Apply
Copy files from `files/` into the repository root, preserving directories.

## Verification
Run:

```powershell
py -3.11 -m py_compile app.py
py -3.11 -m unittest discover tests
```
"""


def create_bundle(root: Path, output: Path, includes: list[str], excludes: list[str], dry_run: bool = False) -> dict[str, object]:
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    bundle_dir = output / "patch_bundle"
    zip_path = output / f"codex_patch_bundle_{timestamp}.zip"
    files = collect_files(root, includes, excludes)
    git_diff = _git_diff(root)
    manifest_files = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        manifest_files.append(
            {
                "path": rel,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    if dry_run:
        return {
            "dry_run": True,
            "bundle_dir": str(bundle_dir),
            "zip_path": str(zip_path),
            "file_count": len(files),
            "git_diff_available": git_diff is not None,
        }

    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    (bundle_dir / "files").mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)

    for path in files:
        rel = path.relative_to(root)
        dest = bundle_dir / "files" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)

    manifest = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "root": str(root),
        "file_count": len(files),
        "git_diff_available": git_diff is not None,
        "files": manifest_files,
        "excluded": {
            "directories": sorted(EXCLUDED_DIRS),
            "secret_file_names": sorted(EXCLUDED_FILE_NAMES),
        },
    }
    (bundle_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (bundle_dir / "MANUAL_APPLY.md").write_text(_manual_apply_md(bool(git_diff)), encoding="utf-8")
    (bundle_dir / "app_py_summary.md").write_text(_app_summary(root), encoding="utf-8")
    (bundle_dir / "checksums.sha256").write_text(
        "\n".join(f"{item['sha256']}  {item['path']}" for item in manifest_files) + "\n",
        encoding="utf-8",
    )
    (bundle_dir / "file_sizes.md").write_text(
        "# File Sizes\n\n| File | Size |\n| --- | ---: |\n"
        + "\n".join(f"| `{item['path']}` | {_human_size(int(item['size_bytes']))} |" for item in manifest_files)
        + "\n",
        encoding="utf-8",
    )
    if git_diff:
        (bundle_dir / "changes.patch").write_text(git_diff, encoding="utf-8")
    else:
        (bundle_dir / "changes.patch").write_text(
            "Unified diff unavailable: git CLI was missing or no base snapshot could be read.\n",
            encoding="utf-8",
        )

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in bundle_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(output).as_posix())

    return {
        "dry_run": False,
        "bundle_dir": str(bundle_dir),
        "zip_path": str(zip_path),
        "file_count": len(files),
        "git_diff_available": git_diff is not None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a safe patch bundle without requiring git.")
    parser.add_argument("--include", action="append", default=[], help="Additional path to include.")
    parser.add_argument("--exclude", action="append", default=[], help="Additional path to exclude.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output directory.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned bundle metadata without writing files.")
    args = parser.parse_args(argv)
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    result = create_bundle(ROOT, output, args.include, args.exclude, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
