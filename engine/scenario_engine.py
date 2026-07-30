from __future__ import annotations

import json
from typing import Any

import pandas as pd

from data.technical_bars import closed_weekly_close
from engine.momentum_trajectory import (
    OPERABLE_TRAJECTORY_STATES,
    analyze_multitimeframe_macd,
)


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


def _legacy_daily_macd_state(trajectory_state: str, histogram: float | None) -> str:
    if trajectory_state in OPERABLE_TRAJECTORY_STATES:
        return (
            "MACD_HIST_BULLISH_INFLECTION_BELOW_ZERO"
            if histogram is not None and histogram < 0
            else "MACD_HIST_POSITIVE_EXPANDING"
        )
    if trajectory_state == "IMPROVING_BUT_DECELERATING":
        return "MACD_HIST_IMPROVING_BUT_DECELERATING"
    if trajectory_state == "DECLINING":
        return "MACD_HIST_DETERIORATING"
    if trajectory_state == "FLAT_NO_EDGE":
        return "MACD_HIST_FLATTENING"
    if trajectory_state == "NOISY":
        return "MACD_HIST_MIXED"
    return "MACD_HIST_UNKNOWN"


def _legacy_weekly_macd_state(trajectory_state: str, histogram: float | None) -> str:
    if trajectory_state in OPERABLE_TRAJECTORY_STATES:
        return "WEEKLY_MACD_HIST_IMPROVING"
    if trajectory_state == "IMPROVING_BUT_DECELERATING":
        return "WEEKLY_MACD_HIST_DECELERATING"
    if trajectory_state == "DECLINING":
        return (
            "WEEKLY_MACD_HIST_BEARISH"
            if histogram is not None and histogram <= 0
            else "WEEKLY_MACD_HIST_DECELERATING"
        )
    if trajectory_state in {"FLAT_NO_EDGE", "NOISY"}:
        return "WEEKLY_MACD_HIST_MIXED"
    return "WEEKLY_MACD_HIST_UNKNOWN"


def _trajectory_from_legacy_weekly(state: str) -> str:
    mapping = {
        "WEEKLY_MACD_HIST_IMPROVING": "IMPROVING_STEADY",
        "WEEKLY_MACD_HIST_DECELERATING": "IMPROVING_BUT_DECELERATING",
        "WEEKLY_MACD_HIST_BEARISH": "DECLINING",
        "WEEKLY_MACD_HIST_MIXED": "NOISY",
        "WEEKLY_MACD_HIST_UNKNOWN": "UNKNOWN",
    }
    return mapping.get(str(state or "").upper(), "UNKNOWN")


