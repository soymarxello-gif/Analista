# Analista - Operating Manual

## System Objective

Analista is a conservative, auditable scanner for long-only swing trading candidates in US-listed stocks and ETFs. Its purpose is to rank and explain candidates for human review, not to automate trading.

The system combines:

- Yahoo Finance as the primary data source.
- Secondary metadata fallback from Finviz, MarketWatch, and auditable manual/free sources when available.
- Technical setup detection.
- Quote and execution data quality checks.
- Options and institutional-flow context.
- Conservative scoring.
- Manual decision checklists and candidate cards.
- Closed-trade calibration and non-automatic calibration recommendations.

## Delayed And Manual Data Sources

Yahoo Finance remains the primary source. Alpaca IEX delayed data and a published
Google Sheets CSV may fill analysis-only gaps. They do not change
`quote_status`, `execution_quote_quality`, signals, recommendations, or P0.

The Google Sheets source is disabled by default. To enable it, publish one sheet
tab as CSV and configure:

```yaml
data_sources:
  providers:
    google_sheets_manual:
      enabled: true
      published_csv_url: "https://docs.google.com/spreadsheets/d/.../pub?output=csv"
```

Required CSV columns:

- `ticker`
- `source`
- `updated_at` as an ISO-8601 timestamp
- `confidence` as `HIGH`, `MEDIUM`, `LOW`, or `UNKNOWN`

Supported optional columns include `price`, `bid`, `ask`, `spread_pct`,
`sector`, `industry`, `market_cap`, `earnings_date`, `next_earnings_date`,
`put_call_ratio`, `options_volume`, `options_open_interest`, `iv`, `delta`,
`gamma`, and `notes`.

Rows with missing traceability, invalid timestamps, or age above
`max_stale_minutes` are audited but not used. Yahoo values are never
overwritten when valid. For quotes the priority is Yahoo, Alpaca IEX, then
Google Sheets. For metadata Google Sheets is the last manual fallback after
Finviz, MarketWatch, and TradingView/manual sources.

Audit commands:

```powershell
python .\tools\google_sheets_data_source_audit.py
python .\tools\source_coverage_audit.py
```

Cboe public market-share and equity-volume datasets are audited independently.
The public `totalpc.csv` dataset may be historical. Its date and age are checked
before use; a stale ratio is reported as `UNKNOWN_OPTIONS_CONTEXT` and is never
treated as current sentiment or a ticker-level signal.

## Main Commands

Activate environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Run daily workflow:

```powershell
python .\tools\daily_validation.py
```

Run tests:

```powershell
python -m pytest -q
```

Review Git:

```powershell
git -c safe.directory="*" status --short
```

## Daily Review Order

1. `reports/daily_operator_index.md`
2. `reports/daily_quality_gate_latest.md`
3. `reports/live_quote_recheck_latest.md`
4. `reports/trade_decision_checklist_latest.md`
5. `reports/trade_candidate_cards_latest.md`
6. `reports/paper_trading_journal_latest.md`
7. `reports/paper_trade_followup_latest.md`
8. `reports/paper_trade_close_latest.md`
9. `reports/paper_trading_cycle_audit_latest.md`
10. `reports/gui_weekly_operational_review_latest.md`
11. `reports/gui_evidence_collection_window_latest.md`
12. `reports/manual_review_top.md`
13. `reports/daily_run_manifest_latest.md`
14. `reports/release_readiness_latest.md`
15. `reports/ui_data_contract_audit_latest.md`
16. `reports/streamlit_smoke_test_latest.md`
17. `reports/gui_actions_audit_latest.md`
18. `reports/daily_validation_summary.txt`

## Signals

| Signal | Meaning | Operable |
|---|---|---|
| `VETO` | Hard block or invalid setup/data state. | No |
| `AVOID` | Weak or risky candidate. | No |
| `WATCHLIST` | Monitoring candidate. | No automatic entry |
| `READY_WAIT_TRIGGER` | Setup may be valid but trigger is not confirmed. | Manual monitoring only |
| `TRIGGER_CONFIRMED` | Trigger state is confirmed by scanner rules. | Manual review only |

`BUY_SETUP_ACTIVE` is disabled and must not be recreated.

## Recommendations

