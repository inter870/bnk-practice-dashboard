# P0 Remediation Ledger

| ID | Root cause | Remediation | Rollback |
|---|---|---|---|
| P0-01 | Process-global risk dictionary was mutable | Immutable defaults plus session-local overrides | Restore direct defaults (not recommended) |
| P0-02 | Portfolio mismatch only warned | Explicit reconciliation result and optimizer NO_TRADE gate | Disable gate argument |
| P0-03 | Missing alpha could imply TRIM | Display WATCH and mark action ineligible | Restore analytical action display |
| P0-04 | SQLite used replace semantics without schema migration | Schema v2, additive columns, unique signal key, monotonic outcome upsert | Restore database backup/schema v1 reader |
| P0-05 | Costs were anonymous arithmetic | Versioned `CostPolicy`, preserving 50 bps legacy default | Use prior arithmetic |
| P0-06 | Public sessions shared writable files | `STANCE_ENABLE_SHARED_WRITES` opt-in and atomic unique briefing files | Set flag true only in trusted deployment |

No API route, provider endpoint, environment-variable alias, investment score formula,
or automatic order behavior was added or changed.

