# Data Lineage And Status

## Canonical Modes

`LIVE`, `DELAYED`, `STALE`, `FALLBACK`, `DEMO`, `DISCONNECTED`, `ERROR`, and
`UNAVAILABLE` are normalized at the provider boundary. Demo takes precedence over
stale/fallback; stale takes precedence over fallback. A timestamped manual portfolio
snapshot is eligible for reconciliation while retaining its manual source label.

## Metadata

`DataSourceMeta` now supports observation date, period end, publication/availability
time, analysis as-of, fetch time, timezone, currency, unit, schema/provider versions,
quality components, formula version, quality flags, and investment eligibility.

## Eligibility

DEMO, STALE, DISCONNECTED, ERROR, UNAVAILABLE, missing data, provider errors, and
missing availability time block investment actions. Fallback remains explicitly
identified and can be further gated by the caller. Raw values are not modified by
quality scoring.

## Point In Time

P0 stores `decision_at`, `next_executable_at`, data snapshot ID, and model/feature/
score/universe versions. DART-derived future analytics must continue to use filing
receipt or availability time, never fiscal period end as the availability timestamp.
