# Dashboard Priority Integration Plan

## Purpose

This document plans how to add institutional-grade investment decision modules to the existing dashboard without rebuilding it, replacing the UI, or breaking current features.

Visible dashboard additions must be introduced one module at a time in this priority order:

1. Portfolio Risk Cockpit
2. Data Trust & Source Panel
3. Market Regime & Macro Radar
4. KRW / Rates / FX Dashboard
5. Valuation & Relative Cheapness Panel
6. Fundamental Quality Panel
7. DART Disclosure Catalyst Panel
8. Smart Money Flow & Short Pressure Panel
9. Forward Alpha Ranking Panel
10. Portfolio Optimizer & Alert Center

Technical implementation may create shared contracts, adapters, mock data, and tests first, but each visible dashboard addition must follow the priority order above.

## Existing Architecture Summary

Detected project type:

- Frontend framework: Streamlit, not React/Vite/Next.
- Main entrypoint: `app.py`.
- UI structure: Streamlit tabs created in `main()`.
- Current tab order:
  1. `Dashboard`
  2. `Portfolio`
  3. `Stocks`
  4. `Alpha Discovery`
  5. `Disclosures`
  6. `Macro`
  7. `Briefing`
  8. `Signal Outcome`
  9. `Settings`
- Charting library: matplotlib via `matplotlib.pyplot`.
- Backend framework: none. Data access is local Streamlit service/helper functions plus external HTTP calls.
- API route structure: none today. Future API boundaries should be planned as service facades first, not HTTP routes.
- Storage layer: SQLite only for `data/signal_ledger.sqlite3` through `src/monitoring/signal_ledger.py`. Other data is in memory, mock modules, Streamlit cache, or external providers.
- Data fetching pattern:
  - `app.py` contains cached loaders with `@st.cache_data`.
  - `src/portfolio/service.py` returns portfolio mock/manual-input data.
  - `src/korea_equity/service.py` returns Korea equity mock/computed data.
  - `src/discovery`, `src/execution`, `src/exits`, and `src/monitoring` hold pure or mostly pure engines.
- Authentication/environment pattern:
  - `src/config/env.py` centralizes secret loading; `app.py` keeps `config_value()` only as a compatibility wrapper.
  - Priority: existing `os.environ`, `st.secrets`, `ENV_FILE_PATH`, `APP_ENV_FILE`, `DOTENV_CONFIG_PATH`, default external `.env`, `.env.local`, `.env`, then `.streamlit/secrets.toml`.
  - Known keys and aliases: `DART_API_KEY` / `OPENDART_API_KEY` / `OPEN_DART_API_KEY`, `ECOS_API_KEY` / `ECOS_AUTH_KEY` / `BOK_ECOS_API_KEY` / `BANK_OF_KOREA_API_KEY`, `OPENAI_API_KEY`, `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_BASE_URL`.
  - `.gitignore` excludes `.env`, `.env.*`, `.streamlit/secrets.toml`, `secrets.toml`, `data/`, `briefings/`, and DB/log files.
- Test framework: Python `unittest`.
- Runtime/deploy:
  - Python `3.11.8` in `runtime.txt`.
  - `requirements.txt` includes Streamlit, FinanceDataReader, pandas, numpy, matplotlib, requests, BeautifulSoup.
  - `Procfile` starts `streamlit run app.py`.
  - `render.yaml` defines a Docker web service with synced secrets disabled for API keys.

## Existing Dashboard Modules To Preserve

Do not remove or break:

- Current sidebar watchlist input and portfolio CSV input.
- Dashboard market cards for KOSPI, KOSDAQ, USD/KRW, US 10Y, KR 3Y.
- Executive decision report/action console.
- Data quality banner and snapshot quality scoring.
- Portfolio Intelligence section.
- Korea Alpha Engine and Korea Investment OS v2.
- Fear/Greed, ECOS macro cards, stock cards, return comparison, candle/volume chart.
- Portfolio tab, Stocks tab, Alpha Discovery tab, Disclosures tab, Macro tab, Briefing tab, Signal Outcome tab, Settings tab.
- Existing SQLite signal ledger behavior.
- GPT briefing validator and safety language.

## Dashboard Display Order

Keep the current top-level Streamlit tab order unless a later task explicitly requests navigation redesign. Inside the `Dashboard` tab, insert the new institutional module stack after the current executive summary/action console and before lower-priority existing detail sections.

Planned `Dashboard` visual order:

