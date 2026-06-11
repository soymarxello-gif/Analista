from __future__ import annotations

from copy import deepcopy

from config_loader import load_config
from scoring.signal_classifier import classify_base_signal, classify_signal


def base_row() -> dict:
    return {
        "ticker": "GOOD",
        "price": 50.0,
        "market_cap": 3_000_000_000,
        "quote_type": "EQUITY",
        "liquidity_pass": True,
        "rr": 2.5,
        "trend_score": 0.8,
        "setup_type": "PULLBACK",
        "final_score": 90,
        "trigger_confirmed": True,
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
    }


def test_buy_setup_active_is_disabled():
    cfg = load_config()
    signal, reasons = classify_signal(base_row(), cfg)

    assert signal != "BUY_SETUP_ACTIVE"
    assert signal == "TRIGGER_CONFIRMED"
    assert reasons == []


def test_base_signal_does_not_emit_buy_setup_active_when_disabled():
    cfg = load_config()
    signal = classify_base_signal(base_row(), cfg)

    assert signal != "BUY_SETUP_ACTIVE"
    assert signal == "TRIGGER_CONFIRMED"


def test_price_filter_is_hard():
    cfg = load_config()
    row = deepcopy(base_row())
    row["price"] = 9.99

    signal, reasons = classify_signal(row, cfg)

    assert signal == "VETO"
    assert "price_below_min" in reasons


def test_market_cap_filter_is_hard():
    cfg = load_config()
    row = deepcopy(base_row())
    row["market_cap"] = 1_499_999_999

    signal, reasons = classify_signal(row, cfg)

    assert signal == "VETO"
    assert "market_cap_below_min" in reasons


def test_no_valid_setup_is_veto():
    cfg = load_config()
    row = deepcopy(base_row())
    row["setup_type"] = "NO_VALID_SETUP"

    signal, reasons = classify_signal(row, cfg)

    assert signal == "VETO"
    assert "no_valid_setup" in reasons


def test_trigger_confirmed_requires_execution_quote_not_low():
    cfg = load_config()
    row = deepcopy(base_row())
    row["trigger_confirmed"] = True
    row["execution_quote_quality"] = "LOW"

    signal, reasons = classify_signal(row, cfg)

    assert signal != "TRIGGER_CONFIRMED"
    assert signal != "BUY_SETUP_ACTIVE"
    assert signal == "WATCHLIST"
    assert reasons == []


def test_ready_wait_trigger_requires_trigger_not_confirmed():
    cfg = load_config()
    row = deepcopy(base_row())
    row["final_score"] = 82
    row["rr"] = 1.8
    row["trigger_confirmed"] = False

    signal, reasons = classify_signal(row, cfg)

    assert signal == "READY_WAIT_TRIGGER"
    assert row["trigger_confirmed"] is False
    assert reasons == []


def test_confirmed_trigger_does_not_return_ready_wait_trigger():
    cfg = load_config()
    row = deepcopy(base_row())
    row["final_score"] = 82
    row["rr"] = 1.8
    row["trigger_confirmed"] = True

    signal, reasons = classify_signal(row, cfg)

    assert signal != "READY_WAIT_TRIGGER"
    assert signal in {"WATCHLIST", "TRIGGER_CONFIRMED"}
    assert reasons == []