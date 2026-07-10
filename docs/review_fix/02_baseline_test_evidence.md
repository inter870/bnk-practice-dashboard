# Baseline Test Evidence

## Environment

- Project root: `C:\Users\BNKFN\Desktop\bnk_practice`
- Python: `3.11.8`
- Streamlit: `1.58.0`
- Baseline commit: `f6b4dc7bdbadd9d884e5690e0281d3d93ed1b33b`
- App entry point: `app.py`

## Commands And Results

| Check | Command | Result |
|---|---|---|
| Syntax/import compilation | `python -m compileall app.py src tests` | PASS |
| Unit/integration suite | `python -m unittest discover tests` | PASS: 220, SKIP: 1 |
| Direct import | `python -c "import app"` | PASS |
| Streamlit health | `GET http://127.0.0.1:8501/_stcore/health` | HTTP 200, `ok` |
| Dark readability audit | `python scripts/audit_dark_dashboard.py` | PASS |
| Data Trust display audit | `python scripts/audit_data_trust_display.py` | PASS |
| Korea OS visibility audit | existing audit command | PASS, broad white-token advisory |
| Korean market color audit | existing audit command | PASS |
| Korean localization audit | existing audit command | PASS |
| Risk alert Korean UI audit | existing audit command | PASS |
| Mobile width | browser at 390 px | `scrollWidth == clientWidth` |
| Desktop width | browser at 1280 px | `scrollWidth == clientWidth` |

## Skip And Warnings

- `tests/test_core_v1.py:81`의 no-credentials branch가 현재 환경에 KIS credentials가 설정돼 있어 1회 건너뛰었다.
- 브라우저 콘솔에서 float slider의 value/step 정렬 경고를 확인했다.
- ECOS 화면의 외부 응답 실패는 실행 환경/공급자 상태와 코드 결함을 구분해 후속 검증한다.

## Why A Green Baseline Was Insufficient

기존 220개 테스트는 모두 통과했지만 다음 잘못된 동작을 테스트가 오히려 정상으로 고정하거나 검사하지 않았다.

1. `tests/test_portfolio_context.py:141-144`는 현재가 누락 시 평균매입가 대체를 성공으로 기대한다.
2. `tests/test_portfolio_context.py:156-171`는 현재 수량을 과거 가격에 고정 적용한 값을 정상 이력으로 기대한다.
3. `tests/test_backtest_integrity.py`는 feature 시점과 동일한 종가를 진입가로 사용하는 fixture를 허용한다.
4. `tests/test_portfolio_optimizer_alert_center.py:125-141`는 주식 목표합이 95% 이하인지만 확인해 77% 미배분도 통과한다.
5. 현금 포함 단일종목 집중도, calibration 없는 기대값 차단, KIS OAuth cache 독립성을 검증하는 테스트가 없다.

따라서 수정은 기존 테스트 삭제나 assertion 약화가 아니라, 실패 재현 테스트를 먼저 추가하고 금융 안전 계약을 강화하는 방식으로 진행한다.

## Reproduction Evidence

독립 재현 스크립트 출력:

```text
missing_price_fallback: 70000.0
cash_inclusive_actual_weight: 0.07216494845360824
reported_concentration: 1.0
optimizer_stock_sum: 0.18
reported_target_cash: 0.05
optimizer_total: 0.23
unheld_kosdaq_target: 0.07
fixed_quantity_first_value: 150.0
same_close_backtest_status: validated
same_close_gross_return: 0.10000000000000009
uncalibrated_edge: (1.55, 1.11, 55.5)
```

이 증적은 RF-001부터 RF-006까지를 코드 수정 전에 재현한 결과다.
