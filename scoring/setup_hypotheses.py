from __future__ import annotations

import json
from typing import Any

import pandas as pd

from setups.breakout import detect_breakout
from setups.macd_momentum import detect_macd_momentum
from setups.pullback import detect_pullback
from setups.reclaim import detect_reclaim
from setups.volatility_contraction import detect_volatility_contraction


ACTIONABLE_SETUPS = {"BREAKOUT", "PULLBACK", "RECLAIM", "MACD_MOMENTUM"}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_components(readiness: dict[str, Any]) -> dict[str, float]:
    raw = readiness.get("setup_readiness_components", {})
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw = {}
    if not isinstance(raw, dict):
        return {}
    return {str(key).upper(): _safe_float(value) for key, value in raw.items()}


def _safe_detector(detector, df: pd.DataFrame, config: dict) -> dict[str, Any]:
    try:
        result = detector(df, config)
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}


def evaluate_setup_hypotheses(
    df: pd.DataFrame,
    config: dict,
    *,
    legacy_structure: dict[str, Any],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    """
    Evaluate every supported setup instead of accepting the first detector hit.

    The legacy structure is retained as evidence so isolated tests and historical
    callers remain compatible. Ranking uses continuous readiness plus a modest
    confirmation bonus; an early detector can no longer hide a stronger thesis.
    """
    detectors = {
        "BREAKOUT": (_safe_detector(detect_breakout, df, config), "is_breakout", "breakout_level"),
        "PULLBACK": (_safe_detector(detect_pullback, df, config), "is_pullback", "pullback_level"),
        "RECLAIM": (_safe_detector(detect_reclaim, df, config), "is_reclaim", "reclaim_level"),
        "MACD_MOMENTUM": (
            _safe_detector(detect_macd_momentum, df, config),
            "is_macd_momentum",
            "macd_momentum_level",
        ),
        "VOLATILITY_CONTRACTION": (
            _safe_detector(detect_volatility_contraction, df, config),
            "is_vcp",
            "trigger_level",
        ),
    }
    components = _read_components(readiness)
    legacy_type = str(legacy_structure.get("setup_type") or "NO_VALID_SETUP").upper()
    legacy_trigger = legacy_structure.get("trigger_level")

    hypotheses: list[dict[str, Any]] = []
    for setup_type, (detector_data, flag_key, trigger_key) in detectors.items():
        exact = bool(detector_data.get(flag_key))
        if setup_type == legacy_type and legacy_type != "NO_VALID_SETUP":
            exact = True
        raw_score = _safe_float(components.get(setup_type))
        if setup_type == legacy_type:
            raw_score = max(
                raw_score,
                100.0 * _safe_float(legacy_structure.get("structure_score"), 0.0),
            )
        trigger_level = detector_data.get(trigger_key)
        if setup_type == legacy_type and legacy_trigger is not None:
            trigger_level = legacy_trigger

        if exact:
            state = "CONFIRMED"
        elif raw_score >= 70.0:
            state = "FORMING"
        else:
            state = "NONE"

        confirmation_bonus = 7.5 if exact else 0.0
        hypothesis_score = min(100.0, raw_score + confirmation_bonus)
        hypotheses.append(
            {
                "setup_type": setup_type,
                "quality_score": round(raw_score, 2),
                "hypothesis_score": round(hypothesis_score, 2),
                "state": state,
                "exact_detected": exact,
                "trigger_level": trigger_level,
                "trigger_confirmed": bool(
                    exact and setup_type in {"BREAKOUT", "PULLBACK", "RECLAIM"}
                ),
                "detector_evidence": detector_data,
            }
        )

    hypotheses.sort(
        key=lambda item: (
            -float(item["hypothesis_score"]),
            0 if item["state"] == "CONFIRMED" else 1,
            item["setup_type"],
        )
    )
    primary = hypotheses[0] if hypotheses else {
        "setup_type": "NO_VALID_SETUP",
        "quality_score": 0.0,
        "hypothesis_score": 0.0,
        "state": "NONE",
        "exact_detected": False,
        "trigger_level": None,
        "trigger_confirmed": False,
    }
    if primary["state"] == "NONE":
        primary = {**primary, "setup_type": "NO_VALID_SETUP"}

    alternatives = [
        item
        for item in hypotheses[1:]
        if item["state"] != "NONE" or float(item["quality_score"]) >= 55.0
    ]
    structure_score = max(
        _safe_float(primary.get("quality_score")) / 100.0,
        _safe_float(legacy_structure.get("structure_score"), 0.0)
        if primary.get("setup_type") == legacy_type
        else 0.0,
    )
    primary_structure = {
        "structure_score": round(min(max(structure_score, 0.0), 1.0), 4),
        "setup_type": primary.get("setup_type", "NO_VALID_SETUP"),
        "trigger_confirmed": bool(primary.get("trigger_confirmed", False)),
        "trigger_level": primary.get("trigger_level"),
        "exact_detected": bool(primary.get("exact_detected", False)),
        "setup_hypothesis_state": primary.get("state", "NONE"),
    }
    serializable = [
        {key: value for key, value in item.items() if key != "detector_evidence"}
        for item in hypotheses
    ]
    return {
        "primary_setup_hypothesis": primary.get("setup_type", "NO_VALID_SETUP"),
        "primary_setup_hypothesis_state": primary.get("state", "NONE"),
        "primary_setup_hypothesis_score": primary.get("hypothesis_score", 0.0),
        "setup_hypothesis_count": int(
            sum(item["state"] in {"CONFIRMED", "FORMING"} for item in hypotheses)
        ),
        "setup_hypotheses": json.dumps(serializable, sort_keys=True),
        "alternative_setup_hypotheses": json.dumps(
            [
                {key: value for key, value in item.items() if key != "detector_evidence"}
                for item in alternatives
            ],
            sort_keys=True,
        ),
        "primary_structure": primary_structure,
    }
