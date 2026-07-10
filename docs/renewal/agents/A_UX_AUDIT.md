# A. UX Audit

## 1. 범위와 판정

범위는 기존 9개 탭 label/기능의 정보 구조, 사용자 흐름, 한국어 가독성, 상태 표현, desktop/mobile 사용성이다. 최신 코드는 실제 `st.tabs` 대신 9개 label의 segmented single-view router를 사용한다. 프로덕션 UI를 실행한 브라우저 검증은 이번 세션에서 수행하지 못했고, `app.py`, theme/CSS, UI tests와 기존 screenshot 기록을 정적으로 감사했다.

공통 기준선:

- Python 3.11.8
- Streamlit 1.58.x
- 193 tests pass 이상
- 9개 탭 유지
- 한국어 우선, 상승 빨강/하락 파랑, warning/error는 severity 색
- 주문 실행 없음

UX 정적 감사에서 독립적인 `Critical` 시각 결함을 단정할 증거는 없었다. 다만 `신호 성과` 실행 오류, mock/backtest, 사용자 격리는 다른 감사의 `Critical`이며 UI에서도 차단 상태로 표현해야 한다.

## 2. 9개 탭 UX inventory

| 탭 | 사용자 목표 | 현재 강점 | 주 마찰 | 조치 |
|---|---|---|---|---|
| 대시보드 | 오늘의 시장·위험·후보를 빠르게 판단 | 시장 카드, action console, risk-first 순서 | 모듈 수가 매우 많고 empty 패널이 연속될 수 있음 | `ENRICH` |
| 포트폴리오 | 보유 위험·손절·집중도 검토 | CSV 입력과 구체적 손실/청산 표 | 입력 오류와 계산 제한이 표 가까이에 충분히 연결되지 않음 | `FIX` |
| 종목 | 한 종목의 action/risk/execution/exit 검토 | 검토 흐름이 한 화면에 연결됨 | Dashboard 카드 선택 후 상세 탭 이동 맥락이 약함 | `ENRICH` |
| 알파 후보 탐색 | 시장 scan과 watchlist 편입 | 수동 실행으로 초기 부하 방지 | 긴 scan의 진행률·취소·유니버스 설명 부족 | `ENRICH` |
| 공시 | 관심종목 리스크 이벤트 검색 | form 기반 검색, 원문 링크, severity | source/fallback/receipt 시각을 카드 가까이 더 명확히 표시해야 함 | `ENRICH` |
| 매크로 | 핵심 지표와 해석 확인 | 간결한 ECOS 카드 | Dashboard와 거의 같은 내용, 상세 drilldown 부족 | `ENRICH` |
| 브리핑 | 검증된 요약 생성 | 버튼 실행, schema/banned phrase 검증 | 오류·저장 경로 노출, 생성 quota/상태 안내 부족 | `FIX` |
| 신호 성과 | 저장 신호의 검증 상태 확인 | kill switch와 표본 수 | UI-data contract 오류 가능, horizon 성숙도 표현 없음 | `FIX` |
| 설정 | 리스크·연결 상태 관리 | key 값이 아닌 연결 상태만 표시 | 실제 편집은 sidebar, Settings는 표라서 mental model 분리 | `RELOCATE_WITH_ALIAS` |

## 3. 보존 대상

### A-P01. 9개 화면 label/function과 공통 sidebar

- **분류:** `PRESERVE`; navigation widget 자체는 승인 전 `FIX` 검토
- 9개 기존 이름·순서·renderer 기능을 유지한다.
- 현재 segmented router의 `view` slug와 query alias를 유지한다.
- 관심종목, 포트폴리오 CSV, 리스크 입력, 새로고침을 유지한다.
- 기존 widget key와 selected stock session state를 유지한다.

### A-P02. 한국형 투자 UI 규칙

- **분류:** `PRESERVE`
- 한국어 labels, 표/경고/empty 상태를 유지한다.
- 수익·상승·순매수는 빨강, 손실·하락·순매도는 파랑을 유지한다.
- stale/error/high risk에는 방향 색을 사용하지 않는다.
- 색만으로 의미를 전달하지 않고 부호·라벨·badge text를 유지한다.

### A-P03. risk-first와 review-only 언어

