import pandas as pd

from indicators.pipeline import add_all_indicators


def test_indicators_basic():
    df = pd.DataFrame({
        "open": range(1, 251),
        "high": range(2, 252),
        "low": range(0, 250),
        "close": range(1, 251),
        "volume": [1000000] * 250,
    })
    out = add_all_indicators(df, {"indicators": {"moving_averages": [20, 50, 200]}})
    assert "sma20" in out
    assert "rsi" in out
    assert "atr" in out
