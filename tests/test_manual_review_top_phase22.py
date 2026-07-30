from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.manual_review_top import (
    build_manual_review_top_dataframe,
    classify_top_group,
    save_manual_review_top_reports,
)


def test_classify_high_quality_operational_candidate():
    row = {
        "signal": "WATCHLIST",
        "recommendation": "WATCHLIST_MONITOR",
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
        "final_trade_score": 78,
        "setup_quality_score": 75,
        "operational_readiness_score": 85,
        "setup_persistence_score": 70,
        "rr": 2.1,
        "scenario_status": "VALID_TRIGGER",
        "scenario_eligible_for_backtest": True,
        "shadow_level_status": "VALID",
        "entry_timing_status": "ON_TIME",
        "ema20_extension_status": "HEALTHY",
        "macd_histogram_state": "MACD_HIST_POSITIVE_EXPANDING",
        "weekly_macd_histogram_state": "WEEKLY_MACD_HIST_IMPROVING",
    }

    assert classify_top_group(row) == "1_ALTA_CALIDAD_OPERATIVA"


def test_classify_quote_recheck_candidate():
    row = {
        "signal": "WATCHLIST",
        "recommendation": "RECHECK_LIVE_QUOTE",
        "quote_status": "STALE_POSSIBLE",
        "execution_quote_quality": "LOW",
        "final_trade_score": 85,
        "setup_quality_score": 90,
        "setup_persistence_score": 79,
        "rr": 2.5,
    }

    assert classify_top_group(row) == "2_REQUIERE_RECHECK_QUOTE"


def test_classify_deteriorated_candidate():
    row = {
        "signal": "AVOID",
        "recommendation": "AVOID_FOR_NOW",
        "setup_persistence_bucket": "D_WEAK_OR_DETERIORATED",
        "persistence_penalty_reason": "signal_deteriorated",
    }

    assert classify_top_group(row) == "4_DETERIORADO_O_DEBIL"


def test_build_manual_review_top_preserves_group_order():
    df = pd.DataFrame(
        [
            {
                "rank": 2,
                "ticker": "BBB",
                "signal": "WATCHLIST",
                "recommendation": "RECHECK_LIVE_QUOTE",
                "quote_status": "STALE_POSSIBLE",
                "execution_quote_quality": "LOW",
                "setup_persistence_score": 79,
                "final_trade_score": 85,
                "setup_quality_score": 80,
                "rr": 2.0,
            },
            {
                "rank": 1,
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "operational_readiness_score": 88,
                "setup_persistence_score": 75,
                "final_trade_score": 80,
                "setup_quality_score": 78,
                "rr": 2.2,
                "scenario_status": "VALID_TRIGGER",
                "scenario_eligible_for_backtest": True,
                "shadow_level_status": "VALID",
                "entry_timing_status": "ON_TIME",
                "ema20_extension_status": "HEALTHY",
                "macd_histogram_state": "MACD_HIST_POSITIVE_EXPANDING",
                "weekly_macd_histogram_state": "WEEKLY_MACD_HIST_IMPROVING",
            },
        ]
    )

    out = build_manual_review_top_dataframe(df)

    assert out.iloc[0]["ticker"] == "AAA"
    assert out.iloc[0]["_top_group"] == "1_ALTA_CALIDAD_OPERATIVA"
    assert out.iloc[1]["ticker"] == "BBB"
    assert out.iloc[1]["_top_group"] == "2_REQUIERE_RECHECK_QUOTE"


def test_manual_review_top_orders_high_quality_by_operational_readiness_first():
    def row(ticker: str, rank: int, readiness: float, trade_score: float) -> dict:
        return {
            "rank": rank,
            "ticker": ticker,
            "signal": "WATCHLIST",
            "recommendation": "WATCHLIST_MONITOR",
            "quote_status": "VALID",
            "execution_quote_quality": "HIGH",
            "operational_readiness_score": readiness,
            "setup_persistence_score": 75,
            "final_trade_score": trade_score,
            "setup_quality_score": 82,
            "rr": 2.0,
            "scenario_status": "VALID_TRIGGER",
            "scenario_eligible_for_backtest": True,
            "shadow_level_status": "VALID",
            "entry_timing_status": "ON_TIME",
            "ema20_extension_status": "HEALTHY",
            "macd_histogram_state": "MACD_HIST_POSITIVE_EXPANDING",
            "weekly_macd_histogram_state": "WEEKLY_MACD_HIST_IMPROVING",
        }

    out = build_manual_review_top_dataframe(
        pd.DataFrame(
            [
                row("AAA", rank=1, readiness=81, trade_score=95),
                row("BBB", rank=2, readiness=92, trade_score=88),
            ]
        )
    )

    assert out["ticker"].tolist()[:2] == ["BBB", "AAA"]


