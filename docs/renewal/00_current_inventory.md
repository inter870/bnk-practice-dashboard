# Renewal Current Inventory

> **Final verification update (2026-07-10):** Python 3.11.8 was located and the final worktree passed `compileall`, three consecutive runs of all 255 tests, Streamlit health, all six UI audits, and nine-view browser checks. Earlier statements below that Python was unavailable describe the initial documentation pass only. Final evidence is in `docs/review_fix/04_test_evidence_after_fix.md`.

## 1. 문서 목적

이 문서는 2026-07-10 작업 스냅샷을 기준으로 기존 Streamlit 금융 대시보드의 보존 계약을 고정한다. 갱신 작업은 대시보드를 다시 만들거나 9개 탭을 교체하는 프로젝트가 아니다. 현재 기능을 식별하고, 이후 변경을 `PRESERVE`, `ENRICH`, `RELOCATE_WITH_ALIAS`, `FIX` 중 하나로 명시하기 위한 기준 문서다.

비밀값은 조사 대상에서 제외했다. 이 문서는 환경 변수 이름과 설정 여부 처리 방식만 다루며, 키 값·토큰·계좌 정보는 포함하지 않는다.

## 2. 기준선과 조사 상태

| 항목 | 기준 | 현재 확인 방식 |
|---|---|---|
| 회귀 기준선 | **193 tests pass** | 요청에서 고정한 인수 기준선 |
| 작업 스냅샷 테스트 수 | 216개 `test_*` 메서드 정적 발견 | 동시 작업으로 signal PIT, portfolio context, backtest integrity 테스트가 추가됨. 실행 통과를 뜻하지 않음 |
| Streamlit | **1.58** | `requirements.txt`: `streamlit>=1.58,<1.59` |
| Python | **3.11.8** | `runtime.txt`, `Dockerfile` |
| 테스트 프레임워크 | `unittest` | `tests/` 35개 파일 |
| 앱 진입점 | `app.py` | 약 9.2K LOC, 약 397KB인 단일 Streamlit 진입점 |
| 차트 | matplotlib | `st.pyplot` 기반 |
| 저장소 | SQLite + 로컬 파일 | 신호 원장과 생성 브리핑 |

이번 문서 작업 환경에서는 `py -3.11`이 설치된 인터프리터를 찾지 못해 compile/test를 다시 실행하지 못했다. 따라서 **193 pass는 인수 기준선**, **216은 현재 정적 발견 수**, **이번 세션 실행 결과는 미검증**으로 구분한다.

## 3. 변경 분류 사전

| 분류 | 의미 | 적용 원칙 |
|---|---|---|
| `PRESERVE` | 사용자 계약과 검증된 동작을 그대로 유지 | 탭 이름·순서, 안전 문구, 중앙 비밀값 로딩, 한국 시장 색 규칙 등 |
| `ENRICH` | 기존 경로를 유지하면서 정보·상태·테스트·데이터를 보강 | 출처 메타데이터, 빈 상태, 상세 설명, 실데이터 어댑터 등 |
| `RELOCATE_WITH_ALIAS` | 코드를 옮기되 기존 함수·import·widget key·query key에 호환 alias를 둠 | `app.py` 모듈화, 설정 위치 정리, 서비스 계층 분리 |
| `FIX` | 잘못되거나 안전하지 않은 동작을 교정 | 계약 불일치, 전역 상태 공유, PIT 위반, 입력 검증 누락 등 |

## 4. 전역 UI 셸

### 4.1 공통 헤더와 사이드바

- 브랜드 헤더: `Stance Stock Strategy`와 한국어 설명.
- 관심종목 입력: 줄바꿈/쉼표 종목코드, 최대 15개.
- 포트폴리오 입력: 총자산, 현금, `code,qty,avg_price,sector` CSV.
- 리스크 입력: 1회 거래 최대 손실, 단일 종목 최대 비중, 거래 비용, 슬리피지.
- 새로고침: 세션의 `refresh_token`을 증가시켜 캐시 키를 갱신.
- 공통 선택 상태: `manual_active_code`, `active_code`, Korea context query parameters.
- 상위 화면 선택: 9개 기존 탭 label을 `st.segmented_control`에 표시하고 `view` query parameter로 현재 화면을 복원한다.
- 현재 router는 선택한 renderer 하나만 `render_view_safely()`로 실행한다.

보존 계약:

- 사이드바 입력과 widget key를 `PRESERVE`한다.
- 리스크 값의 저장 위치는 세션 격리를 위해 `FIX`할 수 있으나 보이는 의미와 기본값은 유지한다.
- 종목 선택 연결은 `ENRICH`하되 기존 관심종목 입력을 대체하지 않는다.

