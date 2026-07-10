# D. Portfolio And Risk Audit

## 1. 범위

범위는 sidebar portfolio 입력, Portfolio 탭, Portfolio Risk Cockpit, portfolio intelligence, optimizer/alerts, execution/exit risk 연결이다.

기준선:

- Python 3.11.8 / Streamlit 1.58.x
- 193 tests pass 이상
- 수동 입력과 실제 source를 우선
- mock은 명시적 demo에서만 사용
- review/rebalance candidate이며 주문 실행 없음

## 2. 현재 portfolio inventory

```text
sidebar
  total_assets
  cash
  holdings CSV(code, qty, avg_price, sector)
  risk settings

Portfolio tab
  parse rows
  load symbol history
  risk plan + exit plan
  holding table / sector concentration / exit priority

Dashboard
  Portfolio Risk Cockpit
  Portfolio Intelligence
  Portfolio Optimizer & Alert Center
```

현재 강점:

- concentration, cash, top holding/top10, sector, stale price alert.
- mock alert를 `예시 알림`과 `example_only`로 차단.
- holdings/price/sector/calculation source를 분리하려는 risk metadata.
- high risk가 alpha/add exposure를 override.
- optimizer에 long-only/no-leverage/cash/single/sector cap 개념 존재.
- `src/portfolio/context.py`가 computed total, discrepancy, history coverage, risk contribution을 정의하고 10개 tests가 추가됨.

## 3. 보존 대상

### D-P01. 수동 CSV workflow

- **분류:** `PRESERVE`
- `code,qty,avg_price,sector` 형식과 sidebar 진입점을 유지한다.
- 오류 행은 전체 앱을 중단하지 않고 행별 경고한다.
- 기존 widget/session key를 유지한다.

### D-P02. risk alert 언어와 metadata

- **분류:** `PRESERVE`
- 한국어 title/body/review action, severity, actionability를 유지한다.
- 모의 데이터는 예시 알림이며 urgent/actionable처럼 보이지 않는다.
- stale 데이터는 최신 가격 전까지 판단 제한.
- 자동 주문 대신 검토·리밸런싱 후보를 사용한다.

### D-P03. execution/exit 연결

- **분류:** `PRESERVE`
- liquidity/cost가 expected edge를 넘으면 대기.
- hard/trailing/time stop과 event risk를 함께 검토.
- 주문 API를 추가하지 않는다.

## 4. Critical finding

### D-C01. 리스크 설정의 세션 간 공유 가능성

- **분류:** `FIX`
- module global `RISK_DEFAULTS`를 sidebar가 직접 변경한다.
- max position, sector cap, cost/slippage, RR gate가 다른 사용자 계산에 영향을 줄 수 있다.

구현:

- immutable defaults.
- session-scoped validated `RiskSettings`.
- 모든 risk/action/execution 함수에 명시 전달.
- Settings/sidebar 동일 object 사용.

Acceptance:

- 두 세션의 cap/cost가 서로 영향을 주지 않는다.
- audit output에 settings snapshot id가 남는다.

## 5. High findings

### D-H01. canonical validation이 Portfolio 탭 전체에 적용되지 않음

- **분류:** `FIX`
- canonical context는 음수·비유한 값과 cash 중복을 검증하지만, Portfolio 탭의 legacy 보유/손절 loop는 parsed rows를 직접 사용한다.
- 0 quantity/average cost, duplicate code, conflicting sector, 매우 큰 값에 대한 제품 정책도 명확하지 않다.

규칙:

- code는 유효 6자리 KRX.
- quantity > 0, avg_price > 0, finite.
- duplicate는 같은 metadata일 때만 합산.
- error row는 계산에서 제외하고 행 번호·필드를 한국어로 표시.
- 입력 원문 전체나 포트폴리오 값을 log에 남기지 않는다.

### D-H02. reconciliation은 도입됐지만 legacy 표가 다른 분모를 사용

