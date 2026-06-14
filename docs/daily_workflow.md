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

This runs the audited scanner, P0 validation, quality gates, optional report builders, candidate cards, paper trading journal summary, paper close summary, calibration, and run manifest.

## 3. Review Reports In This Order

1. `reports/daily_operator_index.md`
2. `reports/daily_quality_gate_latest.md`
3. `reports/live_quote_recheck_latest.md`
4. `reports/trade_decision_checklist_latest.md`
5. `reports/trade_candidate_cards_latest.md`
6. `reports/paper_trading_journal_latest.md`
7. `reports/paper_trade_followup_latest.md`
8. `reports/paper_trade_close_latest.md`
9. `reports/paper_trading_cycle_audit_latest.md`
10. `reports/manual_review_top.md`
11. `reports/daily_run_manifest_latest.md`
12. `reports/release_readiness_latest.md`
13. `reports/ui_data_contract_audit_latest.md`
14. `reports/streamlit_smoke_test_latest.md`
15. `reports/gui_actions_audit_latest.md`
16. `reports/daily_validation_summary.txt`
17. `reports/project_preflight_latest.md`
18. `reports/encoding_audit_latest.md`

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

## 8. Paper Trading Journal

Import today's review candidates into the paper journal:

```powershell
python .\tools\paper_trading_journal.py --import-today
```

Review:

```text
data/paper_trading_journal.csv
reports/paper_trading_journal_latest.md
reports/paper_trading_journal_latest.csv
reports/paper_trading_journal_latest.json
```

Manual decisions allowed in the journal are `PENDING_REVIEW`, `PAPER_WATCH`, `PAPER_ENTER`, `SKIP`, `BLOCKED`, and `NEEDS_LIVE_QUOTE_RECHECK`. `PAPER_ENTER` is simulated only; it creates no broker order and does not modify scanner signals, scores, config, weights, or thresholds.

## 9. Paper Trade Follow-Up

Generate daily follow-up for open paper trades:

```powershell
python .\tools\paper_trade_followup.py
```

Review:

```text
reports/paper_trade_followup_latest.md
reports/paper_trade_followup_latest.csv
reports/paper_trade_followup_latest.json
```

The follow-up report checks latest price versus simulated entry, stop, and target. It may flag hold, near stop, near target, stop hit, target hit, invalidated review, or data unavailable. It does not close paper trades automatically and does not modify `data/paper_trading_journal.csv`.

## 10. Paper Trade Close

List open paper trades:

```powershell
python .\tools\paper_trade_close.py --list-open
```

Close a paper trade manually:

```powershell
python .\tools\paper_trade_close.py --close JOURNAL_ID --exit-price 123.45 --reason TARGET_REACHED_MANUAL
```

Export closed paper trades to calibration outcomes only when intended:

```powershell
python .\tools\paper_trade_close.py --export-outcomes
```

Daily validation runs only:

```powershell
python .\tools\paper_trade_close.py --summary
```

Review:

```text
reports/paper_trade_close_latest.md
reports/paper_trade_close_latest.csv
reports/paper_trade_close_latest.json
```

Closing and export are manual paper-trading actions only. The tool does not connect to a broker, does not send real orders, does not modify scanner signals, scores, config, weights, or thresholds, and does not close anything unless `--close` is explicitly supplied.

## 11. Paper Trading Cycle Audit

Audit the full paper trading cycle:

```powershell
python .\tools\paper_trading_cycle_audit.py
```

Review:

```text
reports/paper_trading_cycle_audit_latest.md
reports/paper_trading_cycle_audit_latest.json
```

The audit verifies journal columns, open and closed paper trades, pending exports, exported outcomes, duplicate `source_journal_id` values, calibration/recommendation status, and paper-only guardrails. It is read-only and does not modify `data/paper_trading_journal.csv`, `data/trade_outcomes.csv`, scanner logic, scores, config, weights, or thresholds.

## 12. UI Data Contract

Audit the read-only data contract for a future graphical interface:

```powershell
python .\tools\ui_data_contract_audit.py
```

Review:

```text
reports/ui_data_contract_audit_latest.md
reports/ui_data_contract_audit_latest.json
```

This validates `ui/report_loader.py` and `ui/view_models.py`, checks that missing or invalid reports are handled with controlled statuses, and confirms the view models can be built without creating trading actions. This is not a Streamlit app and does not add buttons, broker connections, journal writes, outcome exports, scanner changes, score changes, weights, or thresholds.

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

The dashboard reads report data through `ui.report_loader.load_all_ui_sources` and `ui.view_models`. Paper-trading actions are routed through `ui.actions`, require explicit confirmation before journal/outcome writes, and are logged in `data/ui_action_log.csv`.