| Recommendation | Meaning |
|---|---|
| `DO_NOT_TRADE` | Do not use operationally. |
| `AVOID_FOR_NOW` | Avoid unless future data materially improves. |
| `WATCHLIST_MONITOR` | Monitor manually. |
| `RECHECK_LIVE_QUOTE` | Validate live quote before any execution review. |

Recommendations are not orders and do not authorize automatic execution.

## Checklist And Candidate Cards

`trade_decision_checklist` creates a structured status for each review candidate:

- `BLOCKED`
- `NEEDS_LIVE_QUOTE_RECHECK`
- `REVIEW_MANUALLY`
- `HIGH_QUALITY_REVIEW`

`trade_candidate_cards` converts checklist rows into readable per-ticker manual cards. Cards include operational levels, quote state, scores, options context, warnings, blockers, required actions, and a pending manual decision.

## Paper Trading Journal

`paper_trading_journal` imports reviewed candidates into an auditable simulated journal.

```powershell
python .\tools\paper_trading_journal.py --import-today
```

The tool writes:

- `data/paper_trading_journal.csv`
- `reports/paper_trading_journal_latest.csv`
- `reports/paper_trading_journal_latest.md`
- `reports/paper_trading_journal_latest.json`

Allowed manual decisions are `PENDING_REVIEW`, `PAPER_WATCH`, `PAPER_ENTER`, `SKIP`, `BLOCKED`, and `NEEDS_LIVE_QUOTE_RECHECK`. `PAPER_ENTER` is paper-only and requires simulated entry, stop, and target levels. Candidates marked `BLOCKED` cannot be paper-entered, and candidates marked `NEEDS_LIVE_QUOTE_RECHECK` require explicit live quote confirmation before any simulated entry.

The journal does not connect to a broker and does not modify scanner outputs, scores, config, weights, thresholds, or signals.

## Paper Trade Follow-Up

`paper_trade_followup` reviews open paper trades against latest price, simulated entry, stop, and target.

```powershell
python .\tools\paper_trade_followup.py
```

The tool writes:

- `reports/paper_trade_followup_latest.csv`
- `reports/paper_trade_followup_latest.md`
- `reports/paper_trade_followup_latest.json`

Follow-up decisions are review labels only: hold paper, review near stop, review near target, stop hit review close, target hit review close, data unavailable, or invalidated review. The tool does not close trades automatically, does not modify `data/paper_trading_journal.csv`, does not connect to a broker, and does not send orders.

## Paper Trade Close

`paper_trade_close` lists open paper trades, closes a selected paper trade only when `--close` is explicitly supplied, and optionally exports closed paper trades to calibration outcomes only when `--export-outcomes` is supplied.

```powershell
python .\tools\paper_trade_close.py --list-open
python .\tools\paper_trade_close.py --close JOURNAL_ID --exit-price 123.45 --reason TARGET_REACHED_MANUAL
python .\tools\paper_trade_close.py --export-outcomes
python .\tools\paper_trade_close.py --summary
```

The tool writes:

- `reports/paper_trade_close_latest.csv`
- `reports/paper_trade_close_latest.md`
- `reports/paper_trade_close_latest.json`

With `--close`, it updates only the selected row in `data/paper_trading_journal.csv` with exit date, exit price, close reason, close timestamp, PnL percent, R multiple, and export markers. With `--export-outcomes`, it appends non-duplicated closed paper trades to `data/trade_outcomes.csv`.

The daily workflow runs `paper_trade_close --summary` only. No paper trade is closed or exported by daily validation. The tool is paper trading only, uses no broker connection, sends no real orders, and does not modify scanner outputs, scores, config, weights, thresholds, or signals.

## Paper Trading Cycle Audit

`paper_trading_cycle_audit` verifies that the paper workflow can flow from candidate review to journal, follow-up, manual close, outcome export, calibration, and observational recommendations.

```powershell
python .\tools\paper_trading_cycle_audit.py
```

The tool writes:

- `reports/paper_trading_cycle_audit_latest.md`
- `reports/paper_trading_cycle_audit_latest.json`

It checks required journal columns, pending review rows, open paper trades, closed paper trades, pending exports, exported outcomes, duplicate `source_journal_id` values, exported journal rows without matching outcomes, orphan paper outcomes, calibration status, recommendation status, no-real-order notices, and broker/order guardrails.

The audit is read-only. It does not modify `data/paper_trading_journal.csv`, `data/trade_outcomes.csv`, scanner outputs, scores, config, weights, thresholds, or signals.

