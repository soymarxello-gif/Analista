from __future__ import annotations

import json
from pathlib import Path
from pydoc import text

import pandas as pd

from tools.daily_operator_index import (
    build_daily_operator_index_markdown,
    collect_operator_index_data,
)


def _make_reports(tmp_path: Path, gate_status: str = "WARN") -> Path:
    reports = tmp_path / "reports"
    reports.mkdir()

    (reports / "daily_validation_summary.txt").write_text(
        "=== ANALISTA DAILY VALIDATION SUMMARY ===\nStatus: WARN\n",
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
        "daily_validation": {"status": "WARN"},
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
        "status": "PASS",
        "summary": {
            "files_scanned": 10,
            "warn_files": 0,
            "error_files": 0,
            "total_marker_hits": 0,
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

    issues = []
    if gate_status == "WARN":
        issues = [
            {
                "severity": "WARN",
                "source": "latest_scan_audited.csv",
                "message": "Hay candidatos que requieren RECHECK_LIVE_QUOTE.",
            }
        ]
    elif gate_status == "FAIL":
        issues = [
            {
                "severity": "FAIL",
                "source": "daily_validation_summary.txt",
                "message": "daily_validation terminó en FAIL.",
            }
        ]

    quality_gate = {
        "status": gate_status,
        "manual_review_allowed": gate_status != "FAIL",
        "manual_review_mode": (
            "BLOCKED"
            if gate_status == "FAIL"
            else "REINFORCED"
            if gate_status == "WARN"
            else "NORMAL"
        ),
        "issues": issues,
    }

    (reports / "daily_quality_gate_latest.json").write_text(
        json.dumps(quality_gate, indent=2),
        encoding="utf-8",
    )
    (reports / "daily_quality_gate_latest.md").write_text(
        "# daily quality gate\n",
        encoding="utf-8",
    )

    return reports


def test_operator_index_collects_quality_gate_status(tmp_path: Path):
    _make_reports(tmp_path, gate_status="WARN")

    data = collect_operator_index_data(root=tmp_path)

    gate = data["quality_gate"]

    assert gate["available"] is True
    assert gate["status"] == "WARN"
    assert gate["manual_review_allowed"] is True
    assert gate["manual_review_mode"] == "REINFORCED"
    assert gate["issue_count"] == 1
    assert gate["warn_issues"] == 1
    assert gate["fail_issues"] == 0


def test_operator_index_markdown_shows_quality_gate_warn(tmp_path: Path):
    _make_reports(tmp_path, gate_status="WARN")

    data = collect_operator_index_data(root=tmp_path)
    text = build_daily_operator_index_markdown(data)

    assert "## Daily quality gate" in text
    assert "- status: WARN" in text
    assert "- manual_review_allowed: True" in text
    assert "- manual_review_mode: REINFORCED" in text
    assert "- issue_count: 1" in text
    assert "validación reforzada" in text
    assert "reports/daily_quality_gate_latest.md" in text


def test_operator_index_markdown_shows_quality_gate_pass(tmp_path: Path):
    _make_reports(tmp_path, gate_status="PASS")

    data = collect_operator_index_data(root=tmp_path)
    text = build_daily_operator_index_markdown(data)

    assert "## Daily quality gate" in text
    assert "- status: PASS" in text
    assert "- manual_review_mode: NORMAL" in text
    assert "corrida apta para revisión manual normal" in text


def test_operator_index_markdown_shows_quality_gate_fail(tmp_path: Path):
    _make_reports(tmp_path, gate_status="FAIL")

    data = collect_operator_index_data(root=tmp_path)
    text = build_daily_operator_index_markdown(data)

    assert "## Daily quality gate" in text
    assert "- status: FAIL" in text
    assert "- manual_review_allowed: False" in text
    assert "- manual_review_mode: BLOCKED" in text
    assert "no usar candidatos operativamente" in text


def test_operator_index_handles_missing_quality_gate_report(tmp_path: Path):
    _make_reports(tmp_path, gate_status="PASS")

    (tmp_path / "reports" / "daily_quality_gate_latest.json").unlink()

    data = collect_operator_index_data(root=tmp_path)
    text = build_daily_operator_index_markdown(data)

    assert data["quality_gate"]["available"] is False
    assert "No hay reporte de quality gate disponible" in text


def test_operator_index_tracks_quality_gate_files(tmp_path: Path):
    _make_reports(tmp_path, gate_status="PASS")

    data = collect_operator_index_data(root=tmp_path)

    paths = {item["path"] for item in data["report_status"]}

    assert "reports/daily_quality_gate_latest.json" in paths
    assert "reports/daily_quality_gate_latest.md" in paths


def test_open_first_includes_quality_gate_before_manifest(tmp_path: Path):
    _make_reports(tmp_path, gate_status="PASS")

    data = collect_operator_index_data(root=tmp_path)
    text = build_daily_operator_index_markdown(data)

    assert "1. `reports/daily_validation_summary.txt`" in text
    assert "2. `reports/daily_quality_gate_latest.md`" in text
    assert "3. `reports/daily_run_manifest_latest.md`" in text
    assert "4. `reports/project_preflight_latest.md`" in text
    assert "5. `reports/encoding_audit_latest.md`" in text