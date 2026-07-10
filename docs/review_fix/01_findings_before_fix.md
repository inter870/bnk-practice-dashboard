# Findings Before Fix

검토 기준 커밋은 `f6b4dc7bdbadd9d884e5690e0281d3d93ed1b33b`이며, 아래 결과는 해당 기준과 현재 작업트리의 diff 및 독립 재현 스크립트를 함께 비교한 결과다.

## High

### RF-001 - 현재가 누락 시 평균매입가를 대체값으로 사용

- **Status:** VERIFIED
- **Category:** Portfolio valuation / missing data
- **File:** `src/portfolio/context.py:475-478`, `src/portfolio/service.py:31-34`
- **Symbol:** `_adapt_legacy_row`, `rowsToHoldings`
- **Baseline behavior:** 레거시 CSV는 현재가 열을 요구하지 않았다.
- **Current behavior:** 현재가를 구하지 못하면 평균매입가를 현재가로 넣고 정상 포트폴리오처럼 계산한다.
- **Reproduction:** 현재가 맵 없이 `adapt_legacy_csv_rows([{code: 005930, qty: 1, avg_price: 70000}])` 호출.
- **Expected:** 가격 누락 오류 또는 계산 불가 상태.
- **Actual:** `current_price=70000`, 정상 결과.
- **Evidence:** 재현값 `missing_price_fallback=70000.0`; 기존 테스트도 이 대체 동작을 정상으로 고정한다.
- **Impact:** 평가액, 손익, 비중, 집중도, optimizer 입력이 허위 정밀도로 계산된다.
- **Root cause:** 평균매입가와 현재가를 서로 대체 가능한 가격으로 취급했다.
- **Fix recommendation:** 가격이 없으면 해당 포트폴리오 계산을 명시적으로 차단하고 `current_price_missing`을 반환한다.
- **Required test:** 평균매입가만 있는 CSV가 정상 평가액을 만들지 않는지 검증.
- **Confidence:** High

### RF-002 - 현재 수량을 과거 전 기간에 소급해 실현 성과처럼 표시

- **Status:** VERIFIED
- **Category:** Portfolio performance / historical integrity
- **File:** `src/portfolio/context.py:848-903`, `app.py:6488-6583`, `app.py:8000-8040`
- **Symbol:** `reconstruct_portfolio_value_history`, `render_portfolio_intelligence_section`
- **Baseline behavior:** 실제 거래·스냅샷 이력 계약이 없었다.
- **Current behavior:** 현재 보유 수량을 과거 가격 전체에 고정 적용한 시계열로 CAGR, Sharpe, MDD, 벤치마크 초과수익을 계산한다.
- **Reproduction:** 현재 수량 1주와 과거 가격 100, 150을 넣으면 첫 과거 평가액도 현재 수량 기준 100으로 생성된다.
- **Expected:** 고정수량 재구성은 위험 시나리오로만 사용하고 실현 성과 지표는 계산 불가 처리.
- **Actual:** 품질 플래그가 있어도 일반 성과 계산 경로로 전달된다.
- **Evidence:** 재현값 `fixed_quantity_first_value=150.0`; `quality_flags`에는 `fixed_current_quantities`가 있으나 UI 성과 계산은 이를 차단하지 않는다.
- **Impact:** 사용자의 실제 투자 성과와 다른 CAGR/Sharpe/MDD를 운영 지표처럼 보여준다.
- **Root cause:** 위험 프록시 시계열과 실현 포트폴리오 스냅샷 시계열을 같은 계약으로 사용했다.
- **Fix recommendation:** 이력 방법론을 명시하고 고정수량 이력에서는 실현 성과 지표를 `None`으로 제한한다.
- **Required test:** 고정수량 이력은 성과 지표 입력으로 승인되지 않는지 검증.
- **Confidence:** High

### RF-003 - 의사결정 시점과 동일한 종가로 백테스트 진입

