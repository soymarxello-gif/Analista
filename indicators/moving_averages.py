\
import pandas as pd

def add_moving_averages(df: pd.DataFrame, windows=(20, 50, 200)) -> pd.DataFrame:
    out = df.copy()
    for w in windows:
        out[f"sma{w}"] = out["close"].rolling(w).mean()
    return out
