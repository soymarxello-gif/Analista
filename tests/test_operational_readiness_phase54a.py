from __future__ import annotations

from scoring.operational_readiness import calculate_operational_readiness


def _row(**overrides) -> dict:
    row = {
        "signal": "WATCHLIST",
        "recommendation": "WATCHLIST_MONITOR",
        "final_trade_score": 88,
        "scenario_status": "VALID_TRIGGER",
        "momentum_state": "STRONG",
        "extension_state": "HEALTHY",
        "ema20_extension_status": "HEALTHY",
        "entry_timing_status": "ON_TIME",
        "shadow_level_status": "VALID",
        "macd_histogram_state": "MACD_HIST_POSITIVE_EXPANDING",
        "weekly_macd_histogram_state": "WEEKLY_MACD_HIST_IMPROVING",
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
    }
    row.update(overrides)
    return row


def test_weekly_macd_decelerating_reduces_operational_readiness() -> None:
    clean = calculate_operational_readiness(_row())
    decelerating = calculate_operational_readiness(
        _row(weekly_macd_histogram_state="WEEKLY_MACD_HIST_DECELERATING")
    )

    assert decelerating["operational_readiness_score"] < clean["operational_readiness_score"]
    assert "weekly_macd_decelerating" in decelerating["momentum_penalty_reason"]
    assert "weekly_macd_decelerating" in decelerating["operational_readiness_reason"]


def test_strong_ema20_caution_is_penalized_more_than_clean_timing() -> None:
    clean = calculate_operational_readiness(_row())
    caution = calculate_operational_readiness(
        _row(
            ema20_extension_status="CAUTION",
            entry_timing_status="CAUTION",
            technical_distance_ema20_atr=1.35,
            technical_distance_ema20_pct=0.03,
        )
    )

    assert caution["operational_readiness_score"] < clean["operational_readiness_score"]
    assert caution["timing_penalty_reason"] == "ema20_extension_caution"
