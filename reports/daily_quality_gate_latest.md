# Analista - daily quality gate

- generated_at: 2026-06-10T23:01:50
- status: FAIL
- manual_review_allowed: False
- manual_review_mode: BLOCKED

## Decision gate

- Estado FAIL: no usar esta corrida para revisión manual hasta corregir errores.

## Componentes

- daily_validation: FAIL
- project_preflight: WARN
- daily_run_manifest: FAIL
- reports_cleanup: PASS
- encoding_audit: PASS

## Scan snapshot

- latest_scan_rows: 362
- manual_review_rows: 45

Signals:
- VETO: 263
- AVOID: 54
- WATCHLIST: 45

Recommendations:
- WATCHLIST_MONITOR: 30
- RECHECK_LIVE_QUOTE: 15

Quote status:
- VALID: 150
- MISSING: 139
- STALE_POSSIBLE: 53
- INVALID: 20

Execution quote quality:
- LOW: 212
- HIGH: 150

## Logical checks

- disabled_buy_signal_rows: 0
- trigger_with_low_quote_rows: 0
- no_valid_setup_not_veto_rows: 0
- veto_with_actionable_levels_rows: 0
- manual_recheck_quote_rows: 15

## Issues

| severity | source | message |
| --- | --- | --- |
| FAIL | daily_validation_summary.txt | daily_validation terminó en FAIL. |
| WARN | project_preflight | project_preflight terminó en WARN. |
| WARN | daily_run_manifest | daily_run_manifest terminó en FAIL; revisar trazabilidad. |
| WARN | latest_scan_audited.csv | Hay candidatos que requieren RECHECK_LIVE_QUOTE antes de revisión operativa. |

## Archivos críticos

| path | exists | size_bytes | modified |
| --- | --- | --- | --- |
| reports/daily_validation_summary.txt | True | 21823 | 2026-06-10T23:01:46 |
| reports/project_preflight_latest.json | True | 5249 | 2026-06-10T23:01:42 |
| reports/latest_scan_audited.csv | True | 783379 | 2026-06-10T21:56:47 |
| reports/manual_review_latest.csv | True | 32787 | 2026-06-10T23:00:57 |

## Archivos de soporte

| path | exists | size_bytes | modified |
| --- | --- | --- | --- |
| reports/daily_run_manifest_latest.json | True | 17238 | 2026-06-10T23:01:47 |
| reports/encoding_audit_latest.json | True | 127752 | 2026-06-10T23:01:50 |
| reports/reports_cleanup_latest.json | True | 199 | 2026-06-10T23:01:46 |
| reports/daily_operator_index.md | True | 7512 | 2026-06-10T23:01:47 |
| reports/manual_review_top.csv | True | 18754 | 2026-06-10T23:00:57 |
| reports/manual_review_top.md | True | 10495 | 2026-06-10T23:00:57 |