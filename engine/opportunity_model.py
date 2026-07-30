from __future__ import annotations

from typing import Any

import pandas as pd


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def build_extension_distribution_features(
    df: pd.DataFrame,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    result = dict(evidence or {})
    if df is None or df.empty or "close" not in df.columns:
        result["ema20_distance_percentile_1y"] = None
        return result

    ema_column = "ema20" if "ema20" in df.columns else "ma20" if "ma20" in df.columns else None
    if ema_column is None:
        result["ema20_distance_percentile_1y"] = None
        return result

    close = pd.to_numeric(df["close"], errors="coerce")
    ema20 = pd.to_numeric(df[ema_column], errors="coerce")
    distances = ((close / ema20) - 1.0).replace([float("inf"), float("-inf")], pd.NA)
    distances = distances.dropna().tail(252)
    if distances.empty:
        result["ema20_distance_percentile_1y"] = None
        return result

    latest = float(distances.iloc[-1])
    positive_history = distances[distances >= 0]
    if latest <= 0 or positive_history.empty:
        percentile = 0.0
    else:
        percentile = float((positive_history <= latest).mean())
    result["ema20_distance_percentile_1y"] = round(percentile, 4)
    result["ema20_distance_reference"] = "EMA20" if ema_column == "ema20" else "SMA20_FALLBACK"
    return result


def calculate_opportunity_scores(
    *,
    setup_quality: float,
    momentum_quality: float,
    trend_compatibility: float,
    extension_risk: float,
    liquidity_quality: float,
    rr_quality: float,
    data_confidence: float = 0.5,
    context_confidence: float = 0.5,
) -> dict[str, float | str]:
    setup = _clip(setup_quality)
    momentum = _clip(momentum_quality)
    trend = _clip(trend_compatibility)
    timing = _clip(1.0 - extension_risk)
    liquidity = _clip(liquidity_quality)
    rr = _clip(rr_quality)
    data = _clip(data_confidence)
    context = _clip(context_confidence)

    technical_asset_quality = 100.0 * (
        0.34 * setup
        + 0.28 * momentum
        + 0.18 * trend
        + 0.12 * liquidity
        + 0.08 * data
    )
    entry_readiness = 100.0 * (
        0.34 * timing
        + 0.24 * setup
        + 0.20 * momentum
        + 0.12 * trend
        + 0.10 * rr
    )
    research_priority = 100.0 * (
        0.30 * setup
        + 0.22 * momentum
        + 0.16 * trend
        + 0.12 * timing
        + 0.10 * liquidity
        + 0.05 * rr
        + 0.05 * data
    )
    reset_watch = 100.0 * (
        0.38 * setup
        + 0.28 * momentum
        + 0.18 * trend
        + 0.10 * liquidity
        + 0.06 * context
    )
    return {
        "technical_asset_quality_score": round(technical_asset_quality, 2),
        "entry_readiness_score": round(entry_readiness, 2),
        "research_priority_score": round(research_priority, 2),
        "reset_watch_score": round(reset_watch, 2),
        "context_confidence_score": round(100.0 * context, 2),
        "data_confidence_score": round(100.0 * data, 2),
    }


def classify_decision_lane(
    *,
    liquidity_pass: bool,
    evidence_available: bool,
    explicit_deceleration: bool,
    momentum_operable: bool,
    setup_state: str,
    operational_conditions_met: bool,
    extension_status: str,
    extension_risk: float,
    research_priority_score: float,
    reset_watch_score: float,
    config: dict,
) -> tuple[str, list[str]]:
    cfg = config.get("opportunity_model", {})
    research_min = float(cfg.get("tactical_research_min_score", 68.0))
    reset_min = float(cfg.get("reset_watch_min_score", 72.0))
    max_research_extension = float(cfg.get("max_research_extension_risk", 0.72))
    reasons: list[str] = []

    if not evidence_available:
        return "DATA_BLOCKED", ["technical_evidence_missing"]
    if not liquidity_pass:
        return "STRUCTURAL_REJECT", ["core_liquidity_failed"]
    if explicit_deceleration:
        return "MOMENTUM_RECOVERY_WATCH", ["daily_or_weekly_macd_decelerating"]
    if not momentum_operable:
        return "MOMENTUM_RECOVERY_WATCH", ["momentum_not_confirmed"]
    if operational_conditions_met:
        return "EXECUTION_CANDIDATE", ["canonical_operational_conditions_met"]

    severe_extension = extension_status in {"OVEREXTENDED", "LATE_ENTRY"} or extension_risk >= 0.72
    if severe_extension and reset_watch_score >= reset_min:
        return "LEADERSHIP_RESET_WATCH", ["high_quality_leader_waiting_reset"]
    if (
        setup_state in {"CONFIRMED", "FORMING"}
        and research_priority_score >= research_min
        and extension_risk < max_research_extension
    ):
        reasons.append("research_value_above_threshold")
        if extension_status == "CAUTION":
            reasons.append("entry_timing_requires_confirmation")
        return "TACTICAL_RESEARCH", reasons
    return "STRUCTURAL_REJECT", ["opportunity_evidence_below_research_threshold"]


def legacy_lane_for_decision(
    decision_lane: str,
    *,
    explicit_deceleration: bool,
) -> str:
    mapping = {
        "EXECUTION_CANDIDATE": "ADVANCE_DEEP_ANALYSIS",
        "TACTICAL_RESEARCH": "ADVANCE_RESEARCH_ANALYSIS",
        "LEADERSHIP_RESET_WATCH": "RADAR_FORMING_SETUP",
        "MOMENTUM_RECOVERY_WATCH": (
            "REJECT_MOMENTUM" if explicit_deceleration else "RADAR_FORMING_SETUP"
        ),
        "STRUCTURAL_REJECT": "REJECT_RISK",
        "DATA_BLOCKED": "REJECT_RISK",
    }
    return mapping.get(decision_lane, "REJECT_RISK")
