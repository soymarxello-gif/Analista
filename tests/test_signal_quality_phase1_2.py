from scoring.signal_classifier import classify_signal, classify_base_signal


CONFIG = {
    "risk_reward": {"min_rr_absolute": 1.5},
    "veto_rules": {
        "thresholds": {"min_trend_score": 0.55},
        "data_quality": {
            "veto_low_confidence": True,
            "veto_missing_critical": True,
        },
    },
    "signal_thresholds": {
        "buy_setup_active": {"min_score": 85, "min_rr": 2.0, "require_trigger": True},
        "ready_wait_trigger": {"min_score": 80, "min_rr": 1.7},
        "watchlist": {"min_score": 70},
    },
}


def base_row():
    return {
        "liquidity_pass": True,
        "rr": 2.1,
        "trend_score": 0.85,
        "setup_type": "BREAKOUT",
        "earnings_veto": False,
        "final_score": 88,
        "trigger_confirmed": True,
        "data_quality_confidence": "HIGH",
        "missing_critical_fields": "",
    }


def test_base_signal_ignores_veto_context_but_buy_setup_active_disabled():
    row = base_row()
    row["liquidity_pass"] = False

    assert classify_base_signal(row, CONFIG) == "TRIGGER_CONFIRMED"
    assert classify_base_signal(row, CONFIG) != "BUY_SETUP_ACTIVE"


def test_low_data_quality_vetoes():
    row = base_row()
    row["data_quality_confidence"] = "LOW"
    signal, veto = classify_signal(row, CONFIG)
    assert signal == "VETO"
    assert "data_quality_low" in veto


def test_missing_critical_data_vetoes():
    row = base_row()
    row["missing_critical_fields"] = "rr"
    signal, veto = classify_signal(row, CONFIG)
    assert signal == "VETO"
    assert "missing_critical_data" in veto
