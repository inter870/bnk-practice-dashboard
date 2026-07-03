# 한국주식시장 50개 통계 법칙 투자 적용 매뉴얼

**파일 목적**: 한국 KOSPI·KOSDAQ 시장에서 통계적으로 유의미하게 관찰된 anomaly 법칙을 실제 종목 스크리닝, 점수화, 포트폴리오 구축, 리밸런싱에 바로 적용하기 위한 실전 운용 매뉴얼이다.

**버전**: 2026-07-02  
**적용 대상**: 한국 상장 보통주 중심의 중장기 퀀트·팩터 투자  
**핵심 원칙**: 싸고, 현금흐름이 좋고, 거래 과열이 낮고, 변동성이 낮고, 복권형 급등성이 낮고, 회계 발생액이 낮고, 52주 고점 모멘텀이 살아 있는 종목을 선별한다.

---

## 0. 근거와 사용 기준

이 매뉴얼은 Han, Lee, Kang(2020)의 한국시장 anomaly 복제 연구를 기반으로 작성했다. 해당 연구는 한국 KOSPI·KOSDAQ 시장에서 148개 anomaly를 복제했고, KOSPI+KOSDAQ 가치가중 포트폴리오 기준으로 통계적으로 살아남는 anomaly가 제한적이라는 점을 보였다.

- 연구명: *Market Anomalies in the Korean Stock Market*
- 저자: Minyeon Han, Dong-Hyun Lee, Hyoung-Goo Kang
- 학술지: *Journal of Derivatives and Quantitative Studies*, 28(2), 159-228, 2020
- DOI: 10.1108/JDQS-03-2020-0004
- 핵심 결과:
  - KOSPI+KOSDAQ 가치가중 기준에서 148개 anomaly 중 약 37.8%만 |t| > 1.96
  - 더 엄격한 기준인 |t| > 2.78에서는 약 27.7%만 생존
  - 마이크로캡, KOSDAQ 포함 여부, 동일가중/가치가중 방식에 따라 성과가 크게 달라짐
  - tactical asset allocation에 적용할 때는 데이터마이닝과 거래비용을 반드시 고려해야 함

**실전 해석 원칙**

1. `◎` 법칙은 핵심 신호로 사용한다.  
2. `○` 법칙은 보조 신호로만 사용한다.  
3. 단일 법칙 하나로 매수하지 않는다. 최소 3개 이상의 독립 신호가 동시에 맞을 때만 후보로 편입한다.  
4. 마이크로캡 효과를 그대로 믿지 않는다. 실전에서는 유동성 하한과 시가총액 하한을 반드시 둔다.  
5. 고변동성·고회전율·복권형 급등주 회피는 매수보다 더 중요한 방어 법칙이다.

---

## 1. 바로 적용하는 투자 엔진 구조

### 1.1 투자 유니버스

아래 조건을 통과한 종목만 점수화한다.

```yaml
universe:
  market:
    - KOSPI
    - KOSDAQ
  include:
    - 보통주
  exclude:
    - 금융업
    - 우선주
    - ETF
    - ETN
    - 리츠
    - SPAC
    - 관리종목
    - 거래정지 종목
    - 자본잠식 기업
    - 감사의견 비적정 기업
    - 신규상장 12개월 미만 기업
  liquidity_floor:
    min_market_cap_krw: 100_000_000_000
    min_avg_daily_trading_value_20d_krw: 1_000_000_000
```

**운용자 메모**  
논문상으로는 낮은 거래대금·높은 비유동성 종목이 초과수익을 냈지만, 실전에서는 체결비용·슬리피지·호가공백이 수익을 잠식한다. 따라서 “거래 과열은 싫어하지만, 절대 유동성이 너무 낮은 종목도 피한다”가 실전 정답이다.

---

### 1.2 리밸런싱 기본값

```yaml
rebalance:
  frequency: monthly
  date: 매월 마지막 거래일 또는 다음 월 첫 거래일
  holding_period: 1개월 기본
  financial_statement_lag:
    quarterly: 45~60일
    annual: 90일
  max_turnover_per_month: 35%
```

**권장 운용 방식**

- 월 1회 리밸런싱을 기본으로 한다.
- 재무제표 데이터는 발표 지연을 반영한다.
- 리밸런싱 때마다 전체 매매가 아니라 점수 하락 종목만 교체한다.
- 종목 점수는 매월 새로 산출하되, 재무 신호는 분기 단위로 업데이트한다.

---

## 2. 5단계 종목 선정 프로세스

### STEP 1. 거래 불가능·고위험 종목 제거

아래에 해당하면 점수화하지 않고 제외한다.

```yaml
hard_exclusion:
  - 거래정지
  - 관리종목
  - 감사의견 비적정
  - 자본잠식
  - 최근 20거래일 평균 거래대금 10억원 미만
  - 시가총액 1,000억원 미만
  - 상장 12개월 미만
  - 재무제표 결측이 과도한 기업
```

---

### STEP 2. 방어 필터 적용

아래 조건 중 2개 이상 해당하면 매수 후보에서 제외한다.

```yaml
defensive_filter:
  avoid_if_2_or_more:
    - 고유변동성 상위 20%
    - 총변동성 상위 20%
    - 거래회전율 상위 20%
    - 최근 1개월 최대 일일수익률 상위 20%
    - 총발생액 또는 영업발생액 상위 20%
    - 주식 발행 증가율 상위 20%
```

**핵심 판단**  
한국시장에서는 “좋은 종목을 찾는 것”보다 “고변동성·복권형·회계질 낮은 종목을 제거하는 것”의 효용이 크다.

---

