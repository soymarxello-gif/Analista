from __future__ import annotations

import json
from typing import Any

import pandas as pd


SCENARIO_STATUSES = {
    "VALID_TRIGGER",
    "WAIT_FOR_CONFIRMATION",
    "LATE_ENTRY_OVEREXTENDED",
    "WEAK_MOMENTUM",
    "STRUCTURE_INVALID",
    "CONTEXT_CONFLICT",
    "DATA_INSUFFICIENT",
    "NOT_SELECTED_FOR_DEEP_ANALYSIS",
}

SCENARIO_OPERABILITY = {
    "VALID_TRIGGER": "REVIEW_VALID_SCENARIO",
    "WAIT_FOR_CONFIRMATION": "WAIT_FOR_CONFIRMATION",
    "LATE_ENTRY_OVEREXTENDED": "DO_NOT_CHASE",
    "WEAK_MOMENTUM": "MONITOR_MOMENTUM",
    "STRUCTURE_INVALID": "DO_NOT_ADVANCE",
    "CONTEXT_CONFLICT": "WAIT_FOR_CONTEXT",
    "DATA_INSUFFICIENT": "DO_NOT_ADVANCE",
    "NOT_SELECTED_FOR_DEEP_ANALYSIS": "NOT_EVALUATED",
}


def _float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in {None, 0}:
        return None
    return current / previous - 1.0


def _json(items: list[str]) -> str:
    return json.dumps(items, ensure_ascii=False)


def build_technical_evidence(df: pd.DataFrame, *, trigger_level: float | None = None) -> dict:
    if df is None or df.empty or len(df) < 21:
        return {"evidence_available": False}

    row = df.iloc[-1]
    previous = df.iloc[-2]
    close = _float(row.get("close"))
    atr = _float(row.get("atr"))
    sma20 = _float(row.get("sma20"))
    sma50 = _float(row.get("sma50"))
    sma200 = _float(row.get("sma200"))
    rsi = _float(row.get("rsi"))
    rsi_5d_ago = _float(df["rsi"].iloc[-6]) if "rsi" in df and len(df) >= 6 else None
    macd = _float(row.get("macd"))
    macd_signal = _float(row.get("macd_signal"))
    macd_hist = _float(row.get("macd_hist"))
    macd_hist_previous = _float(previous.get("macd_hist"))
    sma20_5d_ago = _float(df["sma20"].iloc[-6]) if "sma20" in df and len(df) >= 6 else None
    sma50_10d_ago = _float(df["sma50"].iloc[-11]) if "sma50" in df and len(df) >= 11 else None
    recent_high = _float(df["high"].shift(1).tail(20).max())
    recent_low = _float(df["low"].shift(1).tail(20).min())
    previous_close = _float(previous.get("close"))
    candle_range = max((_float(row.get("high"), 0.0) or 0.0) - (_float(row.get("low"), 0.0) or 0.0), 0.0)
    close_location = (
        ((_float(row.get("close"), 0.0) or 0.0) - (_float(row.get("low"), 0.0) or 0.0)) / candle_range
        if candle_range > 0
        else 0.5
    )

    def distance(reference: float | None) -> float | None:
        return _pct_change(close, reference)

    def distance_atr(reference: float | None) -> float | None:
        if close is None or reference is None or atr in {None, 0}:
            return None
        return (close - reference) / atr

    return {
        "evidence_available": close is not None,
        "technical_close": close,
        "technical_rsi": rsi,
        "technical_rsi_change_5d": (rsi - rsi_5d_ago) if rsi is not None and rsi_5d_ago is not None else None,
        "technical_macd": macd,
        "technical_macd_signal": macd_signal,
        "technical_macd_hist": macd_hist,
        "technical_macd_hist_change_1d": (
            macd_hist - macd_hist_previous
            if macd_hist is not None and macd_hist_previous is not None
            else None
        ),
        "technical_sma20": sma20,
        "technical_sma50": sma50,
        "technical_sma200": sma200,
        "technical_sma20_slope_5d_pct": _pct_change(sma20, sma20_5d_ago),
        "technical_sma50_slope_10d_pct": _pct_change(sma50, sma50_10d_ago),
        "technical_distance_sma20_pct": distance(sma20),
        "technical_distance_sma50_pct": distance(sma50),
        "technical_distance_sma20_atr": distance_atr(sma20),
        "technical_distance_sma50_atr": distance_atr(sma50),
        "technical_trigger_distance_pct": distance(trigger_level),
        "technical_trigger_distance_atr": distance_atr(trigger_level),
        "technical_recent_high_20d": recent_high,
        "technical_recent_low_20d": recent_low,
        "technical_return_1d": _pct_change(close, previous_close),
        "technical_return_5d": _pct_change(close, _float(df["close"].iloc[-6])) if len(df) >= 6 else None,
        "technical_return_20d": _pct_change(close, _float(df["close"].iloc[-21])),
        "technical_return_63d": _pct_change(close, _float(df["close"].iloc[-64])) if len(df) >= 64 else None,
        "technical_relative_volume": _float(row.get("relative_volume")),
        "technical_atr": atr,
        "technical_atr_pct": _float(row.get("atr_pct")),
        "technical_close_location": close_location,
        "technical_bullish_candle": bool(
            close is not None
            and _float(row.get("open")) is not None
            and close > float(row.get("open"))
            and close_location >= 0.60
        ),
        "technical_rejection_candle": bool(
            close is not None
            and _float(row.get("open")) is not None
            and close >= float(row.get("open"))
            and close_location >= 0.70
        ),
    }


