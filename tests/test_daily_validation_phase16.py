from __future__ import annotations

from tools.daily_validation import build_summary_text, overall_status


def test_overall_status_pass_when_required_steps_and_files_ok():
    results = [
        {"required": True, "passed": True},
        {"required": False, "passed": True},
    ]
    output_status = {
        "files": [
            {"path": "reports/latest_scan_audited.csv", "exists": True},
            {"path": "reports/manual_review_latest.csv", "exists": True},
            {"path": "reports/manual_review_latest.md", "exists": True},
        ]
    }

    assert overall_status(results, output_status) == "PASS"


def test_overall_status_fail_when_required_step_fails():
    results = [
        {"required": True, "passed": False},
    ]
    output_status = {
        "files": [
            {"path": "reports/latest_scan_audited.csv", "exists": True},
            {"path": "reports/manual_review_latest.csv", "exists": True},
            {"path": "reports/manual_review_latest.md", "exists": True},
        ]
    }

    assert overall_status(results, output_status) == "FAIL"


def test_build_summary_text_contains_core_sections():
    results = [
        {
            "name": "dummy",
            "cmd": "python dummy.py",
            "required": True,
            "returncode": 0,
            "stdout": "",
            "stderr": "",
            "passed": True,
        }
    ]
    output_status = {
        "files": [
            {
                "path": "reports/latest_scan_audited.csv",
                "exists": True,
                "size_bytes": 100,
                "modified": "2026-06-08T12:00:00",
            }
        ]
    }
    snapshot = {
        "scan_rows": 10,
        "manual_review_rows": 2,
        "signals": {"WATCHLIST": 2},
        "recommendations": {"WATCHLIST_MONITOR": 2},
        "quote_recheck_priority": {"HIGH": 1},
    }

    text = build_summary_text(results, output_status, snapshot, "PASS")

    assert "ANALISTA DAILY VALIDATION SUMMARY" in text
    assert "Status: PASS" in text
    assert "[Steps]" in text
    assert "[Output files]" in text
    assert "[Scan snapshot]" in text