# Analista - Operating Manual

## System Objective

Analista is a conservative, auditable scanner for long-only swing trading candidates in US-listed stocks. ETFs can remain available as market, sector, or macro context when configured, but the current operating configuration does not treat ETFs as automatic tradable candidates. Its purpose is to rank and explain candidates for human review, not to automate trading.

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
6. `reports/simple_candidate_posttest_latest.md`
7. `reports/manual_review_top.md`
8. `reports/daily_run_manifest_latest.md`
9. `reports/release_readiness_latest.md`
10. `reports/ui_data_contract_audit_latest.md`
11. `reports/streamlit_smoke_test_latest.md`
12. `reports/gui_actions_audit_latest.md`
13. `reports/daily_validation_summary.txt`

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

## Operational Readiness

Analista separates attractive candidates from candidates that are timely enough
for manual execution review. `final_trade_score` and `final_score` keep their
original meaning, while these derived fields describe current operability:

- `operational_readiness_score`: conservative timing/readiness score used to
  rank manual review candidates.
- `asset_attractiveness_score`: quality of the asset without implying that the
  current entry is timely.
- `timing_quality_score`: timing quality based on extension, trigger location,
  and distance from moving-average context.
- `momentum_confirmation_score`: quality of current momentum confirmation.
- `ema20_extension_status`: `HEALTHY`, `CAUTION`, `OVEREXTENDED`, or
  `LATE_ENTRY`.
- `macd_histogram_state`: MACD histogram direction, including bullish
  inflection below zero.

Late entries, overextension above EMA20, weak momentum, deteriorating MACD
histogram, invalid structure, and scenario conflicts can degrade or block a
candidate even when the score remains attractive. This layer can only degrade or
preserve a candidate; it must not promote a setup into `TRIGGER_CONFIRMED`.

## Automatic Simple Posttest

`simple_candidate_posttest` is the preferred automatic feedback loop. It selects only candidates saved with `automatic_posttest_status = BUY_NOW` from previous reported sessions and evaluates what happened after 5, 10, and 15 sessions.

```powershell
python .\tools\simple_candidate_posttest.py
```

The tool writes:

- `reports/simple_candidate_posttest_latest.csv`
- `reports/simple_candidate_posttest_latest.md`
- `reports/simple_candidate_posttest_latest.json`

The report is observational. It uses only automatic scanner memory, does not modify scanner outputs, scores, config, weights, thresholds, signals, trade outcomes, or execution state.

## UI Data Contract

`ui/report_loader.py` and `ui/view_models.py` define the read-only data contract for a future graphical interface. The loader reads generated reports and normalizes missing, invalid, empty, and available states. The view models convert those sources into GUI-ready dictionaries without adding visual framework code or trading actions.

```powershell
python .\tools\ui_data_contract_audit.py
```

The tool writes:

- `reports/ui_data_contract_audit_latest.md`
- `reports/ui_data_contract_audit_latest.json`

This phase does not build Streamlit, does not create buttons, does not modify outcomes, does not connect to a broker, does not send orders, and does not change scanner outputs, scoring, config, weights, thresholds, or signals.

## Streamlit Dashboard MVP

`app.py` is the Streamlit operating cockpit. It renders the UI data contract,
shows the current watchlist, macro context, report health, calibration context,
and exposes controlled read-only actions. Report data is loaded through
`ui.report_loader.load_all_ui_sources` and `ui.view_models`; actions are routed
through `ui.actions`.

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

The cockpit has three primary sections:

- `Resumen`: daily status, quality gate, release readiness, candidate counts,
  quote quality and a compact macro context summary.
- `Candidatos`: selectable watchlist, per-ticker operational card, single-ticker
  deep dive, second-opinion prompt, and full-width analytics.
- `Control`: quality rules, macro context, calibration, simple posttest, and
  report-source status.

The dashboard can trigger only controlled actions: refresh generated reports
through daily validation and run the single-ticker deep dive, which writes only
its own report files. Every action is manual-review only; no real order. The
dashboard does not run the full scanner directly, does not connect to a broker,
does not send orders, and does not change scoring, weights, thresholds, config,
or signals. GUI actions are logged in `data/ui_action_log.csv`.

## Single-Ticker Deep Dive

`tools/single_ticker_deep_dive.py` provides an on-demand read-only analysis for
one ticker. It is available from `Candidatos -> Consulta puntual por ticker` in
the cockpit and from the command line:

```powershell
python .\tools\single_ticker_deep_dive.py AAPL
```

The tool uses the deep technical/scenario layer for the requested ticker:

- OHLCV history and indicators.
- Structure/setup detection.
- Momentum, extension and entry-timing diagnostics.
- Entry, stop, target, R/R and shadow level diagnostics.
- Metadata/fundamentals when available.
- Options context when enabled and available.

It intentionally does not run the full universe screener, does not use the
candidate funnel, does not apply macro context as an operative blocker, and does
not create scanner signals. Its outputs are:

- `reports/single_ticker_deep_dive_latest.json`
- `reports/single_ticker_deep_dive_latest.md`

Guardrails:

- `manual_review_only = True`.
- `execution_enabled = False`.
- `creates_trading_signal = False`.
- It does not create `TRIGGER_CONFIRMED`.
- It does not modify scanner reports, watchlists, outcomes,
  scoring weights, thresholds, or config.

Use it to inspect a ticker that is not currently in the watchlist or to compare
human intuition against the engine's scenario diagnostics. Treat the result as a
manual research card, not as an execution instruction.

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

## Automatic engine posttest

