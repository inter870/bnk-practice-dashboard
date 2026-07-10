# E. Data And Backtest Audit

## 1. 범위

범위는 데이터 source 선택, fallback, metadata, timestamp semantics, DART point-in-time, feature snapshot, signal outcome, backtest/research 재현성이다.

기준선:

- Python 3.11.8 / Streamlit 1.58.x
- 193 tests pass 이상
- 모든 신규 값에 source/date/availability/unit/quality
- DART는 fiscal period end가 아니라 receipt/available timestamp
- look-ahead와 survivorship bias 금지
- mock/planned/cache/public snapshot을 official realtime로 표시하지 않음

## 2. 현재 데이터 inventory

### 2.1 공통 계약

- legacy `Snapshot`: source, asof, unit, frequency, quality, warnings/errors, fallback.
- institutional `DataSourceMeta`: source/provider/URL, as_of, available/fetched, frequency/unit, quality/confidence, fallback/stale/missing.
- `SourceRegistry`: category별 source, auth requirement, adapter availability, reliability, stale threshold, fallback rank.
- `DataTrust`: 연결/부분/오래됨/키 누락/계획/mock와 accuracy grade.

### 2.2 실제/계획 source

| 범주 | 실제 경로 | 현재 등급 | 주요 간극 |
|---|---|---|---|
| 시장/종목 가격 | KIS, Naver, FDR | broker 또는 public snapshot/fallback | timestamp 계약 통합 |
| DART 공시 | OpenDART list 또는 공개 페이지 | official API/public page | 기관 catalyst wiring·history |
| 재무제표 | source registry + fundamental engine | adapter contract 존재 | production adapter wiring 없음 |
| 매크로 | ECOS, snapshot | official API/fallback | release timestamp/frequency 통합 |
| valuation | planned KRX/OpenDART | planned | exact 값 생성 금지 |
| investor flow/short | planned KRX | planned | exact 값 생성 금지 |
| portfolio | manual sidebar 또는 explicit mock | manual/mock | 가격/총자산 reconciliation |
| signal outcome | SQLite + FDR history | local derived | UI PIT helper 연결 완료, owner scope/immutable levels 필요 |

## 3. 보존 대상

### E-P01. source registry와 key policy

- **분류:** `PRESERVE`
- source별 required key, adapter availability, legal access, fallback rank를 유지한다.
- OpenDART/ECOS alias를 canonical presence로 처리한다.
- planned adapter는 `adapter_missing`/`planned`이며 healthy로 보이지 않는다.
- Naver/FDR에 KIS key 누락을 표시하지 않는다.

### E-P02. PIT selector

- **분류:** `PRESERVE`
- fundamental period는 `available_at`이 없는 행을 analytics에 사용하지 않는다.
- future period를 cutoff 이후까지 제외한다.
- disclosure는 `receipt_date`/`available_at` 기준으로 선택한다.
- forward alpha feature timestamp가 prediction time 이후면 leakage validation에 실패한다.

### E-P03. mock/stale/empty separation

- **분류:** `PRESERVE`
- mock은 explicit demo에서만 낮은 confidence로 표시한다.
- missing short/flow 값은 0이 아니라 unavailable.
- cache는 cache age와 stale을 표시한다.
- `SHOW_MOCK_DATA=false` production guard를 유지한다.

## 4. Critical safeguards resolved during audit

### E-C01. 합성 backtest 성과 숫자 차단

- **분류:** `PRESERVE` + `ENRICH`
- current score만 전달한 경로는 `synthetic_demo`/`validation_unavailable`, 빈 returns와 N/A metric을 반환한다.
- historical features/prices/universe를 받는 chronological PIT engine, cutoff, rebalance cost와 8개 integrity tests가 추가됐다.
- production feature store와 historical universe adapter는 아직 없다.

Release rule:

- 현재 synthetic N/A hard gate를 모든 profile에서 유지.
- 실제 PIT dataset 전에는 backtest, probability, calibrated return을 N/A.

### E-C02. Signal Outcome UI-PIT 연결

