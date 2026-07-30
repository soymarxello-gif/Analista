from __future__ import annotations

import json

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


def _model_target_candidates(
    entry: float,
    atr: float,
    risk: float,
    df: pd.DataFrame,
    *,
    resistance: float | None,
    resistance_source: str,
) -> list[dict]:
    candidates: list[dict] = []
    if resistance is not None:
        candidates.append(
            {
                "source": resistance_source,
                "target": float(resistance),
                "model_class": "STRUCTURAL",
                "confidence": "HIGH",
            }
        )

    candidates.append(
        {
            "source": "ATR_PROJECTION_3X",
            "target": float(entry + 3.0 * atr),
            "model_class": "VOLATILITY",
            "confidence": "MEDIUM",
        }
    )
    close = pd.to_numeric(df.get("close"), errors="coerce")
    historical_4d = (close / close.shift(4) - 1.0).replace(
        [float("inf"), float("-inf")],
        np.nan,
    )
    positive_4d = historical_4d[historical_4d > 0].dropna().tail(120)
    if len(positive_4d) >= 20:
        expected_return = float(positive_4d.quantile(0.65))
        candidates.append(
            {
                "source": "HISTORICAL_4_SESSION_UPSIDE_P65",
                "target": float(entry * (1.0 + expected_return)),
                "model_class": "HORIZON",
                "confidence": "MEDIUM",
            }
        )
    if len(df) >= 20:
        recent_high = float(pd.to_numeric(df["high"].tail(20), errors="coerce").max())
        recent_low = float(pd.to_numeric(df["low"].tail(20), errors="coerce").min())
        measured_range = recent_high - recent_low
        if measured_range > 0:
            candidates.append(
                {
                    "source": "MEASURED_RANGE_20D_HALF",
                    "target": float(entry + 0.5 * measured_range),
                    "model_class": "MEASURED_MOVE",
                    "confidence": "MEDIUM",
                }
            )

    for candidate in candidates:
        target = float(candidate["target"])
        candidate["rr"] = float((target - entry) / risk) if risk > 0 else 0.0
    return candidates


