from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools import daily_validation
from tools.daily_operator_index import build_daily_operator_index_markdown
from tools.daily_run_manifest import KEY_REPORT_PATHS, KEY_SCRIPT_PATHS
from tools.release_readiness_audit import (
    collect_release_readiness_audit,
    save_release_readiness_audit,
)


DOCS = [
    "docs/OPERATING_MANUAL.md",
    "docs/DAILY_WORKFLOW.md",
    "docs/REPORTS_REFERENCE.md",
    "docs/SAFETY_RULES.md",
    "docs/CALIBRATION_GUIDE.md",
]

TOOLS = [
    "app.py",
    "tools/daily_validation.py",
    "tools/live_quote_recheck.py",
    "tools/trade_decision_checklist.py",
    "tools/trade_candidate_cards.py",
    "tools/paper_trading_journal.py",
    "tools/paper_trade_followup.py",
    "tools/paper_trade_close.py",
    "tools/paper_trading_cycle_audit.py",
    "tools/trade_score_calibration.py",
    "tools/calibration_recommendations.py",
    "tools/daily_operator_index.py",
    "tools/daily_run_manifest.py",
    "tools/project_preflight.py",
    "tools/report_consistency_audit.py",
    "tools/ui_data_contract_audit.py",
    "tools/streamlit_smoke_test.py",
    "tools/gui_actions_audit.py",
    "tools/gui_visuals_audit.py",
    "tools/gui_release_audit.py",
]

TESTS = [
    "tests/test_live_quote_recheck_phase33b.py",
    "tests/test_options_flow_phase34a.py",
    "tests/test_options_scoring_phase34b.py",
    "tests/test_trade_decision_checklist_phase35a.py",
    "tests/test_trade_candidate_cards_phase35b.py",
    "tests/test_trade_score_calibration_phase36a.py",
    "tests/test_calibration_recommendations_phase36b.py",
    "tests/test_docs_phase37a.py",
    "tests/test_paper_trading_journal_phase38a.py",
    "tests/test_paper_trade_followup_phase38b.py",
    "tests/test_paper_trade_close_phase38c.py",
    "tests/test_paper_trading_cycle_audit_phase38d.py",
    "tests/test_ui_report_loader_phase39a.py",
    "tests/test_ui_view_models_phase39a.py",
    "tests/test_streamlit_dashboard_phase39b.py",
    "tests/test_gui_actions_phase39c.py",
    "tests/test_gui_visuals_phase39d.py",
    "tests/test_gui_release_phase39e.py",
]


def _write(path: Path, text: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding=encoding)


