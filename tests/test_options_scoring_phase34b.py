from __future__ import annotations

import json

from scoring.final_score import calculate_trade_score_breakdown
from scoring.options_score import calculate_options_score_adjustment
from scoring.signal_classifier import classify_signal


def _config() -> dict:
    return {
        "options_flow": {
            "max_score_adjustment": 0.08,
        },
        "signals": {
            "buy_setup_active_enabled": False,
            "allowed_states": [
                "VETO",
                "AVOID",
                "WATCHLIST",
                "READY_WAIT_TRIGGER",
                "TRIGGER_CONFIRMED",
            ],
        },
        "signal_thresholds": {
            "buy_setup_active": {"enabled": False, "min_score": 85, "min_rr": 2.0, "require_trigger": True},
            "trigger_confirmed": {"min_score": 85, "min_rr": 2.0, "require_trigger": True},
            "ready_wait_trigger": {"min_score": 80, "min_rr": 1.7, "require_trigger": False},
            "watchlist": {"min_score": 70},
        },
        "risk_reward": {"min_rr_absolute": 1.5},
        "veto_rules": {"thresholds": {"min_trend_score": 0.55}, "data_quality": {}},
        "filters": {"min_price": 10, "min_market_cap_usd": 1_500_000_000},
        "universe": {"allowed_quote_types": ["EQUITY", "ETF"]},
    }


def _options(**overrides) -> dict:
    data = {
        "options_score": 0.50,
        "options_bias": "NEUTRAL_WITH_DATA",
        "options_confidence": "HIGH",
        "options_liquidity_score": 0.90,
    }
    data.update(overrides)
    return data


def _signal_row(**overrides) -> dict:
    row = {
        "final_score": 90,
        "rr": 2.5,
        "trigger_confirmed": True,
        "price": 100,
        "market_cap": 5_000_000_000,
        "quote_type": "EQUITY",
        "liquidity_pass": True,
        "trend_score": 0.90,
        "setup_type": "BREAKOUT",
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
        "options_bias": "BULLISH_WITH_DATA",
        "options_confidence": "HIGH",
    }
    row.update(overrides)
    return row


def test_unknown_options_flow_is_neutral_or_tiny():
    result = calculate_options_score_adjustment(
        _options(options_bias="UNKNOWN_OPTIONS_FLOW", options_confidence="UNKNOWN"),
        _config(),
    )

    assert abs(result["options_score_adjustment"]) <= 0.005
    assert result["options_score_reason"] == "options_unknown"


def test_no_options_available_does_not_penalize_aggressively():
    result = calculate_options_score_adjustment(
        _options(options_bias="NO_OPTIONS_AVAILABLE", options_confidence="UNKNOWN"),
        _config(),
    )

    assert result["options_score_adjustment"] == 0.0
    assert result["options_score_reason"] == "options_not_listed_neutral"


def test_bullish_high_confidence_adds_moderate_positive_adjustment():
    result = calculate_options_score_adjustment(
        _options(options_bias="BULLISH_WITH_DATA", options_confidence="HIGH"),
        _config(),
    )

    assert 0 < result["options_score_adjustment"] <= 0.08
    assert result["options_score_adjusted"] > result["options_score_raw"]


def test_bearish_high_confidence_adds_moderate_negative_adjustment():
    result = calculate_options_score_adjustment(
        _options(options_bias="BEARISH_WITH_DATA", options_confidence="HIGH"),
        _config(),
    )

    assert -0.08 <= result["options_score_adjustment"] < 0
    assert result["options_score_adjusted"] < result["options_score_raw"]


def test_crowded_bullish_applies_contrarian_penalty():
    result = calculate_options_score_adjustment(
        _options(options_bias="CROWDED_BULLISH", options_confidence="HIGH"),
        _config(),
    )

    assert result["options_score_adjustment"] < 0
    assert result["options_contrarian_adjustment"] < 0
    assert result["options_score_reason"] == "crowded_bullish_contrarian"
    assert result["options_risk_flag"] == "crowded_bullish_contrarian"


def test_crowded_bearish_is_not_automatic_bearish():
    result = calculate_options_score_adjustment(
        _options(options_bias="CROWDED_BEARISH", options_confidence="HIGH"),
        _config(),
    )

    assert 0 <= result["options_score_adjustment"] <= 0.04
    assert result["options_contrarian_reason"] == "crowded_bearish_contrarian"
    assert result["options_risk_flag"] == ""


def test_low_confidence_reduces_adjustment_impact():
    high = calculate_options_score_adjustment(
        _options(options_bias="BULLISH_WITH_DATA", options_confidence="HIGH"),
        _config(),
    )
    low = calculate_options_score_adjustment(
        _options(options_bias="BULLISH_WITH_DATA", options_confidence="LOW"),
        _config(),
    )

    assert 0 < low["options_score_adjustment"] < high["options_score_adjustment"]


def test_low_liquidity_reduces_adjustment_impact():
    liquid = calculate_options_score_adjustment(
        _options(options_bias="BULLISH_WITH_DATA", options_liquidity_score=0.90),
        _config(),
    )
    illiquid = calculate_options_score_adjustment(
        _options(options_bias="BULLISH_WITH_DATA", options_liquidity_score=0.20),
        _config(),
    )

    assert 0 < illiquid["options_score_adjustment"] < liquid["options_score_adjustment"]


def test_score_breakdown_contains_options_adjustment():
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
        "options_score": 0.56,
        "sentiment_score": 0.50,
        "options_score_adjustment": 0.06,
        "options_score_reason": "options_bullish_moderate",
        "options_contrarian_adjustment": 0.0,
        "options_contrarian_reason": "",
        "options_risk_flag": "",
    }

    result = calculate_trade_score_breakdown(
        scores,
        {"setup_type": "PULLBACK", "trigger_confirmed": True},
    )
    breakdown = json.loads(result["score_breakdown_json"])

    assert breakdown["options_adjustment"]["options_score_adjustment"] == 0.06
    assert breakdown["options_adjustment"]["options_score_reason"] == "options_bullish_moderate"


def test_veto_stays_veto_even_when_options_are_bullish():
    signal, veto = classify_signal(
        _signal_row(liquidity_pass=False, options_bias="BULLISH_WITH_DATA"),
        _config(),
    )

    assert signal == "VETO"
    assert "liquidity_fail" in veto


def test_avoid_stays_avoid_even_when_options_are_bullish():
    signal, veto = classify_signal(
        _signal_row(
            final_score=65,
            trigger_confirmed=False,
            options_bias="BULLISH_WITH_DATA",
        ),
        _config(),
    )

    assert veto == []
    assert signal == "AVOID"


def test_trigger_confirmed_still_requires_valid_high_quality_quote():
    signal, veto = classify_signal(
        _signal_row(
            quote_status="MISSING",
            execution_quote_quality="LOW",
            options_bias="CROWDED_BEARISH",
            options_confidence="HIGH",
        ),
        _config(),
    )

    assert veto == []
    assert signal == "WATCHLIST"
    assert signal != "TRIGGER_CONFIRMED"
