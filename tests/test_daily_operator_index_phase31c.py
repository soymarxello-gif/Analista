from __future__ import annotations

import json
from pathlib import Path

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

    preflight = {
        "status": "PASS",
        "root": tmp_path.as_posix(),
        "cwd": tmp_path.as_posix(),
        "cwd_matches_root": True,
        "summary": {
            "missing_required_dirs": [],
            "missing_required_files": [],
            "missing_optional_files": [],
            "failed_write_checks": [],
        },
    }

    (reports / "project_preflight_latest.json").write_text(
        json.dumps(preflight, indent=2),
        encoding="utf-8",
    )
    (reports / "project_preflight_latest.md").write_text(
        "# preflight\n",
        encoding="utf-8",
    )

    cleanup = {
        "status": "PASS",
        "mode": "DRY_RUN",
        "candidate_count": 0,
        "moved_count": 0,
        "archive_dir": "",
    }

    (reports / "reports_cleanup_latest.json").write_text(
        json.dumps(cleanup, indent=2),
        encoding="utf-8",
    )
    (reports / "reports_cleanup_latest.md").write_text(
        "# cleanup\n",
        encoding="utf-8",
    )

    manifest = {
        "status": "PASS",
        "daily_validation": {"status": "PASS"},
        "project_preflight": {"status": "PASS"},
        "reports_cleanup": {"status": "PASS", "mode": "DRY_RUN"},
    }

    (reports / "daily_run_manifest_latest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    (reports / "daily_run_manifest_latest.md").write_text(
        "# manifest\n",
        encoding="utf-8",
    )

    return reports


def test_operator_index_tracks_daily_run_manifest_files(tmp_path: Path):
    _make_reports(tmp_path)

    data = collect_operator_index_data(root=tmp_path)

    paths = {item["path"] for item in data["report_status"]}

    assert "reports/daily_run_manifest_latest.json" in paths
    assert "reports/daily_run_manifest_latest.md" in paths


def test_operator_index_markdown_mentions_daily_run_manifest(tmp_path: Path):
    _make_reports(tmp_path)

    data = collect_operator_index_data(root=tmp_path)
    text = build_daily_operator_index_markdown(data)

    assert "## Manifiesto diario de corrida" in text
    assert "reports/daily_run_manifest_latest.md" in text
    assert "reports/daily_run_manifest_latest.json" in text
    assert "trazabilidad de entorno, Git, hashes de scripts clave" in text


def test_operator_index_open_first_includes_daily_run_manifest(tmp_path: Path):
    _make_reports(tmp_path)

    data = collect_operator_index_data(root=tmp_path)
    text = build_daily_operator_index_markdown(data)

    assert "1. `reports/daily_validation_summary.txt`" in text
    assert "2. `reports/daily_quality_gate_latest.md`" in text
    assert "3. `reports/daily_run_manifest_latest.md`" in text
    assert "4. `reports/project_preflight_latest.md`" in text