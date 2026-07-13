# Current Inventory

## Runtime

- Entry point: `app.py`
- Stack: Python 3.11, Streamlit 1.58, matplotlib, pandas, SQLite
- Tests: Python `unittest`
- Deployment contracts: `requirements.txt`, `runtime.txt`, `Procfile`, `render.yaml`

## Preserved User Surfaces

The nine existing views and their `view` query aliases remain unchanged: dashboard,
portfolio, stocks, alpha discovery, disclosures, macro, briefing, signal outcome,
and settings. Existing `stock`, `module`, and `factor` query parameters remain in
place. Existing sidebar portfolio CSV and risk controls remain available.

## Classification

- PRESERVE: navigation, market cards, portfolio inputs, stock search, DART/ECOS/KIS
  adapters, alpha discovery, briefing, settings, chart and table surfaces.
- ENRICH: provider metadata, portfolio reconciliation, signal/outcome lineage,
  versioned transaction costs.
- FIX: process-global risk settings, unsafe shared writes, optimizer action gates,
  signal ledger migration/idempotency, forward-outcome persistence.
- RELOCATE_WITH_ALIAS: none in P0.

## Storage

- Signal ledger: `data/signal_ledger.sqlite3` (SQLite, schema version 2).
- Briefings: optional files under `briefings/`.
- Shared writes are disabled by default and require
  `STANCE_ENABLE_SHARED_WRITES=true` in a trusted persistent environment.
