# Korea Investment Modules Specification

## Global Rules For All Modules

The dashboard is an investment decision-support tool, not an automatic trading system.

All modules must obey these rules:

- No automatic order execution.
- No guaranteed return language.
- No deterministic buy/sell instruction.
- Use review-oriented labels such as `review candidate`, `risk management first`, `observe`, `rebalance candidate`, and `reduce exposure candidate`.
- Every number must show:
  - `source`
  - `as_of_date`
  - `available_at` or `fetched_at`
  - `unit`
  - quality/stale status
- Data missing means `N/A`, `empty`, or `unavailable`; never fabricate a value.
- High-risk stocks must not be shown as Buy only because of a high score.
- DART financial data availability must be keyed by `receipt_date` or `available_at`.
- Backtests must avoid look-ahead bias and survivorship bias.
- Explanations must state formula, inputs, and risk gates.

## Shared Context

Each module should receive a common context object in a future implementation:

- selected portfolio holdings
- sidebar watchlist
- selected stock code
- market snapshots
- data quality map
- source metadata registry
- risk defaults
- feature flags
- current timestamp

Recommended context name: `InstitutionalDashboardContext`.

## 1. Portfolio Risk Cockpit

Purpose:

- Make portfolio-level downside risk visible before any alpha or stock ranking.

Placement:

- First new institutional module in the Dashboard, directly after the existing action console / executive summary.
- Later, add a deeper view inside the existing `Portfolio` tab.

Inputs:

- Existing sidebar `total_assets`, `cash`, and holdings CSV.
- Current prices from `Snapshot`.
- Existing portfolio analytics from `src/portfolio/analytics.py`.
- Future sector/country/issuer metadata.

Core outputs:

- total portfolio value
- cash ratio
- single-name concentration
- sector concentration
- estimated drawdown
- risk budget used
- stop-loss impact by holding
- top risk contributors
- stale/missing price warnings

Acceptance criteria:

- Empty portfolio shows mock/demo or explicit empty state depending mode.
- Missing current price uses fallback only if clearly labeled.
- Top holding over threshold raises a warning.
- Risk budget cannot exceed user-entered total assets.
- No order instruction is shown.

## 2. Data Trust & Source Panel

Purpose:

- Make data reliability as visible as price and score.

Placement:

- Second new institutional module in the Dashboard.
- Keep the existing data quality banner/details, but make this module the richer source drilldown.

Inputs:

- Existing `Snapshot` quality fields.
- Data provider metadata from KRX, OpenDART, ECOS, KOSIS, FRED, Naver/FDR fallback.

Core outputs:

- provider matrix
- source coverage by module
- stale data list
- missing fields list
- fallback usage
- quality score
- API key status without exposing secrets

Acceptance criteria:

- Keys are never rendered.
- Missing key shows `not configured`, not the key value.
- Fallback data is never labeled as official realtime.
- Every module can report stale/empty/error state.

## 3. Market Regime & Macro Radar

Purpose:

- Gate risk-taking based on market trend, breadth, volatility, liquidity, and macro pressure.

Placement:

- Third new institutional module in the Dashboard.
- It should augment, not replace, existing market regime cards and Korea Alpha market status.

Inputs:

- KOSPI/KOSDAQ price and breadth.
- ECOS/KOSIS macro data.
- US rates/global macro data if already supported.
- Current `build_market_regime_output()` and `KoreaMarketStatus`.

Core outputs:

- regime label
- risk-on/risk-off score
- cash range
- allowed actions
- prohibited actions
- drivers ranked by contribution
- stale/missing macro warnings

Acceptance criteria:

- Regime cannot be aggressive if key macro data is stale or missing without a warning.
- Risk-off state lowers confidence for alpha modules.
- All drivers show source and timestamp.

## 4. KRW / Rates / FX Dashboard

Purpose:

- Isolate KRW, Korean rates, US rates, and FX pressure that directly affects Korean equity risk.

Placement:

- Fourth new institutional module in the Dashboard.
- Later, add more detail under the existing `Macro` tab.

Inputs:

- USD/KRW.
- KR government bond yields.
- US Treasury yields.
- ECOS/KOSIS where available.

Core outputs:

- FX pressure score
- rates pressure score
- KRW trend and level
- US-KR rate differential
- sensitivity notes for exporters, importers, banks, growth stocks

Acceptance criteria:

- Units are explicit.
- Daily vs intraday frequency is labeled.
- If source is Naver/FDR fallback, the module states it is not official realtime.

## 5. Valuation & Relative Cheapness Panel

Purpose:

- Separate cheapness from quality and momentum.

Placement:

- Fifth new institutional module in the Dashboard.
- Later, link to `Stocks` detail and Korea factor heatmap.

