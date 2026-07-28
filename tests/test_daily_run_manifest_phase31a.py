from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools.daily_run_manifest import (
    build_daily_run_manifest_markdown,
    collect_daily_run_manifest,
    save_daily_run_manifest,
    _effective_daily_validation_status,
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
        "tools/scenario_engine_audit.py",
        "tools/live_quote_recheck.py",
        "tools/trade_decision_checklist.py",
        "tools/trade_candidate_cards.py",
        "tools/trade_score_calibration.py",
        "tools/calibration_recommendations.py",
        "tools/posttest_thesis_audit.py",
        "tools/simple_candidate_posttest.py",
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
        "tools/webull_readonly_market_data_audit.py",
        "tools/cboe_market_statistics_audit.py",
        "tools/google_sheets_data_source_audit.py",
        "tools/macro_event_context.py",
        "tools/nasdaq_risk_regime_audit.py",
        "tools/gui_operational_decision_log.py",
        "tools/gui_post_session_review.py",
        "tools/gui_operational_decision_log_audit.py",
        "tools/gui_decision_quality_review.py",
        "tools/gui_decision_quality_audit.py",
        "tools/gui_weekly_operational_review.py",
        "tools/gui_weekly_operational_review_audit.py",
        "tools/gui_evidence_collection_window.py",
        "tools/gui_evidence_collection_audit.py",
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
    (reports / "scenario_engine_audit_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "rows": 50,
                "deep_analysis_rows": 50,
                "within_target_band": True,
                "shadow_mode": True,
            }
        ),
        encoding="utf-8",
    )
    (reports / "scenario_engine_audit_latest.md").write_text(
        "# scenario engine audit\n",
        encoding="utf-8",
    )
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
    (reports / "gui_weekly_operational_review_latest.json").write_text(
        json.dumps(
            {
                "status": "WARN",
                "weekly_operational_score": 65,
                "weekly_operational_bucket": "C_NEEDS_PROCESS_REVIEW",
                "weekly_recommendation": "EXTEND_SAMPLE_SIZE",
                "sessions_count": 0,
                "total_decisions": 0,
            }
        ),
        encoding="utf-8",
    )
    (reports / "gui_weekly_operational_review_latest.md").write_text("# weekly review\n", encoding="utf-8")
    (reports / "gui_weekly_operational_review_latest.csv").write_text("review_id,status\nR1,WARN\n", encoding="utf-8")
    (reports / "gui_weekly_operational_review_audit_latest.json").write_text(
        json.dumps({"status": "PASS", "critical_failures": 0}),
        encoding="utf-8",
    )
    (reports / "gui_weekly_operational_review_audit_latest.md").write_text("# weekly audit\n", encoding="utf-8")
    (reports / "gui_evidence_collection_window_latest.json").write_text(
        json.dumps(
            {
                "status": "WARN",
                "readiness_status": "INSUFFICIENT_SAMPLE",
                "calibration_readiness_score": 50,
                "readiness_bucket": "C_NEEDS_MORE_EVIDENCE",
                "sessions_count": 0,
                "total_decisions": 0,
            }
        ),
        encoding="utf-8",
    )
    (reports / "gui_evidence_collection_window_latest.md").write_text("# evidence window\n", encoding="utf-8")
    (reports / "gui_evidence_collection_window_latest.csv").write_text("window_id,status\nE1,WARN\n", encoding="utf-8")
    (reports / "gui_evidence_collection_audit_latest.json").write_text(
        json.dumps({"status": "PASS", "critical_failures": 0}),
        encoding="utf-8",
    )
    (reports / "gui_evidence_collection_audit_latest.md").write_text("# evidence audit\n", encoding="utf-8")
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
    (reports / "posttest_thesis_audit_latest.md").write_text(
        "# four-day thesis audit\n",
        encoding="utf-8",
    )
    (reports / "posttest_thesis_audit_latest.json").write_text(
        json.dumps(
            {
                "status": "WARN",
                "horizon_days": 4,
                "summary": {
                    "executed_entries": 0,
                    "no_entry_triggers": 0,
                    "win_rate": None,
                    "target_hit_rate": None,
                    "stop_hit_rate": None,
                },
                "sample_size_warning": "sample too small",
                "automatic_changes_allowed": False,
            }
        ),
        encoding="utf-8",
    )
    (reports / "simple_candidate_posttest_latest.csv").write_text(
        "ticker,horizon_sessions,return_close_pct\n",
        encoding="utf-8",
    )
    (reports / "simple_candidate_posttest_latest.md").write_text(
        "# simple candidate posttest\n",
        encoding="utf-8",
    )
    (reports / "simple_candidate_posttest_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "rows": 0,
                "report_sessions_available": 18,
                "horizon_summary": {
                    "5": {"win_rate": 0.4, "avg_return_pct": 0.01},
                    "10": {"win_rate": 0.6, "avg_return_pct": 0.02},
                    "15": {"win_rate": 0.5, "avg_return_pct": 0.03},
                },
                "do_not_change_automatically": True,
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
    (reports / "webull_readonly_market_data_latest.md").write_text("# webull readonly\n", encoding="utf-8")
    (reports / "webull_readonly_market_data_latest.json").write_text(
        json.dumps(
            {
                "status": "WARN",
                "credentials_present": False,
                "endpoint_checks": [],
                "read_only": True,
                "execution_enabled": False,
                "issues": ["missing_webull_credentials"],
            }
        ),
        encoding="utf-8",
    )
    (reports / "cboe_market_statistics_latest.md").write_text("# cboe market statistics\n", encoding="utf-8")
    (reports / "cboe_market_statistics_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "datasets_checked": 3,
                "datasets_available": 3,
                "read_only": True,
                "execution_enabled": False,
                "issues": [],
            }
        ),
        encoding="utf-8",
    )
    (reports / "google_sheets_data_source_latest.md").write_text("# google sheets source\n", encoding="utf-8")
    (reports / "google_sheets_data_source_latest.json").write_text(
        json.dumps(
            {
                "status": "WARN",
                "csv_url_present": False,
                "rows": 0,
                "valid_rows": 0,
                "stale_rows": 0,
                "read_only": True,
                "execution_enabled": False,
                "issues": ["missing_google_sheets_csv_url"],
            }
        ),
        encoding="utf-8",
    )
    (reports / "macro_event_context_latest.md").write_text("# macro context\n", encoding="utf-8")
    (reports / "macro_event_context_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "next_critical_event": "CPI release",
                "next_critical_event_date": "2026-07-14",
                "days_to_critical_event": 21,
                "event_risk_status": "CLEAR",
                "liquidity_context": "MIXED",
                "m2_change_4w_pct": 0.2,
                "reverse_repo_change_4w_pct": -3.0,
                "read_only": True,
                "execution_enabled": False,
                "issues": [],
            }
        ),
        encoding="utf-8",
    )
    (reports / "nasdaq_risk_regime_latest.md").write_text("# nasdaq risk regime\n", encoding="utf-8")
    (reports / "nasdaq_risk_regime_latest.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "macro_regime_mode": "NASDAQ_NORMAL",
                "macro_regime_confidence": "HIGH",
                "macro_risk_flag": "NASDAQ_RISK_BALANCED",
                "nasdaq_risk_score": 42.0,
                "read_only": True,
                "execution_enabled": False,
                "broker_execution": False,
                "creates_trigger_confirmed": False,
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
                "decisions_without_reason": 0,
                "decisions_without_post_review": 0,
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
    (reports / "trade_outcome_analytics_latest.json").write_text(
        json.dumps({"status": "PASS", "rows": 0, "closed_trades": 0}),
        encoding="utf-8",
    )
    (reports / "trade_outcome_analytics_latest.md").write_text("# analytics\n", encoding="utf-8")

    return tmp_path


def test_manifest_treats_final_refresh_running_as_terminal_summary_status() -> None:
    progress = {
        "status": "RUNNING",
        "phase": "final_refresh_steps",
        "current_step": "daily_run_manifest",
    }

    assert _effective_daily_validation_status("PASS", progress) == "PASS"


def test_manifest_keeps_regular_running_progress_visible() -> None:
    progress = {
        "status": "RUNNING",
        "phase": "default_steps",
        "current_step": "run_scanner_audited",
    }

    assert _effective_daily_validation_status("PASS", progress) == "RUNNING"


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
    assert data["scan_snapshot"]["scenario_engine_audit"]["deep_analysis_rows"] == 50
    assert "paper_trade_close" not in data["scan_snapshot"]
    assert "paper_trading_cycle_audit" not in data["scan_snapshot"]
    assert data["scan_snapshot"]["simple_candidate_posttest"]["status"] == "PASS"
    assert data["scan_snapshot"]["ui_data_contract"]["status"] == "PASS"
    assert data["scan_snapshot"]["streamlit_smoke_test"]["status"] == "PASS"
    assert data["scan_snapshot"]["gui_actions_audit"]["status"] == "PASS"
    assert data["scan_snapshot"]["gui_visuals_audit"]["status"] == "PASS"
    assert data["scan_snapshot"]["gui_release_audit"]["status"] == "PASS"
    assert "gui_supervised_session" not in data["scan_snapshot"]
    assert "gui_daily_operating_checklist" not in data["scan_snapshot"]
    assert data["scan_snapshot"]["alpaca_readonly_connectivity"]["status"] == "PASS"
    assert data["scan_snapshot"]["webull_readonly_market_data"]["status"] == "WARN"
    assert data["scan_snapshot"]["cboe_market_statistics"]["status"] == "PASS"
    assert data["scan_snapshot"]["google_sheets_data_source"]["status"] == "WARN"
    assert "gui_operational_decision_log" not in data["scan_snapshot"]
    assert "gui_decision_quality_review" not in data["scan_snapshot"]
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
    assert "Paper trade close:" not in text
    assert "Paper trading cycle audit:" not in text
    assert "Simple candidate posttest:" in text
    assert "UI data contract:" in text
    assert "Streamlit dashboard:" in text
    assert "GUI actions:" in text
    assert "Secondary read-only data sources:" in text


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
