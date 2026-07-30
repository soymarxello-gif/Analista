from __future__ import annotations

import pandas as pd
import pytest

from engine import technical_assessment


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "close": [100.0, 101.0, 102.0],
            "volume": [1_000_000, 1_100_000, 1_200_000],
        }
    )


def _evidence(**overrides) -> dict:
    data = {
        "technical_close": 102.0,
        "technical_atr": 2.0,
        "technical_sma200": 90.0,
        "daily_macd_trajectory_state": "ACCELERATING",
        "weekly_macd_trajectory_state": "IMPROVING_STEADY",
        "momentum_acceleration_score": 80.0,
        "momentum_persistence_score": 80.0,
    }
    data.update(overrides)
    return data


def _install_components(
    monkeypatch,
    *,
    setup_type: str = "BREAKOUT",
    trend_score: float = 0.80,
    rr: float = 2.0,
    extension_status: str = "HEALTHY",
) -> None:
    monkeypatch.setattr(
        technical_assessment,
        "score_structure",
        lambda df, config: {
            "setup_type": setup_type,
            "structure_score": 0.80,
            "trigger_level": 100.0,
            "trigger_confirmed": False,
        },
    )
    monkeypatch.setattr(
        technical_assessment,
        "score_trend",
        lambda df, config: (trend_score, "TREND"),
    )
    monkeypatch.setattr(
        technical_assessment,
        "score_risk_reward",
        lambda df, structure, config: {"rr": rr, "rr_score": min(rr / 3.0, 1.0)},
    )
    monkeypatch.setattr(
        technical_assessment,
        "calculate_extension_risk",
        lambda evidence, setup: {
            "ema20_extension_status": extension_status,
            "ema20_extension_risk": 0.10 if extension_status == "HEALTHY" else 0.55,
            "ema20_extension_reasons": [],
        },
    )


def _evaluate(monkeypatch, **component_overrides) -> dict:
    _install_components(monkeypatch, **component_overrides)
    return technical_assessment.evaluate_technical_opportunity(
        _frame(),
        {"risk_reward": {"min_rr_absolute": 1.5}},
        liquidity={"liquidity_core_pass": True, "liquidity_score": 0.90},
        evidence=_evidence(),
    )


def test_clean_multitimeframe_setup_advances(monkeypatch) -> None:
    result = _evaluate(monkeypatch)

    assert result["technical_analysis_lane"] == "ADVANCE_DEEP_ANALYSIS"
    assert result["daily_macd_operable"] is True
    assert result["weekly_macd_operable"] is True
    assert 0.0 <= result["technical_opportunity_score"] <= 100.0


@pytest.mark.parametrize(
    ("field", "state", "reason"),
    [
        (
            "daily_macd_trajectory_state",
            "IMPROVING_BUT_DECELERATING",
            "daily_macd_improving_but_decelerating",
        ),
        ("weekly_macd_trajectory_state", "DECLINING", "weekly_macd_declining"),
    ],
)
def test_explicit_macd_deceleration_is_rejected(
    monkeypatch, field: str, state: str, reason: str
) -> None:
    _install_components(monkeypatch)
    result = technical_assessment.evaluate_technical_opportunity(
        _frame(),
        {"risk_reward": {"min_rr_absolute": 1.5}},
        liquidity={"liquidity_core_pass": True, "liquidity_score": 0.90},
        evidence=_evidence(**{field: state}),
    )

    assert result["technical_analysis_lane"] == "REJECT_MOMENTUM"
    assert reason in result["technical_eligibility_reason"]


@pytest.mark.parametrize("state", ["FLAT_NO_EDGE", "NOISY", "UNKNOWN"])
def test_unconfirmed_momentum_stays_in_radar(monkeypatch, state: str) -> None:
    _install_components(monkeypatch)
    result = technical_assessment.evaluate_technical_opportunity(
        _frame(),
        {"risk_reward": {"min_rr_absolute": 1.5}},
        liquidity={"liquidity_core_pass": True, "liquidity_score": 0.90},
        evidence=_evidence(daily_macd_trajectory_state=state),
    )

    assert result["technical_analysis_lane"] == "RADAR_FORMING_SETUP"
    assert result["momentum_gate_status"] == "MONITOR"


def test_high_quality_forming_setup_advances_to_research_only(monkeypatch) -> None:
    result = _evaluate(monkeypatch, setup_type="NO_VALID_SETUP")

    assert result["technical_analysis_lane"] == "ADVANCE_RESEARCH_ANALYSIS"
    assert result["deep_analysis_tier"] == "RESEARCH"
    assert result["operational_eligibility"] is False
    assert result["setup_readiness_state"] == "FORMING"


def test_setup_specific_trend_compatibility(monkeypatch) -> None:
    pullback = _evaluate(monkeypatch, setup_type="PULLBACK", trend_score=0.61)
    reclaim = _evaluate(monkeypatch, setup_type="RECLAIM", trend_score=0.46)

    assert pullback["technical_analysis_lane"] == "ADVANCE_DEEP_ANALYSIS"
    assert reclaim["technical_analysis_lane"] == "ADVANCE_DEEP_ANALYSIS"


def test_rr_diagnostic_is_research_but_core_liquidity_remains_a_risk_gate(monkeypatch) -> None:
    low_rr = _evaluate(monkeypatch, rr=1.49)
    _install_components(monkeypatch)
    thin = technical_assessment.evaluate_technical_opportunity(
        _frame(),
        {"risk_reward": {"min_rr_absolute": 1.5}},
        liquidity={"liquidity_core_pass": False, "liquidity_score": 0.20},
        evidence=_evidence(),
    )

    assert low_rr["technical_analysis_lane"] == "ADVANCE_RESEARCH_ANALYSIS"
    assert low_rr["operational_eligibility"] is False
    assert thin["technical_analysis_lane"] == "REJECT_RISK"


def test_caution_can_advance_to_research_but_never_operational(monkeypatch) -> None:
    result = _evaluate(monkeypatch, extension_status="CAUTION")

    assert result["technical_analysis_lane"] == "ADVANCE_RESEARCH_ANALYSIS"
    assert result["decision_lane"] == "TACTICAL_RESEARCH"
    assert result["operational_eligibility"] is False
    assert result["timing_gate_status"] == "MONITOR"
