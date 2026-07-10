# Final Release Decision

## Decision: CONDITIONAL GO

The codebase is suitable for local/mock-safe operation and a controlled deployment candidate because startup, 255 tests, six UI audits, nine-view browser checks, and responsive checks pass. It is not approved for a claim of fully operational OpenDART/ECOS real-data service on this machine.

## Required Conditions Before Real-Data Production

1. Install or mount the trusted organization CA chain and set `BNK_CA_BUNDLE` or `REQUESTS_CA_BUNDLE`.
2. Repeat masked OpenDART and ECOS live smoke tests and require usable `ready` data.
3. Run `docker build` and container `/_stcore/health` on a machine with Docker.
4. Treat browser Back as unsupported for internal view switching; use visible navigation or direct URLs.
5. Confirm persistent storage and access control before shared signal-ledger or briefing writes.

## Rollback

- No destructive Git operation was used.
- Existing feature flags can disable individual institutional panels without removing code.
- Revert only an affected patch/file set if a deployment regression appears; do not reset the whole worktree.

## Explicit No-Go Boundaries

- **Real-data GO is denied** while OpenDART/ECOS return `tls_error`.
- **Automatic trading remains out of scope** and no order execution is approved.
- **Performance claims remain unavailable** without validated PIT history and walk-forward evidence.

## Next Release Gate

After CA and Docker prerequisites are available, rerun compile, all 255 tests, six UI audits, live provider smoke, container health, and the 390/768/1024/1440 browser matrix. If all pass, promote the decision from `CONDITIONAL GO` to `GO`.
