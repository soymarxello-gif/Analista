\
import numpy as np

def score_momentum(df, config):
    if df is None or df.empty:
        return 0.5
    row = df.iloc[-1]
    rsi = row.get("rsi", 50)
    macd = row.get("macd", 0)
    macd_signal = row.get("macd_signal", 0)
    hist = row.get("macd_hist", 0)
    hist_1d_ago = df["macd_hist"].iloc[-2] if len(df) >= 2 and "macd_hist" in df else None
    hist_3d_ago = df["macd_hist"].iloc[-4] if len(df) >= 4 and "macd_hist" in df else None
    hist_improving = (
        hist_1d_ago is not None
        and hist > hist_1d_ago
        and (hist_3d_ago is None or hist > hist_3d_ago)
    )
    macd_ok = macd > macd_signal or hist_improving
    ma_col = "ema20" if "ema20" in df else "sma20"
    ma_slope_ok = row.get(ma_col, 0) > df[ma_col].iloc[-6] if len(df) >= 6 and ma_col in df else False

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
