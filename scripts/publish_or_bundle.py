from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import shutil
import sys

import file_health_report
import github_rest_commit
import make_patch_bundle
import safe_env_check


ROOT = Path(__file__).resolve().parents[1]


def _default_target_branch() -> str:
    return f"codex/publish-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"


def _default_files() -> list[str]:
    files = make_patch_bundle.collect_files(ROOT, [], [])
    return [path.relative_to(ROOT).as_posix() for path in files]


def _write_file_health() -> None:
    output = ROOT / "docs" / "file-health-report.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(file_health_report.build_markdown(ROOT), encoding="utf-8")


def _print_git_workflow(repo: str | None, base_branch: str, target_branch: str, message: str, files: list[str], publish: bool) -> int:
    file_args = " ".join(f'"{item}"' for item in files) if files else "."
    print("Best available path: normal git workflow")
    print("git CLI is available.")
    print("Commands:")
    print(f"  git checkout -b {target_branch}")
    print(f"  git add -- {file_args}")
    print(f"  git commit -m \"{message}\"")
    print(f"  git push -u origin {target_branch}")
    if repo:
        print(f"  Open PR: https://github.com/{repo}/compare/{base_branch}...{target_branch}")
    if publish:
        print("Safety note: wrapper did not execute git commit/push automatically; run the commands above after review.")
    else:
        print("Dry run only. Add --publish after review if you want to use an automated path where supported.")
    return 0


def _run_rest(repo: str | None, base_branch: str, target_branch: str, message: str, files: list[str], publish: bool) -> int:
    if not repo:
        print("REST path requires --repo owner/repo.", file=sys.stderr)
        return 1
    argv = [
        "--repo",
        repo,
        "--base-branch",
        base_branch,
        "--target-branch",
        target_branch,
        "--message",
        message,
        "--files",
        *files,
    ]
    if publish:
        argv.append("--publish")
    return github_rest_commit.main(argv)


def _run_bundle(output: str | None = None) -> int:
    argv: list[str] = []
    if output:
        argv += ["--output", output]
    return make_patch_bundle.main(argv)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Choose the safest publish path: git, REST, or patch bundle.")
    parser.add_argument("--repo", default=None, help="Repository in owner/repo form.")
    parser.add_argument("--base-branch", default="main")
    parser.add_argument("--target-branch", default=None)
    parser.add_argument("--message", default="Codex local publish")
    parser.add_argument("--publish", action="store_true", help="Allow remote write where supported.")
    parser.add_argument("--files", nargs="*", default=None, help="Files to publish or bundle.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry-run is the default.")
    parser.add_argument("--bundle-only", action="store_true")
    parser.add_argument("--rest-only", action="store_true")
    parser.add_argument("--git-only", action="store_true")
    parser.add_argument("--output", default=None, help="Patch bundle output directory.")
    args = parser.parse_args(argv)

    target_branch = args.target_branch or _default_target_branch()
    env_report = safe_env_check.collect(ROOT)
    _write_file_health()
    files = args.files if args.files else _default_files()
    token_present = any(bool(value) for value in (env_report.get("token_env") or {}).values())  # type: ignore[union-attr]
    git_cli = bool(env_report.get("git_cli")) or bool(shutil.which("git"))

    print("Publish path preflight")
    print(f"git_cli: {'present' if git_cli else 'missing'}")
    print(f"token_present: {'true' if token_present else 'false'}")
    print(f"repo: {args.repo or env_report.get('repo') or 'not provided'}")
    print(f"target_branch: {target_branch}")
    print(f"file_count: {len(files)}")

    if args.bundle_only:
        print("Best available path selected: patch bundle")
        return _run_bundle(args.output)

    if args.git_only:
        if not git_cli:
            print("git-only requested, but git CLI is missing.", file=sys.stderr)
            return 1
        return _print_git_workflow(args.repo, args.base_branch, target_branch, args.message, files, args.publish)

    if args.rest_only:
        if not token_present and args.publish:
            print("REST publish requested but no token is present. Creating patch bundle instead.")
            return _run_bundle(args.output)
        return _run_rest(args.repo or env_report.get("repo"), args.base_branch, target_branch, args.message, files, args.publish)

    if git_cli:
        return _print_git_workflow(args.repo or env_report.get("repo"), args.base_branch, target_branch, args.message, files, args.publish)

    if token_present:
        print("Best available path selected: GitHub REST Git Database API")
        return _run_rest(args.repo or env_report.get("repo"), args.base_branch, target_branch, args.message, files, args.publish)

    print("Best available path selected: patch bundle")
    print("No GitHub token is present, so no remote write will be attempted.")
    return _run_bundle(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
