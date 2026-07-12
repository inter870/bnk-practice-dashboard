# P0 Implementation Plan

1. Preserve all user surfaces and API contracts.
2. Add backward-compatible provider metadata and canonical modes.
3. Reconcile holdings, cash, other assets, liabilities, and declared total.
4. Gate optimizer actions when reconciliation or data eligibility fails.
5. Make risk settings session-local.
6. Version SQLite schema; make signal storage idempotent and outcome updates monotonic.
7. Version transaction-cost assumptions without changing existing default totals.
8. Disable shared file/database writes by default in public deployments.
9. Run compilation, all unit tests, UI audits, and a Streamlit health smoke test.

P1 forecasting and P2 visual redesign are explicitly out of scope until this gate is
accepted and real point-in-time data coverage is available.

