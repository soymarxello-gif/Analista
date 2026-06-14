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
