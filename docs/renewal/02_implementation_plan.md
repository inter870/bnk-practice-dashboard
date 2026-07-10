# Renewal Implementation Plan

> **Execution status (2026-07-10):** the safety-critical implementation slice, canonical portfolio guards, PIT backtest and signal guards, provider metadata corrections, runtime/cache fixes, responsive navigation, and regression tests are complete. The final suite passed 255 tests three times. Real-data promotion remains conditional on CA bundle and Docker release gates documented in `docs/review_fix/06_final_release_decision.md`.

## 1. 목표와 비목표

목표는 기존 9개 탭을 유지하면서 정확성, 데이터 신뢰, 세션 격리, 성능, 접근성을 단계적으로 높이는 것이다.

비목표:

- 대시보드 재구축 또는 프레임워크 교체.
- 탭 삭제·이름 변경·순서 변경.
- 자동 주문 실행.
- 검증 전 mock/휴리스틱을 실전 수치로 승격.
- 여러 도메인을 한 번에 옮기는 대규모 `app.py` rewrite.

## 2. 고정 기준선

| Gate | 요구사항 |
|---|---|
| Runtime | Python **3.11.8** |
| Framework | Streamlit **1.58.x** (`>=1.58,<1.59`) |
| Regression floor | 기존 **193 tests pass** 이상. 현재 suite가 216개면 216개 전부 통과 |
| Compile | `py -3.11 -m compileall app.py src tests` |
| Unit | `py -3.11 -m unittest discover tests` |
| Navigation | 기존 9개 label·순서·renderer 유지. segmented router의 tab 호환성은 명시적으로 승인/수정 |
| Safety | 주문 API 없음, 검토/관찰/리스크 관리 문구 유지 |
| Data | mock production 노출 0, metadata 누락 0, future filing 사용 0 |
| Mobile | 390px에서 page-level horizontal overflow 0 |

현재 문서 세션은 Python interpreter 부재로 명령을 재실행하지 못했다. 구현 PR에서는 실행 가능한 Python 3.11.8 환경에서 기준선을 먼저 재현해야 한다.

## 3. 전달 방식

각 단계는 독립 PR/patch bundle로 전달한다.

1. 계산 변경과 UI 이동을 같은 PR에 섞지 않는다.
2. `RELOCATE_WITH_ALIAS` 작업은 최소 한 release 동안 기존 import/function wrapper를 둔다.
3. 기존 widget key, query parameter, tab label을 바꾸지 않는다.
4. DB 변경은 additive migration만 사용한다.
5. 새 provider는 feature flag와 empty/error/stale 상태를 먼저 갖춘다.
6. 새 결과가 준비되지 않으면 N/A/empty를 표시하며 mock으로 채우지 않는다.

## 4. 단계 0: 기준선 동결과 계측

### P0-01. 재현 가능한 실행 환경

- **분류:** `PRESERVE` + `ENRICH`
- Python 3.11.8 환경에서 Streamlit 1.58.x 설치 결과를 기록한다.
- `pip freeze` 전체를 문서에 붙이지 말고, release constraints artifact를 생성한다.
- compile/unit 결과, 테스트 수, 소요 시간, peak RSS를 CI artifact로 남긴다.

### P0-02. 9개 화면/navigation smoke 기준선

- 각 탭의 제목, 핵심 control, empty 상태를 Streamlit AppTest 또는 브라우저로 확인한다.
- desktop 1440x1000, tablet 900x900, mobile 390x844 screenshot을 기준선으로 남긴다.
- provider call count, `load_symbol_history` 호출/고유 cache key 수, matplotlib figure 수, SQLite query 수를 계측한다.

### P0-03. production profile 확인

- `SHOW_MOCK_DATA=false`에서 mock 숫자·후보·backtest가 보이지 않는지 확인한다.
- planned adapter는 `어댑터 미연결` 또는 `연결 예정`만 표시하는지 확인한다.
- 비밀값은 presence boolean 이외에 log/UI/artifact에 나오지 않는지 확인한다.

Rollback:

- 계측은 read-only여야 한다. 계측 hook으로 latency가 5% 이상 증가하면 hook을 feature flag로 끈다.

## 5. 단계 1: Critical 기능·격리 수정

### P1-01. 연결된 신호 PIT 경로를 실행 검증하고 고정