- **분류:** `PRESERVE`
- action console, risk cockpit, execution/exit review 흐름을 유지한다.
- `검토 후보`, `관찰`, `리스크 관리 우선`, `리밸런싱 후보`를 사용한다.
- automatic order CTA를 추가하지 않는다.

## 4. High findings

### A-H00. 실제 tab widget이 segmented control로 변경됨

- **분류:** `FIX` 또는 승인된 경우 `RELOCATE_WITH_ALIAS`
- lazy single-view rendering과 direct `view` query는 성능·오류 격리에 이점이 있다.
- 반면 ARIA tab semantics, 기존 tab interaction, 한 페이지 내 tab persistence가 달라졌다.
- 제품 소유자가 navigation 변경을 승인하고 keyboard/screen reader/back/refresh를 검증하거나, 실제 tabs를 복원해야 한다.

### A-H01. 첫 화면의 인지 부하

- **분류:** `ENRICH`
- 기관 패널 10개, executive report, portfolio intelligence, Korea OS, Fear/Greed, macro, stock cards, chart가 한 탭에 이어진다.
- 핵심 위험을 찾기 전에 상세 카드와 empty 상태를 많이 통과할 수 있다.

구현:

1. 첫 viewport는 시장 5개 카드, action console, Critical/High risk, source freshness로 제한한다.
2. 기관 패널 순서와 module anchor는 유지한다.
3. 미연결 패널은 높이가 고정된 compact status 행으로 표시한다.
4. 상세 표/설명은 expander 또는 동일 페이지 anchor로 점진 노출한다.
5. 다음 섹션의 일부가 viewport 아래에 보여 페이지 연속성을 알 수 있게 한다.

Acceptance:

- desktop 1440x1000에서 핵심 시장·risk·freshness가 첫 viewport 안에 있다.
- 모듈 title/id는 모두 DOM에 존재한다.
- 390px에서 module title/badge가 겹치지 않는다.

### A-H02. 운영 모드의 연속 empty panel

- **분류:** `ENRICH`
- valuation/fundamental/flow/forward/optimizer가 실제 adapter 없이 상세 empty shell을 각각 렌더할 수 있다.

구현:

- `연결됨`, `부분 연결`, `어댑터 미연결`, `데이터 필요`, `업데이트 필요`를 compact 상태로 통일한다.
- planned는 초록/정상처럼 보이지 않게 한다.
- 값 영역은 N/A로 두고 exact-looking placeholder를 만들지 않는다.
- Data Trust에서 해당 source 행으로 이동하는 링크를 제공한다.

### A-H03. 종목 선택 후 cross-view continuity

- **분류:** `ENRICH`
- `view` query router가 생겼지만 Dashboard 카드가 selected code를 바꾼 뒤 종목 상세 화면으로 전환되는지는 별도 계약이 필요하다.
- Korea context와 일반 selected stock이 병렬 상태로 존재한다.

구현:

- selected stock을 공통 context에서 한 번 표시한다.
- `종목 상세에서 검토` 명령은 query alias를 설정하고 현재 9-view router 안에서 안전하게 연결한다.
- segmented router를 승인하면 `view=stocks`와 selected code를 함께 갱신한다. tabs를 복원하면 자동 이동을 가장하지 말고 명시적 안내/링크를 사용한다.
- back/refresh 후에도 허용된 query key만 복원한다.

### A-H04. 신호·백테스트의 상태 언어가 더 엄격해야 함

- **분류:** `FIX`
- 성숙하지 않은 20D/60D outcome은 실패나 0%가 아니라 `기간 미도달`이어야 한다.
- backtest engine은 current score 입력에 대해 이미 `validation_unavailable`과 N/A를 반환한다. UI도 이를 `룰 기반 추정 성과`가 아니라 `검증 불가/역사 데이터 필요`로 그대로 표시한다.
- 실제 PIT 검증 전 probability/expected return은 `계산 불가` 또는 `휴리스틱`으로 표시한다.

### A-H05. 핵심 사용자 오류가 내부 문구와 섞임

- **분류:** `FIX`
- API raw error, 서버 path, 내부 enum/영문 sentence가 사용자 상태로 새어 나올 수 있다.

구현:

