from __future__ import annotations

from scoring.final_score import calculate_final_score


def test_final_score_all_components_full_equals_100():
    cfg = {
        "scoring_weights": {
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
    }
    scores = {
        "rs_score": 1,
        "trend_score": 1,
        "market_regime_score": 1,
        "volume_score": 1,
        "sector_score": 1,
        "structure_score": 1,
        "rr_score": 1,
        "liquidity_score": 1,
        "momentum_score": 1,
        "options_score": 1,
        "fundamental_score": 1,
        "sentiment_score": 1,
    }

    assert abs(calculate_final_score(scores, cfg) - 100.0) < 0.01


def test_final_score_clips_components_to_0_1():
    cfg = {"scoring_weights": {"relative_strength": 100}}
    assert calculate_final_score({"rs_score": 2.5}, cfg) == 100.0
    assert calculate_final_score({"rs_score": -1.0}, cfg) == 0.0
