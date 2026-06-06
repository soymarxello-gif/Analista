\
import numpy as np

def score_momentum(df, config):
    if df is None or df.empty:
        return 0.5
    row = df.iloc[-1]
    rsi = row.get("rsi", 50)
    macd_ok = row.get("macd", 0) > row.get("macd_signal", 0)
    ma_slope_ok = row.get("sma20", 0) > df["sma20"].iloc[-6] if len(df) >= 6 and "sma20" in df else False

    if rsi != rsi:
        rsi_score = 0.5
    elif 55 <= rsi <= 70:
        rsi_score = 1.0
    elif 50 <= rsi < 55 or 70 < rsi <= 75:
        rsi_score = 0.65
    elif rsi > 75:
        rsi_score = 0.35
    else:
        rsi_score = 0.25

    return float(np.clip(0.4 * rsi_score + 0.35 * int(macd_ok) + 0.25 * int(ma_slope_ok), 0, 1))
