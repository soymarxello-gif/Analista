\
import pandas as pd

from .adjusted import price_series


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    out = df.copy()
    high = price_series(out, "high", "adj_high")
    low = price_series(out, "low", "adj_low")
    close = price_series(out, "close", "adj_close")
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    out["atr"] = tr.rolling(period).mean()
    out["atr_pct"] = out["atr"] / close
    return out