def _make_ready_project(tmp_path: Path) -> Path:
    _write(tmp_path / "reports" / "manual_review_latest.md", "# report\n")
    _write(tmp_path / "reports" / "manual_review_top.md", "# report\n")
    
    for path in DOCS:
        _write(tmp_path / path, "# doc\n")

    for path in TOOLS:
        _write(tmp_path / path, "# tool\n")

    for path in TESTS:
        _write(tmp_path / path, "# test\n")

    _write(
        tmp_path / ".gitignore",
        "\n".join(
            [
                "reports/*_latest.*",
                "reports/*.csv",
                "reports/*.json",
                "cache/",
                "reports/tmp/",
                "*.zip",
                ".pytest_cache/",
                "__pycache__/",
            ]
        ),
        encoding="utf-8",
    )

    _write(
        tmp_path / "scoring" / "signal_classifier.py",
        (
            "def classify_signal(row, config):\n"
            "    signal = 'TRIGGER_CONFIRMED'\n"
            "    quote_status = str(row.get('quote_status') or 'MISSING')\n"
            "    execution_quote_quality = str(row.get('execution_quote_quality') or 'LOW')\n"
            "    if signal == 'TRIGGER_CONFIRMED' and (\n"
            "        execution_quote_quality != 'HIGH' or quote_status != 'VALID'\n"
            "    ):\n"
            "        signal = 'WATCHLIST'\n"
            "    return signal, []\n"
        ),
    )

    _write(
        tmp_path / "tools" / "daily_validation.py",
        "\n".join(
            [
                "live_quote_recheck",
                "trade_decision_checklist",
                "trade_candidate_cards",
                "paper_trading_journal",
                "paper_trade_followup",
                "paper_trade_close",
                "paper_trading_cycle_audit",
                "trade_score_calibration",
                "calibration_recommendations",
                "ui_data_contract_audit",
                "streamlit_smoke_test",
                "gui_actions_audit",
                "gui_visuals_audit",
                "gui_release_audit",
            ]
        ),
    )
    _write(
        tmp_path / "tools" / "daily_operator_index.py",
        "\n".join(
            [
                "reports/live_quote_recheck_latest.md",
                "reports/trade_decision_checklist_latest.md",
                "reports/trade_candidate_cards_latest.md",
                "reports/paper_trading_journal_latest.md",
                "reports/paper_trade_followup_latest.md",
                "reports/paper_trade_close_latest.md",
                "reports/paper_trading_cycle_audit_latest.md",
                "reports/trade_score_calibration_latest.md",
                "reports/calibration_recommendations_latest.md",
                "reports/ui_data_contract_audit_latest.md",
                "reports/streamlit_smoke_test_latest.md",
                "reports/gui_actions_audit_latest.md",
                "reports/gui_visuals_audit_latest.md",
                "reports/gui_release_audit_latest.md",
            ]
        ),
    )
    _write(
        tmp_path / "tools" / "daily_run_manifest.py",
        "\n".join(
            [
                "tools/live_quote_recheck.py",
                "tools/trade_decision_checklist.py",
                "tools/trade_candidate_cards.py",
                "tools/paper_trading_journal.py",
                "tools/paper_trade_followup.py",
                "tools/paper_trade_close.py",
                "tools/paper_trading_cycle_audit.py",
                "tools/trade_score_calibration.py",
                "tools/calibration_recommendations.py",
                "tools/ui_data_contract_audit.py",
                "tools/streamlit_smoke_test.py",
                "tools/gui_actions_audit.py",
                "tools/gui_visuals_audit.py",
                "tools/gui_release_audit.py",
                "reports/live_quote_recheck_latest.json",
                "reports/trade_decision_checklist_latest.json",
                "reports/trade_candidate_cards_latest.json",
                "reports/paper_trading_journal_latest.json",
                "reports/paper_trade_followup_latest.json",
                "reports/paper_trade_close_latest.json",
                "reports/paper_trading_cycle_audit_latest.json",
                "reports/trade_score_calibration_latest.json",
                "reports/calibration_recommendations_latest.json",
                "reports/ui_data_contract_audit_latest.json",
                "reports/streamlit_smoke_test_latest.json",
                "reports/gui_actions_audit_latest.json",
                "reports/gui_visuals_audit_latest.json",
                "reports/gui_release_audit_latest.json",
            ]
        ),
    )

    reports = tmp_path / "reports"
    for path in [
        "daily_validation_summary.txt",
        "daily_operator_index.md",
        "daily_quality_gate_latest.md",
        "daily_run_manifest_latest.md",
        "project_preflight_latest.md",
        "encoding_audit_latest.md",
        "latest_scan_audited.csv",
        "manual_review_latest.csv",
        "manual_review_top.csv",
        "live_quote_recheck_latest.csv",
        "live_quote_recheck_latest.md",
        "trade_decision_checklist_latest.csv",
        "trade_decision_checklist_latest.md",
        "trade_candidate_cards_latest.md",
        "paper_trading_journal_latest.csv",
        "paper_trading_journal_latest.md",
        "paper_trade_followup_latest.csv",
        "paper_trade_followup_latest.md",
        "paper_trade_close_latest.csv",
        "paper_trade_close_latest.md",
        "paper_trading_cycle_audit_latest.md",
        "trade_score_calibration_latest.csv",
        "trade_score_calibration_latest.md",
        "calibration_recommendations_latest.md",
        "ui_data_contract_audit_latest.md",
        "streamlit_smoke_test_latest.md",
        "gui_actions_audit_latest.md",
        "gui_visuals_audit_latest.md",
        "gui_release_audit_latest.md",
        "trade_outcome_analytics_latest.csv",
        "trade_outcome_analytics_latest.md",
        "reports_cleanup_latest.md",
    ]:
        _write(reports / path, "ticker\nAAA\n")

    for path in [
        "daily_quality_gate_latest.json",
        "daily_run_manifest_latest.json",
        "project_preflight_latest.json",
        "encoding_audit_latest.json",
        "latest_scan_audited.json",
        "live_quote_recheck_latest.json",
        "trade_decision_checklist_latest.json",
        "trade_candidate_cards_latest.json",
        "paper_trading_journal_latest.json",
        "paper_trade_followup_latest.json",
        "paper_trade_close_latest.json",
        "paper_trading_cycle_audit_latest.json",
        "trade_score_calibration_latest.json",
        "calibration_recommendations_latest.json",
        "ui_data_contract_audit_latest.json",
        "streamlit_smoke_test_latest.json",
        "gui_actions_audit_latest.json",
        "gui_visuals_audit_latest.json",
        "gui_release_audit_latest.json",
        "reports_cleanup_latest.json",
        "report_consistency_latest.json",
    ]:
        _write(reports / path, json.dumps({"status": "PASS"}))

    return tmp_path


