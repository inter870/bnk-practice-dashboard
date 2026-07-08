# Korea OS Typography Visibility Fix Summary

## 1. Repository Detected
- Framework: Streamlit app centered on `app.py`
- Language: Python 3.11
- Styling method: Streamlit `st.markdown(..., unsafe_allow_html=True)` CSS injection plus custom HTML helpers
- Charting: existing matplotlib flow preserved
- Tests/validation: `py_compile`, `compileall`, `unittest`, custom static guardrail, in-app browser DOM/style checks

## 2. Typography and Color Fixes
- Added `src/ui/korea_os_theme.py` with a scoped Korea OS readability layer.
- Font stack: `Pretendard`, `Inter`, `Noto Sans KR`, `Apple SD Gothic Neo`, `Malgun Gothic`, system fonts.
- Text hierarchy now uses off-white/slate tokens instead of a flat pure-white treatment:
  - hero/title `#F8FAFC`
  - primary `#E8EEF8`
  - secondary `#C7D2E5`
  - tertiary `#9FB0C8`
  - muted `#7F8DA6`
- Streamlit widgets covered: sidebar, markdown text, expanders, buttons, metrics, radio groups, checkbox/select/slider labels, dataframe/table wrappers.
- Korea OS tables now use styled scroll containers, sticky headers, sticky first column, tabular numerals, compact spacing, and readable row/hover colors.
- Heatmap cells now render score and label inside compact styled cells with readable text.
- Filter summary and explanation/context text now render as intentional info callouts.

## 3. Sections Fixed
- Korea Alpha Filter: added a styled filter summary row and stronger Streamlit widget text styling.
- Advanced Module Summary: preserved module navigation and applied the shared section/card hierarchy.
- Post Review Notebook: covered by Korea OS styled table/card rules.
- Investment Review Algorithm: section header, count badge, stock cells, metric hierarchy, and table style preserved and strengthened.
- Factor Heatmap: legend/table/heatmap cell readability improved with Korea OS classes.
- Supply Demand Radar: table now uses shared stock cell, numeric alignment, badge/color hierarchy.
- Disclosure/Event Radar: covered by styled table and badge system.
- Value-Up Radar: caveat/cell/table hierarchy covered by shared table and callout CSS.
- Prediction Accuracy/Backtest: metric/card/table styles preserved under new scoped typography.
- Portfolio Review Queue: shared table style and badge hierarchy applied.
- Candle + Volume Chart: Streamlit controls and metric text inherit stronger dark theme typography.

## 4. Files Changed
- `app.py`
  - Injects the new Korea OS theme.
  - Wraps Korea alpha area with `korea-os-theme`.
  - Adds styled filter summary.
  - Adds final table/heatmap/stock-cell classes to existing helpers.
- `src/ui/__init__.py`
  - Adds UI helper package marker.
- `src/ui/korea_os_theme.py`
  - New scoped typography, color, Streamlit widget, table, badge, heatmap, filter, context, and mobile CSS layer.
- `scripts/check_korea_os_visibility.py`
  - New static guardrail for theme injection, styled table/heatmap classes, raw table regressions, and dark text utilities.
- `tests/test_korea_os_typography_visibility.py`
  - New static regression tests for theme injection, required tokens, styled classes, Streamlit coverage, and guardrail checks.

## 5. Validation
- `py -3.11 -m py_compile app.py src\ui\korea_os_theme.py scripts\check_korea_os_visibility.py`: PASS
- `py -3.11 scripts\check_korea_os_visibility.py`: PASS
  - Non-fatal warnings remain for broad white color tokens in existing global CSS.
- `py -3.11 -m unittest discover tests`: PASS, 84 tests
- `py -3.11 -m compileall app.py src tests scripts`: PASS
- In-app browser verification:
  - No Traceback/StreamlitAPIException detected.
  - `Korea Investment OS v2` rendered.
  - `.korea-os-theme`: 1
  - `.korea-os-card`: 10
  - `.korea-os-table`: 10
  - `.korea-os-heatmap-cell`: 114
  - `.korea-filter-summary`: 1
  - Desktop 1280px: no page-level horizontal overflow.
  - Mobile 390px: no page-level horizontal overflow.
  - Computed styles confirmed Korean font stack and off-white text hierarchy on context, filter, table, heatmap, and badge elements.

## 6. Known Limitations
- Some older global `app.py` CSS still contains pure-white tokens outside the final scoped Korea OS theme. The new Korea OS layer overrides the critical rendered modules, and the guardrail reports these as warnings rather than failures.
- Streamlit native widget internals cannot be styled as deeply as custom HTML without risking breakage, so the filter controls are improved with both widget CSS and a styled summary row.
- Matplotlib chart internals remain controlled mostly by existing chart code; the surrounding chart card/control typography is improved by the Streamlit theme layer.
- `git` was not available in the current PowerShell PATH, so git status/diff could not be run from this environment.

## 7. Next Improvement
- Add screenshot regression checks for desktop and mobile.
- Build a small Korea OS component gallery for cards, badges, heatmap cells, and tables.
- Run a formal contrast audit over rendered screenshots.
- Add a compact/comfortable density toggle for large Korean equity tables.