- **위험:** 감사 중 해결된 Critical 후보의 회귀
- **분류:** `PRESERVE` + `ENRICH`
- 현재 `app.py`가 사용하는 `compute_forward_outcomes`, `signal_record_from_mapping` 경로를 유지한다.
- `list_recent_signals()`의 dict 반환을 UI boundary에서 dataclass로 복원한다.
- `generated_at` 이후 첫 거래일부터 1/5/20/60 거래일 outcome을 저장하는 현재 동작을 AppTest로 검증한다.
- 아직 도달하지 않은 horizon은 저장하지 않거나 명시적 unavailable 상태로 유지한다.
- benchmark history와 비용 가정을 동일 기간으로 정렬한다.
- target/stop/entry가 신호 생성 당시 고정되지 않았다면 사후 재계산하지 말고 N/A로 둔다.

테스트:

- 기존 `test_signal_monitoring.py`와 `test_signal_outcome_pit.py`.
- empty ledger, legacy row, malformed row, partial horizon, timezone 경계.
- UI 버튼 integration: save -> list -> update -> list.

Rollback:

- `ENABLE_SIGNAL_OUTCOME_UPDATE=false`로 update 버튼만 비활성화하고 기존 신호 read-only 목록은 유지한다.
- 기존 `signals`/`outcomes` 행을 삭제하지 않는다.

### P1-02. 리스크 설정 세션 격리

- **위험:** `R-C03`
- **분류:** `FIX`
- module global을 immutable `DEFAULT_RISK_SETTINGS`로 바꾼다.
- `st.session_state.risk_settings`를 canonical runtime 값으로 사용한다.
- action, portfolio, execution, exit 계산에 `RiskSettings`를 명시적으로 전달한다.
- Settings 탭과 sidebar는 같은 session object를 편집한다.

테스트:

- default serialization/validation.
- 두 독립 AppTest 세션의 값과 결과가 섞이지 않음.
- 비용/최대비중 변경이 관련 계산에만 반영됨.

Rollback:

- 기존 상수 이름은 read-only mapping alias로 유지한다.
- migration 실패 시 현재 세션만 default로 복구하고 다른 세션/전역을 변경하지 않는다.

### P1-03. public/private write profile

- **위험:** `R-C04`
- **분류:** `FIX`
- 기본 public profile은 `ENABLE_SIGNAL_LEDGER_WRITES=false`, `ENABLE_BRIEFING_PERSISTENCE=false`.
- 유료 생성에는 per-session cooldown과 server-side quota를 둔다.
- private profile에서만 인증 주체의 tenant/user id를 signal/briefing namespace에 포함한다.
- 배포 access control이 외부에 있다면 runbook에 강제 조건과 검증 방법을 기록한다.

테스트:

- public profile write/LLM 차단.
- 두 tenant의 list/update 격리.
- quota, retry, concurrent write, SQLite lock handling.

Rollback:

- write flag를 즉시 off한다.
- schema migration 전 backup을 만들고 additive column은 구버전 reader가 무시할 수 있게 한다.

### P1-04. 사용자 오류 redaction

- **위험:** `R-H08`
- **분류:** `FIX`
- OpenAI, KIS, ECOS, DART, file IO 예외를 공통 `safe_user_error()`로 통과시킨다.
- UI에는 provider, 상태, correlation id만 보여준다.
- 서버 절대 경로 대신 `브리핑 저장됨`과 논리적 id를 표시한다.
- external URL은 `https` allowlist와 provider host 검증 후에만 링크로 렌더한다.

Rollback:

- provider별 기존 메시지로 돌아가지 않고, 실패 시 더 일반적인 안전 메시지를 사용한다.

## 6. 단계 2: 데이터 신뢰 계약 통합

### P2-01. 공통 DashboardContext

- **분류:** `ENRICH`
- `Snapshot`을 즉시 삭제하지 않는다.
- 새 `DashboardContext`에 selected code, holdings, market snapshot, source metadata, risk settings, feature flags, request timestamp를 둔다.
- legacy renderer에는 adapter를 통해 기존 인수를 전달한다.
- 공통 timestamp는 timezone-aware Asia/Seoul로 생성한다.

필수 metadata:

- `source`
- `adapter_id`/endpoint(가능한 경우)
- `as_of_date`
- `available_at` 또는 `fetched_at`
- `unit`, frequency
- stale/fallback/mock/planned
- accuracy grade, confidence/quality

### P2-02. source identity와 fallback 수정

