from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


KEY_SCRIPT_PATHS = [
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
]


KEY_REPORT_PATHS = [
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
    "reports/trade_score_calibration_latest.csv",
    "reports/trade_score_calibration_latest.json",
    "reports/trade_score_calibration_latest.md",
    "reports/calibration_recommendations_latest.md",
    "reports/calibration_recommendations_latest.json",
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
    "reports/reports_cleanup_latest.json",
    "reports/reports_cleanup_latest.md",
    "reports/open_trades_snapshot_latest.csv",
    "reports/open_trades_snapshot_latest.md",
    "reports/trade_outcome_analytics_latest.csv",
    "reports/trade_outcome_analytics_latest.md",
]


def _relative(path: Path, root: Path = ROOT) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _file_sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""

    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def _file_manifest(path: Path, root: Path = ROOT, include_hash: bool = True) -> dict:
    exists = path.exists()
    is_file = path.is_file() if exists else False

    return {
        "path": _relative(path, root),
        "exists": exists,
        "is_file": is_file,
        "size_bytes": path.stat().st_size if exists and is_file else 0,
        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        if exists
        else "",
        "sha256": _file_sha256(path) if exists and is_file and include_hash else "",
    }


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def _read_text(path: Path, max_chars: int = 20000) -> str:
    if not path.exists():
        return ""

    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except Exception:
        return ""


def _parse_status_from_summary(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Status:"):
            return line.split("Status:", 1)[1].strip().upper() or "UNKNOWN"

    return "UNKNOWN"


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _safe_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0

    try:
        return int(len(pd.read_csv(path)))
    except Exception:
        return 0


def _safe_value_counts(path: Path, column: str) -> dict:
    if not path.exists():
        return {}

    try:
        df = pd.read_csv(path)
    except Exception:
        return {}

    if df.empty or column not in df.columns:
        return {}

    return (
        df[column]
        .fillna("MISSING")
        .astype(str)
        .str.strip()
        .replace("", "MISSING")
        .value_counts()
        .to_dict()
    )


def _run_git_command(root: Path, args: list[str]) -> dict:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            text=True,
            capture_output=True,
            shell=False,
            timeout=5,
        )

        return {
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }

    except Exception as exc:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
        }


def collect_git_status(root: Path = ROOT) -> dict:
    git_dir = root / ".git"

    if not git_dir.exists():
        return {
            "available": False,
            "reason": "no_git_directory",
            "branch": "",
            "commit": "",
            "dirty": False,
            "status_short": "",
        }

    branch = _run_git_command(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    commit = _run_git_command(root, ["rev-parse", "HEAD"])
    status = _run_git_command(root, ["status", "--short"])

    available = branch["returncode"] == 0 and commit["returncode"] == 0

    return {
        "available": available,
        "reason": "" if available else "git_command_failed",
        "branch": branch["stdout"] if branch["returncode"] == 0 else "",
        "commit": commit["stdout"] if commit["returncode"] == 0 else "",
        "dirty": bool(status["stdout"]) if status["returncode"] == 0 else False,
        "status_short": status["stdout"] if status["returncode"] == 0 else "",
        "errors": {
            "branch": branch["stderr"],
            "commit": commit["stderr"],
            "status": status["stderr"],
        },
    }


def _normalize_preflight(data: dict) -> dict:
    summary = data.get("summary", {}) if isinstance(data, dict) else {}

    return {
        "available": bool(data),
        "status": str(data.get("status", "MISSING")).upper() if data else "MISSING",
        "missing_required_dirs": len(summary.get("missing_required_dirs", []) or []),
        "missing_required_files": len(summary.get("missing_required_files", []) or []),
        "missing_optional_files": len(summary.get("missing_optional_files", []) or []),
        "failed_write_checks": len(summary.get("failed_write_checks", []) or []),
    }


def _normalize_cleanup(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "mode": "UNKNOWN",
            "candidate_count": 0,
            "moved_count": 0,
        }

    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "mode": str(data.get("mode", "UNKNOWN")).upper(),
        "candidate_count": _safe_int(data.get("candidate_count"), 0),
        "moved_count": _safe_int(data.get("moved_count"), 0),
    }