1. Header and market snapshot cards
2. Existing action console / executive decision summary
3. Portfolio Risk Cockpit
4. Data Trust & Source Panel
5. Market Regime & Macro Radar
6. KRW / Rates / FX Dashboard
7. Valuation & Relative Cheapness Panel
8. Fundamental Quality Panel
9. DART Disclosure Catalyst Panel
10. Smart Money Flow & Short Pressure Panel
11. Forward Alpha Ranking Panel
12. Portfolio Optimizer & Alert Center
13. Existing Portfolio Intelligence section
14. Existing Korea Alpha / Korea Investment OS sections
15. Existing Fear/Greed, ECOS cards, stock cards, charts, and data quality details

If the page becomes too long, use a compact in-page anchor nav above the new module stack, but do not replace the current Streamlit tabs.

## Technical Implementation Order

The visible module order must stay fixed, but the technical order should reduce risk:

1. Add shared institutional data contracts and status wrappers.
2. Add mock data/adapters behind feature flags.
3. Add test-only pure calculations for Portfolio Risk Cockpit.
4. Add Portfolio Risk Cockpit UI behind a feature flag.
5. Repeat module-by-module in visible priority order.

No production data provider connection should be added until the corresponding panel has contracts, loading/empty/error/stale states, source metadata, and tests.

## Shared Data Model Needed

Add a future package such as `src/institutional/` only when implementation begins.

Recommended shared contracts:

```python
DataStatus = Literal["loading", "ready", "empty", "error", "stale"]

@dataclass(frozen=True)
class DataSourceMeta:
    source: str
    provider: str | None
    source_url: str | None
    as_of_date: str | None
    available_at: str | None
    fetched_at: str | None
    frequency: str
    unit: str
    quality_score: int
    is_fallback: bool
    warnings: tuple[str, ...]
    errors: tuple[str, ...]

@dataclass(frozen=True)
class DataPoint:
    key: str
    label: str
    value: Any
    meta: DataSourceMeta

@dataclass(frozen=True)
class ModuleState:
    module_id: str
    status: DataStatus
    title: str
    summary: str
    data_points: tuple[DataPoint, ...]
    explanation: tuple[str, ...]
    risk_flags: tuple[str, ...]
    stale_after_minutes: int
```

Rules:

- Every rendered data point must expose `source`, `as_of_date`, and either `available_at` or `fetched_at`.
- DART financial data must use `receipt_date` or `available_at`, not fiscal period end date, for analytics availability.
- Historical analytics must not use future data relative to the evaluation timestamp.
- All recommendation-like outputs must include explanation, confidence, blocking conditions, and risk flags.
- High-risk stocks must not appear as Buy only because their score is high.

## API Endpoint Plan

There is no backend API layer today. Plan endpoints as service boundaries first.

Future service facade functions:

- `get_portfolio_risk_cockpit(context) -> ModuleState`
- `get_data_trust_panel(context) -> ModuleState`
- `get_market_regime_macro_radar(context) -> ModuleState`
- `get_krw_rates_fx_dashboard(context) -> ModuleState`
- `get_valuation_relative_cheapness(context) -> ModuleState`
- `get_fundamental_quality_panel(context) -> ModuleState`
- `get_dart_disclosure_catalyst_panel(context) -> ModuleState`
- `get_smart_money_short_pressure_panel(context) -> ModuleState`
- `get_forward_alpha_ranking_panel(context) -> ModuleState`
- `get_portfolio_optimizer_alert_center(context) -> ModuleState`

If a backend is introduced later, map these to read-only HTTP endpoints:

- `GET /api/dashboard/modules/portfolio-risk`
- `GET /api/dashboard/modules/data-trust`
- `GET /api/dashboard/modules/market-regime`
- `GET /api/dashboard/modules/krw-rates-fx`
- `GET /api/dashboard/modules/valuation`
- `GET /api/dashboard/modules/fundamental-quality`
- `GET /api/dashboard/modules/dart-catalysts`
- `GET /api/dashboard/modules/smart-money-short-pressure`
- `GET /api/dashboard/modules/forward-alpha`
- `GET /api/dashboard/modules/portfolio-optimizer-alerts`

All endpoints must be read-only. No automatic order execution endpoint is allowed.

## Frontend Component Plan

Streamlit component approach:

