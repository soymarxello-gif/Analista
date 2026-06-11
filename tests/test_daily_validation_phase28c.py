from __future__ import annotations

from tools.daily_validation import (
    DEFAULT_STEPS,
    POST_SUMMARY_STEPS,
    build_summary_text,
    collect_output_status,
)


def test_daily_operator_index_is_post_summary_step_not_default_step():
    default_matches = [
        step
        for step in DEFAULT_STEPS
        if step.get("name") == "daily_operator_index"
    ]

    post_matches = [
        step
        for step in POST_SUMMARY_STEPS
        if step.get("name") == "daily_operator_index"
    ]

    assert default_matches == []
    assert len(post_matches) == 1

    step = post_matches[0]

    assert step["required"] is False
    assert step["timeout_seconds"] == 60
    assert "tools/daily_operator_index.py" in step["cmd"]


def test_daily_validation_tracks_daily_operator_index_output():
    status = collect_output_status()
    paths = {item["path"] for item in status["files"]}

    assert "reports/daily_operator_index.md" in paths


def test_daily_validation_summary_includes_daily_operator_index_in_reports():
    results = [
        {
            "name": "daily_operator_index",
            "cmd": "python tools/daily_operator_index.py",
            "required": False,
            "returncode": 0,
            "stdout": "Status: PASS",
            "stderr": "",
            "passed": True,
            "timeout_seconds": 60,
            "timed_out": False,
        }
    ]

    output_status = {
        "files": [
            {
                "path": "reports/daily_operator_index.md",
                "exists": True,
                "size_bytes": 100,
                "modified": "2026-06-10T12:00:00",
            }
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

    assert "daily_operator_index" in text
    assert "reports/daily_operator_index.md" in text
    assert "[Critical reports]" in text