def test_release_readiness_audit_generates_json_and_markdown(tmp_path: Path):
    root = _make_ready_project(tmp_path)

    result = save_release_readiness_audit(
        root=root,
        json_out=root / "reports" / "release_readiness_latest.json",
        markdown_out=root / "reports" / "release_readiness_latest.md",
    )

    assert result["status"] == "PASS"
    assert (root / "reports" / "release_readiness_latest.json").exists()
    assert (root / "reports" / "release_readiness_latest.md").exists()


def test_missing_critical_doc_fails(tmp_path: Path):
    root = _make_ready_project(tmp_path)
    (root / "docs" / "SAFETY_RULES.md").unlink()

    data = collect_release_readiness_audit(root=root)

    assert data["status"] == "FAIL"
    assert any("SAFETY_RULES.md" in item["message"] for item in data["critical_failure_items"])


def test_missing_critical_tool_fails(tmp_path: Path):
    root = _make_ready_project(tmp_path)
    (root / "tools" / "live_quote_recheck.py").unlink()

    data = collect_release_readiness_audit(root=root)

    assert data["status"] == "FAIL"
    assert any("live_quote_recheck.py" in item["message"] for item in data["critical_failure_items"])


def test_missing_latest_gitignore_rule_warns(tmp_path: Path):
    root = _make_ready_project(tmp_path)
    (root / ".gitignore").write_text(
        "reports/*.csv\nreports/*.json\ncache/\nreports/tmp/\n*.zip\n.pytest_cache/\n",
        encoding="utf-8",
    )

    data = collect_release_readiness_audit(root=root)

    assert data["status"] == "WARN"
    assert any(item["source"] == ".gitignore" for item in data["warning_items"])


def test_active_disabled_signal_usage_fails(tmp_path: Path):
    root = _make_ready_project(tmp_path)
    disabled_signal = "_".join(["BUY", "SETUP", "ACTIVE"])
    _write(root / "tools" / "unsafe_signal.py", f"SIGNAL = '{disabled_signal}'\n")

    data = collect_release_readiness_audit(root=root)

    assert data["status"] == "FAIL"
    assert any(item["source"] == "disabled_signal" for item in data["critical_failure_items"])


def test_missing_quote_status_valid_guard_fails(tmp_path: Path):
    root = _make_ready_project(tmp_path)
    _write(
        root / "scoring" / "signal_classifier.py",
        (
            "def classify_signal(row, config):\n"
            "    signal = 'TRIGGER_CONFIRMED'\n"
            "    execution_quote_quality = 'HIGH'\n"
            "    return signal, []\n"
        ),
    )

    data = collect_release_readiness_audit(root=root)

    assert data["status"] == "FAIL"
    assert any("quote_status" in item["message"] for item in data["critical_failure_items"])


def test_missing_execution_quality_high_guard_fails(tmp_path: Path):
    root = _make_ready_project(tmp_path)
    _write(
        root / "scoring" / "signal_classifier.py",
        (
            "def classify_signal(row, config):\n"
            "    signal = 'TRIGGER_CONFIRMED'\n"
            "    quote_status = 'VALID'\n"
            "    return signal, []\n"
        ),
    )

    data = collect_release_readiness_audit(root=root)

    assert data["status"] == "FAIL"
    assert any("execution_quote_quality" in item["message"] for item in data["critical_failure_items"])