## UI Data Contract

`ui/report_loader.py` and `ui/view_models.py` define the read-only data contract for a future graphical interface. The loader reads generated reports and normalizes missing, invalid, empty, and available states. The view models convert those sources into GUI-ready dictionaries without adding visual framework code or trading actions.

```powershell
python .\tools\ui_data_contract_audit.py
```

The tool writes:

- `reports/ui_data_contract_audit_latest.md`
- `reports/ui_data_contract_audit_latest.json`

This phase does not build Streamlit, does not create buttons, does not modify journal/outcomes, does not connect to a broker, does not send orders, and does not change scanner outputs, scoring, config, weights, thresholds, or signals.

## Streamlit Dashboard MVP

`app.py` is a Streamlit dashboard that renders the UI data contract and exposes controlled paper-trading actions. Report data is loaded through `ui.report_loader.load_all_ui_sources` and `ui.view_models`; paper actions are routed through `ui.actions`.

```powershell
streamlit run .\app.py
python .\tools\streamlit_smoke_test.py
python .\tools\gui_actions_audit.py
```

The smoke and GUI action audits write:

- `reports/streamlit_smoke_test_latest.md`
- `reports/streamlit_smoke_test_latest.json`
- `reports/gui_actions_audit_latest.md`
- `reports/gui_actions_audit_latest.json`

The dashboard can write only through explicit paper-trading actions after confirmation: import candidates to the paper journal, set a paper decision, refresh follow-up reports, manually close a paper trade, and export already closed paper trades to outcomes. Every action is paper trading only; no real order. The dashboard does not run the scanner, does not connect to a broker, does not send orders, and does not change scoring, weights, thresholds, config, or signals. GUI actions are logged in `data/ui_action_log.csv`.

## Live Quote Recheck

Use `live_quote_recheck` when a candidate has stale, missing, invalid, or low-quality execution quote data.

```powershell
python .\tools\live_quote_recheck.py
```

The tool writes:

- `reports/live_quote_recheck_latest.csv`
- `reports/live_quote_recheck_latest.md`
- `reports/live_quote_recheck_latest.json`

The tool does not modify scanner outputs and cannot create entry signals.

## Calibration

Use calibration only after closed trades are recorded.

## Four-day thesis posttest

The historical posttest evaluates only candidates with non-veto signals, an
operational recommendation, `quote_status VALID`,
`execution_quote_quality HIGH`, and valid actionable entry, stop and target
levels. It does not assume an entry: the proposed entry must be reached during
the first two sessions after the scan.

The principal horizon is four trading sessions from the executed entry. The
audit separates target hits, stop hits, profitable four-day closes, negative
closes, ambiguous daily bars where target and stop were both touched, and
proposed entries that were never reached.

Run:

```powershell
python .\tools\run_posttest_batch.py --horizons 4
python .\tools\posttest_thesis_audit.py
```

Review `reports/posttest_thesis_audit_latest.md` for overall and per-ticker win
rates, recurring successes, recurring failures, entry-level quality and
diagnostic hints. Results are observational and never modify scoring,
thresholds or signals automatically.

```powershell
python .\tools\trade_score_calibration.py
python .\tools\calibration_recommendations.py
```

`trade_score_calibration` measures historical outcomes by score buckets and categories.

`calibration_recommendations` produces observations such as insufficient sample, monitor a score bucket, monitor a setup type, monitor checklist status, or monitor options bias.

No calibration tool changes weights, thresholds, config, scanner logic, or signals.

## Release Readiness

Before closing a version, run:

```powershell
python .\tools\release_readiness_audit.py
```

The audit checks required documentation, recent tools, recent tests, Git ignore hygiene, P0 guardrails, daily validation integration, operator index references, manifest outputs, and generated-report tracking risk.

Outputs:

- `reports/release_readiness_latest.md`
- `reports/release_readiness_latest.json`

`FAIL` blocks release closure. `WARN` requires manual review but can be acceptable for optional generated reports or tracked historical artifacts.

## P0 Rules

The P0 rules protect the system from unsafe interpretation:

- No automatic purchase.
- `VETO` and `AVOID` are not operable.
- `WATCHLIST` is monitoring.
- `RECHECK_LIVE_QUOTE` is not entry.
- `TRIGGER_CONFIRMED` requires `quote_status = VALID` and `execution_quote_quality = HIGH`.
- `HIGH_QUALITY_REVIEW` is not an automatic purchase.
- Do not relax quote quality.
- Do not relax execution quote quality.
- Do not use options flow as an automatic trigger.
- Do not change scoring weights automatically.

