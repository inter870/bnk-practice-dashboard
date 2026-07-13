# Feature Regression Matrix

| Surface | Contract preserved | P0 evidence |
|---|---|---|
| Nine-view navigation | Yes | Labels/slugs/widget key unchanged |
| Sidebar portfolio CSV | Yes | Legacy adapter tests pass |
| Market/stock views | Yes | Imports and full suite pass |
| Alpha discovery | Yes | No ranking formula changed |
| DART/ECOS/KIS adapters | Yes | No endpoint/credential alias changed |
| Briefing | Yes | Generation retained; file persistence is opt-in |
| Signal outcome | Conditional | Schema and calculations pass; shared persistence is opt-in |
| Portfolio optimizer | Safer behavior | Reconciliation/data gates force NO_TRADE |
| Settings | Yes | Same controls, now session-local |

No existing module or route was removed. No automatic trading endpoint exists.
