\
import numpy as np

def score_volume(df):
    if df is None or df.empty:
        return 0.0
    row = df.iloc[-1]
    rvol = row.get("relative_volume", 1.0)
    clv = row.get("close_location_value", 0.5)
    obv_slope = row.get("obv_slope", 0)
    rvol_score = min(max((rvol - 0.5) / 1.5, 0), 1)
    obv_score = 1.0 if obv_slope > 0 else 0.35
    score = 0.45 * rvol_score + 0.30 * obv_score + 0.25 * (clv if clv == clv else 0.5)
    return float(np.clip(score, 0, 1))
