\
import pandas as pd

def add_volume_features(df: pd.DataFrame, avg_period: int = 20) -> pd.DataFrame:
    out = df.copy()
    out["avg_volume_20d"] = out["volume"].rolling(avg_period).mean()
    out["relative_volume"] = out["volume"] / out["avg_volume_20d"]
    rng = (out["high"] - out["low"]).replace(0, pd.NA)
    out["close_location_value"] = ((out["close"] - out["low"]) / rng).clip(0, 1)
    out["up_day"] = out["close"] > out["close"].shift(1)
    out["down_day"] = out["close"] < out["close"].shift(1)
    return out
