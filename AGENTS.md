# Repository Agent Guide

This repository is an existing Streamlit financial dashboard. Preserve existing behavior unless a task explicitly asks for implementation changes.

## Architecture

- Main app: `app.py`
- Framework: Streamlit
- Charting: matplotlib
- Tests: Python `unittest`
- Core modules:
  - `src/portfolio/`
  - `src/korea_equity/`
  - `src/discovery/`
  - `src/execution/`
  - `src/exits/`
  - `src/monitoring/`
- Storage: SQLite signal ledger under `data/` when used at runtime.
- Deployment: `Procfile`, `render.yaml`, `runtime.txt`, `requirements.txt`.

## Safety Rules

- Do not rebuild the dashboard.
- Do not replace the existing UI.
- Do not remove existing tabs or modules.
- Keep new features feature-flag friendly.
- Do not add automatic order execution.
- Do not hardcode API keys or secrets.
- Use `.env`, environment variables, or Streamlit secrets through existing patterns.
- Preserve investment safety language: review candidate, observe, risk management first, rebalance candidate.
- Do not label fallback data as official realtime.

## Data Rules

- Every new data point should carry source metadata:
  - `source`
  - `as_of_date`
  - `available_at` or `fetched_at`
  - `unit`
  - quality/stale status
- DART financial analytics must use filing receipt/availability dates, not fiscal period end dates.
- Avoid look-ahead bias and survivorship bias in backtesting.
- Missing data should render as `N/A`, `unavailable`, `empty`, or `data required`.

## Commands

Preferred checks:

```powershell
py -3.11 -m compileall app.py src tests
py -3.11 -m unittest discover tests
```

If `py` is not available in the shell, record the environment limitation and use the configured Python 3.11.8 runtime if available.

## Documentation

Planning documents for institutional modules live in:

- `docs/dashboard-priority-integration-plan.md`
- `docs/korea-investment-modules-spec.md`
- `docs/dashboard-review-checklist.md`

For planning-only tasks, update documentation only and do not change production app behavior.

## Korean Dashboard UI, Localization, and Market Color Rules

- Visible dashboard UI must be Korean-first.
- Keep standard financial abbreviations and source names in English.
- Do not translate API routes, database fields, environment variables, internal enum keys, or code identifiers.
- Internal enum keys must be mapped to Korean display labels.
- Reusable visible labels must come from the central Korean UI dictionary when possible.
- Do not hardcode new English UI strings in dashboard components unless they are approved abbreviations or source names.
- Korean stock market numeric convention: positive market movement, gains, returns, net buy, and upside alpha use red.
- Korean stock market numeric convention: negative market movement, losses, drawdowns, net sell, and downside alpha use blue.
- Flat or neutral market movement uses neutral slate/gray.
- Risk, stale data, warnings, and errors use severity colors, not raw market direction colors.
- Do not rely on color alone; include signs, Korean labels, icons, or accessible text where supported.
- Avoid black or low-contrast text on dark backgrounds.
- Charts, tables, tooltips, alerts, filters, and badges must be readable in Korean.
- Korean labels must not overflow cards or tables.
- Run localization, readability, and Korean market color audits after dashboard UI changes.
- Do not remove or rename dashboard modules during localization or color fixes.

## Data Source, Key, and Fallback Rules

- Do not bypass authentication for APIs that require keys.
- Do not fabricate values or fake exact precision when a reliable source is unavailable.
- Use the central source registry for required keys, source status, accuracy grade, and fallback decisions.
- Missing key display must be source-specific.
- Planned adapters must show `adapter_missing` or `planned`, not "missing keys none".
- Keyless public sources must be labeled as public snapshots and must not be called official real-time data.
- Cached values must be labeled cache and stale when old.
- Mock values must be labeled mock, low confidence, and never treated as real holdings or official data.
- Every displayed value should include source metadata: source, endpoint when available, `as_of_date`, `available_at` or `fetched_at`, stale flag, and accuracy grade.
- Never show `KIS_APP_KEY` or `KIS_APP_SECRET` missing for Naver Finance or FinanceDataReader sources.
- Never use OpenDART endpoints without `OPENDART_API_KEY` or the legacy `DART_API_KEY` alias.
- Never claim "accurate" without a source and timestamp.
- Do not expose, print, log, commit, or hardcode API keys.

## Risk Alert UI and Data Accuracy Rules

- Risk alert UI must be Korean-first.
- Do not display mock portfolio alerts as real actionable alerts.
- Separate holdings source, price source, sector metadata source, and calculation method.
- Format dashboard timestamps in Asia/Seoul Korean format such as `2026.07.08 16:55`.
- Do not show raw ISO timestamps in dashboard risk alert UI.
- Every risk alert must include a Korean title, Korean explanation, Korean review action, severity, actionability, source metadata, and stale/mock status.
- If data is mock, display `모의 데이터` or `예시 알림`.
- If data is stale, display `오래된 데이터`.
- If exact calculation inputs are missing, show `계산 불가` or `실전 판단 제한`.
- Alerts are review gates, not trading instructions.
- Do not fabricate values.
- Do not implement automatic trading.
