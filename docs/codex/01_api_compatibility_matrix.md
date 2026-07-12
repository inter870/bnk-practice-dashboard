# API Compatibility Matrix

| Provider | Existing credential aliases | P0 behavior | Compatibility |
|---|---|---|---|
| KIS Open API | `KIS_APP_KEY`, `KIS_APP_SECRET` | Existing adapter retained | No endpoint or secret rename |
| OpenDART | `OPENDART_API_KEY`, `DART_API_KEY`, `OPEN_DART_API_KEY` | Existing adapter retained | Receipt/availability-time rule retained |
| BOK ECOS | `ECOS_API_KEY`, `ECOS_AUTH_KEY`, `BOK_ECOS_API_KEY`, `BANK_OF_KOREA_API_KEY` | Existing adapter retained | No endpoint or secret rename |
| Naver Finance | none | Existing public fallback retained | Must not be labeled official realtime |
| FinanceDataReader | none | Existing fallback retained | Must carry fallback/stale metadata |
| OpenAI | `OPENAI_API_KEY` | Existing briefing adapter retained | Shared file save disabled by default |

P0 adds no endpoint, authentication bypass, paid provider, or order API. Environment
loading continues through `src/config/env.py`. Secret values must never be included
in UI errors, persisted metadata, or documentation.

