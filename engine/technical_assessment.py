from __future__ import annotations

from typing import Any

import pandas as pd

from engine.momentum_trajectory import (
    DECELERATING_TRAJECTORY_STATES,
    OPERABLE_TRAJECTORY_STATES,
)
from engine.opportunity_model import (
    build_extension_distribution_features,
    calculate_opportunity_scores,
    classify_decision_lane,
    legacy_lane_for_decision,
)
from engine.scenario_engine import calculate_extension_risk
from scoring.risk_reward_score import score_risk_reward
from scoring.setup_hypotheses import evaluate_setup_hypotheses
from scoring.setup_readiness import calculate_setup_readiness
from scoring.structure_score import score_structure
from scoring.trend_score import score_trend


VALID_SETUP_TYPES = {"BREAKOUT", "PULLBACK", "RECLAIM", "MACD_MOMENTUM"}
RADAR_SETUP_TYPES = {"VOLATILITY_CONTRACTION"}


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return default if text.lower() in {"", "nan", "none", "null"} else text


def _trigger_evidence(evidence: dict[str, Any], trigger_level: Any) -> dict[str, Any]:
    enriched = dict(evidence or {})
    close = _safe_float(enriched.get("technical_close"))
    atr = _safe_float(enriched.get("technical_atr"))
    trigger = _safe_float(trigger_level)
    enriched["technical_trigger_level"] = trigger
    enriched["technical_trigger_distance_pct"] = (
        (close - trigger) / trigger
        if close is not None and trigger not in {None, 0}
        else None
    )
    enriched["technical_trigger_distance_atr"] = (
        (close - trigger) / atr
        if close is not None and trigger is not None and atr not in {None, 0}
        else None
    )
    return enriched


def _trend_compatibility(
    *,
    setup_type: str,
    trend_score: float,
    evidence: dict[str, Any],
    momentum_operable: bool,
) -> tuple[str, float, str]:
    close = _safe_float(evidence.get("technical_close"))
    sma200 = _safe_float(evidence.get("technical_sma200"))

    if setup_type in {"BREAKOUT", "MACD_MOMENTUM", "VOLATILITY_CONTRACTION"}:
        minimum = 0.70
        compatible = trend_score >= minimum
        reason = "continuation_trend_compatible" if compatible else "continuation_trend_below_0_70"
    elif setup_type == "PULLBACK":
        minimum = 0.60
        compatible = trend_score >= minimum
        reason = "pullback_trend_compatible" if compatible else "pullback_trend_below_0_60"
    elif setup_type == "RECLAIM":
        minimum = 0.45
        above_sma200 = close is not None and sma200 is not None and close > sma200
        compatible = trend_score >= minimum and above_sma200 and momentum_operable
        if compatible:
            reason = "reclaim_recovery_compatible"
        elif trend_score < minimum:
            reason = "reclaim_trend_below_0_45"
        elif not above_sma200:
            reason = "reclaim_below_sma200"
        else:
            reason = "reclaim_momentum_unconfirmed"
    else:
        minimum = 1.0
        compatible = False
        reason = "setup_missing_or_not_actionable"

    compatibility_score = min(max(trend_score / minimum, 0.0), 1.0) if minimum > 0 else 0.0
    return ("COMPATIBLE" if compatible else "INCOMPATIBLE", compatibility_score, reason)


def _trend_transition_evaluation(
    *,
    setup_type: str,
    trend_score: float,
    evidence: dict[str, Any],
    operational_compatibility: str,
    operational_component: float,
) -> dict[str, Any]:
    ema20_slope = _safe_float(evidence.get("technical_ema20_slope_5d_pct"), 0.0) or 0.0
    sma50_slope = _safe_float(evidence.get("technical_sma50_slope_10d_pct"), 0.0) or 0.0
    close = _safe_float(evidence.get("technical_close"))
    sma200 = _safe_float(evidence.get("technical_sma200"))
    above_sma200 = close is not None and sma200 is not None and close > sma200

    slope_score = 0.5
    slope_score += 0.25 if ema20_slope > 0 else -0.20 if ema20_slope < 0 else 0.0
    slope_score += 0.20 if sma50_slope > 0 else -0.15 if sma50_slope < 0 else 0.0
    slope_score = min(max(slope_score, 0.0), 1.0)
    structure_location = 1.0 if above_sma200 else 0.35
    transition_score = min(
        max(
            0.55 * operational_component
            + 0.25 * slope_score
            + 0.20 * structure_location,
            0.0,
        ),
        1.0,
    )

    if operational_compatibility == "COMPATIBLE":
        state = "COMPATIBLE"
    elif transition_score >= 0.62:
        state = "TRANSITIONAL"
    else:
        state = "INCOMPATIBLE"
    if setup_type == "RECLAIM" and not above_sma200 and transition_score >= 0.48:
        state = "TRANSITIONAL"

    return {
        "trend_transition_score": round(100.0 * transition_score, 2),
        "trend_transition_state": state,
        "trend_transition_reason": (
            "trend_operationally_compatible"
            if state == "COMPATIBLE"
            else "trend_transition_supported_by_slopes"
            if state == "TRANSITIONAL"
            else "trend_evidence_insufficient_for_setup"
        ),
        "trend_above_sma200": above_sma200,
    }


