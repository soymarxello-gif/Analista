\
import pandas as pd

from .adjusted import price_series


def add_moving_averages(df: pd.DataFrame, windows=(20, 50, 200)) -> pd.DataFrame:
    out = df.copy()
    close = price_series(out, "close", "adj_close")
    for w in windows:
        out[f"sma{w}"] = close.rolling(w).mean()
    if 20 in set(windows):
        out["ema20"] = close.ewm(span=20, adjust=False).mean()
    return out
