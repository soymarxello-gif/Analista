# Analista - Daily Workflow

This is the recommended daily workflow for reviewing long-only swing trading candidates. The workflow generates reports only; it does not authorize or automate trades.

## 1. Activate Environment

From PowerShell in the project root:

```powershell
.\.venv\Scripts\Activate.ps1
```

## 2. Run Daily Validation

```powershell
python .\tools\daily_validation.py
```

This runs the audited scanner, P0 validation, quality gates, optional report builders, candidate cards, automatic simple posttest, calibration, and run manifest.
Before the scanner, it synchronizes and validates the local Market Data Engine
snapshot. A sync failure with a valid local copy or Yahoo fallback is `WARN`;
missing history from every trusted source remains unavailable rather than being invented.

## 3. Review Reports In This Order

1. `reports/daily_operator_index.md`
2. `reports/market_data_engine_source_latest.md`
3. `reports/daily_quality_gate_latest.md`
3. `reports/live_quote_recheck_latest.md`
4. `reports/trade_decision_checklist_latest.md`
5. `reports/trade_candidate_cards_latest.md`
6. `reports/simple_candidate_posttest_latest.md`
7. `reports/macro_event_context_latest.md`
8. `reports/manual_review_top.md`
9. `reports/daily_run_manifest_latest.md`
10. `reports/release_readiness_latest.md`
11. `reports/ui_data_contract_audit_latest.md`
12. `reports/streamlit_smoke_test_latest.md`
13. `reports/gui_actions_audit_latest.md`
14. `reports/daily_validation_summary.txt`
15. `reports/project_preflight_latest.md`
16. `reports/encoding_audit_latest.md`

Stop immediately if a required step is `FAIL`.

## 4. Interpret Status

`PASS` means the pipeline completed without blocking errors. It does not mean buy.

`WARN` means the pipeline is usable only with reinforced manual review. Common warnings include insufficient closed-trade sample, missing optional data, unknown options flow, or data-quality limitations.

`FAIL` means do not use candidates operationally until the blocking issue is fixed.

## 5. Live Quote Recheck

Run manually when there are candidates with `RECHECK_LIVE_QUOTE`, stale quotes, missing quotes, invalid quotes, or low execution quote quality:

```powershell
python .\tools\live_quote_recheck.py
```

Review:

```text
reports/live_quote_recheck_latest.md
reports/live_quote_recheck_latest.csv
reports/live_quote_recheck_latest.json
```

Allowed live recheck decisions:

- `KEEP_RECHECK`
- `WATCHLIST_MONITOR`
- `EXECUTION_OK_REVIEW_MANUALLY`
- `AVOID_EXECUTION_RISK`
- `DATA_UNAVAILABLE`

`EXECUTION_OK_REVIEW_MANUALLY` is still manual review, not an entry signal.

## 6. Trade Decision Checklist

Generate or refresh:

```powershell
python .\tools\trade_decision_checklist.py
```

Review:

```text
reports/trade_decision_checklist_latest.md
reports/trade_decision_checklist_latest.csv
reports/trade_decision_checklist_latest.json
```

Checklist statuses:

- `BLOCKED`
- `NEEDS_LIVE_QUOTE_RECHECK`
- `REVIEW_MANUALLY`
- `HIGH_QUALITY_REVIEW`

`HIGH_QUALITY_REVIEW` means high quality for human review only.

## 7. Trade Candidate Cards

Generate or refresh:

```powershell
python .\tools\trade_candidate_cards.py
```

Review:

```text
reports/trade_candidate_cards_latest.md
reports/trade_candidate_cards_latest.json
```

Each card summarizes signal, recommendation, setup, scores, quote quality, operational levels, options context, warnings, blockers, and required manual actions.

## 8. Automatic Simple Posttest

Run the simple automatic posttest when you want the latest diagnostic view:

```powershell
python .\tools\simple_candidate_posttest.py
```

Review:

```text
reports/simple_candidate_posttest_latest.md
reports/simple_candidate_posttest_latest.csv
reports/simple_candidate_posttest_latest.json
```

This report evaluates the top candidates from previous report sessions after 5, 10, and 15 sessions. It is automatic, observational, and does not require manual trade records.

## 9. UI Data Contract

Audit the read-only data contract for a future graphical interface:

```powershell
python .\tools\ui_data_contract_audit.py
```

Review:

```text
reports/ui_data_contract_audit_latest.md
reports/ui_data_contract_audit_latest.json
```

This validates `ui/report_loader.py` and `ui/view_models.py`, checks that missing or invalid reports are handled with controlled statuses, and confirms the view models can be built without creating trading actions. This is not a Streamlit app and does not add buttons, broker connections, scanner changes, score changes, weights, or thresholds.

## 13. Streamlit Dashboard MVP

Run the dashboard locally:

```powershell
streamlit run .\app.py
```

Run the smoke test without starting a Streamlit server:

```powershell
python .\tools\streamlit_smoke_test.py
python .\tools\gui_actions_audit.py
```

Review:

```text
reports/streamlit_smoke_test_latest.md
reports/streamlit_smoke_test_latest.json
reports/gui_actions_audit_latest.md
reports/gui_actions_audit_latest.json
```

The dashboard reads report data through `ui.report_loader.load_all_ui_sources` and `ui.view_models`. GUI actions are limited to refreshing generated reports and running the single-ticker deep dive. Actions are logged in `data/ui_action_log.csv`.