The current diagnostic posttest is fully automatic. It reads the scanner memory
created by `trade_decision_checklist`, keeps only `BUY_NOW` posttest candidates,
and reviews what happened after 5, 10 and 15 sessions. It reports recurring
successes and failures without changing scoring, thresholds or signals.
It also tracks a separate shadow cohort of technically clean
`TACTICAL_RESEARCH` rows to measure possible false negatives. Shadow results
cannot become execution candidates.

Run:

```powershell
python .\tools\simple_candidate_posttest.py
```

Review `reports/simple_candidate_posttest_latest.md`.

## Closed-Bar Policy And Analysis Tiers

All EOD technical evidence uses completed bars. Before 16:20 New York time,
the current Yahoo daily candle is excluded from EMA20, ATR, relative volume,
setups, MACD and R/R. Weekly MACD uses completed weeks only.

- `ADVANCE_DEEP_ANALYSIS` / `OPERATIONAL`: strict technical candidate. It still
  requires every quote and P0 guardrail.
- `ADVANCE_RESEARCH_ANALYSIS` / `RESEARCH`: high-quality forming setup or mild
  timing caution. It cannot enter the execution checklist, automatic posttest,
  or produce `TRIGGER_CONFIRMED`.
- `rr_status = DIAGNOSTIC_ONLY`: the target lacks sufficient independent
  confirmation. Confluent target models may validate R/R with `MEDIUM`
  confidence, still subject to every guardrail.

The candidate cockpit keeps **Oportunidades operativas** and **Radar de
investigación** visibly separate.

The institutional decision book adds:

- `EXECUTION_CANDIDATE`: strict operational review.
- `TACTICAL_RESEARCH`: promising thesis requiring confirmation.
- `LEADERSHIP_RESET_WATCH`: strong but extended; wait for reset.
- `MOMENTUM_RECOVERY_WATCH`: daily or weekly MACD must improve again.
- `STRUCTURAL_REJECT`: invalid structure, instrument or liquidity.
- `DATA_BLOCKED`: insufficient evidence.

The engine evaluates all setup hypotheses and retains a primary thesis plus
alternatives. Daily or weekly MACD deceleration never reaches execution or
tactical research.

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

- `app.py` puede mostrar metricas y graficos de revision manual sobre candidatos, calidad, macro, posttest simple y calibracion.
- Los graficos deben construirse desde `ui.view_models` y `ui.charts`; no deben leer reportes directamente ni escribir datos operativos.
- Validar cambios visuales con `python .\tools\gui_visuals_audit.py`.
- La calibracion mostrada en GUI sigue siendo observacional; no cambia pesos automaticamente.

## GUI release hardening

- `ui/guards.py` centraliza confirmaciones, decisiones permitidas, motivos de cierre y terminos prohibidos.
- `ui/formatters.py` centraliza formatos seguros para estados, numeros, porcentajes, precios y textos.
- `ui/layout.py` centraliza mensajes de estado, empty states, notices y tabla de fuentes.
- Validar el release candidate de GUI con `python .\tools\gui_release_audit.py`.
- La interfaz no debe ejecutar scanner, cambiar scoring, cambiar thresholds, conectar servicios de ejecucion ni enviar ordenes reales.

## Alpaca Read-Only Connectivity Audit

`tools/alpaca_readonly_connectivity_audit.py` validates whether Alpaca credentials can read account status, market clock, and IEX latest quote data. This is diagnostic only. It does not place orders, does not enable execution, does not connect the scanner to execution, and does not modify scores, thresholds, config, signals, or outcomes.

Use:

- `python .\tools\alpaca_readonly_connectivity_audit.py`

Review:

- `reports/alpaca_readonly_connectivity_latest.md`
- `reports/alpaca_readonly_connectivity_latest.json`

## Resilient FRED Macro Context

`tools/macro_event_context.py` retrieves official rates, yield curves,
liquidity, inflation, employment, volatility, credit, dollar, and oil series.
It uses pandas-datareader first, direct FRED CSV second, and a local stale
cache only when both network paths fail.

Use:

- `python .\tools\macro_event_context.py`

Review provider and freshness per series in:

- `reports/macro_event_context_latest.md`
- `reports/macro_event_context_latest.json`

Yahoo comparisons are informational. Macro data remains read-only context and
cannot modify scores, signals, quote quality, or execution status.

In the cockpit, macro appears in two places:

- `Resumen`: compact event/liquidity summary for daily situational awareness.
- `Control -> Contexto macro`: full source, freshness, FRED series and economic
  calendar view.

Macro context helps the operator avoid blind review during major event risk, but
it is not an automatic blocker in single-ticker deep dive and it never relaxes
P0 execution rules.

## Nasdaq Risk Regime

`tools/nasdaq_risk_regime_audit.py` integrates the Nasdaq semaforo model as a
read-only regime audit. It combines Yahoo Finance market series, Cboe aggregate
equity put/call data, credit/volatility/breadth pressure, and QQQ trend context.

Use:

- `python .\tools\nasdaq_risk_regime_audit.py`

Review:

- `reports/nasdaq_risk_regime_latest.md`
- `reports/nasdaq_risk_regime_latest.json`

The regimes are operational context only:

- `NASDAQ_NORMAL`
- `NASDAQ_DISTRIBUTION_OMEGA`
- `NASDAQ_SYSTEMIC_SIGMA`
- `NASDAQ_CAPITULATION_PHI`

The audit does not modify scanner rows, scoring, signals, thresholds,
`quote_status`, `execution_quote_quality`, or broker execution. Sigma/Phi/Omega
language must be read as risk context for manual review, never as an automatic
buy, sell, liquidation, or entry instruction.
