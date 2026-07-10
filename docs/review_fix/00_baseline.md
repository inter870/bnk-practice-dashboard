# Review/Fix Baseline

## Repository

- Requested path: `C:\Users\BNKFN\Desktop\bnk_practice\update1`
- Actual application repository: `C:\Users\BNKFN\Desktop\bnk_practice`
- Path resolution: `update1` contains five instruction/configuration documents, no `.git`, and no `app.py`. The parent directory is the only Git worktree and contains the Streamlit entrypoint, so all review and fixes target the parent repository.
- Framework: Streamlit 1.58.0 on Python 3.11.8
- Entrypoint: `app.py`
- Current branch: `main`
- Current HEAD: `f6b4dc7bdbadd9d884e5690e0281d3d93ed1b33b`
- Remote baseline: `origin/main` at the same commit
- BASE_REF: `HEAD`
- Baseline commit SHA: `f6b4dc7bdbadd9d884e5690e0281d3d93ed1b33b`

## Baseline Selection

All development changes are unstaged or untracked and `HEAD` equals `origin/main`. There is no separate local development commit after the remote baseline. Per the AUTO rule, `HEAD` is therefore the unambiguous baseline. No checkout, reset, clean, rebase, or baseline mutation was performed.

## Worktree State Before Fixes

- Staged files: none
- Tracked modified files: 23
- Tracked diff: 2,384 insertions, 413 deletions
- Source-relevant untracked additions: `src/portfolio/context.py`, four new test files, `docs/renewal/`, and the `update1` instruction bundle
- Generated/deployment untracked content: `.deploy_tmp/`, `deploy_staging/`, `dist/`, and `patches/`
- `.deploy_tmp` inventory at review start: 9,799 files, approximately 523 MB
- User changes were preserved in place; no file was reverted.

## Modified Tracked Files

`.dockerignore`, `.env.example`, `Dockerfile`, `app.py`, `render.yaml`, `requirements.txt`, `src/institutional/data_trust.py`, `src/institutional/data_trust_display.py`, `src/institutional/models.py`, `src/institutional/portfolio_optimizer.py`, `src/institutional/ui.py`, `src/korea_equity/backtest_engine.py`, `src/monitoring/signal_ledger.py`, `src/portfolio/__init__.py`, `src/portfolio/service.py`, `src/ui/korea_os_theme.py`, `src/ui/korean_labels.py`, and the associated tracked tests.

## Baseline Test Status

- `python -m compileall -q app.py src tests`: PASS
- `python -m unittest discover tests`: PASS, 220 tests, 1 skipped
- Skip reason: KIS credentials are configured, so the no-credentials branch test is not applicable in this environment
- `import app`: PASS
- Streamlit health endpoint: HTTP 200, body `ok`
- Dark/readability, Data Trust, Korea OS visibility, Korean market color, Korean localization, and risk-alert audits: PASS
- Existing warnings: bare-mode Streamlit context warnings during unit tests; broad white-token advisory from the visibility audit

## Baseline Functional Inventory Summary

The baseline and current worktree both expose the nine primary views: Dashboard, Portfolio, Stocks, Alpha Discovery, Disclosures, Macro, Briefing, Signal Outcome, and Settings. The baseline contains no `st.download_button`, so no existing download control is present to preserve. Detailed inventory remains in `docs/renewal/00_current_inventory.md` and will be cross-checked in the final review.
