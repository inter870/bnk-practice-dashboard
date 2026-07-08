from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = "https://api.github.com"
TOKEN_NAMES = ["GH_TOKEN", "GITHUB_TOKEN", "GITHUB_PAT"]


class GitHubApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"GitHub API error {status}: {message}")
        self.status = status
        self.message = message


def _token() -> tuple[str | None, str | None]:
    for name in TOKEN_NAMES:
        value = os.environ.get(name)
        if value:
            return name, value
    return None, None


def _safe_path(path_text: str) -> Path:
    rel = Path(path_text)
    if rel.is_absolute():
        try:
            rel = rel.relative_to(ROOT)
        except ValueError as exc:
            raise ValueError(f"file is outside repository: {path_text}") from exc
    normalized = Path(*[part for part in rel.parts if part not in ("", ".")])
    if any(part == ".." for part in normalized.parts):
        raise ValueError(f"unsafe relative path: {path_text}")
    name = normalized.name.lower()
    if name == ".env" or name.startswith(".env") or any(token in name for token in ["secret", "credential", "private_key"]):
        raise ValueError(f"refusing to include secret-like file: {path_text}")
    return normalized


def _collect_files(file_args: list[str], allow_large: bool, max_warning: int, hard_stop: int) -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    for item in file_args:
        rel = _safe_path(item)
        path = ROOT / rel
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"file not found: {rel.as_posix()}")
        size = path.stat().st_size
        if size > hard_stop and not allow_large:
            raise ValueError(f"file exceeds hard size stop ({hard_stop} bytes): {rel.as_posix()}")
        files.append(
            {
                "path": rel.as_posix(),
                "local_path": path,
                "size_bytes": size,
                "large_warning": size > max_warning,
            }
        )
    deduped: dict[str, dict[str, object]] = {str(item["path"]): item for item in files}
    return [deduped[key] for key in sorted(deduped)]


def _request(method: str, repo: str, api_path: str, token: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    url = f"{API_ROOT}/repos/{repo}{api_path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "codex-local-publisher",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        message = raw
        try:
            parsed = json.loads(raw)
            message = str(parsed.get("message") or raw)
        except Exception:
            pass
        raise GitHubApiError(exc.code, message) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"network error: {exc.reason}") from exc


def _create_blob(repo: str, token: str, file_info: dict[str, object]) -> str:
    path = file_info["local_path"]
    assert isinstance(path, Path)
    content = base64.b64encode(path.read_bytes()).decode("ascii")
    response = _request(
        "POST",
        repo,
        "/git/blobs",
        token,
        {"content": content, "encoding": "base64"},
    )
    sha = response.get("sha")
    if not isinstance(sha, str):
        raise RuntimeError(f"blob creation returned no sha for {file_info['path']}")
    return sha


def _get_ref(repo: str, token: str, branch: str) -> dict[str, object] | None:
    try:
        return _request("GET", repo, f"/git/ref/heads/{branch}", token)
    except GitHubApiError as exc:
        if exc.status == 404:
            return None
        raise