### 4.2 상위 9개 화면 inventory와 기존 탭 계약

현재 코드에는 `st.tabs`가 아니라 9개 label의 segmented router가 있다. 따라서 **기능·이름·순서는 보존됐지만 실제 tab widget/ARIA tab semantics는 변경된 상태**다. 제품 계약이 실제 tabs를 요구한다면 `FIX`, lazy 단일-view navigation을 승인한다면 기존 tab label/function/query alias를 `PRESERVE`해야 한다.

| 순서 | 현재 탭 | 핵심 사용자 작업 | 주요 구현/데이터 | 분류 |
|---:|---|---|---|---|
| 1 | 대시보드 | 시장·리스크·후보·출처를 종합 검토 | `render_dashboard_section`, 시장 snapshot, 10개 기관 패널, 포트폴리오 인텔리전스, Korea Alpha, Fear/Greed, ECOS, 종목 비교/차트 | `PRESERVE` + `ENRICH` |
| 2 | 포트폴리오 | 수동 보유 CSV의 평가금액·손절·섹터 집중·청산 우선순위 검토 | `render_portfolio_section`, `src/portfolio`, `src/exits` | `PRESERVE` + `FIX` |
| 3 | 종목 | 관심종목 랭킹, 상세 리스크, 실행 비용, 청산 계획, 캔들 검토 | `render_stocks_section`, `build_watchlist_insights`, execution/exit engine | `PRESERVE` + `ENRICH` |
| 4 | 알파 후보 탐색 | KRX 유니버스를 수동 스캔하고 후보를 관심종목에 추가 | `src/discovery`, FDR 가격 이력, 수동 실행 상태 | `PRESERVE` + `FIX` |
| 5 | 공시 | 관심종목/전체 DART 공시 검색과 규칙 기반 심각도 검토 | OpenDART 또는 DART 공개 페이지 fallback, `render_disclosure_section` | `PRESERVE` + `ENRICH` |
| 6 | 매크로 | ECOS 기준금리·GDP·CPI·M2·대외수지 확인 | `render_ecos_cards`, ECOS key statistics | `PRESERVE` + `ENRICH` |
| 7 | 브리핑 | 구조화 컨텍스트로 GPT 시장 브리핑 생성·검증 | OpenAI Responses 호출, prompt/schema 자산, 로컬 `briefings/` | `PRESERVE` + `FIX` |
| 8 | 신호 성과 | 현재 신호 저장, 사후성과 갱신, kill switch 확인 | `src/monitoring/signal_ledger.py`, SQLite | `PRESERVE` + `FIX` |
| 9 | 설정 | API 연결 상태와 리스크 기본값 확인 | `render_settings_section`, 중앙 환경 설정, 현재는 주로 읽기 전용 표 | `PRESERVE` + `RELOCATE_WITH_ALIAS` |

9개 이름, 순서, 개수와 renderer 기능은 명시적 제품 결정 전까지 `PRESERVE`한다. segmented router의 승인 여부를 결정하기 전에는 이를 새로운 영구 navigation 계약으로 간주하지 않는다.

## 5. 대시보드 상세 inventory

### 5.1 상단 의사결정 흐름

1. 기준일과 최종 업데이트.
2. KOSPI, KOSDAQ, USD/KRW, 미국 10년물, 한국 3년물 카드.
3. 시장 국면과 허용/금지 행동을 보여주는 action console.
4. 기관 패널 스택.
5. executive decision report와 포트폴리오 인텔리전스.
6. Korea Alpha Engine / Korea Investment OS v2.
7. 핵심 판단 3요소, 고도화 모듈 요약.
8. Fear/Greed, ECOS, 주요 종목 카드, 수익률 비교, 캔들·거래량, 데이터 품질.

### 5.2 기관 패널 10개