- **분류:** `FIX`
- 새 context는 computed total을 authoritative로 두고 1% 초과 discrepancy를 경고한다.
- Risk Cockpit/Portfolio Intelligence는 이를 사용하지만 Portfolio 탭 metric/손실률/섹터 경고는 선언 총자산을 계속 분모로 사용한다.
- 한 화면군 안에서 total과 risk ratio가 달라질 수 있다.

필요 상태:

- `declared_total_assets`
- `priced_holdings_value`
- `cash`
- `computed_total`
- `unpriced_cost_basis`
- `reconciliation_difference`
- `reconciliation_status`

tolerance 밖에서는 target weight/optimizer를 차단하고 risk review만 표시한다.

### D-H03. 누락 현재가를 평균단가로 대체

- **분류:** `FIX`
- `rowsToHoldings()`는 snapshot 현재가가 없으면 평균단가를 current price로 사용한다.
- risk cockpit metadata가 stale을 표시해도 평가손익/비중은 exact-looking 값이 된다.

필요:

- current price는 nullable.
- cost basis와 mark-to-market을 분리.
- 가격 누락 종목은 market value/weight/stop loss 계산 불가.
- portfolio priced coverage와 unpriced exposure를 별도 표시.

### D-H04. Portfolio context의 부분 도입

- **분류:** `RELOCATE_WITH_ALIAS`
- Risk Cockpit/Portfolio Intelligence는 새 context를 사용하지만 Portfolio 탭은 dict row와 자체 loop로 계산한다.
- total/sector/current price/alert 기준이 달라질 수 있다.

필요:

- canonical `PortfolioSnapshot`/`ReconciledPortfolio` service.
- Portfolio tab, Dashboard risk, optimizer가 같은 view model 사용.
- 기존 renderer 함수는 wrapper alias 유지.

### D-H05. 현재 보유수량 고정 재구성을 실제 성과로 오인할 수 있음

- **분류:** `FIX` + `ENRICH`
- 새 `build_reconstructed_portfolio_series()`는 현재 보유수량을 과거 520일 가격에 고정 적용하고 60일/80% coverage gate를 둔다.
- 이는 거래·입출금·보유 변경 이력이 없는 hypothetical reconstruction이며 실제 계좌 성과가 아니다.

필요:

- 현재 reconstruction은 `현재 보유 기준 가상 재구성`으로 명명.
- 실제 성과는 보유 변화·거래·입출금 이력을 point-in-time으로 재구성할 수 있을 때만 표시.
- unavailable 이유와 필요한 데이터를 표시.

### D-H06. Optimizer가 실제 upstream과 미연결

- **분류:** `ENRICH`
- Dashboard renderer는 actual holdings/Forward Alpha state를 optimizer builder에 전달하지 않는다.
- production에서는 empty가 안전하지만 기능이 완료된 것은 아니다.

필요:

- reconciled holdings, cash, production alpha, FX/rates state 전달.
- stale/mock/empty upstream이면 actionability block.
- target sum + cash = 100%, caps invariant.

### D-H07. cash/total 입력 상호 제약 없음

- **분류:** `FIX`
- UI number inputs는 각각 nonnegative지만 cash가 total보다 클 수 있다.
- cash 변경이 보유 평가와 reconcile되지 않는다.

필요:

- 입력 즉시 validation.
- 초과 시 자동 조용한 보정 대신 명시적 오류와 계산 중단.

## 6. Medium findings

### D-M01. sector metadata 신뢰도

- **분류:** `ENRICH`
- sector는 사용자가 CSV에 입력한다.
- source를 manual로 표시하고, 향후 official/reference mapping과 충돌 여부를 보여준다.

### D-M02. multi-currency model과 계산

- **분류:** `FIX`
- model은 currency를 지원하지만 total은 숫자를 단순 합산한다.
- 현재 sidebar는 국내 code 중심이므로 즉시 영향은 제한적이다.
- KRW가 아닌 보유는 FX source 없이는 total/weight를 N/A로 둔다.

