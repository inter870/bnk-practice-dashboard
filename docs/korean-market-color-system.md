# Korean Market Color System

Stance Stock Strategy follows Korean stock-market color convention for market-direction numbers.

## Core Rule

- 상승, 수익, 플러스, 초과수익, 순매수, 우호적 알파: red family
- 하락, 손실, 마이너스, 낙폭, 순매도, 부정적 알파: blue family
- 보합, 중립, 변화 없음: neutral slate/gray

## Tokens

- `market-up`: `#FF4D4F`
- `market-up-strong`: `#FF1F3D`
- `market-down`: `#3B82F6`
- `market-down-strong`: `#2563EB`
- `market-flat`: `#CBD5E1`
- `market-neutral`: `#94A3B8`
- `risk-critical`: `#F97316`
- `risk-warning`: `#FCD34D`
- `system-error`: `#FB7185`

## Exceptions

- High risk, severe risk override, delisting risk, accounting risk: warning or critical severity color
- Stale data: warning color
- System or API error: error color
- Source metadata: muted text color
- Disabled controls: disabled text color
- Absolute valuation multiples such as PER/PBR: neutral unless explicitly shown as directional attractiveness or change
- Interest-rate and FX increases: contextual warning/info colors unless interpreted as a direct portfolio tailwind/headwind

## Examples

- `+3.2% 상승`: red
- `-1.1% 하락`: blue
- `외국인 순매수 +123억`: red
- `외국인 순매도 -87억`: blue
- `공매도 압력 높음`: warning/critical
- `금리 부담 확대`: warning
- `오래된 데이터`: warning

## Accessibility

Do not rely on color alone. Important states should also include a sign, Korean label, badge text, icon, or accessible label where the UI supports it.

## Developer Usage

- Use `src/ui/korean_market_colors.py` helpers for directional colors.
- Use market color classes for returns, price changes, net flow, and alpha deltas.
- Use risk severity classes for stale data, errors, high-risk overrides, and alerts.
- Do not reintroduce the global convention of green positive returns and red negative returns in Korean dashboard UI.
