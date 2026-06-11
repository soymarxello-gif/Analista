from __future__ import annotations

import numpy as np
import pandas as pd


def _pivot_highs(df: pd.DataFrame, left: int = 2, right: int = 2) -> list[float]:
    highs = df["high"].astype(float).tolist()
    pivots = []
    for i in range(left, len(highs) - right):
        window = highs[i - left : i + right + 1]
        if highs[i] == max(window) and window.count(highs[i]) == 1:
            pivots.append(highs[i])
    return pivots


def _pivot_lows(df: pd.DataFrame, left: int = 2, right: int = 2) -> list[float]:
    lows = df["low"].astype(float).tolist()
    pivots = []
    for i in range(left, len(lows) - right):
        window = lows[i - left : i + right + 1]
        if lows[i] == min(window) and window.count(lows[i]) == 1:
            pivots.append(lows[i])
    return pivots


def _nearest_resistance_above(entry: float, df: pd.DataFrame, min_distance_pct: float = 0.01) -> tuple[float | None, str]:
    lookbacks = [20, 40, 60, 120]
    candidates: list[tuple[float, str]] = []

    for lb in lookbacks:
        if len(df) >= lb:
            high = float(df["high"].tail(lb).max())
            if high > entry * (1 + min_distance_pct):
                candidates.append((high, f"high_{lb}d"))

    pivots = _pivot_highs(df.tail(140), left=2, right=2)
    for p in pivots:
        if p > entry * (1 + min_distance_pct):
            candidates.append((float(p), "pivot_high"))

    if not candidates:
        return None, "atr_projection"

    # Nearest meaningful resistance above entry.
    candidates = sorted(candidates, key=lambda x: x[0])
    return candidates[0]


def _structural_support(entry: float, df: pd.DataFrame) -> tuple[float | None, str]:
    candidates: list[tuple[float, str]] = []

    if len(df) >= 20:
        candidates.append((float(df["low"].tail(20).min()), "low_20d"))
    if len(df) >= 50:
        candidates.append((float(df["low"].tail(50).min()), "low_50d"))

    for ma_col in ["ma20", "ma50"]:
        if ma_col in df.columns:
            ma = df[ma_col].iloc[-1]
            if ma == ma and ma is not None and float(ma) < entry:
                candidates.append((float(ma), ma_col))

    pivots = _pivot_lows(df.tail(100), left=2, right=2)
    for p in pivots:
        if p < entry:
            candidates.append((float(p), "pivot_low"))

    if not candidates:
        return None, "atr_stop"

    # Highest support below price = closest defendable level.
    candidates = [c for c in candidates if c[0] < entry]
    if not candidates:
        return None, "atr_stop"

    candidates = sorted(candidates, key=lambda x: x[0], reverse=True)
    return candidates[0]


def score_risk_reward(df, structure, config):
    """
    Improved R:R:
    - Entry: latest close for scanner purposes.
    - Stop: max of ATR stop and nearest structural support buffer when valid.
    - Target: nearest relevant resistance above entry; fallback to ATR projection.
    - Score: still maps R:R to 0-1, but returns target/stop method diagnostics.
    """
    if df is None or df.empty:
        return {
           "rr_score": 0.0,
            "entry": None,
            "stop": None,
            "target": None,
            "rr": None,
            "stop_method": None,
            "target_method": None,
        }

    row = df.iloc[-1]
    entry = float(row["close"])
    atr = row.get("atr")

    if atr != atr or atr is None or atr <= 0:
        return {
           "rr_score": 0.0,
            "entry": entry,
            "stop": None,
            "target": None,
            "rr": None,
            "stop_method": "no_atr",
            "target_method": None,
            "atr": None,
            "stop_atr_multiple": None,
            "stop_atr_status": "NO_ATR",
        }

    rr_cfg = config.get("risk_reward", {})
    atr_mult = rr_cfg.get("atr_stop_multiplier", 1.5)
    min_rr_acceptable = rr_cfg.get("min_rr_acceptable", 1.7)

    atr_stop = entry - atr_mult * atr
    support, support_method = _structural_support(entry, df)

    if support is not None:
        structural_stop = support * 0.995
        # Avoid stop that is unrealistically tight.
        min_stop_distance = entry - 0.75 * atr
        stop = min(structural_stop, min_stop_distance)
        stop = max(stop, atr_stop)
        stop_method = f"structural:{support_method}"
    else:
        stop = atr_stop
        stop_method = "atr_stop"

    risk = entry - stop
    if risk <= 0:
        stop = atr_stop
        risk = entry - stop
        stop_method = "atr_stop_fallback"

    resistance, target_method = _nearest_resistance_above(entry, df)

    atr_projection = entry + 3 * atr
    if resistance is None:
        target = atr_projection
    else:
        # Use nearest resistance only if it gives an acceptable R:R; otherwise use ATR projection.
        rr_to_resistance = (resistance - entry) / risk if risk > 0 else 0
        if rr_to_resistance >= min_rr_acceptable:
            target = resistance
        else:
            target = max(resistance, atr_projection)
            target_method = f"{target_method}+atr_projection"

    reward = target - entry
    rr = reward / risk if risk > 0 else 0

    rr_score = np.interp(rr, [1.0, 2.0, 3.0], [0.0, 0.7, 1.0])

    stop_atr_multiple = risk / atr if atr and atr > 0 else None

    risk_profile_cfg = config.get("risk_profile", {})
    stop_atr_cfg = risk_profile_cfg.get("stop_atr_multiple", {})

    hard_min = float(stop_atr_cfg.get("hard_min", 0.60))
    preferred_min = float(stop_atr_cfg.get("preferred_min", 1.00))
    preferred_max = float(stop_atr_cfg.get("preferred_max", 2.50))

    if stop_atr_multiple is None:
        stop_atr_status = "NO_ATR"
    elif stop_atr_multiple < hard_min:
        stop_atr_status = "BELOW_HARD_MIN"
    elif stop_atr_multiple < preferred_min:
        stop_atr_status = "AGGRESSIVE_TIGHT"
    elif stop_atr_multiple <= preferred_max:
        stop_atr_status = "IDEAL"
    else:
        stop_atr_status = "WIDE"
    
    return {
        "rr_score": float(np.clip(rr_score, 0, 1)),
        "entry": entry,
        "stop": float(stop),
        "target": float(target),
        "rr": float(rr),
        "stop_method": stop_method,
        "target_method": target_method,
        "risk_pct": float(risk / entry) if entry else None,
        "reward_pct": float(reward / entry) if entry else None,
        "atr": float(atr),
        "stop_atr_multiple": float(stop_atr_multiple) if stop_atr_multiple is not None else None,
        "stop_atr_status": stop_atr_status,
    }
