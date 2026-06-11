from __future__ import annotations

import json


def _clip01(value) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except Exception:
        return 0.5


def _weighted_average(components: dict[str, float], weights: dict[str, float]) -> float:
    total_weight = sum(float(weights.get(k, 0.0)) for k in components)

    if total_weight <= 0:
        return 0.5

    weighted_sum = sum(
        float(weights.get(k, 0.0)) * _clip01(v)
        for k, v in components.items()
    )

    return _clip01(weighted_sum / total_weight)


def calculate_final_score(scores: dict, config: dict) -> float:
    """
    Legacy/global score.

    Keep this unchanged in behavior for backward compatibility.
    Existing ranking still uses final_score during Phase 4.
    """
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


def calculate_trade_score_breakdown(scores: dict, row_context: dict | None = None) -> dict:
    """
    Phase 4 non-destructive scoring layer.

    Adds interpretable scores without replacing final_score/ranking yet.

    Scores are returned on a 0-100 scale:
    - asset_quality_score: general asset quality
    - setup_quality_score: quality of the actual swing setup
    - context_score: market/sector context
    - institutional_score: options/institutional confirmation proxy
    - final_trade_score: operational score prioritizing setup quality
    """
    row_context = row_context or {}

    asset_components = {
        "trend": scores.get("trend_score", 0.5),
        "relative_strength": scores.get("rs_score", 0.5),
        "liquidity": scores.get("liquidity_score", 0.5),
        "momentum": scores.get("momentum_score", 0.5),
        "fundamentals": scores.get("fundamental_score", 0.5),
    }
    asset_weights = {
        "trend": 0.30,
        "relative_strength": 0.30,
        "liquidity": 0.15,
        "momentum": 0.15,
        "fundamentals": 0.10,
    }

    setup_components = {
        "structure": scores.get("structure_score", 0.5),
        "risk_reward": scores.get("rr_score", 0.5),
        "volume": scores.get("volume_score", 0.5),
        "trigger": 1.0 if row_context.get("trigger_confirmed") is True else 0.55,
    }
    setup_weights = {
        "structure": 0.40,
        "risk_reward": 0.30,
        "volume": 0.20,
        "trigger": 0.10,
    }

    context_components = {
        "market_regime": scores.get("market_regime_score", 0.5),
        "sector": scores.get("sector_score", 0.5),
    }
    context_weights = {
        "market_regime": 0.55,
        "sector": 0.45,
    }

    institutional_components = {
        "options": scores.get("options_score", 0.5),
        "sentiment": scores.get("sentiment_score", 0.5),
    }
    institutional_weights = {
        "options": 0.75,
        "sentiment": 0.25,
    }

    asset_quality = _weighted_average(asset_components, asset_weights)
    setup_quality = _weighted_average(setup_components, setup_weights)
    context_score = _weighted_average(context_components, context_weights)
    institutional_score = _weighted_average(institutional_components, institutional_weights)

    final_trade = (
        0.50 * setup_quality
        + 0.25 * asset_quality
        + 0.15 * context_score
        + 0.10 * institutional_score
    )

    setup_type = row_context.get("setup_type")
    if setup_type in {None, "", "NO_VALID_SETUP"}:
        final_trade = min(final_trade, 0.49)

    result = {
        "asset_quality_score": round(asset_quality * 100, 2),
        "setup_quality_score": round(setup_quality * 100, 2),
        "context_score": round(context_score * 100, 2),
        "institutional_score": round(institutional_score * 100, 2),
        "final_trade_score": round(final_trade * 100, 2),
        "score_breakdown": {
            "asset_components": {k: round(_clip01(v) * 100, 2) for k, v in asset_components.items()},
            "setup_components": {k: round(_clip01(v) * 100, 2) for k, v in setup_components.items()},
            "context_components": {k: round(_clip01(v) * 100, 2) for k, v in context_components.items()},
            "institutional_components": {
                k: round(_clip01(v) * 100, 2)
                for k, v in institutional_components.items()
            },
            "weights": {
                "final_trade_score": {
                    "setup_quality_score": 0.50,
                    "asset_quality_score": 0.25,
                    "context_score": 0.15,
                    "institutional_score": 0.10,
                }
            },
        },
    }

    # CSV-friendly representation. JSON reports can later use the dict if needed.
    result["score_breakdown_json"] = json.dumps(result["score_breakdown"], ensure_ascii=False)

    return result