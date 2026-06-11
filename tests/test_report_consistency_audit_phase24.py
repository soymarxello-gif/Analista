from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.report_consistency_audit import (
    audit_manual_review_latest,
    audit_manual_review_top,
    build_report_consistency_audit,
    save_report_consistency_audit,
)


def test_audit_manual_review_latest_detects_empty_recommendation(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    manual_csv = reports / "manual_review_latest.csv"

    pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "rank": 1,
                "signal": "WATCHLIST",
                "recommendation": None,
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "setup_persistence_score": 80,
                "setup_persistence_bucket": "A_PERSISTENT_HIGH_QUALITY",
            }
        ]
    ).to_csv(manual_csv, index=False)

    result = audit_manual_review_latest(manual_csv)

    assert any("empty_recommendation_rows" in issue for issue in result["issues"])


def test_audit_manual_review_latest_passes_valid_file(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    manual_csv = reports / "manual_review_latest.csv"

    pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "rank": 1,
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "setup_persistence_score": 80,
                "setup_persistence_bucket": "A_PERSISTENT_HIGH_QUALITY",
            }
        ]
    ).to_csv(manual_csv, index=False)

    result = audit_manual_review_latest(manual_csv)

    assert result["issues"] == []


def test_audit_manual_review_top_detects_rank_mismatch(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    manual_csv = reports / "manual_review_latest.csv"
    top_csv = reports / "manual_review_top.csv"

    pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "rank": 1,
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "setup_persistence_score": 80,
                "setup_persistence_bucket": "A_PERSISTENT_HIGH_QUALITY",
            }
        ]
    ).to_csv(manual_csv, index=False)

    pd.DataFrame(
        [
            {
                "_top_group": "1_ALTA_CALIDAD_OPERATIVA",
                "ticker": "AAA",
                "rank": 99,
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
            }
        ]
    ).to_csv(top_csv, index=False)

    result = audit_manual_review_top(top_csv, manual_csv)

    assert any("rank_mismatch_vs_manual" in issue for issue in result["issues"])


def test_build_report_consistency_audit_passes_with_valid_reports(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "rank": 1,
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "setup_persistence_score": 80,
                "setup_persistence_bucket": "A_PERSISTENT_HIGH_QUALITY",
            }
        ]
    ).to_csv(reports / "manual_review_latest.csv", index=False)

    pd.DataFrame(
        [
            {
                "_top_group": "1_ALTA_CALIDAD_OPERATIVA",
                "ticker": "AAA",
                "rank": 1,
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
            }
        ]
    ).to_csv(reports / "manual_review_top.csv", index=False)

    result = build_report_consistency_audit(reports)

    assert result["status"] in {"PASS", "WARN"}
    assert result["issues"] == []


def test_save_report_consistency_audit_writes_files(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "rank": 1,
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "setup_persistence_score": 80,
                "setup_persistence_bucket": "A_PERSISTENT_HIGH_QUALITY",
            }
        ]
    ).to_csv(reports / "manual_review_latest.csv", index=False)

    pd.DataFrame(
        [
            {
                "_top_group": "1_ALTA_CALIDAD_OPERATIVA",
                "ticker": "AAA",
                "rank": 1,
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
            }
        ]
    ).to_csv(reports / "manual_review_top.csv", index=False)

    result = save_report_consistency_audit(
        reports_dir=reports,
        json_out=reports / "report_consistency_latest.json",
        markdown_out=reports / "report_consistency_latest.md",
    )

    assert result["status"] in {"PASS", "WARN"}
    assert (reports / "report_consistency_latest.json").exists()
    assert (reports / "report_consistency_latest.md").exists()