- **분류:** `PRESERVE` + `ENRICH`
- UI는 dict row를 `signal_record_from_mapping()`으로 복원하고 PIT용 `compute_forward_outcomes()`를 호출한다.
- generated time 이후 1/5/20/60D, benchmark, cost, maturity를 처리하는 4개 tests가 추가됐다.
- signal 생성 당시 target/stop/entry와 owner scope 저장은 남아 있다.

Release rule:

- 현재 generated_at 이후, 고정 거래일 horizon, maturity gate를 회귀 테스트로 강제.
- 8번 화면 save/update/list AppTest 통과 전 production write는 flag off.

## 5. High findings

### E-H01. metadata 계약 이원화

- **분류:** `ENRICH`
- legacy cards와 institutional panel이 서로 다른 freshness/availability 필드를 사용한다.
- `asof`가 market observation, source publication, fetch time 중 무엇인지 source별로 다를 수 있다.

필요:

- `observation_at`
- `available_at`
- `fetched_at`
- `effective_date`(필요한 경우)
- timezone
- adapter/instrument id
- revision/vintage id

### E-H02. instrument identity가 fallback에서 바뀔 수 있음

- **분류:** `FIX`
- KR government 3Y가 없을 때 corporate 3Y를 같은 `KR 3Y` key에 넣을 수 있다.
- source fallback은 허용해도 경제적 instrument fallback은 값 대체로 처리하면 안 된다.

필요:

- canonical instrument id.
- 동일 instrument의 provider fallback만 value fallback으로 허용.
- 다른 instrument는 별도 참고값과 caveat.

### E-H03. 실제 기관 panel adapter wiring 미완료

- **분류:** `ENRICH`
- 공시 탭의 actual data와 DART Catalyst panel이 분리되어 있다.
- valuation/fundamental/flow/short/forward/optimizer는 production upstream이 없다.

필요:

- source registry resolution -> adapter -> normalized record -> module state의 단일 pipeline.
- adapter가 없으면 exact value 생성 금지.
- 모든 adapter에 empty/error/stale/partial contract.

### E-H04. historical universe 부재

- **분류:** `FIX`
- Discovery는 현재 listing을 사용한다.
- backtest에 재사용하면 delisted/merged/suspended 종목이 사라져 survivorship bias가 생긴다.

필요:

- date-effective security master.
- listing/delisting, market transfer, share class, trading halt interval.
- 당시 universe query와 exclusion reason snapshot.

### E-H05. corporate action/price adjustment 계약 없음

- **분류:** `ENRICH`
- split, dividend, rights, merger adjustment와 raw/adjusted price 구분이 명시되지 않는다.
- stop/target/outcome 계산이 어떤 series를 쓰는지 재현하기 어렵다.

필요:

- raw close, adjusted close, adjustment factor, event source.
- signal execution은 tradable raw, return research는 명시된 total/price return 사용.

### E-H06. macro release vintage와 revision

- **분류:** `ENRICH`
- ECOS 최신 값은 현재 dashboard에는 유효하지만 historical backtest에는 당시 공개 vintage가 필요하다.
- revised macro를 과거 시점에 넣으면 look-ahead가 된다.

필요:

- release/available timestamp, revision/vintage.
- vintage가 없으면 해당 factor를 PIT backtest에서 제외하거나 limitation 명시.

### E-H07. stale threshold의 source/frequency 정합성

- **분류:** `FIX`
- 공시, 일봉, 금리, 월간 macro에 동일 24시간 기준을 적용하면 잘못된 stale 상태가 생긴다.

필요:

- source registry의 frequency/calendar별 threshold.
- 주말/휴장/발표주기 인식.
- future timestamp는 healthy가 아니라 invalid.

## 6. Medium findings

### E-M01. source URL과 endpoint lineage

- **분류:** `ENRICH`
- endpoint는 가능한 경우 기록하되 key/query secret를 제거한다.
- raw URL 대신 adapter id + sanitized endpoint template를 권장한다.

### E-M02. numeric precision/unit normalization

- **분류:** `FIX`
- KRW, 억원, %, percentage point, bps, ratio를 typed unit으로 구분한다.
- display rounding과 stored precision을 분리한다.