- **Status:** VERIFIED
- **Category:** Backtest / look-ahead bias
- **File:** `src/korea_equity/backtest_engine.py:457-471`, `src/korea_equity/backtest_engine.py:578-669`
- **Symbol:** `_priceAt`, `_periodPriceReturn`, `runWalkForwardBacktest`
- **Baseline behavior:** 운영 가능한 PIT 백테스트가 없었다.
- **Current behavior:** feature가 사용 가능해지는 `rebalance_at`과 정확히 같은 timestamp의 종가를 진입가로 사용한다.
- **Reproduction:** 2026-01-31 feature와 같은 날짜 종가 100, 다음 리밸런스 종가 110 입력.
- **Expected:** feature 공개 이후 첫 거래 가능 가격을 사용하거나 동일 종가만 있으면 검증 불가.
- **Actual:** `status=validated`, `gross_return=10%`.
- **Evidence:** 재현값 `same_close_backtest_status=validated`, `same_close_gross_return=0.10`.
- **Impact:** 미래정보 누수로 표본외 성과가 과대평가될 수 있다.
- **Root cause:** 경계 가격 선택 조건이 `timestamp == boundary`다.
- **Fix recommendation:** 진입은 `timestamp > max(rebalance_at, feature.available_at)`인 첫 거래 가능 가격로 강제하고 실행시각을 기록한다.
- **Required test:** 동일 종가 거부 및 다음 거래일 진입가 사용 검증.
- **Confidence:** High

### RF-004 - optimizer가 시장정보를 잃고 목표비중 잔여분을 잘못 보고

- **Status:** VERIFIED
- **Category:** Portfolio optimizer
- **File:** `src/institutional/models.py:945-967`, `src/institutional/portfolio_optimizer.py:135-200`, `src/institutional/portfolio_optimizer.py:448,493,525`
- **Symbol:** `ForwardAlphaRankRow`, `_row_cap`, `optimize_target_weights`, `build_portfolio_optimizer_alert_center`
- **Baseline behavior:** optimizer가 없었다.
- **Current behavior:** 미보유 후보의 시장을 KOSPI로 가정해 KOSDAQ 5% 한도를 우회할 수 있고, 주식 목표가 18%여도 목표현금을 고정 5%로 보고한다.
- **Reproduction:** KOSDAQ 미보유 후보와 제약 7%/5%를 넣고 소수 후보만 최적화.
- **Expected:** 후보 시장을 보존하고 주식 목표합 + 실제 목표현금 = 100%.
- **Actual:** KOSDAQ 후보 7%, 주식 18% + 보고 현금 5% = 23%.
- **Evidence:** 재현값 `unheld_kosdaq_target=0.07`, `optimizer_total=0.23`.
- **Impact:** 목표비중과 현금 계획이 실행 불가능하거나 오해를 유발한다.
- **Root cause:** alpha row 계약에 market이 없고 현금은 잔여가 아닌 최소 버퍼 상수로 저장된다.
- **Fix recommendation:** market 필드를 전달하고 미상 시장은 보수적 한도를 적용하며 잔여 전부를 목표현금으로 계산한다.
- **Required test:** KOSDAQ 한도와 `sum(stock targets)+target_cash=1` 검증.
- **Confidence:** High

### RF-005 - 현금을 제외한 분모로 종목 집중도 계산

- **Status:** VERIFIED
- **Category:** Portfolio risk
- **File:** `src/portfolio/analytics.py:295-325`, `app.py:6507`
- **Symbol:** `calculateTopHoldingWeight`, `calculateHerfindahlIndex`, `calculateConcentrationRisk`
- **Baseline behavior:** 보유종목 간 집중도만 계산했다.
- **Current behavior:** 포트폴리오 리스크 화면에서도 현금을 제외한 보유주식 합계를 분모로 사용한다.
- **Reproduction:** 주식 7만원, 현금 90만원.
- **Expected:** 전체 포트폴리오 기준 종목비중 약 7.22%.
- **Actual:** 100%.
- **Evidence:** 재현값 `cash_inclusive_actual_weight=0.0721649`, `reported_concentration=1.0`.
- **Impact:** 현금 비중이 큰 포트폴리오의 집중 위험을 크게 과장한다.
- **Root cause:** 함수가 총 포트폴리오 가치 또는 현금을 입력받지 않는다.
- **Fix recommendation:** 선택적 총자산 분모를 지원하고 화면에서 `PortfolioContext.computed_total`을 전달한다.
- **Required test:** 현금 포함 집중도 및 기존 무현금 호환 검증.
- **Confidence:** High

