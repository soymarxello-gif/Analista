from __future__ import annotations

from pathlib import Path
import json

import pandas as pd

from tools.daily_operator_index import (
    build_daily_operator_index_markdown,
    collect_operator_index_data,
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
                "signal": "WATCHLIST",
                "recommendation": "RECHECK_LIVE_QUOTE",
                "setup_type": "BREAKOUT",
                "final_trade_score": 82,
                "quote_status": "STALE_POSSIBLE",
                "execution_quote_quality": "LOW",
                "rr": 3.0,
            }
        ]
    ).to_csv(reports / "latest_scan_audited.csv", index=False)

    pd.DataFrame(
        [
            {
                "rank": 1,
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "RECHECK_LIVE_QUOTE",
                "setup_type": "BREAKOUT",
                "final_trade_score": 82,
                "setup_persistence_score": 79,
                "quote_status": "STALE_POSSIBLE",
                "execution_quote_quality": "LOW",
                "rr": 3.0,
                "quote_recheck_priority": "HIGH",
            }
        ]
    ).to_csv(reports / "manual_review_latest.csv", index=False)

    pd.DataFrame(
        [
            {
                "rank": 1,
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "RECHECK_LIVE_QUOTE",
                "setup_type": "BREAKOUT",
                "final_trade_score": 82,
                "setup_persistence_score": 79,
                "quote_status": "STALE_POSSIBLE",
                "execution_quote_quality": "LOW",
                "rr": 3.0,
            }
        ]
    ).to_csv(reports / "manual_review_top.csv", index=False)

    pd.DataFrame(
        [
            {
                "group": "OVERALL",
                "group_value": "ALL_CLOSED",
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "breakeven": 0,
                "win_rate": "",
                "avg_pnl_pct": "",
                "avg_r_multiple": "",
                "total_r_multiple": "",
                "best_trade_r": "",
                "worst_trade_r": "",
            }
        ]
    ).to_csv(reports / "trade_outcome_analytics_latest.csv", index=False)

    cleanup = {
        "status": "PASS",
        "mode": "DRY_RUN",
        "reports_dir": "reports",
        "archive_dir": "reports/tmp/temp_reports_20260610_120000",
        "candidate_count": 2,
        "moved_count": 0,
        "items": [
            {
                "path": "reports/example_test.csv",
                "matched_pattern": "*_test.csv",
                "size_bytes": 10,
                "modified": "2026-06-10T12:00:00",
                "moved": False,
                "destination": "",
            }
        ],
    }

    (reports / "reports_cleanup_latest.json").write_text(
        json.dumps(cleanup, indent=2),
        encoding="utf-8",
    )
    (reports / "reports_cleanup_latest.md").write_text(
        "# cleanup\n",
        encoding="utf-8",
    )

    return reports


def test_operator_index_collects_cleanup_status(tmp_path: Path):
    _make_reports(tmp_path)

    data = collect_operator_index_data(root=tmp_path)

    cleanup = data["cleanup"]

    assert cleanup["available"] is True
    assert cleanup["status"] == "PASS"
    assert cleanup["mode"] == "DRY_RUN"
    assert cleanup["candidate_count"] == 2
    assert cleanup["moved_count"] == 0


def test_operator_index_markdown_shows_cleanup_warning(tmp_path: Path):
    _make_reports(tmp_path)

    data = collect_operator_index_data(root=tmp_path)
    text = build_daily_operator_index_markdown(data)

    assert "## Limpieza de reportes temporales" in text
    assert "candidate_count: 2" in text
    assert "moved_count: 0" in text
    assert "reports/reports_cleanup_latest.md" in text
    assert "python .\\tools\\reports_cleanup.py --apply" in text


def test_operator_index_handles_missing_cleanup_report(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    (reports / "daily_validation_summary.txt").write_text(
        "Status: PASS\n",
        encoding="utf-8",
    )

    pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
            }
        ]
    ).to_csv(reports / "latest_scan_audited.csv", index=False)

    data = collect_operator_index_data(root=tmp_path)
    text = build_daily_operator_index_markdown(data)

    assert data["cleanup"]["available"] is False
    assert "No hay reporte de limpieza disponible" in text