Main cockpit sections:

- `Resumen`: daily status, quote quality and compact macro context.
- `Candidatos`: operational watchlist, research radar, ticker card and universe analytics.
- `Control`: safety rules, macro context, calibration, simple posttest and report health.

Within `Candidatos`, review the two lanes separately:

- `Oportunidades operativas`: strict closed-bar setups eligible for manual
  execution review, still subject to valid/high quote requirements.
- `Radar de investigación`: forming setups or mild timing cautions. These rows
  do not enter the checklist, execution recheck or automatic posttest.

Confirm `Cierre técnico`, `Política de velas`, `Estado setup` and `Estado R/R`
before interpreting a candidate. `DIAGNOSTIC_ONLY` levels are not operational.

Allowed GUI actions are limited:

- Refresh all generated data through daily validation.
- Run a single-ticker deep dive report.

The GUI does not run the scanner, does not connect to a broker, does not send real orders, and does not change scoring, weights, thresholds, config, or signals.

## 13A. Single-Ticker Deep Dive

Use this when you want to inspect a ticker that is not in the current watchlist
or when you want a focused scenario diagnosis without running the full universe
pipeline.

From the GUI:

```text
Candidatos -> Consulta puntual por ticker
```

From PowerShell:

```powershell
python .\tools\single_ticker_deep_dive.py AAPL
```

Review:

```text
reports/single_ticker_deep_dive_latest.md
reports/single_ticker_deep_dive_latest.json
```

The tool runs only a ticker-level deep technical/scenario review. It does not
run the screener, does not select from the 50-candidate funnel, does not create
scanner signals, does not create `TRIGGER_CONFIRMED`, does not change watchlist
files, and does not apply macro as an operative blocker. It is manual review
only.

## 13B. Macro Context In The GUI

Macro context is visible in:

- `Resumen`, as a compact event/liquidity summary.
- `Control -> Contexto macro`, as the full event calendar and FRED series view.

Refresh the underlying report when needed:

```powershell
python .\tools\macro_event_context.py
python .\tools\nasdaq_risk_regime_audit.py
```

Macro data is read-only context. It does not change `quote_status`,
`execution_quote_quality`, scanner signals, recommendations, scores, weights or
thresholds.

`nasdaq_risk_regime_audit` adds the Nasdaq risk semaforo as a separate lens:
Normal, Omega distribution, Sigma systemic stress, or Phi capitulation watch.
It is context only and never creates entries, broker actions, or
`TRIGGER_CONFIRMED`.

## 14. Calibration

Refresh score calibration:

```powershell
python .\tools\trade_score_calibration.py
python .\tools\calibration_recommendations.py
```

Review:

```text
reports/trade_score_calibration_latest.md
reports/calibration_recommendations_latest.md
```

Calibration is observational. Do not change weights or thresholds from insufficient samples.

## 15. Validate Tests

```powershell
python -m pytest -q
```

## 16. Review Git

```powershell
git -c safe.directory="*" status --short
```

Generated reports and caches should remain ignored. Version code, tests, and durable documentation only.

## 17. Release Readiness Audit

Before closing a version, run:

```powershell
python .\tools\release_readiness_audit.py
```

Review:

```text
reports/release_readiness_latest.md
reports/release_readiness_latest.json
```

`FAIL` blocks release closure. `WARN` requires review, usually for optional generated reports or Git hygiene around runtime artifacts.

## 14. Close A Phase With Git

1. Confirm `python -m pytest -q` passes.
2. Confirm `python .\tools\daily_validation.py` passes or returns controlled warnings only.
3. Confirm no P0 rule was relaxed.
4. Confirm `python .\tools\release_readiness_audit.py` is not `FAIL`.
5. Review `git -c safe.directory="*" status --short`.
6. Stage only intended code, tests, and docs.
7. Commit with a phase-specific message, for example:

```powershell
git add docs README.md tests
git commit -m "Add Phase 37A operating documentation"
```

Do not commit generated reports unless the project explicitly decides to version a specific reference artifact.
## GUI visuals

- Ejecutar `python .\tools\gui_visuals_audit.py` cuando se agreguen graficos, metricas o cambios visuales al dashboard.
- Revisar `reports/gui_visuals_audit_latest.md`.
- Las visualizaciones usan datos ya cargados por la capa UI; no deben modificar scanner, scoring ni outcomes.

## GUI release

- Ejecutar `python .\tools\gui_release_audit.py` antes de usar la interfaz como release candidate diario.
- Revisar `reports/gui_release_audit_latest.md`.
- La GUI debe mostrar solo revision manual, consulta puntual, refresco de datos y posttest automatico; no ejecuta scanner directamente, no conecta a servicios de ejecucion y no envia ordenes reales.

## Alpaca Read-Only Connectivity Audit

Use `tools/alpaca_readonly_connectivity_audit.py` only to validate credentials and read-only connectivity against Alpaca and IEX data. It checks account, clock, and latest IEX quote data. It does not place orders, does not enable execution, does not modify scanner outputs, and does not change signals, scores, thresholds, config, or outcomes.

Credentials are read from environment variables:

- `APCA_API_KEY_ID` or `ALPACA_API_KEY_ID`
- `APCA_API_SECRET_KEY` or `ALPACA_API_SECRET_KEY`

Run:

- `python .\tools\alpaca_readonly_connectivity_audit.py`

Review:

- `reports/alpaca_readonly_connectivity_latest.md`

 
