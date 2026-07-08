# Dashboard Visibility Upgrade Summary

## Repository Detected
- Framework: Streamlit
- Language: Python
- Styling: Streamlit HTML/CSS with centralized Korea dashboard visual token CSS
- Chart library: matplotlib
- State/routing: Streamlit session state and query params
- Test runner: unittest

## Modules Preserved
- 투자검토 알고리즘
- 팩터 히트맵
- 수급 레이더
- 공시·이벤트 레이더
- 밸류업 레이더
- 예측 정확도·백테스트
- 포트폴리오 검토 큐
- 고도화 모듈 요약
- 공포·탐욕 지수
- 최근 60거래일 캔들 + 거래량
- Korea Investment OS v2 modules

## Readability Improvements
- Added centralized Korea dashboard design tokens and visual module registry.
- Improved dark premium card contrast, border hierarchy, selected states, and button focus/hover states.
- Upgraded 투자검토 알고리즘 with a large score hero, grade badge, metric strip, and evidence preview.
- Added a segmented 0-100 공포·탐욕 gauge while preserving the exact explanation text.
- Improved heatmap cells, legend, table density, numeric alignment, and readable evidence cells.
- Improved supply-demand numeric coloring and signal labels.
- Improved disclosure category/sentiment badges.
- Added an operational module health checklist to 고도화 모듈 요약.
- Improved candlestick/volume chart colors, axis contrast, grid visibility, and range behavior.
- Kept mobile page width fixed with no whole-page horizontal overflow.

## Files Changed
- app.py
- src/korea_equity/design_tokens.py
- src/korea_equity/__init__.py
- src/korea_equity/formatting.py
- tests/test_korea_equity_engine.py
- tests/test_korea_visual_tokens.py

## Validation
- `python -m compileall app.py src tests`: PASS
- `python -m unittest discover tests`: PASS, 66 tests
- Browser local render check: PASS
- Required module visibility check: PASS
- Mobile 390px horizontal overflow check: PASS

## Known Limitations
- No visual screenshot diff tooling is configured in this Streamlit project.
- Chart interactivity remains constrained by matplotlib and Streamlit native controls.
- Some market values depend on the existing data providers and may remain delayed or fallback.

## Next Highest-Impact Improvement
- Add a lightweight screenshot-based visual regression check for desktop and mobile dashboard states.