### STEP 3. 팩터 점수 산출

최종 점수는 100점 만점으로 산출한다.

```yaml
score_model:
  valuation_cashflow: 35
  low_risk_liquidity: 25
  momentum: 20
  accounting_quality: 10
  intangible_quality: 10
```

#### A. 가치·현금흐름 35점

| 세부 신호 | 방향 | 점수 |
|---|---:|---:|
| 영업현금흐름/시총 OCP | 높을수록 좋음 | 10 |
| 장부가치/시총 BM, BMJ | 높을수록 좋음 | 8 |
| 자산/시총 AM, 기업가치 기준 장부가치 EBP | 높을수록 좋음 | 5 |
| 매출/시총 SP, 현금흐름/주가 CP | 높을수록 좋음 | 7 |
| EV/EBITDA EM | 낮을수록 좋음 | 3 |
| 부채/시총 DM | 조건부 보조 | 2 |

#### B. 저위험·거래비과열 25점

| 세부 신호 | 방향 | 점수 |
|---|---:|---:|
| 고유변동성 IVOL | 낮을수록 좋음 | 8 |
| 총변동성 TVOL | 낮을수록 좋음 | 5 |
| 거래회전율 Turnover | 낮을수록 좋음 | 5 |
| 최대 일일수익률 MDR | 낮을수록 좋음 | 5 |
| 거래대금 변동성 CVD | 낮을수록 좋음 | 2 |

#### C. 모멘텀 20점

| 세부 신호 | 방향 | 점수 |
|---|---:|---:|
| 52주 고점 근접도 | 높을수록 좋음 | 8 |
| 최근 6개월 모멘텀 | 높을수록 좋음 | 6 |
| 잔차 모멘텀 | 높을수록 좋음 | 4 |
| 직전 1개월 강세 | 과열이 없을 때만 좋음 | 2 |

#### D. 회계 품질 10점

| 세부 신호 | 방향 | 점수 |
|---|---:|---:|
| 총발생액 PTA | 낮을수록 좋음 | 3 |
| 영업발생액 OA | 낮을수록 좋음 | 2 |
| 재량발생액 PDA | 낮을수록 좋음 | 2 |
| 순비현금 운전자본 증가 dWC | 낮을수록 좋음 | 1 |
| 신주발행 CEI | 낮을수록 좋음 | 2 |

#### E. 무형자산·기업질 10점

| 세부 신호 | 방향 | 점수 |
|---|---:|---:|
| R&D/시총 RDM | 높을수록 좋음 | 4 |
| 광고비/시총 ADM | 높을수록 좋음 | 3 |
| 상장 연령 AgeList | 높을수록 좋음 | 2 |
| 매출 증가의 질 dSA | 높을수록 좋음 | 1 |

---

### STEP 4. 종목 선별

```yaml
selection:
  primary_buy_zone:
    score_rank: top_10_percent
  secondary_buy_zone:
    score_rank: top_20_percent
    condition: 포트폴리오 공백이 있을 때만
  minimum_score:
    absolute: 70
  preferred_number_of_holdings:
    concentrated: 15~20
    balanced: 25~35
```

**실전 판단**

- 공격형: 상위 10%, 15~20종목
- 균형형: 상위 20%, 25~35종목
- 보수형: KOSPI+KOSDAQ150 중심, 상위 20%, 30~50종목

---

### STEP 5. 포트폴리오 구성

```yaml
portfolio:
  max_single_stock_weight: 5%
  default_single_stock_weight: 3%~4%
  max_sector_weight: 25%
  max_kosdaq_weight: 40%
  cash_buffer: 5%~15%
  rebalance_band:
    trim_if_weight_above: target_weight * 1.5
    add_if_weight_below: target_weight * 0.5
```

**핵심 운용 규칙**

1. 상위 점수 종목이라도 한 종목 5%를 넘기지 않는다.
2. 동일 업종에 25% 이상 집중하지 않는다.
3. KOSDAQ은 초과수익 가능성이 있지만 변동성·유동성 리스크가 크므로 40% 이내로 제한한다.
4. 현금 5~15%를 유지해 급락 시 교체 매수 여력을 남긴다.
5. 리밸런싱은 점수 하락 종목을 교체하는 방식으로 거래비용을 줄인다.

---

## 3. 50개 통계 법칙 실전 적용표

표기법:

- `◎`: 강한 통계 법칙. 핵심 점수 또는 강한 회피 필터로 사용.
- `○`: 통계적으로 유의하지만 실전에서는 보조 점수로 사용.
- `매수`: 높을수록 좋거나 낮을수록 좋은 방향이 명확한 선별 신호.
- `회피`: 특정 성향이 높은 종목을 피하는 방어 신호.
- `조건부`: 단독 사용 금지. 다른 신호와 결합해야 함.