def classify_momentum(evidence: dict) -> tuple[str, list[str], list[str]]:
    rsi = _float(evidence.get("technical_rsi"))
    rsi_change = _float(evidence.get("technical_rsi_change_5d"))
    macd = _float(evidence.get("technical_macd"))
    macd_signal = _float(evidence.get("technical_macd_signal"))
    hist = _float(evidence.get("technical_macd_hist"))
    hist_change = _float(evidence.get("technical_macd_hist_change_1d"))
    sma20_slope = _float(evidence.get("technical_sma20_slope_5d_pct"))
    positives: list[str] = []
    negatives: list[str] = []

    if rsi is None or macd is None or macd_signal is None:
        return "UNKNOWN", positives, ["momentum_indicators_missing"]
    if 52 <= rsi <= 70:
        positives.append("rsi_in_constructive_range")
    elif rsi > 75:
        negatives.append("rsi_overextended")
    elif rsi < 45:
        negatives.append("rsi_weak")
    if rsi_change is not None:
        (positives if rsi_change > 1 else negatives if rsi_change < -3 else []).append(
            "rsi_improving" if rsi_change > 1 else "rsi_deteriorating"
        )
    if macd > macd_signal:
        positives.append("macd_above_signal")
    else:
        negatives.append("macd_below_signal")
    if hist is not None and hist_change is not None:
        if hist > 0 and hist_change >= 0:
            positives.append("macd_hist_positive_and_improving")
        elif hist_change < 0:
            negatives.append("macd_hist_deteriorating")
    if sma20_slope is not None:
        if sma20_slope > 0:
            positives.append("sma20_rising")
        elif sma20_slope < 0:
            negatives.append("sma20_falling")

    if len(negatives) >= 3 or "rsi_weak" in negatives:
        state = "WEAK"
    elif len(negatives) >= 2:
        state = "DETERIORATING"
    elif len(positives) >= 4:
        state = "STRONG"
    elif len(positives) >= 2:
        state = "IMPROVING"
    else:
        state = "STABLE"
    return state, positives, negatives


def classify_extension(evidence: dict, setup_type: str) -> tuple[str, list[str]]:
    rsi = _float(evidence.get("technical_rsi"))
    trigger_pct = _float(evidence.get("technical_trigger_distance_pct"))
    trigger_atr = _float(evidence.get("technical_trigger_distance_atr"))
    sma20_atr = _float(evidence.get("technical_distance_sma20_atr"))
    reasons: list[str] = []

    if rsi is not None and rsi > 75:
        reasons.append("rsi_above_75")
    if setup_type == "BREAKOUT":
        if trigger_pct is not None and trigger_pct > 0.03:
            reasons.append("price_more_than_3pct_above_breakout")
        if trigger_atr is not None and trigger_atr > 1.0:
            reasons.append("price_more_than_1atr_above_breakout")
    elif setup_type in {"PULLBACK", "RECLAIM"}:
        if sma20_atr is not None and sma20_atr > 1.25:
            reasons.append("price_more_than_1_25atr_above_sma20")
    if len(reasons) >= 2:
        return "LATE_ENTRY", reasons
    if reasons:
        return "OVEREXTENDED", reasons
    if trigger_atr is not None and trigger_atr > 0.65:
        return "CAUTION", ["price_extended_from_trigger"]
    return "HEALTHY", reasons


