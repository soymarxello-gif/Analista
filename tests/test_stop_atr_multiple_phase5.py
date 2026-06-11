from __future__ import annotations

import pandas as pd

from scoring.risk_reward_score import score_risk_reward


def make_df(close: float = 100.0, atr: float = 2.0) -> pd.DataFrame:
    rows = []
    for i in range(80):
        rows.append(
            {
                "open": close - 1,
                "high": close + 1,
                "low": close - 3,
                "close": close,
                "volume": 1_000_000,
                "atr": atr,
                "ma20": close - 5,
                "ma50": close - 8,
            }
        )
    return pd.DataFrame(rows)


def test_stop_atr_multiple_is_returned():
    df = make_df()
    result = score_risk_reward(df, {"setup_type": "PULLBACK"}, {})

    assert "atr" in result
    assert "stop_atr_multiple" in result
    assert "stop_atr_status" in result
    assert result["atr"] == 2.0
    assert result["stop_atr_multiple"] is not None


def test_stop_atr_status_is_valid_enum():
    df = make_df()
    result = score_risk_reward(df, {"setup_type": "PULLBACK"}, {})

    assert result["stop_atr_status"] in {
        "NO_DATA",
        "NO_ATR",
        "BELOW_HARD_MIN",
        "AGGRESSIVE_TIGHT",
        "IDEAL",
        "WIDE",
    }


def test_missing_atr_returns_no_atr_status():
    df = make_df()
    df["atr"] = None

    result = score_risk_reward(df, {"setup_type": "PULLBACK"}, {})

    assert result["atr"] is None
    assert result["stop_atr_multiple"] is None
    assert result["stop_atr_status"] == "NO_ATR"