def _select_model_target(
    candidates: list[dict],
    *,
    min_rr: float,
    tolerance_pct: float,
) -> tuple[float | None, str, str, bool, list[str]]:
    structural = [
        candidate
        for candidate in candidates
        if candidate["model_class"] == "STRUCTURAL" and candidate["rr"] >= min_rr
    ]
    if structural:
        selected = min(structural, key=lambda candidate: candidate["target"])
        return (
            float(selected["target"]),
            str(selected["source"]),
            "HIGH",
            True,
            [str(selected["source"])],
        )

    eligible = [
        candidate
        for candidate in candidates
        if candidate["model_class"] != "STRUCTURAL" and candidate["rr"] >= min_rr
    ]
    best_cluster: list[dict] = []
    for anchor in eligible:
        cluster = [
            candidate
            for candidate in eligible
            if abs(candidate["target"] - anchor["target"]) / max(anchor["target"], 1e-9)
            <= tolerance_pct
            and candidate["model_class"] != anchor["model_class"]
        ]
        cluster.append(anchor)
        unique_classes = {candidate["model_class"] for candidate in cluster}
        if len(unique_classes) >= 2 and len(cluster) > len(best_cluster):
            best_cluster = cluster

    if best_cluster:
        target = float(np.median([candidate["target"] for candidate in best_cluster]))
        sources = sorted({str(candidate["source"]) for candidate in best_cluster})
        return target, "MODEL_CONFLUENCE", "MEDIUM", True, sources

    fallback = max(candidates, key=lambda candidate: candidate["target"]) if candidates else None
    if fallback is None:
        return None, "NONE", "UNKNOWN", False, []
    return (
        float(fallback["target"]),
        str(fallback["source"]),
        "LOW",
        False,
        [str(fallback["source"])],
    )


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
            "rr_valid": False,
            "rr_status": "DATA_UNAVAILABLE",
            "rr_confidence": "UNKNOWN",
            "target_validation_source": "NONE",
            "stop_method": None,
            "target_method": None,
            "rr_stressed": None,
            "risk_geometry_status": "INVALID",
            "risk_geometry_reason": "risk_reward_data_unavailable",
        }

    row = df.iloc[-1]
    entry = float(row["close"])
    atr = row.get("atr")
    setup_type = str((structure or {}).get("setup_type") or "NO_VALID_SETUP").upper()

    if setup_type in {"", "NO_VALID_SETUP", "VOLATILITY_CONTRACTION"}:
        return {
            "rr_score": 0.0,
            "entry": entry,
            "stop": None,
            "target": None,
            "rr": None,
            "rr_valid": False,
            "rr_status": "NOT_APPLICABLE_FORMING_SETUP",
            "rr_confidence": "UNKNOWN",
            "target_validation_source": "NONE",
            "stop_method": None,
            "target_method": None,
            "atr": float(atr) if atr is not None and atr == atr else None,
            "stop_atr_multiple": None,
            "stop_atr_status": "NOT_AVAILABLE",
            "rr_stressed": None,
            "risk_geometry_status": "INVALID",
            "risk_geometry_reason": "forming_setup_has_no_operational_geometry",
        }

    if atr != atr or atr is None or atr <= 0:
        return {
            "rr_score": 0.0,
            "entry": entry,
            "stop": None,
            "target": None,
            "rr": None,
            "rr_valid": False,
            "rr_status": "DATA_UNAVAILABLE",
            "rr_confidence": "UNKNOWN",
            "target_validation_source": "NONE",
            "stop_method": "no_atr",
            "target_method": None,
            "atr": None,
            "stop_atr_multiple": None,
            "stop_atr_status": "NO_ATR",
            "rr_stressed": None,
            "risk_geometry_status": "INVALID",
            "risk_geometry_reason": "atr_unavailable",
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

    resistance, resistance_source = _nearest_resistance_above(entry, df)
    target_candidates = _model_target_candidates(
        entry,
        float(atr),
        float(risk),
        df,
        resistance=resistance,
        resistance_source=resistance_source,
    )
    target, target_validation_source, rr_confidence, target_validated, confluence_sources = (
        _select_model_target(
            target_candidates,
            min_rr=float(rr_cfg.get("min_rr_absolute", 1.5)),
            tolerance_pct=float(rr_cfg.get("model_confluence_tolerance_pct", 0.25)),
        )
    )
    if target is None:
        target = entry + 3 * atr
        target_validation_source = "ATR_PROJECTION"
        rr_confidence = "LOW"
        target_validated = False
        confluence_sources = ["ATR_PROJECTION"]
    target_method = target_validation_source

    reward = target - entry
    rr = reward / risk if risk > 0 else 0

    rr_score = np.interp(rr, [1.0, 2.0, 3.0], [0.0, 0.7, 1.0])
    min_rr_absolute = float(rr_cfg.get("min_rr_absolute", 1.5))
    rr_valid = bool(target_validated and rr >= min_rr_absolute)
    rr_status = "VALIDATED" if rr_valid else "DIAGNOSTIC_ONLY"
    if not rr_valid:
        rr_confidence = "LOW"

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

    stressed_risk = max(float(risk), float(preferred_min * atr))
    rr_stressed = float(reward / stressed_risk) if stressed_risk > 0 and reward > 0 else None
    if not rr_valid:
        risk_geometry_status = "INVALID"
        risk_geometry_reason = "base_rr_not_validated"
    elif rr_stressed is None or rr_stressed < min_rr_absolute:
        risk_geometry_status = "FRAGILE"
        risk_geometry_reason = "rr_depends_on_aggressive_tight_stop"
    else:
        risk_geometry_status = "ROBUST"
        risk_geometry_reason = "rr_survives_one_atr_stop_floor"

    return {
        "rr_score": float(np.clip(rr_score, 0, 1)),
        "entry": entry,
        "stop": float(stop),
        "target": float(target),
        "rr": float(rr),
        "rr_valid": rr_valid,
        "rr_status": rr_status,
        "rr_confidence": rr_confidence,
        "target_validation_source": target_validation_source,
        "target_validation_sources": ", ".join(confluence_sources),
        "target_candidates": json.dumps(target_candidates, sort_keys=True),
        "stop_method": stop_method,
        "target_method": target_method,
        "risk_pct": float(risk / entry) if entry else None,
        "reward_pct": float(reward / entry) if entry else None,
        "atr": float(atr),
        "stop_atr_multiple": float(stop_atr_multiple) if stop_atr_multiple is not None else None,
        "stop_atr_status": stop_atr_status,
        "rr_stressed": rr_stressed,
        "risk_geometry_status": risk_geometry_status,
        "risk_geometry_reason": risk_geometry_reason,
    }