def test_daily_validation_has_optional_release_readiness_audit_at_end():
    post_names = [item["name"] for item in daily_validation.POST_SUMMARY_STEPS]

    assert "release_readiness_audit" in post_names
    assert "ui_data_contract_audit" in post_names
    assert "streamlit_smoke_test" in post_names
    assert "gui_actions_audit" in post_names
    assert "gui_visuals_audit" in post_names
    assert "gui_release_audit" in post_names
    assert post_names.index("release_readiness_audit") < post_names.index("streamlit_smoke_test")
    assert post_names.index("streamlit_smoke_test") < post_names.index("gui_actions_audit")
    assert post_names.index("gui_actions_audit") < post_names.index("gui_visuals_audit")
    assert post_names.index("gui_visuals_audit") < post_names.index("gui_release_audit")
    assert post_names.index("gui_release_audit") < post_names.index("ui_data_contract_audit")
    assert post_names[-1] == "ui_data_contract_audit"

    step = next(item for item in daily_validation.POST_SUMMARY_STEPS if item["name"] == "release_readiness_audit")
    assert step["required"] is False
    assert "tools/release_readiness_audit.py" in step["cmd"]
    assert "reports/release_readiness_latest.json" in step["cmd"]
    assert "reports/release_readiness_latest.md" in step["cmd"]


def test_daily_operator_index_renders_release_readiness_section():
    text = build_daily_operator_index_markdown(
        {
            "generated_at": "2026-06-12T00:00:00",
            "validation_status": "PASS",
            "scan_rows": 1,
            "manual_review_rows": 1,
            "manual_top_rows": 1,
            "open_trades_rows": 0,
            "analytics_rows": 0,
            "trigger_count": 0,
            "watchlist_count": 1,
            "recheck_count": 0,
            "signals": {"WATCHLIST": 1},
            "recommendations": {"WATCHLIST_MONITOR": 1},
            "quote_recheck_priority": {},
            "quality_gate": {"available": False},
            "live_quote_recheck": {"available": False},
            "trade_decision_checklist": {"available": False},
            "trade_candidate_cards": {"available": False},
            "trade_score_calibration": {"available": False},
            "calibration_recommendations": {"available": False},
            "release_readiness": {
                "available": True,
                "status": "PASS",
                "critical_failures": 0,
                "warnings": 0,
            },
            "ui_data_contract": {"available": False},
            "streamlit_smoke_test": {"available": False},
            "gui_actions_audit": {"available": False},
            "gui_visuals_audit": {"available": False},
            "gui_release_audit": {"available": False},
            "top_candidates": pd.DataFrame(),
            "recheck_candidates": pd.DataFrame(),
            "open_trades": pd.DataFrame(),
            "analytics_overall": pd.DataFrame(),
            "cleanup": {},
            "preflight": {},
            "encoding_audit": {},
            "report_status": [],
        }
    )

    assert "## Release readiness" in text
    assert "- critical_failures: 0" in text
    assert "reports/release_readiness_latest.md" in text


def test_daily_run_manifest_tracks_release_readiness_outputs():
    assert "tools/release_readiness_audit.py" in KEY_SCRIPT_PATHS
    assert "tools/streamlit_smoke_test.py" in KEY_SCRIPT_PATHS
    assert "tools/gui_actions_audit.py" in KEY_SCRIPT_PATHS
    assert "tools/gui_visuals_audit.py" in KEY_SCRIPT_PATHS
    assert "tools/gui_release_audit.py" in KEY_SCRIPT_PATHS
    assert "reports/release_readiness_latest.json" in KEY_REPORT_PATHS
    assert "reports/release_readiness_latest.md" in KEY_REPORT_PATHS
    assert "reports/streamlit_smoke_test_latest.json" in KEY_REPORT_PATHS
    assert "reports/streamlit_smoke_test_latest.md" in KEY_REPORT_PATHS
    assert "reports/gui_actions_audit_latest.json" in KEY_REPORT_PATHS
    assert "reports/gui_actions_audit_latest.md" in KEY_REPORT_PATHS
    assert "reports/gui_visuals_audit_latest.json" in KEY_REPORT_PATHS
    assert "reports/gui_visuals_audit_latest.md" in KEY_REPORT_PATHS
    assert "reports/gui_release_audit_latest.json" in KEY_REPORT_PATHS
    assert "reports/gui_release_audit_latest.md" in KEY_REPORT_PATHS