def _manifest_status(
    daily_validation_status: str,
    preflight: dict,
    cleanup: dict,
    script_files: list[dict],
) -> str:
    missing_scripts = [item for item in script_files if not item.get("exists")]

    if daily_validation_status == "FAIL":
        return "FAIL"

    if preflight.get("status") == "FAIL":
        return "FAIL"

    if missing_scripts:
        return "WARN"

    if daily_validation_status == "WARN":
        return "WARN"

    if preflight.get("status") in {"WARN", "MISSING"}:
        return "WARN"

    if cleanup.get("status") in {"MISSING", "FAIL"}:
        return "WARN"

    return "PASS"


def collect_daily_run_manifest(
    root: Path = ROOT,
    key_script_paths: list[str] | None = None,
    key_report_paths: list[str] | None = None,
) -> dict:
    root = root.resolve()
    reports = root / "reports"

    key_script_paths = key_script_paths or KEY_SCRIPT_PATHS
    key_report_paths = key_report_paths or KEY_REPORT_PATHS

    daily_summary_path = reports / "daily_validation_summary.txt"
    preflight_path = reports / "project_preflight_latest.json"
    cleanup_path = reports / "reports_cleanup_latest.json"
    latest_scan_path = reports / "latest_scan_audited.csv"
    manual_review_path = reports / "manual_review_latest.csv"
    live_quote_recheck_path = reports / "live_quote_recheck_latest.json"
    trade_decision_checklist_path = reports / "trade_decision_checklist_latest.json"
    trade_candidate_cards_path = reports / "trade_candidate_cards_latest.json"
    paper_trading_journal_path = reports / "paper_trading_journal_latest.json"
    paper_trade_followup_path = reports / "paper_trade_followup_latest.json"
    paper_trade_close_path = reports / "paper_trade_close_latest.json"
    paper_trading_cycle_audit_path = reports / "paper_trading_cycle_audit_latest.json"
    trade_score_calibration_path = reports / "trade_score_calibration_latest.json"
    calibration_recommendations_path = reports / "calibration_recommendations_latest.json"
    release_readiness_path = reports / "release_readiness_latest.json"
    ui_data_contract_path = reports / "ui_data_contract_audit_latest.json"
    streamlit_smoke_path = reports / "streamlit_smoke_test_latest.json"
    gui_actions_path = reports / "gui_actions_audit_latest.json"
    gui_visuals_path = reports / "gui_visuals_audit_latest.json"
    gui_release_path = reports / "gui_release_audit_latest.json"
    gui_supervised_session_path = reports / "gui_supervised_session_latest.json"
    gui_supervised_session_audit_path = reports / "gui_supervised_session_audit_latest.json"

    daily_summary_text = _read_text(daily_summary_path)
    daily_validation_status = _parse_status_from_summary(daily_summary_text)

    preflight = _normalize_preflight(_load_json(preflight_path))
    cleanup = _normalize_cleanup(_load_json(cleanup_path))

    script_files = [
        _file_manifest(root / path, root=root, include_hash=True)
        for path in key_script_paths
    ]

    report_files = [
        _file_manifest(root / path, root=root, include_hash=False)
        for path in key_report_paths
    ]

    data = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "",
        "root": root.as_posix(),
        "cwd": Path.cwd().resolve().as_posix(),
        "python": {
            "executable": sys.executable,
            "version": sys.version,
            "version_info": {
                "major": sys.version_info.major,
                "minor": sys.version_info.minor,
                "micro": sys.version_info.micro,
            },
        },
        "environment": {
            "virtual_env": os.environ.get("VIRTUAL_ENV", ""),
        },
        "git": collect_git_status(root),
        "daily_validation": {
            "status": daily_validation_status,
            "summary_path": _relative(daily_summary_path, root),
        },
        "project_preflight": preflight,
        "reports_cleanup": cleanup,
        "scan_snapshot": {
            "latest_scan_rows": _safe_csv_rows(latest_scan_path),
            "manual_review_rows": _safe_csv_rows(manual_review_path),
            "signals": _safe_value_counts(latest_scan_path, "signal"),
            "recommendations": _safe_value_counts(
                manual_review_path if manual_review_path.exists() else latest_scan_path,
                "recommendation",
            ),
            "quote_recheck_priority": _safe_value_counts(manual_review_path, "quote_recheck_priority"),
            "options_bias": _safe_value_counts(latest_scan_path, "options_bias"),
            "options_confidence": _safe_value_counts(latest_scan_path, "options_confidence"),
            "options_source": _safe_value_counts(latest_scan_path, "options_source"),
            "options_available": _safe_value_counts(latest_scan_path, "options_available")
            or _safe_value_counts(latest_scan_path, "options_data_available"),
            "options_error": _safe_value_counts(latest_scan_path, "options_error"),
            "live_quote_recheck": _load_json(live_quote_recheck_path),
            "trade_decision_checklist": _load_json(trade_decision_checklist_path),
            "trade_candidate_cards": _load_json(trade_candidate_cards_path),
            "paper_trading_journal": _load_json(paper_trading_journal_path),
            "paper_trade_followup": _load_json(paper_trade_followup_path),
            "paper_trade_close": _load_json(paper_trade_close_path),
            "paper_trading_cycle_audit": _load_json(paper_trading_cycle_audit_path),
            "trade_score_calibration": _load_json(trade_score_calibration_path),
            "calibration_recommendations": _load_json(calibration_recommendations_path),
            "release_readiness": _load_json(release_readiness_path),
            "ui_data_contract": _load_json(ui_data_contract_path),
            "streamlit_smoke_test": _load_json(streamlit_smoke_path),
            "gui_actions_audit": _load_json(gui_actions_path),
            "gui_visuals_audit": _load_json(gui_visuals_path),
            "gui_release_audit": _load_json(gui_release_path),
            "gui_supervised_session": _load_json(gui_supervised_session_path),
            "gui_supervised_session_audit": _load_json(gui_supervised_session_audit_path),
        },
        "script_files": script_files,
        "report_files": report_files,
        "summary": {
            "missing_script_files": [
                item["path"] for item in script_files if not item.get("exists")
            ],
            "missing_report_files": [
                item["path"] for item in report_files if not item.get("exists")
            ],
        },
    }

    data["status"] = _manifest_status(
        daily_validation_status=daily_validation_status,
        preflight=preflight,
        cleanup=cleanup,
        script_files=script_files,
    )

    return data