### E-M03. data quality score provenance

- **분류:** `ENRICH`
- quality/confidence가 source base score, missing, stale penalty를 섞는다.
- component와 formula version을 저장한다.

### E-M04. snapshot immutability

- **분류:** `ENRICH`
- refresh cache와 current mock objects는 재현 가능한 historical snapshot store가 아니다.
- production alpha/backtest는 content hash와 immutable manifest가 필요하다.

## 7. 목표 시간축 모델

```text
event/economic period
  period_start / period_end

source publication
  released_at / receipt_date

analytics availability
  available_at

collection
  fetched_at

decision
  prediction_at / signal_generated_at

label
  label_start_at / label_end_at
```

Invariant:

```text
available_at <= prediction_at < label_start_at <= label_end_at
```

DART fiscal period end는 `period_end`일 뿐 `available_at`이 아니다.

## 8. 목표 pipeline

```text
SourceRegistry
  -> SourceResolution
  -> Adapter(raw response)
  -> Normalizer(typed value + metadata)
  -> Validation(schema/time/unit/identity)
  -> Immutable snapshot
  -> Module calculation
  -> UI/API projection
```

각 단계는 source id, instrument id, timestamp, unit, status를 잃지 않아야 한다.

## 9. 실제 backtest 구현 순서

1. date-effective security master.
2. adjusted/raw price와 trading calendar.
3. DART available-at financial facts.
4. source-vintage macro/flow where available.
5. immutable daily feature snapshots.
6. prediction/rebalance schedule.
7. future return label generator.
8. tradability/cost/tax/slippage/capacity.
9. walk-forward train/calibration/evaluation split.
10. report with universe, periods, sample, missing coverage, assumptions.

최소 report:

- snapshot/version id
- universe definition and count by date
- start/end/rebalance/holding horizon
- benchmark and calendar
- turnover/cost/tax/slippage
- missing/stale coverage
- return/CAGR/volatility/MDD/Sharpe/Sortino
- IC/rank IC/precision/spread with confidence interval
- delisted contribution
- limitations and no-guarantee language

## 10. 테스트 계획

Source/metadata:

- key present/missing/alias.
- planned adapter.
- keyless public fallback.
- stale by frequency/calendar.
- future timestamp invalid.
- unit conversion and instrument identity.
- secret-free endpoint serialization.

PIT:

- DART fiscal end before cutoff but available after cutoff => excluded.
- revised filing only after amendment available time.
- disclosure same-day before/after decision cutoff.
- macro revision vintage.
- feature available after prediction => fail.

Backtest:

- delisted/suspended/no-price/security transfer.
- split/dividend/rights adjustment.
- no fill/limit-up/liquidity cap.
- cost sensitivity and turnover.
- incomplete horizon N/A.
- deterministic snapshot rerun.
- randomized future-column leakage sentinel.

Regression:

```powershell
py -3.11 -m compileall app.py src tests
py -3.11 -m unittest discover tests
```

193 기준선 이상 전체 suite가 통과해야 한다.

## 11. Rollback

- adapter별 feature flag와 source resolution rollback.
- 실패 source는 error/empty로 내리고 다른 instrument 또는 mock으로 대체하지 않는다.
- PIT backtest flag off 시 숫자를 숨기고 `검증 데이터 필요`를 표시한다.
- snapshot schema는 versioned/additive. 이전 reader를 최소 한 release 유지한다.
- bad snapshot manifest는 quarantine하고 immutable 원본을 수정하지 않는다.
- DART availability/secret policy를 낮추는 rollback은 금지한다.

## 12. 완료 조건

- 모든 표시 숫자에 완전한 lineage와 typed unit이 있다.
- source fallback이 instrument identity를 바꾸지 않는다.
- future/revised data가 과거 decision에 들어가지 않는다.
- historical universe에 delisted/suspended가 포함된다.
- 합성 score return을 실제 backtest로 표시하지 않는다.
- production panel은 actual adapter 또는 명시적 empty 상태다.
- 193 기준선 이상 전체 테스트와 PIT suite가 통과한다.