| # | 법칙 | 코드 | 방향 | 실전 사용 | 강도 |
|---:|---|---|---|---|:---:|
| 1 | 거래대금이 지나치게 큰 종목은 피한다. | Dtv1 | 낮은 거래대금 우위 | 절대 유동성 하한 통과 후, 상대적 과열 거래대금 감점 | ◎ |
| 2 | 영업현금흐름/시총이 높은 종목을 산다. | Ocp | 높을수록 좋음 | 가치·현금흐름 핵심 점수 | ◎ |
| 3 | 거래회전율이 높은 종목은 피한다. | Tur12 | 낮을수록 좋음 | 과열거래 회피 필터 | ◎ |
| 4 | 단기 거래회전율이 높은 종목은 피한다. | Tur1 | 낮을수록 좋음 | 단기 과열 회피 | ◎ |
| 5 | CAPM 기준 고유변동성이 높은 종목은 피한다. | Ivc1 | 낮을수록 좋음 | 핵심 방어 필터 | ◎ |
| 6 | 장부가치/6월 말 시총이 높은 기업을 선호한다. | Bmj | 높을수록 좋음 | 저PBR 가치 점수 | ◎ |
| 7 | FF3 기준 고유변동성이 높은 종목은 피한다. | Ivff1 | 낮을수록 좋음 | 핵심 방어 필터 | ◎ |
| 8 | B/M이 높은 주식, 즉 PBR이 낮은 주식을 선호한다. | Bm | 높을수록 좋음 | 가치 핵심 점수 | ◎ |
| 9 | 고유변동성 낮은 종목은 6개월 보유에서도 우위다. | Ivc6 | 낮을수록 좋음 | 중기 방어 점수 | ◎ |
| 10 | 최근 대박 일봉이 컸던 복권형 주식은 피한다. | Mdr10_12 | 낮을수록 좋음 | 복권형 급등주 회피 | ◎ |
| 11 | 총발생액이 높은 기업은 피한다. | Pta | 낮을수록 좋음 | 회계 품질 필터 | ◎ |
| 12 | FF3 고유변동성 낮은 종목은 6개월 보유에서도 강하다. | Ivff6 | 낮을수록 좋음 | 중기 방어 점수 | ◎ |
| 13 | 자산/시총이 높은 자산가치주를 선호한다. | Am | 높을수록 좋음 | 자산가치 점수 | ◎ |
| 14 | 총변동성이 높은 종목은 피한다. | Tv6 | 낮을수록 좋음 | 방어 필터 | ◎ |
| 15 | 고유변동성 낮은 종목은 12개월 보유에서도 우위다. | Ivc12 | 낮을수록 좋음 | 장기 방어 점수 | ◎ |
| 16 | 광고비/시총이 높은 기업을 선호한다. | Adm | 높을수록 좋음 | 브랜드·무형자산 보조 점수 | ◎ |
| 17 | 총변동성 낮은 종목은 12개월 보유에서도 우위다. | Tv12 | 낮을수록 좋음 | 장기 방어 점수 | ◎ |
| 18 | 최근 최대 일일수익률이 높은 종목은 이후 약하다. | Mdr5_6 | 낮을수록 좋음 | 복권형 주식 회피 | ◎ |
| 19 | 복권형 급등주 회피 효과는 12개월 보유에서도 남는다. | Mdr5_12 | 낮을수록 좋음 | 복권형 주식 회피 | ◎ |
| 20 | R&D/시총이 높은 기업을 선호한다. | Rdm | 높을수록 좋음 | 무형자산 투자 점수 | ◎ |
| 21 | 신규상장주보다 오래 상장된 기업이 유리하다. | AgeList | 높을수록 좋음 | 신규상장 과열 회피 | ◎ |
| 22 | 월중 극단적 급등 성향이 큰 종목은 피한다. | Mdr10_6 | 낮을수록 좋음 | 복권형 주식 회피 | ◎ |
| 23 | FF3 고유변동성 낮은 종목은 12개월 보유에서도 강하다. | Ivff12 | 낮을수록 좋음 | 장기 방어 점수 | ◎ |
| 24 | 단기 급등 복권주는 다음 달 약하다. | Mdr5_1 | 낮을수록 좋음 | 단기 급등주 매수 금지 | ◎ |
| 25 | 매출/시총이 높은 기업을 선호한다. | Sp | 높을수록 좋음 | 저PSR 가치 점수 | ◎ |
| 26 | 최근 6개월 모멘텀은 한국시장에서도 작동한다. | R6_6 | 높을수록 좋음 | 가격 모멘텀 점수 | ◎ |
| 27 | 52주 신고가에 가까운 종목은 강하다. | 52w12 | 높을수록 좋음 | 52주 고점 모멘텀 핵심 점수 | ◎ |
| 28 | 거래회전율 낮은 종목은 6개월 보유에서도 우위다. | Tur6 | 낮을수록 좋음 | 과열거래 회피 | ◎ |
| 29 | 거래대금 낮은 종목 우위는 6개월 보유에서도 나타난다. | Dtv6 | 낮을수록 좋음 | 절대 유동성 하한 후 상대 감점 | ◎ |
| 30 | 주식 발행을 많이 한 기업은 피한다. | Cei | 낮을수록 좋음 | 희석·과잉조달 회피 | ◎ |
| 31 | 잔차 모멘텀도 작동한다. | ε6_6 | 높을수록 좋음 | 시장·업종 영향 제거 후 모멘텀 | ◎ |
| 32 | 52주 고점 모멘텀은 6개월 보유에서도 강하다. | 52w6 | 높을수록 좋음 | 모멘텀 핵심 점수 | ◎ |
| 33 | 비유동성 프리미엄이 존재한다. | Ami1 | 높을수록 좋음 | 중형주 내 보조 점수. 초소형주는 제외 | ◎ |
| 34 | 월중 극단적 급등 성향이 큰 종목은 다음 달 약하다. | Mdr10_1 | 낮을수록 좋음 | 단기 급등주 회피 | ◎ |
| 35 | 직전 1개월 강세 종목은 단기적으로 강했다. | Srev1 | 높을수록 좋음 | 과열·복권형 필터 통과 시만 보조 | ◎ |
| 36 | 단기 총변동성이 높은 종목은 피한다. | Tv1 | 낮을수록 좋음 | 핵심 방어 필터 | ◎ |
| 37 | 매출 증가가 매출채권 증가보다 강한 기업을 선호한다. | dSa | 높을수록 좋음 | 매출의 질 보조 점수 | ◎ |
| 38 | 거래대금 낮은 종목 우위는 12개월 보유에서도 남는다. | Dtv12 | 낮을수록 좋음 | 과열 거래대금 감점 | ◎ |
| 39 | 영업발생액이 높은 기업은 피한다. | Oa | 낮을수록 좋음 | 회계 품질 필터 | ◎ |
| 40 | 기업가치 기준 장부가치/시장가치가 높은 기업을 선호한다. | Ebp | 높을수록 좋음 | 가치 보조 점수 | ◎ |
| 41 | 부채/시총이 높은 기업은 초과수익을 냈지만 조건부로만 쓴다. | Dm | 높을수록 좋음 | 재무위험 통과 기업에만 보조 | ◎ |
| 42 | 현금흐름/주가가 높은 기업을 선호한다. | Cp | 높을수록 좋음 | 가치·현금흐름 보조 점수 | ○ |
| 43 | 거래대금 변동성이 큰 종목은 피한다. | Cvd12 | 낮을수록 좋음 | 거래 불안정성 감점 | ○ |
| 44 | 재량적 발생액 비중이 높은 기업은 피한다. | Pda | 낮을수록 좋음 | 회계 품질 보조 필터 | ○ |
| 45 | 11개월 잔차 모멘텀도 작동한다. | ε11_1 | 높을수록 좋음 | 보조 모멘텀 | ○ |
| 46 | 장부가치가 급증한 기업은 조심한다. | dBe | 낮을수록 좋음 | 자본증가·회계누적 감점 | ○ |
| 47 | EV/EBITDA가 낮은 기업을 선호한다. | Em | 낮을수록 좋음 | 밸류에이션 보조 점수 | ○ |
| 48 | 6개월 가격 모멘텀은 12개월 보유에서도 유효하다. | R6_12 | 높을수록 좋음 | 중기 모멘텀 점수 | ○ |
| 49 | 순비현금 운전자본이 크게 증가한 기업은 피한다. | dWc | 낮을수록 좋음 | 운전자본 질 감점 | ○ |
| 50 | 52주 고점 근접 신호는 1개월 보유에서도 작동한다. | 52w1 | 높을수록 좋음 | 단기 모멘텀 보조 | ○ |