- **위험:** `R-H03`, `R-H04`
- **분류:** `FIX`
- 국고채 3년과 회사채 3년을 별도 instrument id로 유지한다.
- Naver/FDR은 public snapshot/fallback으로 표시하고 official realtime 표현을 금지한다.
- 데이터가 없을 때 다른 의미의 상품 값으로 대체하지 않는다.

### P2-03. 기관 패널 실제 wiring 1차

- **위험:** `R-H05`
- **분류:** `ENRICH`
- 기존 실제 입력으로 연결 가능한 순서만 먼저 처리한다.
  1. Portfolio Risk: sidebar holdings + reconciled price metadata.
  2. Data Trust: 공통 context source matrix.
  3. Market Regime/KRW: 현재 snapshot + ECOS.
  4. DART Catalyst: `load_recent_disclosures()` 결과를 receipt/available contract로 변환.
- valuation/fundamental/flow/short는 adapter 전까지 empty 상태를 유지한다.

### P2-04. feature flag registry

- **위험:** `R-H06`
- **분류:** `FIX`
- canonical flag 이름, default, owner, dependency, legacy alias를 한 registry에 둔다.
- Portfolio Risk에도 kill switch를 추가한다.
- 현재 `STANCE_ENABLE_*`과 계획 문서의 `ENABLE_*`는 한 release 동안 alias로 수용하고 충돌 시 canonical 값을 우선한다.

테스트:

- metadata completeness property test.
- future timestamps/stale thresholds.
- source identity/fallback matrix.
- flag on/off/dependency/legacy alias.
- `SHOW_MOCK_DATA=false` mock 0건 정적·render audit.

Rollback:

- panel별 flag off.
- adapter 오류 시 empty/error 상태로 내리고 다른 source를 official로 승격하지 않는다.

## 7. 단계 3: 포트폴리오·리스크 정확성

### P3-01. 도입된 PortfolioContext를 모든 경로에 적용

- **위험:** `R-H01`
- **분류:** `FIX`
- 현재 canonical context, computed-total discrepancy, history coverage/risk contribution tests를 출발점으로 사용한다.
- Risk Cockpit/Portfolio Intelligence뿐 아니라 Portfolio 탭의 보유 표·손실률·섹터 경고에도 같은 context를 적용한다.
- 수량 `>0`, 평균단가 `>0`, 유효 6자리 code, 유한 숫자를 요구한다.
- 중복 code 정책을 명시한다: 동일 sector/currency면 합산, 충돌하면 행 오류.
- `declared_total`, `holdings_value`, `cash`, `unreconciled_amount`를 분리한다.
- tolerance 밖 불일치는 계산 제한과 한국어 경고를 표시한다.
- 누락 현재가는 평균단가를 현재가로 가장하지 않고 `price unavailable`로 유지한다.

### P3-02. risk engine invariant

- allocation 합계는 허용 오차 내 100%.
- 총자산보다 큰 risk budget 금지.
- sector source와 price source를 분리.
- stale/missing 가격이 있으면 actionability를 차단.
- 다중 currency는 FX source가 없으면 KRW total 계산 불가.

### P3-03. 실제 optimizer 연결

- 실제 holdings, reconciled cash, Forward Alpha production state를 전달한다.
- upstream 하나라도 mock/stale/empty면 target action을 N/A/review-only로 내린다.
- long-only, no leverage, cash buffer, single/sector/KOSDAQ cap을 invariant로 검사한다.

테스트:

- 음수/0/NaN/Infinity, duplicate, cash 초과, 총자산 불일치.
- stale price, missing sector, missing FX.
- high-score/high-risk override.
- optimizer weight 합계와 cap property tests.

Rollback:

- `ENABLE_RECONCILED_PORTFOLIO=false`에서 legacy read-only 표를 유지하되 신규 action 출력은 하지 않는다.
- 실제 입력을 mock으로 대체하지 않는다.

## 8. 단계 4: 아키텍처·성능 정비

### P4-01. 선택 화면과 Dashboard 내부 공통 계산 재사용

- **위험:** `R-H02`
- **분류:** `ENRICH`
- market regime, KOSPI series, watchlist histories, leadership rows를 context에서 한 번 계산한다.
- 현재 router는 선택 화면 하나만 실행하므로 cross-view eager 계산은 발생하지 않는다. 같은 Dashboard 내부와 화면 전환 cache에서 immutable result를 재사용한다.
- ECOS fetch/result는 Dashboard summary와 Macro detail이 공유한다.
- Alpha Discovery의 수동 실행은 유지한다.

