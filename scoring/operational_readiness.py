from __future__ import annotations

from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _append_reason(reasons: list[str], reason: str) -> None:
    if reason and reason not in reasons:
        reasons.append(reason)


def _execution_readiness_status(row: dict[str, Any]) -> str:
    technical_lane = _safe_text(row.get("technical_analysis_lane")).upper()
    signal = _safe_text(row.get("signal")).upper()
    recommendation = _safe_text(row.get("recommendation")).upper()
    quote_status = _safe_text(row.get("quote_status")).upper()
    execution_quality = _safe_text(row.get("execution_quote_quality")).upper()
    risk_geometry_status = _safe_text(row.get("risk_geometry_status")).upper()

    if technical_lane == "ADVANCE_RESEARCH_ANALYSIS":
        return "NOT_OPERABLE"

    if _bool(row.get("earnings_operability_block")) or risk_geometry_status in {"FRAGILE", "INVALID"}:
        return "NOT_OPERABLE"

    if signal in {"VETO", "AVOID"} or recommendation in {"DO_NOT_TRADE", "AVOID_FOR_NOW"}:
        return "NOT_OPERABLE"

    if (
        quote_status in {"MISSING", "INVALID", "STALE_POSSIBLE", "WIDE_OR_INCOHERENT"}
        or execution_quality == "LOW"
        or recommendation == "RECHECK_LIVE_QUOTE"
    ):
        return "NEEDS_LIVE_QUOTE_RECHECK"

    if quote_status != "VALID" or execution_quality != "HIGH":
        return "EXECUTION_DATA_BLOCKED"

    return "EXECUTION_READY_REVIEW"


