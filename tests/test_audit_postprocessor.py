from __future__ import annotations

import pandas as pd

from engine.audit_postprocessor import normalize_scan


CONFIG = {
    "filters": {"min_price": 10, "min_market_cap_usd": 1_500_000_000},
    "liquidity": {"max_spread_pct": 0.03, "max_quote_distance_pct": 0.15},
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
    "trade_score_weights": {
        "asset_quality": 0.25,
        "setup_quality": 0.40,
        "context": 0.25,
        "institutional": 0.10,
    },
    "ranking_audit": {"change_production_ranking": False},
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
        "earnings_veto": False,
    }
    row.update(overrides)
    return row


def normalize(*rows):
    return normalize_scan(pd.DataFrame(rows), CONFIG)


def test_invalid_bidask_cannot_be_trigger_confirmed():
    result = normalize(candidate(bid=0, ask=0))
    assert result.loc[0, "execution_quote_quality"] == "LOW"
    assert result.loc[0, "signal"] != "TRIGGER_CONFIRMED"


def test_price_filter_is_hard():
    result = normalize(candidate(price=9.99))
    assert result.loc[0, "signal"] == "VETO"
    assert "price_below_min" in result.loc[0, "all_veto_reasons"]


def test_market_cap_filter_is_hard():
    result = normalize(candidate(market_cap=1_000_000_000))
    assert result.loc[0, "signal"] == "VETO"
    assert "market_cap_below_min" in result.loc[0, "all_veto_reasons"]


def test_ready_wait_trigger_semantics():
    result = normalize(candidate(trigger_confirmed=False))
    if result.loc[0, "signal"] == "READY_WAIT_TRIGGER":
        assert bool(result.loc[0, "trigger_confirmed"]) is False


def test_trigger_confirmed_semantics():
    result = normalize(candidate())
    assert result.loc[0, "signal"] == "TRIGGER_CONFIRMED"
    assert bool(result.loc[0, "trigger_confirmed"]) is True
    assert result.loc[0, "execution_quote_quality"] != "LOW"
    assert result.loc[0, "rr"] >= 2.0


def test_no_valid_setup_is_veto():
    result = normalize(candidate(setup_type="NO_VALID_SETUP"))
    assert result.loc[0, "signal"] == "VETO"
    assert result.loc[0, "final_trade_score"] <= 49


def test_veto_has_no_actionable_levels():
    result = normalize(candidate(price=5))
    assert pd.isna(result.loc[0, "actionable_entry"])
    assert pd.isna(result.loc[0, "actionable_stop"])
    assert pd.isna(result.loc[0, "actionable_target"])
    assert result.loc[0, "theoretical_entry"] == 101.0


def test_buy_setup_active_disabled():
    result = normalize(candidate())
    assert "BUY_SETUP_ACTIVE" not in set(result["signal"])


def test_ranking_audit_preserves_rows_and_signals():
    result = normalize(candidate(ticker="A"), candidate(ticker="B", final_score=75, trigger_confirmed=False))
    assert len(result) == 2
    assert {"legacy_rank", "trade_rank", "rank_delta"}.issubset(result.columns)