---

## 4. 실전 우선순위: 가장 강하게 써야 할 10개 법칙

50개를 모두 같은 비중으로 쓰면 신호 중복과 과최적화가 생긴다. 실제 운용에서는 아래 10개를 중심축으로 삼는다.

| 우선순위 | 핵심 법칙 | 이유 | 적용 방식 |
|---:|---|---|---|
| 1 | 영업현금흐름/시총 OCP 높음 | 현금 기반 가치 신호 | 상위 20% 가산 |
| 2 | 고유변동성 IVOL 낮음 | 한국시장 저변동성 프리미엄 | 상위 변동성 20% 제외 |
| 3 | 거래회전율 Turnover 낮음 | 과열·투기 수요 회피 | 상위 회전율 20% 제외 |
| 4 | 최대 일일수익률 MDR 낮음 | 복권형 급등주 회피 | 최근 급등성 상위 20% 제외 |
| 5 | B/M 높음 | 저PBR 가치주 신호 | 상위 30% 가산 |
| 6 | 52주 고점 근접도 높음 | 모멘텀·추세 지속 신호 | 상위 30% 가산 |
| 7 | 총발생액 PTA 낮음 | 이익의 질 | 발생액 상위 20% 제외 |
| 8 | 6개월 모멘텀 높음 | 추세 지속 | 상위 30% 가산 |
| 9 | 신주발행 CEI 낮음 | 희석·과잉투자 회피 | 상위 발행 증가 기업 제외 |
| 10 | 매출/시총 SP 또는 현금흐름/주가 CP 높음 | 저평가 보강 | 상위 30% 가산 |

---

## 5. 점수 계산 방식

### 5.1 랭킹 변환

각 지표를 원자료 그대로 쓰지 말고 섹터 중립 또는 전체 유니버스 내 percentile rank로 바꾼다.

```text
좋은 방향이 높을수록 좋은 지표:
factor_score = percentile_rank(value)

좋은 방향이 낮을수록 좋은 지표:
factor_score = 1 - percentile_rank(value)
```

예시:

```text
B/M이 높을수록 좋다:
BM_score = percentile_rank(BM)

고유변동성이 낮을수록 좋다:
IVOL_score = 1 - percentile_rank(IVOL)
```

### 5.2 이상치 처리

```yaml
winsorization:
  lower: 1%
  upper: 99%
```

PER, PBR, EV/EBITDA처럼 음수·결측·극단값이 많은 지표는 ranking 전에 winsorization을 적용한다.

### 5.3 최종 점수 공식

```text
FinalScore =
  0.35 * ValuationCashflowScore
+ 0.25 * LowRiskLiquidityScore
+ 0.20 * MomentumScore
+ 0.10 * AccountingQualityScore
+ 0.10 * IntangibleQualityScore
```

### 5.4 매수 기준

```yaml
buy_rule:
  buy_candidate:
    - FinalScore >= 70
    - FinalScore percentile >= 80%
    - hard_exclusion 통과
    - defensive_filter 통과
  strong_buy_candidate:
    - FinalScore percentile >= 90%
    - OCP/BM/52w/IVOL/Turnover 중 3개 이상 상위권
```

### 5.5 매도 기준

