from __future__ import annotations


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}

def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)

def classify_base_signal(row: dict, config: dict) -> str:
    """
    Classify the row before hard vetoes. Useful for diagnostics.

    This function answers:
    "What would this candidate be if no hard veto existed?"

    BUY_SETUP_ACTIVE remains disabled while signals.buy_setup_active_enabled=false.
    """
    thresholds = config.get("signal_thresholds", {})
    signals_cfg = config.get("signals", {})

    buy = thresholds.get("buy_setup_active", {})
    trigger = thresholds.get("trigger_confirmed", {})
    ready = thresholds.get("ready_wait_trigger", {})
    watch = thresholds.get("watchlist", {})

    buy_enabled = bool(signals_cfg.get("buy_setup_active_enabled", False)) and bool(
        buy.get("enabled", False)
    )

    final_score = _safe_float(row.get("final_score"), 0)
    rr = _safe_float(row.get("rr"), 0)
    trigger_confirmed = _truthy(row.get("trigger_confirmed"))

    if (
        buy_enabled
        and final_score >= buy.get("min_score", 85)
        and rr >= buy.get("min_rr", 2.0)
        and (trigger_confirmed or not buy.get("require_trigger", True))
    ):
        return "BUY_SETUP_ACTIVE"

    if (
        final_score >= trigger.get("min_score", 85)
        and rr >= trigger.get("min_rr", 2.0)
        and (trigger_confirmed or not trigger.get("require_trigger", True))
    ):
        return "TRIGGER_CONFIRMED"

    if (
        final_score >= ready.get("min_score", 80)
        and rr >= ready.get("min_rr", 1.7)
        and not trigger_confirmed
    ):
        return "READY_WAIT_TRIGGER"

    if final_score >= watch.get("min_score", 70):
        return "WATCHLIST"

    return "AVOID"


def classify_signal(row: dict, config: dict):
    """
    Final signal classifier.

    Hard-vetoes block operational use even when final_score is high.
    Soft concerns should be handled in scoring/warnings, not here.
    """
    veto: list[str] = []

    risk_cfg = config.get("risk_reward", {})
    veto_cfg = config.get("veto_rules", {})
    threshold_cfg = veto_cfg.get("thresholds", {})
    filters_cfg = config.get("filters", {})
    universe_cfg = config.get("universe", {})
    signals_cfg = config.get("signals", {})

    min_rr_absolute = risk_cfg.get("min_rr_absolute", 1.5)
    min_trend_score = threshold_cfg.get("min_trend_score", 0.55)
    min_price = _safe_float(filters_cfg.get("min_price"), 10)
    min_market_cap_usd = _safe_float(filters_cfg.get("min_market_cap_usd"), 1_500_000_000)

    allowed_quote_types = {
        str(x).upper()
        for x in universe_cfg.get("allowed_quote_types", ["EQUITY"])
    }

    allowed_states = set(
        signals_cfg.get(
            "allowed_states",
            ["VETO", "AVOID", "WATCHLIST", "READY_WAIT_TRIGGER", "TRIGGER_CONFIRMED"],
        )
    )

    buy_setup_active_enabled = bool(signals_cfg.get("buy_setup_active_enabled", False))

    # Preserve previously detected universe-level veto reasons if present.
    existing_reasons = row.get("all_veto_reasons") or row.get("universe_veto_reasons") or ""
    if isinstance(existing_reasons, str):
        for reason in existing_reasons.replace(",", ";").split(";"):
            reason = reason.strip()
            if reason:
                _append_unique(veto, reason)
    elif isinstance(existing_reasons, list):
        for reason in existing_reasons:
            _append_unique(veto, str(reason).strip())

    # Hard universe filters.
    price = _safe_float(row.get("price"), None)
    if price is not None and price < min_price:
        _append_unique(veto, "price_below_min")

    market_cap = _safe_float(row.get("market_cap"), None)
    if market_cap is not None and market_cap < min_market_cap_usd:
        _append_unique(veto, "market_cap_below_min")

    quote_type = str(row.get("quote_type") or "").upper().strip()
    if quote_type and quote_type not in allowed_quote_types:
        _append_unique(veto, "non_tradable_instrument")
        _append_unique(veto, "excluded_security_type")

    # Data-quality vetoes. Disabled unless configured.
    dq_veto_cfg = veto_cfg.get("data_quality", {})
    if dq_veto_cfg.get("veto_low_confidence", False):
        if str(row.get("data_quality_confidence", "")).upper() == "LOW":
            _append_unique(veto, "data_quality_low")

    if dq_veto_cfg.get("veto_missing_critical", False):
        missing_critical = str(row.get("missing_critical_fields") or "").strip()
        if missing_critical:
            _append_unique(veto, "missing_critical_data")

    # Liquidity is still a hard gate.
    if row.get("liquidity_pass") is False:
        _append_unique(veto, "liquidity_fail")

    # R:R is an operational hard gate.
    if row.get("rr") is None or _safe_float(row.get("rr"), 0) < min_rr_absolute:
        _append_unique(veto, "rr_below_minimum")

    if _safe_float(row.get("trend_score"), 0) < min_trend_score:
        _append_unique(veto, "trend_score_too_weak")

    if row.get("setup_type") in {None, "", "NO_VALID_SETUP"}:
        _append_unique(veto, "no_valid_setup")

    if row.get("earnings_veto") is True:
        _append_unique(veto, "earnings_too_close")

    # Optional: invalid bid/ask can veto only if configured.
    # In the next block, invalid quotes will reduce execution_quote_quality instead.
    if veto_cfg.get("veto_invalid_bid_ask", False) and row.get("bid_ask_valid") is False:
        _append_unique(veto, "invalid_bid_ask")

    if veto:
        return "VETO", veto

    signal = classify_base_signal(row, config)

    # BUY_SETUP_ACTIVE is disabled for the current implementation phase.
    if signal == "BUY_SETUP_ACTIVE" and not buy_setup_active_enabled:
        signal = "TRIGGER_CONFIRMED" if _truthy(row.get("trigger_confirmed")) else "READY_WAIT_TRIGGER"

    # Enforce allowed signal states.
    if signal not in allowed_states:
        signal = "WATCHLIST"

    # Defensive semantic guard:
    # READY_WAIT_TRIGGER must not have trigger_confirmed=True.
    if signal == "READY_WAIT_TRIGGER" and _truthy(row.get("trigger_confirmed")):
        signal = "TRIGGER_CONFIRMED"

    # TRIGGER_CONFIRMED requires an executable quote.
    # Missing quote or execution quality is treated as unsafe.
    quote_status = str(row.get("quote_status") or "MISSING").upper().strip()
    execution_quote_quality = str(row.get("execution_quote_quality") or "LOW").upper().strip()

    if signal == "TRIGGER_CONFIRMED" and (
        execution_quote_quality != "HIGH" or quote_status != "VALID"
    ):
        signal = "WATCHLIST"

    return signal, []
