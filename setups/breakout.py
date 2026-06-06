\
def detect_breakout(df, config):
    cfg = config.get("setups", {}).get("breakout", {})
    lookback = cfg.get("lookback_resistance", 20)
    min_rvol = cfg.get("min_relative_volume", 1.3)
    if len(df) < lookback + 2:
        return {"is_breakout": False}
    prev_res = df["high"].shift(1).rolling(lookback).max().iloc[-1]
    row = df.iloc[-1]
    is_breakout = bool(row["close"] > prev_res and row.get("relative_volume", 0) >= min_rvol)
    return {"is_breakout": is_breakout, "breakout_level": float(prev_res) if prev_res == prev_res else None}