```yaml
sell_rule:
  mandatory_sell:
    - 관리종목 지정
    - 거래정지 또는 감사의견 위험
    - 자본잠식 발생
    - 유동성 하한 미달
  factor_sell:
    - FinalScore percentile < 50%
    - 고유변동성 상위 20% 진입
    - 거래회전율 상위 20% 진입
    - 총발생액 상위 20% 진입
    - 신주발행 급증
  trim_rule:
    - 종목 비중이 목표비중의 1.5배 초과
    - 업종 비중 25% 초과
```

---

## 6. 지표 정의와 데이터 컬럼

### 6.1 필수 데이터 컬럼

```csv
date,ticker,company_name,market,sector,
price,market_cap,shares_outstanding,
daily_return,volume,trading_value,
book_equity,total_assets,total_liabilities,
sales,operating_cash_flow,net_income,ebitda,
research_and_development,advertising_expense,
current_assets,current_liabilities,cash,short_term_debt,
accounts_receivable,inventory,
listing_date,audit_opinion,capital_impairment_flag,trading_halt_flag
```

### 6.2 주요 지표 계산식

| 코드 | 지표명 | 계산 개념 | 좋은 방향 |
|---|---|---|---|
| Ocp | 영업현금흐름/시총 | operating_cash_flow / market_cap | 높음 |
| Bm | 장부가치/시총 | book_equity / market_cap | 높음 |
| Bmj | 6월 말 기준 장부가치/시총 | book_equity / June_market_cap | 높음 |
| Am | 자산/시총 | total_assets / market_cap | 높음 |
| Sp | 매출/시총 | sales / market_cap | 높음 |
| Cp | 현금흐름/가격 | cash_flow / market_cap | 높음 |
| Ebp | 기업가치 기준 장부가치 | book_equity / enterprise_value | 높음 |
| Em | EV/EBITDA | enterprise_value / EBITDA | 낮음 |
| Dm | 부채/시총 | total_debt / market_cap | 조건부 높음 |
| Ivc | CAPM 고유변동성 | 시장모형 잔차 변동성 | 낮음 |
| Ivff | FF3 고유변동성 | FF3 잔차 변동성 | 낮음 |
| Tv | 총변동성 | 일간수익률 표준편차 | 낮음 |
| Tur | 거래회전율 | volume / shares_outstanding | 낮음 |
| Dtv | 거래대금 | trading_value | 조건부 낮음 |
| Ami | Amihud 비유동성 | abs(return) / trading_value | 조건부 높음 |
| MDR | 최대 일일수익률 | lookback 내 max(daily_return) | 낮음 |
| PTA | 총발생액 | accruals / total_assets | 낮음 |
| OA | 영업발생액 | operating_accruals / total_assets | 낮음 |
| PDA | 재량발생액 | discretionary_accruals / total_assets | 낮음 |
| CEI | 주식 발행 증가 | shares_outstanding 변화율 | 낮음 |
| dWC | 순비현금 운전자본 증가 | Δnon_cash_working_capital | 낮음 |
| dBE | 장부가치 증가 | Δbook_equity | 낮음 |
| 52w | 52주 고점 근접도 | price / 52_week_high | 높음 |
| R6 | 6개월 모멘텀 | 최근 6개월 누적수익률 | 높음 |
| ε | 잔차 모멘텀 | 요인모형 잔차 누적수익률 | 높음 |
| RDM | R&D/시총 | R&D / market_cap | 높음 |
| ADM | 광고비/시총 | advertising_expense / market_cap | 높음 |
| AgeList | 상장 연령 | months_since_listing | 높음 |
| dSA | 매출의 질 | 매출 증가 - 매출채권 증가 | 높음 |

---

## 7. 실제 운용 규칙

### 7.1 매수 전 체크리스트

아래 10개 중 7개 이상 충족해야 매수 후보로 인정한다.

```markdown
- [ ] 관리종목, 거래정지, 자본잠식, 감사의견 위험이 없다.
- [ ] 시가총액 1,000억원 이상이다.
- [ ] 최근 20거래일 평균 거래대금 10억원 이상이다.
- [ ] 고유변동성 상위 20%가 아니다.
- [ ] 거래회전율 상위 20%가 아니다.
- [ ] 최근 1개월 최대 일일수익률 상위 20%가 아니다.
- [ ] 영업현금흐름/시총 또는 현금흐름/가격이 상위 30%다.
- [ ] B/M, 자산/시총, 매출/시총 중 최소 1개가 상위 30%다.
- [ ] 52주 고점 근접도 또는 6개월 모멘텀이 상위 30%다.
- [ ] 총발생액, 영업발생액, 신주발행 증가율이 과도하지 않다.
```

### 7.2 매수하지 말아야 할 종목

아래 중 하나라도 해당하면 점수가 높아 보여도 매수하지 않는다.

```yaml
never_buy:
  - 테마성 급등 후 거래회전율 폭증
  - 최근 한 달 안에 20% 이상 급등 일봉 발생
  - 영업현금흐름이 지속적으로 음수
  - 매출채권이 매출보다 빠르게 증가
  - 유상증자 또는 전환사채 발행이 반복됨
  - 관리종목 지정 가능성이 있음
  - 호가 스프레드가 넓고 체결량이 얇음
  - 최대주주·감사의견·상장폐지 관련 불확실성이 큼
```

### 7.3 보유 중 점검

```yaml
weekly_monitoring:
  price_risk:
    - 종목별 급락률
    - 거래대금 급증
    - 변동성 급증
  event_risk:
    - 유상증자
    - 전환사채
    - 감사의견
    - 실적 쇼크
    - 관리종목 지정 가능성
  factor_risk:
    - score_rank 하락
    - turnover_rank 상승
    - ivol_rank 상승
    - accrual_rank 상승
```

