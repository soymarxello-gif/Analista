from engine.early_filter_runtime import hard_filter_reasons
from scoring.signal_classifier import classify_signal

CONFIG = {
    "filters": {"min_price": 10, "min_market_cap_usd": 1_500_000_000},
    "universe": {"allowed_quote_types": ["EQUITY", "ETF"]},
    "risk_reward": {"min_rr_absolute": 1.5},
    "veto_rules": {"thresholds": {"min_trend_score": 0.55}},
    "signal_thresholds": {
        "trigger_confirmed": {"min_score": 80, "min_rr": 2.0},
        "ready_wait_trigger": {"min_score": 80, "min_rr": 1.7},
        "watchlist": {"min_score": 70},
    },
}


def test_etf_does_not_require_company_market_cap():
    row = {
        "ticker": "XLE",
        "quote_type": "ETF",
        "price": 90,
        "market_cap": None,
        "liquidity_pass": True,
        "rr": 2.2,
        "trend_score": 0.9,
        "setup_type": "BREAKOUT",
        "earnings_veto": False,
        "final_trade_score": 85,
        "trigger_confirmed": False,
    }
    assert "market_cap_below_min" not in hard_filter_reasons(row, CONFIG)
    assert classify_signal(row, CONFIG)[0] == "READY_WAIT_TRIGGER"


def test_missing_stock_market_cap_is_not_a_veto_when_other_data_is_available():
    row = {
        "ticker": "UNKNOWNCAP",
        "quote_type": "EQUITY",
        "price": 90,
        "market_cap": None,
        "liquidity_pass": True,
        "rr": 2.2,
        "trend_score": 0.9,
        "setup_type": "BREAKOUT",
        "final_trade_score": 85,
        "trigger_confirmed": False,
    }
    assert "market_cap_below_min" not in hard_filter_reasons(row, CONFIG)
    assert classify_signal(row, CONFIG)[0] == "READY_WAIT_TRIGGER"
