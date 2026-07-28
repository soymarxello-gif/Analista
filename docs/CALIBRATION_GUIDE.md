# Analista - Calibration Guide

Calibration evaluates whether historical closed trades support current score and state logic. It is not an automatic tuning system.

## Record Closed Trades

Closed trades should be recorded in the outcome tracker format used by the project, normally:

```text
data/trade_outcomes.csv
```

Recommended fields include:

- trade id
- ticker
- status
- entry date
- exit date
- outcome
- PnL percent
- R multiple
- signal at entry review
- recommendation at entry review
- checklist status
- setup type
- score fields
- options bias and confidence
- sector

Only closed trades are used for calibration metrics.

## Simple Automatic Candidate Posttest

The primary feedback loop is now automatic and does not require manual simulated
trades. It takes the best reported candidates from 5, 10, and 15 reported
sessions ago and evaluates whether the thesis worked.

Run:

```powershell
python .\tools\simple_candidate_posttest.py
```

Outputs:

- `reports/simple_candidate_posttest_latest.csv`
- `reports/simple_candidate_posttest_latest.json`
- `reports/simple_candidate_posttest_latest.md`

The posttest focuses only on rows saved as automatic `BUY_NOW` memory by the
checklist. Those rows must have valid actionable levels and execution-quality
guardrails. It checks whether the proposed entry was reached, whether stop or
target were touched, and the outcome after 5, 10, and 15 sessions.

Use it to identify recurring engine issues such as:

- late or overextended entries;
- weak momentum despite high score;
- false breakouts;
- stops too tight or too wide;
- targets too ambitious for the four-session thesis.

Posttest findings are observational. They can suggest what to inspect next, but
they do not change weights, thresholds, levels, signals, or recommendations.

## Run Trade Score Calibration

```powershell
python .\tools\trade_score_calibration.py
```

Outputs:

- `reports/trade_score_calibration_latest.csv`
- `reports/trade_score_calibration_latest.json`
- `reports/trade_score_calibration_latest.md`

Metrics include:

- closed trades
- wins
- losses
- breakeven
- win rate
- average and median PnL percent
- average, median, and total R multiple
- best and worst trade R
- average holding days
- `sample_size_warning`

## Score Buckets

Calibration groups scores into buckets:

- score >= 85
- 75 <= score < 85
- 65 <= score < 75
- score < 65
- missing

It also groups by checklist status, setup type, signal, recommendation, institutional score bucket, options bias, options confidence, and sector when available.

## Interpret `sample_size_warning`

`sample_size_warning` means the sample is too small for reliable calibration.

Current rule of thumb:

- Fewer than 10 closed trades: global sample is insufficient.
- Fewer than 5 trades in a group: group sample is insufficient.

When sample is insufficient:

- Do not change weights.
- Do not change thresholds.
- Do not infer that one setup type is better or worse.
- Keep recording outcomes.
- Treat observations as monitoring notes only.

## Run Calibration Recommendations

```powershell
python .\tools\calibration_recommendations.py
```

Outputs:

- `reports/calibration_recommendations_latest.md`
- `reports/calibration_recommendations_latest.json`

Allowed recommendation types:

- `INSUFFICIENT_SAMPLE`
- `MONITOR_SCORE_BUCKET`
- `MONITOR_SETUP_TYPE`
- `MONITOR_CHECKLIST_STATUS`
- `MONITOR_OPTIONS_BIAS`
- `POSSIBLE_OVERWEIGHT`
- `POSSIBLE_UNDERWEIGHT`
- `NEED_MORE_TRADES`
- `NO_ACTION`

These are review prompts, not commands.

## How To Read Recommendations

Use the language conservatively:

- "monitor" means keep tracking future outcomes.
- "possible" means worth human review only if the sample is sufficient.
- "insufficient sample" means no statistical basis for change.
- "need more trades" means continue logging closed outcomes before calibration decisions.

The JSON field `do_not_change_automatically` must remain `true`.

## Human Review Required

Calibration can suggest what to inspect, but it cannot decide scoring changes.

Any future score or threshold adjustment requires:

1. Enough closed-trade sample.
2. Human review of grouped results.
3. Review of market regime and data-quality context.
4. Tests proving P0 rules remain intact.
5. Separate implementation phase.

No calibration output creates a trade signal or direct recommendation to buy.
