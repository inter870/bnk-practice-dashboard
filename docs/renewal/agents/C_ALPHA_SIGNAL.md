# C. Alpha And Signal Audit

## 1. 범위

범위는 후보 발굴, 팩터 점수, 기대수익/확률, action gate, execution/exit 검토, 신호 원장과 사후 검증이다.

기준선:

- Python 3.11.8 / Streamlit 1.58.x
- 193 tests pass 이상
- 실전 자동 주문 없음
- high-risk override가 raw score보다 우선
- 운영 모드 `SHOW_MOCK_DATA=false`

## 2. 현재 alpha/signal inventory

| 계층 | 구현 | 현재 의미 | 조치 |
|---|---|---|---|
| 관심종목 판단 | `build_watchlist_insights`, `build_action_decision` | 가격·시장국면·공시·손익비·실행비용 기반 review action | `PRESERVE` + `ENRICH` |
| 시장 후보 탐색 | `src/discovery/scanner.py` | 상대강도, 20/60일 추세, 신고가, 거래량/거래대금, 눌림목 | `PRESERVE` + `FIX` |
| 실행 검토 | `src/execution/cost_model.py` | 유동성, 추정 슬리피지/impact, 분할/대기 review | `PRESERVE` |
| 청산 검토 | `src/exits/exit_plan.py` | hard/trailing/time stop, 목표, event risk | `PRESERVE` |
| Korea Alpha | `src/korea_equity/` | mock universe 기반 factor/prediction/OS | 운영 노출 차단 `PRESERVE`, 실데이터는 `ENRICH` |
| 기관 Forward Alpha | `src/institutional/forward_alpha.py` | valuation/quality/catalyst/flow/macro/liquidity/risk 합성 | `ENRICH` |
| 사후 검증 | `src/monitoring/signal_ledger.py` | signals/outcomes, 1/5/20/60D helper, kill switch | `FIX` + `ENRICH` |

## 3. 보존 대상

### C-P01. review-only action contract

- **분류:** `PRESERVE`
- action은 검토 후보이며 주문이 아니다.
- high disclosure/liquidity/data-quality risk가 score를 override한다.
- expected edge보다 execution cost가 크면 대기/차단한다.
- max position은 risk cap과 market regime를 넘지 않는다.

### C-P02. 설명 가능한 팩터 분해

- **분류:** `PRESERVE`
- positive reasons, negative reasons, blockers, confidence, risk flags를 유지한다.
- factor heatmap, supply-demand, disclosure, value-up 연결을 유지한다.
- 내부 enum은 한국어 display label로 매핑한다.

### C-P03. 수동 full-market scan

- **분류:** `PRESERVE`
- scan은 사용자 버튼 이후에만 시작한다.
- 앱 초기 로딩이나 hidden tab rerun이 scan을 자동 시작하지 않는다.

## 4. Critical safeguard resolved during audit

### C-C01. 합성 성과 숫자 차단

- **분류:** `PRESERVE` + `ENRICH`
- 현재 score만 전달한 `runWalkForwardBacktest()`는 `synthetic_demo`/`validation_unavailable`, 빈 returns를 반환한다.
- `summarizeBacktest()`도 CAGR/Sharpe/precision을 N/A로 유지한다.
- historical features/prices/universe를 요구하는 chronological PIT engine과 8개 integrity tests가 추가됐다.

영향:

- 합성 score-return replay가 다시 들어오면 독립 검증이 아니므로 현재 hard gate를 절대 완화하면 안 된다.
- production historical source wiring, delisting/corporate action/거래 가능성 검증은 아직 남아 있다.

현재 완화:

- `DATA_MODE="mock"`.
- 운영 UI는 `SHOW_MOCK_DATA=false`에서 Korea Alpha를 data-required 상태로 종료한다.

남은 조치:

- UI가 N/A 상태를 `룰 기반 추정 성과`가 아니라 `검증 불가/역사 데이터 필요`로 표시한다.
- production probability/return/backtest 필드는 실제 validated history 전까지 N/A로 유지한다.
- chronological engine에 production snapshot adapter를 연결한다.

