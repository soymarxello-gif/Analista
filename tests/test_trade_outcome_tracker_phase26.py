from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.trade_outcome_tracker import (
    append_trade,
    append_trade_from_manual_review,
    build_trade_record,
    build_trade_record_from_manual_review,
    calculate_trade_metrics,
    close_trade,
    find_manual_review_row,
    init_outcomes,
    load_outcomes,
    save_outcomes_summary,
)


def test_calculate_trade_metrics_long_trade():
    result = calculate_trade_metrics(
        entry_price=100,
        stop_price=95,
        target_price=115,
    )

    assert result["risk_pct"] == 0.05
    assert result["reward_pct"] == 0.15
    assert result["rr"] == 3.0


def test_build_trade_record_defaults_open_status():
    record = build_trade_record(
        ticker="aapl",
        entry_date="2026-06-09",
        entry_price=100,
        stop_price=95,
        target_price=115,
        source_signal="WATCHLIST",
        source_recommendation="WATCHLIST_MONITOR",
    )

    assert record["ticker"] == "AAPL"
    assert record["status"] == "OPEN"
    assert record["rr"] == 3.0
    assert record["source_signal"] == "WATCHLIST"
    assert record["source_recommendation"] == "WATCHLIST_MONITOR"


def test_init_outcomes_creates_files(tmp_path: Path):
    outcomes_path = tmp_path / "reports" / "trade_outcomes.csv"
    summary_out = tmp_path / "reports" / "trade_outcomes_summary.md"

    result = init_outcomes(outcomes_path, summary_out)

    assert result["status"] == "PASS"
    assert outcomes_path.exists()
    assert summary_out.exists()


def test_append_trade_writes_row(tmp_path: Path):
    outcomes_path = tmp_path / "reports" / "trade_outcomes.csv"

    record = build_trade_record(
        ticker="MSFT",
        entry_date="2026-06-09",
        entry_price=200,
        stop_price=190,
        target_price=230,
    )

    result = append_trade(outcomes_path, record)
    df = load_outcomes(outcomes_path)

    assert result["status"] == "PASS"
    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "MSFT"


def test_close_trade_updates_outcome(tmp_path: Path):
    outcomes_path = tmp_path / "reports" / "trade_outcomes.csv"

    record = build_trade_record(
        ticker="NVDA",
        entry_date="2026-06-09",
        entry_price=100,
        stop_price=95,
        target_price=115,
    )

    append_trade(outcomes_path, record)

    result = close_trade(
        outcomes_path=outcomes_path,
        trade_id=record["trade_id"],
        exit_date="2026-06-12",
        exit_price=110,
        outcome="WIN",
    )

    df = pd.read_csv(outcomes_path)

    assert result["status"] == "PASS"
    assert df.iloc[0]["status"] == "CLOSED"
    assert df.iloc[0]["outcome"] == "WIN"
    assert round(float(df.iloc[0]["pnl_pct"]), 6) == 0.1
    assert round(float(df.iloc[0]["r_multiple"]), 6) == 2.0


def test_save_outcomes_summary_writes_markdown(tmp_path: Path):
    outcomes_path = tmp_path / "reports" / "trade_outcomes.csv"
    summary_out = tmp_path / "reports" / "trade_outcomes_summary.md"

    record = build_trade_record(
        ticker="META",
        entry_date="2026-06-09",
        entry_price=100,
        stop_price=95,
        target_price=115,
    )

    append_trade(outcomes_path, record)

    result = save_outcomes_summary(outcomes_path, summary_out)

    assert result["status"] == "PASS"
    assert summary_out.exists()
    assert "META" in summary_out.read_text(encoding="utf-8")


def test_find_manual_review_row_returns_matching_ticker(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    manual_csv = reports / "manual_review_latest.csv"

    pd.DataFrame(
        [
            {
                "ticker": "APH",
                "rank": 16,
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
            }
        ]
    ).to_csv(manual_csv, index=False)

    row = find_manual_review_row(manual_csv=manual_csv, ticker="aph")

    assert row["ticker"] == "APH"
    assert row["rank"] == 16


def test_build_trade_record_from_manual_review_uses_manual_metadata(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    manual_csv = reports / "manual_review_latest.csv"

    pd.DataFrame(
        [
            {
                "ticker": "APH",
                "rank": 16,
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "setup_type": "PULLBACK",
                "final_trade_score": 84.52,
                "setup_quality_score": 78.0,
                "setup_persistence_score": 79.0,
                "actionable_entry": 154.10,
                "actionable_stop": 149.00,
                "actionable_target": 165.00,
            }
        ]
    ).to_csv(manual_csv, index=False)

    record = build_trade_record_from_manual_review(
        manual_csv=manual_csv,
        ticker="APH",
        entry_date="2026-06-09",
    )

    assert record["ticker"] == "APH"
    assert record["entry_price"] == 154.10
    assert record["stop_price"] == 149.00
    assert record["target_price"] == 165.00
    assert record["source_rank"] == 16
    assert record["source_signal"] == "WATCHLIST"
    assert record["source_recommendation"] == "WATCHLIST_MONITOR"
    assert record["source_final_trade_score"] == 84.52
    assert record["source_setup_persistence_score"] == 79.0


def test_append_trade_from_manual_review_writes_outcome_row(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    manual_csv = reports / "manual_review_latest.csv"
    outcomes_path = reports / "trade_outcomes.csv"

    pd.DataFrame(
        [
            {
                "ticker": "UNM",
                "rank": 23,
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "setup_type": "BREAKOUT",
                "final_trade_score": 79.7,
                "setup_quality_score": 75.0,
                "setup_persistence_score": 79.0,
                "actionable_entry": 88.0,
                "actionable_stop": 84.0,
                "actionable_target": 96.0,
            }
        ]
    ).to_csv(manual_csv, index=False)

    result = append_trade_from_manual_review(
        outcomes_path=outcomes_path,
        manual_csv=manual_csv,
        ticker="UNM",
        entry_date="2026-06-09",
        notes="test from manual review",
    )

    df = pd.read_csv(outcomes_path)

    assert result["status"] == "PASS"
    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "UNM"
    assert df.iloc[0]["source_rank"] == 23
    assert df.iloc[0]["source_recommendation"] == "WATCHLIST_MONITOR"    