### RF-006 - 미보정 승률로 기대값을 산출해 Action 점수에 반영

- **Status:** VERIFIED
- **Category:** Decision score / calibration
- **File:** `app.py:5110-5124`, `app.py:5143-5230`
- **Symbol:** `expected_edge_from_plan`, `build_action_decision`
- **Baseline behavior:** 검증된 확률 계약이 없었다.
- **Current behavior:** 주도력 점수를 선형식으로 승률처럼 변환하고 기대값·신뢰도를 산출해 Action 점수에 사용한다.
- **Reproduction:** 임의 리스크 계획과 주도력 55를 입력.
- **Expected:** 검증된 out-of-sample 확률이 없으면 기대값은 계산 불가이며 점수에 가산하지 않는다.
- **Actual:** `(기대값 1.55%, 품질조정 손익비 1.11, 신뢰도 55.5)`.
- **Evidence:** 재현값 `uncalibrated_edge=(1.55, 1.11, 55.5)`.
- **Impact:** 확률처럼 보이는 미보정 휴리스틱이 종목 행동 판단을 끌어올린다.
- **Root cause:** 랭킹 점수와 확률 calibration을 혼동했다.
- **Fix recommendation:** 보정된 확률·표본수 없이는 기대값을 `None`으로 반환하고 Action 점수에서 제외한다.
- **Required test:** calibration 미제공 시 기대값/신뢰도 미산출 검증.
- **Confidence:** High

### RF-015 - Streamlit 재실행 중 KIS 시세 캐시 직렬화 실패

- **Status:** VERIFIED
- **Category:** Runtime / cache serialization
- **File:** `app.py:2501-2517`, `app.py:2995-3004`
- **Symbol:** `Snapshot`, `load_kis_stock_snapshots`
- **Current behavior:** `__main__`에 선언된 `Snapshot` 인스턴스를 `st.cache_data`가 저장하며, 코드 재실행 뒤 이전 클래스와 새 클래스의 정체성이 달라 pickle 오류가 발생한다.
- **Reproduction:** KIS가 활성화된 로컬 서버에서 `app.py` 수정 후 Streamlit rerun을 실행한다.
- **Expected:** 시세 캐시가 재실행과 무관하게 직렬화되고 화면이 계속 열린다.
- **Actual:** `PicklingError: Can't pickle <class '__main__.Snapshot'>`와 `UnserializableReturnValueError`로 앱 실행이 중단된다.
- **Impact:** KIS 사용 환경에서 개발 재실행 또는 핫 리로드 시 전체 화면이 실패한다.
- **Root cause:** 캐시 경계를 넘는 데이터 클래스가 재실행되는 `__main__` 모듈에 정의되어 있다.
- **Fix recommendation:** `Snapshot`을 안정적인 `src` 모듈로 이동하고 pickle 회귀 테스트를 추가한다.
- **Confidence:** High

## Medium

### RF-007 - 새로고침 토큰이 KIS OAuth 캐시 키에 포함

- **Status:** VERIFIED
- **Category:** Cache / rate limit
- **File:** `app.py:2909-2910`, `app.py:2936-2937`, `app.py:9134-9150`
- **Symbol:** `get_kis_access_token`
- **Current behavior:** 대시보드 새로고침 토큰이 바뀔 때마다 OAuth token 캐시가 달라진다.
- **Impact:** 짧은 시간 반복 새로고침 시 불필요한 token 발급과 rate-limit 위험.
- **Root cause:** 데이터 refresh token을 인증 token 캐시 키로 재사용했다.
- **Fix recommendation:** underscore 인수 또는 무인수 캐시로 OAuth 수명만 따르게 한다.
- **Required test:** 서로 다른 화면 refresh token이 OAuth 호출을 늘리지 않는지 검증.
- **Confidence:** High

### RF-008 - ECOS 기준일이 첫 행이며 stale 판정이 실제 관측일을 충분히 반영하지 않음

