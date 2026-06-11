from __future__ import annotations


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def evaluate_execution_review(row: dict) -> dict:
    signal = str(row.get("signal") or "").upper().strip()
    recommendation = str(row.get("recommendation") or "").upper().strip()
    quote_status = str(row.get("quote_status") or "").upper().strip()
    execution_quote_quality = str(row.get("execution_quote_quality") or "").upper().strip()

    final_trade_score = _safe_float(row.get("final_trade_score"), 0.0)
    setup_quality_score = _safe_float(row.get("setup_quality_score"), 0.0)
    rr = _safe_float(row.get("rr"), 0.0)

    quote_low = execution_quote_quality == "LOW" or quote_status in {
        "INVALID",
        "STALE_POSSIBLE",
        "MISSING",
        "WIDE_OR_INCOHERENT",
    }

    reviewable_signal = signal in {
        "WATCHLIST",
        "READY_WAIT_TRIGGER",
        "TRIGGER_CONFIRMED",
    }

    manual_quote_check_required = bool(
        quote_low
        and (
            reviewable_signal
            or recommendation == "RECHECK_LIVE_QUOTE"
        )
    )

    if not manual_quote_check_required:
        return {
            "manual_quote_check_required": False,
            "quote_recheck_priority": "NONE",
            "quote_recheck_reason": "",
        }

    if (
        signal == "WATCHLIST"
        and final_trade_score >= 70
        and setup_quality_score >= 70
        and rr >= 1.7
    ):
        priority = "HIGH"
    elif signal in {"WATCHLIST", "READY_WAIT_TRIGGER"} and final_trade_score >= 65:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    reasons = []

    if quote_status:
        reasons.append(f"quote_status={quote_status}")

    if execution_quote_quality:
        reasons.append(f"execution_quote_quality={execution_quote_quality}")

    if final_trade_score >= 70:
        reasons.append("high_final_trade_score")

    if setup_quality_score >= 70:
        reasons.append("high_setup_quality_score")

    return {
        "manual_quote_check_required": True,
        "quote_recheck_priority": priority,
        "quote_recheck_reason": "; ".join(reasons),
    }