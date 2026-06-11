from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools.daily_operator_index import (
    build_daily_operator_index_markdown,
    collect_operator_index_data,
)


def _make_reports(tmp_path: Path, encoding_status: str = "PASS") -> Path:
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

    encoding_audit = {
        "status": encoding_status,
        "summary": {
            "files_scanned": 10,
            "warn_files": 1 if encoding_status == "WARN" else 0,
            "error_files": 1 if encoding_status == "FAIL" else 0,
            "total_marker_hits": 3 if encoding_status == "WARN" else 0,
        },
        "results": [],
    }

    (reports / "encoding_audit_latest.json").write_text(
        json.dumps(encoding_audit, indent=2),
        encoding="utf-8",
    )
    (reports / "encoding_audit_latest.md").write_text(
        "# encoding audit\n",
        encoding="utf-8",
    )

    return reports


def test_operator_index_collects_encoding_audit_status(tmp_path: Path):
    _make_reports(tmp_path, encoding_status="WARN")

    data = collect_operator_index_data(root=tmp_path)

    encoding = data["encoding_audit"]

    assert encoding["available"] is True
    assert encoding["status"] == "WARN"
    assert encoding["files_scanned"] == 10
    assert encoding["warn_files"] == 1
    assert encoding["error_files"] == 0
    assert encoding["total_marker_hits"] == 3


def test_operator_index_markdown_shows_encoding_audit_warn(tmp_path: Path):
    _make_reports(tmp_path, encoding_status="WARN")

    data = collect_operator_index_data(root=tmp_path)
    text = build_daily_operator_index_markdown(data)

    assert "## Auditoría de encoding" in text
    assert "- status: WARN" in text
    assert "- warn_files: 1" in text
    assert "- total_marker_hits: 3" in text
    assert "reports/encoding_audit_latest.md" in text
    assert "textos mal codificados" in text


def test_operator_index_markdown_shows_encoding_audit_pass(tmp_path: Path):
    _make_reports(tmp_path, encoding_status="PASS")

    data = collect_operator_index_data(root=tmp_path)
    text = build_daily_operator_index_markdown(data)

    assert "## Auditoría de encoding" in text
    assert "- status: PASS" in text
    assert "no se detectaron marcadores típicos de mojibake" in text


def test_operator_index_markdown_shows_encoding_audit_fail(tmp_path: Path):
    _make_reports(tmp_path, encoding_status="FAIL")

    data = collect_operator_index_data(root=tmp_path)
    text = build_daily_operator_index_markdown(data)

    assert "## Auditoría de encoding" in text
    assert "- status: FAIL" in text
    assert "- error_files: 1" in text
    assert "archivos que no pudieron leerse" in text


def test_operator_index_handles_missing_encoding_audit_report(tmp_path: Path):
    _make_reports(tmp_path, encoding_status="PASS")

    (tmp_path / "reports" / "encoding_audit_latest.json").unlink()

    data = collect_operator_index_data(root=tmp_path)
    text = build_daily_operator_index_markdown(data)

    assert data["encoding_audit"]["available"] is False
    assert "No hay reporte de encoding disponible" in text


def test_operator_index_tracks_encoding_audit_files(tmp_path: Path):
    _make_reports(tmp_path, encoding_status="PASS")

    data = collect_operator_index_data(root=tmp_path)

    paths = {item["path"] for item in data["report_status"]}

    assert "reports/encoding_audit_latest.json" in paths
    assert "reports/encoding_audit_latest.md" in paths


def test_open_first_includes_encoding_audit(tmp_path: Path):
    _make_reports(tmp_path, encoding_status="PASS")

    data = collect_operator_index_data(root=tmp_path)
    text = build_daily_operator_index_markdown(data)

    assert "1. `reports/daily_validation_summary.txt`" in text
    assert "2. `reports/daily_quality_gate_latest.md`" in text
    assert "3. `reports/daily_run_manifest_latest.md`" in text
    assert "4. `reports/project_preflight_latest.md`" in text
    assert "5. `reports/encoding_audit_latest.md`" in text