def _markdown_table(items: list[dict], columns: list[str]) -> str:
    if not items:
        return "_Sin datos._"

    lines: list[str] = []
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")

    for item in items:
        values = []
        for col in columns:
            value = item.get(col, "")
            values.append(str(value).replace("\n", " ").replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")

    return "\n".join(lines)


def _format_counts(counts: dict) -> list[str]:
    if not counts:
        return ["- Sin datos."]

    return [f"- {key}: {value}" for key, value in counts.items()]


def build_daily_run_manifest_markdown(data: dict) -> str:
    scan = data.get("scan_snapshot", {})
    preflight = data.get("project_preflight", {})
    cleanup = data.get("reports_cleanup", {})
    git = data.get("git", {})

    lines: list[str] = []

    lines.append("# Analista - daily run manifest")
    lines.append("")
    lines.append(f"- generated_at: {data.get('generated_at')}")
    lines.append(f"- status: {data.get('status')}")
    lines.append(f"- root: `{data.get('root')}`")
    lines.append(f"- cwd: `{data.get('cwd')}`")
    lines.append(f"- python_executable: `{data.get('python', {}).get('executable', '')}`")
    lines.append(f"- virtual_env: `{data.get('environment', {}).get('virtual_env', '')}`")
    lines.append("")

    lines.append("## Decision gate")
    lines.append("")

    if data.get("status") == "FAIL":
        lines.append("- Estado FAIL: no usar esta corrida operativamente hasta corregir errores.")
    elif data.get("status") == "WARN":
        lines.append("- Estado WARN: corrida utilizable solo con revisión manual reforzada.")
    else:
        lines.append("- Estado PASS: manifiesto sin advertencias críticas.")

    lines.append("")

    lines.append("## Core statuses")
    lines.append("")
    lines.append(f"- daily_validation: {data.get('daily_validation', {}).get('status')}")
    lines.append(f"- project_preflight: {preflight.get('status')}")
    lines.append(f"- reports_cleanup: {cleanup.get('status')} / mode={cleanup.get('mode')}")
    lines.append(f"- cleanup_candidate_count: {cleanup.get('candidate_count')}")
    lines.append(f"- cleanup_moved_count: {cleanup.get('moved_count')}")
    lines.append("")

    lines.append("## Git")
    lines.append("")
    lines.append(f"- available: {git.get('available')}")
    lines.append(f"- branch: `{git.get('branch', '')}`")
    lines.append(f"- commit: `{git.get('commit', '')}`")
    lines.append(f"- dirty: {git.get('dirty')}")
    if git.get("status_short"):
        lines.append("")
        lines.append("```text")
        lines.append(str(git.get("status_short")))
        lines.append("```")
    lines.append("")

    lines.append("## Scan snapshot")
    lines.append("")
    lines.append(f"- latest_scan_rows: {scan.get('latest_scan_rows')}")
    lines.append(f"- manual_review_rows: {scan.get('manual_review_rows')}")
    lines.append("")
    lines.append("Signals:")
    lines.extend(_format_counts(scan.get("signals", {})))
    lines.append("")
    lines.append("Recommendations:")
    lines.extend(_format_counts(scan.get("recommendations", {})))
    lines.append("")
    lines.append("Quote recheck priority:")
    lines.extend(_format_counts(scan.get("quote_recheck_priority", {})))
    lines.append("")

    lines.append("Options / institutional flow:")
    lines.append("options_bias:")
    lines.extend(_format_counts(scan.get("options_bias", {})))
    lines.append("options_confidence:")
    lines.extend(_format_counts(scan.get("options_confidence", {})))
    lines.append("options_source:")
    lines.extend(_format_counts(scan.get("options_source", {})))
    lines.append("options_available:")
    lines.extend(_format_counts(scan.get("options_available", {})))
    lines.append("options_error:")
    lines.extend(_format_counts(scan.get("options_error", {})))
    lines.append("")

    live_recheck = scan.get("live_quote_recheck", {}) or {}
    lines.append("Live quote recheck:")
    lines.append(f"- status: {live_recheck.get('status', 'MISSING')}")
    lines.append(f"- rows: {live_recheck.get('rows', 0)}")
    lines.append(f"- execution_ok_review_manually: {live_recheck.get('execution_ok_review_manually', 0)}")
    lines.append(f"- keep_recheck: {live_recheck.get('keep_recheck', 0)}")
    lines.append(f"- avoid_execution_risk: {live_recheck.get('avoid_execution_risk', 0)}")
    lines.append(f"- data_unavailable: {live_recheck.get('data_unavailable', 0)}")
    lines.append("")

    calibration = scan.get("trade_score_calibration", {}) or {}
    lines.append("Trade score calibration:")
    lines.append(f"- status: {calibration.get('status', 'MISSING')}")
    lines.append(f"- closed_trades: {calibration.get('closed_trades', 0)}")
    lines.append(f"- win_rate: {calibration.get('win_rate', '')}")
    lines.append(f"- avg_r_multiple: {calibration.get('avg_r_multiple', '')}")
    lines.append(f"- sample_size_warning: {calibration.get('sample_size_warning', '')}")
    lines.append("")

    calibration_recommendations = scan.get("calibration_recommendations", {}) or {}
    lines.append("Calibration recommendations:")
    lines.append(f"- status: {calibration_recommendations.get('status', 'MISSING')}")
    lines.append(f"- closed_trades: {calibration_recommendations.get('closed_trades', 0)}")
    lines.append(
        f"- recommendation_count: {calibration_recommendations.get('recommendation_count', 0)}"
    )
    lines.append(
        f"- sample_size_warning: {calibration_recommendations.get('sample_size_warning', '')}"
    )
    lines.append("")

    release_readiness = scan.get("release_readiness", {}) or {}
    lines.append("Release readiness:")
    lines.append(f"- status: {release_readiness.get('status', 'MISSING')}")
    lines.append(f"- critical_failures: {release_readiness.get('critical_failures', 0)}")
    lines.append(f"- warnings: {release_readiness.get('warnings', 0)}")
    lines.append("")

    ui_contract = scan.get("ui_data_contract", {}) or {}
    lines.append("UI data contract:")
    lines.append(f"- status: {ui_contract.get('status', 'MISSING')}")
    lines.append(f"- available_sources: {ui_contract.get('available_sources', 0)}")
    lines.append(f"- missing_sources: {ui_contract.get('missing_sources', 0)}")
    lines.append(f"- invalid_sources: {ui_contract.get('invalid_sources', 0)}")
    lines.append(f"- candidate_rows: {ui_contract.get('candidate_rows', 0)}")
    lines.append(f"- paper_journal_rows: {ui_contract.get('paper_journal_rows', 0)}")
    lines.append("")

    streamlit_smoke = scan.get("streamlit_smoke_test", {}) or {}
    lines.append("Streamlit dashboard:")
    lines.append(f"- status: {streamlit_smoke.get('status', 'MISSING')}")
    lines.append(f"- app_exists: {streamlit_smoke.get('app_exists', False)}")
    lines.append(f"- import_ok: {streamlit_smoke.get('import_ok', False)}")
    lines.append(f"- view_models_ok: {streamlit_smoke.get('view_models_ok', False)}")
    lines.append(f"- read_only: {streamlit_smoke.get('read_only', False)}")
    lines.append("")

    gui_actions = scan.get("gui_actions_audit", {}) or {}
    lines.append("GUI actions:")
    lines.append(f"- status: {gui_actions.get('status', 'MISSING')}")
    lines.append(f"- actions_module_exists: {gui_actions.get('actions_module_exists', False)}")
    lines.append(f"- action_log_exists: {gui_actions.get('action_log_exists', False)}")
    lines.append(f"- logged_actions: {gui_actions.get('logged_actions', 0)}")
    lines.append(f"- broker_guardrail_ok: {gui_actions.get('broker_guardrail_ok', False)}")
    lines.append(f"- shell_guardrail_ok: {gui_actions.get('shell_guardrail_ok', False)}")
    lines.append("")

    gui_visuals = scan.get("gui_visuals_audit", {}) or {}
    lines.append("GUI visuals:")
    lines.append(f"- status: {gui_visuals.get('status', 'MISSING')}")
    lines.append(f"- charts_module_exists: {gui_visuals.get('charts_module_exists', False)}")
    lines.append(f"- app_uses_charts: {gui_visuals.get('app_uses_charts', False)}")
    lines.append(f"- empty_data_safe: {gui_visuals.get('empty_data_safe', False)}")
    lines.append(f"- broker_guardrail_ok: {gui_visuals.get('broker_guardrail_ok', False)}")
    lines.append(f"- shell_guardrail_ok: {gui_visuals.get('shell_guardrail_ok', False)}")
    lines.append("")

    gui_release = scan.get("gui_release_audit", {}) or {}
    lines.append("GUI release:")
    lines.append(f"- status: {gui_release.get('status', 'MISSING')}")
    lines.append(f"- app_exists: {gui_release.get('app_exists', False)}")
    lines.append(f"- guards_exists: {gui_release.get('guards_exists', False)}")
    lines.append(f"- formatters_exists: {gui_release.get('formatters_exists', False)}")
    lines.append(f"- read_write_guardrail_ok: {gui_release.get('read_write_guardrail_ok', False)}")
    lines.append(f"- broker_guardrail_ok: {gui_release.get('broker_guardrail_ok', False)}")
    lines.append(f"- shell_guardrail_ok: {gui_release.get('shell_guardrail_ok', False)}")
    lines.append(f"- confirmation_guardrail_ok: {gui_release.get('confirmation_guardrail_ok', False)}")
    lines.append("")

    gui_session = scan.get("gui_supervised_session", {}) or {}
    lines.append("GUI supervised session:")
    lines.append(f"- status: {gui_session.get('status', 'MISSING')}")
    lines.append(f"- latest_session_id: {gui_session.get('latest_session_id', '')}")
    lines.append(f"- latest_session_status: {gui_session.get('latest_session_status', 'MISSING')}")
    lines.append(f"- latest_session_result: {gui_session.get('latest_session_result', '')}")
    lines.append(f"- paper_actions_logged: {gui_session.get('paper_actions_logged', 0)}")
    lines.append(f"- paper_enter_count: {gui_session.get('paper_enter_count', 0)}")
    lines.append(f"- closed_paper_count: {gui_session.get('closed_paper_count', 0)}")
    lines.append(f"- pending_export_count: {gui_session.get('pending_export_count', 0)}")
    lines.append("")

    gui_session_audit = scan.get("gui_supervised_session_audit", {}) or {}
    lines.append("GUI supervised session audit:")
    lines.append(f"- status: {gui_session_audit.get('status', 'MISSING')}")
    lines.append(f"- tool_exists: {gui_session_audit.get('tool_exists', False)}")
    lines.append(f"- data_file_can_be_created: {gui_session_audit.get('data_file_can_be_created', False)}")
    lines.append(f"- broker_guardrail_ok: {gui_session_audit.get('broker_guardrail_ok', False)}")
    lines.append(f"- shell_guardrail_ok: {gui_session_audit.get('shell_guardrail_ok', False)}")
    lines.append("")

    checklist = scan.get("trade_decision_checklist", {}) or {}
    lines.append("Trade decision checklist:")
    lines.append(f"- status: {checklist.get('status', 'MISSING')}")
    lines.append(f"- rows: {checklist.get('rows', 0)}")
    lines.append(f"- blocked: {checklist.get('blocked', 0)}")
    lines.append(f"- needs_live_quote_recheck: {checklist.get('needs_live_quote_recheck', 0)}")
    lines.append(f"- review_manually: {checklist.get('review_manually', 0)}")
    lines.append(f"- high_quality_review: {checklist.get('high_quality_review', 0)}")
    lines.append("")

    cards = scan.get("trade_candidate_cards", {}) or {}
    lines.append("Trade candidate cards:")
    lines.append(f"- status: {cards.get('status', 'MISSING')}")
    lines.append(f"- rows: {cards.get('rows', 0)}")
    lines.append(f"- high_quality_review: {cards.get('high_quality_review', 0)}")
    lines.append(f"- review_manually: {cards.get('review_manually', 0)}")
    lines.append(f"- needs_live_quote_recheck: {cards.get('needs_live_quote_recheck', 0)}")
    lines.append(f"- blocked: {cards.get('blocked', 0)}")
    lines.append("")

    paper_journal = scan.get("paper_trading_journal", {}) or {}
    lines.append("Paper trading journal:")
    lines.append(f"- status: {paper_journal.get('status', 'MISSING')}")
    lines.append(f"- rows: {paper_journal.get('rows', 0)}")
    lines.append(f"- pending_review: {paper_journal.get('pending_review', 0)}")
    lines.append(f"- paper_watch: {paper_journal.get('paper_watch', 0)}")
    lines.append(f"- paper_enter: {paper_journal.get('paper_enter', 0)}")
    lines.append(f"- blocked: {paper_journal.get('blocked', 0)}")
    lines.append(
        f"- needs_live_quote_recheck: {paper_journal.get('needs_live_quote_recheck', 0)}"
    )
    lines.append("- notice: paper trading only; no real order")
    lines.append("")

    paper_followup = scan.get("paper_trade_followup", {}) or {}
    lines.append("Paper trade follow-up:")
    lines.append(f"- status: {paper_followup.get('status', 'MISSING')}")
    lines.append(f"- rows: {paper_followup.get('rows', 0)}")
    lines.append(f"- hold_paper: {paper_followup.get('hold_paper', 0)}")
    lines.append(f"- review_near_stop: {paper_followup.get('review_near_stop', 0)}")
    lines.append(f"- review_near_target: {paper_followup.get('review_near_target', 0)}")
    lines.append(f"- stop_hit_review_close: {paper_followup.get('stop_hit_review_close', 0)}")
    lines.append(f"- target_hit_review_close: {paper_followup.get('target_hit_review_close', 0)}")
    lines.append(f"- data_unavailable: {paper_followup.get('data_unavailable', 0)}")
    lines.append("- notice: paper trading only; no real order")
    lines.append("")

    paper_close = scan.get("paper_trade_close", {}) or {}
    lines.append("Paper trade close:")
    lines.append(f"- status: {paper_close.get('status', 'MISSING')}")
    lines.append(f"- rows: {paper_close.get('rows', 0)}")
    lines.append(f"- open_paper_trades: {paper_close.get('open_paper_trades', 0)}")
    lines.append(f"- closed_paper_trades: {paper_close.get('closed_paper_trades', 0)}")
    lines.append(f"- pending_export: {paper_close.get('pending_export', 0)}")
    lines.append(f"- exported_outcomes: {paper_close.get('exported_outcomes', 0)}")
    lines.append("- notice: paper trading only; no real order")
    lines.append("")

    paper_cycle = scan.get("paper_trading_cycle_audit", {}) or {}
    lines.append("Paper trading cycle audit:")
    lines.append(f"- status: {paper_cycle.get('status', 'MISSING')}")
    lines.append(f"- journal_rows: {paper_cycle.get('journal_rows', 0)}")
    lines.append(f"- open_paper_count: {paper_cycle.get('open_paper_count', 0)}")
    lines.append(f"- closed_paper_count: {paper_cycle.get('closed_paper_count', 0)}")
    lines.append(f"- pending_export_count: {paper_cycle.get('pending_export_count', 0)}")
    lines.append(f"- exported_count: {paper_cycle.get('exported_count', 0)}")
    lines.append(
        f"- duplicate_outcome_ids: {len(paper_cycle.get('duplicate_outcome_ids', []) or [])}"
    )
    lines.append("- notice: paper trading only; no real order")
    lines.append("")

    lines.append("## Script files")
    lines.append("")
    lines.append(
        _markdown_table(
            data.get("script_files", []),
            ["path", "exists", "size_bytes", "modified", "sha256"],
        )
    )
    lines.append("")

    lines.append("## Report files")
    lines.append("")
    lines.append(
        _markdown_table(
            data.get("report_files", []),
            ["path", "exists", "size_bytes", "modified"],
        )
    )
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- missing_script_files: {len(data.get('summary', {}).get('missing_script_files', []))}")
    lines.append(f"- missing_report_files: {len(data.get('summary', {}).get('missing_report_files', []))}")

    return "\n".join(lines)


def save_daily_run_manifest(
    root: Path = ROOT,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict:
    json_out = json_out or root / "reports" / "daily_run_manifest_latest.json"
    markdown_out = markdown_out or root / "reports" / "daily_run_manifest_latest.md"

    data = collect_daily_run_manifest(root=root)

    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    json_out.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    markdown_out.write_text(
        build_daily_run_manifest_markdown(data),
        encoding="utf-8",
    )

    return {
        "status": data["status"],
        "json_out": _relative(json_out, root),
        "markdown_out": _relative(markdown_out, root),
        "daily_validation_status": data["daily_validation"]["status"],
        "project_preflight_status": data["project_preflight"]["status"],
        "cleanup_status": data["reports_cleanup"]["status"],
        "latest_scan_rows": data["scan_snapshot"]["latest_scan_rows"],
        "manual_review_rows": data["scan_snapshot"]["manual_review_rows"],
        "missing_script_files": len(data["summary"]["missing_script_files"]),
        "missing_report_files": len(data["summary"]["missing_report_files"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera manifiesto diario de ejecución de Analista.")
    parser.add_argument("--json-out", default="reports/daily_run_manifest_latest.json")
    parser.add_argument("--markdown-out", default="reports/daily_run_manifest_latest.md")
    args = parser.parse_args()

    result = save_daily_run_manifest(
        root=ROOT,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
    )

    print("=== ANALISTA DAILY RUN MANIFEST ===")
    print(f"Status: {result['status']}")
    print(f"Daily validation: {result['daily_validation_status']}")
    print(f"Project preflight: {result['project_preflight_status']}")
    print(f"Reports cleanup: {result['cleanup_status']}")
    print(f"Latest scan rows: {result['latest_scan_rows']}")
    print(f"Manual review rows: {result['manual_review_rows']}")
    print(f"Missing script files: {result['missing_script_files']}")
    print(f"Missing report files: {result['missing_report_files']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")

    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