Allowed GUI actions are paper-only:

- Import today candidates.
- Set a manual paper decision.
- Refresh paper follow-up reports.
- Manually close a paper trade.
- Export already closed paper trades to outcomes.

The GUI does not run the scanner, does not connect to a broker, does not send real orders, and does not change scoring, weights, thresholds, config, or signals.

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
- Las visualizaciones usan datos ya cargados por la capa UI; no deben modificar scanner, scoring, journal ni outcomes.

## GUI release

- Ejecutar `python .\tools\gui_release_audit.py` antes de usar la interfaz como release candidate diario.
- Revisar `reports/gui_release_audit_latest.md`.
- La GUI debe mostrar solo revision manual, paper trading y acciones confirmadas; no ejecuta scanner, no conecta a servicios de ejecucion y no envia ordenes reales.

## GUI supervised session

- Iniciar bitacora diaria supervisada con `python .\tools\gui_supervised_session.py --start`.
- Revisar estado con `python .\tools\gui_supervised_session.py --status`.
- Agregar notas con `python .\tools\gui_supervised_session.py --note "nota operativa"`.
- Generar resumen con `python .\tools\gui_supervised_session.py --summary`.
- Cerrar la sesion con `python .\tools\gui_supervised_session.py --close --result PASS`.
- Auditar la herramienta con `python .\tools\gui_supervised_session_audit.py`.
- Revisar `reports/gui_supervised_session_latest.md` y `reports/gui_supervised_session_audit_latest.md`.
## Daily GUI Operating Checklist

Use `tools/gui_daily_operating_checklist.py` as a manual paper-only checklist for GUI operation. The checklist records confirmations and notes only; it does not start Streamlit, run the scanner, change journal rows, close trades, connect to a broker, or send real orders.

Recommended commands:

- `python .\tools\gui_daily_operating_checklist.py --init-today`
- `python .\tools\gui_daily_operating_checklist.py --status`
- `python .\tools\gui_daily_operating_checklist.py --mark STEP_ID DONE --note "..."`
- `python .\tools\gui_daily_operating_checklist.py --summary`
- `python .\tools\gui_daily_operating_checklist_audit.py`

Review:

- `reports/gui_daily_operating_checklist_latest.md`
- `reports/gui_daily_operating_checklist_audit_latest.md`

## Alpaca Read-Only Connectivity Audit

Use `tools/alpaca_readonly_connectivity_audit.py` only to validate credentials and read-only connectivity against Alpaca paper trading and IEX data. It checks account, clock, and latest IEX quote data. It does not place orders, does not enable execution, does not modify scanner outputs, and does not change signals, scores, thresholds, config, journal, or outcomes.

Credentials are read from environment variables:

- `APCA_API_KEY_ID` or `ALPACA_API_KEY_ID`
- `APCA_API_SECRET_KEY` or `ALPACA_API_SECRET_KEY`

Run:

- `python .\tools\alpaca_readonly_connectivity_audit.py`

Review:

- `reports/alpaca_readonly_connectivity_latest.md`

## Operational Decision Log

Use `tools/gui_operational_decision_log.py` to record manual GUI decisions during the day. This bitacora is observational and paper-only: it does not modify paper journal rows, does not export outcomes, does not run the scanner, and does not change scoring, config, thresholds, or signals.

Commands:

- `python .\tools\gui_operational_decision_log.py --add --ticker AAPL --decision PAPER_WATCH --reason "..."`
- `python .\tools\gui_operational_decision_log.py --list-today`
- `python .\tools\gui_operational_decision_log.py --review DECISION_ID --outcome-note "..." --lesson "..."`
- `python .\tools\gui_operational_decision_log.py --summary`
- `python .\tools\gui_post_session_review.py`
- `python .\tools\gui_operational_decision_log_audit.py`

Review:

- `reports/gui_operational_decision_log_latest.md`
- `reports/gui_post_session_review_latest.md`
- `reports/gui_operational_decision_log_audit_latest.md`

## Decision Quality Review

Use `tools/gui_decision_quality_review.py` after recording operational decisions and post-session notes. The review scores decision discipline from reasons, checklist alignment, post-session review, quote discipline, follow-up planning, no-real-order confirmation, and lessons captured. It is observational only; no automatic trading changes are applied.

Commands:

- `python .\tools\gui_decision_quality_review.py`
- `python .\tools\gui_decision_quality_audit.py`

Review:

- `reports/gui_decision_quality_review_latest.md`
- `reports/gui_decision_quality_review_latest.csv`
- `reports/gui_decision_quality_audit_latest.md`
 