### P4-02. `app.py` 단계적 추출

- **위험:** `R-M01`
- **분류:** `RELOCATE_WITH_ALIAS`
- PR 순서:
  1. pure formatting -> `src/ui/formatting.py`
  2. chart builder -> `src/charts/`
  3. provider client -> `src/services/`
  4. tab renderer -> `src/components/tabs/`
  5. context assembly -> `src/app_context.py`
- `app.py`의 기존 함수명은 wrapper로 남기고 session/widget key는 바꾸지 않는다.

### P4-03. 9개 navigation 계약과 lazy 비용 고정

- 현재 `st.segmented_control` + `view` query router는 선택한 renderer 하나만 실행한다.
- 제품 소유자가 이를 승인하면 9개 기존 label/function의 compatibility alias와 keyboard/deep-link 동작을 고정한다.
- 실제 `st.tabs`가 필수 계약이면 tabs를 복원하되 heavy work를 explicit action/cached context/deferred detail로 제한한다.
- 어느 경로든 hidden view가 scan/LLM/write를 실행하지 않아야 한다.
- provider별 concurrency/rate limit를 지키고 1000종목 scan은 chunk/progress/cancel을 제공한다.

성능 acceptance:

- warm rerun p95가 P0 기준보다 20% 이상 느려지지 않음.
- 같은 symbol/period history provider 호출은 한 rerun에 1회 이하.
- hidden manual workflow가 외부 scan/LLM/write를 시작하지 않음.
- figure는 표시되는 detail에 필요한 수만 생성.
- 새 cache는 secret/user-specific 값을 cross-session 공유하지 않음.

Rollback:

- wrapper가 old implementation을 호출하도록 전환한다.
- extraction과 계산 변경을 같은 commit에서 되돌릴 필요가 없도록 분리한다.

## 9. 단계 5: UX·접근성·설정 정리

### P5-01. Dashboard progressive disclosure

- **위험:** `R-H10`
- **분류:** `ENRICH`
- 첫 화면 우선순위: 시장 snapshot -> action console -> Critical/High risk -> source freshness.
- 연결되지 않은 패널은 compact status 행으로 유지하고 anchor/module id는 보존한다.
- 연결된 패널만 상세 body를 기본 노출하며 나머지는 expander/anchor로 접근한다.
- 모듈 삭제, 탭 변경, marketing hero 추가는 하지 않는다.

### P5-02. Settings canonical control

- **위험:** `R-M02`
- **분류:** `RELOCATE_WITH_ALIAS`
- Settings 탭에 risk settings, feature status, data mode를 편집/확인하는 canonical UI를 둔다.
- sidebar control은 같은 session state의 shortcut alias로 유지한다.

### P5-03. semantic/a11y

- heading hierarchy, landmarks, table caption/scope, focus order, visible focus를 보강한다.
- matplotlib chart마다 한국어 summary와 데이터 기준/단위를 제공한다.
- 색 외에 부호·라벨·badge text를 유지한다.
- `prefers-reduced-motion`, 200% zoom, keyboard-only, screen reader name을 검증한다.

테스트:

- Playwright 1440/900/390 screenshot diff.
- axe critical/serious 0.
- keyboard로 9개 화면 selector, form, expander, link, button 접근. 실제 tabs를 택하면 tab role도 확인.
- 200% zoom에서 text overlap/page overflow 0.
- 기존 한국어/color/readability audit 전부 통과.

Rollback:

- layout flag로 기존 body 순서를 복구할 수 있게 한다.
- semantic attribute 추가는 rollback 대상이 아니며 깨진 CSS만 scoped rollback한다.

## 10. 단계 6: 실데이터 알파와 PIT 백테스트

### P6-01. production feature snapshot store

- **분류:** `ENRICH`
- 종목/일자별 feature value와 source metadata를 immutable snapshot id로 저장한다.
- DART는 `available_at`, 가격은 거래일 close availability, macro는 release timestamp를 사용한다.
- 당시 상장 universe와 delisted/security status를 저장한다.

### P6-02. 기존 chronological PIT engine을 production 수준으로 확장

