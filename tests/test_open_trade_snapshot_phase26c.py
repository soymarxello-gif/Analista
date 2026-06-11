from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.open_trade_snapshot import (
    build_open_trade_snapshot_dataframe,
    calculate_open_trade_snapshot_row,
    load_open_trades,
    save_open_trade_snapshot_reports,
)


def test_load_open_trades_filters_only_open(tmp_path: Path):
    outcomes_path = tmp_path / "reports" / "trade_outcomes.csv"
    outcomes_path.parent.mkdir()

    pd.DataFrame(
        [
            {"trade_id": "1", "ticker": "AAA", "status": "OPEN"},
            {"trade_id": "2", "ticker": "BBB", "status": "CLOSED"},
        ]
    ).to_csv(outcomes_path, index=False)

    out = load_open_trades(outcomes_path)

    assert len(out) == 1
    assert out.iloc[0]["ticker"] == "AAA"


def test_calculate_open_trade_snapshot_row_open_profit():
    row = calculate_open_trade_snapshot_row(
        trade={
            "trade_id": "1",
            "ticker": "AAA",
            "entry_date": "2026-06-09",
            "entry_price": 100,
            "stop_price": 95,
            "target_price": 115,
        },
        current_price=110,
        price_source="fake",
        price_fetch_status="PASS",
        price_fetch_error="",
    )

    assert row["ticker"] == "AAA"
    assert row["unrealized_pnl_pct"] == 0.1
    assert row["unrealized_r_multiple"] == 2.0
    assert row["trade_status_note"] == "OPEN_PROFIT"


def test_calculate_open_trade_snapshot_row_below_stop():
    row = calculate_open_trade_snapshot_row(
        trade={
            "trade_id": "1",
            "ticker": "AAA",
            "entry_price": 100,
            "stop_price": 95,
            "target_price": 115,
        },
        current_price=94,
        price_source="fake",
        price_fetch_status="PASS",
        price_fetch_error="",
    )

    assert row["trade_status_note"] == "AT_OR_BELOW_STOP"


def test_build_open_trade_snapshot_dataframe_with_fake_fetcher(tmp_path: Path):
    outcomes_path = tmp_path / "reports" / "trade_outcomes.csv"
    outcomes_path.parent.mkdir()

    pd.DataFrame(
        [
            {
                "trade_id": "1",
                "ticker": "AAA",
                "entry_date": "2026-06-09",
                "entry_price": 100,
                "stop_price": 95,
                "target_price": 115,
                "status": "OPEN",
                "source_signal": "WATCHLIST",
                "source_recommendation": "WATCHLIST_MONITOR",
            }
        ]
    ).to_csv(outcomes_path, index=False)

    def fake_fetcher(ticker: str) -> dict:
        return {
            "ticker": ticker,
            "current_price": 110,
            "price_source": "fake",
            "price_fetch_status": "PASS",
            "price_fetch_error": "",
        }

    out = build_open_trade_snapshot_dataframe(
        outcomes_path=outcomes_path,
        price_fetcher=fake_fetcher,
    )

    assert len(out) == 1
    assert out.iloc[0]["ticker"] == "AAA"
    assert out.iloc[0]["unrealized_r_multiple"] == 2.0


def test_save_open_trade_snapshot_reports_writes_files(tmp_path: Path):
    outcomes_path = tmp_path / "reports" / "trade_outcomes.csv"
    csv_out = tmp_path / "reports" / "open_trades_snapshot_latest.csv"
    markdown_out = tmp_path / "reports" / "open_trades_snapshot_latest.md"
    outcomes_path.parent.mkdir()

    pd.DataFrame(
        [
            {
                "trade_id": "1",
                "ticker": "AAA",
                "entry_date": "2026-06-09",
                "entry_price": 100,
                "stop_price": 95,
                "target_price": 115,
                "status": "CLOSED",
            }
        ]
    ).to_csv(outcomes_path, index=False)

    result = save_open_trade_snapshot_reports(
        outcomes_path=outcomes_path,
        csv_out=csv_out,
        markdown_out=markdown_out,
    )

    assert result["status"] == "PASS"
    assert csv_out.exists()
    assert markdown_out.exists()