# Analista

Analista is a conservative, auditable scanner for long-only swing trading candidates in US-listed stocks and ETFs. It generates reports for manual review; it does not place orders, does not automate purchases, and does not replace operator judgment.

## Quick Start

From PowerShell in the project root:

```powershell
.\.venv\Scripts\Activate.ps1
python .\tools\daily_validation.py
```

Then review:

```text
reports/daily_operator_index.md
reports/daily_quality_gate_latest.md
reports/live_quote_recheck_latest.md
reports/trade_decision_checklist_latest.md
reports/trade_candidate_cards_latest.md
reports/manual_review_top.md
reports/daily_run_manifest_latest.md
```

## Main Commands

Run the full daily workflow:

```powershell
python .\tools\daily_validation.py
```

Validate tests:

```powershell
python -m pytest -q
```

Run live quote recheck:

```powershell
python .\tools\live_quote_recheck.py
```

Generate the manual decision checklist:

```powershell
python .\tools\trade_decision_checklist.py
```

Generate candidate cards:

```powershell
python .\tools\trade_candidate_cards.py
```

Run calibration reports:

```powershell
python .\tools\trade_score_calibration.py
python .\tools\calibration_recommendations.py
```

Run release readiness audit:

```powershell
python .\tools\release_readiness_audit.py
```

## Launching the GUI

Run the controlled Streamlit interface:

```powershell
streamlit run .\app.py
```

Before daily GUI use, validate:

```powershell
python .\tools\streamlit_smoke_test.py
python .\tools\gui_actions_audit.py
python .\tools\gui_visuals_audit.py
python .\tools\gui_release_audit.py
```

The GUI is manual review and paper trading only. It does not execute the scanner, send real orders, or change scoring weights.

## Supervised GUI operation

Record a supervised paper-only GUI session:

```powershell
python .\tools\gui_supervised_session.py --start
python .\tools\gui_supervised_session.py --status
python .\tools\gui_supervised_session.py --note "Daily supervised GUI review"
python .\tools\gui_supervised_session.py --summary
python .\tools\gui_supervised_session.py --close --result PASS
python .\tools\gui_supervised_session_audit.py
```

The supervised session log is stored in `data/gui_supervised_sessions.csv`; reports are generated under `reports/gui_supervised_session_latest.*`.

Review Git state:

```powershell
git -c safe.directory="*" status --short
```

## Safety Summary

- No compra automática.
- `BUY_SETUP_ACTIVE` remains disabled.
- `VETO` and `AVOID` are not operable.
- `WATCHLIST` is monitoring.
- `RECHECK_LIVE_QUOTE` is not an entry.
- `TRIGGER_CONFIRMED` requires `quote_status = VALID` and `execution_quote_quality = HIGH`.
- `HIGH_QUALITY_REVIEW` is for manual review only.
- Options and institutional flow are contextual, conservative, and not automatic triggers.
- Calibration does not change weights or thresholds automatically.

## Documentation

- [Operating Manual](docs/OPERATING_MANUAL.md)
- [Daily Workflow](docs/DAILY_WORKFLOW.md)
- [Reports Reference](docs/REPORTS_REFERENCE.md)
- [Safety Rules](docs/SAFETY_RULES.md)
- [Calibration Guide](docs/CALIBRATION_GUIDE.md)

Older runbook files may remain for compatibility, but the files above are the Phase 37A operating documentation.

## Generated Artifacts

Most files in `reports/`, `cache/`, `logs/`, `.pytest_cache/`, and `__pycache__/` are generated artifacts and should not be versioned unless explicitly selected as stable references.

## Disclaimer

Analista is analytical software for manual decision support. It is not financial advice and does not execute trades.
## Daily GUI operating checklist

Phase 40B adds `tools/gui_daily_operating_checklist.py` for a manual, paper-only operating checklist around the Streamlit GUI. It records operator confirmations, notes, blocked steps, skipped steps, and a daily close result without running tests, scanner, Streamlit, broker APIs, or real orders.

Core commands:

- `python .\tools\gui_daily_operating_checklist.py --init-today`
- `python .\tools\gui_daily_operating_checklist.py --status`
- `python .\tools\gui_daily_operating_checklist.py --mark STEP_ID DONE --note "..."`
- `python .\tools\gui_daily_operating_checklist.py --close --result WARN`
- `python .\tools\gui_daily_operating_checklist.py --summary`
- `python .\tools\gui_daily_operating_checklist_audit.py`

Outputs are `reports/gui_daily_operating_checklist_latest.json`, `reports/gui_daily_operating_checklist_latest.md`, `reports/gui_daily_operating_checklist_audit_latest.json`, and `reports/gui_daily_operating_checklist_audit_latest.md`.

## Alpaca read-only connectivity audit

`tools/alpaca_readonly_connectivity_audit.py` validates Alpaca credentials and read-only connectivity for account, clock, and IEX latest quote checks. It uses environment variables, masks credentials in reports, and never places orders or enables execution.

Run:

- `python .\tools\alpaca_readonly_connectivity_audit.py`

Outputs:

- `reports/alpaca_readonly_connectivity_latest.json`
- `reports/alpaca_readonly_connectivity_latest.md`

## Operational decision log

`tools/gui_operational_decision_log.py` records manual GUI operating decisions for paper-only review. It can associate a decision with a ticker, journal id, session id, checklist id, or action log id, then capture reason, context, perceived risk, follow-up plan, and post-session lessons. It does not edit the paper journal, outcomes, scanner, scoring, config, thresholds, or signals.

Core commands:

- `python .\tools\gui_operational_decision_log.py --add --ticker AAPL --decision PAPER_WATCH --reason "..."`
- `python .\tools\gui_operational_decision_log.py --list-today`
- `python .\tools\gui_operational_decision_log.py --review DECISION_ID --outcome-note "..." --lesson "..."`
- `python .\tools\gui_operational_decision_log.py --summary`
- `python .\tools\gui_post_session_review.py`
- `python .\tools\gui_operational_decision_log_audit.py`

## Decision quality review

`tools/gui_decision_quality_review.py` evaluates operating discipline from the GUI decision log, supervised sessions, daily checklist, and GUI action log. It is observational only and does not change signals, scoring, thresholds, calibration, paper journal rows, outcomes, or execution state.

Run:

- `python .\tools\gui_decision_quality_review.py`
- `python .\tools\gui_decision_quality_audit.py`

Outputs:

- `reports/gui_decision_quality_review_latest.json`
- `reports/gui_decision_quality_review_latest.md`
- `reports/gui_decision_quality_review_latest.csv`
- `reports/gui_decision_quality_audit_latest.json`
- `reports/gui_decision_quality_audit_latest.md`
