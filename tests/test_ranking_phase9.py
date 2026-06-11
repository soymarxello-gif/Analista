from __future__ import annotations

import pandas as pd


def _apply_phase9_sort(out: pd.DataFrame) -> pd.DataFrame:
    signal_order = {
        "TRIGGER_CONFIRMED": 0,
        "READY_WAIT_TRIGGER": 1,
        "WATCHLIST": 2,
        "AVOID": 3,
        "VETO": 4,
        "BUY_SETUP_ACTIVE": 99,
    }

    recommendation_order = {
        "MANUAL_REVIEW_TRIGGER_CONFIRMED": 0,
        "WAIT_FOR_TRIGGER": 1,
        "WATCHLIST_MONITOR": 2,
        "RECHECK_LIVE_QUOTE": 3,
        "WATCHLIST_MONITOR_QUOTE": 4,
        "WATCHLIST_NO_VALID_SETUP": 5,
        "AVOID_FOR_NOW": 6,
        "DO_NOT_TRADE": 7,
        "REVIEW_MANUALLY": 8,
    }

    quote_quality_order = {
        "HIGH": 0,
        "MEDIUM": 1,
        "LOW": 2,
    }

    out = out.copy()

    out["_signal_order"] = out["signal"].map(signal_order).fillna(99).astype(int)
    out["_recommendation_order"] = out["recommendation"].map(recommendation_order).fillna(99).astype(int)
    out["_quote_quality_order"] = out["execution_quote_quality"].map(quote_quality_order).fillna(99).astype(int)

    out["legacy_rank"] = out["final_score"].rank(method="first", ascending=False).astype(int)
    out["trade_score_rank"] = out["final_trade_score"].rank(method="first", ascending=False).astype(int)

    out = out.sort_values(
        [
            "_signal_order",
            "_recommendation_order",
            "_quote_quality_order",
            "final_trade_score",
            "setup_quality_score",
            "final_score",
        ],
        ascending=[True, True, True, False, False, False],
    ).reset_index(drop=True)

    out["operational_rank"] = range(1, len(out) + 1)
    out["rank_delta_trade_vs_legacy"] = out["trade_score_rank"] - out["legacy_rank"]
    out["rank"] = out["operational_rank"]

    return out.drop(
        columns=["_signal_order", "_recommendation_order", "_quote_quality_order"],
        errors="ignore",
    )


def test_operational_rank_keeps_veto_below_watchlist_even_with_high_trade_score():
    df = pd.DataFrame(
        [
            {
                "ticker": "VETO_HIGH",
                "signal": "VETO",
                "recommendation": "DO_NOT_TRADE",
                "execution_quote_quality": "LOW",
                "final_score": 75,
                "final_trade_score": 95,
                "setup_quality_score": 99,
            },
            {
                "ticker": "WATCH_VALID",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "execution_quote_quality": "HIGH",
                "final_score": 70,
                "final_trade_score": 75,
                "setup_quality_score": 76,
            },
            {
                "ticker": "TRIGGER_VALID",
                "signal": "TRIGGER_CONFIRMED",
                "recommendation": "MANUAL_REVIEW_TRIGGER_CONFIRMED",
                "execution_quote_quality": "HIGH",
                "final_score": 80,
                "final_trade_score": 82,
                "setup_quality_score": 85,
            },
        ]
    )

    out = _apply_phase9_sort(df)

    assert out.loc[0, "ticker"] == "TRIGGER_VALID"
    assert out.loc[1, "ticker"] == "WATCH_VALID"
    assert out.loc[2, "ticker"] == "VETO_HIGH"
    assert out.loc[out["ticker"] == "VETO_HIGH", "operational_rank"].iloc[0] == 3


def test_trade_score_rank_is_kept_as_diagnostic_not_primary_order():
    df = pd.DataFrame(
        [
            {
                "ticker": "VETO_HIGH",
                "signal": "VETO",
                "recommendation": "DO_NOT_TRADE",
                "execution_quote_quality": "LOW",
                "final_score": 75,
                "final_trade_score": 95,
                "setup_quality_score": 99,
            },
            {
                "ticker": "TRIGGER_VALID",
                "signal": "TRIGGER_CONFIRMED",
                "recommendation": "MANUAL_REVIEW_TRIGGER_CONFIRMED",
                "execution_quote_quality": "HIGH",
                "final_score": 80,
                "final_trade_score": 82,
                "setup_quality_score": 85,
            },
        ]
    )

    out = _apply_phase9_sort(df)

    veto = out[out["ticker"] == "VETO_HIGH"].iloc[0]
    trigger = out[out["ticker"] == "TRIGGER_VALID"].iloc[0]

    assert veto["trade_score_rank"] == 1
    assert trigger["operational_rank"] == 1
    assert veto["operational_rank"] > trigger["operational_rank"]