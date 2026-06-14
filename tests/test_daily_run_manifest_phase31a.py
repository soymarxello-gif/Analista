from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools.daily_run_manifest import (
    build_daily_run_manifest_markdown,
    collect_daily_run_manifest,
    save_daily_run_manifest,
)


def _make_project(tmp_path: Path) -> Path:
    tools = tmp_path / "tools"
    reports = tmp_path / "reports"
    tools.mkdir()
    reports.mkdir()

    scripts = [
        "run_scanner_audited.py",
        "validate_latest_scan_p0.py",
        "tools/daily_validation.py",
        "tools/daily_operator_index.py",
        "tools/project_preflight.py",
        "tools/reports_cleanup.py",
        "tools/trade_outcome_analytics.py",
        "tools/trade_outcome_tracker.py",
        "tools/open_trade_snapshot.py",
        "tools/latest_scan_health.py",
        "tools/source_coverage_audit.py",
        "tools/live_quote_recheck.py",
        "tools/trade_decision_checklist.py",
        "tools/trade_candidate_cards.py",
        "tools/paper_trading_journal.py",
        "tools/paper_trade_followup.py",
        "tools/paper_trade_close.py",
        "tools/paper_trading_cycle_audit.py",
        "tools/trade_score_calibration.py",
        "tools/calibration_recommendations.py",
        "tools/release_readiness_audit.py",
        "tools/ui_data_contract_audit.py",
        "tools/streamlit_smoke_test.py",
        "tools/gui_actions_audit.py",
        "tools/gui_visuals_audit.py",
        "tools/gui_release_audit.py",
        "tools/gui_supervised_session.py",
        "tools/gui_supervised_session_audit.py",
        "tools/gui_daily_operating_checklist.py",
        "tools/gui_daily_operating_checklist_audit.py",
        "tools/alpaca_readonly_connectivity_audit.py",
        "tools/gui_operational_decision_log.py",
        "tools/gui_post_session_review.py",
        "tools/gui_operational_decision_log_audit.py",
        "tools/gui_decision_quality_review.py",
        "tools/gui_decision_quality_audit.py",
    ]

    for script in scripts:
        path = tmp_path / script
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {script}\n", encoding="utf-8")

    (reports / "daily_validation_summary.txt").write_text(
        "=== ANALISTA DAILY VALIDATION SUMMARY ===\nStatus: PASS\n",
        encoding="utf-8",
    )

    preflight = {
        "status": "PASS",
        "summary": {
            "missing_required_dirs": [],
            "missing_required_files": [],
            "missing_optional_files": [],
            "failed_write_checks": [],
        },
    }
    (reports / "project_preflight_latest.json").write_text(
        json.dumps(preflight, indent=2),
        encoding="utf-8",
    )
    (reports / "project_preflight_latest.md").write_text("# preflight\n", encoding="utf-8")

    cleanup = {
        "status": "PASS",
        "mode": "DRY_RUN",
        "candidate_count": 0,
        "moved_count": 0,
    }
    (reports / "reports_cleanup_latest.json").write_text(
        json.dumps(cleanup, indent=2),
        encoding="utf-8",
    )
    (reports / "reports_cleanup_latest.md").write_text("# cleanup\n", encoding="utf-8")

    pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "quote_recheck_priority": "",
            },
            {
                "ticker": "BBB",
                "signal": "WATCHLIST",
                "recommendation": "RECHECK_LIVE_QUOTE",
                "quote_recheck_priority": "HIGH",
            },
        ]
    ).to_csv(reports / "latest_scan_audited.csv", index=False)

    pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "quote_recheck_priority": "",
            },
            {
                "ticker": "BBB",
                "signal": "WATCHLIST",
                "recommendation": "RECHECK_LIVE_QUOTE",
                "quote_recheck_priority": "HIGH",
            },
        ]
    ).to_csv(reports / "manual_review_latest.csv", index=False)

    (reports / "latest_scan_audited.json").write_text("[]\n", encoding="utf-8")
    (reports / "manual_review_latest.md").write_text("# manual\n", encoding="utf-8")
    (reports / "manual_review_top.csv").write_text("ticker\nAAA\n", encoding="utf-8")
    (reports / "manual_review_top.md").write_text("# top\n", encoding="utf-8")
    (reports / "daily_operator_index.md").write_text("# index\n", encoding="utf-8")
    (reports / "live_quote_recheck_latest.csv").write_text("ticker,recheck_decision\n", encoding="utf-8")
    (reports / "live_quote_recheck_latest.md").write_text("# live\n", encoding="utf-8")
    (reports / "live_quote_recheck_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "rows": 0,
                "execution_ok_review_manually": 0,
                "keep_recheck": 0,
                "watchlist_monitor": 0,
                "avoid_execution_risk": 0,
                "data_unavailable": 0,
            }
        ),
        encoding="utf-8",
    )
    (reports / "trade_decision_checklist_latest.csv").write_text(
        "ticker,checklist_status\n",
        encoding="utf-8",
    )
    (reports / "trade_decision_checklist_latest.md").write_text("# checklist\n", encoding="utf-8")
    (reports / "trade_decision_checklist_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "rows": 0,
                "blocked": 0,
                "needs_live_quote_recheck": 0,
                "review_manually": 0,
                "high_quality_review": 0,
            }
        ),
        encoding="utf-8",
    )
    (reports / "trade_candidate_cards_latest.md").write_text("# cards\n", encoding="utf-8")
    (reports / "trade_candidate_cards_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "rows": 0,
                "high_quality_review": 0,
                "review_manually": 0,
                "needs_live_quote_recheck": 0,
                "blocked": 0,
            }
        ),
        encoding="utf-8",
    )
    (reports / "paper_trading_journal_latest.csv").write_text(
        "ticker,manual_decision\n",
        encoding="utf-8",
    )
    (reports / "paper_trading_journal_latest.md").write_text("# paper journal\n", encoding="utf-8")
    (reports / "paper_trading_journal_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "rows": 0,
                "pending_review": 0,
                "paper_watch": 0,
                "paper_enter": 0,
                "blocked": 0,
                "needs_live_quote_recheck": 0,
            }
        ),
        encoding="utf-8",
    )
    (reports / "paper_trade_followup_latest.csv").write_text(
        "ticker,followup_decision\n",
        encoding="utf-8",
    )
    (reports / "paper_trade_followup_latest.md").write_text("# paper followup\n", encoding="utf-8")
    (reports / "paper_trade_followup_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "rows": 0,
                "hold_paper": 0,
                "review_near_stop": 0,
                "review_near_target": 0,
                "stop_hit_review_close": 0,
                "target_hit_review_close": 0,
                "data_unavailable": 0,
            }
        ),
        encoding="utf-8",
    )
    (reports / "paper_trade_close_latest.csv").write_text(
        "ticker,paper_close_action\n",
        encoding="utf-8",
    )
    (reports / "paper_trade_close_latest.md").write_text("# paper close\n", encoding="utf-8")
    (reports / "paper_trade_close_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "rows": 0,
                "open_paper_trades": 0,
                "closed_paper_trades": 0,
                "pending_export": 0,
                "exported_outcomes": 0,
            }
        ),
        encoding="utf-8",
    )
    (reports / "paper_trading_cycle_audit_latest.md").write_text(
        "# paper cycle\n",
        encoding="utf-8",
    )
    (reports / "paper_trading_cycle_audit_latest.json").write_text(
        json.dumps(
            {
                "status": "WARN",
                "journal_rows": 0,
                "open_paper_count": 0,
                "closed_paper_count": 0,
                "pending_export_count": 0,
                "exported_count": 0,
                "duplicate_outcome_ids": [],
            }
        ),
        encoding="utf-8",
    )
    (reports / "trade_score_calibration_latest.csv").write_text(
        "group,group_value,closed_trades\nOVERALL,ALL_CLOSED,0\n",
        encoding="utf-8",
    )
    (reports / "trade_score_calibration_latest.md").write_text("# calibration\n", encoding="utf-8")
    (reports / "trade_score_calibration_latest.json").write_text(
        json.dumps(
            {
                "status": "WARN",
                "closed_trades": 0,
                "win_rate": "",
                "avg_r_multiple": "",
                "sample_size_warning": "sample too small",
            }
        ),
        encoding="utf-8",
    )
    (reports / "calibration_recommendations_latest.md").write_text(
        "# calibration recommendations\n",
        encoding="utf-8",
    )
    (reports / "calibration_recommendations_latest.json").write_text(
        json.dumps(
            {
                "status": "WARN",
                "closed_trades": 0,
                "sample_size_warning": "sample too small",
                "recommendation_count": 1,
                "do_not_change_automatically": True,
                "recommendations": [],
            }
        ),
        encoding="utf-8",
    )
    (reports / "release_readiness_latest.md").write_text("# release\n", encoding="utf-8")
    (reports / "release_readiness_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "critical_failures": 0,
                "warnings": 0,
            }
        ),
        encoding="utf-8",
    )
    (reports / "ui_data_contract_audit_latest.md").write_text("# ui contract\n", encoding="utf-8")
    (reports / "ui_data_contract_audit_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "available_sources": 10,
                "missing_sources": 0,
                "invalid_sources": 0,
                "candidate_rows": 2,
                "paper_journal_rows": 0,
            }
        ),
        encoding="utf-8",
    )
    (reports / "streamlit_smoke_test_latest.md").write_text("# streamlit smoke\n", encoding="utf-8")
    (reports / "streamlit_smoke_test_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "app_exists": True,
                "import_ok": True,
                "view_models_ok": True,
                "read_only": True,
            }
        ),
        encoding="utf-8",
    )
    (reports / "gui_actions_audit_latest.md").write_text("# gui actions\n", encoding="utf-8")
    (reports / "gui_actions_audit_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "actions_module_exists": True,
                "action_log_exists": True,
                "logged_actions": 1,
                "broker_guardrail_ok": True,
                "shell_guardrail_ok": True,
            }
        ),
        encoding="utf-8",
    )
    (reports / "gui_visuals_audit_latest.md").write_text("# gui visuals\n", encoding="utf-8")
    (reports / "gui_visuals_audit_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "charts_module_exists": True,
                "app_uses_charts": True,
                "empty_data_safe": True,
                "broker_guardrail_ok": True,
                "shell_guardrail_ok": True,
            }
        ),
        encoding="utf-8",
    )
    (reports / "gui_release_audit_latest.md").write_text("# gui release\n", encoding="utf-8")
    (reports / "gui_release_audit_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "app_exists": True,
                "guards_exists": True,
                "formatters_exists": True,
                "read_write_guardrail_ok": True,
                "broker_guardrail_ok": True,
                "shell_guardrail_ok": True,
                "confirmation_guardrail_ok": True,
            }
        ),
        encoding="utf-8",
    )
    (reports / "gui_supervised_session_latest.md").write_text("# gui supervised session\n", encoding="utf-8")
    (reports / "gui_supervised_session_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "latest_session_id": "S1",
                "latest_session_status": "OPEN",
                "latest_session_result": "",
                "paper_actions_logged": 2,
                "paper_enter_count": 1,
                "closed_paper_count": 0,
                "pending_export_count": 0,
            }
        ),
        encoding="utf-8",
    )
    (reports / "gui_supervised_session_audit_latest.md").write_text("# gui supervised audit\n", encoding="utf-8")
    (reports / "gui_supervised_session_audit_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "tool_exists": True,
                "data_file_can_be_created": True,
                "broker_guardrail_ok": True,
                "shell_guardrail_ok": True,
            }
        ),
        encoding="utf-8",
    )
    (reports / "gui_daily_operating_checklist_latest.md").write_text("# gui daily checklist\n", encoding="utf-8")
    (reports / "gui_daily_operating_checklist_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "checklist_id": "C1",
                "checklist_date": "2026-06-14",
                "pending_steps": 0,
                "done_steps": 10,
                "blocked_steps": 0,
                "skipped_steps": 0,
                "required_pending_steps": 0,
                "latest_result": "PASS",
            }
        ),
        encoding="utf-8",
    )
    (reports / "gui_daily_operating_checklist_audit_latest.md").write_text(
        "# gui daily checklist audit\n",
        encoding="utf-8",
    )
    (reports / "gui_daily_operating_checklist_audit_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "tool_exists": True,
                "data_file_can_be_created": True,
                "no_real_order_notice_present": True,
                "manual_review_only": True,
                "critical_failures": 0,
                "warnings": 0,
            }
        ),
        encoding="utf-8",
    )
    (reports / "alpaca_readonly_connectivity_latest.md").write_text("# alpaca readonly\n", encoding="utf-8")
    (reports / "alpaca_readonly_connectivity_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "credentials_present": True,
                "account_check": {"status": "PASS"},
                "clock_check": {"status": "PASS"},
                "iex_quote_check": {"status": "PASS"},
                "account_summary": {"status": "ACTIVE"},
                "read_only": True,
                "execution_enabled": False,
                "orders_endpoint_called": False,
            }
        ),
        encoding="utf-8",
    )
    (reports / "gui_operational_decision_log_latest.md").write_text("# decision log\n", encoding="utf-8")
    (reports / "gui_operational_decision_log_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "decisions_today": 1,
                "paper_watch_decisions": 1,
                "paper_enter_decisions": 0,
                "skip_decisions": 0,
                "needs_recheck_decisions": 0,
                "decisions_without_reason": 0,
                "decisions_without_post_review": 1,
                "lessons_added": 0,
            }
        ),
        encoding="utf-8",
    )
    (reports / "gui_post_session_review_latest.md").write_text("# post session\n", encoding="utf-8")
    (reports / "gui_post_session_review_latest.json").write_text(
        json.dumps(
            {
                "status": "WARN",
                "decisions_today": 1,
                "decisions_without_post_review": 1,
                "lessons_added": 0,
            }
        ),
        encoding="utf-8",
    )
    (reports / "gui_operational_decision_log_audit_latest.md").write_text("# decision audit\n", encoding="utf-8")
    (reports / "gui_operational_decision_log_audit_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "tool_exists": True,
                "post_session_review_exists": True,
                "data_file_can_be_created": True,
                "decision_log_reports_generated": True,
                "post_session_reports_generated": True,
            }
        ),
        encoding="utf-8",
    )
    (reports / "gui_decision_quality_review_latest.csv").write_text(
        "decision_id,decision_quality_score\n",
        encoding="utf-8",
    )
    (reports / "gui_decision_quality_review_latest.md").write_text("# quality\n", encoding="utf-8")
    (reports / "gui_decision_quality_review_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "total_decisions": 1,
                "decision_quality_score": 92,
                "decision_quality_bucket": "A_DISCIPLINED",
                "paper_enter_count": 0,
                "decisions_without_reason": 0,
                "decisions_without_post_review": 0,
                "paper_enter_with_low_quote_quality": 0,
                "quality_warnings_count": 0,
            }
        ),
        encoding="utf-8",
    )
    (reports / "gui_decision_quality_audit_latest.md").write_text("# quality audit\n", encoding="utf-8")
    (reports / "gui_decision_quality_audit_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "tool_exists": True,
                "review_reports_generated": True,
                "critical_failures": 0,
            }
        ),
        encoding="utf-8",
    )
    (reports / "open_trades_snapshot_latest.csv").write_text("ticker\n", encoding="utf-8")
    (reports / "open_trades_snapshot_latest.md").write_text("# open\n", encoding="utf-8")
    (reports / "trade_outcome_analytics_latest.csv").write_text("group\n", encoding="utf-8")
    (reports / "trade_outcome_analytics_latest.md").write_text("# analytics\n", encoding="utf-8")

    return tmp_path


