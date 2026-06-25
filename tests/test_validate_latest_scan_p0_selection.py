from pathlib import Path

import validate_latest_scan_p0


def test_latest_csv_prioritizes_audited_scan_over_newer_secondary_report(
    monkeypatch, tmp_path: Path
):
    reports = tmp_path / "reports"
    reports.mkdir()
    audited = reports / "latest_scan_audited.csv"
    secondary = reports / "manual_review_top.csv"
    audited.write_text("ticker\nAAA\n", encoding="utf-8")
    secondary.write_text("ticker\nBBB\n", encoding="utf-8")
    secondary.touch()
    monkeypatch.setattr(validate_latest_scan_p0, "REPORTS_DIR", reports)

    assert validate_latest_scan_p0.latest_csv() == audited