def test_manual_review_top_zero_group_limit_keeps_all_candidates():
    rows = []
    for index in range(25):
        rows.append(
            {
                "rank": index + 1,
                "ticker": f"AAA{index}",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "operational_readiness_score": 70,
                "setup_persistence_score": 60,
                "final_trade_score": 72,
                "setup_quality_score": 70,
                "rr": 2.0,
                "scenario_status": "WAIT_FOR_CONFIRMATION",
                "scenario_eligible_for_backtest": False,
            }
        )

    out = build_manual_review_top_dataframe(pd.DataFrame(rows), per_group_limit=0)

    assert len(out) == 25


def test_save_manual_review_top_reports_writes_files(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    manual_csv = reports / "manual_review_latest.csv"

    pd.DataFrame(
        [
            {
                "rank": 1,
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "operational_readiness_score": 88,
                "setup_persistence_score": 75,
                "final_trade_score": 80,
                "setup_quality_score": 78,
                "rr": 2.2,
                "scenario_status": "VALID_TRIGGER",
                "scenario_eligible_for_backtest": True,
                "shadow_level_status": "VALID",
                "entry_timing_status": "ON_TIME",
                "ema20_extension_status": "HEALTHY",
                "macd_histogram_state": "MACD_HIST_POSITIVE_EXPANDING",
                "weekly_macd_histogram_state": "WEEKLY_MACD_HIST_IMPROVING",
            }
        ]
    ).to_csv(manual_csv, index=False)

    result = save_manual_review_top_reports(
        manual_csv=manual_csv,
        csv_out=reports / "manual_review_top.csv",
        markdown_out=reports / "manual_review_top.md",
    )

    assert result["status"] == "PASS"
    assert (reports / "manual_review_top.csv").exists()
    assert (reports / "manual_review_top.md").exists()


def test_invalid_shadow_or_late_ema20_prevents_high_quality_top_group():
    base = {
        "signal": "WATCHLIST",
        "recommendation": "WATCHLIST_MONITOR",
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
        "final_trade_score": 90,
        "setup_quality_score": 88,
        "operational_readiness_score": 90,
        "setup_persistence_score": 80,
        "rr": 2.1,
        "scenario_status": "VALID_TRIGGER",
        "scenario_eligible_for_backtest": True,
        "shadow_level_status": "VALID",
        "entry_timing_status": "ON_TIME",
        "ema20_extension_status": "HEALTHY",
        "macd_histogram_state": "MACD_HIST_POSITIVE_EXPANDING",
        "weekly_macd_histogram_state": "WEEKLY_MACD_HIST_IMPROVING",
    }

    shadow_invalid = dict(base, shadow_level_status="RR_BELOW_MINIMUM")
    ema_late = dict(base, ema20_extension_status="LATE_ENTRY")

    assert classify_top_group(shadow_invalid) == "1B_REVISION_OPERATIVA_PRIORITARIA"
    assert classify_top_group(ema_late) == "3_PERSISTENTE_NO_ACCIONABLE_TODAVIA"


def test_weekly_macd_decelerating_prevents_high_quality_top_group():
    row = {
        "signal": "WATCHLIST",
        "recommendation": "WATCHLIST_MONITOR",
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
        "final_trade_score": 90,
        "setup_quality_score": 88,
        "operational_readiness_score": 90,
        "setup_persistence_score": 80,
        "rr": 2.1,
        "scenario_status": "VALID_TRIGGER",
        "scenario_eligible_for_backtest": True,
        "shadow_level_status": "VALID",
        "entry_timing_status": "ON_TIME",
        "ema20_extension_status": "HEALTHY",
        "macd_histogram_state": "MACD_HIST_POSITIVE_EXPANDING",
        "weekly_macd_histogram_state": "WEEKLY_MACD_HIST_DECELERATING",
    }

    assert classify_top_group(row) == "4_DETERIORADO_O_DEBIL"
