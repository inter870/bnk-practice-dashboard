# Korean UI Readability Checklist

Use this checklist before deploying dashboard UI changes.

## Korean-First Labels

- All priority module titles are Korean-first.
- Standard abbreviations remain English where Korean investors expect them: KOSPI, KOSDAQ, KRX, OpenDART, DART, ECOS, KOSIS, FRED, USD/KRW, PER, PBR, EV/EBITDA, ROE, ROA, ROIC, EPS, FCF, ETF, API.
- Major labels, table headers, buttons, tabs, filters, alerts, empty states, loading states, error states, and stale states are Korean.
- Source metadata labels are readable: 출처, 기준일, 수집 시각, 오래된 데이터, 누락 데이터.
- Internal enum keys are not shown directly when a Korean display label exists.

## Korean Market Colors

- Positive market movement, returns, gains, net buy, upside alpha, and favorable directional deltas are red.
- Negative market movement, losses, drawdowns, net sell, downside alpha, and unfavorable directional deltas are blue.
- Flat or neutral values are slate/gray.
- High risk, stale data, warning, critical, and error states use severity colors instead of raw market direction colors.
- Important states include signs or labels, not color alone.

## Dark UI Readability

- No black or near-black text appears on dark cards.
- Primary labels and KPI values use readable contrast.
- Source metadata is muted but still legible.
- Stale data flags are visually noticeable.
- Loading, empty, error, warning, and critical states are readable.

## Layout

- Korean headings use comfortable line-height and do not overflow.
- Badges and buttons have enough padding for Korean labels.
- Financial values use tabular numbers.
- Numeric table columns are right-aligned where practical.
- Wide tables scroll horizontally instead of clipping.
- Tooltips and popovers wrap Korean text and are not clipped.
- Chart axes, legends, and labels remain readable on the dark background.
- Mobile layout stacks cards without left-right shaking or clipping.

## Module Preservation

- 포트폴리오 리스크 종합 현황
- 데이터 신뢰도·출처
- 시장 국면·매크로 레이더
- 원화·금리·환율
- 밸류에이션·상대 저평가
- 펀더멘털 품질
- DART 공시 촉매
- 수급·공매도 압력
- 미래 알파 랭킹
- 포트폴리오 최적화·알림센터

All modules above must remain present after localization or color fixes.