---

## 8. 시장 국면별 적용법

### 8.1 강세장

강세장에서는 모멘텀 비중을 20%에서 25%까지 올린다.

```yaml
bull_market_weight:
  valuation_cashflow: 30
  low_risk_liquidity: 20
  momentum: 25
  accounting_quality: 10
  intangible_quality: 15
```

중요 법칙:

- 52주 고점 모멘텀
- 6개월 모멘텀
- R&D/시총
- 광고비/시총
- 영업현금흐름/시총

주의:

- 강세장 후반에는 거래회전율과 최대 일일수익률이 급증한 종목을 반드시 제외한다.

---

### 8.2 약세장

약세장에서는 저위험·회계품질 비중을 높인다.

```yaml
bear_market_weight:
  valuation_cashflow: 35
  low_risk_liquidity: 35
  momentum: 10
  accounting_quality: 15
  intangible_quality: 5
```

중요 법칙:

- 고유변동성 낮음
- 총변동성 낮음
- 발생액 낮음
- 신주발행 낮음
- 영업현금흐름/시총 높음

주의:

- 약세장에서는 단순 저PBR보다 현금흐름이 있는 저PBR을 우선한다.

---

### 8.3 횡보장

횡보장에서는 가치+품질+저변동성 조합이 가장 안정적이다.

```yaml
sideways_market_weight:
  valuation_cashflow: 40
  low_risk_liquidity: 30
  momentum: 10
  accounting_quality: 10
  intangible_quality: 10
```

중요 법칙:

- OCP
- BM
- SP
- IVOL 낮음
- Turnover 낮음
- PTA 낮음

---

## 9. 한국시장 특화 해석

### 9.1 저PBR은 단독 매수 사유가 아니다

한국시장에서는 B/M, BMJ, AM, EBP가 통계적으로 강하게 나타났지만, 저PBR만으로 매수하면 가치 함정에 빠질 수 있다. 다음 조건을 함께 확인한다.

```yaml
value_trap_filter:
  avoid_if:
    - 영업현금흐름 음수
    - 매출 감소 지속
    - 부채비율 급등
    - 신주발행 증가
    - 총발생액 증가
    - 52주 고점 대비 과도한 하락 후 회복 없음
```

**좋은 저PBR**

- 영업현금흐름이 양호하다.
- 매출/시총이 높다.
- 총발생액이 낮다.
- 6개월 모멘텀 또는 52주 고점 근접도가 살아 있다.

**나쁜 저PBR**

- 싸지만 계속 싸지는 기업
- 현금흐름이 없는 기업
- 자본조달로 버티는 기업
- 매출채권과 재고가 과도하게 늘어나는 기업

---

### 9.2 모멘텀은 “과열 없는 모멘텀”만 산다

한국시장에서 6개월 모멘텀과 52주 고점 모멘텀은 유효했지만, 동시에 최대 일일수익률이 큰 복권형 종목은 이후 약했다.

따라서 매수 가능한 모멘텀은 다음과 같다.

```yaml
good_momentum:
  - 52주 고점에 가까움
  - 최근 6개월 수익률 양호
  - 일간 급등이 아니라 완만한 상승
  - 거래회전율이 과도하지 않음
  - 변동성이 낮거나 중간 이하
```

매수하면 안 되는 모멘텀은 다음과 같다.

```yaml
bad_momentum:
  - 하루 또는 며칠 만에 급등
  - 거래대금 폭증
  - 회전율 폭증
  - 뉴스·테마 의존
  - 고유변동성 급등
```

---

### 9.3 R&D와 광고비는 “저평가된 무형자산”일 때만 좋다

R&D/시총, 광고비/시총이 높은 기업은 통계적으로 우수했지만, 이 신호는 단독으로 쓰면 위험하다.

좋은 조합:

```yaml
intangible_good_combo:
  - R&D/시총 높음
  - 광고비/시총 높음
  - 매출 성장
  - 영업현금흐름 개선
  - 주식 발행 과도하지 않음
  - 52주 고점 모멘텀 양호
```

나쁜 조합:

```yaml
intangible_bad_combo:
  - R&D만 많고 매출 없음
  - 광고비만 많고 현금흐름 악화
  - 유상증자 반복
  - 고변동성
  - 테마주 급등
```

---

### 9.4 부채/시총 DM은 조심해서 쓴다

DM은 통계적으로 양호하게 나타났지만, 실전에서는 재무위험과 연결될 수 있다. 따라서 다음 조건을 통과할 때만 보조 점수로 사용한다.

```yaml
debt_signal_allowed_if:
  - 이자보상배율 양호
  - 영업현금흐름 양수
  - 만기 구조 안정
  - 유동비율 과도하게 낮지 않음
  - 주식 발행으로 부채를 메우는 구조가 아님
```

---

## 10. 포트폴리오 예시

### 10.1 균형형 한국주식 팩터 포트폴리오

```yaml
portfolio_type: balanced_factor
number_of_holdings: 25
rebalance: monthly
position_weight:
  equal_weight: true
  max_single_name: 5%
selection:
  - universe 통과
  - defensive_filter 통과
  - FinalScore 상위 20%
  - OCP, BM, 52w, IVOL, Turnover 중 3개 이상 우수
risk_overlay:
  max_sector_weight: 25%
  max_kosdaq_weight: 40%
  cash_buffer: 10%
```

### 10.2 보수형 저변동성 가치 포트폴리오

