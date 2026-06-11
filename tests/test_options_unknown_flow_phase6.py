from __future__ import annotations

from scoring.options_score import score_options_flow


def enabled_config() -> dict:
    return {
        "options_flow": {
            "enabled": True,
            "medium_total_option_volume": 300,
            "medium_total_option_open_interest": 1000,
            "high_total_option_volume": 1000,
            "high_total_option_open_interest": 5000,
            "extreme_bullish_put_call_below": 0.35,
            "extreme_bearish_put_call_above": 1.80,
            "crowded_bullish_score_cap": 0.60,
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


def test_disabled_options_are_unknown_not_neutral():
    result = score_options_flow({}, 100, {"options_flow": {"enabled": False}})

    assert result["options_bias"] == "UNKNOWN_OPTIONS_FLOW"
    assert result["options_confidence"] == "UNKNOWN"
    assert result["options_score"] == 0.5


def test_missing_options_data_are_unknown_not_neutral():
    result = score_options_flow(
        {"options_data_available": False, "options_warning": "sin datos"},
        100,
        enabled_config(),
    )

    assert result["options_bias"] == "UNKNOWN_OPTIONS_FLOW"
    assert result["options_confidence"] == "UNKNOWN"
    assert result["options_score"] == 0.5


def test_neutral_with_data_is_distinct_from_unknown():
    metrics = {
        "options_data_available": True,
        "put_call_volume_ratio": 1.1,
        "call_volume_share": 0.50,
        "near_call_oi_share": 0.50,
        "max_call_oi_strike": 110,
        "atm_implied_volatility": 0.45,
        "total_option_volume": 500,
        "total_option_open_interest": 1500,
    }

    result = score_options_flow(metrics, 100, enabled_config())

    assert result["options_bias"] in {
        "NEUTRAL_WITH_DATA",
        "BULLISH_WITH_DATA",
        "BEARISH_WITH_DATA",
        "CROWDED_BULLISH",
        "CROWDED_BEARISH",
    }
    assert result["options_bias"] != "UNKNOWN_OPTIONS_FLOW"
    assert result["options_confidence"] in {"LOW", "MEDIUM", "HIGH"}


def test_crowded_bullish_is_not_clean_bullish():
    metrics = {
        "options_data_available": True,
        "put_call_volume_ratio": 0.20,
        "call_volume_share": 0.90,
        "near_call_oi_share": 0.90,
        "max_call_oi_strike": 110,
        "atm_implied_volatility": 0.40,
        "total_option_volume": 5000,
        "total_option_open_interest": 20000,
    }

    result = score_options_flow(metrics, 100, enabled_config())

    assert result["options_bias"] == "CROWDED_BULLISH"
    assert result["options_bias"] != "BULLISH_WITH_DATA"
    assert result["options_crowded_bullish"] is True
    assert result["options_score"] <= 0.60


def test_crowded_bearish_is_labeled():
    metrics = {
        "options_data_available": True,
        "put_call_volume_ratio": 2.20,
        "call_volume_share": 0.20,
        "near_call_oi_share": 0.20,
        "max_call_oi_strike": 95,
        "atm_implied_volatility": 0.80,
        "total_option_volume": 5000,
        "total_option_open_interest": 20000,
    }

    result = score_options_flow(metrics, 100, enabled_config())

    assert result["options_bias"] == "CROWDED_BEARISH"
    assert result["options_crowded_bearish"] is True
    assert 0 <= result["options_score"] <= 1