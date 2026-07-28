\
import pandas as pd

from .adjusted import price_series


def add_volume_features(df: pd.DataFrame, avg_period: int = 20) -> pd.DataFrame:
    out = df.copy()
    out["avg_volume_20d"] = out["volume"].rolling(avg_period).mean()
    out["relative_volume"] = out["volume"] / out["avg_volume_20d"]
    rng = (out["high"] - out["low"]).replace(0, pd.NA)
    out["close_location_value"] = ((out["close"] - out["low"]) / rng).clip(0, 1)
    close = price_series(out, "close", "adj_close")
    out["up_day"] = close > close.shift(1)
    out["down_day"] = close < close.shift(1)
    return out
