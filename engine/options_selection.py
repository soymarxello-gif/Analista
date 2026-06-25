from __future__ import annotations

from typing import Any


SIGNAL_PRIORITY = {
    "TRIGGER_CONFIRMED": 0,
    "READY_WAIT_TRIGGER": 1,
    "WATCHLIST": 2,
    "AVOID": 3,
    "VETO": 4,
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def select_options_tickers(
    candidates: list[dict[str, Any]],
    *,
    max_tickers: int,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """
    Select option-chain queries using option-neutral candidate quality.

    Options are queried after this selection, so they cannot select themselves
    or act as an automatic signal. Final signal classification remains separate.
    """
    ranked: list[dict[str, Any]] = []
    for candidate in candidates:
        ticker = str(candidate.get("ticker") or "").strip().upper()
        if not ticker or candidate.get("spot") is None:
            continue

        preliminary_signal = str(candidate.get("preliminary_signal") or "AVOID").upper()
        setup_type = str(candidate.get("setup_type") or "").upper()
        technically_valid = (
            setup_type not in {"", "NO_VALID_SETUP", "NONE"}
            and bool(candidate.get("liquidity_pass", False))
            and not bool(candidate.get("earnings_veto", False))
            and _safe_float(candidate.get("rr"), 0.0) > 0
        )
        quote_ready = (
            str(candidate.get("quote_status") or "").upper() == "VALID"
            and str(candidate.get("execution_quote_quality") or "").upper() == "HIGH"
        )

        if preliminary_signal in {"TRIGGER_CONFIRMED", "READY_WAIT_TRIGGER", "WATCHLIST"}:
            selection_group = 0
            reason = f"preliminary_{preliminary_signal.lower()}"
        elif technically_valid:
            selection_group = 1
            reason = "technically_valid_review_candidate"
        else:
            selection_group = 2
            reason = "lower_priority_or_veto_candidate"

        ranked.append(
            {
                "ticker": ticker,
                "selection_group": selection_group,
                "signal_priority": SIGNAL_PRIORITY.get(preliminary_signal, 99),
                "quote_priority": 0 if quote_ready else 1,
                "preliminary_trade_score": _safe_float(
                    candidate.get("preliminary_trade_score"),
                    0.0,
                ),
                "preliminary_final_score": _safe_float(
                    candidate.get("preliminary_final_score"),
                    0.0,
                ),
                "reason": reason,
            }
        )

    ranked.sort(
        key=lambda item: (
            item["selection_group"],
            item["signal_priority"],
            item["quote_priority"],
            -item["preliminary_trade_score"],
            -item["preliminary_final_score"],
            item["ticker"],
        )
    )

    limit = max(int(max_tickers or 0), 0)
    selected = ranked[:limit]
    audit = {
        item["ticker"]: {
            "options_priority_selected": True,
            "options_priority_rank": index,
            "options_priority_reason": item["reason"],
            "options_preliminary_signal": next(
                (
                    signal
                    for signal, priority in SIGNAL_PRIORITY.items()
                    if priority == item["signal_priority"]
                ),
                "UNKNOWN",
            ),
            "options_preliminary_trade_score": round(item["preliminary_trade_score"], 2),
        }
        for index, item in enumerate(selected, start=1)
    }
    return [item["ticker"] for item in selected], audit
