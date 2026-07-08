# Dashboard Review Checklist

Use this checklist before merging or deploying each institutional dashboard module.

## Scope Control

- [ ] Existing Streamlit app still starts from `app.py`.
- [ ] Existing tab order is preserved unless explicitly changed.
- [ ] No existing Dashboard/Portfolio/Stocks/Alpha Discovery/Disclosures/Macro/Briefing/Signal Outcome/Settings feature is removed.
- [ ] Only one visible module is added at a time.
- [ ] Visible module order follows the priority list.
- [ ] The module is feature-flag friendly.
- [ ] No production backend panel, database migration, real API connector, or ML code is added unless the task explicitly asks for it.

## Data Integrity

- [ ] Every displayed data point includes `source`.
- [ ] Every displayed data point includes `as_of_date`.
- [ ] Every displayed data point includes `available_at` or `fetched_at`.
- [ ] Units are explicit.
- [ ] Stale data is visually flagged.
- [ ] Fallback data is not labeled as official realtime.
- [ ] Missing values render as `N/A`, `unavailable`, `empty`, or `data required`.
- [ ] No `NaN`, `Infinity`, raw exception, empty URL, or broken HTML appears in the UI.
- [ ] No hardcoded API keys or secrets are added.

## Investment Safety

- [ ] No automatic order execution is implemented.
- [ ] No deterministic buy/sell instruction is shown.
- [ ] Recommendation-like labels are explainable review candidates.
- [ ] High-risk stocks are not shown as Buy only because of a high score.
- [ ] Risk gates can override alpha score.
- [ ] Disclosure risk can block new exposure when severity is high/critical.
- [ ] Confidence is reduced for stale or incomplete data.
- [ ] User-facing text avoids guaranteed return language.

## Point-In-Time Analytics

- [ ] DART financial data uses `receipt_date` or `available_at` for analytics availability.
- [ ] Fiscal period end date is not used as the data availability date.
- [ ] Backtests avoid look-ahead bias.
- [ ] Backtests avoid survivorship bias or clearly label mock/universe limitation.
- [ ] Rebalance dates and decision timestamps are explicit.
- [ ] Transaction costs, taxes, and slippage assumptions are visible when used.

## UI States

- [ ] Loading state exists.
- [ ] Empty state exists.
- [ ] Error state exists.
- [ ] Stale state exists.
- [ ] Mobile layout does not create page-level horizontal scroll.
- [ ] Wide tables scroll inside their own container.
- [ ] Text does not overlap or overflow cards/buttons.
- [ ] Tooltips/captions explain formulas and assumptions.
- [ ] Source metadata remains visible on desktop and mobile.

## Test Requirements

- [ ] Pure calculations have unit tests.
- [ ] Metadata completeness is tested.
- [ ] Empty/error/stale state behavior is tested where practical.
- [ ] Risk override behavior is tested.
- [ ] Existing tests still pass.
- [ ] Compile check passes.

Recommended commands:

```powershell
py -3.11 -m compileall app.py src tests
py -3.11 -m unittest discover tests
```

If local `py` is unavailable, document the available Python command or environment limitation.

## Deployment Readiness

- [ ] `.env`, `.env.*`, `.streamlit/secrets.toml`, `data/`, `briefings/`, and DB files remain ignored.
- [ ] Streamlit Cloud/Render secrets are not printed.
- [ ] Feature flag default is safe.
- [ ] Rollback is possible by disabling the feature flag.
- [ ] The public URL loads after deploy.
- [ ] Mobile smoke check confirms no page-level horizontal wobble.

## Module Acceptance Summary

1. Portfolio Risk Cockpit
   - [ ] Portfolio risk, concentration, drawdown, cash, and risk-budget usage render with metadata.
   - [ ] Missing holdings or prices do not crash the app.

2. Data Trust & Source Panel
   - [ ] Provider matrix and stale/fallback warnings render.
   - [ ] API key status is shown without exposing values.

3. Market Regime & Macro Radar
   - [ ] Regime drivers are source-backed.
   - [ ] Risk-off state affects allowed/prohibited actions.

4. KRW / Rates / FX Dashboard
   - [ ] FX/rates pressure is explained with unit/frequency/source.
   - [ ] Fallback data is labeled as fallback.

5. Valuation & Relative Cheapness Panel
   - [ ] Valuation uses point-in-time available financial data.
   - [ ] Value trap warnings can override cheapness.

6. Fundamental Quality Panel
   - [ ] Quality metrics are separate from price momentum.
   - [ ] Missing XBRL fields are explicit.

7. DART Disclosure Catalyst Panel
   - [ ] High/critical filings gate exposure.
   - [ ] Filing receipt date and URL behavior are correct.

8. Smart Money Flow & Short Pressure Panel
   - [ ] Flow and short data are not treated as standalone Buy signals.
   - [ ] Missing short data is unavailable, not zero.

9. Forward Alpha Ranking Panel
   - [ ] Ranking includes risk gates, confidence, and explanations.
   - [ ] High-risk high-score names are not Buy-only.

10. Portfolio Optimizer & Alert Center
    - [ ] Output is review/alert/rebalance candidate only.
    - [ ] Risk budget, cash, and concentration constraints are enforced.
