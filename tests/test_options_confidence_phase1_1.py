from scoring.options_score import score_options_flow


CONFIG = {
    "options_flow": {
        "enabled": True,
        "medium_total_option_volume": 300,
        "medium_total_option_open_interest": 1000,
        "high_total_option_volume": 1000,
        "high_total_option_open_interest": 5000,
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


def base_metrics(total_volume, total_oi):
    return {
        "options_data_available": True,
        "put_call_volume_ratio": 0.55,
        "call_volume_share": 0.70,
        "near_call_oi_share": 0.70,
        "max_call_oi_strike": 105,
        "atm_implied_volatility": 0.35,
        "total_option_volume": total_volume,
        "total_option_open_interest": total_oi,
        "options_warning": "",
    }


def test_high_options_confidence_requires_volume_and_oi():
    result = score_options_flow(base_metrics(1500, 7000), 100, CONFIG)
    assert result["options_confidence"] == "HIGH"


def test_medium_options_confidence():
    result = score_options_flow(base_metrics(500, 2000), 100, CONFIG)
    assert result["options_confidence"] == "MEDIUM"


def test_low_options_confidence():
    result = score_options_flow(base_metrics(100, 500), 100, CONFIG)
    assert result["options_confidence"] == "LOW"
