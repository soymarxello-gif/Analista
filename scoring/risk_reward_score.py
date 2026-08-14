import numpy as np


def score_risk_reward(df, structure, config):
    if df is None or df.empty:
        return {"rr_score": 0.0, "entry": None, "stop": None, "target": None, "rr": None}
    row = df.iloc[-1]
    entry = float(row["close"])
    atr = row.get("atr")
    if atr != atr or atr is None or atr <= 0:
        return {"rr_score": 0.0, "entry": entry, "stop": None, "target": None, "rr": None}

    atr_mult = config.get("risk_reward", {}).get("atr_stop_multiplier", 1.5)
    stop_atr = entry - atr_mult * atr
    recent_support = float(df["low"].tail(20).min())
    stop = max(stop_atr, recent_support * 0.995) if recent_support < entry else stop_atr
    target = max(float(df["high"].tail(60).max()), entry + 3 * atr)
    risk = entry - stop
    reward = target - entry
    rr = reward / risk if risk > 0 else 0
    rr_score = np.interp(rr, [1.0, 2.0, 3.0], [0.0, 0.7, 1.0])
    return {
        "rr_score": float(np.clip(rr_score, 0, 1)),
        "entry": entry,
        "stop": float(stop),
        "target": float(target),
        "rr": float(rr),
    }