| 순서 | 모듈 | 현재 연결 | 운영 모드 상태 | flag/rollback |
|---:|---|---|---|---|
| 1 | Portfolio Risk Cockpit | 사이드바 보유종목, snapshot, portfolio service | 실제 입력이 없으면 empty. `SHOW_MOCK_DATA=true`일 때만 demo | 전용 flag 없음 |
| 2 | Data Trust & Source Panel | snapshot, 보유 입력 유무, 키 presence boolean | source/adapter/stale/accuracy 상태 표시 | `STANCE_ENABLE_DATA_TRUST` |
| 3 | Market Regime & Macro Radar | 시장 snapshot, 선택적 mock macro | 실데이터가 부족하면 empty/partial | `STANCE_ENABLE_MARKET_REGIME_RADAR` |
| 4 | KRW / Rates / FX | snapshot과 보유종목 | 환율·금리 및 포트폴리오 민감도, 부족 입력은 N/A | `STANCE_ENABLE_KRW_RATES_FX` |
| 5 | Valuation & Relative Cheapness | 패널 엔진만 연결 | 실제 valuation adapter 미연결 시 empty | `STANCE_ENABLE_VALUATION_PANEL` |
| 6 | Fundamental Quality | 패널 엔진만 연결 | OpenDART financial input 미연결 시 empty | `STANCE_ENABLE_FUNDAMENTAL_QUALITY` |
| 7 | DART Disclosure Catalyst | 패널 엔진만 연결 | 기관 패널에는 실제 공시 입력이 아직 전달되지 않아 empty | `STANCE_ENABLE_DART_CATALYSTS` |
| 8 | Smart Money / Short Pressure | 패널 엔진만 연결 | KRX 수급·공매도 adapter 미연결 시 empty | `STANCE_ENABLE_FLOW_SHORT_PRESSURE` |
| 9 | Forward Alpha Ranking | 패널 엔진만 연결 | upstream feature가 없어 empty | `STANCE_ENABLE_FORWARD_ALPHA_RANKING` |
| 10 | Portfolio Optimizer & Alert Center | 패널 엔진만 연결 | 실제 보유·alpha state가 전달되지 않아 empty | `STANCE_ENABLE_PORTFOLIO_OPTIMIZER` |

`render.yaml`은 `SHOW_MOCK_DATA=false`를 기본으로 둔다. Korea Alpha 화면도 운영 모드에서 mock 가격·재무·수급·백테스트를 표시하지 않고 데이터 필요 상태로 종료한다. 이 경계는 `PRESERVE` 대상이다.

## 6. 도메인 모듈 inventory

| 경로 | 책임 | 상태/주의 |
|---|---|---|
| `src/config/env.py` | 환경·Streamlit secrets·파일 기반 설정 로딩, alias, 문구 sanitization | 비밀값 단일 진입점. `PRESERVE` |
| `src/common.py` | OHLCV, 숫자, 수익률 공통 함수 | 순수 함수 중심 |
| `src/portfolio/` | 보유 모델, canonical context, mock/service, 배분·성과·집중도 분석 | context/reconciliation/history coverage가 추가됐으나 Portfolio 탭은 부분적으로 legacy 계산 유지 |
| `src/discovery/` | KRX listing 정제와 가격 기반 후보 스캔 | 현재 listing의 앞 N개 순차 스캔 |
| `src/execution/` | 유동성·슬리피지·시장충격 기반 실행 검토 | 주문 API 없음 |
| `src/exits/` | hard/trailing/time stop과 목표가 검토 | 검토 계획이며 주문 실행 없음 |
| `src/monitoring/` | SQLite 신호/성과 원장, PIT 1/5/20/60D outcome, kill switch | UI PIT 연결 완료; 영속 owner scope와 immutable level 보강 필요 |
| `src/korea_equity/` | mock 기반 팩터, 예측, 추천, OS, PIT backtest engine | current-score synthetic 성과는 N/A로 차단; production historical adapter는 미연결 |
| `src/institutional/` | 10개 기관 패널 contracts, 계산, source registry, HTML | 계산·empty/stale/mock 상태와 단위 테스트가 풍부하나 실제 adapter wiring은 일부만 존재 |
| `src/ui/` | 한국어 labels, 한국 시장 색, 전역 theme | 한국어·색·focus 회귀 기준 |

## 7. 데이터 소스와 fallback inventory

| 범주 | 소스 | 인증 | 현재 용도 | 필수 표시 |
|---|---|---|---|---|
| 국내 가격 | KIS Open API | key 필요 | 설정 시 관심종목 현재가 우선 | broker source, timestamp, unit |
| 시장/가격 fallback | Naver Finance | key 없음 | 지수·환율·금리 공개 snapshot | 공개 snapshot, 지연/구조 변경 가능성 |
| 가격 이력/listing | FinanceDataReader | key 없음 | KRX listing, 지수·종목 history | wrapper/fallback, 기준일 |
| 공시 | OpenDART | key 필요 | 최근 공시 목록 | receipt/available 시각, URL, source |
| 공시 fallback | DART 공개 페이지 | key 없음 | API 미연결 시 최근 공시 | 공개 페이지 snapshot, official realtime 아님 |
| 매크로 | BOK ECOS | key 필요 | 핵심 지표 카드 | 항목, 주기, 단위, 기준일 |
| 심리 | alternative.me Fear & Greed | key 없음 | 시장 심리 참고 | 외부 글로벌 지표임을 명시 |
| 생성형 브리핑 | OpenAI Responses | key 필요 | 버튼 기반 브리핑 | 모델 결과 검증, 생성 시각, 안전 문구 |
| 계획 소스 | KRX/KOSIS/FRED 및 valuation/flow/short adapter | 소스별 상이 | source registry에 planned 상태 | `어댑터 미연결`/`연결 예정`, 값 생성 금지 |

