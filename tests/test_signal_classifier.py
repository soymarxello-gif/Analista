from __future__ import annotations

from scoring.signal_classifier import classify_signal


BASE_CONFIG = {
    "risk_reward": {"min_rr_absolute": 1.5},
    "veto_rules": {"thresholds": {"min_trend_score": 0.55}},
    "signal_thresholds": {
        "buy_setup_active": {"min_score": 85, "min_rr": 2.0},
        "ready_wait_trigger": {"min_score": 80, "min_rr": 1.7},
        "watchlist": {"min_score": 70},
    },
}


def base_row():
    return {
        "liquidity_pass": True,
        "rr": 2.0,
        "trend_score": 0.8,
        "setup_type": "BREAKOUT",
        "earnings_veto": False,
        "final_score": 86,
        "trigger_confirmed": True,
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


def test_buy_setup_active():
    signal, reasons = classify_signal(base_row(), BASE_CONFIG)
    assert signal == "BUY_SETUP_ACTIVE"
    assert reasons == []


def test_ready_wait_trigger_without_trigger():
    row = base_row()
    row["trigger_confirmed"] = False
    row["final_score"] = 82
    signal, reasons = classify_signal(row, BASE_CONFIG)
    assert signal == "READY_WAIT_TRIGGER"
    assert reasons == []
