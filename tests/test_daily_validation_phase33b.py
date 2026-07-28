from __future__ import annotations

from tools.daily_validation import (
    DEFAULT_STEPS,
    POST_SUMMARY_STEPS,
    build_summary_text,
    collect_output_status,
    _format_stdout_stderr_block,
    _steps_with_scanner_timeout,
)


def test_daily_quality_gate_runs_before_release_readiness_audit():
    default_names = [step["name"] for step in DEFAULT_STEPS]
    post_names = [step["name"] for step in POST_SUMMARY_STEPS]

    assert "daily_quality_gate" not in default_names
    assert "daily_quality_gate" in post_names

    assert "daily_operator_index" in post_names
    assert "daily_run_manifest" in post_names
    assert "encoding_audit" in post_names
    assert "release_readiness_audit" in post_names
    assert "ui_data_contract_audit" in post_names
    assert "streamlit_smoke_test" in post_names
    assert "gui_actions_audit" in post_names
    assert "gui_visuals_audit" in post_names
    assert "gui_release_audit" in post_names
    assert "gui_supervised_session_audit" not in post_names
    assert "gui_daily_operating_checklist_audit" not in post_names

    assert post_names.index("daily_operator_index") < post_names.index("daily_run_manifest")
    assert post_names.index("daily_run_manifest") < post_names.index("encoding_audit")
    assert post_names.index("encoding_audit") < post_names.index("daily_quality_gate")
    assert post_names.index("daily_quality_gate") < post_names.index("release_readiness_audit")
    assert post_names.index("release_readiness_audit") < post_names.index("streamlit_smoke_test")
    assert post_names.index("streamlit_smoke_test") < post_names.index("gui_actions_audit")
    assert post_names.index("gui_actions_audit") < post_names.index("gui_visuals_audit")
    assert post_names.index("gui_visuals_audit") < post_names.index("gui_release_audit")
    assert post_names.index("gui_release_audit") < post_names.index("ui_data_contract_audit")

    assert post_names[-1] == "ui_data_contract_audit"


def test_ui_refresh_can_override_scanner_timeout_without_mutating_default_steps():
    default_scanner = [
        step for step in DEFAULT_STEPS if step["name"] == "run_scanner_audited"
    ][0]

    adjusted = _steps_with_scanner_timeout(DEFAULT_STEPS, 420)
    adjusted_scanner = [
        step for step in adjusted if step["name"] == "run_scanner_audited"
    ][0]

    assert default_scanner["timeout_seconds"] == 1800
    assert adjusted_scanner["timeout_seconds"] == 420
    assert default_scanner["timeout_seconds"] == 1800


def test_daily_validation_summary_truncates_long_step_output():
    block = _format_stdout_stderr_block("stderr", "\n".join(f"line {i}" for i in range(80)), max_lines=5)

    assert len(block) == 3
    assert "line 0" in "\n".join(block)
    assert "line 20" not in "\n".join(block)
    assert "salida truncada" in block[-1]


def test_daily_quality_gate_post_step_is_optional_and_safe():
    matches = [
        step
        for step in POST_SUMMARY_STEPS
        if step.get("name") == "daily_quality_gate"
    ]

    assert len(matches) == 1

    step = matches[0]

    assert step["required"] is False
    assert step["timeout_seconds"] == 60

    assert "tools/daily_quality_gate.py" in step["cmd"]
    assert "--json-out" in step["cmd"]
    assert "reports/daily_quality_gate_latest.json" in step["cmd"]
    assert "--markdown-out" in step["cmd"]
    assert "reports/daily_quality_gate_latest.md" in step["cmd"]

    # Seguridad: el gate no debe ejecutar scanner ni aplicar cambios.
    assert "run_scanner_audited.py" not in step["cmd"]
    assert "run_scanner.py" not in step["cmd"]
    assert "--apply" not in step["cmd"]
    assert "--fix" not in step["cmd"]


def test_daily_validation_tracks_daily_quality_gate_outputs():
    status = collect_output_status()
    paths = {item["path"] for item in status["files"]}

    assert "reports/daily_quality_gate_latest.json" in paths
    assert "reports/daily_quality_gate_latest.md" in paths
    assert "reports/streamlit_smoke_test_latest.json" in paths
    assert "reports/streamlit_smoke_test_latest.md" in paths
    assert "reports/gui_actions_audit_latest.json" in paths
    assert "reports/gui_actions_audit_latest.md" in paths
    assert "reports/gui_visuals_audit_latest.json" in paths
    assert "reports/gui_visuals_audit_latest.md" in paths
    assert "reports/gui_release_audit_latest.json" in paths
    assert "reports/gui_release_audit_latest.md" in paths
    assert "reports/simple_candidate_posttest_latest.json" in paths
    assert "reports/simple_candidate_posttest_latest.md" in paths
    assert "reports/gui_supervised_session_latest.json" not in paths


def test_daily_validation_summary_includes_daily_quality_gate_reports():
    results = [
        {
            "name": "daily_quality_gate",
            "cmd": (
                "python tools/daily_quality_gate.py "
                "--json-out reports/daily_quality_gate_latest.json "
                "--markdown-out reports/daily_quality_gate_latest.md"
            ),
            "required": False,
            "returncode": 0,
            "stdout": (
                "=== ANALISTA DAILY QUALITY GATE ===\n"
                "Status: WARN\n"
                "Manual review allowed: True\n"
                "Manual review mode: REINFORCED\n"
                "Issues: 1\n"
            ),
            "stderr": "",
            "passed": True,
            "timeout_seconds": 60,
            "duration_seconds": 1.25,
            "timed_out": False,
        }
    ]

    output_status = {
        "files": [
            {
                "path": "reports/daily_quality_gate_latest.json",
                "exists": True,
                "size_bytes": 100,
                "modified": "2026-06-10T12:00:00",
            },
            {
                "path": "reports/daily_quality_gate_latest.md",
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

    assert "daily_quality_gate" in text
    assert "ANALISTA DAILY QUALITY GATE" in text
    assert "Manual review allowed: True" in text
    assert "Manual review mode: REINFORCED" in text
    assert "reports/daily_quality_gate_latest.json" in text
    assert "reports/daily_quality_gate_latest.md" in text
    assert "[Critical reports]" in text
    assert "[Step durations]" in text
    assert "duration_seconds" in text
    assert "1.25" in text