def test_collect_daily_run_manifest_reads_core_statuses(tmp_path: Path):
    root = _make_project(tmp_path)

    data = collect_daily_run_manifest(root=root)

    assert data["status"] == "PASS"
    assert data["daily_validation"]["status"] == "PASS"
    assert data["project_preflight"]["status"] == "PASS"
    assert data["reports_cleanup"]["status"] == "PASS"
    assert data["reports_cleanup"]["mode"] == "DRY_RUN"
    assert data["scan_snapshot"]["latest_scan_rows"] == 2
    assert data["scan_snapshot"]["manual_review_rows"] == 2
    assert data["scan_snapshot"]["recommendations"]["RECHECK_LIVE_QUOTE"] == 1
    assert data["scan_snapshot"]["paper_trade_close"]["status"] == "PASS"
    assert data["scan_snapshot"]["paper_trading_cycle_audit"]["status"] == "WARN"
    assert data["scan_snapshot"]["ui_data_contract"]["status"] == "PASS"
    assert data["scan_snapshot"]["streamlit_smoke_test"]["status"] == "PASS"
    assert data["scan_snapshot"]["gui_actions_audit"]["status"] == "PASS"
    assert data["scan_snapshot"]["gui_visuals_audit"]["status"] == "PASS"
    assert data["scan_snapshot"]["gui_release_audit"]["status"] == "PASS"
    assert data["scan_snapshot"]["gui_supervised_session"]["latest_session_status"] == "OPEN"
    assert data["scan_snapshot"]["gui_supervised_session_audit"]["status"] == "PASS"
    assert data["scan_snapshot"]["gui_daily_operating_checklist"]["status"] == "PASS"
    assert data["scan_snapshot"]["alpaca_readonly_connectivity"]["status"] == "PASS"
    assert data["scan_snapshot"]["gui_operational_decision_log"]["status"] == "PASS"
    assert data["scan_snapshot"]["gui_post_session_review"]["status"] == "WARN"
    assert data["scan_snapshot"]["gui_decision_quality_review"]["status"] == "PASS"
    assert data["summary"]["missing_script_files"] == []

    script_files = data["script_files"]
    assert len(script_files) > 0
    assert all(item["exists"] for item in script_files)
    assert all(len(item["sha256"]) == 64 for item in script_files)


