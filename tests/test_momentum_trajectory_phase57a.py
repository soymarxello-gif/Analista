from __future__ import annotations
import pandas as pd

from engine.momentum_trajectory import analyze_histogram_trajectory
from scoring.operational_readiness import calculate_operational_readiness
from tools.trade_decision_checklist import evaluate_checklist_row


def _trajectory(values: list[float]) -> dict:
    index = pd.date_range("2026-01-01", periods=len(values), freq="D")
    return analyze_histogram_trajectory(
        pd.Series(values, index=index),
        pd.Series([100.0] * len(values), index=index),
        prefix="daily",
        slope_window=4,
        noise_lookback=20,
    )


def test_accelerating_histogram_is_operable() -> None:
    result = _trajectory([0.0, 0.3, 0.7, 1.2, 2.0, 3.2, 5.0, 7.5, 10.8])

    assert result["daily_macd_trajectory_state"] == "ACCELERATING"
    assert result["daily_macd_non_decelerating"] is True


def test_steady_improving_histogram_is_operable() -> None:
    result = _trajectory([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])

    assert result["daily_macd_trajectory_state"] == "IMPROVING_STEADY"
    assert result["daily_macd_non_decelerating"] is True


def test_rising_but_losing_slope_is_decelerating() -> None:
    result = _trajectory([0.0, 4.0, 7.5, 10.5, 13.0, 15.0, 16.4, 17.2, 17.6])

    assert result["daily_macd_trajectory_state"] == "IMPROVING_BUT_DECELERATING"
    assert result["daily_macd_non_decelerating"] is False


def test_declining_histogram_is_not_operable() -> None:
    result = _trajectory([8.0, 7.5, 6.8, 5.8, 4.5, 3.0, 1.2, -0.8, -3.0])

    assert result["daily_macd_trajectory_state"] == "DECLINING"
    assert result["daily_macd_non_decelerating"] is False


def _candidate(**overrides) -> dict:
    row = {
        "ticker": "AAA",
        "signal": "WATCHLIST",
        "recommendation": "WATCHLIST_MONITOR",
        "setup_type": "BREAKOUT",
        "final_trade_score": 90,
        "operational_readiness_score": 90,
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
        "actionable_entry": 100,
        "actionable_stop": 95,
        "actionable_target": 112,
        "rr": 2.4,
        "price": 100,
        "market_cap": 5_000_000_000,
        "liquidity_pass": True,
        "scenario_status": "VALID_TRIGGER",
        "scenario_eligible_for_backtest": True,
        "execution_readiness_status": "EXECUTION_READY_REVIEW",
        "shadow_level_status": "VALID",
        "entry_timing_status": "ON_TIME",
        "ema20_extension_status": "HEALTHY",
        "macd_histogram_state": "MACD_HIST_POSITIVE_EXPANDING",
        "weekly_macd_histogram_state": "WEEKLY_MACD_HIST_IMPROVING",
        "daily_macd_trajectory_state": "ACCELERATING",
        "weekly_macd_trajectory_state": "IMPROVING_STEADY",
        "momentum_operability_status": "CONFIRMED_NON_DECELERATING",
    }
    row.update(overrides)
    return row


def test_daily_deceleration_blocks_high_quality_and_buy_now() -> None:
    result = evaluate_checklist_row(
        _candidate(
            daily_macd_trajectory_state="IMPROVING_BUT_DECELERATING",
            momentum_operability_status="REJECT_MOMENTUM",
        )
    )

    assert result["checklist_status"] == "BLOCKED"
    assert result["automatic_posttest_status"] == "NOT_BUY_NOW"


def test_weekly_deceleration_blocks_high_quality_and_buy_now() -> None:
    result = evaluate_checklist_row(
        _candidate(
            weekly_macd_trajectory_state="IMPROVING_BUT_DECELERATING",
            momentum_operability_status="REJECT_MOMENTUM",
        )
    )

    assert result["checklist_status"] == "BLOCKED"
    assert result["automatic_posttest_status"] == "NOT_BUY_NOW"


def test_wait_for_confirmation_is_monitoring_not_engine_block() -> None:
    result = calculate_operational_readiness(
        _candidate(
            scenario_status="WAIT_FOR_CONFIRMATION",
            scenario_eligible_for_backtest=False,
        )
    )

    assert result["engine_block_reason"] == ""
    assert result["operational_status"] == "MONITOR_NEXT_TRIGGER"


def test_sector_bearish_penalizes_but_does_not_block_leading_ticker() -> None:
    result = calculate_operational_readiness(
        _candidate(
            sector_weekly_macd_state="SECTOR_MACD_BEARISH",
            rs_score=0.92,
            relative_volume=1.3,
        )
    )

    assert result["engine_block_reason"] == ""
    assert result["sector_leadership_override_status"] == "LEADERSHIP_OVERRIDE"