## Closing A Phase

Before closing a development phase:

1. Confirm the requested files were created or updated.
2. Confirm no scanner logic, scoring, thresholds, or P0 rules were changed unless explicitly requested.
3. Run `python -m pytest -q`.
4. Run `python .\tools\daily_validation.py`.
5. Run `python .\tools\release_readiness_audit.py`.
6. Run `git -c safe.directory="*" status --short`.
7. Review generated report changes and avoid committing ignored runtime artifacts.
8. Commit only intended source, tests, config, and documentation.

## Final Operator Rule

If there is any conflict between ranking and safety, safety wins.

If there is any conflict between setup quality and quote quality, quote quality wins.

If a candidate cannot be verified manually, do not use it operationally.
## GUI visuals

- `app.py` puede mostrar metricas y graficos de revision manual sobre candidatos, calidad, paper trading, follow-up, ciclo y calibracion.
- Los graficos deben construirse desde `ui.view_models` y `ui.charts`; no deben leer reportes directamente ni escribir datos operativos.
- Validar cambios visuales con `python .\tools\gui_visuals_audit.py`.
- La calibracion mostrada en GUI sigue siendo observacional; no cambia pesos automaticamente.

## GUI release hardening

- `ui/guards.py` centraliza confirmaciones, decisiones permitidas, motivos de cierre y terminos prohibidos.
- `ui/formatters.py` centraliza formatos seguros para estados, numeros, porcentajes, precios y textos.
- `ui/layout.py` centraliza mensajes de estado, empty states, notices y tabla de fuentes.
- Validar el release candidate de GUI con `python .\tools\gui_release_audit.py`.
- La interfaz no debe ejecutar scanner, cambiar scoring, cambiar thresholds, conectar servicios de ejecucion ni enviar ordenes reales.

## GUI supervised operation

- `tools/gui_supervised_session.py` registra una sesion diaria supervisada de uso GUI paper-only.
- La bitacora queda en `data/gui_supervised_sessions.csv`.
- Los reportes quedan en `reports/gui_supervised_session_latest.json` y `reports/gui_supervised_session_latest.md`.
- Comandos principales: `--start`, `--status`, `--note`, `--summary`, `--close --result PASS|WARN|FAIL|ABORTED`.
- La herramienta solo lee reportes existentes y el log de acciones GUI; no abre Streamlit, no ejecuta scanner, no modifica journal/outcomes y no envia ordenes reales.
- Validar con `python .\tools\gui_supervised_session_audit.py`.
## Daily GUI Operating Checklist

`tools/gui_daily_operating_checklist.py` creates and maintains the daily GUI operating checklist. It is a manual review artifact for paper trading only. It can initialize today's checklist, show status, mark individual steps as `DONE`, `SKIPPED`, or `BLOCKED`, attach notes, close the checklist with `PASS`, `WARN`, `FAIL`, or `ABORTED`, and regenerate summary reports.

The checklist is intentionally read/manual in spirit: it does not execute scanner runs, does not start Streamlit, does not modify scoring, does not modify paper journal or trade outcomes, does not connect to any execution venue, and does not send real orders. Always keep the notice: paper trading only; no real order.

Primary outputs:

- `reports/gui_daily_operating_checklist_latest.md`
- `reports/gui_daily_operating_checklist_latest.json`
- `reports/gui_daily_operating_checklist_audit_latest.md`
- `reports/gui_daily_operating_checklist_audit_latest.json`

## Alpaca Read-Only Connectivity Audit

`tools/alpaca_readonly_connectivity_audit.py` validates whether Alpaca credentials can read account status, market clock, and IEX latest quote data. This is diagnostic only. It does not place orders, does not enable execution, does not connect the scanner to execution, and does not modify scores, thresholds, config, signals, journal, or outcomes.

Use:

- `python .\tools\alpaca_readonly_connectivity_audit.py`

Review:

- `reports/alpaca_readonly_connectivity_latest.md`
- `reports/alpaca_readonly_connectivity_latest.json`

## Operational Decision Log

`tools/gui_operational_decision_log.py` records human operating decisions made while reviewing the GUI. It is a bitacora for manual reasoning, not a trading engine. It can record ticker, journal id, session id, checklist id, decision type, reason, observed context, perceived risk, follow-up plan, checklist alignment, and later post-session review notes or lessons.