- Add small render helpers in `app.py` first only if necessary.
- Prefer extracting future institutional UI into `src/institutional/ui.py` once stable.
- Reuse existing dark-purple design tokens from `src/korea_equity/design_tokens.py` and `src/ui/korea_os_theme.py`.
- Reuse existing card/table patterns:
  - compact card
  - module header
  - badge
  - source/stale caption
  - horizontally scrollable table on mobile
- Each module must render four states:
  - loading
  - empty
  - error
  - stale
- Each module must include an explanation block that states formula, data inputs, limitations, and risk gate logic.

## Mock Data Plan

Create mock data only under a dedicated module when implementation begins, for example:

- `src/institutional/mock_data.py`

Mock data must:

- Use realistic Korean market identifiers and KRW units.
- Include `DataSourceMeta` for every value.
- Include stale and missing examples for UI state tests.
- Avoid pretending mock data is live.
- Support existing watchlist and portfolio CSV inputs.
- Include high-risk stocks to validate that risk gates override raw scores.

## Feature Flag Plan

Use feature flags before showing new modules by default.

Suggested env flags:

- `ENABLE_PORTFOLIO_RISK_COCKPIT`
- `ENABLE_DATA_TRUST_PANEL`
- `ENABLE_MARKET_REGIME_MACRO_RADAR`
- `ENABLE_KRW_RATES_FX_DASHBOARD`
- `ENABLE_VALUATION_RELATIVE_CHEAPNESS`
- `ENABLE_FUNDAMENTAL_QUALITY_PANEL`
- `ENABLE_DART_DISCLOSURE_CATALYST_PANEL`
- `ENABLE_SMART_MONEY_SHORT_PRESSURE_PANEL`
- `ENABLE_FORWARD_ALPHA_RANKING_PANEL`
- `ENABLE_PORTFOLIO_OPTIMIZER_ALERT_CENTER`

Default should be off for production until tests and manual Streamlit smoke checks pass, except for mock/dev mode if explicitly enabled.

## Test Plan

Required tests before each visible module ships:

- Pure calculation tests for module analytics.
- Data metadata tests: every `DataPoint` has `source`, `as_of_date`, and `available_at` or `fetched_at`.
- Loading/empty/error/stale render tests where possible.
- Safety tests:
  - no hardcoded API keys
  - no automatic order execution language
  - high-risk candidate is gated away from Buy-only display
  - DART financial analytics use `receipt_date` or `available_at`
  - backtests avoid look-ahead and survivorship bias
- Existing regression tests:
  - `py -3.11 -m compileall app.py src tests`
  - `py -3.11 -m unittest discover tests`

If `py` is not on PATH in the local shell, use the configured Python 3.11.8 environment and record the exact command used.

## Rollback Plan

- Ship one visible module at a time.
- Keep each module behind a feature flag.
- Avoid schema-breaking changes to current `Snapshot`, `Holding`, `KoreaFactorScore`, and signal ledger tables.
- Keep old render path active until the new module is verified.
- If a module causes runtime errors, disable the module flag without reverting unrelated code.
- If data provider assumptions are wrong, keep mock/empty state and do not fabricate values.

## First Implementation Task

Recommended next task:

Implement the shared institutional contracts and the hidden Portfolio Risk Cockpit calculation layer only.

Scope:

- Add `src/institutional/models.py`.
- Add `src/institutional/portfolio_risk.py`.
- Add mock/test fixtures only.
- Add tests for risk concentration, drawdown, risk budget, source metadata, stale states, and high-risk gating.
- Do not add visible Dashboard UI until those tests pass.

Acceptance for the first implementation task:

- Existing app behavior unchanged with all feature flags off.
- Portfolio Risk Cockpit data can be built from existing sidebar portfolio CSV or mock holdings.
- Every data point carries source/date metadata.
- Tests pass.

## Key Risks And Mitigations

- Risk: `app.py` is large and fragile.
  - Mitigation: add small adapters first; avoid broad refactors.
- Risk: data provider timestamps differ from economic availability.
  - Mitigation: keep `as_of_date`, `available_at`, and `fetched_at` separate.
- Risk: scoring can imply deterministic recommendations.
  - Mitigation: use candidate/review/risk-gate language; show blockers.
- Risk: backtests can accidentally use future listings or filings.
  - Mitigation: require point-in-time universe and DART `receipt_date` before validation.
- Risk: UI becomes too dense.
  - Mitigation: compact card stack, source captions, and in-page anchors.
- Risk: Streamlit Cloud secrets leak.
  - Mitigation: no hardcoded keys, use `.env`/env/`st.secrets`, keep `.gitignore`.
