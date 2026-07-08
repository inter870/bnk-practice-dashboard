# Risk & Return UI Rebuild Summary

## Repository Detected
- Framework: Streamlit
- Language: Python
- Styling system: inline Streamlit HTML/CSS in `app.py`
- Chart library: matplotlib
- Test runner: unittest
- Package manager: none detected; no `package.json`

## Affected Section Fixed
- Rebuilt the lower Portfolio Intelligence area:
  - `Risk & Return`
  - `집중도 위험`
  - `보유/관심 신호`
  - `Insight Engine`
- Moved benchmark excess return into the Risk & Return card as a designed strip.
- Removed raw stacked text treatment from the affected cards.
- Verified no standalone `0 0` appears inside the Portfolio Intelligence detail shell.

## Files Changed
- `app.py`
  - Added scoped `.pi-detail-*`, metric tile, holding bar, signal row, and insight block styles.
  - Added direct HTML helpers for Risk & Return, concentration risk, watchlist signals, and Insight Engine.
  - Replaced the old lower `st.columns` card calls with one responsive detail grid.
- `tests/test_portfolio_visibility.py`
  - Added regression checks for the new card classes and layout wiring.
  - Added guardrails to prevent the affected cards from reverting to `rank-row` / `signal-row`.
- `tests/test_portfolio_analytics.py`
  - Added formatter examples for the dashboard values such as `+97.6%`, `-12.5%`, `0.0%`, `1.30`, and `0.202`.

## Design Changes Made
- `Risk & Return`: six readable metric tiles with helper labels and semantic colors.
- Benchmark excess return: highlighted strip inside the Risk & Return card.
- `집중도 위험`: ranked horizontal bar list for top holdings.
- `보유/관심 신호`: compact table-like rows with code, name, change, and neutral signal badge.
- `Insight Engine`: structured blocks for `관찰`, `근거`, and `후보 행동`.
- Responsive behavior:
  - Desktop uses a 12-column detail grid.
  - Mobile collapses to one column without horizontal page overflow.

## Validation
- `py -3.11 -m compileall app.py src tests`: passed
- `py -3.11 -m unittest discover tests`: passed, 74 tests
- Local browser verification at `http://127.0.0.1:8501/`: passed
  - Desktop 1280px: no horizontal overflow, 6 metric tiles, 5 holding rows, 6 signal rows, 3 insight blocks
  - Mobile 390px: no horizontal overflow, `scrollX = 0`, same content counts
  - No `Traceback` or `StreamlitAPIException`

## Known Limitations
- No separate component test framework exists for Streamlit HTML fragments; guardrails are source-level plus browser DOM verification.
- Charts remain matplotlib-based and were preserved rather than replaced.
- Pixel-perfect screenshot visual regression was not added.

## Next Improvement
- Add a lightweight screenshot regression check for Portfolio Intelligence desktop/mobile states.
- Expand the metric explanation registry so each Risk & Return tile can open a consistent formula panel.
