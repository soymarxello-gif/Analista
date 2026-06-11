from __future__ import annotations

from pathlib import Path

from tools.project_preflight import (
    build_project_preflight_markdown,
    collect_project_preflight,
    save_project_preflight,
)


def _make_minimal_project(tmp_path: Path) -> Path:
    tools = tmp_path / "tools"
    tests = tmp_path / "tests"
    reports = tmp_path / "reports"

    tools.mkdir()
    tests.mkdir()
    reports.mkdir()

    (tools / "daily_validation.py").write_text("# daily validation\n", encoding="utf-8")
    (tools / "daily_operator_index.py").write_text("# operator index\n", encoding="utf-8")
    (tools / "reports_cleanup.py").write_text("# cleanup\n", encoding="utf-8")

    return tmp_path


def test_project_preflight_passes_with_minimal_required_project(tmp_path: Path):
    root = _make_minimal_project(tmp_path)

    data = collect_project_preflight(
        root=root,
        optional_files=[],
    )

    assert data["status"] == "WARN" or data["status"] == "PASS"
    assert data["summary"]["missing_required_dirs"] == []
    assert data["summary"]["missing_required_files"] == []
    assert data["summary"]["failed_write_checks"] == []


def test_project_preflight_fails_when_required_file_is_missing(tmp_path: Path):
    root = _make_minimal_project(tmp_path)

    (root / "tools" / "reports_cleanup.py").unlink()

    data = collect_project_preflight(
        root=root,
        optional_files=[],
    )

    assert data["status"] == "FAIL"
    assert "tools/reports_cleanup.py" in data["summary"]["missing_required_files"]


def test_project_preflight_warns_when_optional_files_are_missing(tmp_path: Path):
    root = _make_minimal_project(tmp_path)

    data = collect_project_preflight(
        root=root,
        optional_files=[
            "reports/latest_scan_audited.csv",
            "reports/manual_review_latest.csv",
        ],
    )

    assert data["status"] in {"WARN", "FAIL"}
    assert "reports/latest_scan_audited.csv" in data["summary"]["missing_optional_files"]
    assert "reports/manual_review_latest.csv" in data["summary"]["missing_optional_files"]


def test_project_preflight_markdown_contains_core_sections(tmp_path: Path):
    root = _make_minimal_project(tmp_path)

    data = collect_project_preflight(
        root=root,
        optional_files=[],
    )

    text = build_project_preflight_markdown(data)

    assert "Analista - project preflight" in text
    assert "## Decision gate" in text
    assert "## Required dirs" in text
    assert "## Required files" in text
    assert "## Optional files" in text
    assert "## Write checks" in text
    assert "## Summary" in text


def test_save_project_preflight_writes_outputs(tmp_path: Path):
    root = _make_minimal_project(tmp_path)

    json_out = root / "reports" / "project_preflight_latest.json"
    markdown_out = root / "reports" / "project_preflight_latest.md"

    result = save_project_preflight(
        root=root,
        json_out=json_out,
        markdown_out=markdown_out,
    )

    assert result["status"] in {"PASS", "WARN"}
    assert json_out.exists()
    assert markdown_out.exists()

    text = markdown_out.read_text(encoding="utf-8")

    assert "project preflight" in text