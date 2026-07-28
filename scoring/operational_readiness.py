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
    signal = _safe_text(row.get("signal")).upper()
    recommendation = _safe_text(row.get("recommendation")).upper()
    quote_status = _safe_text(row.get("quote_status")).upper()
    execution_quality = _safe_text(row.get("execution_quote_quality")).upper()

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
    sector_weekly_macd_state = _safe_text(row.get("sector_weekly_macd_state")).upper()
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
    if scenario_status == "LATE_ENTRY_OVEREXTENDED" or extension_state in {"OVEREXTENDED", "LATE_ENTRY"}:
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
    if scenario_status == "WEAK_MOMENTUM" or momentum_state in {"WEAK", "DETERIORATING"}:
        momentum_penalty_reason = "weak_momentum"
        adjustment += float(cfg.get("weak_momentum_extra_penalty", -10.0))
    elif macd_histogram_state == "MACD_HIST_DETERIORATING":
        momentum_penalty_reason = "macd_hist_deteriorating"
        adjustment += float(cfg.get("macd_hist_deteriorating_penalty", -8.0))

    if weekly_macd_histogram_state in {
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
        ema20_extension_status == "CAUTION"
        and weekly_macd_histogram_state
        and weekly_macd_histogram_state != "WEEKLY_MACD_HIST_IMPROVING"
    ):
        adjustment += float(cfg.get("ema20_caution_weekly_not_improving_penalty", -8.0))
        _append_reason(reasons, "ema20_caution_with_weekly_macd_not_improving")

    sector_context_penalty_reason = ""
    if sector_weekly_macd_state in {
        "SECTOR_MACD_DECELERATING",
        "SECTOR_MACD_BEARISH",
    }:
        sector_penalties = {
            "SECTOR_MACD_DECELERATING": cfg.get("sector_macd_decelerating_penalty", -14.0),
            "SECTOR_MACD_BEARISH": cfg.get("sector_macd_bearish_penalty", -20.0),
        }
        adjustment += float(sector_penalties[sector_weekly_macd_state])
        sector_context_penalty_reason = sector_weekly_macd_state.lower()
        _append_reason(reasons, sector_context_penalty_reason)
    elif sector_weekly_macd_state == "SECTOR_MACD_IMPROVING_BUT_DECELERATING":
        adjustment += float(cfg.get("sector_macd_improving_but_decelerating_penalty", -8.0))
        sector_context_penalty_reason = "sector_macd_improving_but_decelerating"
        _append_reason(reasons, sector_context_penalty_reason)
    elif sector_weekly_macd_state == "SECTOR_MACD_ACCELERATING":
        adjustment += float(cfg.get("sector_macd_accelerating_bonus", 3.0))
        _append_reason(reasons, "sector_macd_accelerating_context")

    engine_block_reason = ""
    if signal in {"VETO", "AVOID"}:
        engine_block_reason = f"signal_{signal.lower()}_not_operable"
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
    elif weekly_macd_histogram_state == "WEEKLY_MACD_HIST_BEARISH":
        engine_block_reason = "weekly_macd_bearish"
    elif sector_weekly_macd_state == "SECTOR_MACD_BEARISH":
        engine_block_reason = "sector_weekly_macd_bearish"
    elif sector_weekly_macd_state == "SECTOR_MACD_DECELERATING":
        engine_block_reason = "sector_weekly_macd_decelerating"
    elif _safe_text(row.get("scenario_eligible_for_backtest")) and not _bool(row.get("scenario_eligible_for_backtest")):
        engine_block_reason = "scenario_not_eligible_for_backtest"
    elif shadow_level_status in {"INVALID_STOP_DISTANCE", "RR_BELOW_MINIMUM"}:
        engine_block_reason = f"shadow_level_{shadow_level_status.lower()}"

    if engine_block_reason:
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

    if engine_block_reason or execution_readiness == "NOT_OPERABLE":
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
        "operational_readiness_reason": "; ".join(reasons),
    }
