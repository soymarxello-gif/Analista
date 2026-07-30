from __future__ import annotations

import json

import numpy as np
import pandas as pd

from engine.opportunity_model import (
    build_extension_distribution_features,
    calculate_opportunity_scores,
    classify_decision_lane,
)
from scoring import setup_hypotheses
from scoring.risk_reward_score import score_risk_reward
from tools.simple_candidate_posttest import select_shadow_research_candidates


def _history(periods: int = 120) -> pd.DataFrame:
    index = pd.bdate_range("2026-01-05", periods=periods)
    close = pd.Series(np.linspace(80.0, 100.0, periods), index=index)
    return pd.DataFrame(
        {
            "open": close - 0.4,
            "high": close + 0.5,
            "low": close - 0.8,
            "close": close,
            "volume": 1_000_000.0,
            "ema20": close - 1.5,
            "ma20": close - 1.5,
            "ma50": close - 3.0,
            "atr": 2.0,
        },
        index=index,
    )


def test_setup_hypotheses_choose_best_evidence_not_first_detector(monkeypatch) -> None:
    monkeypatch.setattr(
        setup_hypotheses,
        "detect_breakout",
        lambda df, config: {"is_breakout": True, "breakout_level": 99.0},
    )
    monkeypatch.setattr(
        setup_hypotheses,
        "detect_macd_momentum",
        lambda df, config: {
            "is_macd_momentum": True,
            "macd_momentum_level": 100.0,
        },
    )
    result = setup_hypotheses.evaluate_setup_hypotheses(
        _history(),
        {},
        legacy_structure={
            "setup_type": "BREAKOUT",
            "structure_score": 0.60,
            "trigger_level": 99.0,
        },
        readiness={
            "setup_readiness_components": json.dumps(
                {
                    "BREAKOUT": 60.0,
                    "PULLBACK": 45.0,
                    "RECLAIM": 40.0,
                    "MACD_MOMENTUM": 91.0,
                }
            )
        },
    )

    assert result["primary_setup_hypothesis"] == "MACD_MOMENTUM"
    assert result["setup_hypothesis_count"] >= 2
    assert "BREAKOUT" in result["alternative_setup_hypotheses"]


def test_extension_percentile_is_signed_and_below_ema_is_not_extended() -> None:
    frame = _history()
    frame.loc[frame.index[-1], "close"] = frame.loc[frame.index[-1], "ema20"] - 1.0
    result = build_extension_distribution_features(frame, {})

    assert result["ema20_distance_percentile_1y"] == 0.0


def test_opportunity_scores_separate_quality_entry_and_reset() -> None:
    result = calculate_opportunity_scores(
        setup_quality=0.90,
        momentum_quality=0.90,
        trend_compatibility=0.85,
        extension_risk=0.80,
        liquidity_quality=0.90,
        rr_quality=0.70,
    )

    assert result["technical_asset_quality_score"] > result["entry_readiness_score"]
    assert result["reset_watch_score"] >= 80


def test_high_quality_extended_candidate_goes_to_reset_watch() -> None:
    lane, reasons = classify_decision_lane(
        liquidity_pass=True,
        evidence_available=True,
        explicit_deceleration=False,
        momentum_operable=True,
        setup_state="CONFIRMED",
        operational_conditions_met=False,
        extension_status="OVEREXTENDED",
        extension_risk=0.70,
        research_priority_score=82.0,
        reset_watch_score=88.0,
        config={},
    )

    assert lane == "LEADERSHIP_RESET_WATCH"
    assert reasons == ["high_quality_leader_waiting_reset"]


def test_macd_deceleration_never_enters_execution_or_tactical_research() -> None:
    lane, _ = classify_decision_lane(
        liquidity_pass=True,
        evidence_available=True,
        explicit_deceleration=True,
        momentum_operable=False,
        setup_state="CONFIRMED",
        operational_conditions_met=False,
        extension_status="HEALTHY",
        extension_risk=0.10,
        research_priority_score=95.0,
        reset_watch_score=95.0,
        config={},
    )

    assert lane == "MOMENTUM_RECOVERY_WATCH"


def test_model_target_confluence_can_validate_rr_without_overhead_resistance() -> None:
    frame = _history()
    frame.loc[frame.index[-20], "low"] = 88.0
    result = score_risk_reward(
        frame,
        {
            "setup_type": "MACD_MOMENTUM",
            "trigger_level": 100.0,
        },
        {
            "risk_reward": {
                "atr_stop_multiplier": 1.5,
                "min_rr_absolute": 1.5,
                "model_confluence_tolerance_pct": 0.25,
            }
        },
    )

    assert result["target_validation_source"] == "MODEL_CONFLUENCE"
    assert result["rr_status"] == "VALIDATED"
    assert result["rr_confidence"] == "MEDIUM"
    assert len(json.loads(result["target_candidates"])) >= 3


def test_shadow_cohort_keeps_only_clean_tactical_research() -> None:
    frame = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "decision_lane": "TACTICAL_RESEARCH",
                "daily_macd_trajectory_state": "ACCELERATING",
                "weekly_macd_trajectory_state": "IMPROVING_STEADY",
                "ema20_extension_status": "CAUTION",
                "shadow_entry": 100.0,
                "shadow_stop": 95.0,
                "shadow_target": 110.0,
                "research_priority_score": 85.0,
            },
            {
                "ticker": "BBB",
                "decision_lane": "LEADERSHIP_RESET_WATCH",
                "daily_macd_trajectory_state": "ACCELERATING",
                "weekly_macd_trajectory_state": "ACCELERATING",
                "ema20_extension_status": "OVEREXTENDED",
                "shadow_entry": 100.0,
                "shadow_stop": 95.0,
                "shadow_target": 110.0,
                "research_priority_score": 95.0,
            },
        ]
    )

    selected = select_shadow_research_candidates(frame)

    assert selected["ticker"].tolist() == ["AAA"]