- **위험:** 해결된 synthetic hard gate의 회귀, `R-H07`
- **분류:** `PRESERVE` + `ENRICH`
- historical feature/price/universe와 cutoff/cost를 요구하는 현재 engine 및 integrity tests를 유지한다.
- train/calibration/evaluation window를 시간 순서로 분리한다.
- rebalance timestamp 이전에 available한 feature만 join한다.
- corporate action, suspension, delisting, 거래 불가, liquidity capacity를 반영한다.
- turnover별 commission, tax, slippage, market impact를 적용한다.
- KOSPI/KOSDAQ benchmark와 동일 calendar로 비교한다.

### P6-03. calibration과 UI 승격

- 표본 수, 기간, universe, IC/precision confidence interval, calibration error를 표시한다.
- 최소 표본/기간 gate 전에는 probability와 expected return을 N/A로 유지한다.
- 기존 합성 결과는 `데모 시뮬레이션` namespace에만 남기거나 제거한다.

테스트:

- future feature leakage fixture는 실패.
- fiscal period end만 있는 DART 행은 제외.
- delisted 종목 포함 universe.
- same-day disclosure cutoff.
- 거래정지/가격 없음/상한가 체결 불가.
- cost 0/기본/스트레스 sensitivity.
- deterministic seed와 snapshot reproducibility.

Rollback:

- `ENABLE_PIT_BACKTEST=false`로 숫자 대신 `검증 데이터 필요`를 표시한다.
- 이전 합성 수치를 production fallback으로 사용하지 않는다.

## 11. CI test matrix

| Job | 명령/도구 | 필수 조건 |
|---|---|---|
| Compile | `py -3.11 -m compileall app.py src tests` | 오류 0 |
| Unit | `py -3.11 -m unittest discover tests` | 193 기준선 이상 전체 pass |
| Static policy | 기존 localization/color/data-trust/risk scripts | finding 0 |
| Streamlit smoke | AppTest | 9개 화면/router 핵심 control/empty state pass |
| Browser | Playwright | desktop/tablet/mobile, console error 0 |
| Accessibility | axe + keyboard script | critical/serious 0 |
| Security | secret scan, URL scheme, public write profile | secret output/write 우회 0 |
| Data contract | provider fixtures | metadata 누락/future row 0 |
| Performance | cold/warm rerun benchmark | baseline 대비 정의된 budget 충족 |

## 12. 배포와 rollback playbook

### 12.1 배포 순서

1. staging에 모든 신규 flag off로 배포.
2. compile/unit/static policy 확인.
3. read-only context/metadata flag on.
4. 한 기관 패널씩 on.
5. private profile에서만 write/LLM flag on.
6. 24시간 error/latency/source freshness 관찰.
7. 다음 단계 진행.

### 12.2 즉시 rollback trigger

- 기존 9개 화면 중 하나가 렌더되지 않거나 label/order/deep link가 깨짐.
- baseline test 하나라도 실패.
- mock이 production profile에 숫자로 노출.
- source/timestamp/unit 없이 새 숫자 노출.
- signal outcome이 signal 이전 날짜를 사용.
- allocation 합계 invariant 위반.
- 사용자 간 설정/ledger/briefing 교차 노출.
- p95 warm rerun 20% 초과 악화 또는 provider rate-limit 급증.
- mobile page overflow 또는 axe critical/serious 발생.

### 12.3 rollback 동작

- panel/feature flag off.
- adapter를 empty/error 상태로 전환.
- compatibility wrapper를 old implementation으로 전환.
- DB write 중지 후 migration 전 backup으로 read-only 복구.
- 관련 PR만 되돌리고 다른 작업자의 변경은 건드리지 않는다.
- 데이터가 없다는 이유로 mock을 production에 켜지 않는다.

## 13. 완료 정의

- 9개 탭과 기존 주요 기능이 유지된다.
- Python 3.11.8 / Streamlit 1.58에서 전체 suite 통과.
- 모든 신규 값에 source/date/availability/unit/quality가 있다.
- 운영 모드 mock 숫자 0.
- 신호 성과는 PIT horizon으로 재현 가능하다.
- 리스크 설정과 영속 데이터가 사용자 범위에서 격리된다.
- 백테스트는 실제 point-in-time 데이터가 없으면 숫자를 만들지 않는다.
- automatic order execution endpoint/function/UI가 없다.
- desktop/mobile, 한국어, 한국 시장 색, 접근성 gate를 통과한다.
- 각 단계의 flag·DB·코드 rollback이 검증됐다.
