from __future__ import annotations

import pytest

from scoring.final_score import calculate_final_score


WEIGHTS = {
    "relative_strength": 11.4,
    "trend": 11.0,
    "market_regime": 10.7,
    "volume_accumulation": 10.3,
    "sector_rotation": 9.5,
    "structure_trigger": 9.0,
    "risk_reward_atr": 8.4,
    "liquidity": 7.6,
    "momentum": 6.9,
    "options_flow": 6.1,
    "fundamentals": 5.1,
    "sentiment": 4.0,
}

FULL_SCORES = {
    "rs_score": 1.0,
    "trend_score": 1.0,
    "market_regime_score": 1.0,
    "volume_score": 1.0,
    "sector_score": 1.0,
    "structure_score": 1.0,
    "rr_score": 1.0,
    "liquidity_score": 1.0,
    "momentum_score": 1.0,
    "options_score": 1.0,
    "fundamental_score": 1.0,
    "sentiment_score": 1.0,
}


def test_final_score_all_components_full_equals_100():
    result = calculate_final_score(FULL_SCORES, {"scoring_weights": WEIGHTS})
    assert result == pytest.approx(100.0, abs=1e-9)


def test_final_score_clips_components_to_0_1():
    cfg = {"scoring_weights": {"relative_strength": 100.0}}
    assert calculate_final_score({"rs_score": 2.5}, cfg) == pytest.approx(100.0)
    assert calculate_final_score({"rs_score": -1.0}, cfg) == pytest.approx(0.0)
