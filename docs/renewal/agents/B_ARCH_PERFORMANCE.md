# B. Architecture And Performance Audit

## 1. 범위

범위는 Streamlit rerun 구조, 모듈 경계, 캐시·외부 호출, session/global state, SQLite/file persistence, 단계적 모듈화다.

기준선:

- Python 3.11.8
- Streamlit 1.58.x
- 193 tests pass 이상
- `app.py` 약 9.2K LOC / 약 397KB
- `src/institutional/ui.py` 약 2.1K LOC / 약 112KB
- `src/ui/korea_os_theme.py` 약 1.5K LOC / 약 43KB

## 2. 현재 실행 구조

```text
main()
  sidebar/session 입력
  load_listing_cache()
  load_market_snapshot()
    Naver/FDR/KIS/FearGreed
  segmented_control(9 labels) + view query
  render_view_safely(selected renderer only)
```

감사 중 main router가 변경되어 현재는 선택한 renderer 하나만 평가한다. 이전 eager 9-view 실행은 완화됐지만 실제 `st.tabs` 계약은 segmented navigation으로 바뀌었다. 공통 listing/snapshot은 모든 화면 전환에서 조립되며, Dashboard 하나만 선택해도 기관 패널·portfolio intelligence·Korea OS·차트가 대량 실행된다.

## 3. 보존 대상

### B-P01. 진입점과 9개 화면 계약

- **분류:** `PRESERVE`
- `app.py`는 당분간 entrypoint로 유지한다.
- 9개 기존 이름·순서·renderer와 `view` slug를 유지한다.
- segmented widget 자체는 제품/접근성 승인 전 영구 계약으로 고정하지 않는다.
- session/widget/query key를 유지한다.

### B-P02. 명시적 timeout, TLS, cache

- **분류:** `PRESERVE` + `ENRICH`
- 외부 HTTP timeout과 TLS verification을 유지한다.
- public market data의 `@st.cache_data`를 유지하되 TTL/키/격리 정책을 문서화한다.
- Alpha Discovery와 Briefing의 explicit action trigger를 유지한다.

### B-P03. 도메인 엔진

- **분류:** `PRESERVE`
- `src/portfolio`, `src/discovery`, `src/execution`, `src/exits`, `src/monitoring`, `src/korea_equity`, `src/institutional` 경계를 재사용한다.
- UI 정리를 위해 금융 계산을 다시 구현하지 않는다.

## 4. Critical findings

### B-C01. module-global mutable risk settings

- **분류:** `FIX`
- `RISK_DEFAULTS`를 sidebar가 변경하고 여러 계산 함수가 암묵적으로 읽는다.
- Streamlit multi-session 프로세스에서 세션 간 결과가 교차 오염될 수 있다.

구현:

- frozen defaults + session `RiskSettings`.
- dependency injection으로 action/execution/portfolio 계산에 전달.
- 계산 함수의 hidden global read를 제거.
- old constant는 read-only compatibility alias.

검증:

- 두 session 동시 실행 isolation.
- 같은 입력+설정은 deterministic output.
- 설정 변경 전후 cache key가 정확히 분리.

### B-C02. 공용 persistence boundary

- **분류:** `FIX`
- signal SQLite와 briefing 파일이 process-wide이며 user/tenant namespace가 없다.
- public deployment라면 data isolation과 write authorization이 없다.

구현:

- public profile write-off.
- private profile tenant/user scope.
- SQLite WAL/busy timeout, migration version, retention.
- briefing logical id와 atomic write.

## 5. High findings

### B-H01. lazy router는 도입됐지만 계측·계약 검증이 없음

- **분류:** `PRESERVE` + `ENRICH`; navigation은 `FIX` 결정 필요
- 선택 renderer 한 개만 실행하는 것은 성능상 개선이다.
- 화면 전환마다 공통 listing/snapshot context를 다시 조립하며, Dashboard 내부에서는 history/leadership/기관 패널/figure가 연속 계산된다.
- segmented control의 keyboard/ARIA/deep-link 회귀 테스트와 이전 대비 latency/provider-call 계측이 없다.

개선:

- lazy selected-renderer router를 유지하거나 실제 tabs 복원 여부를 제품 결정으로 확정.
- `DashboardContext`에서 market regime, benchmark, histories, leadership를 한 번 계산.
- renderer는 pure/read-only view model을 받는다.
- DB summary는 Signal 화면에서만 request-scoped lazy accessor.
- hidden view의 manual action은 절대 실행하지 않음.

### B-H02. 캐시가 계층 경계를 대신함

- **분류:** `RELOCATE_WITH_ALIAS`
- provider client와 `st.cache_data` wrapper가 `app.py`에 함께 있어 테스트와 cache semantics가 결합된다.

개선:

- `src/services/*_client.py`: 순수 provider call/parse.
- `src/services/cached_market_data.py`: Streamlit cache wrapper.
- retry/backoff/rate limit/source metadata를 adapter별로 통일.
- 기존 `load_*` 함수는 wrapper alias로 유지.

### B-H03. sequential full-market scan

- **분류:** `FIX` + `ENRICH`
- 최대 1000종목 history를 순차 provider 호출하며 universe의 앞 N개를 사용한다.
- timeout/cancel/chunk checkpoint가 없다.

개선:

