# Analista - Safety Rules

Analista is a manual decision-support system for long-only swing trading candidates in US-listed stocks. ETFs may be used as contextual market references when configured, but they are not automatic operable candidates under the current safety posture. It does not place orders, does not size positions, and does not replace operator judgment.

## Non-Negotiable Rules

- No compra automática.
- `BUY_SETUP_ACTIVE` sigue deshabilitado.
- `VETO` no es operable.
- `AVOID` no es operable.
- `WATCHLIST` no es compra; es monitoreo.
- `RECHECK_LIVE_QUOTE` exige validacion en vivo.
- `TRIGGER_CONFIRMED` exige `quote_status = VALID` y `execution_quote_quality = HIGH`.
- `HIGH_QUALITY_REVIEW` no equivale a compra.
- `single_ticker_deep_dive` no crea señales del scanner ni habilita entrada.
- No relajar `quote_status`.
- No relajar `execution_quote_quality`.
- No cambiar pesos ni thresholds automaticamente.

## Manual Review Required

Before any external trading decision, review:

- Daily chart and weekly context.
- Volume and relative volume.
- Bid, ask, spread, and current price.
- Actionable entry, stop, target, and R/R.
- ATR stop status.
- Earnings date or next earnings date.
- News, gaps, unusual events, and macro context.
- Sector behavior and relative strength.
- Options and institutional-flow context.

## Quote And Execution Quality

`RECHECK_LIVE_QUOTE` is not an entry. It means current quote quality is not sufficient for execution review.

If live bid/ask is missing, stale, invalid, or too wide, keep the candidate out of execution review. If last price is used because bid/ask is unavailable, the case requires manual review and spread must be treated as unknown.

## Options And Institutional Flow

Options and institutional-flow data are context only. They do not invalidate a setup and do not participate in scoring until options coverage is reliable. They are not an automatic trigger and are not a hard veto in the current system.

Unknown options flow must be reported as unknown or unavailable. Do not invent options data.

## Macro Context

Macro context is read-only situational awareness. It can appear in the scanner,
daily reports, and GUI cockpit, but it does not relax quote quality, execution
quality, signal rules, or P0 guardrails.

Single-ticker deep dive intentionally does not use macro as an operative blocker.
If macro event risk is elevated, the operator must still review the event
calendar manually before any external trading decision.

## Single-Ticker Deep Dive

The single-ticker deep dive is a manual research tool. It may diagnose a valid
technical scenario, late entry, weak momentum, invalid structure, quote issue,
or missing data for a requested ticker.

It must not be interpreted as:

- a scanner signal;
- an execution authorization;
- a `TRIGGER_CONFIRMED` generator;
- a replacement for live quote review;
- a reason to bypass earnings, news, sector or macro review.

## Calibration Safety

Trade score calibration and calibration recommendations are observational only.

- Calibration does not change weights automatically.
- Calibration does not change thresholds automatically.
- Calibration does not create entry signals.
- Insufficient sample size must remain explicit.
- Human review is required before any future scoring change.

## PASS, WARN, FAIL

- `PASS`: flow completed without blocking errors. Manual review is still required.
- `WARN`: flow completed with data-quality or optional-step warnings. Use reinforced manual review.
- `FAIL`: blocking issue. Do not use candidates operationally until fixed.

When ranking conflicts with safety, safety wins.
