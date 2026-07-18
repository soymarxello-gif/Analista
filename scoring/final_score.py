from __future__ import annotations

from math import fsum


COMPONENT_KEYS = {
    "relative_strength": "rs_score",
    "trend": "trend_score",
    "market_regime": "market_regime_score",
    "volume_accumulation": "volume_score",
    "sector_rotation": "sector_score",
    "structure_trigger": "structure_score",
    "risk_reward_atr": "rr_score",
    "liquidity": "liquidity_score",
    "momentum": "momentum_score",
    "options_flow": "options_score",
    "fundamentals": "fundamental_score",
    "sentiment": "sentiment_score",
}


def _clip01(value) -> float:
    return max(0.0, min(float(value), 1.0))


def calculate_final_score(scores: dict, config: dict) -> float:
    weights = config.get("scoring_weights", {})
    terms = []

    for weight_key, score_key in COMPONENT_KEYS.items():
        weight = float(weights.get(weight_key, 0.0))
        component = _clip01(scores.get(score_key, 0.5))
        terms.append(weight * component)

    return round(float(fsum(terms)), 10)
