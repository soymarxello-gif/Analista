from __future__ import annotations

from scoring.execution_review import evaluate_execution_review


def test_watchlist_low_quote_requires_manual_recheck_high_priority():
    row = {
        "signal": "WATCHLIST",
        "recommendation": "RECHECK_LIVE_QUOTE",
        "quote_status": "STALE_POSSIBLE",
        "execution_quote_quality": "LOW",
        "final_trade_score": 75,
        "setup_quality_score": 80,
        "rr": 2.0,
    }

    result = evaluate_execution_review(row)

    assert result["manual_quote_check_required"] is True
    assert result["quote_recheck_priority"] == "HIGH"
    assert "quote_status=STALE_POSSIBLE" in result["quote_recheck_reason"]


def test_valid_quote_does_not_require_manual_recheck():
    row = {
        "signal": "WATCHLIST",
        "recommendation": "WATCHLIST_MONITOR",
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
        "final_trade_score": 75,
        "setup_quality_score": 80,
        "rr": 2.0,
    }

    result = evaluate_execution_review(row)

    assert result["manual_quote_check_required"] is False
    assert result["quote_recheck_priority"] == "NONE"


def test_veto_low_quote_does_not_create_operational_recheck():
    row = {
        "signal": "VETO",
        "recommendation": "DO_NOT_TRADE",
        "quote_status": "MISSING",
        "execution_quote_quality": "LOW",
        "final_trade_score": 90,
        "setup_quality_score": 90,
        "rr": 3.0,
    }

    result = evaluate_execution_review(row)

    assert result["manual_quote_check_required"] is False
    assert result["quote_recheck_priority"] == "NONE"