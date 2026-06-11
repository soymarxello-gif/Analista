from __future__ import annotations

import json
from pathlib import Path

from tools.release_readiness_check import (
    build_release_readiness_markdown,
    collect_release_readiness,
    save_release_readiness,
)


def _make_ready_project(tmp_path: Path, gate_status: str = "PASS", validation_status: str = "PASS") -> Path:
    reports = tmp_path / "reports"
    tools = tmp_path / "tools"
    reports.mkdir()
    tools.mkdir()

    required_tools = [
        "daily_validation.py",
        "daily_operator_index.py",
        "daily_quality_gate.py",
        "daily_run_manifest.py",
        "encoding_audit.py",
        "project_preflight.py",
        "reports_cleanup.py",
        "project_consistency_audit.py",
    ]

    for name in required_tools:
        (tools / name).write_text("# tool\n", encoding="utf-8")

    (reports / "daily_validation_summary.txt").write_text(
        f"=== ANALISTA DAILY VALIDATION SUMMARY ===\nStatus: {validation_status}\n",
        encoding="utf-8",
    )

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
        "issues": [],
    }

    (reports / "daily_quality_gate_latest.json").write_text(
        json.dumps(quality_gate, indent=2),
        encoding="utf-8",
    )
    (reports / "daily_quality_gate_latest.md").write_text(
        "# quality gate\n",
        encoding="utf-8",
    )

    (reports / "daily_operator_index.md").write_text(
        "# operator index\n\n"
        "## Daily quality gate\n\n"
        "- manual_review_allowed: True\n"
        "- manual_review_mode: NORMAL\n"
        "- Archivo: `reports/daily_quality_gate_latest.md`\n",
        encoding="utf-8",
    )

    (reports / "daily_run_manifest_latest.json").write_text(
        json.dumps({"status": "PASS"}, indent=2),
        encoding="utf-8",
    )
    (reports / "daily_run_manifest_latest.md").write_text(
        "# manifest\n",
        encoding="utf-8",
    )

    (reports / "encoding_audit_latest.json").write_text(
        json.dumps({"status": "PASS"}, indent=2),
        encoding="utf-8",
    )
    (reports / "encoding_audit_latest.md").write_text(
        "# encoding\n",
        encoding="utf-8",
    )

    (reports / "project_preflight_latest.json").write_text(
        json.dumps({"status": "PASS"}, indent=2),
        encoding="utf-8",
    )
    (reports / "project_preflight_latest.md").write_text(
        "# preflight\n",
        encoding="utf-8",
    )

    (reports / "latest_scan_audited.csv").write_text(
        "ticker,signal\nAAA,WATCHLIST\n",
        encoding="utf-8",
    )
    (reports / "manual_review_latest.csv").write_text(
        "ticker,signal\nAAA,WATCHLIST\n",
        encoding="utf-8",
    )
    (reports / "manual_review_top.csv").write_text(
        "ticker,signal\nAAA,WATCHLIST\n",
        encoding="utf-8",
    )

    return tmp_path


def test_release_readiness_passes_ready_project_when_commands_skipped(tmp_path: Path):
    _make_ready_project(tmp_path)

    data = collect_release_readiness(
        root=tmp_path,
        run_pytest=False,
        run_project_consistency=False,
    )

    assert data["status"] == "WARN"
    assert data["release_ready"] is True
    assert data["release_mode"] == "READY_WITH_WARNINGS"

    sources = [item["source"] for item in data["issues"]]
    assert "pytest" in sources
    assert "project_consistency_audit" in sources


def test_release_readiness_fails_on_quality_gate_fail(tmp_path: Path):
    _make_ready_project(tmp_path, gate_status="FAIL")

    data = collect_release_readiness(
        root=tmp_path,
        run_pytest=False,
        run_project_consistency=False,
    )

    assert data["status"] == "FAIL"
    assert data["release_ready"] is False
    assert data["release_mode"] == "BLOCKED"


def test_release_readiness_fails_on_daily_validation_fail(tmp_path: Path):
    _make_ready_project(tmp_path, validation_status="FAIL")

    data = collect_release_readiness(
        root=tmp_path,
        run_pytest=False,
        run_project_consistency=False,
    )

    assert data["status"] == "FAIL"
    assert data["release_ready"] is False


def test_release_readiness_fails_when_operator_index_missing_gate_section(tmp_path: Path):
    _make_ready_project(tmp_path)

    (tmp_path / "reports" / "daily_operator_index.md").write_text(
        "# operator index\n",
        encoding="utf-8",
    )

    data = collect_release_readiness(
        root=tmp_path,
        run_pytest=False,
        run_project_consistency=False,
    )

    assert data["status"] == "FAIL"

    messages = [item["message"] for item in data["issues"]]
    assert any("daily_operator_index" in msg for msg in messages)


def test_release_readiness_markdown_contains_sections(tmp_path: Path):
    _make_ready_project(tmp_path)

    data = collect_release_readiness(
        root=tmp_path,
        run_pytest=False,
        run_project_consistency=False,
    )

    text = build_release_readiness_markdown(data)

    assert "Analista - release readiness check" in text
    assert "## Decision gate" in text
    assert "## Componentes" in text
    assert "## Comandos de validación" in text
    assert "## Operator index checks" in text
    assert "## Issues" in text
    assert "## Archivos críticos" in text


def test_save_release_readiness_writes_outputs(tmp_path: Path):
    _make_ready_project(tmp_path)

    json_out = tmp_path / "reports" / "release_readiness_latest.json"
    markdown_out = tmp_path / "reports" / "release_readiness_latest.md"

    result = save_release_readiness(
        root=tmp_path,
        json_out=json_out,
        markdown_out=markdown_out,
        run_pytest=False,
        run_project_consistency=False,
    )

    assert result["status"] == "WARN"
    assert result["release_ready"] is True
    assert json_out.exists()
    assert markdown_out.exists()

    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert data["release_ready"] is True

    text = markdown_out.read_text(encoding="utf-8")
    assert "release readiness check" in text