def calculate_operational_readiness(row: dict[str, Any], config: dict | None = None) -> dict[str, Any]:
    """
    Derive a conservative operational-readiness layer from existing scanner output.

    This function does not alter final_score/final_trade_score, signals, quote status
    or execution quote quality. It only produces downstream ranking and audit fields
    so late, overextended or weak-momentum setups stop looking equally urgent.
    """
    config = config or {}
    cfg = config.get("operational_readiness", {})

    base_score = _safe_float(
        row.get("final_trade_score"),
        _safe_float(row.get("final_score"), 0.0),
    )
    adjustment = 0.0
    reasons: list[str] = []

    signal = _safe_text(row.get("signal")).upper()
    recommendation = _safe_text(row.get("recommendation")).upper()
    scenario_status = _safe_text(row.get("scenario_status")).upper()
    momentum_state = _safe_text(row.get("momentum_state")).upper()
    extension_state = _safe_text(row.get("extension_state")).upper()
    ema20_extension_status = _safe_text(row.get("ema20_extension_status")).upper()
    entry_timing_status = _safe_text(row.get("entry_timing_status")).upper()
    shadow_level_status = _safe_text(row.get("shadow_level_status")).upper()
    macd_histogram_state = _safe_text(row.get("macd_histogram_state")).upper()
    weekly_macd_histogram_state = _safe_text(row.get("weekly_macd_histogram_state")).upper()
    daily_trajectory_state = _safe_text(row.get("daily_macd_trajectory_state")).upper()
    weekly_trajectory_state = _safe_text(row.get("weekly_macd_trajectory_state")).upper()
    momentum_operability_status = _safe_text(row.get("momentum_operability_status")).upper()
    sector_weekly_macd_state = _safe_text(row.get("sector_weekly_macd_state")).upper()
    technical_analysis_lane = _safe_text(row.get("technical_analysis_lane")).upper()
    ema20_distance_atr = _safe_float(row.get("technical_distance_ema20_atr"), 0.0)
    ema20_distance_pct = _safe_float(row.get("technical_distance_ema20_pct"), 0.0)

    scenario_adjustments = {
        "VALID_TRIGGER": cfg.get("valid_trigger_adjustment", 4.0),
        "WAIT_FOR_CONFIRMATION": cfg.get("wait_for_confirmation_adjustment", -14.0),
        "LATE_ENTRY_OVEREXTENDED": cfg.get("late_entry_overextended_adjustment", -32.0),
        "WEAK_MOMENTUM": cfg.get("weak_momentum_adjustment", -28.0),
        "STRUCTURE_INVALID": cfg.get("structure_invalid_adjustment", -38.0),
        "CONTEXT_CONFLICT": cfg.get("context_conflict_adjustment", -30.0),
        "DATA_INSUFFICIENT": cfg.get("data_insufficient_adjustment", -22.0),
        "NOT_SELECTED_FOR_DEEP_ANALYSIS": cfg.get("not_selected_adjustment", -8.0),
    }

    if scenario_status:
        scenario_delta = float(scenario_adjustments.get(scenario_status, cfg.get("unknown_scenario_adjustment", -6.0)))
        adjustment += scenario_delta
        if scenario_delta < 0:
            _append_reason(reasons, f"scenario_{scenario_status.lower()}")

    timing_penalty_reason = ""
    if scenario_status == "LATE_ENTRY_OVEREXTENDED":
        timing_penalty_reason = "late_entry_overextended"
    elif extension_state in {"OVEREXTENDED", "LATE_ENTRY"}:
        timing_penalty_reason = "late_entry_overextended"
        adjustment += float(cfg.get("late_timing_extra_penalty", -10.0))
    elif ema20_extension_status in {"OVEREXTENDED", "LATE_ENTRY"}:
        timing_penalty_reason = f"ema20_{ema20_extension_status.lower()}"
        adjustment += float(cfg.get("late_timing_extra_penalty", -10.0))
    elif entry_timing_status in {"OVEREXTENDED", "LATE_ENTRY"}:
        timing_penalty_reason = f"entry_timing_{entry_timing_status.lower()}"
        adjustment += float(cfg.get("late_timing_extra_penalty", -10.0))
    elif entry_timing_status == "CAUTION" or ema20_extension_status == "CAUTION":
        strong_ema20_caution = ema20_distance_atr > 1.25 or ema20_distance_pct > 0.04
        timing_penalty_reason = "ema20_extension_caution" if strong_ema20_caution else "entry_timing_caution"
        adjustment += float(
            cfg.get("ema20_strong_caution_penalty" if strong_ema20_caution else "timing_caution_penalty", -16.0 if strong_ema20_caution else -8.0)
        )

    momentum_penalty_reason = ""
    if scenario_status == "WEAK_MOMENTUM":
        momentum_penalty_reason = "weak_momentum"
    elif momentum_state in {"WEAK", "DETERIORATING"}:
        momentum_penalty_reason = "weak_momentum"
        adjustment += float(cfg.get("weak_momentum_extra_penalty", -10.0))
    elif macd_histogram_state == "MACD_HIST_DETERIORATING":
        momentum_penalty_reason = "macd_hist_deteriorating"
        adjustment += float(cfg.get("macd_hist_deteriorating_penalty", -8.0))

    legacy_trajectory_missing = not daily_trajectory_state and not weekly_trajectory_state
    if legacy_trajectory_missing and weekly_macd_histogram_state in {
        "WEEKLY_MACD_HIST_DECELERATING",
        "WEEKLY_MACD_HIST_MIXED",
        "WEEKLY_MACD_HIST_BEARISH",
    }:
        weekly_penalties = {
            "WEEKLY_MACD_HIST_DECELERATING": cfg.get("weekly_macd_decelerating_penalty", -18.0),
            "WEEKLY_MACD_HIST_MIXED": cfg.get("weekly_macd_mixed_penalty", -12.0),
            "WEEKLY_MACD_HIST_BEARISH": cfg.get("weekly_macd_bearish_penalty", -24.0),
        }
        adjustment += float(weekly_penalties[weekly_macd_histogram_state])
        weekly_reason = weekly_macd_histogram_state.replace("WEEKLY_MACD_HIST_", "weekly_macd_").lower()
        momentum_penalty_reason = (
            weekly_reason
            if not momentum_penalty_reason
            else f"{momentum_penalty_reason}; {weekly_reason}"
        )
        _append_reason(reasons, weekly_reason)

    if (
        legacy_trajectory_missing
        and
        ema20_extension_status == "CAUTION"
        and weekly_macd_histogram_state
        and weekly_macd_histogram_state != "WEEKLY_MACD_HIST_IMPROVING"
    ):
        adjustment += float(cfg.get("ema20_caution_weekly_not_improving_penalty", -8.0))
        _append_reason(reasons, "ema20_caution_with_weekly_macd_not_improving")

    sector_context_penalty_reason = ""
    rs_score = _safe_float(row.get("rs_score"), 0.0)
    relative_volume = _safe_float(row.get("relative_volume"), 0.0)
    sector_relative_strength_score = _safe_float(
        row.get("sector_relative_strength_score"),
        rs_score * 100.0 if rs_score <= 1.0 else rs_score,
    )
    leadership_override = (
        sector_weekly_macd_state in {"SECTOR_MACD_DECELERATING", "SECTOR_MACD_BEARISH"}
        and sector_relative_strength_score
        >= float(cfg.get("sector_relative_strength_score_min", 70.0))
        and relative_volume >= float(cfg.get("sector_leadership_relative_volume_min", 1.10))
        and daily_trajectory_state in {"ACCELERATING", "IMPROVING_STEADY"}
        and weekly_trajectory_state in {"ACCELERATING", "IMPROVING_STEADY"}
    )
    if sector_weekly_macd_state in {
        "SECTOR_MACD_DECELERATING",
        "SECTOR_MACD_BEARISH",
    }:
        sector_penalties = {
            "SECTOR_MACD_DECELERATING": cfg.get("sector_macd_decelerating_penalty", -14.0),
            "SECTOR_MACD_BEARISH": cfg.get("sector_macd_bearish_penalty", -20.0),
        }
        sector_penalty = float(sector_penalties[sector_weekly_macd_state])
        if leadership_override:
            sector_penalty *= float(cfg.get("sector_leadership_penalty_multiplier", 0.35))
            sector_context_penalty_reason = "sector_headwind_with_leadership_override"
        else:
            sector_context_penalty_reason = sector_weekly_macd_state.lower()
        adjustment += sector_penalty
        _append_reason(reasons, sector_context_penalty_reason)
    elif sector_weekly_macd_state == "SECTOR_MACD_IMPROVING_BUT_DECELERATING":
        adjustment += float(cfg.get("sector_macd_improving_but_decelerating_penalty", -8.0))
        sector_context_penalty_reason = "sector_macd_improving_but_decelerating"
        _append_reason(reasons, sector_context_penalty_reason)
    elif sector_weekly_macd_state == "SECTOR_MACD_ACCELERATING":
        adjustment += float(cfg.get("sector_macd_accelerating_bonus", 3.0))
        _append_reason(reasons, "sector_macd_accelerating_context")

    engine_block_reason = ""
    if technical_analysis_lane == "ADVANCE_RESEARCH_ANALYSIS":
        engine_block_reason = "research_lane_not_operational"
    elif signal in {"VETO", "AVOID"}:
        engine_block_reason = f"signal_{signal.lower()}_not_operable"
    elif _bool(row.get("earnings_operability_block")):
        engine_block_reason = "earnings_operability_block"
    elif _safe_text(row.get("risk_geometry_status")).upper() in {"FRAGILE", "INVALID"}:
        engine_block_reason = (
            _safe_text(row.get("risk_geometry_reason"))
            or "risk_geometry_not_robust"
        )
    elif scenario_status in {
        "LATE_ENTRY_OVEREXTENDED",
        "WEAK_MOMENTUM",
        "STRUCTURE_INVALID",
        "CONTEXT_CONFLICT",
        "DATA_INSUFFICIENT",
    }:
        engine_block_reason = f"scenario_{scenario_status.lower()}"
    elif ema20_extension_status == "LATE_ENTRY":
        engine_block_reason = "ema20_late_entry"
    elif ema20_extension_status == "OVEREXTENDED":
        engine_block_reason = "ema20_overextended"
    elif momentum_operability_status == "REJECT_MOMENTUM":
        engine_block_reason = "daily_or_weekly_macd_decelerating"
    elif daily_trajectory_state in {"IMPROVING_BUT_DECELERATING", "DECLINING"}:
        engine_block_reason = "daily_macd_decelerating"
    elif weekly_trajectory_state in {"IMPROVING_BUT_DECELERATING", "DECLINING"}:
        engine_block_reason = "weekly_macd_decelerating"
    elif legacy_trajectory_missing and weekly_macd_histogram_state == "WEEKLY_MACD_HIST_BEARISH":
        engine_block_reason = "weekly_macd_bearish"
    elif (
        scenario_status != "WAIT_FOR_CONFIRMATION"
        and _safe_text(row.get("scenario_eligible_for_backtest"))
        and not _bool(row.get("scenario_eligible_for_backtest"))
    ):
        engine_block_reason = "scenario_not_eligible_for_backtest"
    engine_block_is_distinct = bool(
        engine_block_reason
        and not engine_block_reason.startswith(("signal_", "scenario_"))
        and engine_block_reason
        not in {
            timing_penalty_reason,
            momentum_penalty_reason,
            f"ema20_{ema20_extension_status.lower()}" if ema20_extension_status else "",
        }
    )
    if engine_block_reason:
        if engine_block_is_distinct:
            adjustment += float(cfg.get("engine_block_penalty", -12.0))
        _append_reason(reasons, engine_block_reason)

    execution_readiness = _execution_readiness_status(row)
    if execution_readiness == "NEEDS_LIVE_QUOTE_RECHECK":
        adjustment += float(cfg.get("quote_recheck_penalty", -12.0))
        _append_reason(reasons, "needs_live_quote_recheck")
    elif execution_readiness == "EXECUTION_DATA_BLOCKED":
        adjustment += float(cfg.get("execution_data_blocked_penalty", -18.0))
        _append_reason(reasons, "execution_data_blocked")
    elif execution_readiness == "NOT_OPERABLE":
        adjustment += float(cfg.get("not_operable_penalty", -28.0))
        _append_reason(reasons, "not_operable")

    if recommendation == "RECHECK_LIVE_QUOTE":
        _append_reason(reasons, "recommendation_recheck_live_quote")

    readiness_score = round(_clamp(base_score + adjustment), 2)

    if technical_analysis_lane == "ADVANCE_RESEARCH_ANALYSIS":
        bucket = "R_RESEARCH"
    elif engine_block_reason or execution_readiness == "NOT_OPERABLE":
        bucket = "D_BLOCKED"
    elif execution_readiness == "NEEDS_LIVE_QUOTE_RECHECK":
        bucket = "C_RECHECK_QUOTE"
    elif scenario_status == "WAIT_FOR_CONFIRMATION":
        bucket = "B_MONITOR_CONFIRMATION"
    elif readiness_score >= 80 and execution_readiness == "EXECUTION_READY_REVIEW":
        bucket = "A_READY_REVIEW"
    elif readiness_score >= 65:
        bucket = "B_REVIEW"
    elif readiness_score >= 45:
        bucket = "C_MONITOR"
    else:
        bucket = "D_BLOCKED"

    if technical_analysis_lane == "ADVANCE_RESEARCH_ANALYSIS":
        operational_status = "RESEARCH_ONLY"
    elif engine_block_reason:
        operational_status = "REJECTED_TECHNICAL"
    elif execution_readiness in {"NEEDS_LIVE_QUOTE_RECHECK", "EXECUTION_DATA_BLOCKED"}:
        operational_status = "DATA_BLOCKED"
    elif (
        scenario_status == "VALID_TRIGGER"
        and execution_readiness == "EXECUTION_READY_REVIEW"
        and daily_trajectory_state in {"ACCELERATING", "IMPROVING_STEADY", ""}
        and weekly_trajectory_state in {"ACCELERATING", "IMPROVING_STEADY", ""}
    ):
        operational_status = "OPERABLE_REVIEW"
    else:
        operational_status = "MONITOR_NEXT_TRIGGER"

    decision_lane = _safe_text(row.get("decision_lane")).upper()
    if (
        decision_lane == "EXECUTION_CANDIDATE"
        and not engine_block_reason
        and execution_readiness == "EXECUTION_READY_REVIEW"
    ):
        market_opportunity_status = "EXECUTION_READY_REVIEW"
    elif decision_lane == "EXECUTION_CANDIDATE" and (
        _safe_text(row.get("quote_status")).upper() in {
            "MISSING",
            "INVALID",
            "STALE_POSSIBLE",
            "WIDE_OR_INCOHERENT",
        }
        or _safe_text(row.get("execution_quote_quality")).upper() == "LOW"
    ):
        market_opportunity_status = "EXECUTION_RECHECK_PENDING"
    elif decision_lane in {
        "TACTICAL_RESEARCH",
        "LEADERSHIP_RESET_WATCH",
        "MOMENTUM_RECOVERY_WATCH",
    } or technical_analysis_lane == "ADVANCE_RESEARCH_ANALYSIS":
        market_opportunity_status = "RESEARCH_ONLY"
    else:
        market_opportunity_status = "NO_CLEAN_EXECUTION"

    return {
        "operational_readiness_score": readiness_score,
        "operational_readiness_bucket": bucket,
        "scenario_quality_adjustment": round(adjustment, 2),
        "timing_penalty_reason": timing_penalty_reason,
        "momentum_penalty_reason": (
            f"{momentum_penalty_reason}; {sector_context_penalty_reason}"
            if momentum_penalty_reason and sector_context_penalty_reason
            else momentum_penalty_reason or sector_context_penalty_reason
        ),
        "engine_block_reason": engine_block_reason,
        "execution_readiness_status": execution_readiness,
        "operational_status": operational_status,
        "market_opportunity_status": market_opportunity_status,
        "sector_leadership_override_status": (
            "LEADERSHIP_OVERRIDE" if leadership_override else "NOT_APPLIED"
        ),
        "sector_headwind_strength": round(
            abs(float(sector_penalty)) if "sector_penalty" in locals() else 0.0,
            2,
        ),
        "operational_readiness_reason": "; ".join(reasons),
    }
