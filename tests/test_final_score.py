from __future__ import annotations

import pytest

from scoring.final_score import calculate_final_score
from scoring.fundamental_score import score_fundamentals

WEIGHTS = {
    "relative_strength": 11.4,
    "trend": 11.0,
    "market_regime": 10.7,
    "volume_accumulation": 10.3,
    "sector_rotation": 9.5,
    "structure_trigger": 9.0,
    "risk_reward_atr": 8.4,
    "liquidity": 7.6,
    "momentum": 6.9,
    "options_flow": 6.1,
    "fundamentals": 5.1,
    "sentiment": 4.0,
}

FULL_SCORES = {
    "rs_score": 1.0,
    "trend_score": 1.0,
    "market_regime_score": 1.0,
    "volume_score": 1.0,
    "sector_score": 1.0,
    "structure_score": 1.0,
    "rr_score": 1.0,
    "liquidity_score": 1.0,
    "momentum_score": 1.0,
    "options_score": 1.0,
    "fundamental_score": 1.0,
    "sentiment_score": 1.0,
}


def test_final_score_all_components_full_equals_100():
    result = calculate_final_score(FULL_SCORES, {"scoring_weights": WEIGHTS})
    assert result == pytest.approx(100.0, abs=1e-9)


def test_final_score_clips_components_to_0_1():
    cfg = {"scoring_weights": {"relative_strength": 100.0}}
    assert calculate_final_score({"rs_score": 2.5}, cfg) == pytest.approx(100.0)
    assert calculate_final_score({"rs_score": -1.0}, cfg) == pytest.approx(0.0)


def test_macro_fundamentals_options_and_sentiment_never_change_selection_score():
    config = {
        "scoring_weights": WEIGHTS,
        "selection_policy": {
            "context_only_components": ["market_regime", "fundamentals", "options_flow", "sentiment"]
        },
    }
    technical = {**FULL_SCORES, "market_regime_score": 0, "fundamental_score": 0, "options_score": 0, "sentiment_score": 0}
    supportive = {**technical, "market_regime_score": 1, "fundamental_score": 1, "options_score": 1, "sentiment_score": 1}

    assert calculate_final_score(technical, config) == calculate_final_score(supportive, config)


def test_missing_context_fields_do_not_reduce_selection_score():
    technical = {
        key: value
        for key, value in FULL_SCORES.items()
        if key not in {"market_regime_score", "fundamental_score", "options_score", "sentiment_score"}
    }
    assert calculate_final_score(technical, {"scoring_weights": WEIGHTS}) == pytest.approx(100.0)


def test_missing_technical_component_is_ignored_and_available_weights_are_renormalized():
    config = {"scoring_weights": {"trend": 60.0, "volume_accumulation": 40.0}}
    assert calculate_final_score({"trend_score": 0.8, "volume_score": None}, config) == pytest.approx(80.0)


def test_nearby_earnings_warns_without_penalizing_fundamental_context_score():
    config = {"fundamentals": {"earnings_risk": {"warn_if_days_to_earnings_lte": 7}}}
    base = {
        "revenue_growth": 0.15,
        "earnings_growth": 0.12,
        "operating_margins": 0.20,
        "profit_margins": 0.15,
        "debt_to_equity": 80,
        "return_on_equity": 0.18,
    }
    imminent = score_fundamentals({**base, "days_to_earnings": 2}, config)
    distant = score_fundamentals({**base, "days_to_earnings": 30}, config)

    assert imminent["fundamental_score"] == distant["fundamental_score"]
    assert imminent["earnings_veto"] is False
    assert imminent["earnings_penalty"] is False
    assert imminent["earnings_warning"] is True
