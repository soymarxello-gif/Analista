from __future__ import annotations

import json
from typing import Any

import pandas as pd


ACTIONABLE_SETUPS = {"BREAKOUT", "PULLBACK", "RECLAIM", "MACD_MOMENTUM"}


def _float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clip(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _proximity(distance: float | None, maximum: float) -> float:
    if distance is None or maximum <= 0:
        return 0.0
    return _clip(1.0 - abs(distance) / maximum)


def _rsi_quality(rsi: float | None) -> float:
    if rsi is None:
        return 0.0
    if 50.0 <= rsi <= 65.0:
        return 1.0
    if 45.0 <= rsi < 50.0:
        return _clip((rsi - 45.0) / 5.0)
    if 65.0 < rsi <= 72.0:
        return _clip((72.0 - rsi) / 7.0)
    return 0.0


def calculate_setup_readiness(
    df: pd.DataFrame,
    *,
    structure: dict[str, Any],
    evidence: dict[str, Any],
    trend_score: float,
) -> dict[str, Any]:
    if df is None or df.empty:
        return {
            "setup_readiness_score": 0.0,
            "setup_readiness_state": "NONE",
            "setup_candidate_type": "NO_VALID_SETUP",
            "setup_readiness_reason": "technical_history_missing",
            "setup_readiness_components": "{}",
        }

    row = df.iloc[-1]
    close = _float(row.get("close"))
    high = _float(row.get("high"), close)
    low = _float(row.get("low"), close)
    ema20 = _float(row.get("ema20"))
    sma50 = _float(row.get("sma50"))
    sma200 = _float(row.get("sma200"))
    rsi = _float(row.get("rsi"))
    relative_volume = _float(row.get("relative_volume"), 0.0) or 0.0
    ema_slope = _float(evidence.get("technical_ema20_slope_5d_pct"), 0.0) or 0.0
    bullish_candle = bool(evidence.get("technical_bullish_candle"))
    rejection_candle = bool(evidence.get("technical_rejection_candle"))
    close_location = _float(evidence.get("technical_close_location"), 0.5) or 0.5
    extension_risk = _float(evidence.get("ema20_extension_risk"), 0.5) or 0.5
    momentum_acceleration = (
        _float(evidence.get("momentum_acceleration_score"), 0.0) or 0.0
    ) / 100.0
    momentum_persistence = (
        _float(evidence.get("momentum_persistence_score"), 0.0) or 0.0
    ) / 100.0

    if close in {None, 0}:
        return {
            "setup_readiness_score": 0.0,
            "setup_readiness_state": "NONE",
            "setup_candidate_type": "NO_VALID_SETUP",
            "setup_readiness_reason": "close_missing",
            "setup_readiness_components": "{}",
        }

    previous_resistance = None
    if len(df) >= 21:
        previous_resistance = _float(df["high"].iloc[-21:-1].max())
    resistance_gap = (
        (previous_resistance - close) / previous_resistance
        if previous_resistance not in {None, 0}
        else None
    )
    breakout = (
        0.35 * _proximity(resistance_gap, 0.05)
        + 0.25 * _clip(relative_volume / 1.30)
        + 0.20 * _clip(trend_score)
        + 0.20 * _clip(close_location)
    )

    distances = [
        abs(close - value) / close for value in (ema20, sma50) if value is not None
    ]
    nearest_ma_distance = min(distances) if distances else None
    reaction_quality = _clip(
        0.55 * float(bullish_candle or rejection_candle) + 0.45 * close_location
    )
    pullback_volume = _clip(1.0 - abs(relative_volume - 0.80) / 0.80)
    pullback = (
        0.35 * _proximity(nearest_ma_distance, 0.06)
        + 0.25 * _clip(trend_score)
        + 0.20 * reaction_quality
        + 0.20 * pullback_volume
    )

    reclaim_distances = [
        abs(close - value) / close for value in (ema20, sma50) if value is not None
    ]
    reclaim_distance = min(reclaim_distances) if reclaim_distances else None
    above_sma200 = float(sma200 is not None and close > sma200)
    slope_quality = _clip((ema_slope + 0.01) / 0.03)
    reclaim = (
        0.35 * _proximity(reclaim_distance, 0.04)
        + 0.25 * above_sma200
        + 0.20 * slope_quality
        + 0.20 * reaction_quality
    )

    momentum_alignment = _clip(
        0.55 * momentum_acceleration + 0.45 * momentum_persistence
    )
    macd_momentum = (
        0.40 * momentum_alignment
        + 0.25 * _clip(trend_score)
        + 0.15 * _rsi_quality(rsi)
        + 0.20 * _clip(1.0 - extension_risk)
    )

    component_scores = {
        "BREAKOUT": round(100.0 * breakout, 2),
        "PULLBACK": round(100.0 * pullback, 2),
        "RECLAIM": round(100.0 * reclaim, 2),
        "MACD_MOMENTUM": round(100.0 * macd_momentum, 2),
    }
    detected_setup = str(structure.get("setup_type") or "NO_VALID_SETUP").upper()
    exact_detected = structure.get("exact_detected")
    if exact_detected is None:
        exact_detected = detected_setup in ACTIONABLE_SETUPS
    if detected_setup in ACTIONABLE_SETUPS and bool(exact_detected):
        candidate_type = detected_setup
        state = "CONFIRMED"
        score = max(component_scores.get(detected_setup, 0.0), 70.0)
        reason = f"exact_{detected_setup.lower()}_detector"
    else:
        candidate_type = max(component_scores, key=component_scores.get)
        score = component_scores[candidate_type]
        state = "FORMING" if score >= 70.0 else "NONE"
        reason = (
            f"{candidate_type.lower()}_forming_score_{score:.2f}"
            if state == "FORMING"
            else "setup_readiness_below_70"
        )

    return {
        "setup_readiness_score": round(score, 2),
        "setup_readiness_state": state,
        "setup_candidate_type": candidate_type,
        "setup_readiness_reason": reason,
        "setup_readiness_components": json.dumps(component_scores, sort_keys=True),
        "setup_breakout_resistance": previous_resistance,
        "setup_breakout_gap_pct": resistance_gap,
    }
