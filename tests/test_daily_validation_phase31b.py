from __future__ import annotations

from tools.daily_validation import (
    DEFAULT_STEPS,
    POST_SUMMARY_STEPS,
    build_summary_text,
    collect_output_status,
)


def test_daily_run_manifest_is_post_summary_step_after_operator_index():
    default_names = [step["name"] for step in DEFAULT_STEPS]
    post_names = [step["name"] for step in POST_SUMMARY_STEPS]

    assert "daily_run_manifest" not in default_names
    assert "daily_operator_index" in post_names
    assert "daily_run_manifest" in post_names

    assert post_names.index("daily_operator_index") < post_names.index("daily_run_manifest")


def test_daily_run_manifest_post_step_is_optional_and_safe():
    matches = [
        step
        for step in POST_SUMMARY_STEPS
        if step.get("name") == "daily_run_manifest"
    ]

    assert len(matches) == 1

    step = matches[0]

    assert step["required"] is False
    assert step["timeout_seconds"] == 60

    assert "tools/daily_run_manifest.py" in step["cmd"]
    assert "--json-out" in step["cmd"]
    assert "reports/daily_run_manifest_latest.json" in step["cmd"]
    assert "--markdown-out" in step["cmd"]
    assert "reports/daily_run_manifest_latest.md" in step["cmd"]

    # Seguridad: el manifiesto no debe ejecutar scanner ni limpieza destructiva.
    assert "run_scanner_audited.py" not in step["cmd"]
    assert "run_scanner.py" not in step["cmd"]
    assert "--apply" not in step["cmd"]


def test_daily_validation_tracks_daily_run_manifest_outputs():
    status = collect_output_status()
    paths = {item["path"] for item in status["files"]}

    assert "reports/daily_run_manifest_latest.json" in paths
    assert "reports/daily_run_manifest_latest.md" in paths


def test_daily_validation_summary_includes_daily_run_manifest_reports():
    results = [
        {
            "name": "daily_run_manifest",
            "cmd": (
                "python tools/daily_run_manifest.py "
                "--json-out reports/daily_run_manifest_latest.json "
                "--markdown-out reports/daily_run_manifest_latest.md"
            ),
            "required": False,
            "returncode": 0,
            "stdout": (
                "=== ANALISTA DAILY RUN MANIFEST ===\n"
                "Status: PASS\n"
                "Daily validation: PASS\n"
                "Project preflight: PASS\n"
                "Reports cleanup: PASS\n"
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
                "path": "reports/daily_run_manifest_latest.json",
                "exists": True,
                "size_bytes": 100,
                "modified": "2026-06-10T12:00:00",
            },
            {
                "path": "reports/daily_run_manifest_latest.md",
                "exists": True,
                "size_bytes": 100,
                "modified": "2026-06-10T12:00:00",
            },
        ]
    }

    snapshot = {
        "scan_rows": 364,
        "manual_review_rows": 45,
        "signals": {"WATCHLIST": 45, "AVOID": 54, "VETO": 265},
        "recommendations": {
            "WATCHLIST_MONITOR": 30,
            "RECHECK_LIVE_QUOTE": 15,
        },
        "quote_recheck_priority": {},
    }

    text = build_summary_text(
        results=results,
        output_status=output_status,
        snapshot=snapshot,
        status="PASS",
    )

    assert "daily_run_manifest" in text
    assert "ANALISTA DAILY RUN MANIFEST" in text
    assert "reports/daily_run_manifest_latest.json" in text
    assert "reports/daily_run_manifest_latest.md" in text
    assert "[Secondary reports]" in text