`tools/gui_post_session_review.py` summarizes the day's decisions, decisions without post review, paper-enter decisions, skipped decisions, recheck decisions, high-risk notes, missing reasons, checklist alignment gaps, lessons, and consistency with the UI action log.

Primary outputs:

- `reports/gui_operational_decision_log_latest.md`
- `reports/gui_operational_decision_log_latest.json`
- `reports/gui_post_session_review_latest.md`
- `reports/gui_post_session_review_latest.json`
- `reports/gui_operational_decision_log_audit_latest.md`
- `reports/gui_operational_decision_log_audit_latest.json`

The bitacora does not modify scanner outputs, scoring, thresholds, config, signals, paper journal rows, trade outcomes, or execution state.

## Decision Quality Review

`tools/gui_decision_quality_review.py` evaluates the quality of recorded operating decisions without changing trading logic. It computes a 0-100 `decision_quality_score`, assigns a bucket from `A_DISCIPLINED` through `D_UNDISCIPLINED`, and flags missing reasons, missing post-session reviews, missing follow-up plans, checklist misalignment, low quote quality, missing paper-only confirmation, and repeated ticker reviews without context.

Primary outputs:

- `reports/gui_decision_quality_review_latest.md`
- `reports/gui_decision_quality_review_latest.json`
- `reports/gui_decision_quality_review_latest.csv`
- `reports/gui_decision_quality_audit_latest.md`
- `reports/gui_decision_quality_audit_latest.json`

The review is observational only; no automatic trading changes are applied.

## Weekly GUI Operational Review

`tools/gui_weekly_operational_review.py` summarizes the GUI and paper trading operating cycle over a configurable window. It computes a 0-100 `weekly_operational_score`, a weekly bucket, and an observational recommendation from supervised sessions, daily checklists, GUI decisions, UI action logs, paper journal, outcomes, decision quality, cycle audit, and calibration reports.

```powershell
python .\tools\gui_weekly_operational_review.py
python .\tools\gui_weekly_operational_review.py --days 5
python .\tools\gui_weekly_operational_review_audit.py
```

Primary outputs:

- `data/gui_weekly_operational_reviews.csv`
- `reports/gui_weekly_operational_review_latest.md`
- `reports/gui_weekly_operational_review_latest.json`
- `reports/gui_weekly_operational_review_latest.csv`
- `reports/gui_weekly_operational_review_audit_latest.md`
- `reports/gui_weekly_operational_review_audit_latest.json`

The review is observational only. It does not modify `data/gui_operational_decisions.csv`, `data/paper_trading_journal.csv`, `data/trade_outcomes.csv`, scanner logic, scoring, thresholds, config, weights, or signals. It can mark `READY_FOR_CALIBRATION_REVIEW` only as a human review label, never as an automatic calibration or trading action.

## Evidence Collection Window

`tools/gui_evidence_collection_window.py` consolidates multi-session evidence before any human calibration, ranking, or weight review. It reads supervised sessions, daily checklists, GUI decisions, weekly operational reviews, UI action logs, paper journal, paper outcomes, decision quality, cycle audit, and calibration reports.

```powershell
python .\tools\gui_evidence_collection_window.py
python .\tools\gui_evidence_collection_window.py --days 20
python .\tools\gui_evidence_collection_window.py --min-sessions 10 --min-decisions 40 --min-paper-enters 10 --min-closed-trades 5
python .\tools\gui_evidence_collection_audit.py
```

Primary outputs:

- `data/gui_evidence_collection_windows.csv`
- `reports/gui_evidence_collection_window_latest.md`
- `reports/gui_evidence_collection_window_latest.json`
- `reports/gui_evidence_collection_window_latest.csv`
- `reports/gui_evidence_collection_audit_latest.md`
- `reports/gui_evidence_collection_audit_latest.json`

Readiness states are `INSUFFICIENT_SAMPLE`, `COLLECT_MORE_EVIDENCE`, `PROCESS_REVIEW_REQUIRED`, `READY_FOR_CALIBRATION_REVIEW`, and `NOT_READY_GUARDRAIL_FAILURE`. They are observational labels only. The tool does not modify scanner logic, scoring, thresholds, config, journal rows, outcomes, ranking, calibration, or signals.
