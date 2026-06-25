\
import numpy as np
import pandas as pd


def _safe_number(value, default: float) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default

def score_volume(df):
    if df is None or df.empty:
        return 0.0
    row = df.iloc[-1]
    rvol = _safe_number(row.get("relative_volume"), 1.0)
    clv = _safe_number(row.get("close_location_value"), 0.5)
    obv_slope = _safe_number(row.get("obv_slope"), 0.0)
    rvol_score = min(max((rvol - 0.5) / 1.5, 0), 1)
    obv_score = 1.0 if obv_slope > 0 else 0.35
    score = 0.45 * rvol_score + 0.30 * obv_score + 0.25 * clv
    return float(np.clip(score, 0, 1))
