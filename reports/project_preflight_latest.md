# Analista - project preflight

- generated_at: 2026-06-11T01:04:55
- status: WARN
- root: `C:/Users/El otro Yo/Projects/ChatGPT/Analista`
- cwd: `C:/Users/El otro Yo/Projects/ChatGPT/Analista`
- cwd_matches_root: True
- python_executable: `C:\Python314\python.exe`
- virtual_env: ``

## Decision gate

- Estado WARN: el flujo puede ejecutarse, pero hay advertencias operativas.
- Hay reportes opcionales faltantes.

## Required dirs

| path | exists | is_dir | modified |
| --- | --- | --- | --- |
| tools | True | True | 2026-06-10T23:07:34 |
| tests | True | True | 2026-06-10T21:45:39 |
| reports | True | True | 2026-06-10T23:51:37 |

## Required files

| path | exists | is_file | size_bytes | modified |
| --- | --- | --- | --- | --- |
| tools/daily_validation.py | True | True | 25029 | 2026-06-10T20:49:13 |
| tools/daily_operator_index.py | True | True | 30405 | 2026-06-10T23:07:03 |
| tools/reports_cleanup.py | True | True | 9150 | 2026-06-10T13:35:47 |

## Optional files

| path | exists | is_file | size_bytes | modified |
| --- | --- | --- | --- | --- |
| config.yaml | True | True | 7629 | 2026-06-08T12:56:51 |
| reports/latest_scan_audited.csv | True | True | 783379 | 2026-06-10T21:56:47 |
| reports/latest_scan_audited.json | True | True | 2268078 | 2026-06-10T21:56:47 |
| reports/manual_review_latest.csv | True | True | 32785 | 2026-06-10T23:35:26 |
| reports/manual_review_latest.md | True | True | 19748 | 2026-06-10T23:35:26 |
| reports/manual_review_top.csv | True | True | 18754 | 2026-06-10T23:35:26 |
| reports/manual_review_top.md | True | True | 10495 | 2026-06-10T23:35:26 |
| reports/daily_validation_summary.txt | True | True | 24346 | 2026-06-10T23:35:26 |
| reports/daily_operator_index.md | True | True | 7638 | 2026-06-10T23:52:58 |
| reports/reports_cleanup_latest.json | True | True | 199 | 2026-06-10T23:35:19 |
| reports/reports_cleanup_latest.md | True | True | 561 | 2026-06-10T23:35:19 |
| reports/open_trades_snapshot_latest.csv | False | False | 0 |  |
| reports/open_trades_snapshot_latest.md | False | False | 0 |  |
| reports/trade_outcome_analytics_latest.csv | True | True | 199 | 2026-06-10T23:35:19 |
| reports/trade_outcome_analytics_latest.md | True | True | 136 | 2026-06-10T23:35:19 |

## Write checks

| path | exists | is_dir | writeable | error |
| --- | --- | --- | --- | --- |
| C:\Users\El otro Yo\Projects\ChatGPT\Analista\reports | True | True | True |  |

## Summary

- missing_required_dirs: 0
- missing_required_files: 0
- missing_optional_files: 2
- failed_write_checks: 0