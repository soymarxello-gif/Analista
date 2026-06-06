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
    veto = []

    if not _as_bool(row.get("liquidity_pass", False)):
        veto.append("liquidity_fail")

    if row.get("rr") is None or row.get("rr", 0) < config.get("risk_reward", {}).get("min_rr_absolute", 1.5):
        veto.append("rr_below_minimum")

    if row.get("trend_score", 0) < config.get("veto_rules", {}).get("thresholds", {}).get("min_trend_score", 0.55):
        veto.append("trend_score_too_weak")

    if row.get("setup_type") == "NO_VALID_SETUP":
        veto.append("no_valid_setup")

    if _as_bool(row.get("earnings_veto", False)):
        veto.append("earnings_too_close")

    if veto:
        return "VETO", veto

    score = row.get("final_score", 0)
    rr = row.get("rr", 0)
    trigger = _as_bool(row.get("trigger_confirmed", False))
    thresholds = config.get("signal_thresholds", {})

    buy_cfg = thresholds.get("buy_setup_active", {})
    ready_cfg = thresholds.get("ready_wait_trigger", {})
    watch_cfg = thresholds.get("watchlist", {})

    if (
        score >= buy_cfg.get("min_score", 85)
        and trigger
        and rr >= buy_cfg.get("min_rr", 2.0)
    ):
        return "BUY_SETUP_ACTIVE", []

    if (
        score >= ready_cfg.get("min_score", 80)
        and rr >= ready_cfg.get("min_rr", 1.7)
    ):
        return "READY_WAIT_TRIGGER", []

    if score >= watch_cfg.get("min_score", 70):
        return "WATCHLIST", []

    return "AVOID", []
