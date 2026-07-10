# Renewal Risk And Gap Analysis

> **Final verification update (2026-07-10):** the code-level Critical and High findings identified during implementation and independent re-review were fixed and regression-tested. The remaining release conditions are the external OpenDART/ECOS CA trust failure, unavailable Docker CLI, and Streamlit browser-Back popstate limitation. See `docs/review_fix/03_fix_ledger.md` through `06_final_release_decision.md`. Earlier open-risk language below is preserved as the pre-fix analysis record.

## 1. 평가 기준

### 1.1 심각도

| 등급 | 정의 | 처리 원칙 |
|---|---|---|
| `Critical` | 사용자 데이터 격리, 투자 판단 정확성, 핵심 탭 실행을 깨뜨리거나 잘못된 검증 결과를 실데이터처럼 노출할 수 있음 | 영향 기능 release blocker. 먼저 차단 또는 수정 |
| `High` | 주요 워크플로, 데이터 신뢰, 성능, 보안, 접근성에 유의미한 결함/간극이 있음 | 다음 production increment 전에 처리 |
| `Medium` | 즉시 오판 가능성은 낮지만 유지보수·일관성·장기 신뢰성을 저해 | 계획된 정비 PR에서 처리 |

### 1.2 변경 분류

- `PRESERVE`: 현재 계약을 회귀 테스트로 고정.
- `ENRICH`: 기존 경로를 유지하면서 데이터·상태·설명·테스트 추가.
- `RELOCATE_WITH_ALIAS`: 위치를 옮기되 기존 함수/import/widget/query alias 유지.
- `FIX`: 잘못된 동작을 직접 교정. 잘못된 결과에 호환성을 제공하지 않음.

## 2. 요약

현재 앱은 9개 탭, 한국어 UI, 한국 시장 색 규칙, source registry, 기관 패널 계약, 투자 안전 문구를 폭넓게 갖췄다. `SHOW_MOCK_DATA=false`인 운영 모드에서 Korea Alpha와 기관 mock 입력을 차단하는 최근 경계도 적절하다.

감사 중 동시 작업으로 두 안전 결함은 코드 수준에서 완화됐다. 신호 성과 UI는 mapping/PIT helper를 사용하고, 현재 점수만 전달한 backtest는 성과 숫자 대신 `validation_unavailable`을 반환한다. 두 항목은 실행 검증 전이므로 회귀 gate로 유지한다.

production readiness를 가르는 열린 핵심 간극은 다음 네 가지다.

1. 리스크 설정이 공용 module global에서 변경된다.
2. signal/briefing 영속 데이터와 유료 호출의 사용자 격리가 없다.
3. 기존 `st.tabs` 계약이 segmented single-view router로 바뀌어 제품·접근성 호환성 결정이 필요하다.
4. 실제 valuation/fundamental/flow/short/forward-alpha/optimizer 데이터 wiring이 미완료다.

## 3. Critical

### 감사 중 해결된 Critical 후보: 회귀 방지

- **신호 성과 계약:** UI가 `signal_record_from_mapping()`과 `compute_forward_outcomes()`를 사용하도록 연결됐다. 1/5/20/60 거래일, benchmark, 비용, 미성숙 horizon 처리를 4개 PIT 테스트가 고정한다. `PRESERVE`하되 AppTest 실행 검증이 남았다.
- **합성 backtest 숫자:** current score만 전달하면 `synthetic_demo`/`validation_unavailable`과 빈 returns/N/A metrics를 반환한다. historical universe, cutoff, 비용을 요구하는 chronological engine과 8개 integrity 테스트가 추가됐다. 이 hard gate를 `PRESERVE`한다.

두 항목은 **코드 정적 확인상 해결**이며 이번 세션에서 테스트를 실행하지 못했으므로 release 완료로 간주하지 않는다.

### R-C03. 리스크 설정이 프로세스 전역에서 변경됨

