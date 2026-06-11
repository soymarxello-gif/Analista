# Analista - daily run manifest

- generated_at: 2026-06-10T23:01:47
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
- commit: `79308712b2507346dd015924b527f7d1e568bfb2`
- dirty: True

```text
D Analista_MVP.zip
 D Analista_patch_2_decimals.zip
 D Analista_patch_audit_fixes.zip
 D Analista_patch_liquidity_signal_fix.zip
 D Analista_patch_metadata_fundamentals.zip
 D Analista_patch_options_dashboard.zip
 D Analista_patch_options_flow.zip
 D Analista_patch_professional_dashboard.zip
 D Analista_patch_quality_tests_ci.zip
 D Analista_patch_scanner_engine_options_clean.zip
 D Analista_patch_syntax_scanner_engine_fix.zip
 M README_PATCH.txt
 M cache/fundamentals/AAOI.json
 M cache/fundamentals/ABM.json
 M cache/fundamentals/ADPT.json
 M cache/fundamentals/ALHC.json
 M cache/fundamentals/ALL.json
 M cache/fundamentals/AMG.json
 M cache/fundamentals/AMRX.json
 M cache/fundamentals/ANDG.json
 M cache/fundamentals/ARCB.json
 M cache/fundamentals/ARGX.json
 M cache/fundamentals/BLLN.json
 M cache/fundamentals/BLSH.json
 M cache/fundamentals/BMNR.json
 M cache/fundamentals/BX.json
 M cache/fundamentals/CAI.json
 M cache/fundamentals/CHEF.json
 M cache/fundamentals/CHRN.json
 M cache/fundamentals/CL.json
 M cache/fundamentals/CLX.json
 M cache/fundamentals/CMG.json
 M cache/fundamentals/CNC.json
 M cache/fundamentals/COKE.json
 M cache/fundamentals/COO.json
 M cache/fundamentals/CWK.json
 M cache/fundamentals/CXW.json
 M cache/fundamentals/DAVE.json
 M cache/fundamentals/EG.json
 M cache/fundamentals/EHC.json
 M cache/fundamentals/ENVA.json
 M cache/fundamentals/ERIE.json
 M cache/fundamentals/ESTA.json
 M cache/fundamentals/FIZZ.json
 M cache/fundamentals/FLNC.json
 M cache/fundamentals/GEO.json
 M cache/fundamentals/GKOS.json
 M cache/fundamentals/GS.json
 M cache/fundamentals/HAE.json
 M cache/fundamentals/HCI.json
 M cache/fundamentals/HG.json
 M cache/fundamentals/HOOD.json
 M cache/fundamentals/HRI.json
 M cache/fundamentals/INOD.json
 M cache/fundamentals/IRDM.json
 M cache/fundamentals/KMB.json
 M cache/fundamentals/KVUE.json
 M cache/fundamentals/LQDA.json
 M cache/fundamentals/M.json
 M cache/fundamentals/MCY.json
 M cache/fundamentals/MH.json
 M cache/fundamentals/MRVL.json
 M cache/fundamentals/NN.json
 M cache/fundamentals/NP.json
 M cache/fundamentals/ORKA.json
 M cache/fundamentals/OSCR.json
 M cache/fundamentals/OUST.json
 M cache/fundamentals/PG.json
 M cache/fundamentals/PGR.json
 M cache/fundamentals/PLMR.json
 M cache/fundamentals/PODD.json
 M cache/fundamentals/PPC.json
 M cache/fundamentals/PTGX.json
 M cache/fundamentals/RDW.json
 M cache/fundamentals/RLI.json
 M cache/fundamentals/RNR.json
 M cache/fundamentals/SBRA.json
 M cache/fundamentals/SEZL.json
 M cache/fundamentals/SLDE.json
 M cache/fundamentals/SLG.json
 M cache/fundamentals/SOLV.json
 M cache/fundamentals/SRAD.json
 M cache/fundamentals/SYRE.json
 M cache/fundamentals/TEM.json
 M cache/fundamentals/TTAN.json
 M cache/fundamentals/TXRH.json
 M cache/fundamentals/VECO.json
 M cache/fundamentals/VG.json
 M cache/fundamentals/VOYG.json
 M cache/fundamentals/WPP.json
 M cache/options/ABM.json
 M cache/options/ALL.json
 M cache/options/ARGX.json
 M cache/options/CHEF.json
 M cache/options/CL.json
 M cache/options/CLX.json
 M cache/options/CMG.json
 M cache/options/COKE.json
 M cache/options/COO.json
 M cache/options/EG.json
 M cache/options/EHC.json
 M cache/options/FIZZ.json
 M cache/options/HG.json
 M cache/options/KMB.json
 M cache/options/KVUE.json
 M cache/options/OSCR.json
 M cache/options/PG.json
 M cache/options/PGR.json
 M cache/options/PODD.json
 M cache/options/RLI.json
 M cache/options/RNR.json
 M cache/options/SBRA.json
 M cache/options/SLDE.json
 M cache/options/TTAN.json
 M cache/options/TXRH.json
 M cache/screener/day_gainers.json
 M cache/screener/growth_technology_stocks.json
 M cache/screener/most_actives.json
 M cache/screener/undervalued_growth_stocks.json
 M config.yaml
 M data/screener_client.py
 M engine/report_engine.py
 M engine/scanner_engine.py
 M logs/scanner.log
 D reports/latest_scan_test.csv
 D reports/latest_scan_test.json
 M run_scanner.py
 M scoring/final_score.py
 M scoring/options_score.py
 M scoring/risk_reward_score.py
 M scoring/signal_classifier.py
 M tests/test_options_score.py
 M tests/test_signal_classifier.py
 M ui/dashboard.py
 M universe/equity_validator.py
 M universe/liquidity_filter.py
?? CONFIG_FRAGMENT_EVOLUTION_PHASE1.yaml
?? CONFIG_FRAGMENT_PHASE1_1.yaml
?? CONFIG_FRAGMENT_PHASE1_2.yaml
?? CONFIG_FRAGMENT_PHASE2_2.yaml
?? CONFIG_FRAGMENT_PHASE2_3.yaml
?? DASHBOARD_PHASE2_3_NOTES.md
?? SCANNER_ENGINE_EVOLUTION_NOTES.md
?? SCANNER_ENGINE_PHASE1_2_NOTES.md
?? SCANNER_ENGINE_PHASE2_3_NOTES.md
?? agente.md
?? csv.txt
?? data/data_quality.py
?? docs/
?? engine/calibration_engine.py
?? engine/posttest_batch_engine.py
?? engine/posttest_engine.py
?? engine/scan_audit_engine.py
?? engine/universe_source_audit.py
?? report.txt
?? reports/audits/
?? reports/calibration/
?? reports/daily_operator_index.md
?? reports/daily_quality_gate_latest.md
?? reports/daily_run_manifest_latest.md
?? reports/daily_validation_summary.txt
?? reports/encoding_audit_latest.md
?? reports/history_evolution_latest.md
?? reports/latest_scan_audited.html
?? reports/latest_scan_audited.md
?? reports/live_quote_recheck_latest.md
?? reports/manual_review_latest.md
?? reports/manual_review_top.md
?? reports/posttests/
?? reports/project_preflight_latest.md
?? reports/release_readiness_latest.md
?? reports/report_consistency_latest.md
?? reports/reports_cleanup_latest.md
?? reports/setup_persistence_latest.md
?? reports/tmp/
?? reports/trade_outcome_analytics_latest.md
?? reports/trade_outcomes_summary.md
?? reports/trade_outcomes_test_summary.md
?? run_posttest.py
?? run_scan_audit.py
?? run_scanner_audited.py
?? salida.txt
?? scoring/execution_review.py
?? scoring/operational_priority.py
?? tests/conftest.py
?? tests/test_calibration_engine_phase2_0.py
?? tests/test_daily_operator_index_phase28b.py
?? tests/test_daily_operator_index_phase29c.py
?? tests/test_daily_operator_index_phase30c.py
?? tests/test_daily_operator_index_phase31c.py
?? tests/test_daily_operator_index_phase32c.py
?? tests/test_daily_operator_index_phase33c.py
?? tests/test_daily_quality_gate_phase33a.py
?? tests/test_daily_run_manifest_phase31a.py
?? tests/test_daily_validation_phase16.py
?? tests/test_daily_validation_phase27b.py
?? tests/test_daily_validation_phase28c.py
?? tests/test_daily_validation_phase29b.py
?? tests/test_daily_validation_phase30b.py
?? tests/test_daily_validation_phase31b.py
?? tests/test_daily_validation_phase32b.py
?? tests/test_daily_validation_phase33b.py
?? tests/test_daily_validation_summary_phase28.py
?? tests/test_data_quality_phase11.py
?? tests/test_data_quality_phase1_1.py
?? tests/test_encoding_audit_phase32a.py
?? tests/test_execution_review_phase13.py
?? tests/test_history_archive_phase17.py
?? tests/test_history_evolution_phase18.py
?? tests/test_latest_scan_health_phase1_4.py
?? tests/test_liquidity_filter_phase1_1.py
?? tests/test_live_quote_recheck_phase23.py
?? tests/test_manual_review_export_phase14.py
?? tests/test_manual_review_persistence_enricher_phase21.py
?? tests/test_manual_review_top_phase22.py
?? tests/test_open_trade_snapshot_phase26c.py
?? tests/test_operational_priority_phase2_3.py
?? tests/test_operator_runbook_phase34b.py
?? tests/test_options_confidence_phase1_1.py
?? tests/test_options_crowded_phase1_2.py
?? tests/test_options_unknown_flow_phase6.py
?? tests/test_p0_logical_consistency.py
?? tests/test_posttest_batch_engine_phase2_1.py
?? tests/test_project_consistency_phase10.py
?? tests/test_project_preflight_phase30a.py
?? tests/test_ranking_phase9.py
?? tests/test_release_readiness_phase34a.py
?? tests/test_report_consistency_audit_phase24.py
?? tests/test_report_engine_phase7.py
?? tests/test_reports_cleanup_phase29a.py
?? tests/test_scan_audit_engine_phase1_3.py
?? tests/test_scan_audit_engine_phase8.py
?? tests/test_screener_client_phase2_2.py
?? tests/test_setup_persistence_score_phase19a.py
?? tests/test_signal_quality_phase1_2.py
?? tests/test_source_coverage_audit_phase12.py
?? tests/test_stop_atr_multiple_phase5.py
?? tests/test_trade_outcome_analytics_phase27.py
?? tests/test_trade_outcome_tracker_phase26.py
?? tests/test_trade_score_breakdown_phase4.py
?? tests/test_universe_source_audit_phase2_2.py
?? tools/daily_operator_index.py
?? tools/daily_quality_gate.py
?? tools/daily_run_manifest.py
?? tools/daily_validation.py
?? tools/encoding_audit.py
?? tools/evidence_pipeline.py
?? tools/history_archive.py
?? tools/history_evolution.py
?? tools/latest_scan_health.py
?? tools/live_quote_recheck.py
?? tools/manual_review_export.py
?? tools/manual_review_persistence_enricher.py
?? tools/manual_review_top.py
?? tools/open_trade_snapshot.py
?? tools/project_consistency_audit.py
?? tools/project_preflight.py
?? tools/release_readiness_check.py
?? tools/report_consistency_audit.py
?? tools/reports_cleanup.py
?? tools/run_calibration.py
?? tools/run_posttest_batch.py
?? tools/run_universe_audit.py
?? tools/setup_persistence_score.py
?? tools/source_coverage_audit.py
?? tools/trade_outcome_analytics.py
?? tools/trade_outcome_tracker.py
?? validate_latest_scan_p0.py
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
| tools/daily_operator_index.py | True | 29597 | 2026-06-10T21:16:35 | 4359fe43df7111abc7111fad3cfdb2e810c2b279d33ebde2126b01c6818f1ef9 |
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
| reports/project_preflight_latest.json | True | 5249 | 2026-06-10T23:01:42 |
| reports/project_preflight_latest.md | True | 2607 | 2026-06-10T23:01:42 |
| reports/latest_scan_audited.csv | True | 783379 | 2026-06-10T21:56:47 |
| reports/latest_scan_audited.json | True | 2268078 | 2026-06-10T21:56:47 |
| reports/manual_review_latest.csv | True | 32787 | 2026-06-10T23:00:57 |
| reports/manual_review_latest.md | True | 19748 | 2026-06-10T23:00:57 |
| reports/manual_review_top.csv | True | 18754 | 2026-06-10T23:00:57 |
| reports/manual_review_top.md | True | 10495 | 2026-06-10T23:00:57 |
| reports/daily_validation_summary.txt | True | 21823 | 2026-06-10T23:01:46 |
| reports/daily_operator_index.md | True | 7512 | 2026-06-10T23:01:47 |
| reports/reports_cleanup_latest.json | True | 199 | 2026-06-10T23:01:46 |
| reports/reports_cleanup_latest.md | True | 561 | 2026-06-10T23:01:46 |
| reports/open_trades_snapshot_latest.csv | False | 0 |  |
| reports/open_trades_snapshot_latest.md | False | 0 |  |
| reports/trade_outcome_analytics_latest.csv | True | 199 | 2026-06-10T23:01:46 |
| reports/trade_outcome_analytics_latest.md | True | 136 | 2026-06-10T23:01:46 |

## Summary

- missing_script_files: 0
- missing_report_files: 2