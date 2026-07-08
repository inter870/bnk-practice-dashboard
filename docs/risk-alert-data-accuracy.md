# Risk Alert Data Accuracy

This dashboard treats portfolio risk alerts as review gates, not trading instructions.

## Required Data

Single-stock concentration needs actual holding quantity, latest or current price, and total portfolio value.

Sector concentration needs holding value plus sector mapping.

Cash buffer needs actual cash balance and total portfolio value.

Top-10 concentration needs holding market values for the portfolio.

Stale data checks need source metadata with `as_of_date`, `fetched_at`, and `stale_data_flag`.

Volatility and drawdown need a historical portfolio value series. If it is unavailable, the UI must show `계산 불가` or an explanatory empty state instead of a fake proxy.

## Actionability

`actionable` means holdings are real/manual/imported/broker-based and market prices are fresh enough for review.

`example_only` means holdings are mock/demo data. The UI must show `예시 알림` and `모의 데이터`, not a real urgent alert.

`blocked_by_stale_data` means prices or metadata are stale. The UI must show `오래된 데이터` and ask the user to refresh before using the alert.

`review_only` means the alert is useful context but should not be treated as a fully actionable investment risk.

## Source Metadata

Risk alert source display must separate:

- `보유`: holdings source
- `가격`: price source
- `섹터`: sector metadata source when relevant
- `계산`: calculation method

Timestamps must be shown in Asia/Seoul format:

`수집: 2026.07.08 16:55`

Raw ISO timestamps such as `2026-07-08T07:55:27+00:00` must not be visible in the risk alert UI.

## Korean Message Examples

Single-stock concentration:

`SK하이닉스 비중은 26.2%로 기준치 10.0%를 초과했습니다.`

Mock single-stock concentration:

`SK하이닉스 비중은 26.2%로 표시되지만 현재 보유 데이터는 모의 데이터입니다.`

Cash buffer:

`현금 비중은 0.0%로 최소 기준 3.0%보다 낮습니다.`

Stale data:

`일부 가격 또는 메타데이터가 신선도 기준보다 오래되었습니다.`
