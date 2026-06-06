\
def calculate_final_score(scores: dict, config: dict) -> float:
    w = config.get("scoring_weights", {})
    components = {
        "relative_strength": scores.get("rs_score", 0.5),
        "trend": scores.get("trend_score", 0.5),
        "market_regime": scores.get("market_regime_score", 0.5),
        "volume_accumulation": scores.get("volume_score", 0.5),
        "sector_rotation": scores.get("sector_score", 0.5),
        "structure_trigger": scores.get("structure_score", 0.5),
        "risk_reward_atr": scores.get("rr_score", 0.5),
        "liquidity": scores.get("liquidity_score", 0.5),
        "momentum": scores.get("momentum_score", 0.5),
        "options_flow": scores.get("options_score", 0.5),
        "fundamentals": scores.get("fundamental_score", 0.5),
        "sentiment": scores.get("sentiment_score", 0.5),
    }
    return float(sum(w.get(k, 0) * max(0, min(float(v), 1)) for k, v in components.items()))