def _momentum_component(evidence: dict[str, Any]) -> float:
    acceleration = _safe_float(evidence.get("momentum_acceleration_score"), 0.0) or 0.0
    persistence = _safe_float(evidence.get("momentum_persistence_score"), 0.0) or 0.0
    return min(max((acceleration + persistence) / 200.0, 0.0), 1.0)


def evaluate_technical_opportunity(
    df: pd.DataFrame,
    config: dict,
    *,
    liquidity: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    legacy_structure = score_structure(df, config)
    trend_score, trend_status = score_trend(df, config)
    legacy_setup_type = _safe_text(
        legacy_structure.get("setup_type"),
        "NO_VALID_SETUP",
    ).upper()
    evidence = build_extension_distribution_features(df, evidence)
    preliminary_evidence = _trigger_evidence(
        evidence,
        legacy_structure.get("trigger_level"),
    )
    preliminary_evidence["setup_type"] = legacy_setup_type
    preliminary_extension = calculate_extension_risk(
        preliminary_evidence,
        legacy_setup_type,
    )
    preliminary_readiness = calculate_setup_readiness(
        df,
        structure=legacy_structure,
        evidence={**preliminary_evidence, **preliminary_extension},
        trend_score=float(trend_score),
    )
    hypotheses = evaluate_setup_hypotheses(
        df,
        config,
        legacy_structure=legacy_structure,
        readiness=preliminary_readiness,
    )
    structure = hypotheses.get("primary_structure") or legacy_structure
    setup_type = _safe_text(structure.get("setup_type"), "NO_VALID_SETUP").upper()
    evidence_with_trigger = _trigger_evidence(evidence, structure.get("trigger_level"))
    evidence_with_trigger["setup_type"] = setup_type
    extension = calculate_extension_risk(evidence_with_trigger, setup_type)
    readiness = calculate_setup_readiness(
        df,
        structure=structure,
        evidence={**evidence_with_trigger, **extension},
        trend_score=float(trend_score),
    )
    rr_data = score_risk_reward(df, structure, config)
    readiness_state = _safe_text(
        readiness.get("setup_readiness_state"),
        "NONE",
    ).upper()
    research_setup_type = _safe_text(
        readiness.get("setup_candidate_type"),
        setup_type,
    ).upper()
    research_rr_data: dict[str, Any] = {}
    if (
        readiness_state == "FORMING"
        and setup_type not in VALID_SETUP_TYPES
        and research_setup_type in VALID_SETUP_TYPES
    ):
        research_rr_data = score_risk_reward(
            df,
            {**structure, "setup_type": research_setup_type},
            config,
        )
        research_rr_data = {
            **research_rr_data,
            "rr_valid": False,
            "rr_status": "DIAGNOSTIC_ONLY",
            "rr_confidence": "LOW",
        }
    compatibility_setup_type = (
        setup_type if setup_type in VALID_SETUP_TYPES else research_setup_type
    )

    daily_state = _safe_text(
        evidence.get("daily_macd_trajectory_state"),
        "UNKNOWN",
    ).upper()
    weekly_state = _safe_text(
        evidence.get("weekly_macd_trajectory_state"),
        "UNKNOWN",
    ).upper()
    daily_operable = daily_state in OPERABLE_TRAJECTORY_STATES
    weekly_operable = weekly_state in OPERABLE_TRAJECTORY_STATES
    momentum_operable = daily_operable and weekly_operable
    explicit_deceleration = (
        daily_state in DECELERATING_TRAJECTORY_STATES
        or weekly_state in DECELERATING_TRAJECTORY_STATES
    )

    trend_compatibility, trend_component, trend_reason = _trend_compatibility(
        setup_type=compatibility_setup_type,
        trend_score=float(trend_score),
        evidence=evidence_with_trigger,
        momentum_operable=momentum_operable,
    )
    trend_transition = _trend_transition_evaluation(
        setup_type=compatibility_setup_type,
        trend_score=float(trend_score),
        evidence=evidence_with_trigger,
        operational_compatibility=trend_compatibility,
        operational_component=trend_component,
    )
    close = _safe_float(evidence_with_trigger.get("technical_close"))
    sma200 = _safe_float(evidence_with_trigger.get("technical_sma200"))
    above_sma200 = close is not None and sma200 is not None and close > sma200
    research_trend_compatible = trend_transition["trend_transition_state"] in {
        "COMPATIBLE",
        "TRANSITIONAL",
    }
    research_trend_reason = trend_reason
    if (
        not research_trend_compatible
        and readiness_state == "FORMING"
        and research_setup_type == "MACD_MOMENTUM"
        and float(trend_score) >= 0.60
        and above_sma200
    ):
        research_trend_compatible = True
        research_trend_reason = "macd_momentum_forming_research_trend_above_0_60"
    liquidity_core_pass = bool(
        liquidity.get("liquidity_core_pass", liquidity.get("liquidity_pass", False))
    )
    liquidity_score = _safe_float(liquidity.get("liquidity_score"), 0.0) or 0.0
    rr = _safe_float(rr_data.get("rr"))
    min_rr = float(config.get("risk_reward", {}).get("min_rr_absolute", 1.5))
    rr_valid_value = rr_data.get("rr_valid")
    rr_valid = (
        bool(rr_valid_value)
        if rr_valid_value is not None
        else rr is not None and rr >= min_rr
    )
    extension_status = _safe_text(extension.get("ema20_extension_status"), "UNKNOWN").upper()
    extension_risk = _safe_float(extension.get("ema20_extension_risk"), 1.0) or 0.0
    setup_actionable = setup_type in VALID_SETUP_TYPES
    ema20_pct = _safe_float(evidence_with_trigger.get("technical_distance_ema20_pct"))
    ema20_atr = _safe_float(evidence_with_trigger.get("technical_distance_ema20_atr"))
    caution_mild = bool(
        extension_status == "CAUTION"
        and ema20_pct is not None
        and ema20_atr is not None
        and max(0.0, ema20_pct) <= 0.04
        and max(0.0, ema20_atr) <= 1.25
    )
    setup_research_eligible = bool(
        readiness_state == "FORMING"
        or (readiness_state == "CONFIRMED" and setup_actionable)
    )
    operational_conditions_met = bool(
        setup_actionable
        and readiness_state == "CONFIRMED"
        and trend_compatibility == "COMPATIBLE"
        and extension_status == "HEALTHY"
        and rr_valid
    )

    momentum_quality = _momentum_component(evidence)
    setup_quality = max(
        float(structure.get("structure_score", 0.0) or 0.0),
        float(readiness.get("setup_readiness_score", 0.0) or 0.0) / 100.0,
    )
    opportunity_scores = calculate_opportunity_scores(
        setup_quality=setup_quality,
        momentum_quality=momentum_quality,
        trend_compatibility=float(trend_transition["trend_transition_score"]) / 100.0,
        extension_risk=extension_risk,
        liquidity_quality=min(max(liquidity_score, 0.0), 1.0),
        rr_quality=float(rr_data.get("rr_score", 0.0) or 0.0),
        data_confidence=1.0 if evidence.get("evidence_available", True) else 0.0,
        context_confidence=0.5,
    )
    decision_lane, decision_reasons = classify_decision_lane(
        liquidity_pass=liquidity_core_pass,
        evidence_available=bool(evidence.get("evidence_available", True)),
        explicit_deceleration=explicit_deceleration,
        momentum_operable=momentum_operable,
        setup_state=readiness_state if setup_research_eligible else "NONE",
        operational_conditions_met=operational_conditions_met,
        extension_status=extension_status,
        extension_risk=extension_risk,
        research_priority_score=float(opportunity_scores["research_priority_score"]),
        reset_watch_score=float(opportunity_scores["reset_watch_score"]),
        config=config,
    )
    lane = legacy_lane_for_decision(
        decision_lane,
        explicit_deceleration=explicit_deceleration,
    )
    reasons = list(decision_reasons)
    if explicit_deceleration:
        reasons = []
        if daily_state in DECELERATING_TRAJECTORY_STATES:
            reasons.append(f"daily_macd_{daily_state.lower()}")
        if weekly_state in DECELERATING_TRAJECTORY_STATES:
            reasons.append(f"weekly_macd_{weekly_state.lower()}")
    elif decision_lane == "TACTICAL_RESEARCH":
        if readiness_state == "FORMING":
            reasons.append("high_quality_setup_forming")
        if extension_status == "CAUTION":
            reasons.append("adaptive_ema20_caution")
        if not rr_valid:
            reasons.append("rr_diagnostic_not_operational")
        if not research_trend_compatible:
            reasons.append(trend_reason)

    deep_analysis_tier = (
        "OPERATIONAL"
        if lane == "ADVANCE_DEEP_ANALYSIS"
        else "RESEARCH"
        if lane == "ADVANCE_RESEARCH_ANALYSIS"
        else "NONE"
    )
    operational_eligibility = lane == "ADVANCE_DEEP_ANALYSIS"
    research_eligibility_reason = (
        "; ".join(reasons) if deep_analysis_tier == "RESEARCH" else ""
    )

    momentum_gate_status = (
        "PASS"
        if momentum_operable
        else "REJECT"
        if explicit_deceleration
        else "MONITOR"
    )
    timing_gate_status = (
        "PASS"
        if extension_status == "HEALTHY"
        else "MONITOR"
        if extension_status in {"CAUTION", "UNKNOWN"}
        else "REJECT"
    )
    core_liquidity_status = "PASS" if liquidity_core_pass else "FAIL"

    opportunity_score = 100.0 * (
        0.30 * _momentum_component(evidence)
        + 0.25
        * max(
            float(structure.get("structure_score", 0.0) or 0.0),
            float(readiness.get("setup_readiness_score", 0.0) or 0.0) / 100.0,
        )
        + 0.15 * (float(trend_transition["trend_transition_score"]) / 100.0)
        + 0.15 * (1.0 - extension_risk)
        + 0.10 * min(max(liquidity_score, 0.0), 1.0)
        + 0.05 * float(rr_data.get("rr_score", 0.0) or 0.0)
    )

    return {
        **evidence_with_trigger,
        **extension,
        **readiness,
        **hypotheses,
        **trend_transition,
        **opportunity_scores,
        "technical_opportunity_score": round(max(0.0, min(100.0, opportunity_score)), 2),
        "technical_analysis_lane": lane,
        "decision_lane": decision_lane,
        "decision_reasons": "; ".join(reasons),
        "deep_analysis_tier": deep_analysis_tier,
        "operational_eligibility": operational_eligibility,
        "research_eligibility_reason": research_eligibility_reason,
        "research_setup_type": research_setup_type,
        "research_rr_data": research_rr_data,
        "ema20_caution_mild": caution_mild,
        "entry_zone_low": (
            min(
                value
                for value in [
                    _safe_float(structure.get("trigger_level")),
                    _safe_float(rr_data.get("entry")),
                ]
                if value is not None
            )
            if any(
                value is not None
                for value in [
                    _safe_float(structure.get("trigger_level")),
                    _safe_float(rr_data.get("entry")),
                ]
            )
            else None
        ),
        "entry_zone_high": _safe_float(rr_data.get("entry")),
        "required_confirmations": (
            "live_quote_and_execution_review"
            if decision_lane == "EXECUTION_CANDIDATE"
            else "setup_trigger_and_timing_confirmation"
            if decision_lane == "TACTICAL_RESEARCH"
            else "pullback_or_consolidation_reset"
            if decision_lane == "LEADERSHIP_RESET_WATCH"
            else "daily_and_weekly_macd_resume_improvement"
            if decision_lane == "MOMENTUM_RECOVERY_WATCH"
            else "new_technical_evidence"
        ),
        "invalidation_conditions": (
            "structural_stop_or_setup_failure"
            if decision_lane in {"EXECUTION_CANDIDATE", "TACTICAL_RESEARCH"}
            else "thesis_not_actionable"
        ),
        "technical_eligibility_reason": "; ".join(reasons),
        "trend_setup_compatibility": trend_compatibility,
        "trend_setup_compatibility_reason": trend_reason,
        "research_trend_compatibility": (
            "COMPATIBLE" if research_trend_compatible else "INCOMPATIBLE"
        ),
        "research_trend_compatibility_reason": research_trend_reason,
        "momentum_gate_status": momentum_gate_status,
        "timing_gate_status": timing_gate_status,
        "core_liquidity_status": core_liquidity_status,
        "daily_macd_operable": daily_operable,
        "weekly_macd_operable": weekly_operable,
        "daily_macd_non_decelerating": daily_operable,
        "weekly_macd_non_decelerating": weekly_operable,
        "trend_score": float(trend_score),
        "trend_status": trend_status,
        "structure": structure,
        "rr_data": rr_data,
        "setup_type": setup_type,
        "trigger_confirmed": bool(structure.get("trigger_confirmed", False)),
        "trigger_level": structure.get("trigger_level"),
        "rr": rr,
        "rr_valid": rr_valid,
        "rr_status": rr_data.get("rr_status", "VALIDATED" if rr_valid else "DIAGNOSTIC_ONLY"),
        "rr_confidence": rr_data.get("rr_confidence", "HIGH" if rr_valid else "LOW"),
        "target_validation_source": rr_data.get("target_validation_source", "LEGACY"),
        "technical_assessment_version": "INSTITUTIONAL_OPPORTUNITY_V2",
    }
