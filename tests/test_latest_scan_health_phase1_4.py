from pathlib import Path

from tools.latest_scan_health import _discover_latest_csv


def test_discover_latest_csv(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    a = reports / "a.csv"
    b = reports / "b.csv"

    a.write_text("ticker\nAAA\n", encoding="utf-8")
    b.write_text("ticker\nBBB\n", encoding="utf-8")

    latest = _discover_latest_csv(reports)
    assert latest.name in {"a.csv", "b.csv"}
