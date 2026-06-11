from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools.daily_operator_index import (
    build_daily_operator_index_markdown,
    collect_operator_index_data,
)


def _make_reports(tmp_path: Path, preflight_status: str = "PASS") -> Path:
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
                "recommendation": "WATCHLIST_MONITOR",
                "setup_type": "PULLBACK",
                "final_trade_score": 78,
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "rr": 2.5,
            }
        ]
    ).to_csv(reports / "latest_scan_audited.csv", index=False)

    pd.DataFrame(
        [
            {
                "rank": 1,
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "setup_type": "PULLBACK",
                "final_trade_score": 78,
                "setup_persistence_score": 76,
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "rr": 2.5,
                "quote_recheck_priority": "",
            }
        ]
    ).to_csv(reports / "manual_review_latest.csv", index=False)

    pd.DataFrame(
        [
            {
                "rank": 1,
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "setup_type": "PULLBACK",
                "final_trade_score": 78,
                "setup_persistence_score": 76,
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "rr": 2.5,
            }
        ]
    ).to_csv(reports / "manual_review_top.csv", index=False)

    cleanup = {
        "status": "PASS",
        "mode": "DRY_RUN",
        "candidate_count": 0,
        "moved_count": 0,
        "archive_dir": "reports/tmp/temp_reports_20260610_120000",
    }

    (reports / "reports_cleanup_latest.json").write_text(
        json.dumps(cleanup, indent=2),
        encoding="utf-8",
    )

    (reports / "reports_cleanup_latest.md").write_text(
        "# cleanup\n",
        encoding="utf-8",
    )

    preflight = {
        "status": preflight_status,
        "root": tmp_path.as_posix(),
        "cwd": tmp_path.as_posix(),
        "cwd_matches_root": True,
        "python": {
            "executable": "python",
        },
        "environment": {
            "virtual_env": ".venv",
        },
        "summary": {
            "missing_required_dirs": [],
            "missing_required_files": [],
            "missing_optional_files": ["reports/example_optional.csv"]
            if preflight_status == "WARN"
            else [],
            "failed_write_checks": [],
        },
    }

    if preflight_status == "FAIL":
        preflight["summary"]["missing_required_files"] = ["tools/reports_cleanup.py"]

    (reports / "project_preflight_latest.json").write_text(
        json.dumps(preflight, indent=2),
        encoding="utf-8",
    )

    (reports / "project_preflight_latest.md").write_text(
        "# preflight\n",
        encoding="utf-8",
    )

    return reports


def test_operator_index_collects_project_preflight_status(tmp_path: Path):
    _make_reports(tmp_path, preflight_status="PASS")

    data = collect_operator_index_data(root=tmp_path)

    preflight = data["preflight"]

    assert preflight["available"] is True
    assert preflight["status"] == "PASS"
    assert preflight["cwd_matches_root"] is True
    assert preflight["missing_required_dirs"] == 0
    assert preflight["missing_required_files"] == 0
    assert preflight["missing_optional_files"] == 0
    assert preflight["failed_write_checks"] == 0


def test_operator_index_markdown_shows_project_preflight_pass(tmp_path: Path):
    _make_reports(tmp_path, preflight_status="PASS")

    data = collect_operator_index_data(root=tmp_path)
    text = build_daily_operator_index_markdown(data)

    assert "## Project preflight" in text
    assert "- status: PASS" in text
    assert "- missing_required_files: 0" in text
    assert "reports/project_preflight_latest.md" in text
    assert "Estado PASS: estructura mínima validada" in text


def test_operator_index_markdown_shows_project_preflight_warn(tmp_path: Path):
    _make_reports(tmp_path, preflight_status="WARN")

    data = collect_operator_index_data(root=tmp_path)
    text = build_daily_operator_index_markdown(data)

    assert "## Project preflight" in text
    assert "- status: WARN" in text
    assert "- missing_optional_files: 1" in text
    assert "Estado WARN" in text


def test_operator_index_markdown_shows_project_preflight_fail(tmp_path: Path):
    _make_reports(tmp_path, preflight_status="FAIL")

    data = collect_operator_index_data(root=tmp_path)
    text = build_daily_operator_index_markdown(data)

    assert "## Project preflight" in text
    assert "- status: FAIL" in text
    assert "- missing_required_files: 1" in text
    assert "corregir estructura del proyecto antes de operar" in text


def test_operator_index_handles_missing_preflight_report(tmp_path: Path):
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

    assert data["preflight"]["available"] is False
    assert "No hay reporte de preflight disponible" in text