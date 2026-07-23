from __future__ import annotations

from scoring.options_score import score_options_flow

CONFIG = {
    "options_flow": {
        "enabled": True,
        "min_total_option_volume": 100,
        "min_total_option_open_interest": 1000,
        "extreme_bullish_put_call_below": 0.35,
        "weights": {
            "put_call_volume_ratio": 0.25,
            "call_volume_share": 0.20,
            "near_call_oi_share": 0.20,
            "call_wall_position": 0.15,
            "iv_risk": 0.10,
            "options_liquidity": 0.10,
        },
    }
}


def test_options_no_data_is_unknown():
    result = score_options_flow({"options_data_available": False, "options_warning": "missing"}, 100, CONFIG)
    assert result["options_score"] == 0.5
    assert result["options_bias"] == "UNKNOWN_OPTIONS_FLOW"
    assert result["options_confidence"] == "UNKNOWN"
    assert result["options_data_available"] is False


def test_options_bullish_case():
    metrics = {
        "options_data_available": True,
        "put_call_volume_ratio": 0.55,
        "call_volume_share": 0.72,
        "near_call_oi_share": 0.70,
        "max_call_oi_strike": 105,
        "atm_implied_volatility": 0.35,
        "total_option_volume": 5000,
        "total_option_open_interest": 50000,
        "options_warning": "",
    }
    result = score_options_flow(metrics, 100, CONFIG)
    assert result["options_score"] >= 0.65
    assert result["options_bias"] == "BULLISH_WITH_DATA"


def test_extremely_low_put_call_sets_crowded_warning():
    metrics = {
        "options_data_available": True,
        "put_call_volume_ratio": 0.20,
        "call_volume_share": 0.85,
        "near_call_oi_share": 0.80,
        "max_call_oi_strike": 105,
        "atm_implied_volatility": 0.35,
        "total_option_volume": 5000,
        "total_option_open_interest": 50000,
        "options_warning": "",
    }
    result = score_options_flow(metrics, 100, CONFIG)
    assert result["options_crowded_bullish"] is True
    assert result["options_bias"] == "CROWDED_BULLISH"
    assert "crowded trade" in result["options_warning"]
