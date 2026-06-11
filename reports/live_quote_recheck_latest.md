# Analista — live quote recheck

> Revalidación auxiliar. No modifica ranking, señales ni recomendaciones.

## Resumen

- QUOTE_OK_FOR_MANUAL_REVIEW: 2
- QUOTE_STILL_UNCONFIRMED: 8
- QUOTE_FETCH_FAILED: 0

## QUOTE_OK_FOR_MANUAL_REVIEW

| rank | ticker | signal | recommendation | quote_status | execution_quote_quality | live_recheck_decision | live_quote_status | live_execution_quote_quality | live_price | live_bid | live_ask | live_spread_pct | setup_persistence_score | final_trade_score | rr | live_quote_warning | live_fetch_error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 16 | APH | WATCHLIST | RECHECK_LIVE_QUOTE | INVALID | LOW | QUOTE_OK_FOR_MANUAL_REVIEW | VALID | HIGH | 154.07000732421875 | 153.02 | 154.01 | 0.006426 | 79.0 | 84.52 | 2.9936977677968013 |  |  |
| 23 | UNM | WATCHLIST | RECHECK_LIVE_QUOTE | INVALID | LOW | QUOTE_OK_FOR_MANUAL_REVIEW | VALID | HIGH | 88.0 | 87.94 | 87.99 | 0.000568 | 79.0 | 79.7 | 2.0 |  |  |

## QUOTE_STILL_UNCONFIRMED

| rank | ticker | signal | recommendation | quote_status | execution_quote_quality | live_recheck_decision | live_quote_status | live_execution_quote_quality | live_price | live_bid | live_ask | live_spread_pct | setup_persistence_score | final_trade_score | rr | live_quote_warning | live_fetch_error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 14 | WWD | WATCHLIST | RECHECK_LIVE_QUOTE | INVALID | LOW | QUOTE_STILL_UNCONFIRMED | INVALID | LOW | 380.75 | 381.56 | 376.36 |  | 79.0 | 85.69 | 3.3807142038639566 | ask_less_or_equal_bid |  |
| 15 | AMRX | WATCHLIST | RECHECK_LIVE_QUOTE | STALE_POSSIBLE | LOW | QUOTE_STILL_UNCONFIRMED | STALE_POSSIBLE | LOW | 14.6899995803833 | 10.55 | 17.9 | 0.50034 | 79.0 | 84.65 | 3.016789466664403 | bid_ask_far_from_last_price |  |
| 17 | MRX | WATCHLIST | RECHECK_LIVE_QUOTE | STALE_POSSIBLE | LOW | QUOTE_STILL_UNCONFIRMED | STALE_POSSIBLE | LOW | 60.4900016784668 | 43.43 | 60.51 | 0.282361 | 79.0 | 83.43 | 2.0 | bid_ask_far_from_last_price |  |
| 18 | ALHC | WATCHLIST | RECHECK_LIVE_QUOTE | STALE_POSSIBLE | LOW | QUOTE_STILL_UNCONFIRMED | STALE_POSSIBLE | LOW | 19.200000762939453 | 13.98 | 19.23 | 0.273437 | 79.0 | 82.46 | 4.000000000000004 | bid_ask_far_from_last_price |  |
| 19 | ESTA | WATCHLIST | RECHECK_LIVE_QUOTE | STALE_POSSIBLE | LOW | QUOTE_STILL_UNCONFIRMED | STALE_POSSIBLE | LOW | 79.81999969482422 | 57.66 | 97.89 | 0.504009 | 79.0 | 82.33 | 1.9999999999999976 | bid_ask_far_from_last_price |  |
| 20 | CECO | WATCHLIST | RECHECK_LIVE_QUOTE | STALE_POSSIBLE | LOW | QUOTE_STILL_UNCONFIRMED | STALE_POSSIBLE | LOW | 95.44499969482422 | 68.12 | 95.0 | 0.281628 | 78.48 | 81.8 | 1.9999999999999984 | bid_ask_far_from_last_price |  |
| 21 | PTGX | WATCHLIST | RECHECK_LIVE_QUOTE | STALE_POSSIBLE | LOW | QUOTE_STILL_UNCONFIRMED | STALE_POSSIBLE | LOW | 105.87000274658203 | 76.25 | 125.61 | 0.466232 | 79.0 | 80.73 | 2.8649223433307243 | bid_ask_far_from_last_price |  |
| 22 | ARCB | WATCHLIST | RECHECK_LIVE_QUOTE | MISSING | LOW | QUOTE_STILL_UNCONFIRMED | STALE_POSSIBLE | LOW | 173.22000122070312 | 124.02 | 210.82 | 0.501097 | 72.27 | 79.83 | 2.000000000000003 | bid_ask_far_from_last_price |  |

## QUOTE_FETCH_FAILED

_Sin candidatos._