### D-M03. liquidity input coverage

- **분류:** `ENRICH`
- Holding model에 ADV가 기본 포함되지 않아 liquidity alert가 자주 계산되지 않는다.
- source/date/unit가 있는 ADV20을 연결하고 position/ADV ratio를 표시한다.

### D-M04. risk budget 표현

- **분류:** `ENRICH`
- per-trade loss, aggregate stop loss, correlated sector shock를 분리한다.
- sum of stop losses가 total risk budget을 넘을 때 review gate를 추가한다.

### D-M05. alert deduplication과 lifecycle

- **분류:** `ENRICH`
- 같은 원인의 concentration/top10/sector alert를 priority와 affected exposure로 묶는다.
- acknowledged/resolved 상태는 주문 상태와 분리한다.

## 7. 목표 데이터 계약

```text
ReconciledPortfolio
  portfolio_id / owner_scope
  as_of / fetched_at
  declared_total_assets
  priced_holdings_value
  unpriced_cost_basis
  cash
  computed_total
  reconciliation_difference/status
  holdings[]
    symbol, qty, avg_cost
    current_price nullable
    market_value nullable
    sector/currency
    holdings_meta
    price_meta
    sector_meta
  risk_settings_snapshot
  stale/missing/mock flags
```

이 계약에서 숫자가 없으면 downstream이 0으로 해석하지 않는다.

## 8. 구현 순서

1. session `RiskSettings`와 parser validation.
2. nullable price를 지원하는 holding/view model.
3. 기존 context/reconciliation invariant를 Portfolio 탭까지 연결.
4. Portfolio tab/Risk Cockpit을 같은 canonical service에 연결.
5. hypothetical reconstruction과 actual performance를 명확히 분리.
6. optimizer actual upstream 연결.
7. sector/FX/ADV metadata adapter.

## 9. 테스트 계획

Unit/property:

- negative/zero/NaN/Infinity/overflow 입력.
- duplicate same/conflicting metadata.
- cash > total, holdings+cash > total, tolerance boundary.
- missing/stale price와 coverage.
- allocation 합 100%.
- single/sector/KOSDAQ/cash cap.
- multi-currency missing FX.
- high-risk override.
- mock alert example-only.

Integration/UI:

- empty portfolio.
- valid 1종목/15종목.
- 일부 가격 누락.
- Settings/sidebar sync, two-session isolation.
- Dashboard risk와 Portfolio tab total이 동일.
- optimizer empty/blocked/ready.
- 390px table internal scroll, page overflow 0.

기준 명령:

```powershell
py -3.11 -m compileall app.py src tests
py -3.11 -m unittest discover tests
```

## 10. Rollback

- `ENABLE_RECONCILED_PORTFOLIO`와 `ENABLE_PRODUCTION_OPTIMIZER`를 분리한다.
- 새 service 실패 시 legacy Portfolio 표를 read-only로 유지하고 신규 action/optimizer를 숨긴다.
- legacy parser wrapper를 한 release 유지하되 invalid 값을 계산에 통과시키지는 않는다.
- schema 변경은 additive; 기존 sidebar text는 변환 없이 보존한다.
- 실제 데이터 부족 시 empty로 복귀하고 mock을 자동 활성화하지 않는다.
- 두 계산 경로의 total 차이, allocation invariant 실패, session leakage가 발견되면 해당 flag를 즉시 off한다.

## 11. 완료 조건

- 사용자별 risk settings가 격리된다.
- invalid portfolio 값이 계산에 들어가지 않는다.
- total/cash/holdings가 reconcile되고 allocation 합이 유효하다.
- 누락 가격이 평균단가 current price로 가장되지 않는다.
- Dashboard/Portfolio/Optimizer가 같은 canonical portfolio를 사용한다.
- mock/stale는 actionability를 차단한다.
- 193 기준선 이상 전체 테스트가 통과한다.
