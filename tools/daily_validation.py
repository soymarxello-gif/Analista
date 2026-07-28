from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROGRESS_OUT = ROOT / "reports" / "daily_validation_progress_latest.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.history_archive import archive_current_reports
from tools.history_evolution import save_history_evolution_reports
from tools.manual_review_persistence_enricher import save_enriched_manual_review_reports
from tools.manual_review_top import save_manual_review_top_reports
from tools.setup_persistence_score import save_setup_persistence_reports

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
        "timeout_seconds": 1800,
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
        "name": "posttest_thesis_audit",
        "cmd": [
            sys.executable,
            "tools/posttest_thesis_audit.py",
            "--posttests",
            "reports/posttests/**/*.csv",
            "--json-out",
            "reports/posttest_thesis_audit_latest.json",
            "--markdown-out",
            "reports/posttest_thesis_audit_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "simple_candidate_posttest",
        "cmd": [
            sys.executable,
            "tools/simple_candidate_posttest.py",
            "--csv-out",
            "reports/simple_candidate_posttest_latest.csv",
            "--json-out",
            "reports/simple_candidate_posttest_latest.json",
            "--markdown-out",
            "reports/simple_candidate_posttest_latest.md",
        ],
        "required": False,
        "timeout_seconds": 180,
    },
    {
        "name": "engine_feedback",
        "cmd": [
            sys.executable,
            "tools/engine_feedback.py",
            "--audit-json",
            "reports/posttest_thesis_audit_latest.json",
            "--json-out",
            "reports/engine_feedback_latest.json",
            "--markdown-out",
            "reports/engine_feedback_latest.md",
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
        "name": "scenario_engine_audit",
        "cmd": [
            sys.executable,
            "tools/scenario_engine_audit.py",
            "--input-csv",
            "reports/latest_scan_audited.csv",
            "--json-out",
            "reports/scenario_engine_audit_latest.json",
            "--markdown-out",
            "reports/scenario_engine_audit_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
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
        "name": "portfolio_concentration_audit",
        "cmd": [
            sys.executable,
            "tools/portfolio_concentration_audit.py",
            "--input-csv",
            "reports/manual_review_top.csv",
            "--json-out",
            "reports/portfolio_concentration_latest.json",
            "--markdown-out",
            "reports/portfolio_concentration_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "webull_readonly_market_data_audit",
        "cmd": [
            sys.executable,
            "tools/webull_readonly_market_data_audit.py",
            "--json-out",
            "reports/webull_readonly_market_data_latest.json",
            "--markdown-out",
            "reports/webull_readonly_market_data_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "cboe_market_statistics_audit",
        "cmd": [
            sys.executable,
            "tools/cboe_market_statistics_audit.py",
            "--json-out",
            "reports/cboe_market_statistics_latest.json",
            "--markdown-out",
            "reports/cboe_market_statistics_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "google_sheets_data_source_audit",
        "cmd": [
            sys.executable,
            "tools/google_sheets_data_source_audit.py",
            "--json-out",
            "reports/google_sheets_data_source_latest.json",
            "--markdown-out",
            "reports/google_sheets_data_source_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "macro_event_context",
        "cmd": [
            sys.executable,
            "tools/macro_event_context.py",
            "--calendar",
            "data/economic_calendar.csv",
            "--json-out",
            "reports/macro_event_context_latest.json",
            "--markdown-out",
            "reports/macro_event_context_latest.md",
        ],
        "required": False,
        "timeout_seconds": 60,
    },
    {
        "name": "nasdaq_risk_regime_audit",
        "cmd": [
            sys.executable,
            "tools/nasdaq_risk_regime_audit.py",
            "--json-out",
            "reports/nasdaq_risk_regime_latest.json",
            "--markdown-out",
            "reports/nasdaq_risk_regime_latest.md",
        ],
        "required": False,
        "timeout_seconds": 120,
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
        "name": "alpaca_readonly_connectivity_audit",
        "cmd": [
            sys.executable,
            "tools/alpaca_readonly_connectivity_audit.py",
            "--json-out",
            "reports/alpaca_readonly_connectivity_latest.json",
            "--markdown-out",
            "reports/alpaca_readonly_connectivity_latest.md",
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

FINAL_DERIVED_REFRESH_STEP_NAMES = [
    "trade_decision_checklist",
    "trade_candidate_cards",
    "ui_data_contract_audit",
    "daily_run_manifest",
    "encoding_audit",
    "daily_quality_gate",
    "release_readiness_audit",
    "daily_operator_index",
    "daily_run_manifest",
]


def _steps_with_scanner_timeout(steps: list[dict], scanner_timeout_seconds: int | None) -> list[dict]:
    if scanner_timeout_seconds is None:
        return [dict(step) for step in steps]
    out = []
    for step in steps:
        item = dict(step)
        if item.get("name") == "run_scanner_audited":
            item["timeout_seconds"] = int(scanner_timeout_seconds)
        out.append(item)
    return out


def run_step(step: dict) -> dict:
    timeout_seconds = int(step.get("timeout_seconds", 600))
    started = time.perf_counter()

    print(
        f"[daily_validation] running: {step['name']} "
        f"(timeout={timeout_seconds}s)",
        flush=True,
    )

    process = subprocess.Popen(
        step["cmd"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )

    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        returncode = process.returncode
        passed = returncode == 0
        duration_seconds = round(time.perf_counter() - started, 2)

        print(
            f"[daily_validation] finished: {step['name']} "
            f"status={'PASS' if passed else 'FAIL'} "
            f"returncode={returncode} "
            f"duration={duration_seconds}s",
            flush=True,
        )

        return {
            "name": step["name"],
            "cmd": " ".join(step["cmd"]),
            "required": bool(step.get("required", True)),
            "returncode": returncode,
            "stdout": (stdout or "").strip(),
            "stderr": (stderr or "").strip(),
            "passed": passed,
            "timeout_seconds": timeout_seconds,
            "duration_seconds": duration_seconds,
            "timed_out": False,
        }

    except subprocess.TimeoutExpired as exc:
        duration_seconds = round(time.perf_counter() - started, 2)
        if sys.platform.startswith("win"):
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
            )
        else:  # pragma: no cover - Windows is the primary desktop runtime here.
            process.kill()
        stdout, stderr = process.communicate()
        print(
            f"[daily_validation] timeout: {step['name']} "
            f"after {timeout_seconds}s "
            f"duration={duration_seconds}s",
            flush=True,
        )

        stdout = stdout or exc.stdout or ""
        stderr = stderr or exc.stderr or ""

        return {
            "name": step["name"],
            "cmd": " ".join(step["cmd"]),
            "required": bool(step.get("required", True)),
            "returncode": -1,
            "stdout": str(stdout).strip(),
            "stderr": str(stderr).strip(),
            "passed": False,
            "timeout_seconds": timeout_seconds,
            "duration_seconds": duration_seconds,
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
        ROOT / "reports" / "scan_performance_latest.json",
        ROOT / "reports" / "project_preflight_latest.md",
        ROOT / "reports" / "latest_scan_audited.csv",
        ROOT / "reports" / "latest_scan_audited.json",
        ROOT / "reports" / "manual_review_latest.csv",
        ROOT / "reports" / "manual_review_latest.md",
        ROOT / "reports" / "manual_review_top.csv",
        ROOT / "reports" / "manual_review_top.md",
        ROOT / "reports" / "daily_validation_summary.txt",
        ROOT / "reports" / "daily_validation_progress_latest.json",
        ROOT / "reports" / "daily_operator_index.md",
        ROOT / "reports" / "live_quote_recheck_latest.csv",
        ROOT / "reports" / "live_quote_recheck_latest.md",
        ROOT / "reports" / "live_quote_recheck_latest.json",
        ROOT / "reports" / "trade_decision_checklist_latest.csv",
        ROOT / "reports" / "trade_decision_checklist_latest.md",
        ROOT / "reports" / "trade_decision_checklist_latest.json",
        ROOT / "reports" / "trade_candidate_cards_latest.md",
        ROOT / "reports" / "trade_candidate_cards_latest.json",
        ROOT / "reports" / "webull_readonly_market_data_latest.json",
        ROOT / "reports" / "webull_readonly_market_data_latest.md",
        ROOT / "reports" / "cboe_market_statistics_latest.json",
        ROOT / "reports" / "cboe_market_statistics_latest.md",
        ROOT / "reports" / "google_sheets_data_source_latest.json",
        ROOT / "reports" / "google_sheets_data_source_latest.md",
        ROOT / "reports" / "macro_event_context_latest.json",
        ROOT / "reports" / "macro_event_context_latest.md",
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
        ROOT / "reports" / "alpaca_readonly_connectivity_latest.json",
        ROOT / "reports" / "alpaca_readonly_connectivity_latest.md",
        ROOT / "reports" / "reports_cleanup_latest.json",
        ROOT / "reports" / "reports_cleanup_latest.md",
        ROOT / "reports" / "source_coverage_latest.json",
        ROOT / "reports" / "scenario_engine_audit_latest.json",
        ROOT / "reports" / "scenario_engine_audit_latest.md",
        ROOT / "reports" / "history_evolution_latest.csv",
        ROOT / "reports" / "history_evolution_latest.md",
        ROOT / "reports" / "setup_persistence_latest.csv",
        ROOT / "reports" / "setup_persistence_latest.md",
        ROOT / "reports" / "trade_outcome_analytics_latest.csv",
        ROOT / "reports" / "trade_outcome_analytics_latest.json",
        ROOT / "reports" / "trade_outcome_analytics_latest.md",
        ROOT / "reports" / "trade_score_calibration_latest.csv",
        ROOT / "reports" / "trade_score_calibration_latest.json",
        ROOT / "reports" / "trade_score_calibration_latest.md",
        ROOT / "reports" / "calibration_recommendations_latest.md",
        ROOT / "reports" / "calibration_recommendations_latest.json",
        ROOT / "reports" / "posttest_thesis_audit_latest.json",
        ROOT / "reports" / "posttest_thesis_audit_latest.md",
        ROOT / "reports" / "simple_candidate_posttest_latest.csv",
        ROOT / "reports" / "simple_candidate_posttest_latest.json",
        ROOT / "reports" / "simple_candidate_posttest_latest.md",
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
    calibration_path = ROOT / "reports" / "trade_score_calibration_latest.json"
    calibration_recommendations_path = ROOT / "reports" / "calibration_recommendations_latest.json"
    simple_posttest_path = ROOT / "reports" / "simple_candidate_posttest_latest.json"
    release_readiness_path = ROOT / "reports" / "release_readiness_latest.json"
    ui_contract_path = ROOT / "reports" / "ui_data_contract_audit_latest.json"
    streamlit_smoke_path = ROOT / "reports" / "streamlit_smoke_test_latest.json"
    gui_actions_path = ROOT / "reports" / "gui_actions_audit_latest.json"
    gui_visuals_path = ROOT / "reports" / "gui_visuals_audit_latest.json"
    gui_release_path = ROOT / "reports" / "gui_release_audit_latest.json"

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
        "simple_candidate_posttest": {
            "status": "MISSING",
            "rows": 0,
            "report_sessions_available": 0,
            "horizons": [],
            "win_rate_5": "",
            "win_rate_10": "",
            "win_rate_15": "",
            "avg_return_5": "",
            "avg_return_10": "",
            "avg_return_15": "",
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

    if simple_posttest_path.exists():
        try:
            simple_posttest_data = json.loads(simple_posttest_path.read_text(encoding="utf-8"))
        except Exception:
            simple_posttest_data = {}
        horizons = simple_posttest_data.get("horizon_summary", {}) or {}
        snapshot["simple_candidate_posttest"] = {
            "status": str(simple_posttest_data.get("status", "UNKNOWN")),
            "rows": int(simple_posttest_data.get("rows", 0) or 0),
            "report_sessions_available": int(simple_posttest_data.get("report_sessions_available", 0) or 0),
            "horizons": simple_posttest_data.get("horizons", []),
            "win_rate_5": (horizons.get("5", {}) or {}).get("win_rate", ""),
            "win_rate_10": (horizons.get("10", {}) or {}).get("win_rate", ""),
            "win_rate_15": (horizons.get("15", {}) or {}).get("win_rate", ""),
            "avg_return_5": (horizons.get("5", {}) or {}).get("avg_return_pct", ""),
            "avg_return_10": (horizons.get("10", {}) or {}).get("avg_return_pct", ""),
            "avg_return_15": (horizons.get("15", {}) or {}).get("avg_return_pct", ""),
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


def _format_stdout_stderr_block(label: str, value: str, *, max_lines: int = 24, max_chars: int = 4000) -> list[str]:
    if not value:
        return []

    text = str(value).strip()
    omitted = False
    if len(text) > max_chars:
        text = text[:max_chars].rstrip()
        omitted = True

    raw_lines = text.splitlines()
    if len(raw_lines) > max_lines:
        raw_lines = raw_lines[:max_lines]
        omitted = True

    lines: list[str] = []
    lines.append(f"  {label}:")
    lines.append("  " + "\n  ".join(raw_lines))
    if omitted:
        lines.append(f"  ... salida truncada; revisar consola o reporte específico del paso para detalle completo.")
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


def _write_validation_progress(
    *,
    results: list[dict],
    current_step: str = "",
    phase: str = "running",
    started_at: datetime,
) -> None:
    PROGRESS_OUT.parent.mkdir(parents=True, exist_ok=True)
    failed = [r.get("name", "") for r in results if not r.get("passed", False)]
    timed_out = [r.get("name", "") for r in results if r.get("timed_out", False)]
    completed = [r.get("name", "") for r in results]
    payload = {
        "status": "RUNNING" if phase != "complete" else "COMPLETE",
        "phase": phase,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "started_at": started_at.isoformat(timespec="seconds"),
        "current_step": current_step,
        "last_completed_step": completed[-1] if completed else "",
        "completed_steps": completed,
        "failed_steps": failed,
        "timed_out_steps": timed_out,
        "duration_seconds_total": round(
            sum(float(r.get("duration_seconds", 0) or 0) for r in results),
            2,
        ),
    }
    PROGRESS_OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


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
    lines.append("- Revisar posttest automático simple: reports/simple_candidate_posttest_latest.md")
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
        "reports/scan_performance_latest.json",
        "reports/project_preflight_latest.md",
        "reports/latest_scan_audited.csv",
        "reports/latest_scan_audited.json",
        "reports/manual_review_latest.csv",
        "reports/manual_review_latest.md",
        "reports/manual_review_top.csv",
        "reports/manual_review_top.md",
        "reports/daily_validation_summary.txt",
        "reports/daily_validation_progress_latest.json",
        "reports/daily_operator_index.md",
        "reports/daily_quality_gate_latest.json",
        "reports/daily_quality_gate_latest.md",
    ]

    secondary_reports = [
        "reports/source_coverage_latest.json",
        "reports/scenario_engine_audit_latest.json",
        "reports/scenario_engine_audit_latest.md",
        "reports/history_evolution_latest.csv",
        "reports/history_evolution_latest.md",
        "reports/setup_persistence_latest.csv",
        "reports/setup_persistence_latest.md",
        "reports/trade_outcome_analytics_latest.csv",
        "reports/trade_outcome_analytics_latest.json",
        "reports/trade_outcome_analytics_latest.md",
        "reports/trade_score_calibration_latest.csv",
        "reports/trade_score_calibration_latest.json",
        "reports/trade_score_calibration_latest.md",
        "reports/calibration_recommendations_latest.md",
        "reports/calibration_recommendations_latest.json",
        "reports/posttest_thesis_audit_latest.json",
        "reports/posttest_thesis_audit_latest.md",
        "reports/simple_candidate_posttest_latest.csv",
        "reports/simple_candidate_posttest_latest.json",
        "reports/simple_candidate_posttest_latest.md",
        "reports/live_quote_recheck_latest.csv",
        "reports/live_quote_recheck_latest.md",
        "reports/live_quote_recheck_latest.json",
        "reports/trade_decision_checklist_latest.csv",
        "reports/trade_decision_checklist_latest.md",
        "reports/trade_decision_checklist_latest.json",
        "reports/trade_candidate_cards_latest.md",
        "reports/trade_candidate_cards_latest.json",
        "reports/macro_event_context_latest.json",
        "reports/macro_event_context_latest.md",
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
        "reports/alpaca_readonly_connectivity_latest.json",
        "reports/alpaca_readonly_connectivity_latest.md",
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
    calibration = snapshot.get("trade_score_calibration", {}) or {}
    calibration_recommendations = snapshot.get("calibration_recommendations", {}) or {}
    simple_posttest = snapshot.get("simple_candidate_posttest", {}) or {}
    release_readiness = snapshot.get("release_readiness", {}) or {}
    ui_contract = snapshot.get("ui_data_contract", {}) or {}
    streamlit_smoke = snapshot.get("streamlit_smoke_test", {}) or {}
    gui_actions = snapshot.get("gui_actions_audit", {}) or {}
    gui_visuals = snapshot.get("gui_visuals_audit", {}) or {}
    gui_release = snapshot.get("gui_release_audit", {}) or {}
    lines.append(f"- Live quote recheck rows: {live.get('rows')}")
    lines.append(f"- Trade decision checklist rows: {checklist.get('rows')}")
    lines.append(f"- Trade candidate cards rows: {cards.get('rows')}")
    lines.append(f"- Trade score calibration closed trades: {calibration.get('closed_trades')}")
    lines.append(
        "- Calibration recommendations count: "
        f"{calibration_recommendations.get('recommendation_count')}"
    )
    lines.append(
        "- Simple posttest: "
        f"status={simple_posttest.get('status')} rows={simple_posttest.get('rows')} "
        f"win_rate_5={simple_posttest.get('win_rate_5')} "
        f"win_rate_10={simple_posttest.get('win_rate_10')} "
        f"win_rate_15={simple_posttest.get('win_rate_15')}"
    )
    lines.append(f"- Release readiness status: {release_readiness.get('status')}")
    lines.append(f"- UI data contract status: {ui_contract.get('status')}")
    lines.append(f"- Streamlit smoke test status: {streamlit_smoke.get('status')}")
    lines.append(f"- GUI actions audit status: {gui_actions.get('status')}")
    lines.append(f"- GUI visuals audit status: {gui_visuals.get('status')}")
    lines.append(f"- GUI release audit status: {gui_release.get('status')}")
    lines.append("")

    lines.extend(_build_operational_next_steps(status, snapshot))
    lines.append("")

    lines.append("[Step durations]")
    lines.append("| step | required | passed | timeout_seconds | duration_seconds | timed_out |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for result in results:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(result.get("name", "")),
                    str(bool(result.get("required", True))),
                    str(bool(result.get("passed", False))),
                    str(result.get("timeout_seconds", "")),
                    str(result.get("duration_seconds", "")),
                    str(bool(result.get("timed_out", False))),
                ]
            )
            + " |"
        )
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
        if "duration_seconds" in result:
            lines.append(f"  duration_seconds: {result.get('duration_seconds')}")

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

    lines.append("")
    lines.append("[Manual operating reminder]")
    lines.append("- VETO y AVOID no son operables.")
    lines.append("- RECHECK_LIVE_QUOTE no es entrada; requiere validación live quote.")
    lines.append("- TRIGGER_CONFIRMED requiere revisión manual final.")
    lines.append("- WATCHLIST es monitoreo, no compra automática.")
    lines.append("- Confirmar siempre gráfico, quote, R/R, stop, target, earnings y contexto de mercado.")

    return "\n".join(lines)


def run_daily_validation(summary_out: Path, *, scanner_timeout_seconds: int | None = None) -> int:
    started_at = datetime.now()
    results: list[dict] = []
    default_steps = _steps_with_scanner_timeout(DEFAULT_STEPS, scanner_timeout_seconds)
    _write_validation_progress(
        results=results,
        current_step="startup",
        phase="default_steps",
        started_at=started_at,
    )
    for step in default_steps:
        _write_validation_progress(
            results=results,
            current_step=step["name"],
            phase="default_steps",
            started_at=started_at,
        )
        results.append(run_step(step))
        _write_validation_progress(
            results=results,
            current_step="",
            phase="default_steps",
            started_at=started_at,
        )

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
        _write_validation_progress(
            results=results + post_summary_results,
            current_step=step["name"],
            phase="post_summary_steps",
            started_at=started_at,
        )
        result = run_step(step)
        post_summary_results.append(result)
        _write_validation_progress(
            results=results + post_summary_results,
            current_step="",
            phase="post_summary_steps",
            started_at=started_at,
        )

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
        per_group_limit=0,
    )

    post_steps_by_name = {step["name"]: step for step in POST_SUMMARY_STEPS}
    final_refresh_results = []
    for step_name in FINAL_DERIVED_REFRESH_STEP_NAMES:
        step = post_steps_by_name.get(step_name)
        if step is None:
            continue
        _write_validation_progress(
            results=results + final_refresh_results,
            current_step=step["name"],
            phase="final_refresh_steps",
            started_at=started_at,
        )
        result = run_step(step)
        final_refresh_results.append(result)
        _write_validation_progress(
            results=results + final_refresh_results,
            current_step="",
            phase="final_refresh_steps",
            started_at=started_at,
        )
    results.extend(final_refresh_results)

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
            "trade_decision_checklist_latest.csv",
            "trade_decision_checklist_latest.md",
            "trade_decision_checklist_latest.json",
            "trade_candidate_cards_latest.md",
            "trade_candidate_cards_latest.json",
            "daily_quality_gate_latest.md",
            "daily_quality_gate_latest.json",
            "daily_operator_index.md",
            "daily_run_manifest_latest.md",
            "daily_run_manifest_latest.json",
        ]:
            src = ROOT / "reports" / filename
            dst = archive_dir / filename
            if src.exists():
                dst.write_bytes(src.read_bytes())

    print(summary_text)
    print(f"Resumen escrito en: {summary_out}")
    print(f"Historial escrito en: {ROOT / archive_manifest['archive_dir']}")
    _write_validation_progress(
        results=results,
        current_step="",
        phase="complete",
        started_at=started_at,
    )

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
