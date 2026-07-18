from datetime import datetime, timezone

import pandas as pd

from data.quote_context import (
    add_quote_temporal_context,
    normalize_market_session,
    normalize_scan_with_quote_context,
    temporal_quote_penalty,
)


def _config():
    return {
        "filters": {"min_price": 10, "min_market_cap_usd": 1_500_000_000},
        "liquidity": {"max_spread_pct": 0.03, "max_quote_distance_pct": 0.15},
        "quote_quality": {
            "max_age_seconds_regular": 900,
            "max_age_seconds_extended": 3600,
            "max_age_seconds_closed": 86400,
        },
        "signals": {
            "allowed_states": [
                "VETO",
                "AVOID",
                "WATCHLIST",
                "READY_WAIT_TRIGGER",
                "TRIGGER_CONFIRMED",
            ]
        },
        "signal_thresholds": {
            "trigger_confirmed": {"min_score": 80, "min_rr": 2.0},
            "ready_wait_trigger": {"min_score": 80, "min_rr": 1.7},
            "watchlist": {"min_score": 70},
        },
        "risk_reward": {"min_rr_absolute": 1.5},
        "veto_rules": {"thresholds": {"min_trend_score": 0.55}},
        "trade_score_weights": {
            "asset_quality": 0.25,
            "setup_quality": 0.40,
            "context": 0.25,
            "institutional": 0.10,
        },
        "ranking_audit": {"change_production_ranking": False},
    }


def _candidate(timestamp: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "TEST",
                "price": 100.0,
                "market_cap": 10_000_000_000,
                "quote_type": "EQUITY",
                "bid": 99.95,
                "ask": 100.05,
                "liquidity_pass": True,
                "liquidity_score": 0.9,
                "trend_score": 0.9,
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
                "entry": 101.0,
                "stop": 97.0,
                "target": 113.0,
                "rr": 3.0,
                "final_score": 88.0,
                "final_trade_score": 88.0,
                "quote_timestamp": timestamp,
                "market_session": "REGULAR",
            }
        ]
    )


def test_normalize_market_session_aliases():
    assert normalize_market_session("REGULAR_MARKET") == "REGULAR"
    assert normalize_market_session("postmarket") == "POST"
    assert normalize_market_session("unexpected") == "UNKNOWN"


def test_add_quote_temporal_context_computes_age():
    now = datetime(2026, 7, 18, 15, 0, tzinfo=timezone.utc)
    row = add_quote_temporal_context(
        {"quote_timestamp": "2026-07-18T14:55:00Z", "market_session": "REGULAR"},
        now=now,
    )
    assert row["quote_age_seconds"] == 300.0
    assert row["quote_temporal_status"] == "KNOWN"


def test_missing_timestamp_is_unknown_without_forced_penalty():
    row = add_quote_temporal_context({"market_session": "REGULAR"})
    assert row["quote_temporal_status"] == "UNKNOWN"
    assert temporal_quote_penalty(row, _config()) == (None, None)


def test_stale_regular_quote_is_downgraded():
    now = datetime(2026, 7, 18, 15, 0, tzinfo=timezone.utc)
    df = _candidate("2026-07-18T14:30:00Z")
    out = normalize_scan_with_quote_context(df, _config(), now=now)
    row = out.iloc[0]
    assert row["quote_status"] == "STALE_POSSIBLE"
    assert row["execution_quote_quality"] == "LOW"
    assert row["signal"] == "WATCHLIST"
    assert pd.isna(row["actionable_entry"])
    assert "stale_quote_timestamp" in row["penalty_reasons"]


def test_fresh_regular_quote_remains_actionable():
    now = datetime(2026, 7, 18, 15, 0, tzinfo=timezone.utc)
    df = _candidate("2026-07-18T14:58:00Z")
    out = normalize_scan_with_quote_context(df, _config(), now=now)
    row = out.iloc[0]
    assert row["quote_status"] == "VALID"
    assert row["execution_quote_quality"] == "HIGH"
    assert row["signal"] == "TRIGGER_CONFIRMED"
