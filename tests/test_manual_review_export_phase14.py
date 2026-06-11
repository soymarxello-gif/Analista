from __future__ import annotations

import pandas as pd

from tools.manual_review_export import build_manual_review_dataframe


def test_manual_review_keeps_trigger_confirmed_first():
    df = pd.DataFrame(
        [
            {
                "rank": 2,
                "ticker": "BBB",
                "signal": "WATCHLIST",
                "recommendation": "RECHECK_LIVE_QUOTE",
                "manual_quote_check_required": True,
                "final_trade_score": 80,
                "setup_quality_score": 82,
            },
            {
                "rank": 1,
                "ticker": "AAA",
                "signal": "TRIGGER_CONFIRMED",
                "recommendation": "MANUAL_REVIEW_TRIGGER_CONFIRMED",
                "manual_quote_check_required": False,
                "final_trade_score": 75,
                "setup_quality_score": 76,
            },
        ]
    )

    result = build_manual_review_dataframe(df)

    assert list(result["ticker"]) == ["AAA", "BBB"]
    assert result.iloc[0]["_review_group"] == "TRIGGER_CONFIRMED"
    assert result.iloc[1]["_review_group"] == "RECHECK_LIVE_QUOTE"


def test_manual_review_excludes_veto_and_avoid():
    df = pd.DataFrame(
        [
            {
                "rank": 1,
                "ticker": "AAA",
                "signal": "VETO",
                "recommendation": "DO_NOT_TRADE",
                "manual_quote_check_required": False,
                "final_trade_score": 95,
                "setup_quality_score": 95,
            },
            {
                "rank": 2,
                "ticker": "BBB",
                "signal": "AVOID",
                "recommendation": "AVOID_FOR_NOW",
                "manual_quote_check_required": False,
                "final_trade_score": 80,
                "setup_quality_score": 80,
            },
            {
                "rank": 3,
                "ticker": "CCC",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "manual_quote_check_required": False,
                "final_trade_score": 72,
                "setup_quality_score": 75,
            },
        ]
    )

    result = build_manual_review_dataframe(df)

    assert list(result["ticker"]) == ["CCC"]
    assert set(result["signal"]) == {"WATCHLIST"}


def test_manual_review_handles_empty_dataframe():
    result = build_manual_review_dataframe(pd.DataFrame())

    assert result.empty