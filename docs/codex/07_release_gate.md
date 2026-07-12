# Release Gate

## Decision: CONDITIONAL GO

Code-level P0 compilation and all 277 unit tests pass. Existing navigation and API
contracts are preserved, and new safety gates default closed.

## Conditions Before Production GO

1. Repeat the passed Streamlit headless health check in the deployment image.
2. Verify all nine views and mobile widths in a real browser.
3. Confirm durable, single-tenant or access-controlled storage before enabling
   `STANCE_ENABLE_SHARED_WRITES=true`.
4. Validate DART/ECOS/KIS with deployment secrets without logging credentials.
5. Back up the existing SQLite ledger before first schema-v2 production write.
6. Keep advanced prediction/model work in shadow mode until point-in-time samples
   and after-cost out-of-sample evidence are sufficient.

Failure of any condition keeps the release at CONDITIONAL GO; credential leakage,
startup failure, migration failure, or action-gate bypass is NO-GO.

