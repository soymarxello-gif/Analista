# Analista

Analista is a conservative, auditable scanner for long-only swing trading candidates in US-listed stocks. ETFs may be used as contextual references when enabled for data/context, but the current operating configuration keeps tradable candidates focused on stocks. It generates reports for manual review; it does not place orders, does not automate purchases, and does not replace operator judgment.

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

Run a read-only deep dive for one ticker without the full universe screener:

```powershell
python .\tools\single_ticker_deep_dive.py AAPL
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

The cockpit has three main sections:

- `Resumen`: quality, release, candidate and macro context summary.
- `Candidatos`: selectable watchlist, per-ticker operational card, single-ticker deep dive, and universe analytics.
- `Control`: quality rules, macro context, calibration, automatic posttest, and report status.

The `Candidatos` view includes `Consulta puntual por ticker`. This runs only the
deep technical/scenario review for the requested ticker. It does not use the
full universe screener, does not apply the macro filter as a blocker, does not
create scanner signals, and does not create `TRIGGER_CONFIRMED`.

Before daily GUI use, validate:

```powershell
python .\tools\streamlit_smoke_test.py
python .\tools\gui_actions_audit.py
python .\tools\gui_visuals_audit.py
python .\tools\gui_release_audit.py
```

The GUI is manual review only. It does not execute the scanner directly, send real orders, modify scanner outputs, or change scoring weights.

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
- Single-ticker deep dive is manual review only and does not create scanner signals.
- Options and institutional flow are contextual only; they do not invalidate setups or participate in scoring until data coverage is reliable.
- Macro context is read-only context and does not modify quote quality or execution status.
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
## Alpaca read-only connectivity audit

`tools/alpaca_readonly_connectivity_audit.py` validates Alpaca credentials and read-only connectivity for account, clock, and IEX latest quote checks. It uses environment variables, masks credentials in reports, and never places orders or enables execution.

Run:

- `python .\tools\alpaca_readonly_connectivity_audit.py`

Outputs:

- `reports/alpaca_readonly_connectivity_latest.json`
- `reports/alpaca_readonly_connectivity_latest.md`

## Automatic candidate posttest

`tools/simple_candidate_posttest.py` is the preferred simple diagnostic loop. It takes only rows saved as automatic `BUY_NOW` posttest memory by the checklist and evaluates outcomes after 5, 10, and 15 sessions. It does not depend on manual trade records, does not modify scanner outputs, and does not change weights or thresholds.

Run:

- `python .\tools\simple_candidate_posttest.py`

Outputs:

- `reports/simple_candidate_posttest_latest.csv`
- `reports/simple_candidate_posttest_latest.json`
- `reports/simple_candidate_posttest_latest.md`