- **분류:** `FIX`
- **영향:** action score, 기대값, 최대 비중, portfolio/stock/execution 판단.
- **근거:** module-level mutable `RISK_DEFAULTS`를 sidebar slider가 직접 수정한다.
- **위험:** 같은 Streamlit 프로세스의 한 세션이 다른 세션의 리스크·비용 기준을 바꿀 수 있다. 화면에 보이는 값과 계산 당시 값이 달라질 수 있다.
- **필수 수정:** immutable default와 session-scoped `RiskSettings`를 분리하고 모든 계산 함수에 명시적으로 전달한다.
- **종료 조건:** 서로 다른 설정을 가진 두 AppTest 세션의 계산이 교차 오염되지 않고, 새 세션은 고정 기본값으로 시작해야 한다.

### R-C04. 공용 배포에서 영속 데이터·유료 호출 격리가 없음

- **분류:** `FIX`
- **영향:** `data/signal_ledger.sqlite3`, 날짜별 briefing 파일, 서버의 OpenAI 호출.
- **근거:** Render/Procfile은 `0.0.0.0`에 앱을 열지만 앱 자체 인증/tenant 식별자가 없다. signals/outcomes에 사용자/세션 열이 없고 briefing 파일명은 날짜 단위다. 생성 버튼 rate limit도 없다.
- **위험:** 공개 배포라면 사용자가 서로의 신호 기록을 조회/갱신하고 같은 날짜 브리핑을 덮어쓸 수 있으며, 서버 API quota를 소모할 수 있다.
- **조건:** 외부 access control이 강제된 단일 사용자 배포라면 심각도는 `High`로 낮출 수 있으나 그 가정이 배포 설정에 명시되어야 한다.
- **필수 수정:** public profile에서는 write/LLM 기능 default-off. 인증된 private profile에서는 tenant/user scope, quota, retention, audit event를 추가한다.
- **종료 조건:** 두 사용자 fixture의 signal/briefing이 분리되고, 비인증·quota 초과 요청이 영속 write/유료 호출을 수행하지 않아야 한다.

## 4. High

### R-H01. 포트폴리오 canonical context의 부분 연결

- **분류:** `FIX`
- `src/portfolio/context.py`와 10개 테스트가 추가돼 computed total을 authoritative로 두고 discrepancy/validation/history coverage/risk contribution을 표현한다.
- Risk Cockpit과 Portfolio Intelligence는 새 context를 사용하지만, 2번 Portfolio 탭의 보유 표·손절 loop는 여전히 legacy parsed rows를 직접 계산한다.
- context adapter도 누락 현재가를 평균단가로 대체하고 warning만 남겨 exact-looking 평가액이 생길 수 있다.
- **완료 기준:** Portfolio 탭까지 canonical context를 사용하고, 누락 현재가는 nullable/계산 제한으로 처리하며, parser validation·source 근접 표시·합계 invariant가 UI integration에서 통과.

### R-H02. 기존 tab widget 계약이 segmented router로 변경됨

- **분류:** `FIX` 또는 승인된 경우 `RELOCATE_WITH_ALIAS`
- 현재 main은 9개 label을 `st.segmented_control`로 표시하고 선택한 renderer 하나만 실행한다. `view` query parameter와 `render_view_safely()`가 추가돼 eager 실행 문제는 완화됐다.
- 하지만 실제 `st.tabs`와 ARIA tab semantics가 사라졌고, 저장된 session/query/deep link 및 기존 tab 기대와 다른 navigation 계약이다.
- **완료 기준:** 제품 소유자가 segmented navigation을 승인하거나 실제 tabs를 복원한다. 어느 쪽이든 9개 label/order/function, keyboard semantics, direct link, back/refresh를 AppTest/browser로 고정한다.

### R-H03. legacy `Snapshot`과 기관 metadata 계약이 분리됨

- **분류:** `ENRICH`
- legacy snapshot은 `asof`, source, unit, quality, fallback을 갖지만 `available_at`/`fetched_at`를 일관되게 보존하지 않는다.
- 상단 `last_refresh`는 KST 포맷으로 개선됐지만 signal/legacy metadata의 timezone·availability 의미는 아직 통합되지 않았다.
- **완료 기준:** Asia/Seoul aware timestamp, source adapter id, endpoint, as-of/available/fetched, stale, accuracy grade를 공통 context로 전달한다.

