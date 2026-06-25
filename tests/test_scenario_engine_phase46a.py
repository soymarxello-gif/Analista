from __future__ import annotations

import json

import pandas as pd

from engine.scenario_engine import (
    analyze_scenario,
    apply_scenario_guardrail,
    calculate_shadow_levels,
)
from indicators.pipeline import add_all_indicators


CONFIG = {
    "indicators": {
        "moving_averages": [20, 50, 200],
        "rsi": {"period": 14},
        "macd": {"fast": 12, "slow": 26, "signal": 9},
        "atr": {"period": 14},
        "volume": {"avg_period": 20},
        "obv": {"slope_period": 20},
    }
}


def _history(
    *,
    start: float = 80.0,
    daily_step: float = 0.12,
    final_close: float | None = None,
    final_volume: float = 1_600_000,
) -> pd.DataFrame:
    closes = [start + daily_step * i + (0.22 if i % 3 else -0.18) for i in range(220)]
    for offset in range(8, 0, -1):
        closes[-offset] += (8 - offset) * 0.18
    if final_close is not None:
        closes[-1] = final_close
    frame = pd.DataFrame(
        {
            "open": [value - 0.15 for value in closes],
            "high": [value + 0.40 for value in closes],
            "low": [value - 0.40 for value in closes],
            "close": closes,
            "volume": [1_000_000] * 219 + [final_volume],
        },
        index=pd.bdate_range("2025-08-01", periods=220),
    )
    return add_all_indicators(frame, CONFIG)


def _constructive_momentum(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.loc[out.index[-6], "rsi"] = 58.0
    out.loc[out.index[-1], "rsi"] = 63.0
    out.loc[out.index[-2], "macd_hist"] = 0.10
    out.loc[out.index[-1], "macd"] = 1.20
    out.loc[out.index[-1], "macd_signal"] = 1.00
    out.loc[out.index[-1], "macd_hist"] = 0.20
    return out


def test_breakout_near_trigger_with_volume_can_be_valid() -> None:
    df = _constructive_momentum(_history())
    trigger = float(df.iloc[-1]["close"]) * 0.995

    result = analyze_scenario(
        df,
        setup_type="BREAKOUT",
        trigger_level=trigger,
        market_regime="RISK_ON",
    )

    assert result["scenario_status"] == "VALID_TRIGGER"
    assert result["scenario_trigger_confirmed"] is True
    assert result["momentum_state"] in {"STRONG", "IMPROVING"}


def test_breakout_far_above_trigger_is_late_entry() -> None:
    df = _constructive_momentum(_history())
    close = float(df.iloc[-1]["close"])

    result = analyze_scenario(
        df,
        setup_type="BREAKOUT",
        trigger_level=close * 0.90,
        market_regime="RISK_ON",
    )

    assert result["scenario_status"] == "LATE_ENTRY_OVEREXTENDED"
    assert result["engine_recommendation"] == "DO_NOT_CHASE"
    assert result["scenario_trigger_confirmed"] is False


def test_pullback_without_rejection_waits_for_confirmation() -> None:
    df = _constructive_momentum(_history(final_volume=700_000))
    last = df.index[-1]
    df.loc[last, "close"] = float(df.iloc[-1]["sma20"]) * 1.002
    df.loc[last, "open"] = df.loc[last, "close"] + 0.30
    df.loc[last, "high"] = df.loc[last, "open"] + 0.10
    df.loc[last, "low"] = df.loc[last, "close"] - 0.10

    result = analyze_scenario(
        df,
        setup_type="PULLBACK",
        trigger_level=float(df.iloc[-1]["sma20"]),
        market_regime="RISK_ON",
    )

    assert result["scenario_status"] in {"WAIT_FOR_CONFIRMATION", "WEAK_MOMENTUM"}
    assert result["scenario_trigger_confirmed"] is False


def test_pullback_exactly_on_sma20_is_recognized_as_near_support() -> None:
    df = _constructive_momentum(_history(final_volume=700_000))
    last = df.index[-1]
    support = float(df.loc[last, "sma20"])
    df.loc[last, "close"] = support
    df.loc[last, "open"] = support - 0.20
    df.loc[last, "high"] = support + 0.10
    df.loc[last, "low"] = support - 0.30

    result = analyze_scenario(
        df,
        setup_type="PULLBACK",
        trigger_level=support,
        market_regime="RISK_ON",
    )

    evidence = json.loads(result["scenario_evidence"])
    contradictions = json.loads(result["scenario_contradictions"])
    assert "price_near_moving_average_support" in evidence
    assert "price_not_near_support" not in contradictions


def test_unselected_candidate_is_not_deep_analyzed() -> None:
    result = analyze_scenario(
        _history(),
        setup_type="BREAKOUT",
        trigger_level=100,
        selected=False,
    )

    assert result["scenario_status"] == "NOT_SELECTED_FOR_DEEP_ANALYSIS"
    assert result["engine_recommendation"] == "FUNNEL_ONLY"


def test_risk_off_context_blocks_otherwise_valid_trigger() -> None:
    df = _constructive_momentum(_history())
    trigger = float(df.iloc[-1]["close"]) * 0.995

    result = analyze_scenario(
        df,
        setup_type="BREAKOUT",
        trigger_level=trigger,
        market_regime="RISK_OFF",
    )

    assert result["scenario_status"] == "CONTEXT_CONFLICT"
    assert result["scenario_trigger_confirmed"] is False


def test_guardrail_can_demote_but_never_promote() -> None:
    blocked = apply_scenario_guardrail(
        {
            "signal": "TRIGGER_CONFIRMED",
            "deep_analysis_selected": True,
            "scenario_status": "LATE_ENTRY_OVEREXTENDED",
            "scenario_trigger_confirmed": False,
        }
    )
    valid_watchlist = apply_scenario_guardrail(
        {
            "signal": "WATCHLIST",
            "deep_analysis_selected": True,
            "scenario_status": "VALID_TRIGGER",
            "scenario_trigger_confirmed": True,
        }
    )

    assert blocked["signal"] == "WATCHLIST"
    assert blocked["scenario_operability"] == "DO_NOT_CHASE"
    assert blocked["scenario_eligible_for_backtest"] is False
    assert valid_watchlist["signal"] == "WATCHLIST"
    assert valid_watchlist["scenario_eligible_for_backtest"] is True


def test_shadow_levels_are_separate_and_conservative() -> None:
    df = _constructive_momentum(_history())
    latest = df.iloc[-1]
    entry = float(latest["close"])
    atr = float(latest["atr"])
    result = calculate_shadow_levels(
        df,
        scenario={"scenario_status": "VALID_TRIGGER"},
        setup_type="BREAKOUT",
        rr_data={
            "entry": entry,
            "stop": entry - 0.5 * atr,
            "target": entry + 4.0 * atr,
        },
        config=CONFIG,
    )

    assert result["shadow_entry"] == entry
    assert result["shadow_stop_atr_multiple"] >= 1.0
    assert result["shadow_target"] <= entry + 2.0 * atr + 1e-9
    assert result["shadow_level_status"] in {"VALID", "RR_BELOW_MINIMUM"}