- deterministic universe ordering과 selection reason.
- bounded concurrency 또는 provider batch API.
- chunk progress, cancel, failure budget, rate-limit backoff.
- completed snapshot만 cache publish.

### B-H04. feature flag의 분산 parsing

- **분류:** `FIX`
- renderer마다 `os.getenv(...).strip().lower()`가 반복된다.
- Portfolio Risk 전용 flag가 없고 legacy/plan naming이 다르다.

개선:

- central `FeatureFlagRegistry`.
- canonical name, legacy alias, default, dependency, owner.
- UI에서 presence/value가 아니라 enabled/disabled reason만 표시.

### B-H05. integration contract test 부족

- **분류:** `ENRICH`
- signal ledger처럼 pure helper가 있어도 app wiring이 오래된 계약을 사용할 수 있다.
- import success/unit test만으로 tab workflow를 보장하지 못한다.

개선:

- renderer boundary typing.
- AppTest로 9개 view/router core workflow.
- API/view-model snapshot contract tests.

## 6. Medium findings

### B-M01. oversized entry/UI/theme modules

- **분류:** `RELOCATE_WITH_ALIAS`
- broad edit conflict와 review 난이도가 높다.
- `snapshot_source_label` 중복 정의처럼 shadowing 가능성이 있다.

추출 순서:

1. pure formatter.
2. chart builder.
3. source adapters.
4. institutional wrappers.
5. tab renderer.
6. context assembly.

한 PR에서 한 책임만 이동한다.

### B-M02. fake API path와 실제 route 경계

- **분류:** `ENRICH`
- institutional payload는 `/api/...` path를 표현하지만 현재 HTTP backend route는 없다.
- 이를 실제 endpoint처럼 운영 문서에 쓰지 말고 `service contract id`와 future path를 구분한다.

### B-M03. dependency lock 부족

- **분류:** `ENRICH`
- Python/Streamlit은 고정됐지만 pandas/numpy/matplotlib/requests 등은 하한만 있다.
- constraints lock, SBOM, 정기 upgrade test를 추가한다.

### B-M04. file lifecycle

- **분류:** `ENRICH`
- signal DB와 briefing의 size/retention/backup/atomicity가 정의되지 않았다.
- health check는 process health만 보고 write/storage health는 보지 않는다.

## 7. 목표 구조

```text
app.py
  configure page
  build session settings
  build DashboardContext
  route preserved 9 labels to one renderer

src/app_context.py
  immutable request context

src/services/
  provider clients
  cached adapters
  source metadata

src/components/tabs/
  dashboard.py
  portfolio.py
  stocks.py
  discovery.py
  disclosures.py
  macro.py
  briefing.py
  signal_outcomes.py
  settings.py

src/charts/
  pure matplotlib builders

src/domain packages
  existing calculation engines preserved
```

Compatibility:

- `app.py`의 기존 public helper는 새 함수로 위임한다.
- import alias와 widget key를 최소 한 release 유지한다.
- SQLite 기존 schema는 additive migration으로 읽는다.

## 8. Performance budget

P0에서 실제 값을 측정한 뒤 다음 상대 budget을 적용한다.

| 항목 | Gate |
|---|---|
| warm rerun p95 | P0 대비 +20% 이내, 최종 목표는 감소 |
| 동일 symbol/period provider read | 한 rerun 1회 이하 |
| listing/provider fetch | TTL 내 중복 0 |
| hidden view full-market scan | 0 |
| hidden view LLM/write | 0 |
| visible matplotlib figure | 필요한 detail 수만 생성 |
| cache payload | secret/user-specific 데이터 cross-session 공유 0 |
| provider timeout | 명시적 timeout 유지, 실패 시 bounded |

계측 필드:

- renderer name
- external provider/operation
- cache hit/miss
- duration ms
- row/symbol count
- status만 기록하고 URL query/key/user portfolio 값은 기록하지 않는다.

## 9. 테스트 계획

- Python 3.11.8 compile + 전체 unittest.
- AppTest 9개 화면/router smoke와 두 session isolation.
- provider fake로 timeout/retry/cache key/rate limit.
- performance benchmark cold/warm/refresh/15 symbols/1000 scan.
- SQLite concurrent read/write, lock timeout, migration, legacy row.
- memory leak: 50 rerun 후 figure close/cache size.
- feature flag canonical/legacy/dependency matrix.
- static import cycle와 duplicate function name audit.

## 10. Rollback

- 각 extraction은 wrapper switch로 old/new 구현을 전환한다.
- `ENABLE_RENEWAL_CONTEXT`, `ENABLE_CACHED_SERVICE_LAYER`를 독립 flag로 둔다.
- DB migration 전 backup, migration 실패 시 write-off/read-only.
- performance budget 실패 시 기능을 삭제하지 않고 새 context/cache 경로만 off한다.
- provider 오류 시 empty/error로 내리며 mock/다른 상품으로 바꾸지 않는다.
- unrelated worker 변경은 rollback 범위에 포함하지 않는다.

## 11. 완료 조건

- 9개 탭 계약 유지.
- global mutable user setting 0.
- public profile shared write 0.
- 같은 데이터/계산 중복 감소가 계측으로 증명됨.
- `app.py` 추출 후에도 기존 import/widget/query 호환.
- 193 기준선 이상 전체 test와 performance budget 통과.
