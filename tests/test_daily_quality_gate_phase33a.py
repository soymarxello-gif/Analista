from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools.daily_quality_gate import (
    build_daily_quality_gate_markdown,
    collect_daily_quality_gate,
    save_daily_quality_gate,
)


def _make_reports(tmp_path: Path, daily_status: str = "PASS", preflight_status: str = "PASS") -> Path:
    reports = tmp_path / "reports"
    reports.mkdir()

    (reports / "daily_validation_summary.txt").write_text(
        f"=== ANALISTA DAILY VALIDATION SUMMARY ===\nStatus: {daily_status}\n",
        encoding="utf-8",
    )

    preflight = {
        "status": preflight_status,
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

    manifest = {
        "status": "PASS",
        "daily_validation": {"status": daily_status},
        "project_preflight": {"status": preflight_status},
    }
    (reports / "daily_run_manifest_latest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    cleanup = {
        "status": "PASS",
        "mode": "DRY_RUN",
        "candidate_count": 0,
        "moved_count": 0,
    }
    (reports / "reports_cleanup_latest.json").write_text(
        json.dumps(cleanup, indent=2),
        encoding="utf-8",
    )

    encoding = {
        "status": "PASS",
        "summary": {
            "files_scanned": 10,
            "warn_files": 0,
            "error_files": 0,
            "total_marker_hits": 0,
        },
    }
    (reports / "encoding_audit_latest.json").write_text(
        json.dumps(encoding, indent=2),
        encoding="utf-8",
    )

    pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "setup_type": "PULLBACK",
                "execution_quote_quality": "HIGH",
                "quote_status": "VALID",
                "actionable_entry": "",
                "actionable_stop": "",
                "actionable_target": "",
            },
            {
                "ticker": "BBB",
                "signal": "VETO",
                "recommendation": "DO_NOT_TRADE",
                "setup_type": "NO_VALID_SETUP",
                "execution_quote_quality": "LOW",
                "quote_status": "STALE_POSSIBLE",
                "actionable_entry": "",
                "actionable_stop": "",
                "actionable_target": "",
            },
        ]
    ).to_csv(reports / "latest_scan_audited.csv", index=False)

    pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "quote_recheck_priority": "",
            }
        ]
    ).to_csv(reports / "manual_review_latest.csv", index=False)

    (reports / "daily_operator_index.md").write_text("# index\n", encoding="utf-8")
    (reports / "manual_review_top.csv").write_text("ticker\nAAA\n", encoding="utf-8")
    (reports / "manual_review_top.md").write_text("# top\n", encoding="utf-8")

    return reports


def test_daily_quality_gate_passes_clean_run(tmp_path: Path):
    _make_reports(tmp_path)

    data = collect_daily_quality_gate(root=tmp_path)

    assert data["status"] == "PASS"
    assert data["manual_review_allowed"] is True
    assert data["manual_review_mode"] == "NORMAL"
    assert data["scan_snapshot"]["latest_scan_rows"] == 2
    assert data["scan_snapshot"]["manual_review_rows"] == 1


def test_daily_quality_gate_warns_on_preflight_warn(tmp_path: Path):
    _make_reports(tmp_path, preflight_status="WARN")

    data = collect_daily_quality_gate(root=tmp_path)

    assert data["status"] == "WARN"
    assert data["manual_review_allowed"] is True
    assert data["manual_review_mode"] == "REINFORCED"

    messages = [item["message"] for item in data["issues"]]
    assert any("project_preflight terminó en WARN" in msg for msg in messages)


def test_daily_quality_gate_fails_on_daily_validation_fail(tmp_path: Path):
    _make_reports(tmp_path, daily_status="FAIL")

    data = collect_daily_quality_gate(root=tmp_path)

    assert data["status"] == "FAIL"
    assert data["manual_review_allowed"] is False
    assert data["manual_review_mode"] == "BLOCKED"


def test_daily_quality_gate_fails_when_scan_is_missing(tmp_path: Path):
    _make_reports(tmp_path)

    (tmp_path / "reports" / "latest_scan_audited.csv").unlink()

    data = collect_daily_quality_gate(root=tmp_path)

    assert data["status"] == "FAIL"
    assert data["manual_review_allowed"] is False

    sources = [item["source"] for item in data["issues"]]
    assert "reports/latest_scan_audited.csv" in sources or "latest_scan_audited.csv" in sources


def test_daily_quality_gate_warns_on_recheck_live_quote(tmp_path: Path):
    _make_reports(tmp_path)

    scan_path = tmp_path / "reports" / "latest_scan_audited.csv"
    df = pd.read_csv(scan_path)
    df.loc[0, "recommendation"] = "RECHECK_LIVE_QUOTE"
    df.to_csv(scan_path, index=False)

    data = collect_daily_quality_gate(root=tmp_path)

    assert data["status"] == "WARN"
    assert data["manual_review_allowed"] is True
    assert data["logic_checks"]["manual_recheck_quote_rows"] == 1


def test_daily_quality_gate_fails_on_trigger_with_low_quote(tmp_path: Path):
    _make_reports(tmp_path)

    scan_path = tmp_path / "reports" / "latest_scan_audited.csv"
    df = pd.read_csv(scan_path)
    df.loc[0, "signal"] = "TRIGGER_CONFIRMED"
    df.loc[0, "execution_quote_quality"] = "LOW"
    df.to_csv(scan_path, index=False)

    data = collect_daily_quality_gate(root=tmp_path)

    assert data["status"] == "FAIL"
    assert data["manual_review_allowed"] is False
    assert data["logic_checks"]["trigger_with_low_quote_rows"] == 1


def test_daily_quality_gate_markdown_contains_sections(tmp_path: Path):
    _make_reports(tmp_path)

    data = collect_daily_quality_gate(root=tmp_path)
    text = build_daily_quality_gate_markdown(data)

    assert "Analista - daily quality gate" in text
    assert "## Decision gate" in text
    assert "## Componentes" in text
    assert "## Scan snapshot" in text
    assert "## Logical checks" in text
    assert "## Issues" in text
    assert "manual_review_allowed" in text


def test_save_daily_quality_gate_writes_outputs(tmp_path: Path):
    _make_reports(tmp_path)

    json_out = tmp_path / "reports" / "daily_quality_gate_latest.json"
    markdown_out = tmp_path / "reports" / "daily_quality_gate_latest.md"

    result = save_daily_quality_gate(
        root=tmp_path,
        json_out=json_out,
        markdown_out=markdown_out,
    )

    assert result["status"] == "PASS"
    assert result["manual_review_allowed"] is True
    assert json_out.exists()
    assert markdown_out.exists()

    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert data["status"] == "PASS"

    text = markdown_out.read_text(encoding="utf-8")
    assert "daily quality gate" in text