```yaml
portfolio_type: conservative_low_vol_value
number_of_holdings: 30~50
rebalance: monthly_or_quarterly
selection_focus:
  - OCP 높음
  - BM 높음
  - SP 높음
  - IVOL 낮음
  - TVOL 낮음
  - PTA 낮음
avoid:
  - KOSDAQ 과소유동성
  - 고회전율
  - 급등 테마주
  - 신주발행 기업
```

### 10.3 공격형 모멘텀+가치 포트폴리오

```yaml
portfolio_type: aggressive_momentum_value
number_of_holdings: 15~20
rebalance: monthly
selection_focus:
  - 52주 고점 근접도 높음
  - 6개월 모멘텀 높음
  - OCP 높음
  - BM 또는 SP 높음
  - MDR 낮음
  - Turnover 과열 없음
risk_overlay:
  max_single_name: 5%
  stop_new_buy_if_market_drawdown: -10%
```

---

## 11. 백테스트 프로토콜

실전 적용 전 아래 조건으로 반드시 검증한다.

```yaml
backtest:
  universe:
    - KOSPI
    - KOSDAQ
  period:
    start: 2000-01
    end: 최신 가능 시점
  rebalance:
    frequency: monthly
  weighting:
    primary: equal_weight_after_liquidity_filter
    robustness: value_weight
  transaction_cost:
    base_case: 0.30% per trade
    conservative_case: 0.50% per trade
  slippage:
    use_avg_daily_trading_value_cap: true
    max_participation_rate: 10% of ADV
  benchmark:
    - KOSPI
    - KOSDAQ
    - KOSPI200
    - KRX300
  metrics:
    - CAGR
    - volatility
    - Sharpe
    - max_drawdown
    - hit_rate_vs_benchmark
    - annual_turnover
    - monthly_turnover
    - worst_month
    - worst_year
```

### 11.1 반드시 해봐야 할 강건성 검정

```yaml
robustness_tests:
  - KOSPI only
  - KOSDAQ only
  - 대형주 only
  - 중형주 only
  - 소형주 only
  - 금융업 포함/제외 비교
  - 거래비용 0.3%, 0.5%, 1.0% 비교
  - 동일가중 vs 가치가중 비교
  - 2000~2009, 2010~2019, 2020~현재 구간 분리
  - 코로나 이후 구간 분리
  - 시가총액 하한 500억, 1000억, 2000억 비교
  - 평균 거래대금 하한 5억, 10억, 20억 비교
```

---

## 12. 자동화용 의사코드

```python
# 1. 데이터 로드
prices = load_daily_price_data()
fundamentals = load_financial_statement_data()
universe = load_listed_companies()

# 2. 유니버스 필터
universe = universe[
    (universe["is_common_stock"] == True) &
    (universe["is_financial"] == False) &
    (universe["is_spac"] == False) &
    (universe["is_etf"] == False) &
    (universe["is_reit"] == False) &
    (universe["market_cap"] >= 100_000_000_000) &
    (universe["avg_dtv_20d"] >= 1_000_000_000) &
    (universe["months_since_listing"] >= 12) &
    (universe["capital_impairment_flag"] == False) &
    (universe["trading_halt_flag"] == False)
]

# 3. 팩터 계산
factors = calculate_factors(prices, fundamentals, universe)

# 4. 이상치 처리
factors = winsorize(factors, lower=0.01, upper=0.99)

# 5. 방향성 반영 percentile 점수
factors["OCP_score"] = percentile_rank(factors["OCP"])
factors["BM_score"] = percentile_rank(factors["BM"])
factors["SP_score"] = percentile_rank(factors["SP"])
factors["IVOL_score"] = 1 - percentile_rank(factors["IVOL"])
factors["TVOL_score"] = 1 - percentile_rank(factors["TVOL"])
factors["TURNOVER_score"] = 1 - percentile_rank(factors["TURNOVER"])
factors["MDR_score"] = 1 - percentile_rank(factors["MDR"])
factors["PTA_score"] = 1 - percentile_rank(factors["PTA"])
factors["CEI_score"] = 1 - percentile_rank(factors["CEI"])
factors["HIGH52_score"] = percentile_rank(factors["HIGH52"])
factors["MOM6_score"] = percentile_rank(factors["MOM6"])
factors["RDM_score"] = percentile_rank(factors["RDM"])
factors["ADM_score"] = percentile_rank(factors["ADM"])

# 6. 클러스터 점수
factors["ValuationCashflowScore"] = weighted_mean([
    factors["OCP_score"],
    factors["BM_score"],
    factors["SP_score"]
], weights=[0.45, 0.35, 0.20])

factors["LowRiskLiquidityScore"] = weighted_mean([
    factors["IVOL_score"],
    factors["TVOL_score"],
    factors["TURNOVER_score"],
    factors["MDR_score"]
], weights=[0.35, 0.20, 0.25, 0.20])

factors["MomentumScore"] = weighted_mean([
    factors["HIGH52_score"],
    factors["MOM6_score"]
], weights=[0.60, 0.40])

factors["AccountingQualityScore"] = weighted_mean([
    factors["PTA_score"],
    factors["CEI_score"]
], weights=[0.60, 0.40])

factors["IntangibleQualityScore"] = weighted_mean([
    factors["RDM_score"],
    factors["ADM_score"]
], weights=[0.60, 0.40])

# 7. 최종 점수
factors["FinalScore"] = (
    0.35 * factors["ValuationCashflowScore"] +
    0.25 * factors["LowRiskLiquidityScore"] +
    0.20 * factors["MomentumScore"] +
    0.10 * factors["AccountingQualityScore"] +
    0.10 * factors["IntangibleQualityScore"]
)

# 8. 방어 필터
candidates = factors[
    (factors["IVOL_rank"] < 0.80) &
    (factors["TVOL_rank"] < 0.80) &
    (factors["TURNOVER_rank"] < 0.80) &
    (factors["MDR_rank"] < 0.80) &
    (factors["PTA_rank"] < 0.80) &
    (factors["CEI_rank"] < 0.80)
]

# 9. 최종 선별
portfolio = candidates.sort_values("FinalScore", ascending=False).head(25)

# 10. 비중 산출
portfolio["target_weight"] = min(1 / len(portfolio), 0.05)
```