## 5. High findings

### C-H01. 기대수익과 초과확률은 hand-tuned heuristic

- **분류:** `FIX` + `ENRICH`
- `estimateForwardReturnRange`, `estimateExpectedAlpha`, `estimateOutperformanceProbability`는 score/confidence/regime의 선형 수식이다.
- `calibrateScoreToHistoricalReturns`도 historical fit 없이 선형 변환한다.

필요:

- UI 명칭을 `휴리스틱 범위`, `점수 기반 참고값`으로 제한.
- empirical calibration dataset, model version, sample size, reliability diagram을 갖춘 뒤 probability로 승격.
- score bucket별 realized return와 confidence interval을 기록.

### C-H02. Discovery universe 선택과 regime 연결

- **분류:** `FIX`
- 현재 KRX listing에서 제외 규칙을 적용한 뒤 앞 N개를 scan한다.
- listing 정렬 의미가 보장되지 않아 max_symbols가 universe bias를 만든다.
- scan 호출은 실제 dashboard regime 대신 `market_regime_score=50.0`을 전달한다.

필요:

- deterministic universe order와 기준(시장/거래대금/시가총액)을 표시.
- selected universe count, exclusion count/reason, snapshot date 저장.
- 실제 regime output과 data quality를 전달.
- partial scan 결과는 전체시장 ranking처럼 명명하지 않음.

### C-H03. Discovery expected edge가 target heuristic에 의존

- **분류:** `FIX`
- 52주 고점을 upside target, 20일 저점을 stop으로 두고 score 기반 confidence로 edge를 만든다.
- 이 값은 forecast나 calibrated expectation이 아니다.

필요:

- `구조적 손익비`, `휴리스틱 기대값`으로 명확히 구분.
- 값에 formula, input date, unavailable fields, execution cost를 붙임.
- 공시/가격 stale이면 actionability 차단.

### C-H04. 여러 alpha/action 체계의 의미가 겹침

- **분류:** `ENRICH`
- legacy action (`Strong Buy`, `Accumulate Small` 등), Korea grade, institutional rating, optimizer action이 병렬이다.
- 같은 종목이 서로 다른 label과 cap을 보일 수 있다.

필요:

- 공통 `SignalEnvelope`:
  - `signal_id`, `generated_at`, `code`
  - `review_action`, `actionability`
  - `raw_score`, `confidence`
  - `expected_edge_kind`
  - `risk_flags`, `blockers`
  - `max_review_weight`
  - `feature_snapshot_id`, source metadata
- 기존 enum은 alias mapping으로 유지.

### C-H05. PIT outcome UI 연결 후 schema 재현성 보강 필요

- **분류:** `PRESERVE` + `ENRICH`
- UI는 현재 mapping adapter와 1/5/20/60D `compute_forward_outcomes()`를 사용하고 benchmark/비용을 전달한다.
- target/stop/entry가 signal schema에 고정되지 않아 hit/R 계산은 아직 재현할 입력이 없다.

필요:

- 생성 당시 levels/cost assumptions를 immutable signal row에 저장.
- generated_at 이후의 거래일만 사용.
- 1/5/20/60D 성숙도를 구분.
- benchmark-relative outcome과 universe context 저장.

### C-H06. kill switch의 통계적 gate가 얕음

- **분류:** `ENRICH`
- 최근 5D/20D outcome 최대 80개, min 8, hit rate 35%와 평균수익으로 판단한다.
- regime/strategy/version별 분리, uncertainty, multiple horizon dependency가 없다.

필요:

- model/score version과 action family별 cohort.
- 최소 독립 표본, Wilson interval 또는 bootstrap interval.
- regime shift와 stale outcome 분리.
- kill switch는 신호 생성 confidence/cap을 낮추되 기존 보유의 자동 매도를 유발하지 않음.

