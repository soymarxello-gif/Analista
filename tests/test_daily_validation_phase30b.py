from __future__ import annotations

from tools.daily_validation import (
    DEFAULT_STEPS,
    build_summary_text,
    collect_output_status,
)


def test_project_preflight_is_first_required_daily_validation_step():
    assert len(DEFAULT_STEPS) > 0

    first_step = DEFAULT_STEPS[0]

    assert first_step["name"] == "project_preflight"
    assert first_step["required"] is True
    assert first_step["timeout_seconds"] == 60

    assert "tools/project_preflight.py" in first_step["cmd"]
    assert "--json-out" in first_step["cmd"]
    assert "reports/project_preflight_latest.json" in first_step["cmd"]
    assert "--markdown-out" in first_step["cmd"]
    assert "reports/project_preflight_latest.md" in first_step["cmd"]


def test_daily_validation_tracks_project_preflight_outputs():
    status = collect_output_status()
    paths = {item["path"] for item in status["files"]}

    assert "reports/project_preflight_latest.json" in paths
    assert "reports/project_preflight_latest.md" in paths


def test_daily_validation_summary_includes_project_preflight_reports():
    results = [
        {
            "name": "project_preflight",
            "cmd": (
                "python tools/project_preflight.py "
                "--json-out reports/project_preflight_latest.json "
                "--markdown-out reports/project_preflight_latest.md"
            ),
            "required": True,
            "returncode": 0,
            "stdout": (
                "=== ANALISTA PROJECT PREFLIGHT ===\n"
                "Status: PASS\n"
                "Missing required dirs: 0\n"
                "Missing required files: 0\n"
                "Missing optional files: 0\n"
                "Failed write checks: 0\n"
            ),
            "stderr": "",
            "passed": True,
            "timeout_seconds": 60,
            "timed_out": False,
        }
    ]

    output_status = {
        "files": [
            {
                "path": "reports/project_preflight_latest.json",
                "exists": True,
                "size_bytes": 100,
                "modified": "2026-06-10T12:00:00",
            },
            {
                "path": "reports/project_preflight_latest.md",
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

    assert "project_preflight" in text
    assert "Status: PASS" in text
    assert "reports/project_preflight_latest.json" in text
    assert "reports/project_preflight_latest.md" in text
    assert "[Critical reports]" in text