# app.py Modularization Plan

## Current Responsibilities

`app.py` is currently a large Streamlit entrypoint that includes several responsibilities in one file:

- Page configuration and global CSS injection
- Environment/key loading
- Market data loading and fallback handling
- Korea equity dashboard rendering
- Portfolio intelligence rendering
- Alpha discovery rendering
- Disclosure/macro/briefing tabs
- Chart construction
- Formatting helpers
- Risk/reward and action decision glue code
- Streamlit session-state wiring

Current observed size:

- Size: about 349 KB
- Lines: about 7,421
- Risk: high line-count risk for connector-style whole-file updates, even though it is below the 1 MB connector-risk threshold used by the report script

## Target Structure

```text
app.py                         thin Streamlit entrypoint
src/config.py                  environment and app settings
src/ui/                        global CSS/theme helpers
src/components/                reusable Streamlit render components
src/services/                  data loading and API adapters
src/data/                      static mappings and mock/fallback data
src/charts/                    matplotlib chart builders
src/utils/                     formatting, parsing, safe display helpers
src/models/                    cross-feature dataclasses
src/korea_equity/              existing Korea equity engines and UI support
src/portfolio/                 existing portfolio models/services/analytics
```

## Extraction Priority

### 1. Constants And Configuration
- Move page constants, default symbols, labels, and configuration defaults first.
- Target: `src/config.py`
- Risk: low
- Test: import module and run current unittest suite.

### 2. Formatting Utilities
- Move pure formatting helpers that do not depend on Streamlit.
- Target: `src/utils/formatting.py`
- Risk: low if functions are pure and covered with tests.
- Examples: percent, KRW, score, fallback display, safe float parsing.

### 3. Data Loading
- Move API/fallback loaders behind service functions.
- Target: `src/services/market_data.py`, `src/services/ecos.py`, `src/services/kis.py`
- Risk: medium because caching/session behavior may depend on Streamlit.
- Plan: keep Streamlit cache wrappers near app layer until behavior is verified.

### 4. Chart Builders
- Move matplotlib figure construction into `src/charts/`.
- Risk: medium-low.
- Benefit: smaller UI functions and easier visual smoke tests.

### 5. Reusable UI Sections
- Move stable render blocks into `src/components/`.
- Risk: medium because Streamlit state keys must remain stable.
- Rule: preserve widget keys and session state names exactly.

### 6. Business Logic
- Keep business logic in existing engine modules where possible.
- Avoid moving logic that mixes data fetch, session state, and rendering until tests cover it.

## Low-Risk First PR Plan

1. Add `src/config.py` with constants only.
2. Add `src/utils/formatting.py` and move two or three pure helpers with tests.
3. Move one chart builder into `src/charts/market.py`.
4. Move one small UI card renderer into `src/components/`.
5. Run:

```powershell
py -3.11 -m py_compile app.py src
py -3.11 -m unittest discover tests
```

6. Deploy only after all existing tabs render locally.

## Rollback Plan

- Keep each extraction in a small commit/patch bundle.
- If a Streamlit widget key or session-state behavior breaks, revert only that extraction.
- Keep import names stable with wrapper functions during the transition.
- Avoid moving more than one feature area per PR.

## Test Plan

- Unit tests for pure formatting and analytics.
- Compile checks for `app.py` and `src/`.
- Streamlit smoke check for:
  - Dashboard
  - Portfolio
  - Stocks
  - Alpha Discovery
  - Disclosures
  - Macro
  - Briefing
  - Signal Outcome
  - Settings
- Browser/mobile check for page-level horizontal overflow.

## What Not To Do First

- Do not split all of `app.py` in one change.
- Do not rename session-state keys casually.
- Do not move Streamlit cached functions without validating cache behavior.
- Do not change financial calculations while moving UI files.
- Do not mix deployment fixes and investment logic changes in the same refactor.
