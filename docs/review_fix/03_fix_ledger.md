# Review/Fix Ledger

## Scope

- Baseline: `f6b4dc7bdbadd9d884e5690e0281d3d93ed1b33b`
- Existing user changes were preserved; no reset, checkout, clean, rebase, or force operation was used.
- No order execution was added, no API route was renamed, and no secret was exposed.

## Verified Fixes

| ID | Severity | Resolution | Evidence |
|---|---|---|---|
| RF-001 | High | Missing current price blocks canonical valuation; average cost is not substituted. | `src/portfolio/context.py`, context tests |
| RF-002 | High | Fixed-current-quantity history is a risk proxy and cannot feed realized performance metrics. | `src/portfolio/context.py`, visibility tests |
| RF-003 | High | Backtest entry requires the first tradable observation strictly after feature availability. | `src/korea_equity/backtest_engine.py`, integrity tests |
| RF-004 | High | Market is preserved, KOSDAQ cap enforced, and target stocks plus cash reconcile to 100%. | optimizer module/tests |
| RF-005 | High | Concentration calculations accept the cash-inclusive authoritative total. | portfolio analytics/tests |
| RF-006 | High | Uncalibrated scores no longer create expected-return probabilities or action-score credit. | `app.py`, core tests |
| RF-007 | Medium | KIS OAuth cache uses credential fingerprint, not dashboard refresh token. | `app.py:2917`, runtime tests |
| RF-008 | Medium | ECOS uses the latest valid observation and separates observation/fetch timestamps. | Data Trust tests |
| RF-009 | Medium | Runtime OpenDART rows feed PIT-safe catalyst and alpha inputs. | `app.py:6462`, DART tests |
| RF-010 | Medium | Saved discovery results remain available after request flags reset. | alpha discovery tests |
| RF-011 | Medium | Generated deployment trees are ignored by Git and Docker contexts. | `.gitignore`, `.dockerignore` |
| RF-012 | Low | Visible legacy English was localized and float risk sliders became integer basis-point controls. | Korean audits |
| RF-015 | High | `Snapshot` moved from rerun-prone `__main__` into `src/market_snapshot.py`. | runtime tests |
| RF-016 | Medium | Lightweight views render before full market snapshot loading. | `app.py`, runtime tests |
| RF-017 | Low | Alpha scan default aligns to the slider step. | discovery tests |
| RF-018 | High | Docker tracks the maintained Python 3.11 Debian bookworm image line. | `Dockerfile:1` |
| RF-019 | High | KIS token failures are not cached and retry on the next request. | `app.py:2917-2950`, core tests |
| RF-020 | Medium | Session refresh no longer clears cross-session shared caches. | `app.py:9421`, runtime tests |
| RF-021 | Medium | Keyless public DART fallback has independent source metadata. | source registry/Data Trust tests |
| RF-022 | Medium | Direct URL query changes reconcile before the view widget is instantiated. | `app.py:9316`, AppTest |
| RF-023 | High | Naive dates localize to Asia/Seoul; internal comparisons are timezone-aware. | backtest engine/tests |
| RF-024 | High | Rank IC/Precision are calculated in aligned rebalance cross-sections, then aggregated. | backtest engine/tests |
| RF-025 | High | Future/unavailable macro inputs are excluded and flagged before alpha scoring. | forward alpha/tests |
| RF-026 | High | Date-only financial availability is end-of-day KST; exact receipt timestamps persist. | fundamental quality/tests |
| RF-027 | High | Mixed currencies without FX conversion block portfolio construction. | portfolio context/tests |
| RF-028 | Medium | Unscored holdings retain proportional weights subject to portfolio and sector caps. | optimizer/tests |
| RF-029 | Medium | DART event source fetch timestamps are retained. | DART catalyst/tests |
| RF-030 | Medium | Missing portfolio timestamps are marked missing/stale. | portfolio context/tests |
| RF-031 | High | MFE/MAE and target/stop checks start after the close-entry bar. | signal ledger/PIT tests |
| RF-032 | Medium | Durable keys preserve demo and submitted disclosure filters across view unmounts. | `app.py:203,8364,9143`, AppTest |
| RF-033 | Medium | DART provider errors become error state; valid zero rows remain empty. | `app.py:6462-6523`, runtime tests |
| RF-034 | Medium | FX/rate explanation dictionary keys now match their source sentences. | Korean labels/tests |
| RF-035 | Medium | Current-view live status and deterministic 9/3-column navigation were added. | app/theme/browser evidence |
| RF-036 | Test defect | Test permits registered public DART fallback while OpenDART API still requires a key. | source registry test |

## Deferred With Risk

### RF-037 — Browser Back does not trigger a Streamlit rerun

- Direct links and all nine visible navigation buttons are correct.
- Browser `popstate` changes the URL but Streamlit 1.58 does not send a rerun event, so mounted content can remain unchanged until another interaction or reload.
- JavaScript and periodic-fragment workarounds were tested and removed because they were nonfunctional or added permanent overhead.
- Mitigation: use the visible navigation controls or a direct URL.
- Follow-up: retest after a Streamlit upgrade that explicitly fixes query-history synchronization.

## Externally Blocked

### EXT-001 — Local trust store rejects OpenDART and ECOS TLS chains

- Secrets load correctly and remain masked.
- Live smoke: `DART status=error error=tls_error`; `ECOS status=error error=tls_error`.
- TLS verification remains enabled; `verify=False` was not introduced.
- Required action: provide a trusted CA bundle through `BNK_CA_BUNDLE` or `REQUESTS_CA_BUNDLE`, then repeat live provider smoke tests.