- 오류 UI는 `무엇을 표시하지 못했는가`, `판단 제한`, `다음 검토 행동`, correlation id 순서로 통일한다.
- provider/표준 약어를 제외한 설명은 한국어 dictionary를 사용한다.
- 파일 시스템 절대 경로는 표시하지 않는다.

## 5. Medium findings

### A-M01. Settings와 sidebar의 역할 중복

- **분류:** `RELOCATE_WITH_ALIAS`
- Settings를 canonical 편집/상태 화면으로 만들고 sidebar는 빠른 조정 alias로 둔다.
- 두 곳은 동일 session state를 사용해 값 차이를 만들지 않는다.

### A-M02. Macro 탭의 고유 가치 부족

- **분류:** `ENRICH`
- Dashboard에는 1줄 summary, Macro 탭에는 release date, frequency, unit, history, source detail을 제공한다.
- 같은 ECOS fetch 결과를 재사용한다.

### A-M03. 긴 scan의 제어감 부족

- **분류:** `ENRICH`
- 대상 universe/정렬 기준, 완료/전체, skip/error 수를 표시한다.
- chunk 단위 progress와 cancel을 제공한다.
- scan 버튼은 중복 실행을 막고 마지막 완료 시각을 표시한다.

### A-M04. custom HTML semantic hierarchy

- **분류:** `ENRICH`
- section title을 시각적 `<div>`에만 의존하지 말고 semantic heading/landmark와 연결한다.
- table caption, header scope, chart summary를 추가한다.
- badge/작은 source text는 200% zoom에서도 읽을 수 있어야 한다.

## 6. 목표 정보 구조

```text
공통 sidebar
  관심종목 / 보유 입력 / 빠른 리스크 조정 / 새로고침

대시보드
  시장 snapshot
  action console
  Critical/High risk + Data Trust freshness
  기관 모듈 compact index
  연결된 모듈 detail
  기존 portfolio intelligence / Korea OS / 차트

포트폴리오
  입력 validation + reconciliation
  risk/cash/concentration
  holding/exit detail

종목
  selected context
  action -> risk -> execution -> exit -> chart

나머지 6탭
  기존 역할 유지, 고유 detail 강화
```

## 7. 테스트 계획

필수 자동 검증:

- 9개 view label/order와 `view` slug assertion. 실제 tabs를 선택하면 tab role/selected state도 검증.
- 1440/900/390 screenshot diff.
- 390px `scrollWidth == clientWidth`.
- 200% zoom에서 text/button/card overlap 0.
- keyboard-only tab/form/button/expander/link 이동.
- axe critical/serious 0.
- 한국어 localization, 한국 시장 색, dark readability 기존 audit.
- `SHOW_MOCK_DATA=false`에서 mock 수치/후보/backtest 문구 0.
- empty/stale/error/planned 상태 snapshot.

수동 시나리오:

1. 잘못된 종목코드와 잘못된 CSV.
2. 빈 포트폴리오와 실제 포트폴리오.
3. provider key 없음/오류/stale/fallback.
4. Alpha scan 시작/취소/완료.
5. Disclosure 검색/원문 링크.
6. Briefing 생성 실패/검증 실패/성공.
7. Signal empty/부분 horizon/kill switch.

## 8. Rollback

- Dashboard 재배치는 `ENABLE_RENEWAL_DASHBOARD_LAYOUT` flag 뒤에서 진행한다.
- flag off 시 기존 section 순서를 복원한다.
- module title/id, tab label, widget key, query alias는 rollback 중에도 유지한다.
- Settings 이동은 sidebar alias가 검증된 뒤에만 canonical로 승격한다.
- mobile overflow, tab 누락, 한국어/color audit 실패가 하나라도 생기면 해당 layout PR만 rollback한다.
- 데이터 오류를 숨기기 위해 mock을 켜는 rollback은 금지한다.

## 9. 완료 조건

- 기존 9개 탭과 기능이 보존된다.
- 첫 viewport에서 시장·핵심 risk·freshness를 찾을 수 있다.
- planned/empty가 실제 데이터처럼 보이지 않는다.
- 모든 주요 흐름이 keyboard와 mobile에서 완료 가능하다.
- 193 기준선 이상 전체 테스트와 browser/a11y gate를 통과한다.
