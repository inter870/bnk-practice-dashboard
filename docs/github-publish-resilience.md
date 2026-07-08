# GitHub Publish Resilience Workflow

This project uses a Streamlit/Python dashboard with a large `app.py`. A direct connector-style whole-file update can be brittle when the file is large, git is unavailable, or GitHub credentials are not visible in the current shell. This workflow gives the repository a deterministic fallback path.

## Problem This Solves
- `git` may not be installed or may not be on `PATH`.
- GitPython is not enough when `git.exe` is missing because it shells out to the git executable.
- GitHub tokens may not be available in the environment.
- `app.py` is large enough that whole-file connector updates can be unstable.
- Remote writes should not happen by accident.

## Safe Paths

### 1. Normal Git Path
Use this when `git` is installed and authenticated:

```powershell
git status --short
git checkout -b codex/publish-YYYYMMDD-HHMMSS
git add -- app.py src scripts docs tests requirements.txt
git commit -m "Publish Stance Stock Strategy updates"
git push -u origin codex/publish-YYYYMMDD-HHMMSS
```

The wrapper prints these commands when git is available. It does not commit or push automatically by default.

### 2. REST Commit Path
Use this when git is missing but a GitHub token exists. The script uses only Python standard library modules and the GitHub REST Git Database API.

Dry run:

```powershell
py -3.11 scripts/publish_or_bundle.py --repo OWNER/REPO --base-branch main
```

Publish to a branch:

```powershell
py -3.11 scripts/publish_or_bundle.py --repo OWNER/REPO --base-branch main --publish
```

The publisher creates or updates a target branch such as `codex/publish-YYYYMMDD-HHMMSS`. It does not force push and does not update `main` directly.

### 3. Patch Bundle Path
Use this when no GitHub token is available:

```powershell
py -3.11 scripts/publish_or_bundle.py --bundle-only
```

This creates:

```text
dist/patch_bundle/
dist/codex_patch_bundle_<timestamp>.zip
```

The bundle includes source files, documentation, checksums, file sizes, and manual apply instructions. It excludes `.env`, `.git`, caches, virtual environments, existing `dist`, and secret-like files.

## Environment Check

```powershell
py -3.11 scripts/safe_env_check.py
py -3.11 scripts/safe_env_check.py --json
```

This prints only presence/absence for token-like environment variables. It never prints token values.

## Set A Token Safely In PowerShell

```powershell
$env:GH_TOKEN = "YOUR_TOKEN_HERE"
```

Remove it from the current shell session:

```powershell
Remove-Item Env:\GH_TOKEN
```

Do not put tokens in `.env`, source files, screenshots, logs, patch bundles, or documentation.

## REST Publisher Details

The REST publisher performs this workflow when `--publish` is explicitly provided:

1. Read `GH_TOKEN`, `GITHUB_TOKEN`, or `GITHUB_PAT`.
2. Get the base branch ref.
3. Get the base commit and tree.
4. Create blobs for selected local files.
5. Create a tree with the base tree.
6. Create a commit.
7. Create or update the target branch without force.
8. Print the compare URL for a pull request.

Dry-run mode does not write remotely.

## Manual Fallback

When only a bundle is available:

1. Open the generated zip.
2. Review `MANUAL_APPLY.md`.
3. Create a branch on GitHub.
4. Upload files from `files/`, preserving paths.
5. Do not upload `.env`, credentials, caches, or `.git`.
6. Open a pull request.

## File Health Report

```powershell
py -3.11 scripts/file_health_report.py
```

This writes:

```text
docs/file-health-report.md
```

It reports `app.py` size, line count, function count, import count, and longest functions.

## Troubleshooting Matrix

| Symptom | Meaning | Next Step |
| --- | --- | --- |
| git missing | No git CLI is on PATH | Use REST path with token or patch bundle |
| token missing | No `GH_TOKEN`, `GITHUB_TOKEN`, or `GITHUB_PAT` | Run bundle path or set token |
| 401 | Token invalid | Replace token and retry |
| 403 | Token lacks permission or rate limit hit | Grant repo contents permission or wait |
| 404 | Repo or branch not visible to token | Check `OWNER/REPO`, token scope, base branch |
| 409 | Branch update conflict | Script creates a timestamped branch instead of force pushing |
| 422 | Branch exists or invalid request | Script retries safe branch flow when possible |
| file too large | File exceeds hard stop | Review file, split it, or pass `--allow-large` intentionally |
| base branch missing | `main` or selected branch does not exist | Use `--base-branch master` or the correct branch |

## Recommended Commands

No token:

```powershell
py -3.11 scripts/publish_or_bundle.py --repo OWNER/REPO --base-branch main --bundle-only
```

Token later:

```powershell
$env:GH_TOKEN = "YOUR_TOKEN_HERE"
py -3.11 scripts/publish_or_bundle.py --repo OWNER/REPO --base-branch main --publish
```

## Modularization Recommendation

`app.py` should gradually become a thin entrypoint. See `docs/app-py-modularization-plan.md` for a low-risk extraction plan.