- **Status:** VERIFIED
- **Category:** Macro metadata / stale data
- **File:** `app.py:6271-6276`, `src/institutional/data_trust.py:639-676`
- **Symbol:** `render_data_trust_source_panel_section`
- **Current behavior:** 응답 첫 행의 주기를 전체 ECOS 기준일로 사용한다.
- **Impact:** 응답 정렬이 바뀌거나 빈 주기가 앞에 오면 기준일·신선도 상태가 틀릴 수 있다.
- **Root cause:** 전체 유효 관측일을 정규화하지 않고 위치 기반 행을 선택했다.
- **Fix recommendation:** 모든 유효 ECOS 주기를 파싱해 최신 관측일을 사용하고 그 기준으로 stale를 판정한다.
- **Required test:** 정렬되지 않은 ECOS 행에서 최신 유효 날짜 선택 검증.
- **Confidence:** High

### RF-009 - 조회한 OpenDART 운영 데이터가 공시 촉매·알파 모듈에 전달되지 않음

- **Status:** VERIFIED
- **Category:** Data integration
- **File:** `app.py:6268`, `app.py:6355-6364`, `app.py:6379-6388`
- **Symbol:** `render_dart_disclosure_catalyst_panel_section`, `render_forward_alpha_ranking_panel_section`
- **Current behavior:** Data Trust용 OpenDART DataFrame을 조회하지만 DART 촉매 builder는 인수 없이 호출된다.
- **Impact:** 키와 실데이터가 있어도 핵심 모듈은 empty/mock 경로를 사용한다.
- **Root cause:** Data Trust 진단 경로와 기관형 모듈 입력 어댑터가 분리돼 있다.
- **Fix recommendation:** DataFrame을 PIT-safe DART event 입력으로 변환하는 어댑터를 추가해 촉매 및 alpha state에 공유한다.
- **Required test:** 운영 DataFrame이 event row와 alpha driver로 전달되는지 검증.
- **Confidence:** High

### RF-010 - 완료된 Alpha Discovery 결과를 Dashboard 요약이 무시

- **Status:** VERIFIED
- **Category:** Session state / UI regression
- **File:** `app.py:8240-8246`, `app.py:8359-8370`
- **Symbol:** `render_alpha_discovery_summary`, `render_alpha_discovery_section`
- **Current behavior:** 스캔 완료 뒤 `discovery_scan_requested=False`가 되면 저장된 `discovery_scan_result`가 있어도 홈 요약은 안내문만 표시한다.
- **Impact:** 사용자가 수행한 스캔 결과가 대시보드로 연결되지 않는다.
- **Root cause:** 요약 컴포넌트가 요청 플래그만 읽고 저장 결과를 읽지 않는다.
- **Fix recommendation:** 저장 결과 우선, 요청 중일 때만 실행.
- **Required test:** 저장된 결과가 요청 플래그 false에서도 표시되는지 검증.
- **Confidence:** High

### RF-011 - 대형 배포 산출물이 Git ignore 대상이 아님

- **Status:** VERIFIED
- **Category:** Deployment hygiene
- **File:** `.gitignore`
- **Current behavior:** `.deploy_tmp/`, `deploy_staging/`, `dist/`, 백업 폴더가 untracked로 남는다.
- **Impact:** 실수로 500MB 이상 산출물을 커밋하거나 배포 컨텍스트가 비대해질 수 있다.
- **Root cause:** `.dockerignore`와 `.gitignore` 규칙이 일치하지 않는다.
- **Fix recommendation:** 생성 산출물 패턴을 `.gitignore`에 추가한다.
- **Required test:** `git check-ignore` 검증.
- **Confidence:** High

### RF-016 - 선택 화면과 무관한 전체 시장 데이터 선로딩

