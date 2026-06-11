from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.history_evolution import (
    load_history_scans,
    save_history_evolution_reports,
    summarize_ticker_history,
)


def _write_run(root: Path, run_id: str, scan_rows: list[dict], manual_rows: list[dict] | None = None):
    run_dir = root / "reports" / "history" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(scan_rows).to_csv(run_dir / "latest_scan_audited.csv", index=False)

    if manual_rows is not None:
        pd.DataFrame(manual_rows).to_csv(run_dir / "manual_review_latest.csv", index=False)

    return run_dir


def test_history_evolution_detects_promotion_to_trigger(tmp_path: Path):
    _write_run(
        tmp_path,
        "20260609_090000",
        [
            {
                "ticker": "AAA",
                "rank": 10,
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "final_trade_score": 72,
                "setup_quality_score": 80,
            }
        ],
        [{"ticker": "AAA"}],
    )

    _write_run(
        tmp_path,
        "20260610_090000",
        [
            {
                "ticker": "AAA",
                "rank": 2,
                "signal": "TRIGGER_CONFIRMED",
                "recommendation": "MANUAL_REVIEW_TRIGGER_CONFIRMED",
                "final_trade_score": 85,
                "setup_quality_score": 90,
            }
        ],
        [{"ticker": "AAA"}],
    )

    history = load_history_scans(tmp_path / "reports" / "history")
    evolution = summarize_ticker_history(history)

    row = evolution[evolution["ticker"] == "AAA"].iloc[0]

    assert row["appearances"] == 2
    assert row["latest_signal"] == "TRIGGER_CONFIRMED"
    assert bool(row["promoted_to_trigger"]) is True
    assert row["rank_delta"] == 8
    assert row["score_delta"] == 13


def test_history_evolution_detects_persistent_watchlist(tmp_path: Path):
    for idx, run_id in enumerate(["20260609_090000", "20260610_090000", "20260611_090000"], start=1):
        _write_run(
            tmp_path,
            run_id,
            [
                {
                    "ticker": "BBB",
                    "rank": idx,
                    "signal": "WATCHLIST",
                    "recommendation": "WATCHLIST_MONITOR",
                    "final_trade_score": 70 + idx,
                    "setup_quality_score": 80,
                }
            ],
            [{"ticker": "BBB"}],
        )

    history = load_history_scans(tmp_path / "reports" / "history")
    evolution = summarize_ticker_history(history)

    row = evolution[evolution["ticker"] == "BBB"].iloc[0]

    assert row["appearances"] == 3
    assert bool(row["persistent_watchlist"]) is True
    assert bool(row["promoted_to_trigger"]) is False


def test_history_evolution_detects_disappeared_from_manual_review(tmp_path: Path):
    _write_run(
        tmp_path,
        "20260609_090000",
        [
            {
                "ticker": "CCC",
                "rank": 3,
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "final_trade_score": 75,
                "setup_quality_score": 82,
            }
        ],
        [{"ticker": "CCC"}],
    )

    _write_run(
        tmp_path,
        "20260610_090000",
        [
            {
                "ticker": "CCC",
                "rank": 80,
                "signal": "AVOID",
                "recommendation": "AVOID_FOR_NOW",
                "final_trade_score": 50,
                "setup_quality_score": 55,
            }
        ],
        [],
    )

    history = load_history_scans(tmp_path / "reports" / "history")
    evolution = summarize_ticker_history(history)

    row = evolution[evolution["ticker"] == "CCC"].iloc[0]

    assert bool(row["deteriorated_signal"]) is True
    assert bool(row["disappeared_from_manual_review"]) is True


def test_save_history_evolution_reports_writes_files(tmp_path: Path):
    _write_run(
        tmp_path,
        "20260609_090000",
        [{"ticker": "AAA", "rank": 10, "signal": "WATCHLIST", "final_trade_score": 72}],
        [{"ticker": "AAA"}],
    )
    _write_run(
        tmp_path,
        "20260610_090000",
        [{"ticker": "AAA", "rank": 1, "signal": "TRIGGER_CONFIRMED", "final_trade_score": 85}],
        [{"ticker": "AAA"}],
    )

    result = save_history_evolution_reports(
        history_root=tmp_path / "reports" / "history",
        csv_out=tmp_path / "reports" / "history_evolution_latest.csv",
        markdown_out=tmp_path / "reports" / "history_evolution_latest.md",
    )

    assert result["status"] == "PASS"
    assert (tmp_path / "reports" / "history_evolution_latest.csv").exists()
    assert (tmp_path / "reports" / "history_evolution_latest.md").exists()
