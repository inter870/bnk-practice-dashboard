# F. Test, Security And Accessibility Audit

## 1. 범위와 실행 제한

범위는 테스트 전략, CI/release gate, 비밀값·외부 호출·영속 데이터 보안, HTML/link 안전, keyboard/screen reader/mobile 접근성이다.

기준선:

- Python 3.11.8
- Streamlit 1.58.x
- **193 tests pass**
- 기존 compile/unit 명령

현재 작업 스냅샷에는 signal PIT 4개, portfolio context 10개, backtest integrity 8개와 확장된 optimizer 테스트를 포함해 216개 test method가 정적으로 발견됐다. 이번 셸의 `py -3.11`은 설치된 interpreter를 찾지 못해 실행하지 못했다. 따라서 216은 pass 결과가 아니며, 구현 환경에서 전체 실행해야 한다.

## 2. 테스트 inventory

| 영역 | 정적 수 | 성격 |
|---|---:|---|
| 기관 패널·Data Trust·Source | 87 | 계산, mock/stale/empty, PIT, HTML fragment |
| Korea engine·UI·색·가독성 | 62 | pure engine, label/color, CSS source audit |
| Portfolio analytics/UI/context | 27 | 계산, canonical context와 source-text 기반 UI 구조 |
| Core/discovery/execution/exit/signal | 32 | core unit 28 + 신규 PIT signal 4 |
| Backtest integrity | 8 | synthetic 차단, historical universe/PIT/cost/precision gate |
| 합계 | 216 | 정적 발견, 실행 미검증 |

강점:

- financial pure function coverage가 넓다.
- DART available-at, high-risk override, mock/stale/planned 상태가 테스트된다.
- 한국어 labels, 한국 시장 색, dark UI readability 정적 audit가 있다.
- SQLite는 tempfile unit test를 사용한다.

간극:

- 9개 segmented view/router AppTest/E2E가 없다.
- browser screenshot/axe가 CI에 없다.
- multi-session isolation/performance/provider contract test가 없다.
- CSS/HTML source substring test는 실제 DOM/render 회귀를 완전히 잡지 못한다.

## 3. 보존 대상

### F-P01. secret loading boundary

- **분류:** `PRESERVE`
- API key는 `src/config/env.py`를 통해 읽는다.
- file-based env가 deployment env를 override하지 않는다.
- UI에는 key 값이 아니라 presence/status만 전달한다.
- `.env*`, Streamlit secrets, data, briefing, DB/log가 gitignore 대상이다.

### F-P02. transport와 SQL 기본 안전

- **분류:** `PRESERVE`
- TLS verification을 끄지 않는다.
- HTTP timeout을 유지한다.
- SQLite parameter binding을 유지한다.
- Docker는 non-root user로 실행한다.

### F-P03. 접근성 기반 자산

- **분류:** `PRESERVE`
- focus ring, reduced motion, responsive overflow CSS를 유지한다.
- 중요한 상태의 text/badge를 유지한다.
- 한국어/color/readability audit를 삭제하지 않는다.

## 4. Critical findings

### F-C01. 공개 배포에서 인증·사용자 격리 없는 write surface

- **분류:** `FIX`
- signal ledger와 briefing persistence가 server-wide다.
- Render/Procfile은 외부 address로 서비스하지만 앱 수준 auth/tenant가 없다.
- LLM 생성에도 사용자 quota/rate limit이 없다.

위험:

- cross-user signal visibility/update.
- 같은 날짜 briefing overwrite.
- server API quota abuse.
- audit/ownership 부재.

수정:

- public profile write/LLM default-off.
- private profile auth + tenant scope + quota.
- external access control 의존 시 배포 preflight로 실제 차단을 검증.
- owner/tenant 없는 기존 row는 admin-only legacy namespace.

### F-C02. multi-session global risk state

- **분류:** `FIX`
- module-level mutable risk settings가 사용자별 계산을 오염시킬 수 있다.
- 테스트는 두 Streamlit session을 동시에 만들어 isolation을 검증해야 한다.

## 5. High security findings

### F-H01. 사용자 오류 redaction 불일치

- **분류:** `FIX`
- 일부 provider는 sanitized error를 사용하지만 OpenAI/KIS/file path는 raw 문구가 UI에 전달될 수 있다.
- 서버 절대 briefing path가 표시된다.

수정:

