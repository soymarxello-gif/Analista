from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.history_archive import archive_current_reports
from tools.history_evolution import save_history_evolution_reports
from tools.setup_persistence_score import save_setup_persistence_reports
from tools.manual_review_persistence_enricher import save_enriched_manual_review_reports
from tools.manual_review_top import save_manual_review_top_reports

DEFAULT_STEPS = [
    {
        "name": "project_preflight",
        "cmd": [
            sys.executable,
            "tools/project_preflight.py",
            "--json-out",
            "reports/project_preflight_latest.json",
            "--markdown-out",
            "reports/project_preflight_latest.md",
        ],
        "required": True,
        "timeout_seconds": 60,
    },
    {
        "name": "run_scanner_audited",
        "cmd": [sys.executable, "run_scanner_audited.py"],
        "required": True,
        "timeout_seconds": 900,
    },
    {
        "name": "validate_latest_scan_p0",
        "cmd": [
            sys.executable,
            "validate_latest_scan_p0.py",
            "reports/latest_scan_audited.csv",
        ],
        "required": True,
        "timeout_seconds": 120,
    },
    {
        "name": "latest_scan_health",
        "cmd": [
            sys.executable,
            "tools/latest_scan_health.py",
            "--reports-dir",
            "reports",
        ],
        "required": True,
        "timeout_seconds": 120,
    },
    {
        "name": "project_consistency_audit",
        "cmd": [sys.executable, "tools/project_consistency_audit.py"],
        "required": True,
        "timeout_seconds": 120,
    },
    {
        "name": "source_coverage_audit",
        "cmd": [
            sys.executable,
            "tools/source_coverage_audit.py",
            "--json-out",
            "reports/source_coverage_latest.json",
        ],
        "required": False,
        "timeout_seconds": 120,
    },
    {
        "name": "trade_outcome_analytics",
        "cmd": [sys.executable, "tools/trade_outcome_analytics.py"],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "trade_score_calibration",
        "cmd": [
            sys.executable,
            "tools/trade_score_calibration.py",
            "--csv-out",
            "reports/trade_score_calibration_latest.csv",
            "--json-out",
            "reports/trade_score_calibration_latest.json",
            "--markdown-out",
            "reports/trade_score_calibration_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "calibration_recommendations",
        "cmd": [
            sys.executable,
            "tools/calibration_recommendations.py",
            "--calibration-csv",
            "reports/trade_score_calibration_latest.csv",
            "--calibration-json",
            "reports/trade_score_calibration_latest.json",
            "--markdown-out",
            "reports/calibration_recommendations_latest.md",
            "--json-out",
            "reports/calibration_recommendations_latest.json",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "reports_cleanup",
        "cmd": [
            sys.executable,
            "tools/reports_cleanup.py",
            "--json-out",
            "reports/reports_cleanup_latest.json",
            "--markdown-out",
            "reports/reports_cleanup_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },    
]

POST_SUMMARY_STEPS = [
    {
        "name": "live_quote_recheck",
        "cmd": [
            sys.executable,
            "tools/live_quote_recheck.py",
            "--input-csv",
            "reports/manual_review_latest.csv",
            "--csv-out",
            "reports/live_quote_recheck_latest.csv",
            "--markdown-out",
            "reports/live_quote_recheck_latest.md",
            "--json-out",
            "reports/live_quote_recheck_latest.json",
        ],
        "required": False,
        "timeout_seconds": 120,
    },
    {
        "name": "trade_decision_checklist",
        "cmd": [
            sys.executable,
            "tools/trade_decision_checklist.py",
            "--csv-out",
            "reports/trade_decision_checklist_latest.csv",
            "--markdown-out",
            "reports/trade_decision_checklist_latest.md",
            "--json-out",
            "reports/trade_decision_checklist_latest.json",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "trade_candidate_cards",
        "cmd": [
            sys.executable,
            "tools/trade_candidate_cards.py",
            "--markdown-out",
            "reports/trade_candidate_cards_latest.md",
            "--json-out",
            "reports/trade_candidate_cards_latest.json",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "paper_trading_journal",
        "cmd": [
            sys.executable,
            "tools/paper_trading_journal.py",
            "--import-today",
            "--csv-out",
            "reports/paper_trading_journal_latest.csv",
            "--json-out",
            "reports/paper_trading_journal_latest.json",
            "--markdown-out",
            "reports/paper_trading_journal_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "paper_trade_followup",
        "cmd": [
            sys.executable,
            "tools/paper_trade_followup.py",
            "--csv-out",
            "reports/paper_trade_followup_latest.csv",
            "--json-out",
            "reports/paper_trade_followup_latest.json",
            "--markdown-out",
            "reports/paper_trade_followup_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "paper_trade_close",
        "cmd": [
            sys.executable,
            "tools/paper_trade_close.py",
            "--summary",
            "--csv-out",
            "reports/paper_trade_close_latest.csv",
            "--json-out",
            "reports/paper_trade_close_latest.json",
            "--markdown-out",
            "reports/paper_trade_close_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "paper_trading_cycle_audit",
        "cmd": [
            sys.executable,
            "tools/paper_trading_cycle_audit.py",
            "--json-out",
            "reports/paper_trading_cycle_audit_latest.json",
            "--markdown-out",
            "reports/paper_trading_cycle_audit_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "daily_operator_index",
        "cmd": [
            sys.executable,
            "tools/daily_operator_index.py",
            "--output-path",
            "reports/daily_operator_index.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "daily_run_manifest",
        "cmd": [
            sys.executable,
            "tools/daily_run_manifest.py",
            "--json-out",
            "reports/daily_run_manifest_latest.json",
            "--markdown-out",
            "reports/daily_run_manifest_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "encoding_audit",
        "cmd": [
            sys.executable,
            "tools/encoding_audit.py",
            "--scan-dir",
            "reports",
            "--json-out",
            "reports/encoding_audit_latest.json",
            "--markdown-out",
            "reports/encoding_audit_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "daily_quality_gate",
        "cmd": [
            sys.executable,
            "tools/daily_quality_gate.py",
            "--json-out",
            "reports/daily_quality_gate_latest.json",
            "--markdown-out",
            "reports/daily_quality_gate_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "release_readiness_audit",
        "cmd": [
            sys.executable,
            "tools/release_readiness_audit.py",
            "--json-out",
            "reports/release_readiness_latest.json",
            "--markdown-out",
            "reports/release_readiness_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "streamlit_smoke_test",
        "cmd": [
            sys.executable,
            "tools/streamlit_smoke_test.py",
            "--json-out",
            "reports/streamlit_smoke_test_latest.json",
            "--markdown-out",
            "reports/streamlit_smoke_test_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "gui_actions_audit",
        "cmd": [
            sys.executable,
            "tools/gui_actions_audit.py",
            "--json-out",
            "reports/gui_actions_audit_latest.json",
            "--markdown-out",
            "reports/gui_actions_audit_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "gui_visuals_audit",
        "cmd": [
            sys.executable,
            "tools/gui_visuals_audit.py",
            "--json-out",
            "reports/gui_visuals_audit_latest.json",
            "--markdown-out",
            "reports/gui_visuals_audit_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "gui_release_audit",
        "cmd": [
            sys.executable,
            "tools/gui_release_audit.py",
            "--json-out",
            "reports/gui_release_audit_latest.json",
            "--markdown-out",
            "reports/gui_release_audit_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "gui_supervised_session_audit",
        "cmd": [
            sys.executable,
            "tools/gui_supervised_session_audit.py",
            "--json-out",
            "reports/gui_supervised_session_audit_latest.json",
            "--markdown-out",
            "reports/gui_supervised_session_audit_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "ui_data_contract_audit",
        "cmd": [
            sys.executable,
            "tools/ui_data_contract_audit.py",
            "--json-out",
            "reports/ui_data_contract_audit_latest.json",
            "--markdown-out",
            "reports/ui_data_contract_audit_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
]


def run_step(step: dict) -> dict:
    result = subprocess.run(
        step["cmd"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        shell=False,
    )

    return {
        "name": step["name"],
        "cmd": " ".join(step["cmd"]),
        "required": bool(step.get("required", True)),
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "passed": result.returncode == 0,
    }


def run_step(step: dict) -> dict:
    timeout_seconds = int(step.get("timeout_seconds", 600))

    print(
        f"[daily_validation] running: {step['name']} "
        f"(timeout={timeout_seconds}s)",
        flush=True,
    )

    try:
        result = subprocess.run(
            step["cmd"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            shell=False,
            timeout=timeout_seconds,
        )

        passed = result.returncode == 0

        print(
            f"[daily_validation] finished: {step['name']} "
            f"status={'PASS' if passed else 'FAIL'} "
            f"returncode={result.returncode}",
            flush=True,
        )

        return {
            "name": step["name"],
            "cmd": " ".join(step["cmd"]),
            "required": bool(step.get("required", True)),
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "passed": passed,
            "timeout_seconds": timeout_seconds,
            "timed_out": False,
        }

    except subprocess.TimeoutExpired as exc:
        print(
            f"[daily_validation] timeout: {step['name']} "
            f"after {timeout_seconds}s",
            flush=True,
        )

        stdout = exc.stdout or ""
        stderr = exc.stderr or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")

        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")

        return {
            "name": step["name"],
            "cmd": " ".join(step["cmd"]),
            "required": bool(step.get("required", True)),
            "returncode": -1,
            "stdout": str(stdout).strip(),
            "stderr": str(stderr).strip(),
            "passed": False,
            "timeout_seconds": timeout_seconds,
            "timed_out": True,
        }


def _file_status(path: Path) -> dict:
    exists = path.exists()
    relative_path = path.relative_to(ROOT).as_posix()

    return {
        "path": relative_path,
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else 0,
        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        if exists
        else None,
    }


def collect_output_status() -> dict:
    files = [
        ROOT / "reports" / "project_preflight_latest.json",
        ROOT / "reports" / "project_preflight_latest.md",
        ROOT / "reports" / "latest_scan_audited.csv",
        ROOT / "reports" / "latest_scan_audited.json",
        ROOT / "reports" / "manual_review_latest.csv",
        ROOT / "reports" / "manual_review_latest.md",
        ROOT / "reports" / "manual_review_top.csv",
        ROOT / "reports" / "manual_review_top.md",
        ROOT / "reports" / "daily_validation_summary.txt",
        ROOT / "reports" / "daily_operator_index.md",
        ROOT / "reports" / "live_quote_recheck_latest.csv",
        ROOT / "reports" / "live_quote_recheck_latest.md",
        ROOT / "reports" / "live_quote_recheck_latest.json",
        ROOT / "reports" / "trade_decision_checklist_latest.csv",
        ROOT / "reports" / "trade_decision_checklist_latest.md",
        ROOT / "reports" / "trade_decision_checklist_latest.json",
        ROOT / "reports" / "trade_candidate_cards_latest.md",
        ROOT / "reports" / "trade_candidate_cards_latest.json",
        ROOT / "reports" / "paper_trading_journal_latest.csv",
        ROOT / "reports" / "paper_trading_journal_latest.json",
        ROOT / "reports" / "paper_trading_journal_latest.md",
        ROOT / "reports" / "paper_trade_followup_latest.csv",
        ROOT / "reports" / "paper_trade_followup_latest.json",
        ROOT / "reports" / "paper_trade_followup_latest.md",
        ROOT / "reports" / "paper_trade_close_latest.csv",
        ROOT / "reports" / "paper_trade_close_latest.json",
        ROOT / "reports" / "paper_trade_close_latest.md",
        ROOT / "reports" / "paper_trading_cycle_audit_latest.json",
        ROOT / "reports" / "paper_trading_cycle_audit_latest.md",
        ROOT / "reports" / "daily_run_manifest_latest.json",
        ROOT / "reports" / "daily_run_manifest_latest.md",
        ROOT / "reports" / "encoding_audit_latest.json",
        ROOT / "reports" / "encoding_audit_latest.md",
        ROOT / "reports" / "daily_quality_gate_latest.json",
        ROOT / "reports" / "daily_quality_gate_latest.md",
        ROOT / "reports" / "release_readiness_latest.json",
        ROOT / "reports" / "release_readiness_latest.md",
        ROOT / "reports" / "ui_data_contract_audit_latest.json",
        ROOT / "reports" / "ui_data_contract_audit_latest.md",
        ROOT / "reports" / "streamlit_smoke_test_latest.json",
        ROOT / "reports" / "streamlit_smoke_test_latest.md",
        ROOT / "reports" / "gui_actions_audit_latest.json",
        ROOT / "reports" / "gui_actions_audit_latest.md",
        ROOT / "reports" / "gui_visuals_audit_latest.json",
        ROOT / "reports" / "gui_visuals_audit_latest.md",
        ROOT / "reports" / "gui_release_audit_latest.json",
        ROOT / "reports" / "gui_release_audit_latest.md",
        ROOT / "reports" / "gui_supervised_session_latest.json",
        ROOT / "reports" / "gui_supervised_session_latest.md",
        ROOT / "reports" / "gui_supervised_session_audit_latest.json",
        ROOT / "reports" / "gui_supervised_session_audit_latest.md",
        ROOT / "reports" / "reports_cleanup_latest.json",
        ROOT / "reports" / "reports_cleanup_latest.md",
        ROOT / "reports" / "source_coverage_latest.json",
        ROOT / "reports" / "history_evolution_latest.csv",
        ROOT / "reports" / "history_evolution_latest.md",
        ROOT / "reports" / "setup_persistence_latest.csv",
        ROOT / "reports" / "setup_persistence_latest.md",
        ROOT / "reports" / "trade_outcome_analytics_latest.csv",
        ROOT / "reports" / "trade_outcome_analytics_latest.md",
        ROOT / "reports" / "trade_score_calibration_latest.csv",
        ROOT / "reports" / "trade_score_calibration_latest.json",
        ROOT / "reports" / "trade_score_calibration_latest.md",
        ROOT / "reports" / "calibration_recommendations_latest.md",
        ROOT / "reports" / "calibration_recommendations_latest.json",
    ]

    return {
        "files": [_file_status(path) for path in files],
    }

def collect_scan_snapshot() -> dict:
    scan_path = ROOT / "reports" / "latest_scan_audited.csv"
    manual_path = ROOT / "reports" / "manual_review_latest.csv"
    live_recheck_path = ROOT / "reports" / "live_quote_recheck_latest.json"
    checklist_path = ROOT / "reports" / "trade_decision_checklist_latest.json"
    cards_path = ROOT / "reports" / "trade_candidate_cards_latest.json"
    paper_journal_path = ROOT / "reports" / "paper_trading_journal_latest.json"
    paper_followup_path = ROOT / "reports" / "paper_trade_followup_latest.json"
    paper_close_path = ROOT / "reports" / "paper_trade_close_latest.json"
    paper_cycle_path = ROOT / "reports" / "paper_trading_cycle_audit_latest.json"
    calibration_path = ROOT / "reports" / "trade_score_calibration_latest.json"
    calibration_recommendations_path = ROOT / "reports" / "calibration_recommendations_latest.json"
    release_readiness_path = ROOT / "reports" / "release_readiness_latest.json"
    ui_contract_path = ROOT / "reports" / "ui_data_contract_audit_latest.json"
    streamlit_smoke_path = ROOT / "reports" / "streamlit_smoke_test_latest.json"
    gui_actions_path = ROOT / "reports" / "gui_actions_audit_latest.json"
    gui_visuals_path = ROOT / "reports" / "gui_visuals_audit_latest.json"
    gui_release_path = ROOT / "reports" / "gui_release_audit_latest.json"
    gui_supervised_session_path = ROOT / "reports" / "gui_supervised_session_latest.json"
    gui_supervised_session_audit_path = ROOT / "reports" / "gui_supervised_session_audit_latest.json"

    snapshot: dict = {
        "scan_rows": None,
        "manual_review_rows": None,
        "signals": {},
        "recommendations": {},
        "quote_recheck_priority": {},
        "trade_score_calibration": {
            "status": "MISSING",
            "closed_trades": 0,
            "win_rate": "",
            "avg_r_multiple": "",
            "sample_size_warning": "",
        },
        "calibration_recommendations": {
            "status": "MISSING",
            "closed_trades": 0,
            "recommendation_count": 0,
            "sample_size_warning": "",
        },
        "release_readiness": {
            "status": "MISSING",
            "critical_failures": 0,
            "warnings": 0,
        },
        "ui_data_contract": {
            "status": "MISSING",
            "available_sources": 0,
            "missing_sources": 0,
            "invalid_sources": 0,
            "candidate_rows": 0,
            "paper_journal_rows": 0,
        },
        "streamlit_smoke_test": {
            "status": "MISSING",
            "app_exists": False,
            "import_ok": False,
            "view_models_ok": False,
            "read_only": False,
        },
        "gui_actions_audit": {
            "status": "MISSING",
            "actions_module_exists": False,
            "action_log_exists": False,
            "logged_actions": 0,
            "broker_guardrail_ok": False,
            "shell_guardrail_ok": False,
        },
        "gui_visuals_audit": {
            "status": "MISSING",
            "charts_module_exists": False,
            "app_uses_charts": False,
            "empty_data_safe": False,
            "broker_guardrail_ok": False,
            "shell_guardrail_ok": False,
        },
        "gui_release_audit": {
            "status": "MISSING",
            "app_exists": False,
            "guards_exists": False,
            "formatters_exists": False,
            "read_write_guardrail_ok": False,
            "broker_guardrail_ok": False,
            "shell_guardrail_ok": False,
            "confirmation_guardrail_ok": False,
        },
        "gui_supervised_session": {
            "status": "MISSING",
            "latest_session_id": "",
            "latest_session_status": "MISSING",
            "latest_session_result": "",
            "paper_actions_logged": 0,
            "paper_enter_count": 0,
            "closed_paper_count": 0,
            "pending_export_count": 0,
        },
        "gui_supervised_session_audit": {
            "status": "MISSING",
            "tool_exists": False,
            "data_file_can_be_created": False,
            "broker_guardrail_ok": False,
            "shell_guardrail_ok": False,
        },
        "live_quote_recheck": {
            "status": "MISSING",
            "rows": 0,
            "execution_ok_review_manually": 0,
            "keep_recheck": 0,
            "watchlist_monitor": 0,
            "avoid_execution_risk": 0,
            "data_unavailable": 0,
        },
        "trade_decision_checklist": {
            "status": "MISSING",
            "rows": 0,
            "blocked": 0,
            "needs_live_quote_recheck": 0,
            "review_manually": 0,
            "high_quality_review": 0,
        },
        "trade_candidate_cards": {
            "status": "MISSING",
            "rows": 0,
            "blocked": 0,
            "needs_live_quote_recheck": 0,
            "review_manually": 0,
            "high_quality_review": 0,
        },
        "paper_trading_journal": {
            "status": "MISSING",
            "rows": 0,
            "pending_review": 0,
            "paper_watch": 0,
            "paper_enter": 0,
            "blocked": 0,
            "needs_live_quote_recheck": 0,
        },
        "paper_trade_followup": {
            "status": "MISSING",
            "rows": 0,
            "hold_paper": 0,
            "review_near_stop": 0,
            "review_near_target": 0,
            "stop_hit_review_close": 0,
            "target_hit_review_close": 0,
            "data_unavailable": 0,
        },
        "paper_trade_close": {
            "status": "MISSING",
            "rows": 0,
            "open_paper_trades": 0,
            "closed_paper_trades": 0,
            "pending_export": 0,
            "exported_outcomes": 0,
        },
        "paper_trading_cycle_audit": {
            "status": "MISSING",
            "journal_rows": 0,
            "open_paper_count": 0,
            "closed_paper_count": 0,
            "pending_export_count": 0,
            "exported_count": 0,
            "duplicate_outcome_ids": 0,
        },
    }

    if scan_path.exists():
        df = pd.read_csv(scan_path)

        snapshot["scan_rows"] = int(len(df))

        if "signal" in df.columns:
            snapshot["signals"] = (
                df["signal"]
                .fillna("MISSING")
                .astype(str)
                .value_counts()
                .to_dict()
            )

        if "recommendation" in df.columns:
            snapshot["recommendations"] = (
                df["recommendation"]
                .fillna("MISSING")
                .astype(str)
                .value_counts()
                .to_dict()
            )

    if manual_path.exists():
        manual_df = pd.read_csv(manual_path)
        snapshot["manual_review_rows"] = int(len(manual_df))

        if "quote_recheck_priority" in manual_df.columns:
            snapshot["quote_recheck_priority"] = (
                manual_df["quote_recheck_priority"]
                .fillna("MISSING")
                .astype(str)
                .value_counts()
                .to_dict()
            )

    if live_recheck_path.exists():
        try:
            live_data = json.loads(live_recheck_path.read_text(encoding="utf-8"))
        except Exception:
            live_data = {}

        snapshot["live_quote_recheck"] = {
            "status": str(live_data.get("status", "UNKNOWN")),
            "rows": int(live_data.get("rows", 0) or 0),
            "execution_ok_review_manually": int(live_data.get("execution_ok_review_manually", 0) or 0),
            "keep_recheck": int(live_data.get("keep_recheck", 0) or 0),
            "watchlist_monitor": int(live_data.get("watchlist_monitor", 0) or 0),
            "avoid_execution_risk": int(live_data.get("avoid_execution_risk", 0) or 0),
            "data_unavailable": int(live_data.get("data_unavailable", 0) or 0),
        }

    if checklist_path.exists():
        try:
            checklist_data = json.loads(checklist_path.read_text(encoding="utf-8"))
        except Exception:
            checklist_data = {}

        snapshot["trade_decision_checklist"] = {
            "status": str(checklist_data.get("status", "UNKNOWN")),
            "rows": int(checklist_data.get("rows", 0) or 0),
            "blocked": int(checklist_data.get("blocked", 0) or 0),
            "needs_live_quote_recheck": int(checklist_data.get("needs_live_quote_recheck", 0) or 0),
            "review_manually": int(checklist_data.get("review_manually", 0) or 0),
            "high_quality_review": int(checklist_data.get("high_quality_review", 0) or 0),
        }

    if cards_path.exists():
        try:
            cards_data = json.loads(cards_path.read_text(encoding="utf-8"))
        except Exception:
            cards_data = {}

        snapshot["trade_candidate_cards"] = {
            "status": str(cards_data.get("status", "UNKNOWN")),
            "rows": int(cards_data.get("rows", 0) or 0),
            "blocked": int(cards_data.get("blocked", 0) or 0),
            "needs_live_quote_recheck": int(cards_data.get("needs_live_quote_recheck", 0) or 0),
            "review_manually": int(cards_data.get("review_manually", 0) or 0),
            "high_quality_review": int(cards_data.get("high_quality_review", 0) or 0),
        }

    if paper_journal_path.exists():
        try:
            paper_data = json.loads(paper_journal_path.read_text(encoding="utf-8"))
        except Exception:
            paper_data = {}

        snapshot["paper_trading_journal"] = {
            "status": str(paper_data.get("status", "UNKNOWN")),
            "rows": int(paper_data.get("rows", 0) or 0),
            "pending_review": int(paper_data.get("pending_review", 0) or 0),
            "paper_watch": int(paper_data.get("paper_watch", 0) or 0),
            "paper_enter": int(paper_data.get("paper_enter", 0) or 0),
            "blocked": int(paper_data.get("blocked", 0) or 0),
            "needs_live_quote_recheck": int(paper_data.get("needs_live_quote_recheck", 0) or 0),
        }

    if paper_followup_path.exists():
        try:
            paper_followup_data = json.loads(paper_followup_path.read_text(encoding="utf-8"))
        except Exception:
            paper_followup_data = {}

        snapshot["paper_trade_followup"] = {
            "status": str(paper_followup_data.get("status", "UNKNOWN")),
            "rows": int(paper_followup_data.get("rows", 0) or 0),
            "hold_paper": int(paper_followup_data.get("hold_paper", 0) or 0),
            "review_near_stop": int(paper_followup_data.get("review_near_stop", 0) or 0),
            "review_near_target": int(paper_followup_data.get("review_near_target", 0) or 0),
            "stop_hit_review_close": int(
                paper_followup_data.get("stop_hit_review_close", 0) or 0
            ),
            "target_hit_review_close": int(
                paper_followup_data.get("target_hit_review_close", 0) or 0
            ),
            "data_unavailable": int(paper_followup_data.get("data_unavailable", 0) or 0),
        }

    if paper_close_path.exists():
        try:
            paper_close_data = json.loads(paper_close_path.read_text(encoding="utf-8"))
        except Exception:
            paper_close_data = {}

        snapshot["paper_trade_close"] = {
            "status": str(paper_close_data.get("status", "UNKNOWN")),
            "rows": int(paper_close_data.get("rows", 0) or 0),
            "open_paper_trades": int(paper_close_data.get("open_paper_trades", 0) or 0),
            "closed_paper_trades": int(paper_close_data.get("closed_paper_trades", 0) or 0),
            "pending_export": int(paper_close_data.get("pending_export", 0) or 0),
            "exported_outcomes": int(paper_close_data.get("exported_outcomes", 0) or 0),
        }

    if paper_cycle_path.exists():
        try:
            paper_cycle_data = json.loads(paper_cycle_path.read_text(encoding="utf-8"))
        except Exception:
            paper_cycle_data = {}

        snapshot["paper_trading_cycle_audit"] = {
            "status": str(paper_cycle_data.get("status", "UNKNOWN")),
            "journal_rows": int(paper_cycle_data.get("journal_rows", 0) or 0),
            "open_paper_count": int(paper_cycle_data.get("open_paper_count", 0) or 0),
            "closed_paper_count": int(paper_cycle_data.get("closed_paper_count", 0) or 0),
            "pending_export_count": int(paper_cycle_data.get("pending_export_count", 0) or 0),
            "exported_count": int(paper_cycle_data.get("exported_count", 0) or 0),
            "duplicate_outcome_ids": len(paper_cycle_data.get("duplicate_outcome_ids", []) or []),
        }

    if calibration_path.exists():
        try:
            calibration_data = json.loads(calibration_path.read_text(encoding="utf-8"))
        except Exception:
            calibration_data = {}

        snapshot["trade_score_calibration"] = {
            "status": str(calibration_data.get("status", "UNKNOWN")),
            "closed_trades": int(calibration_data.get("closed_trades", 0) or 0),
            "win_rate": calibration_data.get("win_rate", ""),
            "avg_r_multiple": calibration_data.get("avg_r_multiple", ""),
            "sample_size_warning": str(calibration_data.get("sample_size_warning", "")),
        }

    if calibration_recommendations_path.exists():
        try:
            calibration_recommendations_data = json.loads(
                calibration_recommendations_path.read_text(encoding="utf-8")
            )
        except Exception:
            calibration_recommendations_data = {}

        snapshot["calibration_recommendations"] = {
            "status": str(calibration_recommendations_data.get("status", "UNKNOWN")),
            "closed_trades": int(calibration_recommendations_data.get("closed_trades", 0) or 0),
            "recommendation_count": int(
                calibration_recommendations_data.get("recommendation_count", 0) or 0
            ),
            "sample_size_warning": str(
                calibration_recommendations_data.get("sample_size_warning", "")
            ),
        }

    if release_readiness_path.exists():
        try:
            release_readiness_data = json.loads(release_readiness_path.read_text(encoding="utf-8"))
        except Exception:
            release_readiness_data = {}

        snapshot["release_readiness"] = {
            "status": str(release_readiness_data.get("status", "UNKNOWN")),
            "critical_failures": int(release_readiness_data.get("critical_failures", 0) or 0),
            "warnings": int(release_readiness_data.get("warnings", 0) or 0),
        }

    if ui_contract_path.exists():
        try:
            ui_contract_data = json.loads(ui_contract_path.read_text(encoding="utf-8"))
        except Exception:
            ui_contract_data = {}

        snapshot["ui_data_contract"] = {
            "status": str(ui_contract_data.get("status", "UNKNOWN")),
            "available_sources": int(ui_contract_data.get("available_sources", 0) or 0),
            "missing_sources": int(ui_contract_data.get("missing_sources", 0) or 0),
            "invalid_sources": int(ui_contract_data.get("invalid_sources", 0) or 0),
            "candidate_rows": int(ui_contract_data.get("candidate_rows", 0) or 0),
            "paper_journal_rows": int(ui_contract_data.get("paper_journal_rows", 0) or 0),
        }

    if streamlit_smoke_path.exists():
        try:
            streamlit_smoke_data = json.loads(streamlit_smoke_path.read_text(encoding="utf-8"))
        except Exception:
            streamlit_smoke_data = {}

        snapshot["streamlit_smoke_test"] = {
            "status": str(streamlit_smoke_data.get("status", "UNKNOWN")),
            "app_exists": bool(streamlit_smoke_data.get("app_exists", False)),
            "import_ok": bool(streamlit_smoke_data.get("import_ok", False)),
            "view_models_ok": bool(streamlit_smoke_data.get("view_models_ok", False)),
            "read_only": bool(streamlit_smoke_data.get("read_only", False)),
        }

    if gui_actions_path.exists():
        try:
            gui_actions_data = json.loads(gui_actions_path.read_text(encoding="utf-8"))
        except Exception:
            gui_actions_data = {}

        snapshot["gui_actions_audit"] = {
            "status": str(gui_actions_data.get("status", "UNKNOWN")),
            "actions_module_exists": bool(gui_actions_data.get("actions_module_exists", False)),
            "action_log_exists": bool(gui_actions_data.get("action_log_exists", False)),
            "logged_actions": int(gui_actions_data.get("logged_actions", 0) or 0),
            "broker_guardrail_ok": bool(gui_actions_data.get("broker_guardrail_ok", False)),
            "shell_guardrail_ok": bool(gui_actions_data.get("shell_guardrail_ok", False)),
        }

    if gui_visuals_path.exists():
        try:
            gui_visuals_data = json.loads(gui_visuals_path.read_text(encoding="utf-8"))
        except Exception:
            gui_visuals_data = {}

        snapshot["gui_visuals_audit"] = {
            "status": str(gui_visuals_data.get("status", "UNKNOWN")),
            "charts_module_exists": bool(gui_visuals_data.get("charts_module_exists", False)),
            "app_uses_charts": bool(gui_visuals_data.get("app_uses_charts", False)),
            "empty_data_safe": bool(gui_visuals_data.get("empty_data_safe", False)),
            "broker_guardrail_ok": bool(gui_visuals_data.get("broker_guardrail_ok", False)),
            "shell_guardrail_ok": bool(gui_visuals_data.get("shell_guardrail_ok", False)),
        }

    if gui_release_path.exists():
        try:
            gui_release_data = json.loads(gui_release_path.read_text(encoding="utf-8"))
        except Exception:
            gui_release_data = {}

        snapshot["gui_release_audit"] = {
            "status": str(gui_release_data.get("status", "UNKNOWN")),
            "app_exists": bool(gui_release_data.get("app_exists", False)),
            "guards_exists": bool(gui_release_data.get("guards_exists", False)),
            "formatters_exists": bool(gui_release_data.get("formatters_exists", False)),
            "read_write_guardrail_ok": bool(gui_release_data.get("read_write_guardrail_ok", False)),
            "broker_guardrail_ok": bool(gui_release_data.get("broker_guardrail_ok", False)),
            "shell_guardrail_ok": bool(gui_release_data.get("shell_guardrail_ok", False)),
            "confirmation_guardrail_ok": bool(gui_release_data.get("confirmation_guardrail_ok", False)),
        }

    if gui_supervised_session_path.exists():
        try:
            gui_session_data = json.loads(gui_supervised_session_path.read_text(encoding="utf-8"))
        except Exception:
            gui_session_data = {}

        snapshot["gui_supervised_session"] = {
            "status": str(gui_session_data.get("status", "UNKNOWN")),
            "latest_session_id": str(gui_session_data.get("latest_session_id", "")),
            "latest_session_status": str(gui_session_data.get("latest_session_status", "UNKNOWN")),
            "latest_session_result": str(gui_session_data.get("latest_session_result", "")),
            "paper_actions_logged": int(gui_session_data.get("paper_actions_logged", 0) or 0),
            "paper_enter_count": int(gui_session_data.get("paper_enter_count", 0) or 0),
            "closed_paper_count": int(gui_session_data.get("closed_paper_count", 0) or 0),
            "pending_export_count": int(gui_session_data.get("pending_export_count", 0) or 0),
        }

    if gui_supervised_session_audit_path.exists():
        try:
            gui_session_audit_data = json.loads(gui_supervised_session_audit_path.read_text(encoding="utf-8"))
        except Exception:
            gui_session_audit_data = {}

        snapshot["gui_supervised_session_audit"] = {
            "status": str(gui_session_audit_data.get("status", "UNKNOWN")),
            "tool_exists": bool(gui_session_audit_data.get("tool_exists", False)),
            "data_file_can_be_created": bool(gui_session_audit_data.get("data_file_can_be_created", False)),
            "broker_guardrail_ok": bool(gui_session_audit_data.get("broker_guardrail_ok", False)),
            "shell_guardrail_ok": bool(gui_session_audit_data.get("shell_guardrail_ok", False)),
        }

    return snapshot


def overall_status(results: list[dict], output_status: dict) -> str:
    required_failed = [r for r in results if r["required"] and not r["passed"]]

    missing_required_files = [
        f
        for f in output_status.get("files", [])
        if f["path"]
        in {
            "reports/latest_scan_audited.csv",
            "reports/manual_review_latest.csv",
            "reports/manual_review_latest.md",
        }
        and not f["exists"]
    ]

    if required_failed or missing_required_files:
        return "FAIL"

    optional_failed = [r for r in results if not r["required"] and not r["passed"]]
    if optional_failed:
        return "WARN"

    return "PASS"


def merge_status(
    base_status: str,
    archive_manifest: dict | None = None,
    history_evolution_result: dict | None = None,
    setup_persistence_result: dict | None = None,
) -> str:
    statuses = [base_status]

    if archive_manifest is not None:
        statuses.append(str(archive_manifest.get("status", "FAIL")))

    if history_evolution_result is not None:
        statuses.append(str(history_evolution_result.get("status", "FAIL")))

    if setup_persistence_result is not None:
        statuses.append(str(setup_persistence_result.get("status", "FAIL")))

    if "FAIL" in statuses:
        return "FAIL"

    if "WARN" in statuses:
        return "WARN"

    return "PASS"


def _format_stdout_stderr_block(label: str, value: str) -> list[str]:
    if not value:
        return []

    lines: list[str] = []
    lines.append(f"  {label}:")
    lines.append("  " + str(value).replace("\n", "\n  "))
    return lines


def _status_icon(value: bool) -> str:
    return "PASS" if value else "FAIL"


def _get_file_status_map(output_status: dict) -> dict:
    return {
        item.get("path", ""): item
        for item in output_status.get("files", [])
    }


def _format_file_line(path: str, file_map: dict) -> str:
    item = file_map.get(path, {})
    exists = bool(item.get("exists", False))
    size = item.get("size_bytes", 0)
    modified = item.get("modified")

    status = "OK" if exists else "MISSING"

    if exists:
        return f"- {status}: {path} ({size} bytes, modified={modified})"

    return f"- {status}: {path}"


def _build_operational_next_steps(status: str, snapshot: dict) -> list[str]:
    lines: list[str] = []

    lines.append("[Operational next steps]")

    if status == "FAIL":
        lines.append("- NO usar candidatos operativamente hasta revisar los errores requeridos.")
        lines.append("- Revisar primero la sección [Steps] y corregir el primer step requerido fallido.")
        lines.append("- Luego volver a correr: python .\\tools\\daily_validation.py")
        return lines

    if status == "WARN":
        lines.append("- Flujo utilizable solo con revisión manual reforzada.")
        lines.append("- Revisar steps opcionales fallidos o warnings antes de tomar decisiones.")
    else:
        lines.append("- Flujo diario completo sin fallos requeridos.")

    manual_rows = snapshot.get("manual_review_rows")
    signals = snapshot.get("signals", {})
    recommendations = snapshot.get("recommendations", {})

    trigger_count = int(signals.get("TRIGGER_CONFIRMED", 0) or 0)
    watchlist_count = int(signals.get("WATCHLIST", 0) or 0)
    recheck_count = int(recommendations.get("RECHECK_LIVE_QUOTE", 0) or 0)

    lines.append("- Revisar primero: reports/manual_review_top.md")
    lines.append("- Revisar después: reports/manual_review_latest.md")
    lines.append("- Revisar checklist operativo: reports/trade_decision_checklist_latest.md")
    lines.append("- Revisar fichas por candidato: reports/trade_candidate_cards_latest.md")
    lines.append("- Revisar journal paper trading: reports/paper_trading_journal_latest.md")
    lines.append("- Revisar seguimiento paper trading: reports/paper_trade_followup_latest.md")
    lines.append("- Revisar cierres paper manuales: reports/paper_trade_close_latest.md")
    lines.append("- Revisar auditoría ciclo paper: reports/paper_trading_cycle_audit_latest.md")
    lines.append("- Revisar calibración de scores: reports/trade_score_calibration_latest.md")
    lines.append("- Revisar recomendaciones de calibración: reports/calibration_recommendations_latest.md")
    lines.append("- Revisar release readiness: reports/release_readiness_latest.md")
    lines.append("- Revisar contrato de datos UI: reports/ui_data_contract_audit_latest.md")
    lines.append("- Revisar smoke test Streamlit: reports/streamlit_smoke_test_latest.md")
    lines.append("- Revisar auditoría de acciones GUI: reports/gui_actions_audit_latest.md")
    lines.append("- Revisar analytics: reports/trade_outcome_analytics_latest.md")

    if recheck_count > 0:
        lines.append("- Hay candidatos con RECHECK_LIVE_QUOTE: ejecutar live_quote_recheck antes de considerar operación.")
        lines.append("- Revisar reporte live: reports/live_quote_recheck_latest.md")

    if trigger_count > 0:
        lines.append(f"- Hay {trigger_count} TRIGGER_CONFIRMED: revisar manualmente quote, gráfico, entrada, stop y target.")

    if watchlist_count > 0:
        lines.append(f"- Hay {watchlist_count} WATCHLIST: priorizar solo los de mejor calidad operativa.")

    if manual_rows is not None:
        lines.append(f"- Filas en revisión manual: {manual_rows}")

    return lines


def build_summary_text(
    results: list[dict],
    output_status: dict,
    snapshot: dict,
    status: str,
) -> str:
    lines: list[str] = []

    required_failed = [r for r in results if r.get("required", True) and not r.get("passed", False)]
    optional_failed = [r for r in results if not r.get("required", True) and not r.get("passed", False)]

    file_map = _get_file_status_map(output_status)

    critical_reports = [
        "reports/project_preflight_latest.json",
        "reports/project_preflight_latest.md",
        "reports/latest_scan_audited.csv",
        "reports/latest_scan_audited.json",
        "reports/manual_review_latest.csv",
        "reports/manual_review_latest.md",
        "reports/manual_review_top.csv",
        "reports/manual_review_top.md",
        "reports/daily_validation_summary.txt",
        "reports/daily_operator_index.md",
        "reports/daily_quality_gate_latest.json",
        "reports/daily_quality_gate_latest.md",
    ]

    secondary_reports = [
        "reports/source_coverage_latest.json",
        "reports/history_evolution_latest.csv",
        "reports/history_evolution_latest.md",
        "reports/setup_persistence_latest.csv",
        "reports/setup_persistence_latest.md",
        "reports/trade_outcome_analytics_latest.csv",
        "reports/trade_outcome_analytics_latest.md",
        "reports/trade_score_calibration_latest.csv",
        "reports/trade_score_calibration_latest.json",
        "reports/trade_score_calibration_latest.md",
        "reports/calibration_recommendations_latest.md",
        "reports/calibration_recommendations_latest.json",
        "reports/live_quote_recheck_latest.csv",
        "reports/live_quote_recheck_latest.md",
        "reports/live_quote_recheck_latest.json",
        "reports/trade_decision_checklist_latest.csv",
        "reports/trade_decision_checklist_latest.md",
        "reports/trade_decision_checklist_latest.json",
        "reports/trade_candidate_cards_latest.md",
        "reports/trade_candidate_cards_latest.json",
        "reports/paper_trading_journal_latest.csv",
        "reports/paper_trading_journal_latest.json",
        "reports/paper_trading_journal_latest.md",
        "reports/paper_trade_followup_latest.csv",
        "reports/paper_trade_followup_latest.json",
        "reports/paper_trade_followup_latest.md",
        "reports/paper_trade_close_latest.csv",
        "reports/paper_trade_close_latest.json",
        "reports/paper_trade_close_latest.md",
        "reports/paper_trading_cycle_audit_latest.json",
        "reports/paper_trading_cycle_audit_latest.md",
        "reports/reports_cleanup_latest.json",
        "reports/reports_cleanup_latest.md",
        "reports/daily_run_manifest_latest.json",
        "reports/daily_run_manifest_latest.md",
        "reports/encoding_audit_latest.json",
        "reports/encoding_audit_latest.md",
        "reports/release_readiness_latest.json",
        "reports/release_readiness_latest.md",
        "reports/ui_data_contract_audit_latest.json",
        "reports/ui_data_contract_audit_latest.md",
        "reports/streamlit_smoke_test_latest.json",
        "reports/streamlit_smoke_test_latest.md",
        "reports/gui_actions_audit_latest.json",
        "reports/gui_actions_audit_latest.md",
        "reports/gui_visuals_audit_latest.json",
        "reports/gui_visuals_audit_latest.md",
        "reports/gui_release_audit_latest.json",
        "reports/gui_release_audit_latest.md",
        "reports/gui_supervised_session_latest.json",
        "reports/gui_supervised_session_latest.md",
        "reports/gui_supervised_session_audit_latest.json",
        "reports/gui_supervised_session_audit_latest.md",
    ]

    lines.append("=== ANALISTA DAILY VALIDATION SUMMARY ===")
    lines.append(f"Timestamp: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Status: {status}")
    lines.append("")

    lines.append("[Executive summary]")
    lines.append(f"- Required steps failed: {len(required_failed)}")
    lines.append(f"- Optional steps failed: {len(optional_failed)}")
    lines.append(f"- Scan rows: {snapshot.get('scan_rows')}")
    lines.append(f"- Manual review rows: {snapshot.get('manual_review_rows')}")
    live = snapshot.get("live_quote_recheck", {}) or {}
    checklist = snapshot.get("trade_decision_checklist", {}) or {}
    cards = snapshot.get("trade_candidate_cards", {}) or {}
    paper = snapshot.get("paper_trading_journal", {}) or {}
    paper_followup = snapshot.get("paper_trade_followup", {}) or {}
    paper_close = snapshot.get("paper_trade_close", {}) or {}
    paper_cycle = snapshot.get("paper_trading_cycle_audit", {}) or {}
    calibration = snapshot.get("trade_score_calibration", {}) or {}
    calibration_recommendations = snapshot.get("calibration_recommendations", {}) or {}
    release_readiness = snapshot.get("release_readiness", {}) or {}
    ui_contract = snapshot.get("ui_data_contract", {}) or {}
    streamlit_smoke = snapshot.get("streamlit_smoke_test", {}) or {}
    gui_actions = snapshot.get("gui_actions_audit", {}) or {}
    gui_visuals = snapshot.get("gui_visuals_audit", {}) or {}
    gui_release = snapshot.get("gui_release_audit", {}) or {}
    gui_session = snapshot.get("gui_supervised_session", {}) or {}
    gui_session_audit = snapshot.get("gui_supervised_session_audit", {}) or {}
    lines.append(f"- Live quote recheck rows: {live.get('rows')}")
    lines.append(f"- Trade decision checklist rows: {checklist.get('rows')}")
    lines.append(f"- Trade candidate cards rows: {cards.get('rows')}")
    lines.append(f"- Paper trading journal rows: {paper.get('rows')}")
    lines.append(f"- Paper trade follow-up rows: {paper_followup.get('rows')}")
    lines.append(f"- Paper trade close open trades: {paper_close.get('open_paper_trades')}")
    lines.append(f"- Paper trade close pending export: {paper_close.get('pending_export')}")
    lines.append(f"- Paper trading cycle audit status: {paper_cycle.get('status')}")
    lines.append(f"- Trade score calibration closed trades: {calibration.get('closed_trades')}")
    lines.append(
        "- Calibration recommendations count: "
        f"{calibration_recommendations.get('recommendation_count')}"
    )
    lines.append(f"- Release readiness status: {release_readiness.get('status')}")
    lines.append(f"- UI data contract status: {ui_contract.get('status')}")
    lines.append(f"- Streamlit smoke test status: {streamlit_smoke.get('status')}")
    lines.append(f"- GUI actions audit status: {gui_actions.get('status')}")
    lines.append(f"- GUI visuals audit status: {gui_visuals.get('status')}")
    lines.append(f"- GUI release audit status: {gui_release.get('status')}")
    lines.append(f"- GUI supervised session status: {gui_session.get('latest_session_status')}")
    lines.append(f"- GUI supervised session audit status: {gui_session_audit.get('status')}")
    lines.append("")

    lines.extend(_build_operational_next_steps(status, snapshot))
    lines.append("")

    lines.append("[Steps]")
    for result in results:
        step_status = _status_icon(bool(result.get("passed", False)))
        required = "required" if result.get("required", True) else "optional"

        lines.append(f"- {step_status}: {result.get('name')} ({required})")
        lines.append(f"  cmd: {result.get('cmd')}")
        lines.append(f"  returncode: {result.get('returncode')}")

        if "timeout_seconds" in result:
            lines.append(f"  timeout_seconds: {result.get('timeout_seconds')}")

        if result.get("timed_out"):
            lines.append("  timed_out: True")

        lines.extend(_format_stdout_stderr_block("stdout", result.get("stdout", "")))
        lines.extend(_format_stdout_stderr_block("stderr", result.get("stderr", "")))

    lines.append("")

    lines.append("[Output files]")
    for path in critical_reports + secondary_reports:
        lines.append(_format_file_line(path, file_map))

    lines.append("")

    lines.append("[Critical reports]")
    for path in critical_reports:
        lines.append(_format_file_line(path, file_map))

    lines.append("")

    lines.append("[Secondary reports]")
    for path in secondary_reports:
        lines.append(_format_file_line(path, file_map))

    lines.append("")

    lines.append("[Scan snapshot]")

    lines.append(f"- scan_rows: {snapshot.get('scan_rows')}")
    lines.append(f"- manual_review_rows: {snapshot.get('manual_review_rows')}")

    lines.append("")
    lines.append("Signals:")
    for key, value in snapshot.get("signals", {}).items():
        lines.append(f"- {key}: {value}")

    lines.append("")
    lines.append("Recommendations:")
    for key, value in snapshot.get("recommendations", {}).items():
        lines.append(f"- {key}: {value}")

    lines.append("")
    lines.append("Quote recheck priority:")
    for key, value in snapshot.get("quote_recheck_priority", {}).items():
        lines.append(f"- {key}: {value}")

    calibration = snapshot.get("trade_score_calibration", {}) or {}
    lines.append("")
    lines.append("Trade score calibration:")
    lines.append(f"- status: {calibration.get('status')}")
    lines.append(f"- closed_trades: {calibration.get('closed_trades')}")
    lines.append(f"- win_rate: {calibration.get('win_rate')}")
    lines.append(f"- avg_r_multiple: {calibration.get('avg_r_multiple')}")
    lines.append(f"- sample_size_warning: {calibration.get('sample_size_warning')}")

    calibration_recommendations = snapshot.get("calibration_recommendations", {}) or {}
    lines.append("")
    lines.append("Calibration recommendations:")
    lines.append(f"- status: {calibration_recommendations.get('status')}")
    lines.append(f"- closed_trades: {calibration_recommendations.get('closed_trades')}")
    lines.append(
        f"- recommendation_count: {calibration_recommendations.get('recommendation_count')}"
    )
    lines.append(
        f"- sample_size_warning: {calibration_recommendations.get('sample_size_warning')}"
    )

    release_readiness = snapshot.get("release_readiness", {}) or {}
    lines.append("")
    lines.append("Release readiness:")
    lines.append(f"- status: {release_readiness.get('status')}")
    lines.append(f"- critical_failures: {release_readiness.get('critical_failures')}")
    lines.append(f"- warnings: {release_readiness.get('warnings')}")

    ui_contract = snapshot.get("ui_data_contract", {}) or {}
    lines.append("")
    lines.append("UI data contract:")
    lines.append(f"- status: {ui_contract.get('status')}")
    lines.append(f"- available_sources: {ui_contract.get('available_sources')}")
    lines.append(f"- missing_sources: {ui_contract.get('missing_sources')}")
    lines.append(f"- invalid_sources: {ui_contract.get('invalid_sources')}")
    lines.append(f"- candidate_rows: {ui_contract.get('candidate_rows')}")
    lines.append(f"- paper_journal_rows: {ui_contract.get('paper_journal_rows')}")

    streamlit_smoke = snapshot.get("streamlit_smoke_test", {}) or {}
    lines.append("")
    lines.append("Streamlit smoke test:")
    lines.append(f"- status: {streamlit_smoke.get('status')}")
    lines.append(f"- app_exists: {streamlit_smoke.get('app_exists')}")
    lines.append(f"- import_ok: {streamlit_smoke.get('import_ok')}")
    lines.append(f"- view_models_ok: {streamlit_smoke.get('view_models_ok')}")
    lines.append(f"- read_only: {streamlit_smoke.get('read_only')}")

    gui_actions = snapshot.get("gui_actions_audit", {}) or {}
    lines.append("")
    lines.append("GUI actions audit:")
    lines.append(f"- status: {gui_actions.get('status')}")
    lines.append(f"- actions_module_exists: {gui_actions.get('actions_module_exists')}")
    lines.append(f"- action_log_exists: {gui_actions.get('action_log_exists')}")
    lines.append(f"- logged_actions: {gui_actions.get('logged_actions')}")
    lines.append(f"- broker_guardrail_ok: {gui_actions.get('broker_guardrail_ok')}")
    lines.append(f"- shell_guardrail_ok: {gui_actions.get('shell_guardrail_ok')}")

    gui_visuals = snapshot.get("gui_visuals_audit", {}) or {}
    lines.append("")
    lines.append("GUI visuals audit:")
    lines.append(f"- status: {gui_visuals.get('status')}")
    lines.append(f"- charts_module_exists: {gui_visuals.get('charts_module_exists')}")
    lines.append(f"- app_uses_charts: {gui_visuals.get('app_uses_charts')}")
    lines.append(f"- empty_data_safe: {gui_visuals.get('empty_data_safe')}")
    lines.append(f"- broker_guardrail_ok: {gui_visuals.get('broker_guardrail_ok')}")
    lines.append(f"- shell_guardrail_ok: {gui_visuals.get('shell_guardrail_ok')}")

    gui_release = snapshot.get("gui_release_audit", {}) or {}
    lines.append("")
    lines.append("GUI release audit:")
    lines.append(f"- status: {gui_release.get('status')}")
    lines.append(f"- app_exists: {gui_release.get('app_exists')}")
    lines.append(f"- guards_exists: {gui_release.get('guards_exists')}")
    lines.append(f"- formatters_exists: {gui_release.get('formatters_exists')}")
    lines.append(f"- read_write_guardrail_ok: {gui_release.get('read_write_guardrail_ok')}")
    lines.append(f"- broker_guardrail_ok: {gui_release.get('broker_guardrail_ok')}")
    lines.append(f"- shell_guardrail_ok: {gui_release.get('shell_guardrail_ok')}")
    lines.append(f"- confirmation_guardrail_ok: {gui_release.get('confirmation_guardrail_ok')}")

    gui_session = snapshot.get("gui_supervised_session", {}) or {}
    lines.append("")
    lines.append("GUI supervised session:")
    lines.append(f"- status: {gui_session.get('status')}")
    lines.append(f"- latest_session_id: {gui_session.get('latest_session_id')}")
    lines.append(f"- latest_session_status: {gui_session.get('latest_session_status')}")
    lines.append(f"- latest_session_result: {gui_session.get('latest_session_result')}")
    lines.append(f"- paper_actions_logged: {gui_session.get('paper_actions_logged')}")
    lines.append(f"- paper_enter_count: {gui_session.get('paper_enter_count')}")
    lines.append(f"- closed_paper_count: {gui_session.get('closed_paper_count')}")
    lines.append(f"- pending_export_count: {gui_session.get('pending_export_count')}")

    gui_session_audit = snapshot.get("gui_supervised_session_audit", {}) or {}
    lines.append("")
    lines.append("GUI supervised session audit:")
    lines.append(f"- status: {gui_session_audit.get('status')}")
    lines.append(f"- tool_exists: {gui_session_audit.get('tool_exists')}")
    lines.append(f"- data_file_can_be_created: {gui_session_audit.get('data_file_can_be_created')}")
    lines.append(f"- broker_guardrail_ok: {gui_session_audit.get('broker_guardrail_ok')}")
    lines.append(f"- shell_guardrail_ok: {gui_session_audit.get('shell_guardrail_ok')}")

    live = snapshot.get("live_quote_recheck", {}) or {}
    lines.append("")
    lines.append("Live quote recheck:")
    lines.append(f"- status: {live.get('status')}")
    lines.append(f"- rows: {live.get('rows')}")
    lines.append(f"- execution_ok_review_manually: {live.get('execution_ok_review_manually')}")
    lines.append(f"- keep_recheck: {live.get('keep_recheck')}")
    lines.append(f"- watchlist_monitor: {live.get('watchlist_monitor')}")
    lines.append(f"- avoid_execution_risk: {live.get('avoid_execution_risk')}")
    lines.append(f"- data_unavailable: {live.get('data_unavailable')}")

    checklist = snapshot.get("trade_decision_checklist", {}) or {}
    lines.append("")
    lines.append("Trade decision checklist:")
    lines.append(f"- status: {checklist.get('status')}")
    lines.append(f"- rows: {checklist.get('rows')}")
    lines.append(f"- blocked: {checklist.get('blocked')}")
    lines.append(f"- needs_live_quote_recheck: {checklist.get('needs_live_quote_recheck')}")
    lines.append(f"- review_manually: {checklist.get('review_manually')}")
    lines.append(f"- high_quality_review: {checklist.get('high_quality_review')}")

    cards = snapshot.get("trade_candidate_cards", {}) or {}
    lines.append("")
    lines.append("Trade candidate cards:")
    lines.append(f"- status: {cards.get('status')}")
    lines.append(f"- rows: {cards.get('rows')}")
    lines.append(f"- blocked: {cards.get('blocked')}")
    lines.append(f"- needs_live_quote_recheck: {cards.get('needs_live_quote_recheck')}")
    lines.append(f"- review_manually: {cards.get('review_manually')}")
    lines.append(f"- high_quality_review: {cards.get('high_quality_review')}")

    paper = snapshot.get("paper_trading_journal", {}) or {}
    lines.append("")
    lines.append("Paper trading journal:")
    lines.append(f"- status: {paper.get('status')}")
    lines.append(f"- rows: {paper.get('rows')}")
    lines.append(f"- pending_review: {paper.get('pending_review')}")
    lines.append(f"- paper_watch: {paper.get('paper_watch')}")
    lines.append(f"- paper_enter: {paper.get('paper_enter')}")
    lines.append(f"- blocked: {paper.get('blocked')}")
    lines.append(f"- needs_live_quote_recheck: {paper.get('needs_live_quote_recheck')}")

    paper_followup = snapshot.get("paper_trade_followup", {}) or {}
    lines.append("")
    lines.append("Paper trade follow-up:")
    lines.append(f"- status: {paper_followup.get('status')}")
    lines.append(f"- rows: {paper_followup.get('rows')}")
    lines.append(f"- hold_paper: {paper_followup.get('hold_paper')}")
    lines.append(f"- review_near_stop: {paper_followup.get('review_near_stop')}")
    lines.append(f"- review_near_target: {paper_followup.get('review_near_target')}")
    lines.append(f"- stop_hit_review_close: {paper_followup.get('stop_hit_review_close')}")
    lines.append(f"- target_hit_review_close: {paper_followup.get('target_hit_review_close')}")
    lines.append(f"- data_unavailable: {paper_followup.get('data_unavailable')}")

    paper_close = snapshot.get("paper_trade_close", {}) or {}
    lines.append("")
    lines.append("Paper trade close:")
    lines.append(f"- status: {paper_close.get('status')}")
    lines.append(f"- rows: {paper_close.get('rows')}")
    lines.append(f"- open_paper_trades: {paper_close.get('open_paper_trades')}")
    lines.append(f"- closed_paper_trades: {paper_close.get('closed_paper_trades')}")
    lines.append(f"- pending_export: {paper_close.get('pending_export')}")
    lines.append(f"- exported_outcomes: {paper_close.get('exported_outcomes')}")
    lines.append("- notice: paper trading only; no real order")

    paper_cycle = snapshot.get("paper_trading_cycle_audit", {}) or {}
    lines.append("")
    lines.append("Paper trading cycle audit:")
    lines.append(f"- status: {paper_cycle.get('status')}")
    lines.append(f"- journal_rows: {paper_cycle.get('journal_rows')}")
    lines.append(f"- open_paper_count: {paper_cycle.get('open_paper_count')}")
    lines.append(f"- closed_paper_count: {paper_cycle.get('closed_paper_count')}")
    lines.append(f"- pending_export_count: {paper_cycle.get('pending_export_count')}")
    lines.append(f"- exported_count: {paper_cycle.get('exported_count')}")
    lines.append(f"- duplicate_outcome_ids: {paper_cycle.get('duplicate_outcome_ids')}")

    lines.append("")
    lines.append("[Manual operating reminder]")
    lines.append("- VETO y AVOID no son operables.")
    lines.append("- RECHECK_LIVE_QUOTE no es entrada; requiere validación live quote.")
    lines.append("- TRIGGER_CONFIRMED requiere revisión manual final.")
    lines.append("- WATCHLIST es monitoreo, no compra automática.")
    lines.append("- Confirmar siempre gráfico, quote, R/R, stop, target, earnings y contexto de mercado.")

    return "\n".join(lines)


def run_daily_validation(summary_out: Path) -> int:
    results = [run_step(step) for step in DEFAULT_STEPS]

    output_status = collect_output_status()
    snapshot = collect_scan_snapshot()
    status = overall_status(results, output_status)

    summary_text = build_summary_text(
        results=results,
        output_status=output_status,
        snapshot=snapshot,
        status=status,
    )

    summary_out.parent.mkdir(parents=True, exist_ok=True)
    summary_out.write_text(summary_text, encoding="utf-8")

    post_summary_results = []
    for step in POST_SUMMARY_STEPS:
        result = run_step(step)
        post_summary_results.append(result)

    results.extend(post_summary_results)

    output_status = collect_output_status()
    snapshot = collect_scan_snapshot()
    status = overall_status(results, output_status)

    summary_text = build_summary_text(
        results=results,
        output_status=output_status,
        snapshot=snapshot,
        status=status,
    )

    summary_out.write_text(summary_text, encoding="utf-8")

    archive_manifest = archive_current_reports(root=ROOT)

    history_evolution_result = save_history_evolution_reports(
        history_root=ROOT / "reports" / "history",
        csv_out=ROOT / "reports" / "history_evolution_latest.csv",
        markdown_out=ROOT / "reports" / "history_evolution_latest.md",
    )

    setup_persistence_result = save_setup_persistence_reports(
        evolution_csv=ROOT / "reports" / "history_evolution_latest.csv",
        csv_out=ROOT / "reports" / "setup_persistence_latest.csv",
        markdown_out=ROOT / "reports" / "setup_persistence_latest.md",
    )

    manual_review_persistence_result = save_enriched_manual_review_reports(
        manual_csv=ROOT / "reports" / "manual_review_latest.csv",
        persistence_csv=ROOT / "reports" / "setup_persistence_latest.csv",
        csv_out=ROOT / "reports" / "manual_review_latest.csv",
        markdown_out=ROOT / "reports" / "manual_review_latest.md",
    )

    manual_review_top_result = save_manual_review_top_reports(
        manual_csv=ROOT / "reports" / "manual_review_latest.csv",
        csv_out=ROOT / "reports" / "manual_review_top.csv",
        markdown_out=ROOT / "reports" / "manual_review_top.md",
        per_group_limit=20,
    )

    # Refresh after history_evolution and setup_persistence are generated.
    output_status = collect_output_status()
    snapshot = collect_scan_snapshot()

    final_status = merge_status(
        base_status=overall_status(results, output_status),
        archive_manifest=archive_manifest,
        history_evolution_result=history_evolution_result,
        setup_persistence_result=setup_persistence_result,
    )

    summary_text = build_summary_text(
        results=results,
        output_status=output_status,
        snapshot=snapshot,
        status=final_status,
    )

    summary_text = (
        summary_text
        + "\n[History archive]\n"
        + f"- status: {archive_manifest['status']}\n"
        + f"- archive_dir: {archive_manifest['archive_dir']}\n"
        + f"- copied: {len(archive_manifest['copied'])}\n"
        + f"- missing_required: {len(archive_manifest['missing_required'])}\n"
        + "\n[History evolution]\n"
        + f"- status: {history_evolution_result['status']}\n"
        + f"- history_runs: {history_evolution_result['history_runs']}\n"
        + f"- tickers: {history_evolution_result['tickers']}\n"
        + "\n[Setup persistence]\n"
        + f"- status: {setup_persistence_result['status']}\n"
        + f"- rows: {setup_persistence_result['rows']}\n"
        + "\n[Manual review persistence]\n"
        + f"- status: {manual_review_persistence_result['status']}\n"
        + f"- rows: {manual_review_persistence_result['rows']}\n"
        + f"- matched: {manual_review_persistence_result['matched']}\n"
        + f"- missing: {manual_review_persistence_result['missing']}\n"
        + "\n[Manual review top]\n"
        + f"- status: {manual_review_top_result['status']}\n"
        + f"- rows: {manual_review_top_result['rows']}\n"
        + f"- groups: {manual_review_top_result['groups']}\n"        
    )

    summary_out.write_text(summary_text, encoding="utf-8")

    archive_dir = ROOT / archive_manifest["archive_dir"]

    archive_summary = archive_dir / "daily_validation_summary.txt"
    if archive_summary.parent.exists():
        archive_summary.write_text(summary_text, encoding="utf-8")

    # Re-copy enriched manual review into the same archive folder.
    if archive_dir.exists():
        for filename in [
            "manual_review_latest.csv",
            "manual_review_latest.md",
            "manual_review_top.csv",
            "manual_review_top.md",
        ]:
            src = ROOT / "reports" / filename
            dst = archive_dir / filename
            if src.exists():
                dst.write_bytes(src.read_bytes())

    print(summary_text)
    print(f"Resumen escrito en: {summary_out}")
    print(f"Historial escrito en: {ROOT / archive_manifest['archive_dir']}")

    return 0 if final_status in {"PASS", "WARN"} else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Ejecuta validación diaria completa de Analista.")
    parser.add_argument(
        "--summary-out",
        default="reports/daily_validation_summary.txt",
    )
    args = parser.parse_args()

    return run_daily_validation(ROOT / args.summary_out)


if __name__ == "__main__":
    raise SystemExit(main())
