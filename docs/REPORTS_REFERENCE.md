# Analista - Reports Reference

Reports are generated artifacts for manual review and auditability. Most files under `reports/` are runtime outputs and should not be versioned unless explicitly chosen as stable references.

## Core Daily Reports

### `reports/daily_validation_summary.txt`

End-to-end daily run summary. Shows required and optional step status, output file status, scan snapshot, quote recheck summary, checklist summary, candidate cards summary, calibration summary, and operational next steps.

### `reports/daily_operator_index.md`

Primary operator index. Open this first after the daily run. It links the key reports and summarizes quality gate, calibration, live quote recheck, checklist, candidate cards, signals, recommendations, options flow, and manifest status.

### `reports/daily_quality_gate_latest.*`

Manual-review gate. Use it to identify whether manual review is allowed, reinforced, or blocked. A `FAIL` here stops operational use of candidates.

### `reports/daily_run_manifest_latest.*`

Run manifest with environment, Git status, script file hashes, report file presence, and scan snapshot. Use it for reproducibility and audit trail.

### `reports/project_preflight_latest.*`

Project structure and writeability check. It verifies required folders, required scripts, optional reports, Python environment, and report directory write access.

### `reports/encoding_audit_latest.*`

Encoding and mojibake audit for generated reports. Use it before sharing reports externally.

## Scanner Outputs

### `reports/latest_scan_audited.*`

Full audited scanner output. Contains all candidates after universe, metadata, technical indicators, data quality, quote quality, options context, scoring, signals, recommendations, and audit columns.

### `reports/manual_review_latest.*`

Filtered manual-review set. This is not an execution list; it is a curated report for human review.

### `reports/manual_review_top.*`

Prioritized subset of manual-review candidates. Open after daily operator index and quality gate.

## Execution Review Reports

### `reports/live_quote_recheck_latest.*`

Live quote validation for candidates needing execution-quality review. It checks live price, bid, ask, spread, quote status, execution quote quality, price versus entry, and manual review requirement.

The output decision does not create `TRIGGER_CONFIRMED`; it only informs human review.

### `reports/trade_decision_checklist_latest.*`

Checklist generated from current candidates. It classifies each candidate as blocked, needing live quote recheck, manual review, or high-quality manual review.

### `reports/trade_candidate_cards_latest.*`

Per-candidate manual card. Each card includes signal, recommendation, setup, sector, scores, options context, quote quality, entry, stop, target, R/R, warnings, blockers, required actions, and a pending manual decision note.

### `reports/simple_candidate_posttest_latest.*`

Automatic retrospective diagnostic for the five best reported candidates from
5, 10, and 15 reported sessions ago. It estimates return, win rate, target hit,
stop hit, entry touched, profit factor, expectancy, common failures, and common
success patterns.

This report replaces the old manual simulated workflow as the primary feedback
loop. It does not create orders, scanner signals, score changes,
weights, thresholds, or automatic recommendations to buy.

### `reports/ui_data_contract_audit_latest.*`

Audit of the read-only data contract for the GUI. It verifies
`ui/report_loader.py`, `ui/view_models.py`, controlled missing/invalid/empty
statuses, candidate table model readiness, macro context readiness,
calibration summaries, simple posttest readiness, and guardrails against
operational actions.

This report does not build a GUI, does not create action buttons, and does not modify reports, data, scanner, scoring, config, weights, thresholds, or signals.

### `reports/streamlit_smoke_test_latest.*`

Smoke test for the read-only Streamlit MVP in `app.py`. It imports the dashboard without starting a server, validates that UI sources and view models build successfully, and checks read-only guardrails for the dashboard surface.

This report is observational only. It does not write scanner data, does not modify trade outcomes, does not run the scanner, does not connect to a broker, and does not send orders.

### `reports/gui_actions_audit_latest.*`

Audit of controlled actions exposed by the Streamlit dashboard. It verifies that `app.py` routes actions through `ui/actions.py`, that only approved read-only actions exist, that no shell execution is allowed, and that order/broker guardrails remain intact.

This report is observational only. It does not modify trade outcomes, scanner, scoring, config, weights, thresholds, or signals.

### `reports/single_ticker_deep_dive_latest.*`

Read-only, on-demand deep analysis for one ticker. It is generated from
`tools/single_ticker_deep_dive.py` or from `Candidatos -> Consulta puntual por
ticker` in the GUI.

The report includes ticker metadata, technical scenario status, momentum,
extension, entry timing, levels, R/R, quote quality, options context when
available, warnings, required manual actions, and no-real-order guardrails.

