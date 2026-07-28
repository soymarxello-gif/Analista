from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools import simple_candidate_posttest as posttest


def test_select_top_candidates_uses_operational_readiness_then_trade_score() -> None:
    def row(ticker: str, readiness: float, trade_score: float, status: str = "BUY_NOW") -> dict:
        return {
            "ticker": ticker,
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
            "weekly_macd_histogram_state": "WEEKLY_MACD_HIST_IMPROVING",
            "rr": 2.0,
            "actionable_entry": 100.0,
            "actionable_stop": 95.0,
            "actionable_target": 110.0,
            "operational_readiness_score": readiness,
            "final_trade_score": trade_score,
            "automatic_posttest_status": status,
        }

    df = pd.DataFrame(
        [
            row("BBB", readiness=70, trade_score=90),
            row("AAA", readiness=80, trade_score=75),
            row("CCC", readiness=99, trade_score=99, status="NOT_BUY_NOW"),
        ]
    )

    selected = posttest.select_top_candidates(df, top_n=2)

    assert selected["ticker"].tolist() == ["AAA", "BBB"]
    assert "CCC" not in selected["ticker"].tolist()
    assert set(selected["automatic_posttest_status"]) == {"BUY_NOW"}


def test_weekly_macd_must_improve_for_buy_now_memory() -> None:
    df = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "checklist_status": "HIGH_QUALITY_REVIEW",
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "scenario_status": "VALID_TRIGGER",
                "scenario_eligible_for_backtest": True,
                "execution_readiness_status": "EXECUTION_READY_REVIEW",
                "shadow_level_status": "VALID",
                "entry_timing_status": "ON_TIME",
                "ema20_extension_status": "HEALTHY",
                "weekly_macd_histogram_state": "WEEKLY_MACD_HIST_DECELERATING",
                "rr": 2.0,
                "actionable_entry": 100.0,
                "actionable_stop": 95.0,
                "actionable_target": 110.0,
                "operational_readiness_score": 90,
                "final_trade_score": 90,
                "automatic_posttest_status": "BUY_NOW",
            }
        ]
    )

    assert posttest.select_top_candidates(df, top_n=5).empty


def test_save_reports_generates_outputs(tmp_path: Path) -> None:
    result = {
        "status": "WARN",
        "rows": 0,
        "report_sessions_available": 0,
        "horizons": [5, 10, 15],
        "horizon_summary": {},
        "recommendations": ["need_more_report_history"],
        "notice": posttest.NOTICE,
        "rows_data": [],
    }

    payload = posttest.save_reports(
        result,
        csv_out=tmp_path / "posttest.csv",
        json_out=tmp_path / "posttest.json",
        markdown_out=tmp_path / "posttest.md",
    )

    assert payload["status"] == "WARN"
    assert (tmp_path / "posttest.csv").exists()
    assert (tmp_path / "posttest.json").exists()
    assert (tmp_path / "posttest.md").exists()
    assert "No automatic trading" in (tmp_path / "posttest.md").read_text(encoding="utf-8")