def _weekly_macd_histogram_metrics(
    df: pd.DataFrame,
    *,
    trajectory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    empty = {
        "weekly_macd_histogram_state": "WEEKLY_MACD_HIST_UNKNOWN",
        "weekly_macd_hist": None,
        "weekly_macd_hist_change_1w": None,
        "weekly_macd_hist_change_2w": None,
        "weekly_macd_hist_two_week_rising": False,
        "weekly_macd_hist_two_week_falling": False,
    }
    if df is None or df.empty or "close" not in df.columns:
        return empty
    if not isinstance(df.index, pd.DatetimeIndex) or len(df) < 90:
        return empty

    weekly_close, _ = closed_weekly_close(df["close"].astype(float))
    if len(weekly_close) < 35:
        return empty

    macd = weekly_close.ewm(span=12, adjust=False).mean() - weekly_close.ewm(span=26, adjust=False).mean()
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    latest = _float(hist.iloc[-1])
    previous = _float(hist.iloc[-2])
    two_ago = _float(hist.iloc[-3])
    if latest is None or previous is None or two_ago is None:
        return empty

    trajectory = trajectory or analyze_multitimeframe_macd(df)
    trajectory_state = str(trajectory.get("weekly_macd_trajectory_state") or "UNKNOWN")
    two_week_rising = latest > previous >= two_ago
    two_week_falling = latest < previous < two_ago
    state = _legacy_weekly_macd_state(trajectory_state, latest)

    return {
        **trajectory,
        "weekly_macd_histogram_state": state,
        "weekly_macd_hist": latest,
        "weekly_macd_hist_change_1w": latest - previous,
        "weekly_macd_hist_change_2w": latest - two_ago,
        "weekly_macd_hist_two_week_rising": two_week_rising,
        "weekly_macd_hist_two_week_falling": two_week_falling,
    }


def _weekly_macd_histogram_state(df: pd.DataFrame) -> str:
    return str(_weekly_macd_histogram_metrics(df).get("weekly_macd_histogram_state"))


def build_technical_evidence(df: pd.DataFrame, *, trigger_level: float | None = None) -> dict:
    if df is None or df.empty or len(df) < 21:
        return {"evidence_available": False}

    row = df.iloc[-1]
    previous = df.iloc[-2]
    close = _float(row.get("close"))
    atr = _float(row.get("atr"))
    ema20 = _float(row.get("ema20"))
    sma20 = _float(row.get("sma20"))
    sma50 = _float(row.get("sma50"))
    sma200 = _float(row.get("sma200"))
    rsi = _float(row.get("rsi"))
    rsi_5d_ago = _float(df["rsi"].iloc[-6]) if "rsi" in df and len(df) >= 6 else None
    macd = _float(row.get("macd"))
    macd_signal = _float(row.get("macd_signal"))
    macd_hist = _float(row.get("macd_hist"))
    macd_hist_previous = _float(previous.get("macd_hist"))
    macd_hist_2d_ago = _float(df["macd_hist"].iloc[-3]) if "macd_hist" in df and len(df) >= 3 else None
    macd_hist_3d_ago = _float(df["macd_hist"].iloc[-4]) if "macd_hist" in df and len(df) >= 4 else None
    ema20_5d_ago = _float(df["ema20"].iloc[-6]) if "ema20" in df and len(df) >= 6 else None
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

    trajectory = analyze_multitimeframe_macd(df)
    try:
        weekly_macd = _weekly_macd_histogram_metrics(df, trajectory=trajectory)
    except TypeError as exc:
        if "trajectory" not in str(exc):
            raise
        weekly_macd = _weekly_macd_histogram_metrics(df)
    if "weekly_macd_trajectory_state" not in weekly_macd:
        weekly_state = str(
            weekly_macd.get("weekly_macd_histogram_state")
            or "WEEKLY_MACD_HIST_UNKNOWN"
        )
        legacy_trajectory = _trajectory_from_legacy_weekly(weekly_state)
        trajectory["weekly_macd_trajectory_state"] = legacy_trajectory
        trajectory["weekly_macd_non_decelerating"] = (
            legacy_trajectory in OPERABLE_TRAJECTORY_STATES
        )
        trajectory["momentum_operability_status"] = (
            "CONFIRMED_NON_DECELERATING"
            if trajectory.get("daily_macd_non_decelerating")
            and trajectory.get("weekly_macd_non_decelerating")
            else "REJECT_MOMENTUM"
            if legacy_trajectory in {"IMPROVING_BUT_DECELERATING", "DECLINING"}
            else "MONITOR_MOMENTUM"
        )

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
        "technical_macd_hist_change_2d": (
            macd_hist - macd_hist_2d_ago
            if macd_hist is not None and macd_hist_2d_ago is not None
            else None
        ),
        "technical_macd_hist_change_3d": (
            macd_hist - macd_hist_3d_ago
            if macd_hist is not None and macd_hist_3d_ago is not None
            else None
        ),
        "technical_macd_hist_two_day_rising": bool(
            macd_hist is not None
            and macd_hist_previous is not None
            and macd_hist_2d_ago is not None
            and macd_hist > macd_hist_previous > macd_hist_2d_ago
        ),
        "technical_macd_hist_two_day_falling": bool(
            macd_hist is not None
            and macd_hist_previous is not None
            and macd_hist_2d_ago is not None
            and macd_hist < macd_hist_previous < macd_hist_2d_ago
        ),
        **trajectory,
        **weekly_macd,
        "technical_ema20": ema20,
        "technical_sma20": sma20,
        "technical_sma50": sma50,
        "technical_sma200": sma200,
        "technical_ema20_slope_5d_pct": _pct_change(ema20, ema20_5d_ago),
        "technical_sma20_slope_5d_pct": _pct_change(sma20, sma20_5d_ago),
        "technical_sma50_slope_10d_pct": _pct_change(sma50, sma50_10d_ago),
        "technical_distance_ema20_pct": distance(ema20),
        "technical_distance_sma20_pct": distance(sma20),
        "technical_distance_sma50_pct": distance(sma50),
        "technical_distance_ema20_atr": distance_atr(ema20),
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


def classify_macd_histogram(evidence: dict) -> str:
    trajectory_state = str(evidence.get("daily_macd_trajectory_state") or "").upper()
    if trajectory_state and trajectory_state != "UNKNOWN":
        return _legacy_daily_macd_state(
            trajectory_state,
            _float(evidence.get("technical_macd_hist")),
        )
    hist = _float(evidence.get("technical_macd_hist"))
    hist_change_1d = _float(evidence.get("technical_macd_hist_change_1d"))
    two_day_rising = bool(evidence.get("technical_macd_hist_two_day_rising"))
    two_day_falling = bool(evidence.get("technical_macd_hist_two_day_falling"))

    if hist is None or hist_change_1d is None:
        return "MACD_HIST_UNKNOWN"
    improving = two_day_rising
    deteriorating = two_day_falling
    flat = abs(hist_change_1d) < 1e-9

    if improving and hist < 0:
        return "MACD_HIST_BULLISH_INFLECTION_BELOW_ZERO"
    if improving and hist >= 0:
        return "MACD_HIST_POSITIVE_EXPANDING"
    if deteriorating:
        return "MACD_HIST_DETERIORATING"
    if flat:
        return "MACD_HIST_FLATTENING"
    return "MACD_HIST_MIXED"


def classify_momentum(evidence: dict) -> tuple[str, list[str], list[str]]:
    rsi = _float(evidence.get("technical_rsi"))
    rsi_change = _float(evidence.get("technical_rsi_change_5d"))
    macd = _float(evidence.get("technical_macd"))
    macd_signal = _float(evidence.get("technical_macd_signal"))
    hist = _float(evidence.get("technical_macd_hist"))
    hist_change = _float(evidence.get("technical_macd_hist_change_1d"))
    hist_state = classify_macd_histogram(evidence)
    ema20_slope = _float(evidence.get("technical_ema20_slope_5d_pct"))
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
    elif hist_state not in {"MACD_HIST_BULLISH_INFLECTION_BELOW_ZERO", "MACD_HIST_POSITIVE_EXPANDING"}:
        negatives.append("macd_below_signal")
    if hist_state == "MACD_HIST_BULLISH_INFLECTION_BELOW_ZERO":
        positives.append("macd_hist_bullish_inflection_below_zero")
    elif hist_state == "MACD_HIST_POSITIVE_EXPANDING":
        positives.append("macd_hist_positive_expanding")
    elif hist_state == "MACD_HIST_DETERIORATING":
        negatives.append("macd_hist_deteriorating")
    elif hist_state == "MACD_HIST_FLATTENING":
        negatives.append("macd_hist_flattening")

    slope = ema20_slope if ema20_slope is not None else sma20_slope
    slope_label = "ema20" if ema20_slope is not None else "sma20"
    if slope is not None:
        if slope > 0:
            positives.append(f"{slope_label}_rising")
        elif slope < 0:
            negatives.append(f"{slope_label}_falling")

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
    ema20_pct = _float(evidence.get("technical_distance_ema20_pct"))
    sma20_pct = _float(evidence.get("technical_distance_sma20_pct"))
    ema20_atr = _float(evidence.get("technical_distance_ema20_atr"))
    sma20_atr = _float(evidence.get("technical_distance_sma20_atr"))
    reasons: list[str] = []
    caution_reasons: list[str] = []
    severe_reasons: list[str] = []

    if rsi is not None and rsi > 75:
        severe_reasons.append("rsi_above_75")
    reference_atr = ema20_atr if ema20_atr is not None else sma20_atr
    reference_pct = ema20_pct if ema20_pct is not None else sma20_pct
    reference_label = "ema20" if ema20_atr is not None else "sma20_fallback"
    if reference_atr is not None:
        if reference_atr > 2.0 and (reference_pct is None or reference_pct > 0.06):
            severe_reasons.append(f"price_more_than_2atr_and_6pct_above_{reference_label}")
        elif reference_atr > 1.25 and reference_pct is not None and reference_pct > 0.05:
            reasons.append(f"price_more_than_1_25atr_and_5pct_above_{reference_label}")
        elif reference_atr > 1.25:
            caution_reasons.append(f"price_more_than_1_25atr_above_{reference_label}")
        elif reference_atr > 0.75:
            caution_reasons.append(f"price_more_than_0_75atr_above_{reference_label}")
    if setup_type == "BREAKOUT":
        if trigger_pct is not None and trigger_pct > 0.03:
            severe_reasons.append("price_more_than_3pct_above_breakout")
        if trigger_atr is not None and trigger_atr > 1.0:
            caution_reasons.append("price_more_than_1atr_above_breakout")
    elif setup_type in {"PULLBACK", "RECLAIM", "MACD_MOMENTUM"}:
        if sma20_atr is not None and sma20_atr > 1.25 and sma20_pct is not None and sma20_pct > 0.05:
            reasons.append("price_more_than_1_25atr_and_5pct_above_sma20")
        elif sma20_atr is not None and sma20_atr > 1.25:
            caution_reasons.append("price_more_than_1_25atr_above_sma20")
    all_reasons = severe_reasons + reasons + caution_reasons
    if severe_reasons:
        return "LATE_ENTRY", all_reasons
    if len(reasons) >= 2:
        return "LATE_ENTRY", all_reasons
    if reasons:
        return "OVEREXTENDED", all_reasons
    if caution_reasons:
        return "CAUTION", all_reasons
    if trigger_atr is not None and trigger_atr > 0.65:
        return "CAUTION", ["price_extended_from_trigger"]
    return "HEALTHY", all_reasons


def calculate_extension_risk(evidence: dict, setup_type: str) -> dict[str, Any]:
    ema20_atr = _float(evidence.get("technical_distance_ema20_atr"))
    ema20_pct = _float(evidence.get("technical_distance_ema20_pct"))
    trigger_atr = _float(evidence.get("technical_trigger_distance_atr"))
    rsi = _float(evidence.get("technical_rsi"))
    return_5d = _float(evidence.get("technical_return_5d"))
    distance_percentile = _float(evidence.get("ema20_distance_percentile_1y"))
    setup = str(setup_type or "").upper()

    # Extension is one-sided: a price below EMA20 cannot be overextended above it.
    positive_atr = max(0.0, ema20_atr or 0.0)
    positive_pct = max(0.0, ema20_pct or 0.0)
    positive_trigger_atr = max(0.0, trigger_atr or 0.0)
    positive_return_5d = max(0.0, return_5d or 0.0)
    rsi_pressure = max(0.0, ((rsi or 50.0) - 65.0) / 15.0)
    percentile_pressure = max(
        0.0,
        ((distance_percentile if distance_percentile is not None else 0.50) - 0.65)
        / 0.35,
    )

    risk = (
        0.30 * min(positive_atr / 2.25, 1.0)
        + 0.22 * min(positive_pct / 0.08, 1.0)
        + 0.14 * min(positive_trigger_atr / 1.25, 1.0)
        + 0.12 * min(rsi_pressure, 1.0)
        + 0.12 * min(positive_return_5d / 0.10, 1.0)
        + 0.10 * min(percentile_pressure, 1.0)
    )
    if setup == "BREAKOUT":
        risk += 0.06 * min(positive_trigger_atr / 1.0, 1.0)
        trigger_pct = max(0.0, _float(evidence.get("technical_trigger_distance_pct")) or 0.0)
        if trigger_pct > 0.05 or positive_trigger_atr > 1.50:
            risk = max(risk, 0.80)
    elif setup == "PULLBACK":
        risk -= 0.07
    elif setup == "RECLAIM":
        risk -= 0.05
    elif setup == "MACD_MOMENTUM":
        risk -= 0.02

    if positive_atr > 2.0 and positive_pct > 0.06:
        risk = max(risk, 0.78)
    elif positive_atr > 1.25 and positive_pct > 0.05:
        risk = max(risk, 0.58)
    risk = max(0.0, min(1.0, risk))

    if ema20_atr is None:
        status = "UNKNOWN"
        confidence = "LOW"
        driver = "ema20_distance_missing"
    elif risk >= 0.75:
        status = "LATE_ENTRY"
        confidence = "HIGH"
        driver = "combined_extension_risk_extreme"
    elif risk >= 0.55:
        status = "OVEREXTENDED"
        confidence = "HIGH"
        driver = "combined_extension_risk_high"
    elif risk >= 0.28:
        status = "CAUTION"
        confidence = "MEDIUM"
        driver = "combined_extension_risk_moderate"
    else:
        status = "HEALTHY"
        confidence = "HIGH" if ema20_atr <= 0.75 else "MEDIUM"
        driver = "extension_risk_controlled"

    return {
        "ema20_extension_risk": round(risk, 4),
        "ema20_extension_confidence": confidence,
        "ema20_extension_driver": driver,
        "ema20_extension_reasons": driver,
        "entry_chase_risk": status,
        "ema20_extension_status": status,
        "ema20_distance_percentile_1y": distance_percentile,
        "ema20_extension_model": "ADAPTIVE_SETUP_VOLATILITY_V2",
    }


def classify_ema20_extension_status(evidence: dict) -> str:
    adaptive = calculate_extension_risk(evidence, str(evidence.get("setup_type") or ""))
    if adaptive["ema20_extension_status"] != "UNKNOWN":
        return str(adaptive["ema20_extension_status"])
    ema20_atr = _float(evidence.get("technical_distance_ema20_atr"))
    ema20_pct = _float(evidence.get("technical_distance_ema20_pct"))
    if ema20_atr is None:
        return "UNKNOWN"
    if ema20_atr > 2.0 and (ema20_pct is None or ema20_pct > 0.06):
        return "LATE_ENTRY"
    if ema20_atr > 1.25 and ema20_pct is not None and ema20_pct > 0.05:
        return "OVEREXTENDED"
    if ema20_atr > 0.75:
        return "CAUTION"
    return "HEALTHY"


def _state_score(state: str, mapping: dict[str, float], default: float = 50.0) -> float:
    return float(mapping.get(str(state or "").upper(), default))


def analyze_scenario(
    df: pd.DataFrame,
    *,
    setup_type: str,
    trigger_level: float | None,
    market_regime: str = "",
    selected: bool = True,
    technical_evidence: dict[str, Any] | None = None,
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
            "ema20_extension_status": "UNKNOWN",
            "entry_timing_status": "NOT_EVALUATED",
            "timing_quality_score": 0.0,
            "momentum_confirmation_score": 0.0,
            "macd_histogram_state": "MACD_HIST_UNKNOWN",
            "required_confirmation": "",
            "invalidation_reason": "",
            "engine_recommendation": "FUNNEL_ONLY",
            "scenario_trigger_confirmed": False,
        }

    evidence = (
        dict(technical_evidence)
        if technical_evidence is not None
        else build_technical_evidence(df, trigger_level=trigger_level)
    )
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
            "ema20_extension_status": "UNKNOWN",
            "entry_timing_status": "NOT_EVALUATED",
            "timing_quality_score": 0.0,
            "momentum_confirmation_score": 0.0,
            "macd_histogram_state": "MACD_HIST_UNKNOWN",
            "required_confirmation": "obtain_complete_technical_history",
            "invalidation_reason": "technical_evidence_missing",
            "engine_recommendation": "DO_NOT_ADVANCE",
            "scenario_trigger_confirmed": False,
        }

    setup = str(setup_type or "NO_VALID_SETUP").upper()
    evidence["setup_type"] = setup
    momentum_state, momentum_evidence, momentum_conflicts = classify_momentum(evidence)
    if evidence.get("ema20_extension_status"):
        extension_risk = {
            "ema20_extension_risk": evidence.get("ema20_extension_risk"),
            "ema20_extension_confidence": evidence.get("ema20_extension_confidence"),
            "ema20_extension_driver": evidence.get("ema20_extension_driver"),
            "ema20_extension_reasons": evidence.get("ema20_extension_reasons"),
            "entry_chase_risk": evidence.get(
                "entry_chase_risk",
                evidence.get("ema20_extension_status"),
            ),
            "ema20_extension_status": evidence.get("ema20_extension_status"),
        }
        evidence["technical_extension_evidence_reused"] = True
    else:
        extension_risk = calculate_extension_risk(evidence, setup)
        evidence["technical_extension_evidence_reused"] = False
    extension_state = str(extension_risk["ema20_extension_status"])
    extension_reasons = (
        [str(extension_risk.get("ema20_extension_driver"))]
        if extension_state != "HEALTHY" and extension_risk.get("ema20_extension_driver")
        else []
    )
    macd_histogram_state = classify_macd_histogram(evidence)
    weekly_macd_histogram_state = str(evidence.get("weekly_macd_histogram_state") or "WEEKLY_MACD_HIST_UNKNOWN")
    daily_trajectory_state = str(evidence.get("daily_macd_trajectory_state") or "UNKNOWN")
    weekly_trajectory_state = str(evidence.get("weekly_macd_trajectory_state") or "UNKNOWN")
    daily_macd_non_decelerating = daily_trajectory_state in OPERABLE_TRAJECTORY_STATES
    weekly_macd_non_decelerating = weekly_trajectory_state in OPERABLE_TRAJECTORY_STATES
    momentum_gate_ok = daily_macd_non_decelerating and weekly_macd_non_decelerating
    weekly_macd_improving = weekly_macd_non_decelerating
    weekly_macd_non_bearish = weekly_macd_histogram_state != "WEEKLY_MACD_HIST_BEARISH"
    ema20_extension_status = str(extension_risk["ema20_extension_status"])
    ema20_distance_atr = _float(evidence.get("technical_distance_ema20_atr"))
    ema20_distance_pct = _float(evidence.get("technical_distance_ema20_pct"))
    ema20_caution_strong = bool(
        ema20_extension_status == "CAUTION"
        and (
            (ema20_distance_atr is not None and ema20_distance_atr > 1.25)
            or (ema20_distance_pct is not None and ema20_distance_pct > 0.04)
        )
    )
    momentum_confirmation_score = _state_score(
        momentum_state,
        {
            "STRONG": 95.0,
            "IMPROVING": 82.0,
            "STABLE": 65.0,
            "DETERIORATING": 35.0,
            "WEAK": 20.0,
            "UNKNOWN": 45.0,
        },
    )
    if macd_histogram_state == "MACD_HIST_BULLISH_INFLECTION_BELOW_ZERO":
        momentum_confirmation_score = max(momentum_confirmation_score, 74.0)
    elif macd_histogram_state == "MACD_HIST_POSITIVE_EXPANDING":
        momentum_confirmation_score = max(momentum_confirmation_score, 82.0)
    elif macd_histogram_state == "MACD_HIST_DETERIORATING":
        momentum_confirmation_score = min(momentum_confirmation_score, 42.0)
    trajectory_score = (
        0.55 * _float(evidence.get("momentum_acceleration_score"), 0.0)
        + 0.45 * _float(evidence.get("momentum_persistence_score"), 0.0)
    )
    momentum_confirmation_score = 0.55 * momentum_confirmation_score + 0.45 * trajectory_score
    timing_quality_score = _state_score(
        extension_state,
        {
            "HEALTHY": 90.0,
            "CAUTION": 58.0,
            "OVEREXTENDED": 28.0,
            "LATE_ENTRY": 10.0,
            "UNKNOWN": 45.0,
        },
    )
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

    if daily_trajectory_state == "IMPROVING_BUT_DECELERATING":
        conflicts.append("daily_macd_improving_but_decelerating")
    elif daily_trajectory_state == "DECLINING":
        conflicts.append("daily_macd_declining")
    elif not daily_macd_non_decelerating:
        conflicts.append("daily_macd_trajectory_unconfirmed")

    if weekly_trajectory_state == "IMPROVING_BUT_DECELERATING":
        conflicts.append("weekly_macd_improving_but_decelerating")
    elif weekly_trajectory_state == "DECLINING":
        conflicts.append("weekly_macd_declining")
    elif weekly_macd_histogram_state == "WEEKLY_MACD_HIST_BEARISH":
        conflicts.append("weekly_macd_hist_bearish")
    elif weekly_macd_histogram_state == "WEEKLY_MACD_HIST_DECELERATING":
        conflicts.append("weekly_macd_hist_decelerating")
    elif weekly_macd_histogram_state == "WEEKLY_MACD_HIST_MIXED":
        conflicts.append("weekly_macd_hist_mixed")
    elif weekly_macd_histogram_state == "WEEKLY_MACD_HIST_UNKNOWN":
        conflicts.append("weekly_macd_hist_unknown")

    if ema20_caution_strong:
        conflicts.append("ema20_extension_caution_strong")

    if setup not in {"BREAKOUT", "PULLBACK", "RECLAIM", "MACD_MOMENTUM"}:
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
        scenario_trigger = bool(
            level_ok
            and volume_ok
            and momentum_gate_ok
            and not ema20_caution_strong
            and momentum_state in {"STRONG", "IMPROVING"}
        )
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
            and momentum_gate_ok
            and not ema20_caution_strong
            and momentum_state in {"STRONG", "IMPROVING", "STABLE"}
        )
        status = "VALID_TRIGGER" if scenario_trigger else "WAIT_FOR_CONFIRMATION"
        thesis = "Orderly pullback into support with rejection and momentum stabilization."
        required_confirmation = "" if scenario_trigger else "bullish_rejection_near_support_with_stable_momentum"
    elif setup == "RECLAIM":
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
            level_ok
            and bullish_candle
            and volume_ok
            and momentum_gate_ok
            and not ema20_caution_strong
            and momentum_state not in {"WEAK", "DETERIORATING"}
        )
        status = "VALID_TRIGGER" if scenario_trigger else "WAIT_FOR_CONFIRMATION"
        thesis = "Reclaim of support with closing and volume confirmation."
        required_confirmation = "" if scenario_trigger else "hold_reclaimed_level_with_volume"
    else:
        hist_ok = macd_histogram_state in {
            "MACD_HIST_BULLISH_INFLECTION_BELOW_ZERO",
            "MACD_HIST_POSITIVE_EXPANDING",
        }
        weekly_ok = weekly_macd_non_decelerating
        volume_ok = relative_volume >= 0.80
        if hist_ok:
            supportive.append("daily_macd_hist_two_day_rising")
        else:
            conflicts.append("daily_macd_hist_not_two_day_rising")
        if weekly_ok:
            supportive.append("weekly_macd_hist_improving")
        else:
            conflicts.append("weekly_macd_hist_not_improving")
        if volume_ok:
            supportive.append("relative_volume_acceptable_for_momentum")
        else:
            conflicts.append("relative_volume_below_0_8")
        scenario_trigger = bool(
            hist_ok
            and weekly_ok
            and daily_macd_non_decelerating
            and bullish_candle
            and momentum_state in {"STRONG", "IMPROVING"}
            and extension_state == "HEALTHY"
        )
        status = "VALID_TRIGGER" if scenario_trigger else "WAIT_FOR_CONFIRMATION"
        thesis = "MACD histogram momentum is improving inside a constructive trend."
        required_confirmation = "" if scenario_trigger else "daily_macd_hist_2d_rising_weekly_improving_and_clean_candle"

    if not momentum_gate_ok and status == "VALID_TRIGGER":
        status = "WEAK_MOMENTUM"
        scenario_trigger = False
        required_confirmation = "daily_and_weekly_macd_trajectories_resume_without_deceleration"

    if ema20_caution_strong and status == "VALID_TRIGGER":
        status = "WAIT_FOR_CONFIRMATION"
        scenario_trigger = False
        required_confirmation = "wait_for_pullback_or_consolidation_near_ema20"

    if not momentum_gate_ok and status == "WAIT_FOR_CONFIRMATION":
        required_confirmation = "daily_and_weekly_macd_trajectories_resume_without_deceleration"
    elif ema20_caution_strong and status == "WAIT_FOR_CONFIRMATION":
        required_confirmation = "wait_for_pullback_or_consolidation_near_ema20"

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
        "ema20_extension_status": ema20_extension_status,
        **extension_risk,
        "entry_timing_status": "ON_TIME" if extension_state == "HEALTHY" else extension_state,
        "timing_quality_score": round(timing_quality_score, 2),
        "momentum_confirmation_score": round(momentum_confirmation_score, 2),
        "macd_histogram_state": macd_histogram_state,
        "weekly_macd_histogram_state": weekly_macd_histogram_state,
        "weekly_macd_hist_non_bearish": weekly_macd_non_bearish,
        "weekly_macd_hist_improving": weekly_macd_improving,
        "weekly_macd_hist": evidence.get("weekly_macd_hist"),
        "weekly_macd_hist_change_1w": evidence.get("weekly_macd_hist_change_1w"),
        "weekly_macd_hist_change_2w": evidence.get("weekly_macd_hist_change_2w"),
        "weekly_macd_hist_two_week_rising": evidence.get("weekly_macd_hist_two_week_rising"),
        "weekly_macd_hist_two_week_falling": evidence.get("weekly_macd_hist_two_week_falling"),
        "daily_macd_non_decelerating": daily_macd_non_decelerating,
        "weekly_macd_non_decelerating": weekly_macd_non_decelerating,
        "momentum_alignment": evidence.get("momentum_alignment"),
        "momentum_alignment_confidence": evidence.get("momentum_alignment_confidence"),
        "momentum_acceleration_score": evidence.get("momentum_acceleration_score"),
        "momentum_persistence_score": evidence.get("momentum_persistence_score"),
        "momentum_operability_status": evidence.get("momentum_operability_status"),
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
    diagnostic_only: bool = False,
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
    eligible_statuses = (
        {"VALID_TRIGGER", "WAIT_FOR_CONFIRMATION"}
        if diagnostic_only
        else {"VALID_TRIGGER"}
    )
    if (
        df is None
        or df.empty
        or str(scenario.get("scenario_status") or "").upper() not in eligible_statuses
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
    status = (
        "DIAGNOSTIC_ONLY"
        if diagnostic_only
        else "VALID"
        if rr is not None and rr >= 1.5
        else "RR_BELOW_MINIMUM"
    )
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