- 중앙 redactor.
- user-safe status + correlation id.
- log에도 secret pattern masking.
- absolute path/response body/headers를 UI에 출력하지 않음.

### F-H02. external URL scheme/host validation

- **분류:** `FIX`
- HTML escape는 attribute injection을 줄이지만 `javascript:` 같은 scheme 자체를 막지 않는다.
- `safe_external_url()`을 모든 동적 link에 공통 적용한다.

Gate:

- `https`만 허용.
- DART 등 provider별 host allowlist.
- empty/invalid URL은 link를 렌더하지 않음.

### F-H03. `unsafe_allow_html` surface와 static-only 검증

- **분류:** `ENRICH`
- custom HTML이 많고 dynamic text 대부분은 escape되지만 모든 sink를 자동 추적하지 않는다.

수정:

- safe HTML builder/helper로 dynamic text/url/class/token을 분리.
- class/style 값은 allowlist.
- stored/reflected XSS fixture를 browser에서 검증.
- CSP/Streamlit 제약은 runbook에 기록.

### F-H04. dependency/supply-chain reproducibility

- **분류:** `ENRICH`
- Python/Streamlit 외 package는 하한 범위 중심이고 hash lock/SBOM이 없다.

수정:

- tested constraints lock.
- dependency vulnerability scan과 SBOM.
- scheduled upgrade PR에서 전체 UI/data test 실행.
- base image digest 검토.

### F-H05. write/LLM abuse controls

- **분류:** `FIX`
- action 버튼에 CSRF보다 더 직접적인 문제인 auth/quota/idempotency가 없다.

수정:

- authenticated principal.
- cooldown/rate limit/daily quota.
- idempotency key와 request size limit.
- timeout/cancel과 safe retry.
- user input/portfolio raw values를 log하지 않음.

## 6. High test findings

### F-H06. renderer integration coverage 없음

- **분류:** `ENRICH`
- helper tests만으로는 app wiring을 보장하지 못한다. 현재 signal PIT wiring은 정적으로 확인됐지만 실행 AppTest가 없다.

추가:

- Streamlit AppTest로 9개 view/router load.
- portfolio save/validate.
- discovery manual trigger.
- disclosure form.
- briefing disabled/failure/success fake.
- signal save/update/list.

### F-H07. browser·performance regression 없음

- **분류:** `ENRICH`
- 기존 문서에 수동 browser 확인 기록은 있으나 지속 CI가 아니다.

추가:

- Playwright screenshot/console/network assertions.
- 1440/900/390.
- cold/warm rerun timing과 provider call budget.
- 50 rerun memory/figure close check.

### F-H08. data contract integration fixture 부족

- **분류:** `ENRICH`
- provider parser -> normalized metadata -> panel -> UI 전체 chain을 fake response로 검증해야 한다.

추가:

- KIS/Naver/FDR/OpenDART/ECOS success/error/malformed/stale.
- key presence only, raw key absence assertion.
- instrument identity와 unit.

## 7. High accessibility findings

### F-H09. 실제 DOM 접근성 검사가 없음

- **분류:** `ENRICH`
- CSS token/문자열은 focus와 contrast 의도를 확인하지만 accessible name, role, focus order를 보장하지 않는다.

추가:

- axe critical/serious 0.
- keyboard-only 9개 view selector와 controls. 실제 tabs를 택하면 tab key semantics도 검증.
- focus visible/return after rerun/modal/expander.
- screen reader landmark/heading/name.

### F-H10. chart와 custom table 대체 표현

- **분류:** `ENRICH`
- matplotlib chart에 일관된 alt/long description/data table 계약이 없다.
- custom table의 caption/scope/semantic role가 불완전할 수 있다.

수정:

- chart title, summary, as-of, unit, key extrema/return을 text로 제공.
- underlying accessible table 또는 다운로드가 아닌 화면 내 summary.
- table caption, `th scope`, empty cell label.

## 8. Medium findings

### F-M01. static substring test의 취약성

- **분류:** `ENRICH`
- source slice 길이/문구 변경에 민감하고 실제 render를 보지 않는다.
- 중요한 것은 semantic component test로 옮기고 static audit는 policy guard로 유지한다.

### F-M02. coverage와 mutation signal 부족

- **분류:** `ENRICH`
- 단순 test count는 branch/risk gate coverage를 뜻하지 않는다.
- coverage report와 핵심 계산 mutation test를 추가한다.

### F-M03. audit log와 privacy