Inputs:

- KRX valuation metrics where available.
- OpenDART financial statement data with receipt-date availability.
- Sector peer set.
- Price and market cap.

Core outputs:

- PER/PBR/EV-EBITDA/PSR where available
- sector percentile
- historical percentile
- value trap warnings
- source completeness

Acceptance criteria:

- No valuation value is calculated from unavailable future filings.
- Cheap but low-quality/high-risk stocks are labeled as value trap risk, not Buy.
- Peer comparison discloses peer universe and survivorship caveat.

## 6. Fundamental Quality Panel

Purpose:

- Show whether earnings, balance sheet, cash flow, and profitability support the score.

Placement:

- Sixth new institutional module in the Dashboard.
- Later, link to `Stocks` detail.

Inputs:

- OpenDART XBRL financial statements.
- Existing `KoreaFundamentalSnapshot`.
- Optional KOSIS/sector context.

Core outputs:

- revenue/operating profit/net income trend
- ROE/ROA/ROIC
- margin quality
- debt risk
- cash flow conversion
- dividend quality
- accounting anomaly flags

Acceptance criteria:

- Uses DART receipt availability, not fiscal period end.
- Missing XBRL facts are shown as unavailable.
- Quality score is explainable and not mixed with price momentum.

## 7. DART Disclosure Catalyst Panel

Purpose:

- Convert disclosures into event risk and catalyst context.

Placement:

- Seventh new institutional module in the Dashboard.
- Should link to the existing `Disclosures` tab.

Inputs:

- OpenDART filing list and disclosure metadata.
- Existing `load_recent_disclosures()` and `KoreaDisclosureEvent`.

Core outputs:

- recent catalysts
- negative event severity
- positive catalyst confidence
- event windows
- filing URL when available
- blocked-new-exposure flags

Acceptance criteria:

- Critical/high risk disclosure blocks aggressive action.
- Empty URL is not rendered as a link.
- Filing date/receipt date is visible.

## 8. Smart Money Flow & Short Pressure Panel

Purpose:

- Show investor flow, foreign/institution behavior, pension flow, and short-selling pressure.

Placement:

- Eighth new institutional module in the Dashboard.
- Later, link to Korea Alpha `supplyDemandRadar`.

Inputs:

- KRX investor flow.
- KRX short selling and short balance.
- Existing `KoreaSupplyDemandPoint`.

Core outputs:

- foreign/institution/pension net buy trend
- program flow
- short-sell value
- short balance ratio
- flow conflict warnings
- liquidity context

Acceptance criteria:

- Flow is never treated as a standalone Buy signal.
- Short pressure can cap or block alpha confidence.
- Missing short data shows unavailable, not zero.

## 9. Forward Alpha Ranking Panel

Purpose:

- Rank review candidates with explainable expected edge and risk gates.

Placement:

- Ninth new institutional module in the Dashboard.
- Must come after valuation, quality, disclosures, and flow so ranking can include those gates.

Inputs:

- Existing Korea Alpha scores.
- Market regime.
- Valuation/quality/disclosure/flow module summaries.
- Signal ledger validation where available.

Core outputs:

- alpha candidate rank
- expected excess return range
- confidence
- risk gate status
- source coverage
- primary positive/negative reasons
- block reasons

Acceptance criteria:

- High score plus high risk displays as `observe` or `risk management first`, not Buy.
- Ranking shows explainability and data coverage.
- Backtest validation uses point-in-time assumptions.

## 10. Portfolio Optimizer & Alert Center

Purpose:

- Turn module outputs into portfolio-level review actions and alerts.

Placement:

- Tenth new institutional module in the Dashboard.
- Later, add deeper controls in the `Portfolio` tab and `Settings`.

Inputs:

- Portfolio Risk Cockpit.
- All preceding module summaries.
- User risk defaults.
- Existing signal ledger.

Core outputs:

- rebalance candidates
- max position by risk budget
- alert rules
- watchlist review queue
- stale data alerts
- thesis invalidation alerts

Acceptance criteria:

- No trade is sent.
- Any suggested action is phrased as candidate/review.
- Alert thresholds are visible and user-adjustable later.
- Optimizer respects risk-off haircuts, cash constraints, concentration caps, and high-risk gates.

## Cross-Module Validation Requirements

Before a panel can graduate from mock/dev to production:

- All inputs have metadata.
- All calculations have unit tests.
- Empty/error/stale states render.
- User-facing text avoids guaranteed returns.
- Backtest validation records universe, rebalance dates, costs, taxes, slippage, and data availability assumptions.
- DART point-in-time availability is tested.
- Feature flag can disable the module without breaking the app.