def analyze_scenario(
    df: pd.DataFrame,
    *,
    setup_type: str,
    trigger_level: float | None,
    market_regime: str = "",
    selected: bool = True,
) -> dict:
    if not selected:
        return {
            "scenario_status": "NOT_SELECTED_FOR_DEEP_ANALYSIS",
            "scenario_confidence": "UNKNOWN",
            "scenario_thesis": "Candidate remained outside the bounded deep-analysis budget.",
            "scenario_evidence": "[]",
            "scenario_contradictions": "[]",
            "momentum_state": "UNKNOWN",
            "extension_state": "UNKNOWN",
            "entry_timing_status": "NOT_EVALUATED",
            "required_confirmation": "",
            "invalidation_reason": "",
            "engine_recommendation": "FUNNEL_ONLY",
            "scenario_trigger_confirmed": False,
        }

    evidence = build_technical_evidence(df, trigger_level=trigger_level)
    if not evidence.get("evidence_available"):
        return {
            **evidence,
            "scenario_status": "DATA_INSUFFICIENT",
            "scenario_confidence": "LOW",
            "scenario_thesis": "Technical evidence is insufficient.",
            "scenario_evidence": "[]",
            "scenario_contradictions": _json(["technical_evidence_missing"]),
            "momentum_state": "UNKNOWN",
            "extension_state": "UNKNOWN",
            "entry_timing_status": "NOT_EVALUATED",
            "required_confirmation": "obtain_complete_technical_history",
            "invalidation_reason": "technical_evidence_missing",
            "engine_recommendation": "DO_NOT_ADVANCE",
            "scenario_trigger_confirmed": False,
        }

    setup = str(setup_type or "NO_VALID_SETUP").upper()
    momentum_state, momentum_evidence, momentum_conflicts = classify_momentum(evidence)
    extension_state, extension_reasons = classify_extension(evidence, setup)
    supportive = list(momentum_evidence)
    conflicts = list(momentum_conflicts) + extension_reasons
    relative_volume = _float(evidence.get("technical_relative_volume"), 0.0) or 0.0
    bullish_candle = bool(evidence.get("technical_bullish_candle"))
    rejection_candle = bool(evidence.get("technical_rejection_candle"))
    close = _float(evidence.get("technical_close"))
    trigger = _float(trigger_level)
    required_confirmation = ""
    thesis = ""
    scenario_trigger = False

    if setup not in {"BREAKOUT", "PULLBACK", "RECLAIM"}:
        status = "STRUCTURE_INVALID"
        thesis = "No actionable scenario structure is present."
        conflicts.append("unsupported_or_missing_setup")
        required_confirmation = "valid_setup_structure"
    elif extension_state in {"OVEREXTENDED", "LATE_ENTRY"}:
        status = "LATE_ENTRY_OVEREXTENDED"
        thesis = "The structure may be valid, but the current entry is late or overextended."
        required_confirmation = "wait_for_consolidation_or_new_support"
    elif momentum_state in {"WEAK", "DETERIORATING"}:
        status = "WEAK_MOMENTUM"
        thesis = "The setup lacks sufficient momentum confirmation."
        required_confirmation = "momentum_turn_and_macd_confirmation"
    elif setup == "BREAKOUT":
        volume_ok = relative_volume >= 1.30
        level_ok = close is not None and trigger is not None and close > trigger
        if level_ok:
            supportive.append("close_above_breakout_level")
        if volume_ok:
            supportive.append("breakout_volume_confirmed")
        else:
            conflicts.append("breakout_volume_below_1_3")
        scenario_trigger = bool(level_ok and volume_ok and momentum_state in {"STRONG", "IMPROVING"})
        status = "VALID_TRIGGER" if scenario_trigger else "WAIT_FOR_CONFIRMATION"
        thesis = "Breakout continuation with volume and momentum confirmation."
        required_confirmation = "" if scenario_trigger else "close_above_resistance_with_volume_and_momentum"
    elif setup == "PULLBACK":
        distance_sma20_atr = _float(evidence.get("technical_distance_sma20_atr"))
        distance_sma50_atr = _float(evidence.get("technical_distance_sma50_atr"))
        support_distances = [
            abs(value)
            for value in (distance_sma20_atr, distance_sma50_atr)
            if value is not None
        ]
        near_support_atr = min(support_distances) if support_distances else 99.0
        support_ok = near_support_atr <= 0.75
        volume_ok = relative_volume <= 1.20
        if support_ok:
            supportive.append("price_near_moving_average_support")
        else:
            conflicts.append("price_not_near_support")
        if volume_ok:
            supportive.append("pullback_volume_controlled")
        else:
            conflicts.append("pullback_volume_not_controlled")
        if rejection_candle:
            supportive.append("bullish_rejection_confirmation")
        else:
            conflicts.append("no_bullish_rejection_confirmation")
        scenario_trigger = bool(
            support_ok
            and rejection_candle
            and momentum_state in {"STRONG", "IMPROVING", "STABLE"}
        )
        status = "VALID_TRIGGER" if scenario_trigger else "WAIT_FOR_CONFIRMATION"
        thesis = "Orderly pullback into support with rejection and momentum stabilization."
        required_confirmation = "" if scenario_trigger else "bullish_rejection_near_support_with_stable_momentum"
    else:
        level_ok = close is not None and trigger is not None and close > trigger
        volume_ok = relative_volume >= 1.10
        if level_ok:
            supportive.append("close_above_reclaimed_level")
        else:
            conflicts.append("reclaim_level_not_held")
        if volume_ok:
            supportive.append("reclaim_volume_confirmed")
        else:
            conflicts.append("reclaim_volume_below_1_1")
        scenario_trigger = bool(
            level_ok and bullish_candle and volume_ok and momentum_state not in {"WEAK", "DETERIORATING"}
        )
        status = "VALID_TRIGGER" if scenario_trigger else "WAIT_FOR_CONFIRMATION"
        thesis = "Reclaim of support with closing and volume confirmation."
        required_confirmation = "" if scenario_trigger else "hold_reclaimed_level_with_volume"

    if str(market_regime).upper() == "RISK_OFF" and status == "VALID_TRIGGER":
        status = "CONTEXT_CONFLICT"
        conflicts.append("risk_off_market_regime")
        scenario_trigger = False
        required_confirmation = "market_context_improves"

    confidence = "HIGH" if status == "VALID_TRIGGER" and len(conflicts) == 0 else "MEDIUM" if supportive else "LOW"
    recommendation_map = {
        "VALID_TRIGGER": "REVIEW_VALID_SCENARIO",
        "WAIT_FOR_CONFIRMATION": "WAIT_FOR_CONFIRMATION",
        "LATE_ENTRY_OVEREXTENDED": "DO_NOT_CHASE",
        "WEAK_MOMENTUM": "MONITOR_MOMENTUM",
        "STRUCTURE_INVALID": "DO_NOT_ADVANCE",
        "CONTEXT_CONFLICT": "WAIT_FOR_CONTEXT",
        "DATA_INSUFFICIENT": "DO_NOT_ADVANCE",
    }
    return {
        **evidence,
        "scenario_status": status,
        "scenario_confidence": confidence,
        "scenario_thesis": thesis,
        "scenario_evidence": _json(supportive),
        "scenario_contradictions": _json(conflicts),
        "momentum_state": momentum_state,
        "extension_state": extension_state,
        "entry_timing_status": "ON_TIME" if extension_state == "HEALTHY" else extension_state,
        "required_confirmation": required_confirmation,
        "invalidation_reason": "; ".join(conflicts),
        "engine_recommendation": recommendation_map.get(status, "MANUAL_REVIEW"),
        "scenario_trigger_confirmed": scenario_trigger,
    }