- **Status:** VERIFIED
- **Category:** Performance / API rate limit
- **File:** `app.py:9309-9382`
- **Symbol:** `main`
- **Current behavior:** 화면 선택 전에 KRX 목록과 전체 시장 스냅샷을 불러와 설정·매크로·알파 탐색·공시 화면도 불필요한 시세 API를 기다린다.
- **Reproduction:** 깨끗한 세션에서 `?view=settings`로 접속하고 화면 로딩과 공급자 호출 로그를 관찰한다.
- **Expected:** 선택 화면에 필요한 공급자만 호출하고 설정 화면은 즉시 렌더링한다.
- **Actual:** 설정 화면도 `load_listing_cache`와 `load_market_snapshot` 완료 전까지 대기하며, 연속 경로 점검에서 40초 이상 로딩이 지속되었다.
- **Impact:** 화면 전환 지연, 중복 네트워크 호출, 공급자 rate-limit 위험이 증가한다.
- **Root cause:** 내비게이션 결정이 공통 데이터 로딩 뒤에 배치되어 있다.
- **Fix recommendation:** 내비게이션을 사이드바 직후 결정하고 경량 화면을 조기 반환한다. 공시는 목록 확인 뒤, 시세 스냅샷 전 렌더링한다.
- **Confidence:** High

## Low

### RF-017 - 알파 스캔 슬라이더 기본값이 눈금과 불일치

- **Status:** VERIFIED
- **Category:** UI / browser warning
- **File:** `app.py:8465-8472`
- **Symbol:** `render_alpha_discovery_section`
- **Current behavior:** 기본값 220을 최소값 50, 단계 50인 슬라이더에 전달한다.
- **Reproduction:** 알파 후보 탐색 화면을 열고 브라우저 콘솔을 확인한다.
- **Expected:** 기본값이 `min + n * step` 눈금에 정확히 정렬된다.
- **Actual:** Streamlit 프론트엔드가 `values property is in conflict with step, min, and max` 경고를 기록한다.
- **Impact:** 값 접근성 경고와 브라우저 QA 잡음이 발생한다.
- **Root cause:** 세션 기본값을 슬라이더 눈금에 보정하지 않았다.
- **Fix recommendation:** 정수 눈금 정렬 함수를 적용하고 경계·결측값을 테스트한다.
- **Confidence:** High

### RF-012 - 일부 운영 문구가 영어로 남고 숫자 slider가 브라우저 경고를 발생

- **Status:** VERIFIED
- **Category:** Localization / browser console
- **File:** `app.py:3672-3681`, `app.py:9129-9132`
- **Current behavior:** 일부 coach 문구가 영어로 노출되고 거래비용 float slider에서 step/value 정렬 경고가 발생한다.
- **Impact:** 한국어 우선 UI의 일관성과 브라우저 QA 신뢰도가 낮아진다.
- **Root cause:** legacy 문자열과 부동소수 slider 단위가 남았다.
- **Fix recommendation:** 표시 문자열을 중앙 한글 표현으로 바꾸고 비용 입력을 정수 bp로 받는다.
- **Required test:** 금지 영어 문구 정적 감사와 bp 변환 검증.
- **Confidence:** Medium

## False Positive / Preserved Behavior

### RF-013 - 탭별 예외 격리가 오류를 은폐한다는 우려

- **Status:** FALSE_POSITIVE
- **Category:** Runtime resilience
- **File:** `app.py:9060-9066`
- **Evidence:** `render_view_safely`는 예외를 `st.error`로 사용자에게 표시하며 다른 탭 전체의 중단을 막는다. `pass` 또는 정상 데이터 위조가 아니다.
- **Decision:** 보존한다. 단, 예외 문자열의 secret 마스킹은 기존 중앙 안전 규칙을 유지한다.
- **Confidence:** High

### RF-014 - 기존 다운로드 기능 손실

- **Status:** FALSE_POSITIVE
- **Category:** Compatibility
- **Evidence:** 기준 커밋과 현재 작업트리 모두 `st.download_button`이 없다. 현재 diff가 다운로드 기능을 제거한 증거가 없다.
- **Decision:** 신규 다운로드 기능을 만들지 않는다.
- **Confidence:** High

## Review Coverage Notes

- 전체 9개 기존 화면 이름과 route map은 유지돼 있다.
- TLS 검증을 끄는 `verify=False` 또는 전역 monkey patch는 현재 코드에서 발견되지 않았다.
- `.env` 및 `secrets.toml`은 추적되지 않으며 raw secret 출력도 발견되지 않았다.
- 현재 PIT 백테스트는 universe/feature timestamp 계약을 갖지만 RF-003의 실행가격 시점 결함 때문에 수정 전에는 검증 결과로 사용할 수 없다.
- 요청된 여섯 하위 에이전트는 읽기 전용으로 시작했으나 서비스 사용량 제한으로 결과를 반환하지 못했다. 부모 검토가 동일한 여섯 영역을 직접 재현했으며, 이 제한은 최종 독립 재검토에도 명시한다.

