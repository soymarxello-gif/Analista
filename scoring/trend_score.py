\
def score_trend(df, config):
    if len(df) < 200:
        return 0.0, "weak"
    row = df.iloc[-1]
    weights = config.get("trend", {}).get("scoring", {})
    score = 0.0
    score += weights.get("close_above_ma20", 0.20) if row["close"] > row.get("sma20", row["close"]) else 0
    score += weights.get("close_above_ma50", 0.25) if row["close"] > row.get("sma50", row["close"]) else 0
    score += weights.get("close_above_ma200", 0.25) if row["close"] > row.get("sma200", row["close"]) else 0
    score += weights.get("ma20_above_ma50", 0.15) if row.get("sma20", 0) > row.get("sma50", 0) else 0
    score += weights.get("ma50_above_ma200", 0.15) if row.get("sma50", 0) > row.get("sma200", 0) else 0
    th = config.get("trend", {}).get("thresholds", {})
    status = "excellent" if score >= th.get("excellent", 0.85) else "acceptable" if score >= th.get("acceptable", 0.70) else "weak"
    return float(min(score, 1.0)), status