def apply_scenario_guardrail(row: dict) -> dict:
    """Conservatively demote scenario conflicts without ever promoting a signal."""
    status = str(row.get("scenario_status") or "DATA_INSUFFICIENT").upper()
    signal = str(row.get("signal") or "").upper()
    selected = bool(row.get("deep_analysis_selected"))
    eligible = bool(
        selected
        and status == "VALID_TRIGGER"
        and row.get("scenario_trigger_confirmed") is True
    )
    applied = bool(selected and not eligible)
    guarded_signal = signal
    if applied and signal in {"TRIGGER_CONFIRMED", "READY_WAIT_TRIGGER"}:
        guarded_signal = "WATCHLIST"

    reason_map = {
        "WAIT_FOR_CONFIRMATION": "scenario_wait_for_confirmation",
        "LATE_ENTRY_OVEREXTENDED": "scenario_do_not_chase",
        "WEAK_MOMENTUM": "scenario_weak_momentum",
        "STRUCTURE_INVALID": "scenario_structure_invalid",
        "CONTEXT_CONFLICT": "scenario_context_conflict",
        "DATA_INSUFFICIENT": "scenario_data_insufficient",
    }
    return {
        "signal": guarded_signal,
        "scenario_operability": SCENARIO_OPERABILITY.get(status, "MANUAL_REVIEW"),
        "scenario_guardrail_applied": applied,
        "scenario_guardrail_reason": reason_map.get(status, ""),
        "scenario_eligible_for_backtest": eligible,
    }