- **분류:** `ENRICH`
- security event에는 principal/action/status/correlation id만 기록한다.
- portfolio rows, API response, prompt 전문, key/token은 기록하지 않는다.
- retention/redaction/access를 정의한다.

### F-M04. timestamp 접근성/현지화

- **분류:** `FIX`
- 사용자 UI는 Asia/Seoul `YYYY.MM.DD HH:mm`.
- machine/API에는 timezone 포함 ISO.
- screen reader가 숫자열을 읽을 수 있도록 주변 한국어 label을 제공한다.

## 9. 목표 test pyramid

| 층 | 목적 | 예시 |
|---|---|---|
| Pure unit | 계산·format·selector | risk, factor, PIT, metadata |
| Contract | provider/DB/schema | fake HTTP, SQLite migration |
| Component | renderer/view model | empty/stale/error/mock HTML/DOM |
| AppTest | Streamlit session workflow | 9개 view/router, state, buttons, two sessions |
| Browser E2E | 실제 DOM/layout/a11y | Playwright + axe + screenshot |
| Nonfunctional | perf/security/reliability | timing, rate limit, XSS, secret scan |

## 10. CI jobs

### 10.1 Fast gate

```powershell
py -3.11 -m compileall app.py src tests
py -3.11 -m unittest discover tests
```

- 193보다 적은 test discovery는 실패.
- 현재 216이 유지되면 216 전부 pass.

### 10.2 Policy gate

- localization audit.
- Korean market color audit.
- Data Trust display audit.
- risk alert Korean UI audit.
- dark readability/visibility audit.
- secret and unsafe URL scan.

### 10.3 Integration gate

- AppTest 9개 view/router.
- provider/DB contract.
- two-session isolation.
- public/private profile.

### 10.4 Browser gate

- desktop/tablet/mobile screenshot.
- console `Traceback`/`StreamlitAPIException` 0.
- horizontal overflow 0.
- axe critical/serious 0.
- keyboard scenario pass.

### 10.5 Release gate

- production profile mock 0.
- shared unauthenticated write 0.
- source metadata completeness 100%.
- PIT leakage sentinel 0.
- performance budget pass.

## 11. Security test cases

- secret-like value가 error/response/path에 포함돼도 UI/log에서 redacted.
- missing key는 source-specific 상태만 표시.
- malformed provider body가 raw dump되지 않음.
- `javascript:`, `data:`, protocol-relative URL link 차단.
- HTML/script payload가 text로 escape.
- unauthorized signal/briefing write 차단.
- tenant A가 tenant B row 조회/수정 불가.
- rate limit과 idempotency.
- SQLite path가 workspace data dir 밖으로 나가지 않음.
- file name은 server-generated, user path traversal 불가.

## 12. Accessibility test cases

- Tab/Shift+Tab focus order와 visible focus.
- 9개 view accessible name과 selected state. 실제 tabs를 택하면 tab role/tabpanel association.
- form label/description/error association.
- metric의 label/value/unit/source 읽기 순서.
- custom link/button keyboard activation.
- table caption/header association.
- chart text summary.
- 200% zoom/reflow.
- 390px portrait와 900px landscape.
- reduced motion.
- 색 없이도 up/down/risk/stale 구분.

## 13. Rollback

- test 실패 시 기준선을 낮추거나 test를 삭제하지 않는다.
- 신규 browser/a11y gate가 기존 결함을 발견하면 issue를 명시하고 production 승격을 보류한다.
- public write/LLM flag는 문제가 생기면 즉시 off.
- dependency upgrade는 constraints를 이전 검증 버전으로 되돌린다.
- DB migration 실패 시 write-off + backup read-only.
- UI/a11y 변경 rollback은 해당 scoped CSS/component만 대상으로 하고 탭/기능을 제거하지 않는다.
- 보안 redaction, TLS verification, secret gitignore를 rollback하지 않는다.

## 14. 완료 조건

- Python 3.11.8/Streamlit 1.58에서 전체 suite 통과.
- test discovery가 193 미만으로 내려가지 않는다.
- 9개 view/router AppTest와 browser smoke가 지속 실행된다.
- public profile에 unauthenticated persistence/LLM write가 없다.
- secret/raw path/unsafe URL/XSS finding 0.
- axe critical/serious 0, keyboard/mobile/zoom pass.
- mock/PIT/source metadata release gate가 자동화된다.
