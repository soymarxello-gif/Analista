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
6. `reports/manual_review_top.md`
7. `reports/daily_run_manifest_latest.md`
8. `reports/daily_validation_summary.txt`

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

```powershell
python .\tools\trade_score_calibration.py
python .\tools\calibration_recommendations.py
```

`trade_score_calibration` measures historical outcomes by score buckets and categories.

`calibration_recommendations` produces observations such as insufficient sample, monitor a score bucket, monitor a setup type, monitor checklist status, or monitor options bias.

No calibration tool changes weights, thresholds, config, scanner logic, or signals.

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
5. Run `git -c safe.directory="*" status --short`.
6. Review generated report changes and avoid committing ignored runtime artifacts.
7. Commit only intended source, tests, config, and documentation.

## Final Operator Rule

If there is any conflict between ranking and safety, safety wins.

If there is any conflict between setup quality and quote quality, quote quality wins.

If a candidate cannot be verified manually, do not use it operationally.
