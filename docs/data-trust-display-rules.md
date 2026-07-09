# Data Trust Display Rules

Data Trust UI is a normal investor-facing dashboard surface. It must be Korean-first, readable in dark mode, and must not expose raw internal metadata unless the view is explicitly a developer/debug view.

## Key Status Matrix

| Source state | Display status | Key display | Do not display |
| --- | --- | --- | --- |
| Planned adapter or missing adapter | `연결 예정` or `어댑터 미연결` | `키 확인: 어댑터 구현 후 확인` | `필요 키 없음`, `누락 없음`, `누락 키: 없음` |
| Active keyless source | `사용 가능` or source-specific status | `필요 키: 없음` or `키 없이 공개 데이터 사용 중` | `누락 없음` |
| Active source with missing required keys | `키 필요` | `누락 키: {KEY_NAMES}` | Secret values |
| Active source with all required keys present | `사용 가능` or source-specific status | `필요 키: 설정됨` | `누락 없음` |
| Optional keys missing | Source-specific status | `선택 키 미설정: {KEY_NAMES}` | Required-key warning styling unless required keys are missing |

## Planned Adapter Rule

For `source_type == "planned"`, `status == "planned"`, `status == "adapter_missing"`, `adapter_id` starting with `planned:`, or rows marked as planned/missing adapters:

- Status badge: `연결 예정`
- Accuracy badge: `표시 불가`
- Confidence: `신뢰도 N/A`
- As-of date: `기준일: 해당 없음`
- Key status: `키 확인: 어댑터 구현 후 확인`
- Message example: `밸류에이션 어댑터가 아직 연결되지 않아 정확 수치를 표시할 수 없습니다.`

Planned adapters must not look healthy and must not show exact or official values.

## Timestamp Formatting

Normal dashboard UI must not show raw ISO timestamps.

- Convert UTC timestamps to Asia/Seoul.
- Display as `YYYY.MM.DD HH:mm`.
- Missing timestamp: `수집 시각: 확인 불가`
- Invalid timestamp: `수집 시각: 형식 오류`

Example:

- Bad: `수집 시각 2026-07-08T08:39:17+00:00`
- Good: `수집 시각: 2026.07.08 17:39`

## Good And Bad Examples

Bad:

`밸류에이션 어댑터가 아직 연결되지 않아 정확 수치를 표시할 수 없습니다. · 어댑터 구현 후 필요한 키를 다시 확인하세요. · 수집 시각 2026-07-08T08:39:17+00:00 · 필요 키 필요 키 없음 · 누락 없음`

Good:

`밸류에이션 어댑터가 아직 연결되지 않아 정확 수치를 표시할 수 없습니다. · 키 확인: 어댑터 구현 후 확인 · 수집 시각: 2026.07.08 17:39`

## Audit

Run:

```powershell
python scripts/check_data_trust_display.py
```

The audit checks generated Data Trust HTML for duplicate key labels, misleading `누락 없음`, visible raw ISO timestamps, and untranslated adapter-planned text. Planned adapters may show `신뢰도 N/A` because exact confidence cannot be evaluated before the adapter is implemented.