## 6. Medium findings

### C-M01. factor weight/version governance

- **분류:** `ENRICH`
- `FACTOR_WEIGHTS`와 threshold는 코드 상수다.
- version, 변경 사유, effective date, validation report를 함께 관리한다.

### C-M02. execution cost는 order-book 없이 추정

- **분류:** `PRESERVE` + `ENRICH`
- bid/ask/spread가 unavailable로 명시되는 것은 적절하다.
- 추정 slippage/impact를 실제 quote처럼 보이지 않게 유지하고, 실측 체결 데이터가 생기면 calibration한다.

### C-M03. 동일 bar에서 target/stop 동시 hit 처리

- **분류:** `ENRICH`
- OHLC만 있을 때 순서를 알 수 없어 현재 보수적으로 stop 우선 처리한다.
- 이 가정을 outcome metadata와 backtest notes에 노출한다.

### C-M04. timestamp/version 표시

- **분류:** `FIX`
- signal time은 timezone-aware Asia/Seoul, model/score/data snapshot version을 포함해야 한다.

## 7. 구현 계획

### 7.1 즉시: 명칭과 UI 안전 경계

1. `validation_unavailable`을 UI의 `검증 불가/역사 데이터 필요`로 직접 표시.
2. uncalibrated probability/expected return을 N/A 또는 heuristic label로 변경.
3. `SHOW_MOCK_DATA=false` guard regression test 추가.
4. partial universe를 전체시장으로 표현하지 않음.

### 7.2 SignalEnvelope 통합

1. legacy/Korea/institutional score adapter 작성.
2. 공통 actionability/risk override 적용.
3. UI는 공통 envelope만 읽고 기존 renderer wrapper 유지.
4. score version과 feature snapshot id 저장.

### 7.3 PIT outcome pipeline

1. signal 생성 시 timestamp/entry/target/stop/cost/benchmark 저장.
2. 거래일 calendar로 horizon maturity 계산.
3. future data만 join.
4. idempotent outcome upsert.
5. model/version/regime cohort summary.

### 7.4 empirical calibration

1. 당시 universe와 delisted 종목 포함.
2. feature available timestamp snapshot.
3. forward return label store.
4. time split/walk-forward.
5. calibration/IC/precision/turnover/cost report.
6. 최소 표본 gate 후 production 승격.

## 8. 테스트 계획

- 기존 alpha/discovery/execution/exit/Korea/forward-alpha/signal tests 전부 통과.
- future feature injection 실패.
- partial horizon N/A.
- delisted/suspended/no-price universe.
- partial scan ordering reproducibility.
- actual regime propagation.
- high score + severe risk => exclude/review-only.
- expected edge <= cost => wait/block.
- score version change가 snapshot id를 변경.
- two runs with same snapshot are deterministic.
- probability calibration: Brier score/reliability bucket acceptance.

## 9. Rollback

- `SHOW_MOCK_DATA=false`와 synthetic backtest N/A hard gate를 production에서 유지.
- `ENABLE_PIT_SIGNAL_OUTCOMES`, `ENABLE_EMPIRICAL_ALPHA`를 독립 flag로 둔다.
- PIT pipeline 실패 시 outcome update만 off하고 signal read-only 목록을 유지한다.
- empirical model 실패 시 heuristic 숫자로 fallback하지 않고 N/A로 복귀한다.
- legacy action renderer는 compatibility alias로 한 release 유지한다.
- SQLite migration은 additive이며 기존 행 삭제 금지.

## 10. 완료 조건

- 합성 return이 backtest/validation으로 production에 노출되지 않는다.
- 모든 signal은 source, timestamp, feature snapshot, version, blockers를 갖는다.
- outcome은 signal 이후 거래일로만 계산된다.
- risk override와 execution cost gate가 모든 alpha 계층에 동일하게 적용된다.
- 자동 주문 기능이 없다.
- 193 기준선 이상 전체 테스트와 PIT/calibration 테스트가 통과한다.