### R-H04. 한국 3년물 fallback이 다른 상품을 같은 키로 대체할 수 있음

- **분류:** `FIX`
- 국고채 3년 조회 실패 시 회사채 3년 snapshot을 `KR 3Y` 키로 대체한다.
- 상단 고정 제목은 한국 국고채 3년으로 읽힐 수 있어 instrument identity가 바뀐다.
- **완료 기준:** 정부채와 회사채를 별도 key/label로 유지하고, 대체가 필요하면 값이 아니라 explicit unavailable + 대체 참고 행을 표시한다.

### R-H05. 기관 패널 계산 엔진과 실제 adapter wiring 사이 간극

- **분류:** `ENRICH`
- valuation, fundamental, institutional DART catalyst, flow/short, forward alpha, optimizer가 운영 모드에서 실제 입력을 받지 못한다.
- 공시 탭의 실제 `load_recent_disclosures()` 결과도 기관 DART panel에 전달되지 않는다.
- optimizer는 실제 sidebar holdings와 실제 upstream alpha state를 받지 않는다.
- **완료 기준:** 패널별 read-only adapter, 공통 context, metadata completeness, empty/error/stale 테스트를 갖추고 priority 순서대로 연결한다.

### R-H06. feature flag 계약이 불완전하고 기존 계획과 이름이 다름

- **분류:** `FIX`
- 9개 기관 패널은 `STANCE_ENABLE_*`이 있으나 Portfolio Risk Cockpit 전용 flag는 없다.
- flag 기본값은 on이고 parsing이 각 renderer에 반복된다.
- 기존 계획 문서의 `ENABLE_*` 이름과 현재 runtime 이름이 다르다.
- **완료 기준:** 중앙 registry, canonical flag + legacy alias, safe default, panel별 kill switch, flag matrix test.

### R-H07. 알파 확률·기대수익 명칭이 실증 보정 수준보다 강함

- **분류:** `FIX` + `ENRICH`
- prediction engine은 hand-tuned linear formula로 기대수익/초과확률을 만든다.
- backtest engine은 합성 성과 숫자를 차단하도록 개선됐지만 `calibrateScoreToHistoricalReturns()`와 UI의 `룰 기반 추정 성과` 명칭은 실제 fit 수준과 구분해야 한다.
- Discovery scan은 listing의 앞 N개를 순차 선택하고 실제 regime 대신 50점을 고정 전달한다.
- **완료 기준:** 검증 전에는 `휴리스틱 범위`로 표시하고 probability 명칭을 사용하지 않는다. universe selection, regime input, calibration dataset/version을 기록한다.

### R-H08. 오류·경로·외부 URL 출력 sanitization이 일관되지 않음

- **분류:** `FIX`
- view-level 오류는 `render_view_safely()`와 debug redaction으로 개선됐지만 OpenAI/KIS 내부 경로는 raw exception/response message를 UI state로 저장할 수 있다.
- briefing 저장 후 서버 절대 경로를 화면에 표시한다.
- 일부 동적 external URL은 HTML escape만 하고 scheme allowlist를 공통 적용하지 않는다.
- **완료 기준:** 모든 사용자 오류는 중앙 redaction, 내부 correlation id, 허용 scheme(`https`) 검증, 사용자용 상대 식별자로 통일한다.

### R-H09. 현재 테스트는 unit/static 중심이며 실제 앱 경로를 충분히 검증하지 않음

- **분류:** `ENRICH`
- 193 pass 기준선은 강점이나, Streamlit AppTest/브라우저 E2E, provider contract, 성능 budget, axe 기반 접근성, 다중 세션 격리 검증이 없다.
- signal ledger처럼 함수 테스트가 존재해도 UI wiring 오류가 남을 수 있다.
- **완료 기준:** 9개 화면/router smoke, 핵심 버튼 workflow, mobile/desktop screenshot, keyboard/axe, public profile security 테스트를 CI에 추가한다.

### R-H10. 대시보드 정보 밀도와 반복 empty 상태

