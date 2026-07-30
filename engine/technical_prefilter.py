from __future__ import annotations

from typing import Any

import pandas as pd

from engine.scenario_engine import (
    build_technical_evidence,
    calculate_extension_risk,
    classify_ema20_extension_status,
    classify_macd_histogram,
)
from engine.momentum_trajectory import (
    DECELERATING_TRAJECTORY_STATES,
    OPERABLE_TRAJECTORY_STATES,
)


DAILY_MACD_PASS_STATES = {
    "MACD_HIST_BULLISH_INFLECTION_BELOW_ZERO",
    "MACD_HIST_POSITIVE_EXPANDING",
}

WEEKLY_MACD_PASS_STATES = {"WEEKLY_MACD_HIST_IMPROVING"}

EMA20_EXTENSION_FAIL_STATES = {"OVEREXTENDED", "LATE_ENTRY"}
EMA20_EXTENSION_WARN_STATES = {"CAUTION"}


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    text = str(value).strip()
    return default if text.lower() in {"", "nan", "none", "null"} else text


def _ema20_reference_source(evidence: dict[str, Any]) -> str:
    return "EMA20" if evidence.get("technical_ema20") is not None else "SMA20_FALLBACK"


def evaluate_technical_prefilter(df: pd.DataFrame) -> dict[str, Any]:
    """
    Conservative early technical gate.

    This gate only decides whether a ticker deserves expensive enrichment and
    deep analysis. It does not create an entry signal and never changes P0 quote
    or execution rules.
    """
    if df is None or df.empty:
        return {
            "technical_prefilter_status": "FAIL",
            "technical_prefilter_reason": "technical_history_missing",
            "daily_macd_prefilter_status": "FAIL",
            "weekly_macd_prefilter_status": "FAIL",
            "ema20_extension_prefilter_status": "UNKNOWN",
            "ema20_extension_reference_source": "UNKNOWN",
            "macd_histogram_state": "MACD_HIST_UNKNOWN",
            "weekly_macd_histogram_state": "WEEKLY_MACD_HIST_UNKNOWN",
            "ema20_extension_status": "UNKNOWN",
            "daily_macd_trajectory_state": "UNKNOWN",
            "weekly_macd_trajectory_state": "UNKNOWN",
            "daily_macd_non_decelerating": False,
            "weekly_macd_non_decelerating": False,
            "technical_prefilter_triage": "INSUFFICIENT_DATA",
        }

    evidence = build_technical_evidence(df)
    if not evidence.get("evidence_available"):
        return {
            **evidence,
            "technical_prefilter_status": "FAIL",
            "technical_prefilter_reason": "technical_evidence_missing",
            "daily_macd_prefilter_status": "FAIL",
            "weekly_macd_prefilter_status": "FAIL",
            "ema20_extension_prefilter_status": "UNKNOWN",
            "ema20_extension_reference_source": _ema20_reference_source(evidence),
            "macd_histogram_state": "MACD_HIST_UNKNOWN",
            "weekly_macd_histogram_state": _safe_text(
                evidence.get("weekly_macd_histogram_state"),
                "WEEKLY_MACD_HIST_UNKNOWN",
            ),
            "ema20_extension_status": "UNKNOWN",
            "daily_macd_trajectory_state": _safe_text(
                evidence.get("daily_macd_trajectory_state"),
                "UNKNOWN",
            ),
            "weekly_macd_trajectory_state": _safe_text(
                evidence.get("weekly_macd_trajectory_state"),
                "UNKNOWN",
            ),
            "daily_macd_non_decelerating": False,
            "weekly_macd_non_decelerating": False,
            "technical_prefilter_triage": "INSUFFICIENT_DATA",
        }

    daily_state = classify_macd_histogram(evidence)
    weekly_state = _safe_text(
        evidence.get("weekly_macd_histogram_state"),
        "WEEKLY_MACD_HIST_UNKNOWN",
    )
    # Setup is not known at this stage. Extension is diagnostic only here and
    # becomes authoritative after structure detection in technical_assessment.
    extension_risk = calculate_extension_risk(evidence, "PREFILTER")
    ema20_state = str(extension_risk.get("ema20_extension_status") or "UNKNOWN")
    daily_trajectory = _safe_text(
        evidence.get("daily_macd_trajectory_state"),
        "UNKNOWN",
    ).upper()
    weekly_trajectory = _safe_text(
        evidence.get("weekly_macd_trajectory_state"),
        "UNKNOWN",
    ).upper()

    daily_status = (
        "PASS"
        if daily_trajectory in OPERABLE_TRAJECTORY_STATES
        or (daily_trajectory == "UNKNOWN" and daily_state in DAILY_MACD_PASS_STATES)
        else "FAIL"
    )
    weekly_status = (
        "PASS"
        if weekly_trajectory in OPERABLE_TRAJECTORY_STATES
        or (weekly_trajectory == "UNKNOWN" and weekly_state in WEEKLY_MACD_PASS_STATES)
        else "FAIL"
    )
    if ema20_state in EMA20_EXTENSION_FAIL_STATES | EMA20_EXTENSION_WARN_STATES:
        ema20_status = "WARN"
    else:
        ema20_status = "PASS" if ema20_state == "HEALTHY" else "UNKNOWN"

    reasons: list[str] = []
    if daily_status != "PASS":
        reasons.append(f"daily_macd_{daily_state.lower()}")
    if weekly_status != "PASS":
        reasons.append(f"weekly_macd_{weekly_state.lower()}")

    daily_decelerating = (
        daily_trajectory in DECELERATING_TRAJECTORY_STATES
        or daily_state in {"MACD_HIST_DETERIORATING", "MACD_HIST_IMPROVING_BUT_DECELERATING"}
    )
    weekly_decelerating = (
        weekly_trajectory in DECELERATING_TRAJECTORY_STATES
        or weekly_state in {
            "WEEKLY_MACD_HIST_DECELERATING",
            "WEEKLY_MACD_HIST_BEARISH",
        }
    )
    if daily_decelerating or weekly_decelerating:
        triage = "REJECT_MOMENTUM"
    elif daily_status != "PASS" or weekly_status != "PASS":
        triage = "MONITOR_MOMENTUM"
    else:
        triage = "ADVANCE_DEEP_ANALYSIS"

    status = "PASS" if triage == "ADVANCE_DEEP_ANALYSIS" else "FAIL"

    return {
        **evidence,
        **extension_risk,
        "technical_prefilter_status": status,
        "technical_prefilter_reason": "; ".join(reasons) if reasons else "technical_prefilter_pass",
        "daily_macd_prefilter_status": daily_status,
        "weekly_macd_prefilter_status": weekly_status,
        "ema20_extension_prefilter_status": ema20_status,
        "ema20_extension_reference_source": _ema20_reference_source(evidence),
        "macd_histogram_state": daily_state,
        "weekly_macd_histogram_state": weekly_state,
        "daily_macd_trajectory_state": daily_trajectory,
        "weekly_macd_trajectory_state": weekly_trajectory,
        "daily_macd_non_decelerating": daily_status == "PASS",
        "weekly_macd_non_decelerating": weekly_status == "PASS",
        "technical_prefilter_triage": triage,
        "ema20_extension_status": ema20_state,
        "technical_prefilter_guardrail": "analysis_only_no_trigger_promotion",
    }