## Independent Second-Pass Findings

최초 수정 뒤 별도 관점으로 런타임·금융 계산·UI를 다시 감사해 아래 항목을 추가 확인했다. 각 항목의 최종 처리 결과는 `03_fix_ledger.md`에 기록한다.

### High

- **RF-018 — Docker patch pin 고정:** `Dockerfile:1`의 장기 고정 patch image가 보안 업데이트 수신을 제한했다.
- **RF-019 — KIS 일시 오류 장기 캐시:** `app.py:_get_kis_access_token_cached`가 실패 결과까지 한 시간 캐시할 수 있었다.
- **RF-023 — aware/naive 시각 비교:** `src/korea_equity/backtest_engine.py:_timestamp`가 날짜 문자열을 UTC 자정으로 간주해 한국 거래일 경계를 앞당길 수 있었다.
- **RF-024 — 횡단면 검증 평탄화:** 서로 다른 리밸런스·보유기간의 score/return을 한 배열로 합쳐 Rank IC와 Precision을 계산했다.
- **RF-025 — 미래 매크로 특징 사용:** `src/institutional/forward_alpha.py`가 regime 메타데이터의 `available_at`을 모두 검증하지 않았다.
- **RF-026 — DART 재무정보 시각 손실:** 날짜만 있는 receipt/available 값을 하루 시작으로 해석해 공시일 장중 이전에 사용할 수 있었다.
- **RF-027 — 혼합통화 직접 합산:** `src/portfolio/context.py`가 환산율 없이 KRW와 외화를 합산했다.
- **RF-031 — 진입봉 장중 경로 누수:** 종가 진입 신호의 MFE/MAE·목표/손절 판정에 같은 봉의 고가·저가를 포함했다.

### Medium

- **RF-020 — 세션 새로고침의 전역 캐시 삭제:** 한 사용자의 새로고침이 모든 사용자의 공유 캐시를 제거했다.
- **RF-021 — 공개 DART fallback 메타데이터:** 키 없이 이용 가능한 공개 페이지 fallback도 OpenDART 키 누락으로 표시될 수 있었다.
- **RF-022 — query/session 재조정:** 직접 URL 변경 뒤 기존 segmented-control 상태가 새 query를 덮을 수 있었다.
- **RF-028 — optimizer 종목코드 순서 편향:** 점수 없는 보유종목에 잔여 예산을 코드 정렬 순으로 배분했다.
- **RF-029 — DART 수집시각 덮어쓰기:** 이벤트별 `fetched_at`을 패널 계산시각으로 바꿨다.
- **RF-030 — 시각 없는 포트폴리오 메타데이터:** 기준시각이 없어도 fresh처럼 보일 수 있었다.
- **RF-032 — 화면 이탈 시 필터 상태 소실:** Streamlit이 unmounted widget key를 정리해 데모 설정과 공시 필터가 초기화됐다.
- **RF-033 — DART 오류와 빈 응답 혼동:** 공급자 TLS/HTTP 오류가 정상적인 공시 0건과 같은 empty state가 됐다.
- **RF-034 — 도달 불가능한 한글 매핑:** 원문이 아닌 부분 번역 문자열을 dictionary key로 사용해 두 문장이 영문으로 남았다.
- **RF-035 — 내비게이션 정보·배치:** 선택 화면 접근성 문구가 없고 마지막 행 버튼 폭이 불균형했다.
- **RF-037 — 브라우저 Back의 popstate 한계:** URL history가 바뀌어도 Streamlit이 rerun event를 보내지 않아 보이는 화면이 즉시 동기화되지 않는다.

### Test Defect

- **RF-036 — 공개 DART fallback 기대값 오류:** 기존 테스트가 합법적인 keyless 공개 fallback을 차단해야 한다고 기대했다. source registry 계약과 안전 규칙을 확인한 뒤 테스트를 올바른 계약으로 수정했다.