- **분류:** `ENRICH`
- 단일 Dashboard에 기관 10개, portfolio intelligence, Korea OS, Fear/Greed, macro, stock cards와 차트가 이어진다.
- 운영 모드에서는 미연결 기관 패널 empty state가 연속 노출될 수 있다.
- **완료 기준:** 상단에는 시장·핵심 위험·즉시 검토만 유지하고, 나머지는 compact status/anchor/progressive disclosure로 정리한다. 모듈은 삭제하지 않는다.

## 5. Medium

### R-M01. `app.py`와 UI/CSS 파일의 규모

- **분류:** `RELOCATE_WITH_ALIAS`
- `app.py` 약 9.2K LOC, `src/institutional/ui.py` 약 2.1K LOC, theme 약 1.5K LOC다.
- `snapshot_source_label` 같은 중복 정의도 존재한다.
- pure formatter, chart, service facade, renderer를 작은 PR로 옮기고 기존 symbol wrapper를 유지한다.

### R-M02. 설정의 편집 위치와 조회 위치가 분리됨

- **분류:** `RELOCATE_WITH_ALIAS`
- risk slider는 sidebar에 있고 Settings 탭은 값을 표로만 보여준다.
- Settings에 canonical controls를 추가하되 sidebar controls는 alias로 유지해 기존 사용 흐름을 깨지 않는다.

### R-M03. dependency 재현성

- **분류:** `ENRICH`
- Streamlit/Python 기준은 고정됐지만 나머지 package는 넓은 하한 범위이며 hash lock이 없다.
- Python 3.11.8 + Streamlit 1.58 기준 constraints/lock과 주기적 upgrade PR을 둔다.

### R-M04. semantic HTML과 chart 대체 설명

- **분류:** `ENRICH`
- custom card의 제목이 `<div>` 중심이고 일부 table에는 caption/scope가 없다.
- matplotlib chart의 핵심 수치 요약은 화면에 일부 존재하지만 일관된 대체 설명 계약이 없다.
- heading hierarchy, table caption/header scope, chart summary/underlying data link를 추가한다.

### R-M05. SQLite schema migration·retention 정책 없음

- **분류:** `ENRICH`
- `CREATE TABLE IF NOT EXISTS`만 있고 schema version, migration, backup/retention 정책이 없다.
- additive migration, version table, pre-migration backup, 오래된 outcome 정리 정책을 도입한다.

### R-M06. 날짜·언어 표기 일관성

- **분류:** `FIX`
- Data Trust/Risk는 KST 한국형 포맷을 갖지만 dashboard/signal/portfolio 일부는 raw ISO 또는 하이픈 형식이다.
- 모든 사용자 timestamp를 `YYYY.MM.DD HH:mm` Asia/Seoul로 통일하고 raw ISO는 API payload에만 둔다.

## 6. 보존해야 할 강점

다음은 결함이 아니며 변경 과정에서 `PRESERVE`해야 한다.

- 중앙 `src/config/env.py`와 비밀값 presence-only 표시.
- TLS verification 유지와 요청 timeout.
- no automatic order execution.
- high-risk override가 alpha score보다 우선하는 규칙.
- mock/stale/planned/empty를 분리하는 기관 contracts.
- DART `available_at`/`receipt_date` selector와 관련 테스트.
- 한국 시장 방향 색과 severity 색 분리.
- 한국어 labels와 내부 enum mapping.
- 수동 실행인 Alpha Discovery와 버튼 기반 GPT 생성.
- SQLite parameter binding과 `.gitignore`의 secret/runtime data 제외.

## 7. 우선순위 의존성

```text
R-C03 세션 설정 격리
  -> 포트폴리오/종목/알파 계산의 재현성

PIT 신호 UI 계약(감사 중 연결됨)
  -> 실제 forward outcome 축적
  -> R-H07 실제 calibration/backtest 근거

R-H03 공통 metadata
  -> R-H05 실제 adapter wiring
  -> Forward Alpha / Optimizer production 승격

R-C04 사용자·영속 범위 결정
  -> Signal ledger/Briefing write 기능 production 활성화

R-H02 navigation 계약 결정
  -> 9개 화면 keyboard/deep-link 회귀 + lazy 성능 기준 확정
```

구현 순서는 `02_implementation_plan.md`에 정의한다.
