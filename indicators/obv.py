\
import numpy as np
import pandas as pd

def add_obv(df: pd.DataFrame, slope_period: int = 20) -> pd.DataFrame:
    out = df.copy()
    direction = np.sign(out["close"].diff()).fillna(0)
    out["obv"] = (direction * out["volume"]).cumsum()
    out["obv_slope"] = out["obv"].diff(slope_period) / slope_period
    return out