---

## 13. 월간 운용 루틴

### 월말 D-3

```markdown
- [ ] 가격 데이터 업데이트
- [ ] 거래대금·회전율·변동성 계산
- [ ] 52주 고점 및 6개월 모멘텀 계산
- [ ] 관리종목·거래정지·감사의견 위험 업데이트
```

### 월말 D-2

```markdown
- [ ] 재무제표 데이터 업데이트
- [ ] OCP, BM, SP, CP, AM 계산
- [ ] 발생액, 운전자본, 신주발행 지표 계산
- [ ] R&D/시총, 광고비/시총 계산
```

### 월말 D-1

```markdown
- [ ] 전체 종목 점수화
- [ ] 상위 10%, 상위 20% 후보군 확인
- [ ] 기존 보유 종목 점수 하락 여부 확인
- [ ] 신규 편입 후보의 유동성·호가 확인
```

### 리밸런싱 당일

```markdown
- [ ] 강제 매도 종목 먼저 정리
- [ ] 점수 하락 종목 교체
- [ ] 신규 편입 종목 분할 매수
- [ ] 종목별 5% 초과 금지
- [ ] 업종별 25% 초과 금지
- [ ] KOSDAQ 40% 초과 금지
```

---

## 14. 투자 판단 문장 템플릿

종목 검토 시 아래 형식으로 한 문단 요약을 작성한다.

```markdown
[종목명]은 OCP/BM/SP 기준으로 가치 점수가 높고, 52주 고점 근접도와 6개월 모멘텀이 양호하다. 동시에 IVOL, Turnover, MDR이 상위권이 아니어서 복권형 급등주 위험은 낮다. PTA와 CEI도 과도하지 않아 회계 품질과 희석 위험이 관리된다. 따라서 월간 리밸런싱 기준으로 신규 편입 또는 보유 유지가 가능하다.
```

매수 금지 판단은 아래처럼 쓴다.

```markdown
[종목명]은 최근 수익률은 높지만 MDR, Turnover, IVOL이 동시에 급등했다. 이는 52주 고점 모멘텀이 아니라 복권형 급등주 성격에 가깝다. OCP와 PTA도 좋지 않아 통계 법칙상 매수 후보에서 제외한다.
```

---

## 15. 핵심 결론

한국주식시장 anomaly를 실제 투자에 적용할 때 가장 중요한 결론은 다음이다.

1. **고변동성 종목을 피한다.**
2. **거래회전율이 폭증한 종목을 피한다.**
3. **최근 대박 일봉이 나온 복권형 급등주를 피한다.**
4. **영업현금흐름/시총이 높은 종목을 선호한다.**
5. **B/M, 자산/시총, 매출/시총이 높은 가치주를 선호한다.**
6. **총발생액, 영업발생액, 재량발생액이 높은 기업을 피한다.**
7. **신주발행이 많은 기업을 피한다.**
8. **52주 고점에 가까운 종목을 선호하되, 과열 거래가 동반되면 제외한다.**
9. **R&D/시총, 광고비/시총이 높은 무형자산 투자 기업을 보조적으로 선호한다.**
10. **마이크로캡 효과는 그대로 믿지 말고 유동성 하한을 둔다.**

최종적으로 매수할 종목은 다음 문장을 만족해야 한다.

> **싸다. 현금흐름이 있다. 회계 이익의 질이 나쁘지 않다. 변동성이 낮다. 거래가 과열되지 않았다. 복권형 급등주가 아니다. 추세는 살아 있다.**

---

## 16. 참고 문헌

1. Han, Minyeon, Dong-Hyun Lee, and Hyoung-Goo Kang. 2020. *Market Anomalies in the Korean Stock Market*. Journal of Derivatives and Quantitative Studies, 28(2), 159-228. DOI: 10.1108/JDQS-03-2020-0004.  
   - KCI: https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002608852
   - Emerald: https://www.emerald.com/jdqs/article/28/2/3/206237/Market-anomalies-in-the-Korean-stock-market

2. Kang, Hankil, Jangkoo Kang, and Wooyeon Kim. 2019. *A Comparison of New Factor Models in the Korean Stock Market*. Asia-Pacific Journal of Financial Studies, 48(5), 593-614. DOI: 10.1111/ajfs.12274.

---

## 17. 한 장 요약

```yaml
buy:
  - OCP 높음
  - BM 높음
  - SP 높음
  - CP 높음
  - 52주 고점 근접도 높음
  - 6개월 모멘텀 높음
  - R&D/시총 높음
  - 광고비/시총 높음
  - 상장 연령 길음

avoid:
  - IVOL 높음
  - TVOL 높음
  - Turnover 높음
  - MDR 높음
  - PTA 높음
  - OA 높음
  - PDA 높음
  - CEI 높음
  - dWC 높음
  - 거래대금·회전율 동반 폭증

portfolio:
  - 20~35종목
  - 월간 리밸런싱
  - 종목당 최대 5%
  - 업종당 최대 25%
  - KOSDAQ 최대 40%
  - 평균 거래대금 10억원 이상
  - 시가총액 1,000억원 이상
```