This report is not part of the scanner universe pipeline. It does not run the
screener, does not select from the 50-candidate funnel, does not create scanner
signals, does not create `TRIGGER_CONFIRMED`, does not modify watchlists,
outcomes, scoring, thresholds, config, or execution state.

## Calibration And Outcomes

### `reports/trade_score_calibration_latest.*`

Closed-trade calibration report. Groups results by checklist status, setup type, signal, recommendation, score buckets, options bias, options confidence, and sector when available.

Key fields include closed trades, win rate, average PnL, average R multiple, total R multiple, holding days, and `sample_size_warning`.

### `reports/calibration_recommendations_latest.*`

Observational calibration recommendations based on trade score calibration. These recommendations are review prompts only. They do not modify scoring, weights, thresholds, scanner logic, or signals.

### `reports/trade_outcome_analytics_latest.*`

Outcome analytics for closed trades. This is the broader performance report used as input context for calibration.

## Maintenance Reports

### `reports/reports_cleanup_latest.*`

Dry-run or apply report for temporary report cleanup. By default it is diagnostic. Use `--apply` only when intentionally moving temporary report files.

## Generated Files And Version Control

Generated files usually include:

- `reports/*.csv`
- `reports/*.json`
- `reports/*.md`
- `reports/*.txt`
- `reports/history/*`
- `reports/audits/*`
- `cache/*`
- `logs/*`
- `.pytest_cache/*`
- `__pycache__/*`

These are runtime artifacts. Keep durable source code, tests, configuration, and documentation versioned; keep generated reports ignored unless a specific reference artifact is intentionally committed.
## gui_visuals_audit_latest.*

- `reports/gui_visuals_audit_latest.json`
- `reports/gui_visuals_audit_latest.md`
- Auditoria que verifica que las visualizaciones del dashboard usan `ui/charts.py`, toleran datos vacios y no introducen ejecucion automatica ni cambios de scoring.

## gui_release_audit_latest.*

- `reports/gui_release_audit_latest.json`
- `reports/gui_release_audit_latest.md`
- Auditoria final de la interfaz Streamlit como release candidate: valida modulos UI, acciones controladas, ausencia de lecturas/escrituras directas en `app.py`, ausencia de comandos arbitrarios y guardrails de no ejecucion real.

## Alpaca Read-Only Connectivity Reports

- `alpaca_readonly_connectivity_latest.*`: read-only connectivity audit for Alpaca credentials, account, clock, and IEX latest quote checks. It masks credentials, does not place orders, does not enable execution, and does not modify scanner, scoring, thresholds, config, or outcomes.

## Secondary Read-Only Data Source Reports

- `macro_event_context_latest.*`: combines the auditable economic calendar with
  official FRED series. FRED access uses pandas-datareader first, direct FRED
  CSV second, and `cache/macro/fred_latest.json` as a stale fallback. Each
  series reports provider, source, observation date, age, cache status,
  fallback usage, and errors. Yahoo/FRED comparisons are diagnostic only.
  The GUI shows this in `Resumen` and `Control -> Contexto macro`; it remains
  read-only context.
- `nasdaq_risk_regime_latest.*`: read-only Nasdaq regime semaforo. It maps
  volatility, credit, breadth, rates/dollar pressure, Cboe aggregate put/call,
  and QQQ trend into Normal, Omega distribution, Sigma systemic stress, or Phi
  capitulation watch. It is source-traced context only and cannot create
  signals, execution quality, broker actions, or `TRIGGER_CONFIRMED`.
- `webull_readonly_market_data_latest.*`: validates optional Webull OpenAPI
  connectivity without orders or execution.
- `cboe_market_statistics_latest.*`: validates public Cboe market statistics
  used only for aggregate options context. It reports each dataset date and
  age. Historical put/call data is marked stale and unusable rather than being
  presented as current sentiment.
- `google_sheets_data_source_latest.*`: validates the schema, timestamps,
  freshness, and available fields of a published Google Sheets CSV. Stale or
  malformed rows remain visible in the audit and are not used by scanner
  fallbacks.
- `source_coverage_latest.json`: includes distributions for
  `analysis_quote_source`, `analysis_quote_freshness`,
  `analysis_quote_confidence`, and `secondary_data_sources_used`.

## Simple Candidate Posttest Reports

- `simple_candidate_posttest_latest.*`: automatic 5/10/15-session diagnostic
  over the top reported candidates. It is the preferred lightweight feedback
  loop for finding late entries, weak momentum, false breakouts, invalid levels,
  and score/ranking weaknesses. It remains observational and never changes
  scanner logic, execution quality, thresholds, or signals.
