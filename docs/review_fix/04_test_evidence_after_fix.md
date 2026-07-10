# Test Evidence After Fix

## Runtime

| Check | Result |
|---|---|
| Python | 3.11.8 |
| Streamlit | 1.58.0 |
| `compileall -q app.py src tests` | PASS |
| `git diff --check` | PASS |
| `pip check` | PASS, no broken requirements |
| Streamlit health | PASS, `/_stcore/health` returned `ok` |
| Browser console errors | 0 |

## Full Test Repetition

The final worktree was tested three consecutive times with `python -m unittest discover tests`.

| Run | Result | Count |
|---:|---|---:|
| 1 | PASS | 255 |
| 2 | PASS | 255 |
| 3 | PASS | 255 |

No test was deleted or weakened. Bare-mode Streamlit context notices are expected when AppTest imports the app outside a live server.

## UI Audits

- Dark dashboard readability: PASS
- Data Trust display: PASS
- Korean market colors: PASS
- Korean UI localization: PASS
- Korea OS visibility: PASS; broad white-token advisory manually reviewed
- Risk alert Korean UI: PASS

## Browser Evidence

- All nine views opened by direct URL with the expected current-view status.
- Browser-visible Streamlit exceptions: 0 for every view.
- Page-level horizontal overflow: 0 at 390, 768, 1024, and 1440 px.
- Navigation layout: 3 columns at 390/768/1024; 9 columns at 1440.
- Screenshots: `screenshots/dashboard-390-final.png`, `screenshots/dashboard-1440-final.png`.

## Environment And Provider Evidence

- `.env` is ignored and not tracked.
- DART, ECOS, and OpenAI secrets were found through the centralized loader; only masked presence/source status was printed.
- OpenDART live call: blocked by local `tls_error`.
- ECOS live call: blocked by local `tls_error`.
- Docker build: NOT RUN because Docker CLI is not installed.
- Ruff/mypy: NOT RUN because the repository has no configured tools and executables are absent.

## Deployment Evidence

- Dockerfile syntax and repository compile checks pass.
- A container build remains a release-machine gate because this Windows environment has no Docker executable.
