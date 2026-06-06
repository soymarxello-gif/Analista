\
def detect_volatility_contraction(df, config):
    cfg = config.get("setups", {}).get("volatility_contraction", {})
    ratio = cfg.get("min_compression_ratio", 0.75)
    if len(df) < 25 or "atr" not in df:
        return {"is_vcp": False}
    atr5 = df["atr"].tail(5).mean()
    atr20 = df["atr"].tail(20).mean()
    is_vcp = bool(atr20 and atr5 / atr20 <= ratio)
    return {"is_vcp": is_vcp, "compression_ratio": float(atr5 / atr20) if atr20 else None}
