from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.trade_outcome_analytics import (
    build_trade_outcome_analytics_dataframe,
    calculate_group_metrics,
    filter_closed_trades,
    save_trade_outcome_analytics_reports,
    score_bucket,
)


def test_score_bucket():
    assert score_bucket(None) == "UNKNOWN"
    assert score_bucket(95) == "90_PLUS"
    assert score_bucket(85) == "80_TO_89"
    assert score_bucket(75) == "70_TO_79"
    assert score_bucket(65) == "60_TO_69"
    assert score_bucket(50) == "BELOW_60"


def test_filter_closed_trades_ignores_open():
    df = pd.DataFrame(
        [
            {"ticker": "AAA", "status": "OPEN"},
            {"ticker": "BBB", "status": "CLOSED", "outcome": "WIN", "pnl_pct": 0.10, "r_multiple": 2.0},
        ]
    )

    out = filter_closed_trades(df)

    assert len(out) == 1
    assert out.iloc[0]["ticker"] == "BBB"


def test_calculate_group_metrics_basic_win_loss():
    df = pd.DataFrame(
        [
            {"outcome": "WIN", "pnl_pct_num": 0.10, "r_multiple_num": 2.0},
            {"outcome": "LOSS", "pnl_pct_num": -0.05, "r_multiple_num": -1.0},
            {"outcome": "BREAKEVEN", "pnl_pct_num": 0.0, "r_multiple_num": 0.0},
        ]
    )

    result = calculate_group_metrics(df, group="OVERALL", group_value="ALL_CLOSED")

    assert result["total_trades"] == 3
    assert result["wins"] == 1
    assert result["losses"] == 1
    assert result["breakeven"] == 1
    assert result["win_rate"] == 0.5
    assert result["total_r_multiple"] == 1.0
    assert result["best_trade_r"] == 2.0
    assert result["worst_trade_r"] == -1.0


def test_build_trade_outcome_analytics_dataframe_adds_groups():
    df = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "status": "CLOSED",
                "outcome": "WIN",
                "pnl_pct": 0.10,
                "r_multiple": 2.0,
                "source_signal": "WATCHLIST",
                "source_recommendation": "WATCHLIST_MONITOR",
                "source_setup_type": "BREAKOUT",
                "source_final_trade_score": 85,
                "source_setup_persistence_score": 75,
            },
            {
                "ticker": "BBB",
                "status": "CLOSED",
                "outcome": "LOSS",
                "pnl_pct": -0.05,
                "r_multiple": -1.0,
                "source_signal": "WATCHLIST",
                "source_recommendation": "RECHECK_LIVE_QUOTE",
                "source_setup_type": "PULLBACK",
                "source_final_trade_score": 72,
                "source_setup_persistence_score": 82,
            },
        ]
    )

    out = build_trade_outcome_analytics_dataframe(df)

    assert not out.empty
    assert "OVERALL" in out["group"].tolist()
    assert "source_signal" in out["group"].tolist()
    assert "source_recommendation" in out["group"].tolist()
    assert "source_final_trade_score_bucket" in out["group"].tolist()

    overall = out[(out["group"] == "OVERALL") & (out["group_value"] == "ALL_CLOSED")].iloc[0]
    assert overall["total_trades"] == 2
    assert overall["wins"] == 1
    assert overall["losses"] == 1


def test_build_trade_outcome_analytics_dataframe_empty_without_closed():
    df = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "status": "OPEN",
                "outcome": "",
                "pnl_pct": "",
                "r_multiple": "",
            }
        ]
    )

    out = build_trade_outcome_analytics_dataframe(df)

    assert out.empty


def test_save_trade_outcome_analytics_reports_writes_files(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    outcomes_path = reports / "trade_outcomes.csv"
    csv_out = reports / "trade_outcome_analytics_latest.csv"
    markdown_out = reports / "trade_outcome_analytics_latest.md"

    pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "status": "CLOSED",
                "outcome": "WIN",
                "pnl_pct": 0.10,
                "r_multiple": 2.0,
                "source_signal": "WATCHLIST",
                "source_recommendation": "WATCHLIST_MONITOR",
                "source_setup_type": "BREAKOUT",
                "source_final_trade_score": 85,
                "source_setup_persistence_score": 75,
            }
        ]
    ).to_csv(outcomes_path, index=False)

    result = save_trade_outcome_analytics_reports(
        outcomes_path=outcomes_path,
        csv_out=csv_out,
        markdown_out=markdown_out,
    )

    assert result["status"] == "PASS"
    assert result["closed_trades"] == 1
    assert csv_out.exists()
    assert markdown_out.exists()

    markdown = markdown_out.read_text(encoding="utf-8")
    assert "trade outcome analytics" in markdown
    assert "Overall" in markdown