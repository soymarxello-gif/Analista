from __future__ import annotations

from tools.daily_validation import (
    DEFAULT_STEPS,
    POST_SUMMARY_STEPS,
    build_summary_text,
    collect_output_status,
)


def test_encoding_audit_is_post_summary_step():
    default_names = [step["name"] for step in DEFAULT_STEPS]
    post_names = [step["name"] for step in POST_SUMMARY_STEPS]

    assert "encoding_audit" not in default_names
    assert "encoding_audit" in post_names

    assert "daily_operator_index" in post_names
    assert "daily_run_manifest" in post_names

    assert post_names.index("daily_operator_index") < post_names.index("daily_run_manifest")
    assert post_names.index("daily_run_manifest") < post_names.index("encoding_audit")


def test_encoding_audit_post_step_is_optional_and_safe():
    matches = [
        step
        for step in POST_SUMMARY_STEPS
        if step.get("name") == "encoding_audit"
    ]

    assert len(matches) == 1

    step = matches[0]

    assert step["required"] is False
    assert step["timeout_seconds"] == 60

    assert "tools/encoding_audit.py" in step["cmd"]
    assert "--scan-dir" in step["cmd"]
    assert "reports" in step["cmd"]
    assert "--json-out" in step["cmd"]
    assert "reports/encoding_audit_latest.json" in step["cmd"]
    assert "--markdown-out" in step["cmd"]
    assert "reports/encoding_audit_latest.md" in step["cmd"]

    # Seguridad: la auditoría de encoding no debe ejecutar scanner ni aplicar cambios.
    assert "run_scanner_audited.py" not in step["cmd"]
    assert "run_scanner.py" not in step["cmd"]
    assert "--apply" not in step["cmd"]
    assert "--fix" not in step["cmd"]


def test_daily_validation_tracks_encoding_audit_outputs():
    status = collect_output_status()
    paths = {item["path"] for item in status["files"]}

    assert "reports/encoding_audit_latest.json" in paths
    assert "reports/encoding_audit_latest.md" in paths


def test_daily_validation_summary_includes_encoding_audit_reports():
    results = [
        {
            "name": "encoding_audit",
            "cmd": (
                "python tools/encoding_audit.py "
                "--scan-dir reports "
                "--json-out reports/encoding_audit_latest.json "
                "--markdown-out reports/encoding_audit_latest.md"
            ),
            "required": False,
            "returncode": 0,
            "stdout": (
                "=== ANALISTA ENCODING AUDIT ===\n"
                "Status: WARN\n"
                "Files scanned: 10\n"
                "Warn files: 1\n"
                "Error files: 0\n"
                "Total marker hits: 2\n"
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
                "path": "reports/encoding_audit_latest.json",
                "exists": True,
                "size_bytes": 100,
                "modified": "2026-06-10T12:00:00",
            },
            {
                "path": "reports/encoding_audit_latest.md",
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

    assert "encoding_audit" in text
    assert "ANALISTA ENCODING AUDIT" in text
    assert "reports/encoding_audit_latest.json" in text
    assert "reports/encoding_audit_latest.md" in text
    assert "[Secondary reports]" in text