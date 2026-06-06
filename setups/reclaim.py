\
def detect_reclaim(df, config):
    if len(df) < 55:
        return {"is_reclaim": False}
    prev = df.iloc[-2]
    row = df.iloc[-1]
    levels = [row.get("sma20"), row.get("sma50")]
    for level in levels:
        if level == level and prev["close"] < level and row["close"] > level:
            return {"is_reclaim": True, "reclaim_level": float(level)}
    return {"is_reclaim": False}
