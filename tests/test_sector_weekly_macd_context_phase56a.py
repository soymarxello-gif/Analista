from __future__ import annotations

import pandas as pd

from market.sector_rotation import (
    _classify_sector_macd_histogram,
    calculate_sector_benchmark_context,
    sector_benchmark_symbols_for_meta,
)
from scoring.operational_readiness import calculate_operational_readiness
from tools.simple_candidate_posttest import select_top_candidates
from tools.trade_decision_checklist import evaluate_checklist_row


def _base_candidate(**overrides) -> dict:
    row = {
        "ticker": "AAA",
        "signal": "WATCHLIST",
        "recommendation": "WATCHLIST_MONITOR",
        "checklist_status": "HIGH_QUALITY_REVIEW",
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
        "scenario_status": "VALID_TRIGGER",
        "scenario_eligible_for_backtest": True,
        "execution_readiness_status": "EXECUTION_READY_REVIEW",
        "engine_block_reason": "",
        "shadow_level_status": "VALID",
        "entry_timing_status": "ON_TIME",
        "ema20_extension_status": "HEALTHY",
        "macd_histogram_state": "MACD_HIST_POSITIVE_EXPANDING",
        "weekly_macd_histogram_state": "WEEKLY_MACD_HIST_IMPROVING",
        "technical_prefilter_status": "PASS",
        "setup_type": "PULLBACK",
        "market_cap": 5_000_000_000,
        "liquidity_pass": True,
        "price": 100.0,
        "rr": 2.0,
        "actionable_entry": 100.0,
        "actionable_stop": 95.0,
        "actionable_target": 110.0,
        "final_trade_score": 90.0,
        "setup_quality_score": 90.0,
        "operational_readiness_score": 90.0,
        "automatic_posttest_status": "BUY_NOW",
    }
    row.update(overrides)
    return row


def test_sector_macd_histogram_accelerating() -> None:
    result = _classify_sector_macd_histogram(latest=0.55, previous=0.30, two_ago=0.10)

    assert result["sector_weekly_macd_state"] == "SECTOR_MACD_ACCELERATING"
    assert result["sector_weekly_macd_acceleration_state"] == "ACCELERATING"
    assert result["sector_context_status"] == "SUPPORTIVE"


def test_sector_macd_histogram_improving_but_decelerating() -> None:
    result = _classify_sector_macd_histogram(latest=0.35, previous=0.30, two_ago=0.10)

    assert result["sector_weekly_macd_state"] == "SECTOR_MACD_IMPROVING_BUT_DECELERATING"
    assert result["sector_weekly_macd_acceleration_state"] == "DECELERATING"
    assert result["sector_context_status"] == "WATCH"


def test_sector_macd_histogram_decelerating() -> None:
    result = _classify_sector_macd_histogram(latest=0.20, previous=0.35, two_ago=0.40)

    assert result["sector_weekly_macd_state"] == "SECTOR_MACD_DECELERATING"
    assert result["sector_context_status"] == "RISK"


def test_sector_macd_histogram_bearish() -> None:
    result = _classify_sector_macd_histogram(latest=-0.40, previous=-0.25, two_ago=-0.10)

    assert result["sector_weekly_macd_state"] == "SECTOR_MACD_BEARISH"
    assert result["sector_context_status"] == "RISK"


def test_sector_benchmark_symbols_use_spdr_mapping_without_tradable_universe() -> None:
    meta = pd.DataFrame(
        [
            {"ticker": "MSFT", "sector": "Technology"},
            {"ticker": "JPM", "sector": "Financial Services"},
            {"ticker": "UNKNOWN", "sector": "Mystery"},
        ]
    )

    assert sector_benchmark_symbols_for_meta(meta, {}) == ["XLF", "XLK"]


def test_sector_context_fields_are_attached_by_ticker() -> None:
    meta = pd.DataFrame([{"ticker": "MSFT", "sector": "Technology"}])
    index = pd.date_range("2025-01-03", periods=260, freq="B")
    frame = pd.DataFrame({"close": range(100, 360), "adj_close": range(100, 360)}, index=index)

    out = calculate_sector_benchmark_context(meta, {"XLK": frame}, {})

    assert out.loc[0, "ticker"] == "MSFT"
    assert out.loc[0, "sector_benchmark_symbol"] == "XLK"
    assert out.loc[0, "sector_weekly_macd_state"].startswith("SECTOR_MACD_")


def test_sector_decelerating_is_context_warning_not_hard_block() -> None:
    result = evaluate_checklist_row(
        _base_candidate(sector_weekly_macd_state="SECTOR_MACD_DECELERATING")
    )

    assert result["checklist_status"] == "HIGH_QUALITY_REVIEW"
    assert "sector_weekly_macd_sector_macd_decelerating" in result["checklist_warnings"]
    assert result["automatic_posttest_status"] == "BUY_NOW"


def test_sector_improving_but_decelerating_does_not_override_ticker_momentum() -> None:
    df = pd.DataFrame(
        [
            _base_candidate(
                sector_weekly_macd_state="SECTOR_MACD_IMPROVING_BUT_DECELERATING",
                sector_context_status="WATCH",
            )
        ]
    )

    selected = select_top_candidates(df, top_n=5)
    assert selected["ticker"].tolist() == ["AAA"]


def test_sector_macd_does_not_modify_p0_quote_or_signal_fields() -> None:
    row = _base_candidate(
        signal="WATCHLIST",
        quote_status="MISSING",
        execution_quote_quality="LOW",
        sector_weekly_macd_state="SECTOR_MACD_ACCELERATING",
    )

    result = calculate_operational_readiness(row, {})

    assert row["signal"] == "WATCHLIST"
    assert row["quote_status"] == "MISSING"
    assert row["execution_quote_quality"] == "LOW"
    assert result["execution_readiness_status"] == "NEEDS_LIVE_QUOTE_RECHECK"
