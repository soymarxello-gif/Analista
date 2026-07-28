from __future__ import annotations


def _safe_float(value, default=0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _confidence_factor(value: str | None, mapping: dict[str, float]) -> float:
    key = str(value or "").strip().upper()
    return float(mapping.get(key, mapping.get("DEFAULT", 1.0)))


def calculate_operational_priority(row: dict, config: dict | None = None) -> dict:
    """
    Operational priority is not the thesis score.

    final_score answers:
        "How attractive is the setup?"

    operational_priority_score answers:
        "How much should this candidate be prioritized for manual review today,
        after considering data confidence, source quality, liquidity and veto status?"

    This avoids a high final_score looking equally actionable when data/source quality is weak.
    """
    config = config or {}
    cfg = config.get("operational_priority", {})

    final_score = _safe_float(row.get("final_score"), 0.0)
    final_trade_score = _safe_float(row.get("final_trade_score"), final_score)
    setup_quality_score = _safe_float(row.get("setup_quality_score"), 0.0)

    data_quality_score = _safe_float(row.get("data_quality_score"), 0.75)
    liquidity_score = _safe_float(row.get("liquidity_score"), 0.75)
    source_quality_score = _safe_float(row.get("source_quality_score"), 0.50)

    data_quality_weight = cfg.get("data_quality_weight", 0.30)
    liquidity_weight = cfg.get("liquidity_weight", 0.20)
    source_quality_weight = cfg.get("source_quality_weight", 0.20)
    bid_ask_weight = cfg.get("bid_ask_weight", 0.05)

    data_confidence_map = cfg.get(
        "data_confidence_factor",
        {
            "HIGH": 1.00,
            "MEDIUM": 0.88,
            "LOW": 0.65,
            "DEFAULT": 0.80,
        },
    )

    data_conf_factor = _confidence_factor(row.get("data_quality_confidence"), data_confidence_map)

    # Yahoo bid/ask is often stale, so invalid bid/ask is a mild priority penalty, not a hard veto.
    bid_ask_valid = row.get("bid_ask_valid")
    if bid_ask_valid is None:
        bid_ask_factor = cfg.get("missing_bid_ask_factor", 0.92)
    else:
        bid_ask_factor = 1.0 if _bool(bid_ask_valid) else cfg.get("invalid_bid_ask_factor", 0.88)

    # Weighted confidence composite, bounded conceptually between 0 and 1.
    quality_composite = (
        data_quality_weight * data_quality_score * data_conf_factor
        + liquidity_weight * liquidity_score
        + source_quality_weight * source_quality_score
        + bid_ask_weight * bid_ask_factor
    )

    total_weight = (
        data_quality_weight
        + liquidity_weight
        + source_quality_weight
        + bid_ask_weight
    )
    if total_weight > 0:
        quality_composite = quality_composite / total_weight

    pre_veto_signal = str(row.get("pre_veto_signal") or row.get("signal") or "").upper()
    signal = str(row.get("signal") or "").upper()

    signal_factor_map = cfg.get(
        "signal_factor",
        {
            "TRIGGER_CONFIRMED": 1.00,
            "READY_WAIT_TRIGGER": 0.94,
            "WATCHLIST": 0.86,
            "AVOID": 0.65,
            "VETO": 0.35,
            "DEFAULT": 0.75,
        },
    )

    pre_veto_factor_map = cfg.get(
        "pre_veto_signal_factor",
        {
            "TRIGGER_CONFIRMED": 1.00,
            "READY_WAIT_TRIGGER": 0.96,
            "WATCHLIST": 0.90,
            "AVOID": 0.75,
            "VETO": 0.60,
            "DEFAULT": 0.80,
        },
    )

    signal_factor = float(signal_factor_map.get(signal, signal_factor_map.get("DEFAULT", 0.75)))
    pre_veto_factor = float(pre_veto_factor_map.get(pre_veto_signal, pre_veto_factor_map.get("DEFAULT", 0.80)))

    # VETO is not all equal. A strong pre-veto candidate blocked by data issue should remain visible for audit.
    veto_reasons = str(row.get("veto_reasons") or "")
    audit_recoverable_vetoes = {"data_quality_low", "missing_critical_data", "invalid_bid_ask", "missing_critical_fields"}
    has_recoverable_veto = any(v in veto_reasons for v in audit_recoverable_vetoes)

    strong_pre_veto_signal = pre_veto_signal in {
        "TRIGGER_CONFIRMED",
        "READY_WAIT_TRIGGER",
        "WATCHLIST",
    }

    strong_score = max(final_score, final_trade_score, setup_quality_score) >= 70

    strong_veto_candidate = (
        signal == "VETO"
        and (
            strong_pre_veto_signal
            or strong_score
            or has_recoverable_veto
        )
    )

    if strong_veto_candidate:
        signal_factor = max(signal_factor, cfg.get("recoverable_veto_factor", 0.55))

    operational_score = final_score * quality_composite * signal_factor * pre_veto_factor
    operational_score = max(0.0, min(100.0, operational_score))

    if operational_score >= 80:
        priority_bucket = "A_HIGH_PRIORITY"
    elif operational_score >= 65:
        priority_bucket = "B_REVIEW"
    elif operational_score >= 50:
        priority_bucket = "C_LOW_PRIORITY"
    else:
        priority_bucket = "D_IGNORE"

    warnings = []
    if data_quality_score < 0.75:
        warnings.append("data_quality_score bajo")
    if liquidity_score < 0.70:
        warnings.append("liquidity_score bajo")
    if source_quality_score < 0.40:
        warnings.append("source_quality_score bajo")
    if strong_veto_candidate:
        warnings.append("candidato fuerte bloqueado por veto")

    return {
        "operational_priority_score": round(operational_score, 2),
        "operational_priority_bucket": priority_bucket,
        "quality_composite_score": round(quality_composite, 4),
        "operational_priority_warning": "; ".join(warnings),
    }
