from __future__ import annotations

from pathlib import Path

from tools.reports_cleanup import (
    cleanup_temporary_reports,
    discover_temporary_reports,
    save_cleanup_reports,
)


def _make_reports(tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    reports.mkdir()

    # Protegidos
    (reports / "latest_scan_audited.csv").write_text("x\n", encoding="utf-8")
    (reports / "manual_review_latest.md").write_text("# manual\n", encoding="utf-8")
    (reports / "trade_outcomes.csv").write_text("trade_id,ticker\n", encoding="utf-8")
    (reports / "daily_operator_index.md").write_text("# index\n", encoding="utf-8")

    # Temporales
    (reports / "trade_outcome_analytics_test.csv").write_text("x\n", encoding="utf-8")
    (reports / "trade_outcome_analytics_test.md").write_text("# test\n", encoding="utf-8")
    (reports / "open_trades_snapshot_test.csv").write_text("x\n", encoding="utf-8")
    (reports / "manual_review_debug_test.md").write_text("# debug\n", encoding="utf-8")

    # Ya en tmp: no debe tocarse
    tmp_dir = reports / "tmp"
    tmp_dir.mkdir()
    (tmp_dir / "old_test.csv").write_text("x\n", encoding="utf-8")

    return reports


def test_discover_temporary_reports_excludes_protected_files(tmp_path: Path):
    reports = _make_reports(tmp_path)

    items = discover_temporary_reports(
        reports_dir=reports,
        root=tmp_path,
    )

    paths = {item["path"] for item in items}

    assert "reports/trade_outcome_analytics_test.csv" in paths
    assert "reports/trade_outcome_analytics_test.md" in paths
    assert "reports/open_trades_snapshot_test.csv" in paths
    assert "reports/manual_review_debug_test.md" in paths

    assert "reports/latest_scan_audited.csv" not in paths
    assert "reports/manual_review_latest.md" not in paths
    assert "reports/trade_outcomes.csv" not in paths
    assert "reports/daily_operator_index.md" not in paths
    assert "reports/tmp/old_test.csv" not in paths


def test_cleanup_temporary_reports_dry_run_does_not_move(tmp_path: Path):
    reports = _make_reports(tmp_path)

    result = cleanup_temporary_reports(
        root=tmp_path,
        reports_dir=reports,
        apply=False,
    )

    assert result["status"] == "PASS"
    assert result["mode"] == "DRY_RUN"
    assert result["candidate_count"] == 4
    assert result["moved_count"] == 0

    assert (reports / "trade_outcome_analytics_test.csv").exists()
    assert (reports / "open_trades_snapshot_test.csv").exists()


def test_cleanup_temporary_reports_apply_moves_only_temp_files(tmp_path: Path):
    reports = _make_reports(tmp_path)

    archive_dir = reports / "tmp" / "phase29_test"

    result = cleanup_temporary_reports(
        root=tmp_path,
        reports_dir=reports,
        apply=True,
        archive_dir=archive_dir,
    )

    assert result["status"] == "PASS"
    assert result["mode"] == "APPLY"
    assert result["candidate_count"] == 4
    assert result["moved_count"] == 4

    assert not (reports / "trade_outcome_analytics_test.csv").exists()
    assert not (reports / "open_trades_snapshot_test.csv").exists()

    assert (archive_dir / "trade_outcome_analytics_test.csv").exists()
    assert (archive_dir / "open_trades_snapshot_test.csv").exists()

    assert (reports / "latest_scan_audited.csv").exists()
    assert (reports / "manual_review_latest.md").exists()
    assert (reports / "trade_outcomes.csv").exists()
    assert (reports / "daily_operator_index.md").exists()


def test_save_cleanup_reports_writes_json_and_markdown(tmp_path: Path):
    reports = _make_reports(tmp_path)

    json_out = reports / "reports_cleanup_latest.json"
    markdown_out = reports / "reports_cleanup_latest.md"

    result = save_cleanup_reports(
        root=tmp_path,
        reports_dir=reports,
        json_out=json_out,
        markdown_out=markdown_out,
        apply=False,
    )

    assert result["status"] == "PASS"
    assert json_out.exists()
    assert markdown_out.exists()

    markdown = markdown_out.read_text(encoding="utf-8")

    assert "reports cleanup" in markdown
    assert "DRY_RUN" in markdown
    assert "trade_outcome_analytics_test.csv" in markdown