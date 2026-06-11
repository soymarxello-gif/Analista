from __future__ import annotations

from pathlib import Path

from tools.history_archive import archive_current_reports


def test_archive_current_reports_copies_required_files(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    (reports / "latest_scan_audited.csv").write_text("ticker,signal\nAAA,WATCHLIST\n", encoding="utf-8")
    (reports / "manual_review_latest.csv").write_text("ticker\nAAA\n", encoding="utf-8")
    (reports / "manual_review_latest.md").write_text("# Review\n", encoding="utf-8")
    (reports / "daily_validation_summary.txt").write_text("Status: PASS\n", encoding="utf-8")

    manifest = archive_current_reports(
        root=tmp_path,
        timestamp="20260608_120000",
    )

    archive_dir = tmp_path / manifest["archive_dir"]

    assert manifest["status"] == "PASS"
    assert archive_dir.exists()
    assert (archive_dir / "latest_scan_audited.csv").exists()
    assert (archive_dir / "manual_review_latest.csv").exists()
    assert (archive_dir / "manual_review_latest.md").exists()
    assert (archive_dir / "daily_validation_summary.txt").exists()
    assert (archive_dir / "manifest.json").exists()
    assert (tmp_path / "reports" / "history" / "latest.txt").exists()


def test_archive_current_reports_fails_when_required_file_missing(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    (reports / "latest_scan_audited.csv").write_text("ticker,signal\nAAA,WATCHLIST\n", encoding="utf-8")

    manifest = archive_current_reports(
        root=tmp_path,
        timestamp="20260608_120000",
    )

    assert manifest["status"] == "FAIL"
    assert "reports/manual_review_latest.csv" in manifest["missing_required"]
    assert "reports/manual_review_latest.md" in manifest["missing_required"]
    assert "reports/daily_validation_summary.txt" in manifest["missing_required"]