from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.daily_operator_index import (
    build_daily_operator_index_markdown,
    collect_operator_index_data,
    save_daily_operator_index,
)


def _make_reports(tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    reports.mkdir()

    (reports / "daily_validation_summary.txt").write_text(
        "=== ANALISTA DAILY VALIDATION SUMMARY ===\nStatus: PASS\n",
        encoding="utf-8",
    )

    pd.DataFrame(
        [
            {
                "rank": 1,
                "ticker": "AAA",
                "signal": "TRIGGER_CONFIRMED",
                "recommendation": "MANUAL_REVIEW_TRIGGER_CONFIRMED",
                "setup_type": "BREAKOUT",
                "final_trade_score": 88,
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "rr": 2.0,
            },
            {
                "rank": 2,
                "ticker": "BBB",
                "signal": "WATCHLIST",
                "recommendation": "RECHECK_LIVE_QUOTE",
                "setup_type": "PULLBACK",
                "final_trade_score": 82,
                "quote_status": "STALE_POSSIBLE",
                "execution_quote_quality": "LOW",
                "rr": 3.0,
            },
        ]
    ).to_csv(reports / "latest_scan_audited.csv", index=False)

    pd.DataFrame(
        [
            {
                "rank": 1,
                "ticker": "AAA",
                "signal": "TRIGGER_CONFIRMED",
                "recommendation": "MANUAL_REVIEW_TRIGGER_CONFIRMED",
                "setup_type": "BREAKOUT",
                "final_trade_score": 88,
                "setup_persistence_score": 85,
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "rr": 2.0,
                "quote_recheck_priority": "",
            },
            {
                "rank": 2,
                "ticker": "BBB",
                "signal": "WATCHLIST",
                "recommendation": "RECHECK_LIVE_QUOTE",
                "setup_type": "PULLBACK",
                "final_trade_score": 82,
                "setup_persistence_score": 79,
                "quote_status": "STALE_POSSIBLE",
                "execution_quote_quality": "LOW",
                "rr": 3.0,
                "quote_recheck_priority": "HIGH",
            },
        ]
    ).to_csv(reports / "manual_review_latest.csv", index=False)

    pd.DataFrame(
        [
            {
                "rank": 1,
                "ticker": "AAA",
                "signal": "TRIGGER_CONFIRMED",
                "recommendation": "MANUAL_REVIEW_TRIGGER_CONFIRMED",
                "setup_type": "BREAKOUT",
                "final_trade_score": 88,
                "setup_persistence_score": 85,
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "rr": 2.0,
            }
        ]
    ).to_csv(reports / "manual_review_top.csv", index=False)

    pd.DataFrame(
        [
            {
                "trade_id": "T1",
                "ticker": "AAA",
                "entry": 100,
                "current_price": 105,
                "unrealized_pnl_pct": 0.05,
                "unrealized_r_multiple": 1.0,
                "distance_to_stop_pct": 0.10,
                "distance_to_target_pct": 0.08,
                "snapshot_note": "OPEN_PROFIT",
            }
        ]
    ).to_csv(reports / "open_trades_snapshot_latest.csv", index=False)

    pd.DataFrame(
        [
            {
                "group": "OVERALL",
                "group_value": "ALL_CLOSED",
                "total_trades": 3,
                "wins": 2,
                "losses": 1,
                "breakeven": 0,
                "win_rate": 0.666667,
                "avg_pnl_pct": 0.04,
                "avg_r_multiple": 0.8,
                "total_r_multiple": 2.4,
                "best_trade_r": 2.0,
                "worst_trade_r": -1.0,
            }
        ]
    ).to_csv(reports / "trade_outcome_analytics_latest.csv", index=False)

    return reports


def test_collect_operator_index_data_counts_core_items(tmp_path: Path):
    _make_reports(tmp_path)

    data = collect_operator_index_data(root=tmp_path)

    assert data["validation_status"] == "PASS"
    assert data["scan_rows"] == 2
    assert data["manual_review_rows"] == 2
    assert data["trigger_count"] == 1
    assert data["recheck_count"] == 1
    assert data["open_trades_rows"] == 1
    assert not data["top_candidates"].empty
    assert not data["recheck_candidates"].empty
    assert not data["open_trades"].empty
    assert not data["analytics_overall"].empty


def test_build_daily_operator_index_markdown_contains_sections(tmp_path: Path):
    _make_reports(tmp_path)

    data = collect_operator_index_data(root=tmp_path)
    text = build_daily_operator_index_markdown(data)

    assert "Analista - daily operator index" in text
    assert "## Decision gate" in text
    assert "## Abrir primero" in text
    assert "## Top manual review" in text
    assert "## RECHECK_LIVE_QUOTE" in text
    assert "## Trades abiertos" in text
    assert "## Analytics de trades cerrados" in text
    assert "## Archivos monitoreados" in text
    assert "## Recordatorio operativo" in text
    assert "RECHECK_LIVE_QUOTE" in text
    assert "TRIGGER_CONFIRMED" in text


def test_save_daily_operator_index_writes_file(tmp_path: Path):
    _make_reports(tmp_path)

    output = tmp_path / "reports" / "daily_operator_index.md"

    result = save_daily_operator_index(
        root=tmp_path,
        output_path=output,
    )

    assert result["status"] == "PASS"
    assert result["validation_status"] == "PASS"
    assert result["recheck_count"] == 1
    assert result["trigger_count"] == 1
    assert output.exists()

    text = output.read_text(encoding="utf-8")

    assert "daily operator index" in text
    assert "reports/manual_review_top.md" in text