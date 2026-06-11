from __future__ import annotations

from scoring.final_score import calculate_trade_score_breakdown


def base_scores() -> dict:
    return {
        "rs_score": 0.80,
        "trend_score": 0.85,
        "liquidity_score": 0.90,
        "momentum_score": 0.75,
        "fundamental_score": 0.65,
        "structure_score": 0.82,
        "rr_score": 0.80,
        "volume_score": 0.70,
        "market_regime_score": 0.60,
        "sector_score": 0.70,
        "options_score": 0.50,
        "sentiment_score": 0.50,
    }


def test_trade_score_breakdown_returns_expected_fields():
    result = calculate_trade_score_breakdown(
        base_scores(),
        {"setup_type": "PULLBACK", "trigger_confirmed": True},
    )

    assert "asset_quality_score" in result
    assert "setup_quality_score" in result
    assert "context_score" in result
    assert "institutional_score" in result
    assert "final_trade_score" in result
    assert "score_breakdown_json" in result


def test_no_valid_setup_caps_final_trade_score():
    scores = base_scores()
    scores["structure_score"] = 0.25

    result = calculate_trade_score_breakdown(
        scores,
        {"setup_type": "NO_VALID_SETUP", "trigger_confirmed": False},
    )

    assert result["final_trade_score"] <= 49


def test_asset_quality_can_be_high_while_setup_quality_is_low():
    scores = base_scores()
    scores["trend_score"] = 0.95
    scores["rs_score"] = 0.95
    scores["liquidity_score"] = 0.95
    scores["momentum_score"] = 0.90
    scores["fundamental_score"] = 0.80

    scores["structure_score"] = 0.25
    scores["rr_score"] = 0.20
    scores["volume_score"] = 0.40

    result = calculate_trade_score_breakdown(
        scores,
        {"setup_type": "NO_VALID_SETUP", "trigger_confirmed": False},
    )

    assert result["asset_quality_score"] > result["setup_quality_score"]
    assert result["final_trade_score"] <= 49


def test_final_trade_score_prioritizes_setup_quality():
    good_asset_bad_setup = base_scores()
    good_asset_bad_setup.update(
        {
            "trend_score": 0.95,
            "rs_score": 0.95,
            "liquidity_score": 0.95,
            "momentum_score": 0.90,
            "structure_score": 0.30,
            "rr_score": 0.30,
            "volume_score": 0.40,
        }
    )

    weaker_asset_good_setup = base_scores()
    weaker_asset_good_setup.update(
        {
            "trend_score": 0.60,
            "rs_score": 0.60,
            "liquidity_score": 0.70,
            "momentum_score": 0.55,
            "structure_score": 0.90,
            "rr_score": 0.90,
            "volume_score": 0.85,
        }
    )

    bad_setup_result = calculate_trade_score_breakdown(
        good_asset_bad_setup,
        {"setup_type": "PULLBACK", "trigger_confirmed": True},
    )

    good_setup_result = calculate_trade_score_breakdown(
        weaker_asset_good_setup,
        {"setup_type": "PULLBACK", "trigger_confirmed": True},
    )

    assert good_setup_result["setup_quality_score"] > bad_setup_result["setup_quality_score"]
    assert good_setup_result["final_trade_score"] > bad_setup_result["final_trade_score"]