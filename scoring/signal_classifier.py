from __future__ import annotations


EXCLUDED_QUOTE_TYPES = {
    "ETF",
    "ETN",
    "MUTUALFUND",
    "MUTUAL_FUND",
    "PREFERRED",
    "PREFERRED_SHARE",
    "WARRANT",
    "RIGHT",
    "UNIT",
    "CLOSED_END_FUND",
}


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "pass"}
    return bool(value)


def classify_signal(row: dict, config: dict) -> tuple[str, list[str]]:
    """Classify the desktop candidate using the same signal semantics as Android.

    VETO is reserved for confirmed universe/eligibility violations. Missing metadata,
    execution/liquidity quality, setup quality, trend and risk-plan deficiencies are
    downgrade/avoid reasons and must not be promoted to hard vetoes.
    """
    hard_veto: list[str] = []

    filters = config.get("filters", {})
    min_price = float(filters.get("min_price", 10))
    min_market_cap = float(filters.get("min_market_cap_usd", 1_500_000_000))

    price = row.get("price")
    market_cap = row.get("market_cap")
    quote_type = str(row.get("quote_type") or "").strip().upper()

    if price is not None and float(price) < min_price:
        hard_veto.append("price_below_min")
    if market_cap is not None and float(market_cap) < min_market_cap:
        hard_veto.append("market_cap_below_min")
    if quote_type in EXCLUDED_QUOTE_TYPES:
        hard_veto.append("excluded_security_type")
    elif quote_type and quote_type != "EQUITY":
        hard_veto.append("non_tradable_instrument")

    if hard_veto:
        return "VETO", list(dict.fromkeys(hard_veto))

    # Thesis/risk invalidation is AVOID, not a universe veto.
    if row.get("setup_type") == "NO_VALID_SETUP":
        return "AVOID", ["no_valid_setup"]
    if _as_bool(row.get("failed_breakout", False)):
        return "AVOID", ["failed_breakout"]
    if _as_bool(row.get("earnings_veto", False)):
        return "AVOID", ["earnings_too_close"]

    rr = row.get("rr")
    minimum_rr = float(config.get("risk_reward", {}).get("min_rr_absolute", 1.5))
    if rr is None or float(rr) < minimum_rr:
        return "AVOID", ["rr_below_minimum"]

    minimum_trend = float(config.get("veto_rules", {}).get("thresholds", {}).get("min_trend_score", 0.55))
    if float(row.get("trend_score", 0) or 0) < minimum_trend:
        return "AVOID", ["trend_score_too_weak"]

    score = float(row.get("final_trade_score", row.get("final_score", 0)) or 0)
    rr_value = float(row.get("rr", 0) or 0)
    trigger = _as_bool(row.get("trigger_confirmed", False))
    quote_quality = str(row.get("execution_quote_quality") or "HIGH").upper()
    liquidity_pass = _as_bool(row.get("liquidity_pass", False))
    eligibility_verified = price is not None and market_cap is not None and bool(quote_type)
    thresholds = config.get("signal_thresholds", {})

    trigger_cfg = thresholds.get("trigger_confirmed", {})
    ready_cfg = thresholds.get("ready_wait_trigger", {})
    watch_cfg = thresholds.get("watchlist", {})

    # Unknown eligibility is not a veto, but it cannot authorize an execution contract.
    if not eligibility_verified:
        return "WATCHLIST", ["eligibility_metadata_unverified"]

    # Execution-quality failures can retain a watchlist thesis but cannot authorize a contract.
    if not liquidity_pass:
        return "WATCHLIST", ["liquidity_unconfirmed"]
    if quote_quality == "LOW":
        return "WATCHLIST", ["execution_quote_unconfirmed"]

    if (
        trigger
        and score >= trigger_cfg.get("min_score", 80)
        and rr_value >= trigger_cfg.get("min_rr", 2.0)
    ):
        return "TRIGGER_CONFIRMED", []

    if (
        not trigger
        and score >= ready_cfg.get("min_score", 80)
        and rr_value >= ready_cfg.get("min_rr", 1.7)
    ):
        return "READY_WAIT_TRIGGER", []

    if score >= watch_cfg.get("min_score", 70):
        return "WATCHLIST", []

    return "AVOID", []
