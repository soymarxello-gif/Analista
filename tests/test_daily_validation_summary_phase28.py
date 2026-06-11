from __future__ import annotations

from tools.daily_validation import build_summary_text


def test_daily_validation_summary_contains_operational_sections():
    results = [
        {
            "name": "run_scanner_audited",
            "cmd": "python run_scanner_audited.py",
            "required": True,
            "returncode": 0,
            "stdout": "ok",
            "stderr": "",
            "passed": True,
            "timeout_seconds": 900,
            "timed_out": False,
        },
        {
            "name": "trade_outcome_analytics",
            "cmd": "python tools/trade_outcome_analytics.py",
            "required": False,
            "returncode": 0,
            "stdout": "Closed trades: 0",
            "stderr": "",
            "passed": True,
            "timeout_seconds": 60,
            "timed_out": False,
        },
    ]

    output_status = {
        "files": [
            {
                "path": "reports/latest_scan_audited.csv",
                "exists": True,
                "size_bytes": 100,
                "modified": "2026-06-10T10:00:00",
            },
            {
                "path": "reports/manual_review_latest.md",
                "exists": True,
                "size_bytes": 100,
                "modified": "2026-06-10T10:00:00",
            },
            {
                "path": "reports/trade_outcome_analytics_latest.md",
                "exists": True,
                "size_bytes": 100,
                "modified": "2026-06-10T10:00:00",
            },
        ]
    }

    snapshot = {
        "scan_rows": 100,
        "manual_review_rows": 10,
        "signals": {
            "WATCHLIST": 8,
            "TRIGGER_CONFIRMED": 2,
        },
        "recommendations": {
            "WATCHLIST_MONITOR": 6,
            "RECHECK_LIVE_QUOTE": 4,
        },
        "quote_recheck_priority": {
            "HIGH": 4,
        },
    }

    text = build_summary_text(
        results=results,
        output_status=output_status,
        snapshot=snapshot,
        status="PASS",
    )

    assert "[Executive summary]" in text
    assert "[Operational next steps]" in text
    assert "[Critical reports]" in text
    assert "[Secondary reports]" in text
    assert "[Scan snapshot]" in text
    assert "[Manual operating reminder]" in text
    assert "reports/manual_review_top.md" in text
    assert "reports/trade_outcome_analytics_latest.md" in text
    assert "RECHECK_LIVE_QUOTE" in text
    assert "TRIGGER_CONFIRMED" in text


def test_daily_validation_summary_marks_fail_status_as_do_not_use():
    results = [
        {
            "name": "run_scanner_audited",
            "cmd": "python run_scanner_audited.py",
            "required": True,
            "returncode": 1,
            "stdout": "",
            "stderr": "boom",
            "passed": False,
            "timeout_seconds": 900,
            "timed_out": False,
        },
    ]

    output_status = {"files": []}

    snapshot = {
        "scan_rows": None,
        "manual_review_rows": None,
        "signals": {},
        "recommendations": {},
        "quote_recheck_priority": {},
    }

    text = build_summary_text(
        results=results,
        output_status=output_status,
        snapshot=snapshot,
        status="FAIL",
    )

    assert "NO usar candidatos operativamente" in text
    assert "Required steps failed: 1" in text
    assert "stderr" in text
    assert "boom" in text


def test_daily_validation_summary_reports_timeout():
    results = [
        {
            "name": "run_scanner_audited",
            "cmd": "python run_scanner_audited.py",
            "required": True,
            "returncode": -1,
            "stdout": "",
            "stderr": "",
            "passed": False,
            "timeout_seconds": 900,
            "timed_out": True,
        },
    ]

    text = build_summary_text(
        results=results,
        output_status={"files": []},
        snapshot={
            "scan_rows": None,
            "manual_review_rows": None,
            "signals": {},
            "recommendations": {},
            "quote_recheck_priority": {},
        },
        status="FAIL",
    )

    assert "timed_out: True" in text
    assert "timeout_seconds: 900" in text