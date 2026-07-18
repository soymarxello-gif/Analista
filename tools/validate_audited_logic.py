from __future__ import annotations

import pandas as pd
import yaml

from engine.audit_postprocessor import normalize_scan
from scoring.final_score import calculate_final_score
from scoring.options_score import score_options_flow
from scoring.signal_classifier import classify_signal


SIGNAL_CONFIG = {
    "filters": {"min_price": 10, "min_market_cap_usd": 1_500_000_000},
    "risk_reward": {"min_rr_absolute": 1.5},
    "veto_rules": {"thresholds": {"min_trend_score": 0.55}},
    "signals": {
        "buy_setup_active_enabled": False,
        "allowed_states": ["VETO", "AVOID", "WATCHLIST", "READY_WAIT_TRIGGER", "TRIGGER_CONFIRMED"],
    },
    "signal_thresholds": {
        "trigger_confirmed": {"min_score": 80, "min_rr": 2.0},
        "ready_wait_trigger": {"min_score": 80, "min_rr": 1.7},
        "watchlist": {"min_score": 70},
    },
}

CONFIG = {
    **SIGNAL_CONFIG,
    "liquidity": {"max_spread_pct": 0.03, "max_quote_distance_pct": 0.15},
    "trade_score_weights": {
        "asset_quality": 0.25,
        "setup_quality": 0.40,
        "context": 0.25,
        "institutional": 0.10,
    },
    "ranking_audit": {"change_production_ranking": False},
}

OPTIONS_CONFIG = {
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


def candidate(**overrides):
    row = {
        "ticker": "TEST",
        "price": 100.0,
        "market_cap": 10_000_000_000,
        "quote_type": "EQUITY",
        "liquidity_pass": True,
        "bid": 99.95,
        "ask": 100.05,
        "trend_score": 0.9,
        "liquidity_score": 0.9,
        "fundamental_score": 0.8,
        "structure_score": 0.9,
        "rr_score": 0.9,
        "momentum_score": 0.8,
        "volume_score": 0.8,
        "rs_score": 0.9,
        "sector_score": 0.8,
        "options_score": 0.7,
        "options_data_available": True,
        "setup_type": "BREAKOUT",
        "trigger_confirmed": True,
        "rr": 3.0,
        "entry": 101.0,
        "stop": 97.0,
        "target": 113.0,
        "final_score": 88.0,
        "final_trade_score": 88.0,
        "earnings_veto": False,
        "execution_quote_quality": "HIGH",
    }
    row.update(overrides)
    return row


def validate_config() -> None:
    with open("config.yaml", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    assert config["filters"]["min_price"] == 10
    assert config["filters"]["min_market_cap_usd"] == 1_500_000_000
    assert config["signals"]["buy_setup_active_enabled"] is False
    assert "BUY_SETUP_ACTIVE" not in config["signals"]["allowed_states"]
    assert config["ranking_audit"]["change_production_ranking"] is False


def validate_final_score() -> None:
    weights = {
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
    assert calculate_final_score(scores, {"scoring_weights": weights}) == 100.0
    assert calculate_final_score({"rs_score": 2.5}, {"scoring_weights": {"relative_strength": 100}}) == 100.0
    assert calculate_final_score({"rs_score": -1}, {"scoring_weights": {"relative_strength": 100}}) == 0.0


def validate_signals() -> None:
    signal, reasons = classify_signal(candidate(liquidity_pass=False), SIGNAL_CONFIG)
    assert signal == "VETO" and "liquidity_fail" in reasons

    signal, reasons = classify_signal(candidate(setup_type="NO_VALID_SETUP"), SIGNAL_CONFIG)
    assert signal == "VETO" and "no_valid_setup" in reasons

    signal, _ = classify_signal(candidate(), SIGNAL_CONFIG)
    assert signal == "TRIGGER_CONFIRMED"

    signal, _ = classify_signal(candidate(execution_quote_quality="LOW"), SIGNAL_CONFIG)
    assert signal != "TRIGGER_CONFIRMED"

    signal, _ = classify_signal(candidate(trigger_confirmed=False, final_trade_score=82), SIGNAL_CONFIG)
    assert signal == "READY_WAIT_TRIGGER"

    signal, reasons = classify_signal(candidate(price=9.99, market_cap=1_000_000_000), SIGNAL_CONFIG)
    assert signal == "VETO"
    assert "price_below_min" in reasons and "market_cap_below_min" in reasons

    assert "BUY_SETUP_ACTIVE" not in {
        classify_signal(candidate(), SIGNAL_CONFIG)[0],
        classify_signal(candidate(trigger_confirmed=False), SIGNAL_CONFIG)[0],
    }


def validate_options() -> None:
    unknown = score_options_flow({"options_data_available": False, "options_warning": "missing"}, 100, OPTIONS_CONFIG)
    assert unknown["options_bias"] == "UNKNOWN_OPTIONS_FLOW"
    assert unknown["options_confidence"] == "UNKNOWN"

    bullish_metrics = {
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
    bullish = score_options_flow(bullish_metrics, 100, OPTIONS_CONFIG)
    assert bullish["options_score"] >= 0.65
    assert bullish["options_bias"] == "BULLISH_WITH_DATA"

    crowded_metrics = {**bullish_metrics, "put_call_volume_ratio": 0.20, "call_volume_share": 0.85}
    crowded = score_options_flow(crowded_metrics, 100, OPTIONS_CONFIG)
    assert crowded["options_crowded_bullish"] is True
    assert crowded["options_bias"] == "CROWDED_BULLISH"


def validate_postprocessor() -> None:
    invalid = normalize_scan(pd.DataFrame([candidate(bid=0, ask=0)]), CONFIG).iloc[0]
    assert invalid["execution_quote_quality"] == "LOW"
    assert invalid["signal"] != "TRIGGER_CONFIRMED"

    low_price = normalize_scan(pd.DataFrame([candidate(price=9.99)]), CONFIG).iloc[0]
    assert low_price["signal"] == "VETO"
    assert "price_below_min" in low_price["all_veto_reasons"]

    low_cap = normalize_scan(pd.DataFrame([candidate(market_cap=1_000_000_000)]), CONFIG).iloc[0]
    assert low_cap["signal"] == "VETO"
    assert "market_cap_below_min" in low_cap["all_veto_reasons"]

    confirmed = normalize_scan(pd.DataFrame([candidate()]), CONFIG).iloc[0]
    assert confirmed["signal"] == "TRIGGER_CONFIRMED"
    assert confirmed["rr"] >= 2.0

    invalid_setup = normalize_scan(pd.DataFrame([candidate(setup_type="NO_VALID_SETUP")]), CONFIG).iloc[0]
    assert invalid_setup["signal"] == "VETO"
    assert invalid_setup["final_trade_score"] <= 49
    assert pd.isna(invalid_setup["actionable_entry"])
    assert invalid_setup["theoretical_entry"] == 101.0

    ranking = normalize_scan(
        pd.DataFrame([candidate(ticker="A"), candidate(ticker="B", trigger_confirmed=False, final_score=75)]),
        CONFIG,
    )
    assert len(ranking) == 2
    assert {"legacy_rank", "trade_rank", "rank_delta"}.issubset(ranking.columns)
    assert "BUY_SETUP_ACTIVE" not in set(ranking["signal"])


def main() -> int:
    validate_config()
    validate_final_score()
    validate_signals()
    validate_options()
    validate_postprocessor()
    print("OK: audited logic validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
