\
def detect_pullback(df, config):
    cfg = config.get("setups", {}).get("pullback", {})
    max_dist = cfg.get("max_distance_to_ma_pct", 0.025)
    if len(df) < 200:
        return {"is_pullback": False}
    row = df.iloc[-1]
    close = row["close"]
    trend_ok = close > row.get("sma200", close) and (row.get("sma20", close) > row.get("sma50", close) or close > row.get("sma50", close))
    d20 = abs(close - row.get("sma20", close)) / close
    d50 = abs(close - row.get("sma50", close)) / close
    is_pullback = bool(trend_ok and min(d20, d50) <= max_dist)
    level = row.get("sma20") if d20 <= d50 else row.get("sma50")
    return {"is_pullback": is_pullback, "pullback_level": float(level) if level == level else None}
