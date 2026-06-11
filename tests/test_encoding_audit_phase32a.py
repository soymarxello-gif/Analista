from __future__ import annotations

from pathlib import Path
import json

from tools.encoding_audit import (
    build_encoding_audit_markdown,
    collect_encoding_audit,
    save_encoding_audit,
    scan_file,
)


def test_scan_file_passes_clean_utf8_file(tmp_path: Path):
    path = tmp_path / "clean.md"
    path.write_text("revisión correcta\nseñales válidas\n", encoding="utf-8")

    result = scan_file(path, root=tmp_path)

    assert result["status"] == "PASS"
    assert result["total_marker_hits"] == 0
    assert result["marker_hits"] == {}


def test_scan_file_warns_on_mojibake_markers(tmp_path: Path):
    path = tmp_path / "bad.md"
    path.write_text("revisiÃ³n manual reforzada\nseÃ±ales\n", encoding="utf-8")

    result = scan_file(path, root=tmp_path)

    assert result["status"] == "WARN"
    assert result["total_marker_hits"] >= 2
    assert "Ã³" in result["marker_hits"]
    assert "Ã±" in result["marker_hits"]
    assert result["samples"]


def test_collect_encoding_audit_scans_reports_dir(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    (reports / "ok.md").write_text("correcto\n", encoding="utf-8")
    (reports / "bad.md").write_text("revisiÃ³n\n", encoding="utf-8")

    data = collect_encoding_audit(root=tmp_path, scan_dir=reports)

    assert data["status"] == "WARN"
    assert data["summary"]["files_scanned"] == 2
    assert data["summary"]["warn_files"] == 1
    assert data["summary"]["total_marker_hits"] >= 1


def test_encoding_audit_markdown_contains_sections(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    (reports / "bad.md").write_text("revisiÃ³n\n", encoding="utf-8")

    data = collect_encoding_audit(root=tmp_path, scan_dir=reports)
    text = build_encoding_audit_markdown(data)

    assert "Analista - encoding audit" in text
    assert "## Decision gate" in text
    assert "## Archivos con advertencias o errores" in text
    assert "## Muestras" in text
    assert "revisiÃ³n" in text


def test_save_encoding_audit_writes_outputs(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    (reports / "bad.md").write_text("revisiÃ³n\n", encoding="utf-8")

    json_out = reports / "encoding_audit_latest.json"
    markdown_out = reports / "encoding_audit_latest.md"

    result = save_encoding_audit(
        root=tmp_path,
        scan_dir=reports,
        json_out=json_out,
        markdown_out=markdown_out,
    )

    assert result["status"] == "WARN"
    assert json_out.exists()
    assert markdown_out.exists()

    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert data["status"] == "WARN"

    text = markdown_out.read_text(encoding="utf-8")
    assert "encoding audit" in text