기관 `DataSourceMeta`는 `source`, `as_of_date`, `available_at` 또는 `fetched_at`, `unit`, stale/fallback/quality를 표현한다. 반면 `app.py`의 legacy `Snapshot`은 `asof` 중심이므로 두 계약의 통합은 `ENRICH` 대상이다.

## 8. 저장과 세션 상태

| 저장 위치 | 내용 | 수명/범위 | 현재 위험 |
|---|---|---|---|
| `st.session_state` | 종목 선택, 입력 CSV, 새로고침, briefing 상태, discovery 실행 여부 | 브라우저 세션 | 기본 격리 수단 |
| 모듈 전역 `RISK_DEFAULTS` | 리스크·비용 기본값 | Python 프로세스 | sidebar가 직접 변경해 세션 간 공유 가능 |
| `data/signal_ledger.sqlite3` | signals/outcomes | 배포 인스턴스 공용 | 사용자/세션 열 없음, 공용 배포 시 격리 없음 |
| `briefings/briefing_YYYY-MM-DD.txt` | 생성 브리핑 | 배포 인스턴스 공용 | 같은 날짜 파일 덮어쓰기 가능 |
| `@st.cache_data` | listing, snapshot, history, disclosure, macro, scan | 프로세스 캐시 | 공개 데이터에는 유효하나 active tab과 무관하게 호출될 수 있음 |

`data/`, `briefings/`, SQLite/DB, `.env*`, Streamlit secrets는 `.gitignore`로 제외되어 있다.

## 9. 테스트 inventory

현재 정적 발견 216개를 도메인별로 묶으면 다음과 같다.

| 영역 | 정적 테스트 수 | 대표 범위 |
|---|---:|---|
| 기관 패널·source/data trust | 87 | 10개 패널, PIT DART, mock/stale/empty, source registry, risk alert UI |
| Korea engine·UI·색·가독성 | 62 | 팩터/OS, 한국어 labels, 한국 시장 색, CSS 정적 audit |
| Portfolio analytics/UI/context | 27 | 배분·수익·집중도, canonical context, 카드 구조·모바일 CSS |
| Core workflow·discovery·execution·exit·monitoring | 32 | 기존 28 + signal PIT 4 |
| Backtest integrity | 8 | synthetic 차단, historical universe gate, chronological PIT/cost/precision unavailable |
| 합계 | 216 | 실행 결과가 아닌 정적 메서드 수 |

필수 회귀 명령:

```powershell
py -3.11 -m compileall app.py src tests
py -3.11 -m unittest discover tests
```

Release gate는 기존 **193 tests pass 이상**이며, 추가된 테스트를 삭제해 숫자를 맞추면 안 된다. 현재 suite가 216개라면 216개 전부 통과해야 한다.

## 10. 절대 보존 계약

- 9개 탭의 이름·순서·주요 기능.
- 자동 주문 실행 없음.
- 검토 후보, 관찰, 리스크 관리 우선, 리밸런싱 후보 중심 문구.
- 한국어 우선 UI와 한국 시장 상승 빨강/하락 파랑 규칙.
- warning/stale/error는 방향 색이 아니라 severity 색 사용.
- mock은 `SHOW_MOCK_DATA`가 명시적으로 켜진 경우에만 표시하고 모의/데모/낮은 신뢰도를 노출.
- planned adapter는 건강한 연결처럼 보이지 않으며 값을 만들지 않음.
- DART 재무 분석은 fiscal period end가 아니라 `receipt_date`/`available_at` 사용.
- 비밀값은 `src/config/env.py`를 통해 읽고 presence만 UI에 전달.
- 기존 widget key, query key, SQLite 기존 행은 호환 경로 없이 파괴하지 않음.

## 11. inventory에서 확인된 다음 문서

- 통합 위험 및 간극: `01_risk_and_gap_analysis.md`
- 구현·테스트·rollback 순서: `02_implementation_plan.md`
- 분야별 감사: `agents/A_UX_AUDIT.md`부터 `agents/F_TEST_SECURITY_A11Y.md`
