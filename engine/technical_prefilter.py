from __future__ import annotations

from typing import Any

import pandas as pd

from engine.scenario_engine import (
    build_technical_evidence,
    classify_ema20_extension_status,
    classify_macd_histogram,
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
        }

    daily_state = classify_macd_histogram(evidence)
    weekly_state = _safe_text(
        evidence.get("weekly_macd_histogram_state"),
        "WEEKLY_MACD_HIST_UNKNOWN",
    )
    ema20_state = classify_ema20_extension_status(evidence)

    daily_status = "PASS" if daily_state in DAILY_MACD_PASS_STATES else "FAIL"
    weekly_status = "PASS" if weekly_state in WEEKLY_MACD_PASS_STATES else "FAIL"
    if ema20_state in EMA20_EXTENSION_FAIL_STATES:
        ema20_status = "FAIL"
    elif ema20_state in EMA20_EXTENSION_WARN_STATES:
        ema20_status = "WARN"
    else:
        ema20_status = "PASS" if ema20_state == "HEALTHY" else "UNKNOWN"

    reasons: list[str] = []
    if daily_status != "PASS":
        reasons.append(f"daily_macd_{daily_state.lower()}")
    if weekly_status != "PASS":
        reasons.append(f"weekly_macd_{weekly_state.lower()}")
    if ema20_status == "FAIL":
        reasons.append(f"ema20_extension_{ema20_state.lower()}")

    status = "PASS" if not reasons else "FAIL"

    return {
        **evidence,
        "technical_prefilter_status": status,
        "technical_prefilter_reason": "; ".join(reasons) if reasons else "technical_prefilter_pass",
        "daily_macd_prefilter_status": daily_status,
        "weekly_macd_prefilter_status": weekly_status,
        "ema20_extension_prefilter_status": ema20_status,
        "ema20_extension_reference_source": _ema20_reference_source(evidence),
        "macd_histogram_state": daily_state,
        "weekly_macd_histogram_state": weekly_state,
        "ema20_extension_status": ema20_state,
        "technical_prefilter_guardrail": "analysis_only_no_trigger_promotion",
    }
