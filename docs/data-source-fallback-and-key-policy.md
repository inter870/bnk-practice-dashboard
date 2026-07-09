# Data Source Fallback And Key Policy

This dashboard never bypasses authentication, never fabricates exact-looking values, and never marks mock, planned, or cached data as official real-time data.

## Authentication Policy

- KIS broker APIs require `KIS_APP_KEY` and `KIS_APP_SECRET`.
- OpenDART financial statements and disclosures require `OPENDART_API_KEY`. `DART_API_KEY` and `OPEN_DART_API_KEY` are accepted as aliases for local compatibility.
- BOK ECOS requires `BOK_ECOS_API_KEY`. `ECOS_API_KEY`, `ECOS_AUTH_KEY`, and `BANK_OF_KOREA_API_KEY` are accepted as aliases for local compatibility.
- KOSIS requires `KOSIS_API_KEY` when the adapter is connected.
- Public Data Portal sources require `PUBLIC_DATA_API_KEY` when used.
- Secret values must never be printed, logged, rendered, or committed.

## Keyless Sources

Keyless sources may be used only when legally available and enabled:

- Manual portfolio holdings entered by the user
- Mock portfolio holdings only in explicit demo/mock mode
- Naver Finance snapshot when the adapter is enabled and allowed
- FinanceDataReader when the adapter is enabled and allowed
- KRX public downloads only when legally implemented

Naver Finance and FinanceDataReader must not show `KIS_APP_KEY` or `KIS_APP_SECRET` as missing because they do not require KIS authentication.

## Fallback Priority

Portfolio holdings:

1. Broker holdings with user-provided keys
2. Manual user-entered holdings
3. Imported CSV holdings
4. Last-known-good holdings cache
5. Mock holdings only when demo/mock mode is enabled

Market price:

1. Broker real-time API with valid keys
2. Official public API with valid key
3. KRX public EOD adapter when legally implemented
4. Naver Finance or FinanceDataReader public snapshot
5. Last-known-good cache with stale label
6. Unavailable

Valuation:

1. KRX official valuation adapter when implemented
2. OpenDART financial statements plus market cap derived valuation when keys and price source exist
3. Cached valuation
4. Planned/unavailable

Financial statements:

1. OpenDART with valid key
2. Cached OpenDART data
3. User-uploaded statements if supported
4. Unavailable

DART disclosures:

1. OpenDART with valid key
2. Cached disclosure list
3. Unavailable

Macro:

1. BOK ECOS with valid key
2. KOSIS with valid key
3. Public official cached macro
4. FRED/global proxy if configured
5. Cache
6. Unavailable

FX and rates:

1. Official or broker source if available
2. Public keyless source if legally available
3. FinanceDataReader/Naver Finance snapshot if implemented
4. Cache
5. Unavailable

Investor flow and short selling:

1. KRX official/public adapter when implemented
2. Lawful public wrapper if already used and allowed
3. Cache
4. Planned/unavailable

## Accuracy Labels

- 공식 원천값: official source with complete timestamp metadata
- 공식 일마감값: official EOD source
- 증권사 원천값: broker source with user-provided credentials
- 공개 스냅샷: public web snapshot such as Naver Finance
- 계산값: derived from multiple timestamped sources
- 캐시값: last-known-good cache
- 수동 입력값: user-entered holdings or statements
- 모의값: demo/mock data
- 표시 불가: no reliable legal source

## UI Rules

- Planned adapters show `어댑터 미연결` or `연결 예정`, not `누락 키 없음`.
- Keyless active sources show `필요 키 없음` or `키 없이 공개 데이터 사용 중`.
- Key-required active sources show only the missing key names.
- Cached values show cache/stale labels and age when available.
- Mock values show mock labels and low confidence.
- Every Data Trust row must show source, endpoint, status, accuracy grade, confidence, 기준일, 수집 시각, stale/missing status, and a Korean message.

## Troubleshooting

- If KIS keys appear on a Naver Finance row, the active source registry mapping is wrong.
- If OpenDART shows connected without a key, check `OPENDART_API_KEY`, `DART_API_KEY`, or `OPEN_DART_API_KEY`.
- If BOK ECOS shows missing even with a key, check `BOK_ECOS_API_KEY`, `ECOS_API_KEY`, `ECOS_AUTH_KEY`, or `BANK_OF_KOREA_API_KEY`.
- If a planned KRX adapter shows `필요 키 없음` as if complete, mark it as `adapter_missing` or `planned`.
