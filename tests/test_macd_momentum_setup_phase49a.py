from __future__ import annotations

import pandas as pd

from indicators.pipeline import add_all_indicators
from scoring.structure_score import score_structure


CONFIG = {
    "indicators": {
        "moving_averages": [20, 50, 200],
        "rsi": {"period": 14},
        "macd": {"fast": 12, "slow": 26, "signal": 9},
        "atr": {"period": 14},
        "volume": {"avg_period": 20},
        "obv": {"slope_period": 20},
    },
    "setups": {
        "macd_momentum": {
            "enabled": True,
            "min_rsi": 50,
            "max_rsi": 72,
            "min_relative_volume": 0.80,
            "max_distance_ema20_pct": 0.055,
            "max_distance_ema20_atr": 1.75,
            "require_weekly_macd_non_bearish": True,
        }
    },
}


def _constructive_history() -> pd.DataFrame:
    closes = [70.0 + i * 0.16 for i in range(260)]
    frame = pd.DataFrame(
        {
            "open": [value - 0.15 for value in closes],
            "high": [value + 0.35 for value in closes],
            "low": [value - 0.35 for value in closes],
            "close": closes,
            "volume": [1_000_000] * 260,
        },
        index=pd.bdate_range("2025-01-01", periods=260),
    )
    out = add_all_indicators(frame, CONFIG)
    last = out.index[-1]
    out.loc[last, "close"] = float(out.loc[last, "ema20"]) * 1.04
    out.loc[last, "open"] = float(out.loc[last, "close"]) - 0.20
    out.loc[last, "high"] = float(out.loc[last, "close"]) + 0.30
    out.loc[last, "low"] = float(out.loc[last, "close"]) - 0.30
    out.loc[last, "atr"] = (float(out.loc[last, "close"]) - float(out.loc[last, "ema20"])) / 1.10
    out.loc[last, "rsi"] = 61.0
    out.loc[out.index[-3], "macd_hist"] = -0.16
    out.loc[out.index[-2], "macd_hist"] = -0.08
    out.loc[last, "macd_hist"] = -0.02
    out.loc[last, "relative_volume"] = 1.0
    return out


def test_macd_momentum_setup_prevents_false_no_valid_setup() -> None:
    result = score_structure(_constructive_history(), CONFIG)

    assert result["setup_type"] == "MACD_MOMENTUM"
    assert result["structure_score"] > 0.70
    assert result["trigger_confirmed"] is False


def test_macd_momentum_requires_two_day_histogram_rise() -> None:
    frame = _constructive_history()
    last = frame.index[-1]
    frame.loc[frame.index[-3], "macd_hist"] = -0.06
    frame.loc[frame.index[-2], "macd_hist"] = -0.08
    frame.loc[last, "macd_hist"] = -0.07

    result = score_structure(frame, CONFIG)

    assert result["setup_type"] != "MACD_MOMENTUM"
