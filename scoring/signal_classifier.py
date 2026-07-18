from __future__ import annotations


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
    veto: list[str] = []

    filters = config.get("filters", {})
    min_price = float(filters.get("min_price", 10))
    min_market_cap = float(filters.get("min_market_cap_usd", 1_500_000_000))

    price = row.get("price")
    market_cap = row.get("market_cap")
    quote_type = str(row.get("quote_type") or "").strip().upper()

    if price is not None and float(price) < min_price:
        veto.append("price_below_min")
    if market_cap is not None and float(market_cap) < min_market_cap:
        veto.append("market_cap_below_min")
    if quote_type and quote_type != "EQUITY":
        veto.append("non_tradable_instrument")
    if not _as_bool(row.get("liquidity_pass", False)):
        veto.append("liquidity_fail")

    rr = row.get("rr")
    if rr is None or float(rr) < config.get("risk_reward", {}).get("min_rr_absolute", 1.5):
        veto.append("rr_below_minimum")

    if row.get("trend_score", 0) < config.get("veto_rules", {}).get("thresholds", {}).get("min_trend_score", 0.55):
        veto.append("trend_score_too_weak")
    if row.get("setup_type") == "NO_VALID_SETUP":
        veto.append("no_valid_setup")
    if _as_bool(row.get("earnings_veto", False)):
        veto.append("earnings_too_close")

    if veto:
        return "VETO", list(dict.fromkeys(veto))

    score = float(row.get("final_trade_score", row.get("final_score", 0)) or 0)
    rr = float(row.get("rr", 0) or 0)
    trigger = _as_bool(row.get("trigger_confirmed", False))
    quote_quality = str(row.get("execution_quote_quality") or "HIGH").upper()
    thresholds = config.get("signal_thresholds", {})

    trigger_cfg = thresholds.get("trigger_confirmed", {})
    ready_cfg = thresholds.get("ready_wait_trigger", {})
    watch_cfg = thresholds.get("watchlist", {})

    if (
        trigger
        and quote_quality != "LOW"
        and score >= trigger_cfg.get("min_score", 80)
        and rr >= trigger_cfg.get("min_rr", 2.0)
    ):
        return "TRIGGER_CONFIRMED", []

    if (
        not trigger
        and score >= ready_cfg.get("min_score", 80)
        and rr >= ready_cfg.get("min_rr", 1.7)
    ):
        return "READY_WAIT_TRIGGER", []

    if score >= watch_cfg.get("min_score", 70):
        return "WATCHLIST", []

    return "AVOID", []
