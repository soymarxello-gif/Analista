from scoring.options_score import score_options_flow

CONFIG = {
    "options_flow": {
        "enabled": True,
        "medium_total_option_volume": 300,
        "medium_total_option_open_interest": 1000,
        "high_total_option_volume": 1000,
        "high_total_option_open_interest": 5000,
        "extreme_bullish_put_call_below": 0.35,
        "crowded_bullish_score_cap": 0.60,
        "crowded_bullish_bias": "NEUTRAL_CROWDED",
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


def test_crowded_call_flow_caps_score_and_bias():
    metrics = {
        "options_data_available": True,
        "put_call_volume_ratio": 0.15,
        "call_volume_share": 0.90,
        "near_call_oi_share": 0.95,
        "max_call_oi_strike": 105,
        "atm_implied_volatility": 0.35,
        "total_option_volume": 5000,
        "total_option_open_interest": 50000,
        "options_warning": "",
    }

    result = score_options_flow(metrics, 100, CONFIG)

    assert result["options_crowded_bullish"] is True
    assert result["options_score"] <= 0.60
    assert result["options_bias"] == "CROWDED_BULLISH"