def calculate_shadow_levels(
    df: pd.DataFrame,
    *,
    scenario: dict,
    setup_type: str,
    rr_data: dict,
    config: dict,
) -> dict:
    """Build conservative comparison levels without changing actionable levels."""
    empty = {
        "shadow_entry": None,
        "shadow_stop": None,
        "shadow_target": None,
        "shadow_rr": None,
        "shadow_stop_atr_multiple": None,
        "shadow_level_status": "NOT_ELIGIBLE",
        "shadow_entry_method": "",
        "shadow_stop_method": "",
        "shadow_target_method": "",
    }
    if (
        df is None
        or df.empty
        or str(scenario.get("scenario_status") or "").upper() != "VALID_TRIGGER"
    ):
        return empty

    latest = df.iloc[-1]
    close = _float(latest.get("close"))
    high = _float(latest.get("high"))
    atr = _float(latest.get("atr"))
    current_stop = _float(rr_data.get("stop"))
    current_target = _float(rr_data.get("target"))
    if close is None or atr is None or atr <= 0 or current_stop is None:
        return {**empty, "shadow_level_status": "DATA_INSUFFICIENT"}

    setup = str(setup_type or "").upper()
    if setup in {"PULLBACK", "RECLAIM"} and high is not None:
        entry = high * 1.001
        entry_method = "confirmation_above_rejection_high"
    else:
        entry = close
        entry_method = "confirmed_close"

    stop = min(current_stop, entry - atr)
    risk = entry - stop
    stop_atr_multiple = risk / atr
    if risk <= 0 or stop_atr_multiple > 2.5:
        return {
            **empty,
            "shadow_entry": entry,
            "shadow_stop": stop,
            "shadow_stop_atr_multiple": stop_atr_multiple,
            "shadow_level_status": "INVALID_STOP_DISTANCE",
            "shadow_entry_method": entry_method,
            "shadow_stop_method": "structural_with_1atr_floor",
        }

    target_cap = entry + 2.0 * atr
    valid_current_target = (
        current_target if current_target is not None and current_target > entry else None
    )
    target = min(valid_current_target, target_cap) if valid_current_target else target_cap
    reward = target - entry
    rr = reward / risk if risk > 0 else None
    status = "VALID" if rr is not None and rr >= 1.5 else "RR_BELOW_MINIMUM"
    return {
        "shadow_entry": entry,
        "shadow_stop": stop,
        "shadow_target": target,
        "shadow_rr": rr,
        "shadow_stop_atr_multiple": stop_atr_multiple,
        "shadow_level_status": status,
        "shadow_entry_method": entry_method,
        "shadow_stop_method": "structural_with_1atr_floor",
        "shadow_target_method": (
            "nearest_current_target_capped_2atr"
            if valid_current_target is not None and valid_current_target <= target_cap
            else "2atr_four_session_cap"
        ),
    }
