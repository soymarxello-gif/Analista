from __future__ import annotations

from math import fsum, isfinite

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
    context_only = set(
        config.get("selection_policy", {}).get(
            "context_only_components", ("market_regime", "fundamentals", "options_flow", "sentiment")
        )
    )
    terms = []
    active_weight = 0.0

    for weight_key, score_key in COMPONENT_KEYS.items():
        if weight_key in context_only:
            continue
        weight = float(weights.get(weight_key, 0.0))
        raw = scores.get(score_key)
        if raw is None:
            continue
        try:
            numeric = float(raw)
        except (TypeError, ValueError):
            continue
        if not isfinite(numeric):
            continue
        component = _clip01(numeric)
        terms.append(weight * component)
        active_weight += weight

    if active_weight <= 0:
        return 0.0
    return round(float(fsum(terms)) * 100.0 / active_weight, 10)
