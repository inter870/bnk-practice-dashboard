# Korea Alpha Dashboard Upgrade Summary

## Repository Detected
- Framework: Streamlit
- Language: Python 3.11
- Styling: embedded Streamlit CSS in `app.py`
- Chart library: matplotlib
- Test runner: unittest
- Data mode: mock, with future KRX/DART/KIND adapter boundary

## Files Changed
- `app.py`
- `src/korea_equity/models.py`
- `src/korea_equity/config.py`
- `src/korea_equity/formatting.py`
- `src/korea_equity/mock_data.py`
- `src/korea_equity/factor_engine.py`
- `src/korea_equity/prediction_engine.py`
- `src/korea_equity/risk_engine.py`
- `src/korea_equity/backtest_engine.py`
- `src/korea_equity/recommendation_engine.py`
- `src/korea_equity/service.py`
- `src/korea_equity/__init__.py`
- `tests/test_korea_equity_engine.py`

## Features Added
- Korea market regime card
- Korea alpha candidate ranking
- Recommendation table with score, grade, confidence, expected return, excess return, risk, rationale, model version
- Signal breakdown expander
- Factor heatmap
- Supply-demand radar
- DART/KIND-style disclosure event radar using mock events
- Value-up radar
- Risk control panel
- Backtest and accuracy panel
- Portfolio action queue

## Validation
- `py -3.11 -m compileall app.py src tests`: PASS
- `py -3.11 -m unittest discover tests`: PASS, 43 tests
- Streamlit health check: PASS
- Desktop browser smoke: PASS
- Mobile 390px overflow check: PASS

## Known Limitations
- Current Korea Alpha module runs in mock mode.
- No live KRX/DART/KIND adapter is connected yet.
- No brokerage/order API is connected.
- Backtest output is a transparent mock validation, not verified live historical performance.