def publish(
    repo: str,
    base_branch: str,
    target_branch: str,
    message: str,
    files: list[dict[str, object]],
    create_branch: bool,
    open_pr: bool,
) -> dict[str, object]:
    token_name, token_value = _token()
    if not token_value:
        raise RuntimeError("missing GitHub token; set GH_TOKEN or GITHUB_TOKEN before using --publish")
    if target_branch == base_branch:
        raise RuntimeError("refusing to update the base branch directly; choose a target branch")

    base_ref = _get_ref(repo, token_value, base_branch)
    if not base_ref:
        raise RuntimeError(f"base branch not found: {base_branch}")
    base_sha = str(((base_ref.get("object") or {}) if isinstance(base_ref.get("object"), dict) else {}).get("sha") or "")
    if not base_sha:
        raise RuntimeError("base branch ref did not include a commit sha")
    base_commit = _request("GET", repo, f"/git/commits/{base_sha}", token_value)
    base_tree = str(((base_commit.get("tree") or {}) if isinstance(base_commit.get("tree"), dict) else {}).get("sha") or "")
    if not base_tree:
        raise RuntimeError("base commit did not include a tree sha")

    tree_entries = []
    for item in files:
        blob_sha = _create_blob(repo, token_value, item)
        tree_entries.append(
            {
                "path": item["path"],
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha,
            }
        )

    tree = _request("POST", repo, "/git/trees", token_value, {"base_tree": base_tree, "tree": tree_entries})
    tree_sha = str(tree.get("sha") or "")
    if not tree_sha:
        raise RuntimeError("tree creation returned no sha")
    commit = _request(
        "POST",
        repo,
        "/git/commits",
        token_value,
        {"message": message, "tree": tree_sha, "parents": [base_sha]},
    )
    new_sha = str(commit.get("sha") or "")
    if not new_sha:
        raise RuntimeError("commit creation returned no sha")

    target_ref = _get_ref(repo, token_value, target_branch)
    branch_used = target_branch
    if target_ref is None:
        if not create_branch:
            raise RuntimeError(f"target branch does not exist and create_branch=false: {target_branch}")
        try:
            _request("POST", repo, "/git/refs", token_value, {"ref": f"refs/heads/{target_branch}", "sha": new_sha})
        except GitHubApiError as exc:
            if exc.status not in {409, 422}:
                raise
            branch_used = f"{target_branch}-{dt.datetime.now().strftime('%H%M%S')}"
            _request("POST", repo, "/git/refs", token_value, {"ref": f"refs/heads/{branch_used}", "sha": new_sha})
    else:
        try:
            _request("PATCH", repo, f"/git/refs/heads/{target_branch}", token_value, {"sha": new_sha, "force": False})
        except GitHubApiError as exc:
            if exc.status != 409:
                raise
            branch_used = f"{target_branch}-{dt.datetime.now().strftime('%H%M%S')}"
            _request("POST", repo, "/git/refs", token_value, {"ref": f"refs/heads/{branch_used}", "sha": new_sha})

    result: dict[str, object] = {
        "published": True,
        "token_env": token_name,
        "repo": repo,
        "base_branch": base_branch,
        "target_branch": branch_used,
        "commit_sha": new_sha,
        "files": [item["path"] for item in files],
    }
    if open_pr:
        result["pull_request_note"] = (
            f"Create a PR at https://github.com/{repo}/compare/{base_branch}...{branch_used}"
        )
    return result


def dry_run_plan(repo: str, base_branch: str, target_branch: str, message: str, files: list[dict[str, object]]) -> dict[str, object]:
    token_name, token_value = _token()
    return {
        "dry_run": True,
        "would_publish": False,
        "repo": repo,
        "base_branch": base_branch,
        "target_branch": target_branch,
        "message": message,
        "token_present": bool(token_value),
        "token_env": token_name if token_value else None,
        "files": [
            {
                "path": item["path"],
                "size_bytes": item["size_bytes"],
                "large_warning": item["large_warning"],
            }
            for item in files
        ],
        "publish_command": "add --publish to perform the remote branch update",
    }


def _default_target_branch() -> str:
    return f"codex/publish-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Commit files to GitHub via REST Git Database API without git.exe.")
    parser.add_argument("--repo", required=True, help="Repository in owner/repo form.")
    parser.add_argument("--base-branch", default="main", help="Base branch name.")
    parser.add_argument("--target-branch", default=None, help="Target branch name.")
    parser.add_argument("--message", default="Codex publish bundle", help="Commit message.")
    parser.add_argument("--files", nargs="+", required=True, help="Files to include in the commit.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry-run is the default.")
    parser.add_argument("--publish", action="store_true", help="Perform remote writes.")
    parser.add_argument("--create-branch", choices=["true", "false"], default="true")
    parser.add_argument("--open-pr", action="store_true", help="Print PR creation URL after publish.")
    parser.add_argument("--allow-large", action="store_true", help="Allow files over the hard stop.")
    parser.add_argument("--max-file-size", type=int, default=5 * 1024 * 1024, help="Large-file warning threshold.")
    parser.add_argument("--hard-stop-size", type=int, default=50 * 1024 * 1024, help="Hard stop unless --allow-large.")
    args = parser.parse_args(argv)

    target_branch = args.target_branch or _default_target_branch()
    try:
        files = _collect_files(args.files, args.allow_large, args.max_file_size, args.hard_stop_size)
        if args.publish:
            result = publish(
                args.repo,
                args.base_branch,
                target_branch,
                args.message,
                files,
                create_branch=args.create_branch == "true",
                open_pr=args.open_pr,
            )
        else:
            result = dry_run_plan(args.repo, args.base_branch, target_branch, args.message, files)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except GitHubApiError as exc:
        print(f"GitHub API failed with status {exc.status}: {exc.message}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"publish failed safely: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
