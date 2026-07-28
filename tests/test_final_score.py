from __future__ import annotations

from scoring.final_score import calculate_final_score, calculate_trade_score_breakdown


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


def test_options_score_is_not_part_of_final_score_until_data_is_reliable():
    cfg = {
        "scoring_weights": {
            "relative_strength": 50,
            "trend": 40,
            "options_flow": 10,
        }
    }
    base = {"rs_score": 0.8, "trend_score": 0.7, "options_score": 0.0}
    high_options = dict(base, options_score=1.0)

    assert calculate_final_score(base, cfg) == calculate_final_score(high_options, cfg)


def test_options_score_is_not_part_of_trade_score_breakdown_until_data_is_reliable():
    scores = {
        "trend_score": 0.80,
        "rs_score": 0.80,
        "liquidity_score": 0.80,
        "momentum_score": 0.80,
        "fundamental_score": 0.70,
        "structure_score": 0.80,
        "rr_score": 0.80,
        "volume_score": 0.75,
        "market_regime_score": 0.60,
        "sector_score": 0.60,
        "sentiment_score": 0.50,
    }

    low_options = calculate_trade_score_breakdown(
        dict(scores, options_score=0.0),
        {"setup_type": "PULLBACK", "trigger_confirmed": True},
    )
    high_options = calculate_trade_score_breakdown(
        dict(scores, options_score=1.0),
        {"setup_type": "PULLBACK", "trigger_confirmed": True},
    )

    assert low_options["institutional_score"] == high_options["institutional_score"]
    assert low_options["final_trade_score"] == high_options["final_trade_score"]
