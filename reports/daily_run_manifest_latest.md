# Analista - daily run manifest

- generated_at: 2026-06-11T01:17:26
- status: FAIL
- root: `C:/Users/El otro Yo/Projects/ChatGPT/Analista`
- cwd: `C:/Users/El otro Yo/Projects/ChatGPT/Analista`
- python_executable: `C:\Python314\python.exe`
- virtual_env: ``

## Decision gate

- Estado FAIL: no usar esta corrida operativamente hasta corregir errores.

## Core statuses

- daily_validation: FAIL
- project_preflight: WARN
- reports_cleanup: PASS / mode=DRY_RUN
- cleanup_candidate_count: 0
- cleanup_moved_count: 0

## Git

- available: True
- branch: `main`
- commit: `7bec19f160d0cbb456ab0302dfd853189e7ea7bb`
- dirty: True

```text
M reports/daily_operator_index.md
 M reports/daily_quality_gate_latest.md
 M reports/daily_run_manifest_latest.md
 M reports/daily_validation_summary.txt
 M reports/encoding_audit_latest.md
 M reports/history_evolution_latest.md
 M reports/manual_review_latest.md
 M reports/project_preflight_latest.md
 M reports/reports_cleanup_latest.md
 M reports/setup_persistence_latest.md
 M reports/trade_outcome_analytics_latest.md
?? reports/daily_operator_index.md.bak2
?? reports/daily_operator_index.md.new2
?? temp_content.txt
```

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

Quote recheck priority:
- Sin datos.

## Script files

| path | exists | size_bytes | modified | sha256 |
| --- | --- | --- | --- | --- |
| run_scanner_audited.py | True | 3877 | 2026-06-09T13:13:25 | ca4ffb1f7eea06bfcb34bc2f817f616dba97a5fa22023473075999a29f7d93a9 |
| validate_latest_scan_p0.py | True | 3657 | 2026-06-08T07:35:49 | 49412f6dae813960838755cce7ba993aeff39baf5bec6ac4810acc7eb50cb6a0 |
| tools/daily_validation.py | True | 25029 | 2026-06-10T20:49:13 | ae22b71744bda2c8354b6f5277610b1647b3b14c82ffe241091f2b4db65e66f0 |
| tools/daily_operator_index.py | True | 30405 | 2026-06-10T23:07:03 | a26e4ed481e912ec86645202ef8f3ea2545de4310234d2da185972d61324eced |
| tools/project_preflight.py | True | 11631 | 2026-06-10T14:40:51 | 8ce0cb07aa5b18bac6cd9c3d01509eae7f0cd1725ffc80d5516d12b723be7776 |
| tools/reports_cleanup.py | True | 9150 | 2026-06-10T13:35:47 | 5ad2242390818ea93bd18e7636a706e5f33a58aeda71998beb815463370753a9 |
| tools/trade_outcome_analytics.py | True | 11863 | 2026-06-10T11:33:42 | 203f9aea7b47182db95a91ac4a67e327b546ded4030ef6adb8a948545e48a2ae |
| tools/trade_outcome_tracker.py | True | 20483 | 2026-06-09T22:58:00 | 6cd29b0eb647aa2e9aafddb1ff07851f398b47c989c4445914571bf8cfe768fe |
| tools/open_trade_snapshot.py | True | 11609 | 2026-06-09T23:03:11 | fe745f85010caff0d0baa9231e434a5da396aaba361b4eae3e881dc0dd8b9fc9 |
| tools/latest_scan_health.py | True | 1345 | 2026-06-07T18:04:17 | 6a476fa6b062cc5b732445fae205a25050ef4e28b088efc2a5ff911f0ac41bd0 |
| tools/source_coverage_audit.py | True | 6710 | 2026-06-09T12:00:05 | 9ebf56d78941ed4402da22391f7b1c59b789f05ed9c641444509ee64561926c5 |

## Report files

| path | exists | size_bytes | modified |
| --- | --- | --- | --- |
| reports/project_preflight_latest.json | True | 5249 | 2026-06-11T01:04:55 |
| reports/project_preflight_latest.md | True | 2607 | 2026-06-11T01:04:55 |
| reports/latest_scan_audited.csv | True | 783379 | 2026-06-10T21:56:47 |
| reports/latest_scan_audited.json | True | 2268078 | 2026-06-10T21:56:47 |
| reports/manual_review_latest.csv | True | 32785 | 2026-06-11T01:05:15 |
| reports/manual_review_latest.md | True | 19748 | 2026-06-11T01:05:15 |
| reports/manual_review_top.csv | True | 18754 | 2026-06-11T01:05:15 |
| reports/manual_review_top.md | True | 10495 | 2026-06-11T01:05:15 |
| reports/daily_validation_summary.txt | True | 24346 | 2026-06-11T01:05:15 |
| reports/daily_operator_index.md | True | 251 | 2026-06-11T01:15:31 |
| reports/reports_cleanup_latest.json | True | 199 | 2026-06-11T01:05:00 |
| reports/reports_cleanup_latest.md | True | 561 | 2026-06-11T01:05:00 |
| reports/open_trades_snapshot_latest.csv | False | 0 |  |
| reports/open_trades_snapshot_latest.md | False | 0 |  |
| reports/trade_outcome_analytics_latest.csv | True | 199 | 2026-06-11T01:05:00 |
| reports/trade_outcome_analytics_latest.md | True | 136 | 2026-06-11T01:05:00 |

## Summary

- missing_script_files: 0
- missing_report_files: 2