from __future__ import annotations

from scoring.signal_classifier import classify_signal

BASE_CONFIG = {
    "filters": {"min_price": 10, "min_market_cap_usd": 1_500_000_000},
    "risk_reward": {"min_rr_absolute": 1.5},
    "veto_rules": {"thresholds": {"min_trend_score": 0.55}},
    "signal_thresholds": {
        "trigger_confirmed": {"min_score": 80, "min_rr": 2.0},
        "ready_wait_trigger": {"min_score": 80, "min_rr": 1.7},
        "watchlist": {"min_score": 70},
    },
}


def base_row():
    return {
        "price": 100,
        "market_cap": 10_000_000_000,
        "quote_type": "EQUITY",
        "liquidity_pass": True,
        "rr": 2.0,
        "trend_score": 0.8,
        "setup_type": "BREAKOUT",
        "earnings_veto": False,
        "final_trade_score": 86,
        "trigger_confirmed": True,
        "execution_quote_quality": "HIGH",
    }


def test_veto_liquidity_fail():
    row = base_row()
    row["liquidity_pass"] = False
    signal, reasons = classify_signal(row, BASE_CONFIG)
    assert signal == "VETO"
    assert "liquidity_fail" in reasons


def test_veto_no_valid_setup():
    row = base_row()
    row["setup_type"] = "NO_VALID_SETUP"
    signal, reasons = classify_signal(row, BASE_CONFIG)
    assert signal == "VETO"
    assert "no_valid_setup" in reasons


def test_trigger_confirmed_requires_valid_quote():
    signal, reasons = classify_signal(base_row(), BASE_CONFIG)
    assert signal == "TRIGGER_CONFIRMED"
    assert reasons == []


def test_low_quote_cannot_trigger_confirmed():
    row = base_row()
    row["execution_quote_quality"] = "LOW"
    signal, _ = classify_signal(row, BASE_CONFIG)
    assert signal != "TRIGGER_CONFIRMED"


def test_ready_wait_trigger_without_trigger():
    row = base_row()
    row["trigger_confirmed"] = False
    row["final_trade_score"] = 82
    signal, reasons = classify_signal(row, BASE_CONFIG)
    assert signal == "READY_WAIT_TRIGGER"
    assert reasons == []


def test_price_and_market_cap_are_hard_filters():
    row = base_row()
    row["price"] = 9.99
    row["market_cap"] = 1_000_000_000
    signal, reasons = classify_signal(row, BASE_CONFIG)
    assert signal == "VETO"
    assert "price_below_min" in reasons
    assert "market_cap_below_min" in reasons


def test_buy_setup_active_is_never_emitted():
    signal, _ = classify_signal(base_row(), BASE_CONFIG)
    assert signal != "BUY_SETUP_ACTIVE"


def test_nearby_earnings_is_advisory_and_never_vetoes_setup():
    row = base_row()
    row["earnings_veto"] = True
    signal, reasons = classify_signal(row, BASE_CONFIG)
    assert signal == "TRIGGER_CONFIRMED"
    assert "earnings_too_close" not in reasons
