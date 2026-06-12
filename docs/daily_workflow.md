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

This runs the audited scanner, P0 validation, quality gates, optional report builders, candidate cards, calibration, and run manifest.

## 3. Review Reports In This Order

1. `reports/daily_operator_index.md`
2. `reports/daily_quality_gate_latest.md`
3. `reports/live_quote_recheck_latest.md`
4. `reports/trade_decision_checklist_latest.md`
5. `reports/trade_candidate_cards_latest.md`
6. `reports/manual_review_top.md`
7. `reports/daily_run_manifest_latest.md`
8. `reports/daily_validation_summary.txt`
9. `reports/project_preflight_latest.md`
10. `reports/encoding_audit_latest.md`

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

## 8. Calibration

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

## 9. Validate Tests

```powershell
python -m pytest -q
```

## 10. Review Git

```powershell
git -c safe.directory="*" status --short
```

Generated reports and caches should remain ignored. Version code, tests, and durable documentation only.

## 11. Close A Phase With Git

1. Confirm `python -m pytest -q` passes.
2. Confirm `python .\tools\daily_validation.py` passes or returns controlled warnings only.
3. Confirm no P0 rule was relaxed.
4. Review `git -c safe.directory="*" status --short`.
5. Stage only intended code, tests, and docs.
6. Commit with a phase-specific message, for example:

```powershell
git add docs README.md tests
git commit -m "Add Phase 37A operating documentation"
```

Do not commit generated reports unless the project explicitly decides to version a specific reference artifact.