def test_daily_run_manifest_markdown_contains_sections(tmp_path: Path):
    root = _make_project(tmp_path)

    data = collect_daily_run_manifest(root=root)
    text = build_daily_run_manifest_markdown(data)

    assert "Analista - daily run manifest" in text
    assert "## Decision gate" in text
    assert "## Core statuses" in text
    assert "## Git" in text
    assert "## Scan snapshot" in text
    assert "## Script files" in text
    assert "## Report files" in text
    assert "## Summary" in text
    assert "RECHECK_LIVE_QUOTE" in text
    assert "Paper trade close:" in text
    assert "Paper trading cycle audit:" in text
    assert "UI data contract:" in text
    assert "Streamlit dashboard:" in text
    assert "GUI actions:" in text


def test_save_daily_run_manifest_writes_outputs(tmp_path: Path):
    root = _make_project(tmp_path)

    json_out = root / "reports" / "daily_run_manifest_latest.json"
    markdown_out = root / "reports" / "daily_run_manifest_latest.md"

    result = save_daily_run_manifest(
        root=root,
        json_out=json_out,
        markdown_out=markdown_out,
    )

    assert result["status"] == "PASS"
    assert result["daily_validation_status"] == "PASS"
    assert result["project_preflight_status"] == "PASS"
    assert result["cleanup_status"] == "PASS"
    assert result["latest_scan_rows"] == 2
    assert result["manual_review_rows"] == 2
    assert result["missing_script_files"] == 0
    assert json_out.exists()
    assert markdown_out.exists()

    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert data["status"] == "PASS"

    text = markdown_out.read_text(encoding="utf-8")
    assert "daily run manifest" in text


def test_manifest_warns_when_script_file_missing(tmp_path: Path):
    root = _make_project(tmp_path)

    (root / "tools" / "reports_cleanup.py").unlink()

    data = collect_daily_run_manifest(root=root)

    assert data["status"] == "WARN"
    assert "tools/reports_cleanup.py" in data["summary"]["missing_script_files"]
