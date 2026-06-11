from __future__ import annotations

from tools.daily_validation import (
    DEFAULT_STEPS,
    build_summary_text,
    collect_output_status,
)


def test_daily_validation_includes_reports_cleanup_as_optional_dry_run_step():
    matches = [
        step
        for step in DEFAULT_STEPS
        if step.get("name") == "reports_cleanup"
    ]

    assert len(matches) == 1

    step = matches[0]

    assert step["required"] is False
    assert step["timeout_seconds"] == 60
    assert "tools/reports_cleanup.py" in step["cmd"]
    assert "--json-out" in step["cmd"]
    assert "reports/reports_cleanup_latest.json" in step["cmd"]
    assert "--markdown-out" in step["cmd"]
    assert "reports/reports_cleanup_latest.md" in step["cmd"]

    # Seguridad: daily_validation solo debe auditar en DRY_RUN.
    assert "--apply" not in step["cmd"]


def test_daily_validation_tracks_reports_cleanup_outputs():
    status = collect_output_status()
    paths = {item["path"] for item in status["files"]}

    assert "reports/reports_cleanup_latest.json" in paths
    assert "reports/reports_cleanup_latest.md" in paths


def test_daily_validation_summary_includes_reports_cleanup_reports():
    results = [
        {
            "name": "reports_cleanup",
            "cmd": (
                "python tools/reports_cleanup.py "
                "--json-out reports/reports_cleanup_latest.json "
                "--markdown-out reports/reports_cleanup_latest.md"
            ),
            "required": False,
            "returncode": 0,
            "stdout": "Mode: DRY_RUN\nCandidates: 2\nMoved: 0",
            "stderr": "",
            "passed": True,
            "timeout_seconds": 60,
            "timed_out": False,
        }
    ]

    output_status = {
        "files": [
            {
                "path": "reports/reports_cleanup_latest.json",
                "exists": True,
                "size_bytes": 100,
                "modified": "2026-06-10T12:00:00",
            },
            {
                "path": "reports/reports_cleanup_latest.md",
                "exists": True,
                "size_bytes": 100,
                "modified": "2026-06-10T12:00:00",
            },
        ]
    }

    snapshot = {
        "scan_rows": 10,
        "manual_review_rows": 2,
        "signals": {"WATCHLIST": 2},
        "recommendations": {"WATCHLIST_MONITOR": 2},
        "quote_recheck_priority": {},
    }

    text = build_summary_text(
        results=results,
        output_status=output_status,
        snapshot=snapshot,
        status="PASS",
    )

    assert "reports_cleanup" in text
    assert "DRY_RUN" in text
    assert "Moved: 0" in text
    assert "reports/reports_cleanup_latest.json" in text
    assert "reports/reports_cleanup_latest.md" in text