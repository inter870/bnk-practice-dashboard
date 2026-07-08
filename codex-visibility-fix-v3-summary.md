# Stance Stock Strategy Visibility Fix v3 Summary

## Repository
- Detected project: Streamlit + Python app centered on `app.py`
- Framework: Streamlit, matplotlib, unittest
- Git status: local `.git` is not a valid repository in this folder, so no commit was made

## Fixed Screenshot Issues
- Rebuilt the `Portfolio Intelligence` top area as one cohesive dark-purple panel.
- Fixed unreadable dark-on-dark / dark-on-light text in:
  - `Portfolio Health`
  - `배분 이탈`
  - `리밸런싱 후보`
- Removed fragile table-like visual treatment for rebalancing candidates and replaced it with readable stacked mini-cards.
- Kept safe language: rebalancing items remain `후보` and `주문 아님`, not execution instructions.
- Added responsive behavior so the three-card grid becomes one column on mobile.
- Preserved all existing dashboard modules, calculations, tabs, and interactions.

## Files Changed
- `app.py`
  - Added Portfolio Intelligence dark shell and grid styles.
  - Added `.pi-*` card, badge, progress, allocation, and rebalance row styles.
  - Split top Portfolio Intelligence cards into reusable HTML helpers.
  - Rendered the top three cards inside one actual HTML grid panel.
- `tests/test_portfolio_visibility.py`
  - Added UI structure regression checks for the Portfolio Intelligence shell, grid, cards, and mobile collapse.

## Validation
- `py -3.11 -m compileall app.py src tests`: passed
- `py -3.11 -m unittest discover tests`: passed, 70 tests
- Local browser check at `http://127.0.0.1:8501/`: passed
  - No `Traceback`
  - No `StreamlitAPIException`
  - `Portfolio Intelligence`, `Portfolio Health`, `배분 이탈`, `리밸런싱 후보`, `주문 아님` visible
  - Desktop 1280px: 3-column grid, no horizontal overflow
  - Mobile 390px: 1-column grid, no horizontal overflow, `scrollX = 0`

## Known Limitations
- This change fixes local code and local UI verification only.
- No GitHub commit, push, or Streamlit Cloud redeploy was performed because the request explicitly said not to commit.
- Pixel-perfect screenshot comparison was not added; the browser check verifies DOM structure, responsive width, key text, and applied styles.

## Suggested Next Improvement
- Apply the same `.pi-*` visual system to the lower Portfolio Intelligence widgets (`Risk & Return`, charts, concentration, insight engine) so the entire section has one unified premium dark-purple language.
