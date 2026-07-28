from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _safe_text(value) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    if text.lower() in {"", "nan", "none", "null"}:
        return ""

    return text


def _read_text(path: Path, max_chars: int = 12000) -> str:
    if not path.exists():
        return ""

    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except Exception:
        return ""


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _normalize_cleanup_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "mode": "UNKNOWN",
            "candidate_count": 0,
            "moved_count": 0,
            "archive_dir": "",
        }

    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")),
        "mode": str(data.get("mode", "UNKNOWN")),
        "candidate_count": _safe_int(data.get("candidate_count"), 0),
        "moved_count": _safe_int(data.get("moved_count"), 0),
        "archive_dir": str(data.get("archive_dir", "")),
    }


def _count_items(value) -> int:
    if isinstance(value, list):
        return len(value)

    return _safe_int(value, 0)


def _normalize_preflight_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "files_scanned": 0,
            "warn_files": 0,
            "error_files": 0,
            "total_marker_hits": 0,
            "cwd_matches_root": False,
            "missing_required_dirs": 0,
            "missing_required_files": 0,
            "missing_optional_files": 0,
            "failed_write_checks": 0,
            "root": "",
            "cwd": "",
            "python_executable": "",
            "virtual_env": "",
        }

    summary = data.get("summary", {}) or {}
    python_data = data.get("python", {}) or {}
    environment = data.get("environment", {}) or {}

    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "files_scanned": _safe_int(summary.get("files_scanned"), 0),
        "warn_files": _safe_int(summary.get("warn_files"), 0),
        "error_files": _safe_int(summary.get("error_files"), 0),
        "total_marker_hits": _safe_int(summary.get("total_marker_hits"), 0),
        "cwd_matches_root": bool(data.get("cwd_matches_root", False)),
        "missing_required_dirs": _count_items(summary.get("missing_required_dirs", [])),
        "missing_required_files": _count_items(summary.get("missing_required_files", [])),
        "missing_optional_files": _count_items(summary.get("missing_optional_files", [])),
        "failed_write_checks": _count_items(summary.get("failed_write_checks", [])),
        "root": str(data.get("root", "")),
        "cwd": str(data.get("cwd", "")),
        "python_executable": str(python_data.get("executable", "")),
        "virtual_env": str(environment.get("virtual_env", "")),
    }


def _normalize_encoding_audit_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "files_scanned": 0,
            "warn_files": 0,
            "error_files": 0,
            "total_marker_hits": 0,
        }

    summary = data.get("summary", {}) or {}

    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "files_scanned": _safe_int(summary.get("files_scanned"), 0),
        "warn_files": _safe_int(summary.get("warn_files"), 0),
        "error_files": _safe_int(summary.get("error_files"), 0),
        "total_marker_hits": _safe_int(summary.get("total_marker_hits"), 0),
    }


def _normalize_quality_gate_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "manual_review_allowed": False,
            "manual_review_mode": "UNKNOWN",
            "issue_count": 0,
            "fail_issues": 0,
            "warn_issues": 0,
            "scan_freshness_status": "MISSING",
            "scan_age_hours": None,
            "manual_review_age_hours": None,
            "macro_age_hours": None,
            "scan_is_current_local_date": False,
        }

    issues = data.get("issues", []) or []
    fail_issues = 0
    warn_issues = 0

    for issue in issues:
        severity = str(issue.get("severity", "")).upper()
        if severity == "FAIL":
            fail_issues += 1
        elif severity == "WARN":
            warn_issues += 1

    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "manual_review_allowed": bool(data.get("manual_review_allowed", False)),
        "manual_review_mode": str(data.get("manual_review_mode", "UNKNOWN")).upper(),
        "issue_count": len(issues),
        "fail_issues": fail_issues,
        "warn_issues": warn_issues,
        "scan_freshness_status": str(data.get("scan_freshness_status", "UNKNOWN")).upper(),
        "scan_age_hours": data.get("scan_age_hours"),
        "manual_review_age_hours": data.get("manual_review_age_hours"),
        "macro_age_hours": data.get("macro_age_hours"),
        "scan_is_current_local_date": bool(data.get("scan_is_current_local_date", False)),
    }


def _normalize_live_quote_recheck_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "rows": 0,
            "execution_ok_review_manually": 0,
            "keep_recheck": 0,
            "watchlist_monitor": 0,
            "avoid_execution_risk": 0,
            "data_unavailable": 0,
        }

    decisions = data.get("decisions", {}) or {}

    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "rows": _safe_int(data.get("rows"), 0),
        "execution_ok_review_manually": _safe_int(
            data.get("execution_ok_review_manually", decisions.get("EXECUTION_OK_REVIEW_MANUALLY")),
            0,
        ),
        "keep_recheck": _safe_int(data.get("keep_recheck", decisions.get("KEEP_RECHECK")), 0),
        "watchlist_monitor": _safe_int(
            data.get("watchlist_monitor", decisions.get("WATCHLIST_MONITOR")),
            0,
        ),
        "avoid_execution_risk": _safe_int(
            data.get("avoid_execution_risk", decisions.get("AVOID_EXECUTION_RISK")),
            0,
        ),
        "data_unavailable": _safe_int(
            data.get("data_unavailable", decisions.get("DATA_UNAVAILABLE")),
            0,
        ),
    }


def _normalize_trade_decision_checklist_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "rows": 0,
            "blocked": 0,
            "needs_live_quote_recheck": 0,
            "review_manually": 0,
            "high_quality_review": 0,
        }

    statuses = data.get("statuses", {}) or {}

    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "rows": _safe_int(data.get("rows"), 0),
        "blocked": _safe_int(data.get("blocked", statuses.get("BLOCKED")), 0),
        "needs_live_quote_recheck": _safe_int(
            data.get("needs_live_quote_recheck", statuses.get("NEEDS_LIVE_QUOTE_RECHECK")),
            0,
        ),
        "review_manually": _safe_int(
            data.get("review_manually", statuses.get("REVIEW_MANUALLY")),
            0,
        ),
        "high_quality_review": _safe_int(
            data.get("high_quality_review", statuses.get("HIGH_QUALITY_REVIEW")),
            0,
        ),
    }


def _normalize_trade_candidate_cards_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "rows": 0,
            "blocked": 0,
            "needs_live_quote_recheck": 0,
            "review_manually": 0,
            "high_quality_review": 0,
        }

    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "rows": _safe_int(data.get("rows"), 0),
        "blocked": _safe_int(data.get("blocked"), 0),
        "needs_live_quote_recheck": _safe_int(data.get("needs_live_quote_recheck"), 0),
        "review_manually": _safe_int(data.get("review_manually"), 0),
        "high_quality_review": _safe_int(data.get("high_quality_review"), 0),
    }


def _normalize_trade_score_calibration_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "closed_trades": 0,
            "win_rate": "",
            "avg_r_multiple": "",
            "sample_size_warning": "",
        }

    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "closed_trades": _safe_int(data.get("closed_trades"), 0),
        "win_rate": data.get("win_rate", ""),
        "avg_r_multiple": data.get("avg_r_multiple", ""),
        "sample_size_warning": str(data.get("sample_size_warning", "")),
    }


def _normalize_calibration_recommendations_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "closed_trades": 0,
            "recommendation_count": 0,
            "sample_size_warning": "",
        }

    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "closed_trades": _safe_int(data.get("closed_trades"), 0),
        "recommendation_count": _safe_int(data.get("recommendation_count"), 0),
        "sample_size_warning": str(data.get("sample_size_warning", "")),
    }


def _normalize_macro_event_context_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "next_critical_event": "",
            "next_critical_event_date": "",
            "days_to_critical_event": None,
            "event_risk_status": "UNKNOWN",
            "liquidity_context": "UNKNOWN",
            "m2_change_4w_pct": None,
            "reverse_repo_change_4w_pct": None,
            "effective_fed_funds_rate": None,
            "us10y_official": None,
            "us30y_official": None,
            "yield_curve_10y2y": None,
            "yield_curve_10y3m": None,
            "high_yield_spread": None,
            "macro_regime_mode": "UNKNOWN",
            "macro_regime_confidence": "UNKNOWN",
            "macro_event_risk": "UNKNOWN",
            "macro_liquidity_bias": "UNKNOWN",
            "macro_regime_notes": "",
            "fred_provider_counts": {},
            "issues_count": 0,
        }

    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "next_critical_event": str(data.get("next_critical_event", "")),
        "next_critical_event_date": str(data.get("next_critical_event_date", "")),
        "days_to_critical_event": data.get("days_to_critical_event"),
        "event_risk_status": str(data.get("event_risk_status", "UNKNOWN")).upper(),
        "liquidity_context": str(data.get("liquidity_context", "UNKNOWN")).upper(),
        "m2_change_4w_pct": data.get("m2_change_4w_pct"),
        "reverse_repo_change_4w_pct": data.get("reverse_repo_change_4w_pct"),
        "effective_fed_funds_rate": data.get("effective_fed_funds_rate"),
        "us10y_official": data.get("us10y_official"),
        "us30y_official": data.get("us30y_official"),
        "yield_curve_10y2y": data.get("yield_curve_10y2y"),
        "yield_curve_10y3m": data.get("yield_curve_10y3m"),
        "high_yield_spread": data.get("high_yield_spread"),
        "macro_regime_mode": str(data.get("macro_regime_mode", "UNKNOWN")).upper(),
        "macro_regime_confidence": str(data.get("macro_regime_confidence", "UNKNOWN")).upper(),
        "macro_event_risk": str(data.get("macro_event_risk", "UNKNOWN")).upper(),
        "macro_liquidity_bias": str(data.get("macro_liquidity_bias", "UNKNOWN")).upper(),
        "macro_regime_notes": str(data.get("macro_regime_notes", "")),
        "fred_provider_counts": data.get("fred_provider_counts", {}) or {},
        "issues_count": len(data.get("issues", []) or []),
    }


def _normalize_nasdaq_risk_regime_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "macro_regime_mode": "UNKNOWN",
            "macro_regime_confidence": "UNKNOWN",
            "macro_risk_flag": "UNKNOWN",
            "nasdaq_risk_score": None,
            "nasdaq_risk_semaforo": "UNKNOWN",
            "dominant_regime": "UNKNOWN",
            "p_normal": None,
            "p_omega": None,
            "p_sigma": None,
            "p_phi": None,
            "warnings_count": 0,
            "creates_trigger_confirmed": False,
            "broker_execution": False,
        }

    regime = data.get("regime_scores", {}) or {}
    guardrails = data.get("guardrails", {}) or {}
    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "macro_regime_mode": str(data.get("macro_regime_mode", "UNKNOWN")).upper(),
        "macro_regime_confidence": str(data.get("macro_regime_confidence", "UNKNOWN")).upper(),
        "macro_risk_flag": str(data.get("macro_risk_flag", "UNKNOWN")).upper(),
        "nasdaq_risk_score": data.get("nasdaq_risk_score"),
        "nasdaq_risk_semaforo": str(data.get("nasdaq_risk_semaforo", "UNKNOWN")).upper(),
        "dominant_regime": str(data.get("dominant_regime", "UNKNOWN")).upper(),
        "p_normal": regime.get("p_normal"),
        "p_omega": regime.get("p_omega"),
        "p_sigma": regime.get("p_sigma"),
        "p_phi": regime.get("p_phi"),
        "warnings_count": len(data.get("warnings", []) or []),
        "creates_trigger_confirmed": bool(
            data.get("creates_trigger_confirmed", guardrails.get("creates_trigger_confirmed", False))
        ),
        "broker_execution": bool(data.get("broker_execution", guardrails.get("broker_execution", False))),
    }


def _normalize_scenario_engine_audit_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "deep_analysis_rows": 0,
            "within_target_band": False,
            "valid_trigger": 0,
            "wait_for_confirmation": 0,
            "late_entry_overextended": 0,
            "weak_momentum": 0,
            "structure_invalid": 0,
            "context_conflict": 0,
            "data_insufficient": 0,
            "blocked_or_not_operable": 0,
        }
    statuses = data.get("scenario_status", {}) or {}
    blocked_or_not_operable = sum(
        _safe_int(statuses.get(key), 0)
        for key in {
            "WAIT_FOR_CONFIRMATION",
            "LATE_ENTRY_OVEREXTENDED",
            "WEAK_MOMENTUM",
            "STRUCTURE_INVALID",
            "CONTEXT_CONFLICT",
            "DATA_INSUFFICIENT",
        }
    )
    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "deep_analysis_rows": _safe_int(data.get("deep_analysis_rows"), 0),
        "within_target_band": bool(data.get("within_target_band", False)),
        "valid_trigger": _safe_int(statuses.get("VALID_TRIGGER"), 0),
        "wait_for_confirmation": _safe_int(statuses.get("WAIT_FOR_CONFIRMATION"), 0),
        "late_entry_overextended": _safe_int(statuses.get("LATE_ENTRY_OVEREXTENDED"), 0),
        "weak_momentum": _safe_int(statuses.get("WEAK_MOMENTUM"), 0),
        "structure_invalid": _safe_int(statuses.get("STRUCTURE_INVALID"), 0),
        "context_conflict": _safe_int(statuses.get("CONTEXT_CONFLICT"), 0),
        "data_insufficient": _safe_int(statuses.get("DATA_INSUFFICIENT"), 0),
        "blocked_or_not_operable": blocked_or_not_operable,
    }


def _normalize_posttest_thesis_audit_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "executed_entries": 0,
            "no_entry_triggers": 0,
            "win_rate": None,
            "target_hit_rate": None,
            "stop_hit_rate": None,
            "sample_size_warning": "",
        }
    summary = data.get("summary", {}) or {}
    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "executed_entries": _safe_int(summary.get("executed_entries"), 0),
        "no_entry_triggers": _safe_int(summary.get("no_entry_triggers"), 0),
        "win_rate": summary.get("win_rate"),
        "target_hit_rate": summary.get("target_hit_rate"),
        "stop_hit_rate": summary.get("stop_hit_rate"),
        "sample_size_warning": str(data.get("sample_size_warning", "")),
    }


def _normalize_engine_feedback_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "canonical_rows": 0,
            "canonical_dates": 0,
            "recommendation_count": 0,
            "sample_size_warning": "",
        }
    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "canonical_rows": _safe_int(data.get("canonical_rows"), 0),
        "canonical_dates": _safe_int(data.get("canonical_dates"), 0),
        "recommendation_count": _safe_int(data.get("recommendation_count"), 0),
        "sample_size_warning": str(data.get("sample_size_warning", "")),
    }


def _normalize_simple_candidate_posttest_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "rows": 0,
            "report_sessions_available": 0,
            "win_rate_5": "",
            "win_rate_10": "",
            "win_rate_15": "",
            "avg_return_5": "",
            "avg_return_10": "",
            "avg_return_15": "",
            "warnings": 0,
        }
    horizons = data.get("horizon_summary", {}) or {}
    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "rows": _safe_int(data.get("rows"), 0),
        "report_sessions_available": _safe_int(data.get("report_sessions_available"), 0),
        "win_rate_5": (horizons.get("5", {}) or {}).get("win_rate", ""),
        "win_rate_10": (horizons.get("10", {}) or {}).get("win_rate", ""),
        "win_rate_15": (horizons.get("15", {}) or {}).get("win_rate", ""),
        "avg_return_5": (horizons.get("5", {}) or {}).get("avg_return_pct", ""),
        "avg_return_10": (horizons.get("10", {}) or {}).get("avg_return_pct", ""),
        "avg_return_15": (horizons.get("15", {}) or {}).get("avg_return_pct", ""),
        "warnings": len(data.get("warnings", []) or []),
    }


def _normalize_portfolio_concentration_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "rows": 0,
            "warnings": 0,
            "concentration_flags": 0,
        }
    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "rows": _safe_int(data.get("rows"), 0),
        "warnings": len(data.get("warnings", []) or []),
        "concentration_flags": len(data.get("concentration_flags", []) or []),
    }


def _normalize_release_readiness_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "critical_failures": 0,
            "warnings": 0,
        }

    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "critical_failures": _safe_int(data.get("critical_failures"), 0),
        "warnings": _safe_int(data.get("warnings"), 0),
    }


def _normalize_ui_data_contract_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "available_sources": 0,
            "missing_sources": 0,
            "invalid_sources": 0,
            "candidate_rows": 0,
        }

    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "available_sources": _safe_int(data.get("available_sources"), 0),
        "missing_sources": _safe_int(data.get("missing_sources"), 0),
        "invalid_sources": _safe_int(data.get("invalid_sources"), 0),
        "candidate_rows": _safe_int(data.get("candidate_rows"), 0),
    }


def _normalize_streamlit_smoke_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "app_exists": False,
            "import_ok": False,
            "view_models_ok": False,
            "read_only": False,
        }

    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "app_exists": bool(data.get("app_exists", False)),
        "import_ok": bool(data.get("import_ok", False)),
        "view_models_ok": bool(data.get("view_models_ok", False)),
        "read_only": bool(data.get("read_only", False)),
    }


def _normalize_gui_actions_audit_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "actions_module_exists": False,
            "action_log_exists": False,
            "logged_actions": 0,
            "broker_guardrail_ok": False,
            "shell_guardrail_ok": False,
        }

    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "actions_module_exists": bool(data.get("actions_module_exists", False)),
        "action_log_exists": bool(data.get("action_log_exists", False)),
        "logged_actions": _safe_int(data.get("logged_actions"), 0),
        "broker_guardrail_ok": bool(data.get("broker_guardrail_ok", False)),
        "shell_guardrail_ok": bool(data.get("shell_guardrail_ok", False)),
    }


def _parse_status_from_summary(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Status:"):
            status = line.split("Status:", 1)[1].strip().upper()
            return status or "UNKNOWN"

    return "UNKNOWN"


def _value_counts(df: pd.DataFrame, column: str) -> dict:
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


def _file_status(path: Path, root: Path = ROOT) -> dict:
    exists = path.exists()

    try:
        display_path = path.relative_to(root).as_posix()
    except ValueError:
        display_path = path.as_posix()

    return {
        "path": display_path,
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else 0,
        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        if exists
        else "",
    }


def _existing_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    return [col for col in columns if col in df.columns]


def _df_to_markdown_table(df: pd.DataFrame, max_rows: int = 15) -> str:
    if df.empty:
        return "_Sin datos._"

    out = df.head(max_rows).copy()

    columns = list(out.columns)
    lines: list[str] = []

    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")

    for _, row in out.iterrows():
        values = []
        for col in columns:
            value = row.get(col, "")
            if pd.isna(value):
                value = ""
            values.append(str(value).replace("\n", " ").replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")

    return "\n".join(lines)


def _select_top_candidate_columns(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "rank",
        "ticker",
        "signal",
        "recommendation",
        "setup_type",
        "final_trade_score",
        "setup_persistence_score",
        "sector",
        "sector_weekly_macd_state",
        "sector_context_status",
        "quote_status",
        "execution_quote_quality",
        "rr",
        "stop_atr_status",
    ]

    existing = _existing_columns(df, columns)

    if not existing:
        return pd.DataFrame()

    return df[existing].copy()


def _select_recheck_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "recommendation" not in df.columns:
        return pd.DataFrame()

    mask = df["recommendation"].fillna("").astype(str).str.upper() == "RECHECK_LIVE_QUOTE"
    recheck = df[mask].copy()

    columns = [
        "rank",
        "ticker",
        "signal",
        "recommendation",
        "setup_type",
        "final_trade_score",
        "quote_status",
        "execution_quote_quality",
        "rr",
    ]

    existing = _existing_columns(recheck, columns)

    if not existing:
        return pd.DataFrame()

    return recheck[existing].copy()


def _select_open_trade_columns(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "trade_id",
        "ticker",
        "entry",
        "current_price",
        "unrealized_pnl_pct",
        "unrealized_r_multiple",
        "distance_to_stop_pct",
        "distance_to_target_pct",
        "snapshot_note",
    ]

    existing = _existing_columns(df, columns)

    if not existing:
        return pd.DataFrame()

    return df[existing].copy()


def _select_analytics_overall(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "group" not in df.columns or "group_value" not in df.columns:
        return pd.DataFrame()

    mask = (
        (df["group"].fillna("").astype(str) == "OVERALL")
        & (df["group_value"].fillna("").astype(str) == "ALL_CLOSED")
    )

    overall = df[mask].copy()

    columns = [
        "total_trades",
        "wins",
        "losses",
        "breakeven",
        "win_rate",
        "avg_pnl_pct",
        "avg_r_multiple",
        "total_r_multiple",
        "best_trade_r",
        "worst_trade_r",
    ]

    existing = _existing_columns(overall, columns)

    if not existing:
        return pd.DataFrame()

    return overall[existing].copy()


def collect_operator_index_data(root: Path = ROOT) -> dict:
    reports = root / "reports"

    summary_path = reports / "daily_validation_summary.txt"
    scan_path = reports / "latest_scan_audited.csv"
    manual_path = reports / "manual_review_latest.csv"
    manual_top_path = reports / "manual_review_top.csv"
    open_trades_path = reports / "open_trades_snapshot_latest.csv"
    analytics_path = reports / "trade_outcome_analytics_latest.csv"
    cleanup_json_path = reports / "reports_cleanup_latest.json"
    preflight_json_path = reports / "project_preflight_latest.json"
    encoding_audit_json_path = reports / "encoding_audit_latest.json"
    quality_gate_json_path = reports / "daily_quality_gate_latest.json"
    scenario_engine_audit_json_path = reports / "scenario_engine_audit_latest.json"
    live_quote_recheck_json_path = reports / "live_quote_recheck_latest.json"
    trade_decision_checklist_json_path = reports / "trade_decision_checklist_latest.json"
    trade_candidate_cards_json_path = reports / "trade_candidate_cards_latest.json"
    trade_score_calibration_json_path = reports / "trade_score_calibration_latest.json"
    calibration_recommendations_json_path = reports / "calibration_recommendations_latest.json"
    posttest_thesis_audit_json_path = reports / "posttest_thesis_audit_latest.json"
    simple_candidate_posttest_json_path = reports / "simple_candidate_posttest_latest.json"
    engine_feedback_json_path = reports / "engine_feedback_latest.json"
    portfolio_concentration_json_path = reports / "portfolio_concentration_latest.json"
    release_readiness_json_path = reports / "release_readiness_latest.json"
    ui_data_contract_json_path = reports / "ui_data_contract_audit_latest.json"
    streamlit_smoke_json_path = reports / "streamlit_smoke_test_latest.json"
    gui_actions_json_path = reports / "gui_actions_audit_latest.json"
    gui_visuals_json_path = reports / "gui_visuals_audit_latest.json"
    gui_release_json_path = reports / "gui_release_audit_latest.json"
    alpaca_readonly_json_path = reports / "alpaca_readonly_connectivity_latest.json"
    webull_readonly_json_path = reports / "webull_readonly_market_data_latest.json"
    cboe_market_statistics_json_path = reports / "cboe_market_statistics_latest.json"
    google_sheets_data_source_json_path = reports / "google_sheets_data_source_latest.json"
    macro_event_context_json_path = reports / "macro_event_context_latest.json"
    nasdaq_risk_regime_json_path = reports / "nasdaq_risk_regime_latest.json"

    summary_text = _read_text(summary_path)

    scan_df = _load_csv(scan_path)
    manual_df = _load_csv(manual_path)
    manual_top_df = _load_csv(manual_top_path)
    open_trades_df = _load_csv(open_trades_path)
    analytics_df = _load_csv(analytics_path)
    cleanup_data = _normalize_cleanup_status(_load_json(cleanup_json_path))
    preflight_data = _normalize_preflight_status(_load_json(preflight_json_path))
    encoding_audit_data = _normalize_encoding_audit_status(_load_json(encoding_audit_json_path))
    quality_gate_data = _normalize_quality_gate_status(_load_json(quality_gate_json_path))
    scenario_engine_audit_data = _normalize_scenario_engine_audit_status(
        _load_json(scenario_engine_audit_json_path)
    )
    live_quote_recheck_data = _normalize_live_quote_recheck_status(
        _load_json(live_quote_recheck_json_path)
    )
    trade_decision_checklist_data = _normalize_trade_decision_checklist_status(
        _load_json(trade_decision_checklist_json_path)
    )
    trade_candidate_cards_data = _normalize_trade_candidate_cards_status(
        _load_json(trade_candidate_cards_json_path)
    )
    trade_score_calibration_data = _normalize_trade_score_calibration_status(
        _load_json(trade_score_calibration_json_path)
    )
    calibration_recommendations_data = _normalize_calibration_recommendations_status(
        _load_json(calibration_recommendations_json_path)
    )
    posttest_thesis_audit_data = _normalize_posttest_thesis_audit_status(
        _load_json(posttest_thesis_audit_json_path)
    )
    simple_candidate_posttest_data = _normalize_simple_candidate_posttest_status(
        _load_json(simple_candidate_posttest_json_path)
    )
    engine_feedback_data = _normalize_engine_feedback_status(
        _load_json(engine_feedback_json_path)
    )
    portfolio_concentration_data = _normalize_portfolio_concentration_status(
        _load_json(portfolio_concentration_json_path)
    )
    release_readiness_data = _normalize_release_readiness_status(
        _load_json(release_readiness_json_path)
    )
    ui_data_contract_data = _normalize_ui_data_contract_status(
        _load_json(ui_data_contract_json_path)
    )
    streamlit_smoke_data = _normalize_streamlit_smoke_status(
        _load_json(streamlit_smoke_json_path)
    )
    gui_actions_data = _normalize_gui_actions_audit_status(
        _load_json(gui_actions_json_path)
    )
    gui_visuals_data = _normalize_gui_visuals_audit_status(
        _load_json(gui_visuals_json_path)
    )
    gui_release_data = _normalize_gui_release_audit_status(
        _load_json(gui_release_json_path)
    )
    alpaca_readonly_data = _normalize_alpaca_readonly_connectivity_status(
        _load_json(alpaca_readonly_json_path),
    )
    webull_readonly_data = _normalize_secondary_data_provider_status(
        _load_json(webull_readonly_json_path),
        rows_key="endpoint_checks",
    )
    cboe_market_statistics_data = _normalize_secondary_data_provider_status(
        _load_json(cboe_market_statistics_json_path),
        rows_key="datasets_available",
    )
    google_sheets_data_source_data = _normalize_secondary_data_provider_status(
        _load_json(google_sheets_data_source_json_path),
        rows_key="rows",
    )
    macro_event_context_data = _normalize_macro_event_context_status(
        _load_json(macro_event_context_json_path),
    )
    nasdaq_risk_regime_data = _normalize_nasdaq_risk_regime_status(
        _load_json(nasdaq_risk_regime_json_path),
    )
    manifest_data = _load_json(reports / "daily_run_manifest_latest.json")
    manifest_status = manifest_data.get("status", "UNKNOWN")
    git_dirty = bool(manifest_data.get("git", {}).get("dirty", False))
    missing_script_files = len(manifest_data.get("summary", {}).get("missing_script_files", []))
    missing_report_files = len(manifest_data.get("summary", {}).get("missing_report_files", []))
    
    if manual_top_df.empty and not manual_df.empty:
        manual_top_df = manual_df.head(20).copy()

    signals = _value_counts(scan_df, "signal")
    recommendations = _value_counts(manual_df if not manual_df.empty else scan_df, "recommendation")
    quote_recheck_priority = _value_counts(manual_df, "quote_recheck_priority")
    options_bias = _value_counts(scan_df, "options_bias")
    options_confidence = _value_counts(scan_df, "options_confidence")
    options_source = _value_counts(scan_df, "options_source")
    options_available = _value_counts(scan_df, "options_available")
    if not options_available:
        options_available = _value_counts(scan_df, "options_data_available")
    options_error = _value_counts(scan_df, "options_error")
    technical_prefilter = _value_counts(scan_df, "technical_prefilter_status")
    daily_macd_prefilter = _value_counts(scan_df, "daily_macd_prefilter_status")
    weekly_macd_prefilter = _value_counts(scan_df, "weekly_macd_prefilter_status")
    ema20_extension_prefilter = _value_counts(scan_df, "ema20_extension_prefilter_status")
    sector_weekly_macd = _value_counts(scan_df, "sector_weekly_macd_state")
    sector_weekly_macd_acceleration = _value_counts(scan_df, "sector_weekly_macd_acceleration_state")
    sector_context_status = _value_counts(scan_df, "sector_context_status")

    trigger_count = int(signals.get("TRIGGER_CONFIRMED", 0) or 0)
    watchlist_count = int(signals.get("WATCHLIST", 0) or 0)
    recheck_count = int(recommendations.get("RECHECK_LIVE_QUOTE", 0) or 0)

    report_paths = [
        reports / "daily_validation_summary.txt",
        reports / "daily_operator_index.md",
        reports / "daily_quality_gate_latest.json",
        reports / "daily_quality_gate_latest.md",
        reports / "scenario_engine_audit_latest.json",
        reports / "scenario_engine_audit_latest.md",
        reports / "release_readiness_latest.json",
        reports / "release_readiness_latest.md",
        reports / "ui_data_contract_audit_latest.json",
        reports / "ui_data_contract_audit_latest.md",
        reports / "streamlit_smoke_test_latest.json",
        reports / "streamlit_smoke_test_latest.md",
        reports / "gui_actions_audit_latest.json",
        reports / "gui_actions_audit_latest.md",
        reports / "gui_visuals_audit_latest.json",
        reports / "gui_visuals_audit_latest.md",
        reports / "gui_release_audit_latest.json",
        reports / "gui_release_audit_latest.md",
        reports / "alpaca_readonly_connectivity_latest.json",
        reports / "alpaca_readonly_connectivity_latest.md",
        reports / "webull_readonly_market_data_latest.json",
        reports / "webull_readonly_market_data_latest.md",
        reports / "cboe_market_statistics_latest.json",
        reports / "cboe_market_statistics_latest.md",
        reports / "google_sheets_data_source_latest.json",
        reports / "google_sheets_data_source_latest.md",
        reports / "macro_event_context_latest.json",
        reports / "macro_event_context_latest.md",
        reports / "nasdaq_risk_regime_latest.json",
        reports / "nasdaq_risk_regime_latest.md",
        reports / "live_quote_recheck_latest.csv",
        reports / "live_quote_recheck_latest.md",
        reports / "live_quote_recheck_latest.json",
        reports / "trade_decision_checklist_latest.csv",
        reports / "trade_decision_checklist_latest.md",
        reports / "trade_decision_checklist_latest.json",
        reports / "trade_candidate_cards_latest.md",
        reports / "trade_candidate_cards_latest.json",
        reports / "trade_score_calibration_latest.csv",
        reports / "trade_score_calibration_latest.json",
        reports / "trade_score_calibration_latest.md",
        reports / "calibration_recommendations_latest.md",
        reports / "calibration_recommendations_latest.json",
        reports / "posttest_thesis_audit_latest.md",
        reports / "posttest_thesis_audit_latest.json",
        reports / "simple_candidate_posttest_latest.csv",
        reports / "simple_candidate_posttest_latest.md",
        reports / "simple_candidate_posttest_latest.json",
        reports / "engine_feedback_latest.md",
        reports / "engine_feedback_latest.json",
        reports / "portfolio_concentration_latest.md",
        reports / "portfolio_concentration_latest.json",
        reports / "project_preflight_latest.json",
        reports / "project_preflight_latest.md",
        reports / "daily_run_manifest_latest.json",
        reports / "daily_run_manifest_latest.md",
        reports / "encoding_audit_latest.json",
        reports / "encoding_audit_latest.md",
        reports / "manual_review_top.md",
        reports / "manual_review_latest.md",
        reports / "open_trades_snapshot_latest.md",
        reports / "trade_outcome_analytics_latest.md",
        reports / "reports_cleanup_latest.json",
        reports / "reports_cleanup_latest.md",
        reports / "latest_scan_audited.csv",
        reports / "manual_review_top.csv",
        reports / "manual_review_latest.csv",
        reports / "trade_outcome_analytics_latest.csv",
    ]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "validation_status": _parse_status_from_summary(summary_text),
        "scan_rows": int(len(scan_df)) if not scan_df.empty else 0,
        "manual_review_rows": int(len(manual_df)) if not manual_df.empty else 0,
        "manual_top_rows": int(len(manual_top_df)) if not manual_top_df.empty else 0,
        "open_trades_rows": int(len(open_trades_df)) if not open_trades_df.empty else 0,
        "analytics_rows": int(len(analytics_df)) if not analytics_df.empty else 0,
        "signals": signals,
        "recommendations": recommendations,
        "quote_recheck_priority": quote_recheck_priority,
        "options_bias": options_bias,
        "options_confidence": options_confidence,
        "options_source": options_source,
        "options_available": options_available,
        "options_error": options_error,
        "technical_prefilter": technical_prefilter,
        "daily_macd_prefilter": daily_macd_prefilter,
        "weekly_macd_prefilter": weekly_macd_prefilter,
        "ema20_extension_prefilter": ema20_extension_prefilter,
        "sector_weekly_macd": sector_weekly_macd,
        "sector_weekly_macd_acceleration": sector_weekly_macd_acceleration,
        "sector_context_status": sector_context_status,
        "trigger_count": trigger_count,
        "watchlist_count": watchlist_count,
        "recheck_count": recheck_count,
        "top_candidates": _select_top_candidate_columns(manual_top_df),
        "recheck_candidates": _select_recheck_columns(manual_df),
        "open_trades": _select_open_trade_columns(open_trades_df),
        "analytics_overall": _select_analytics_overall(analytics_df),
        "cleanup": cleanup_data,
        "preflight": preflight_data,
        "encoding_audit": encoding_audit_data,
        "quality_gate": quality_gate_data,
        "scenario_engine_audit": scenario_engine_audit_data,
        "live_quote_recheck": live_quote_recheck_data,
        "trade_decision_checklist": trade_decision_checklist_data,
        "trade_candidate_cards": trade_candidate_cards_data,
        "trade_score_calibration": trade_score_calibration_data,
        "calibration_recommendations": calibration_recommendations_data,
        "posttest_thesis_audit": posttest_thesis_audit_data,
        "simple_candidate_posttest": simple_candidate_posttest_data,
        "engine_feedback": engine_feedback_data,
        "portfolio_concentration": portfolio_concentration_data,
        "release_readiness": release_readiness_data,
        "ui_data_contract": ui_data_contract_data,
        "streamlit_smoke_test": streamlit_smoke_data,
        "gui_actions_audit": gui_actions_data,
        "gui_visuals_audit": gui_visuals_data,
        "gui_release_audit": gui_release_data,
        "alpaca_readonly_connectivity": alpaca_readonly_data,
        "webull_readonly_market_data": webull_readonly_data,
        "cboe_market_statistics": cboe_market_statistics_data,
        "google_sheets_data_source": google_sheets_data_source_data,
        "macro_event_context": macro_event_context_data,
        "nasdaq_risk_regime": nasdaq_risk_regime_data,
        "manifest_status": manifest_status,
        "git_dirty": git_dirty,
        "missing_script_files": missing_script_files,
        "missing_report_files": missing_report_files,
        "report_status": [_file_status(path, root=root) for path in report_paths],
    }


def _format_counts(counts: dict) -> list[str]:
    if not counts:
        return ["- Sin datos."]

    return [f"- {key}: {value}" for key, value in counts.items()]


def _format_report_status(report_status: list[dict]) -> str:
    if not report_status:
        return "_Sin archivos monitoreados._"

    lines = []
    lines.append("| file | status | size_bytes | modified |")
    lines.append("| --- | --- | --- | --- |")

    for item in report_status:
        status = "OK" if item.get("exists") else "MISSING"
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.get("path", "")),
                    status,
                    str(item.get("size_bytes", "")),
                    str(item.get("modified", "")),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def _append_encoding_audit_section(lines: list[str], data: dict) -> None:
    encoding = data.get("encoding_audit", {}) or {}

    lines.append("## Auditoría de encoding")
    lines.append("")

    if not encoding.get("available", False):
        lines.append("- No hay reporte de encoding disponible.")
        lines.append("- Ejecutar `python .\\tools\\encoding_audit.py` para generar diagnóstico.")
        lines.append("")
        return

    encoding_status = str(encoding.get("status", "UNKNOWN")).upper()
    files_scanned = encoding.get("files_scanned", 0)
    warn_files = encoding.get("warn_files", 0)
    error_files = encoding.get("error_files", 0)
    total_marker_hits = encoding.get("total_marker_hits", 0)

    lines.append(f"- status: {encoding_status}")
    lines.append(f"- files_scanned: {files_scanned}")
    lines.append(f"- warn_files: {warn_files}")
    lines.append(f"- error_files: {error_files}")
    lines.append(f"- total_marker_hits: {total_marker_hits}")
    lines.append("- report: reports/encoding_audit_latest.md")

    if encoding_status == "PASS":
        lines.append("- Estado PASS: no se detectaron marcadores típicos de mojibake.")
    elif encoding_status == "WARN":
        lines.append("- Estado WARN: se detectaron textos mal codificados o posibles marcadores de mojibake.")
        lines.append("- Revisar `reports/encoding_audit_latest.md`.")
    elif encoding_status == "FAIL":
        lines.append("- Estado FAIL: hay archivos que no pudieron leerse o auditarse correctamente.")
        lines.append("- Revisar `reports/encoding_audit_latest.md`.")
    else:
        lines.append("- Estado desconocido: revisar `reports/encoding_audit_latest.md`.")

    lines.append("")


def build_daily_operator_index_markdown(data: dict) -> str:
    status = str(data.get("validation_status", "UNKNOWN")).upper()
    recheck_count = int(data.get("recheck_count", 0) or 0)
    trigger_count = int(data.get("trigger_count", 0) or 0)
    watchlist_count = int(data.get("watchlist_count", 0) or 0)

    lines: list[str] = []

    lines.append("# Analista - daily operator index")
    lines.append("")
    lines.append(f"- generated_at: {data.get('generated_at')}")
    lines.append(f"- validation_status: {status}")
    lines.append(f"- scan_rows: {data.get('scan_rows')}")
    lines.append(f"- manual_review_rows: {data.get('manual_review_rows')}")
    lines.append(f"- manual_top_rows: {data.get('manual_top_rows')}")
    lines.append(f"- open_trades_rows: {data.get('open_trades_rows')}")
    lines.append(f"- analytics_rows: {data.get('analytics_rows')}")
    lines.append("")

    scenario_audit = data.get("scenario_engine_audit", {}) or {}
    lines.append("## Scenario engine")
    lines.append("")
    if not bool(scenario_audit.get("available", False)):
        lines.append("- status: MISSING")
        lines.append("- Ejecutar `python .\\tools\\scenario_engine_audit.py` para generarlo.")
    else:
        lines.append(f"- status: {scenario_audit.get('status')}")
        lines.append(f"- deep_analysis_rows: {scenario_audit.get('deep_analysis_rows')}")
        lines.append(f"- within_target_band: {scenario_audit.get('within_target_band')}")
        lines.append(f"- valid_trigger: {scenario_audit.get('valid_trigger')}")
        lines.append(f"- wait_for_confirmation: {scenario_audit.get('wait_for_confirmation')}")
        lines.append(f"- late_entry_overextended: {scenario_audit.get('late_entry_overextended')}")
        lines.append(f"- weak_momentum: {scenario_audit.get('weak_momentum')}")
        lines.append(f"- structure_invalid: {scenario_audit.get('structure_invalid')}")
        lines.append(f"- context_conflict: {scenario_audit.get('context_conflict')}")
        lines.append(f"- data_insufficient: {scenario_audit.get('data_insufficient')}")
        lines.append(
            f"- blocked_or_not_operable: {scenario_audit.get('blocked_or_not_operable')}"
        )
        lines.append("- markdown: reports/scenario_engine_audit_latest.md")
        lines.append("- json: reports/scenario_engine_audit_latest.json")
        lines.append("- Modo sombra; no modifica señales ni ejecución.")
    lines.append("")

    lines.append("## Technical prefilter")
    lines.append("")
    technical_prefilter = data.get("technical_prefilter", {}) or {}
    if not technical_prefilter:
        lines.append("- status: MISSING")
        lines.append("- Campos de prefiltro técnico no encontrados en latest_scan_audited.csv.")
    else:
        lines.append(f"- pass: {technical_prefilter.get('PASS', 0)}")
        lines.append(f"- fail: {technical_prefilter.get('FAIL', 0)}")
        lines.append(f"- daily_macd: {data.get('daily_macd_prefilter', {})}")
        lines.append(f"- weekly_macd: {data.get('weekly_macd_prefilter', {})}")
        lines.append(f"- ema20_extension: {data.get('ema20_extension_prefilter', {})}")
        lines.append("- Uso: gate temprano read-only; no crea TRIGGER_CONFIRMED ni relaja quote quality.")
    lines.append("")

    lines.append("## Sector weekly MACD context")
    lines.append("")
    sector_weekly_macd = data.get("sector_weekly_macd", {}) or {}
    if not sector_weekly_macd:
        lines.append("- status: MISSING")
        lines.append("- Campos de MACD semanal sectorial no encontrados en latest_scan_audited.csv.")
    else:
        lines.append(f"- sector_weekly_macd_state: {sector_weekly_macd}")
        lines.append(f"- sector_weekly_macd_acceleration: {data.get('sector_weekly_macd_acceleration', {})}")
        lines.append(f"- sector_context_status: {data.get('sector_context_status', {})}")
        lines.append("- Uso: contexto de timing sectorial; puede degradar revisión, no promueve señales.")
    lines.append("")

    quality_gate = data.get("quality_gate", {}) or {}
    quality_available = bool(quality_gate.get("available", False))
    quality_status = str(quality_gate.get("status", "UNKNOWN")).upper()
    manual_review_allowed = bool(quality_gate.get("manual_review_allowed", False))
    manual_review_mode = str(quality_gate.get("manual_review_mode", "UNKNOWN")).upper()
    issue_count = int(quality_gate.get("issue_count", 0) or 0)
    fail_issues = int(quality_gate.get("fail_issues", 0) or 0)
    warn_issues = int(quality_gate.get("warn_issues", 0) or 0)

    lines.append("## Daily quality gate")
    lines.append("")

    if not quality_available:
        lines.append("- No hay reporte de quality gate disponible.")
        lines.append("- Ejecutar `python .\\tools\\daily_quality_gate.py` o `python .\\tools\\daily_validation.py`.")
    else:
        lines.append(f"- status: {quality_status}")
        lines.append(f"- manual_review_allowed: {manual_review_allowed}")
        lines.append(f"- manual_review_mode: {manual_review_mode}")
        lines.append(f"- issue_count: {issue_count}")
        lines.append(f"- fail_issues: {fail_issues}")
        lines.append(f"- warn_issues: {warn_issues}")
        lines.append(f"- scan_freshness_status: {quality_gate.get('scan_freshness_status', 'UNKNOWN')}")
        lines.append(f"- scan_age_hours: {quality_gate.get('scan_age_hours', '')}")
        lines.append(f"- manual_review_age_hours: {quality_gate.get('manual_review_age_hours', '')}")
        lines.append(f"- macro_age_hours: {quality_gate.get('macro_age_hours', '')}")
        lines.append(f"- scan_is_current_local_date: {quality_gate.get('scan_is_current_local_date', False)}")

        if quality_status == "FAIL":
            lines.append("- Estado FAIL: no usar candidatos operativamente hasta corregir errores.")
            lines.append("- Abrir `reports/daily_quality_gate_latest.md`.")
        elif quality_status == "WARN":
            lines.append("- Estado WARN: revisión manual permitida, pero con validación reforzada.")
            lines.append("- Abrir `reports/daily_quality_gate_latest.md`.")
            if quality_gate.get("scan_freshness_status") == "WARN":
                lines.append("- Scan antiguo: regenerar scan antes de tomar decisiones operativas.")
        elif quality_status == "PASS":
            lines.append("- Estado PASS: corrida apta para revisión manual normal.")
        else:
            lines.append("- Estado desconocido: revisar `reports/daily_quality_gate_latest.md`.")

    lines.append("")

    calibration = data.get("trade_score_calibration", {}) or {}
    calibration_available = bool(calibration.get("available", False))

    lines.append("## Trade score calibration")
    lines.append("")

    if not calibration_available:
        lines.append("- No hay reporte de trade score calibration disponible.")
        lines.append("- Ejecutar `python .\\tools\\trade_score_calibration.py` para generarlo.")
    else:
        lines.append(f"- status: {calibration.get('status', 'UNKNOWN')}")
        lines.append(f"- closed_trades: {calibration.get('closed_trades', 0)}")
        lines.append(f"- win_rate: {calibration.get('win_rate', '')}")
        lines.append(f"- avg_r_multiple: {calibration.get('avg_r_multiple', '')}")
        lines.append(f"- sample_size_warning: {calibration.get('sample_size_warning', '')}")
        lines.append("- csv: reports/trade_score_calibration_latest.csv")
        lines.append("- markdown: reports/trade_score_calibration_latest.md")
        lines.append("- json: reports/trade_score_calibration_latest.json")
        lines.append("- Calibracion observacional; no cambia pesos ni thresholds.")

    lines.append("")

    calibration_recommendations = data.get("calibration_recommendations", {}) or {}
    calibration_recommendations_available = bool(calibration_recommendations.get("available", False))

    lines.append("## Calibration recommendations")
    lines.append("")

    if not calibration_recommendations_available:
        lines.append("- No hay reporte de calibration recommendations disponible.")
        lines.append("- Ejecutar `python .\\tools\\calibration_recommendations.py` para generarlo.")
    else:
        lines.append(f"- status: {calibration_recommendations.get('status', 'UNKNOWN')}")
        lines.append(f"- closed_trades: {calibration_recommendations.get('closed_trades', 0)}")
        lines.append(
            f"- recommendation_count: {calibration_recommendations.get('recommendation_count', 0)}"
        )
        lines.append(
            f"- sample_size_warning: {calibration_recommendations.get('sample_size_warning', '')}"
        )
        lines.append("- markdown: reports/calibration_recommendations_latest.md")
        lines.append("- json: reports/calibration_recommendations_latest.json")
        lines.append("- Recomendaciones observacionales; no cambian pesos ni thresholds.")

    lines.append("")

    thesis_audit = data.get("posttest_thesis_audit", {}) or {}
    lines.append("## Four-day trading thesis audit")
    lines.append("")
    if not bool(thesis_audit.get("available", False)):
        lines.append("- status: MISSING")
        lines.append("- Ejecutar `python .\\tools\\posttest_thesis_audit.py` para generarlo.")
    else:
        lines.append(f"- status: {thesis_audit.get('status', 'UNKNOWN')}")
        lines.append(f"- executed_entries: {thesis_audit.get('executed_entries', 0)}")
        lines.append(f"- no_entry_triggers: {thesis_audit.get('no_entry_triggers', 0)}")
        lines.append(f"- win_rate: {thesis_audit.get('win_rate')}")
        lines.append(f"- target_hit_rate: {thesis_audit.get('target_hit_rate')}")
        lines.append(f"- stop_hit_rate: {thesis_audit.get('stop_hit_rate')}")
        lines.append(f"- sample_size_warning: {thesis_audit.get('sample_size_warning', '')}")
        lines.append("- markdown: reports/posttest_thesis_audit_latest.md")
        lines.append("- json: reports/posttest_thesis_audit_latest.json")
        lines.append("- Evidencia observacional; no cambia scoring, thresholds ni señales.")
    lines.append("")

    simple_posttest = data.get("simple_candidate_posttest", {}) or {}
    lines.append("## Simple candidate posttest")
    lines.append("")
    if not bool(simple_posttest.get("available", False)):
        lines.append("- status: MISSING")
        lines.append("- Ejecutar `python .\\tools\\simple_candidate_posttest.py` para generarlo.")
    else:
        lines.append(f"- status: {simple_posttest.get('status', 'UNKNOWN')}")
        lines.append(f"- rows: {simple_posttest.get('rows', 0)}")
        lines.append(f"- report_sessions_available: {simple_posttest.get('report_sessions_available', 0)}")
        lines.append(f"- win_rate_5: {simple_posttest.get('win_rate_5')}")
        lines.append(f"- win_rate_10: {simple_posttest.get('win_rate_10')}")
        lines.append(f"- win_rate_15: {simple_posttest.get('win_rate_15')}")
        lines.append(f"- avg_return_5: {simple_posttest.get('avg_return_5')}")
        lines.append(f"- avg_return_10: {simple_posttest.get('avg_return_10')}")
        lines.append(f"- avg_return_15: {simple_posttest.get('avg_return_15')}")
        lines.append(f"- warnings: {simple_posttest.get('warnings', 0)}")
        lines.append("- markdown: reports/simple_candidate_posttest_latest.md")
        lines.append("- json: reports/simple_candidate_posttest_latest.json")
        lines.append("- csv: reports/simple_candidate_posttest_latest.csv")
        lines.append("- Diagnóstico automático; no cambia pesos, thresholds ni señales.")
    lines.append("")

    engine_feedback = data.get("engine_feedback", {}) or {}
    lines.append("## Engine feedback")
    lines.append("")
    if not bool(engine_feedback.get("available", False)):
        lines.append("- status: MISSING")
        lines.append("- Ejecutar `python .\\tools\\engine_feedback.py` para generarlo.")
    else:
        lines.append(f"- status: {engine_feedback.get('status', 'UNKNOWN')}")
        lines.append(f"- canonical_rows: {engine_feedback.get('canonical_rows', 0)}")
        lines.append(f"- canonical_dates: {engine_feedback.get('canonical_dates', 0)}")
        lines.append(f"- recommendation_count: {engine_feedback.get('recommendation_count', 0)}")
        lines.append(f"- sample_size_warning: {engine_feedback.get('sample_size_warning', '')}")
        lines.append("- markdown: reports/engine_feedback_latest.md")
        lines.append("- json: reports/engine_feedback_latest.json")
        lines.append("- Feedback observacional; no cambia pesos, thresholds ni señales.")
    lines.append("")

    concentration = data.get("portfolio_concentration", {}) or {}
    lines.append("## Portfolio concentration")
    lines.append("")
    if not bool(concentration.get("available", False)):
        lines.append("- status: MISSING")
        lines.append("- Ejecutar `python .\\tools\\portfolio_concentration_audit.py` para generarlo.")
    else:
        lines.append(f"- status: {concentration.get('status', 'UNKNOWN')}")
        lines.append(f"- rows: {concentration.get('rows', 0)}")
        lines.append(f"- warnings: {concentration.get('warnings', 0)}")
        lines.append(f"- concentration_flags: {concentration.get('concentration_flags', 0)}")
        lines.append("- markdown: reports/portfolio_concentration_latest.md")
        lines.append("- json: reports/portfolio_concentration_latest.json")
        lines.append("- Auditoria read-only de concentración sector/factor.")
    lines.append("")

    release_readiness = data.get("release_readiness", {}) or {}
    release_available = bool(release_readiness.get("available", False))

    lines.append("## Release readiness")
    lines.append("")

    if not release_available:
        lines.append("- No hay reporte de release readiness disponible.")
        lines.append("- Ejecutar `python .\\tools\\release_readiness_audit.py` para generarlo.")
    else:
        lines.append(f"- status: {release_readiness.get('status', 'UNKNOWN')}")
        lines.append(f"- critical_failures: {release_readiness.get('critical_failures', 0)}")
        lines.append(f"- warnings: {release_readiness.get('warnings', 0)}")
        lines.append("- markdown: reports/release_readiness_latest.md")
        lines.append("- json: reports/release_readiness_latest.json")
        lines.append("- Auditoria final de release; no modifica logica operativa.")

    lines.append("")

    ui_contract = data.get("ui_data_contract", {}) or {}
    ui_contract_available = bool(ui_contract.get("available", False))

    lines.append("## UI data contract")
    lines.append("")

    if not ui_contract_available:
        lines.append("- No hay reporte de UI data contract disponible.")
        lines.append("- Ejecutar `python .\\tools\\ui_data_contract_audit.py` para generarlo.")
    else:
        lines.append(f"- status: {ui_contract.get('status', 'UNKNOWN')}")
        lines.append(f"- available_sources: {ui_contract.get('available_sources', 0)}")
        lines.append(f"- missing_sources: {ui_contract.get('missing_sources', 0)}")
        lines.append(f"- invalid_sources: {ui_contract.get('invalid_sources', 0)}")
        lines.append(f"- candidate_rows: {ui_contract.get('candidate_rows', 0)}")
        lines.append("- markdown: reports/ui_data_contract_audit_latest.md")
        lines.append("- json: reports/ui_data_contract_audit_latest.json")
        lines.append("- Contrato read-only para futura GUI; no crea acciones operativas.")

    lines.append("")

    streamlit_smoke = data.get("streamlit_smoke_test", {}) or {}
    streamlit_available = bool(streamlit_smoke.get("available", False))

    lines.append("## Streamlit dashboard")
    lines.append("")

    if not streamlit_available:
        lines.append("- No hay reporte de Streamlit smoke test disponible.")
        lines.append("- Ejecutar `python .\\tools\\streamlit_smoke_test.py` para generarlo.")
    else:
        lines.append(f"- status: {streamlit_smoke.get('status', 'UNKNOWN')}")
        lines.append(f"- app_exists: {streamlit_smoke.get('app_exists', False)}")
        lines.append(f"- import_ok: {streamlit_smoke.get('import_ok', False)}")
        lines.append(f"- view_models_ok: {streamlit_smoke.get('view_models_ok', False)}")
        lines.append(f"- read_only: {streamlit_smoke.get('read_only', False)}")
        lines.append("- markdown: reports/streamlit_smoke_test_latest.md")
        lines.append("- json: reports/streamlit_smoke_test_latest.json")
        lines.append("- Dashboard Streamlit read-only para scanner, reportes y posttest automático; sin ordenes reales.")

    lines.append("")

    gui_actions = data.get("gui_actions_audit", {}) or {}
    gui_actions_available = bool(gui_actions.get("available", False))

    lines.append("## GUI actions")
    lines.append("")

    if not gui_actions_available:
        lines.append("- No hay reporte de GUI actions audit disponible.")
        lines.append("- Ejecutar `python .\\tools\\gui_actions_audit.py` para generarlo.")
    else:
        lines.append(f"- status: {gui_actions.get('status', 'UNKNOWN')}")
        lines.append(f"- actions_module_exists: {gui_actions.get('actions_module_exists', False)}")
        lines.append(f"- action_log_exists: {gui_actions.get('action_log_exists', False)}")
        lines.append(f"- logged_actions: {gui_actions.get('logged_actions', 0)}")
        lines.append(f"- broker_guardrail_ok: {gui_actions.get('broker_guardrail_ok', False)}")
        lines.append(f"- shell_guardrail_ok: {gui_actions.get('shell_guardrail_ok', False)}")
        lines.append("- markdown: reports/gui_actions_audit_latest.md")
        lines.append("- json: reports/gui_actions_audit_latest.json")
        lines.append("- Acciones GUI restringidas a refresco, consulta puntual y logs; sin ordenes reales.")

    lines.append("")

    live_recheck = data.get("live_quote_recheck", {}) or {}
    live_recheck_available = bool(live_recheck.get("available", False))

    lines.append("## Live quote recheck")
    lines.append("")

    if not live_recheck_available:
        lines.append("- No hay reporte de live quote recheck disponible.")
        lines.append("- Ejecutar `python .\\tools\\live_quote_recheck.py` si hay candidatos que validar.")
    else:
        lines.append(f"- status: {live_recheck.get('status', 'UNKNOWN')}")
        lines.append(f"- rows: {live_recheck.get('rows', 0)}")
        lines.append(
            f"- execution_ok_review_manually: {live_recheck.get('execution_ok_review_manually', 0)}"
        )
        lines.append(f"- keep_recheck: {live_recheck.get('keep_recheck', 0)}")
        lines.append(f"- watchlist_monitor: {live_recheck.get('watchlist_monitor', 0)}")
        lines.append(f"- avoid_execution_risk: {live_recheck.get('avoid_execution_risk', 0)}")
        lines.append(f"- data_unavailable: {live_recheck.get('data_unavailable', 0)}")
        lines.append("- report: reports/live_quote_recheck_latest.md")
        lines.append(
            "- EXECUTION_OK_REVIEW_MANUALLY no equivale a TRIGGER_CONFIRMED ni a entrada automatica."
        )

    lines.append("")

    checklist = data.get("trade_decision_checklist", {}) or {}
    checklist_available = bool(checklist.get("available", False))

    lines.append("## Trade decision checklist")
    lines.append("")

    if not checklist_available:
        lines.append("- No hay reporte de trade decision checklist disponible.")
        lines.append("- Ejecutar `python .\\tools\\trade_decision_checklist.py` para generarlo.")
    else:
        lines.append(f"- status: {checklist.get('status', 'UNKNOWN')}")
        lines.append(f"- rows: {checklist.get('rows', 0)}")
        lines.append(f"- blocked: {checklist.get('blocked', 0)}")
        lines.append(
            f"- needs_live_quote_recheck: {checklist.get('needs_live_quote_recheck', 0)}"
        )
        lines.append(f"- review_manually: {checklist.get('review_manually', 0)}")
        lines.append(f"- high_quality_review: {checklist.get('high_quality_review', 0)}")
        lines.append("- csv: reports/trade_decision_checklist_latest.csv")
        lines.append("- md: reports/trade_decision_checklist_latest.md")
        lines.append("- json: reports/trade_decision_checklist_latest.json")
        lines.append("- HIGH_QUALITY_REVIEW no equivale a compra automatica.")

    lines.append("")

    gui_visuals = data.get("gui_visuals_audit", {}) or {}
    gui_visuals_available = bool(gui_visuals.get("available", False))
    lines.append("## GUI visuals")
    lines.append("")
    if not gui_visuals_available:
        lines.append("- No hay reporte de GUI visuals audit disponible.")
        lines.append("- Ejecutar `python .\\tools\\gui_visuals_audit.py` para generarlo.")
    else:
        lines.append(f"- status: {gui_visuals.get('status', 'UNKNOWN')}")
        lines.append(f"- charts_module_exists: {gui_visuals.get('charts_module_exists', False)}")
        lines.append(f"- app_uses_charts: {gui_visuals.get('app_uses_charts', False)}")
        lines.append(f"- empty_data_safe: {gui_visuals.get('empty_data_safe', False)}")
        lines.append(f"- broker_guardrail_ok: {gui_visuals.get('broker_guardrail_ok', False)}")
        lines.append(f"- shell_guardrail_ok: {gui_visuals.get('shell_guardrail_ok', False)}")
        lines.append("- markdown: reports/gui_visuals_audit_latest.md")
        lines.append("- json: reports/gui_visuals_audit_latest.json")
    lines.append("")

    gui_release = data.get("gui_release_audit", {}) or {}
    gui_release_available = bool(gui_release.get("available", False))
    lines.append("## GUI release")
    lines.append("")
    if not gui_release_available:
        lines.append("- No hay reporte de GUI release audit disponible.")
        lines.append("- Ejecutar `python .\\tools\\gui_release_audit.py` para generarlo.")
    else:
        lines.append(f"- status: {gui_release.get('status', 'UNKNOWN')}")
        lines.append(f"- app_exists: {gui_release.get('app_exists', False)}")
        lines.append(f"- guards_exists: {gui_release.get('guards_exists', False)}")
        lines.append(f"- formatters_exists: {gui_release.get('formatters_exists', False)}")
        lines.append(f"- read_write_guardrail_ok: {gui_release.get('read_write_guardrail_ok', False)}")
        lines.append(f"- broker_guardrail_ok: {gui_release.get('broker_guardrail_ok', False)}")
        lines.append(f"- shell_guardrail_ok: {gui_release.get('shell_guardrail_ok', False)}")
        lines.append(f"- confirmation_guardrail_ok: {gui_release.get('confirmation_guardrail_ok', False)}")
        lines.append("- markdown: reports/gui_release_audit_latest.md")
        lines.append("- json: reports/gui_release_audit_latest.json")
    lines.append("")

    alpaca_readonly = data.get("alpaca_readonly_connectivity", {}) or {}
    alpaca_available = bool(alpaca_readonly.get("available", False))
    lines.append("## Alpaca read-only connectivity")
    lines.append("")
    if not alpaca_available:
        lines.append("- No hay reporte de Alpaca read-only connectivity disponible.")
        lines.append("- Ejecutar `python .\\tools\\alpaca_readonly_connectivity_audit.py` para generarlo.")
    else:
        lines.append(f"- status: {alpaca_readonly.get('status', 'UNKNOWN')}")
        lines.append(f"- credentials_present: {alpaca_readonly.get('credentials_present', False)}")
        lines.append(f"- account_status: {alpaca_readonly.get('account_status', 'UNKNOWN')}")
        lines.append(f"- account_check: {alpaca_readonly.get('account_check_status', 'MISSING')}")
        lines.append(f"- clock_check: {alpaca_readonly.get('clock_check_status', 'MISSING')}")
        lines.append(f"- iex_quote_check: {alpaca_readonly.get('iex_quote_check_status', 'MISSING')}")
        lines.append(f"- read_only: {alpaca_readonly.get('read_only', True)}")
        lines.append(f"- execution_enabled: {alpaca_readonly.get('execution_enabled', False)}")
        lines.append(f"- orders_endpoint_called: {alpaca_readonly.get('orders_endpoint_called', False)}")
        lines.append("- markdown: reports/alpaca_readonly_connectivity_latest.md")
        lines.append("- json: reports/alpaca_readonly_connectivity_latest.json")
    lines.append("")

    macro_context = data.get("macro_event_context", {}) or {}
    lines.append("## Macro event and liquidity context")
    lines.append("")
    if not bool(macro_context.get("available", False)):
        lines.append("- status: MISSING")
        lines.append("- Ejecutar `python .\\tools\\macro_event_context.py` para generarlo.")
    else:
        lines.append(f"- status: {macro_context.get('status', 'UNKNOWN')}")
        lines.append(
            f"- next_critical_event: {macro_context.get('next_critical_event', '') or 'UNKNOWN'}"
        )
        lines.append(
            f"- next_critical_event_date: "
            f"{macro_context.get('next_critical_event_date', '') or 'UNKNOWN'}"
        )
        lines.append(f"- days_to_critical_event: {macro_context.get('days_to_critical_event')}")
        lines.append(f"- event_risk_status: {macro_context.get('event_risk_status', 'UNKNOWN')}")
        lines.append(f"- liquidity_context: {macro_context.get('liquidity_context', 'UNKNOWN')}")
        lines.append(f"- macro_regime_mode: {macro_context.get('macro_regime_mode', 'UNKNOWN')}")
        lines.append(f"- macro_regime_confidence: {macro_context.get('macro_regime_confidence', 'UNKNOWN')}")
        lines.append(f"- macro_event_risk: {macro_context.get('macro_event_risk', 'UNKNOWN')}")
        lines.append(f"- macro_liquidity_bias: {macro_context.get('macro_liquidity_bias', 'UNKNOWN')}")
        lines.append(f"- macro_regime_notes: {macro_context.get('macro_regime_notes', '')}")
        lines.append(f"- m2_change_4w_pct: {macro_context.get('m2_change_4w_pct')}")
        lines.append(
            f"- reverse_repo_change_4w_pct: "
            f"{macro_context.get('reverse_repo_change_4w_pct')}"
        )
        lines.append(
            f"- effective_fed_funds_rate: "
            f"{macro_context.get('effective_fed_funds_rate')}"
        )
        lines.append(f"- us10y_official: {macro_context.get('us10y_official')}")
        lines.append(f"- us30y_official: {macro_context.get('us30y_official')}")
        lines.append(f"- yield_curve_10y2y: {macro_context.get('yield_curve_10y2y')}")
        lines.append(f"- yield_curve_10y3m: {macro_context.get('yield_curve_10y3m')}")
        lines.append(f"- high_yield_spread: {macro_context.get('high_yield_spread')}")
        lines.append(f"- fred_provider_counts: {macro_context.get('fred_provider_counts', {})}")
        lines.append(f"- issues_count: {macro_context.get('issues_count', 0)}")
        lines.append("- markdown: reports/macro_event_context_latest.md")
        lines.append("- json: reports/macro_event_context_latest.json")
        lines.append("- Contexto read-only; no modifica scanner, scoring, señales ni ejecución.")
    lines.append("")

    nasdaq_regime = data.get("nasdaq_risk_regime", {}) or {}
    lines.append("## Nasdaq risk regime")
    lines.append("")
    if not bool(nasdaq_regime.get("available", False)):
        lines.append("- status: MISSING")
        lines.append("- Ejecutar `python .\\tools\\nasdaq_risk_regime_audit.py` para generarlo.")
    else:
        lines.append(f"- status: {nasdaq_regime.get('status', 'UNKNOWN')}")
        lines.append(f"- macro_regime_mode: {nasdaq_regime.get('macro_regime_mode', 'UNKNOWN')}")
        lines.append(
            f"- macro_regime_confidence: "
            f"{nasdaq_regime.get('macro_regime_confidence', 'UNKNOWN')}"
        )
        lines.append(f"- macro_risk_flag: {nasdaq_regime.get('macro_risk_flag', 'UNKNOWN')}")
        lines.append(f"- nasdaq_risk_score: {nasdaq_regime.get('nasdaq_risk_score')}")
        lines.append(f"- nasdaq_risk_semaforo: {nasdaq_regime.get('nasdaq_risk_semaforo', 'UNKNOWN')}")
        lines.append(f"- dominant_regime: {nasdaq_regime.get('dominant_regime', 'UNKNOWN')}")
        lines.append(f"- p_normal: {nasdaq_regime.get('p_normal')}")
        lines.append(f"- p_omega: {nasdaq_regime.get('p_omega')}")
        lines.append(f"- p_sigma: {nasdaq_regime.get('p_sigma')}")
        lines.append(f"- p_phi: {nasdaq_regime.get('p_phi')}")
        lines.append(f"- warnings_count: {nasdaq_regime.get('warnings_count', 0)}")
        lines.append(f"- broker_execution: {nasdaq_regime.get('broker_execution', False)}")
        lines.append(
            f"- creates_trigger_confirmed: "
            f"{nasdaq_regime.get('creates_trigger_confirmed', False)}"
        )
        lines.append("- markdown: reports/nasdaq_risk_regime_latest.md")
        lines.append("- json: reports/nasdaq_risk_regime_latest.json")
        lines.append("- Contexto read-only; no modifica scanner, scoring, señales ni ejecución.")
    lines.append("")

    secondary_providers = [
        ("Webull market data", data.get("webull_readonly_market_data", {}) or {}, "reports/webull_readonly_market_data_latest"),
        ("Cboe market statistics", data.get("cboe_market_statistics", {}) or {}, "reports/cboe_market_statistics_latest"),
        ("Google Sheets manual data", data.get("google_sheets_data_source", {}) or {}, "reports/google_sheets_data_source_latest"),
    ]
    lines.append("## Secondary read-only data sources")
    lines.append("")
    for label, provider_data, output_prefix in secondary_providers:
        lines.append(f"### {label}")
        if not bool(provider_data.get("available", False)):
            lines.append("- status: MISSING")
            lines.append("- Ejecutar la auditoría correspondiente para generarlo.")
        else:
            lines.append(f"- status: {provider_data.get('status', 'UNKNOWN')}")
            lines.append(f"- rows_or_checks: {provider_data.get('rows_or_checks', 0)}")
            lines.append(f"- issues_count: {provider_data.get('issues_count', 0)}")
            lines.append(f"- read_only: {provider_data.get('read_only', True)}")
            lines.append(f"- execution_enabled: {provider_data.get('execution_enabled', False)}")
            if provider_data.get("aggregate_options_status"):
                lines.append(
                    f"- aggregate_options_status: {provider_data.get('aggregate_options_status')}"
                )
                lines.append(
                    f"- aggregate_options_bias: {provider_data.get('aggregate_options_bias')}"
                )
                lines.append(
                    f"- aggregate_put_call_usable: {provider_data.get('aggregate_put_call_usable', False)}"
                )
                lines.append(
                    f"- aggregate_contrarian_note: {provider_data.get('aggregate_contrarian_note', '')}"
                )
            lines.append(f"- markdown: {output_prefix}.md")
            lines.append(f"- json: {output_prefix}.json")
        lines.append("")

    cards = data.get("trade_candidate_cards", {}) or {}
    cards_available = bool(cards.get("available", False))

    lines.append("## Trade candidate cards")
    lines.append("")

    if not cards_available:
        lines.append("- No hay reporte de trade candidate cards disponible.")
        lines.append("- Ejecutar `python .\\tools\\trade_candidate_cards.py` para generarlo.")
    else:
        lines.append(f"- status: {cards.get('status', 'UNKNOWN')}")
        lines.append(f"- rows: {cards.get('rows', 0)}")
        lines.append(f"- high_quality_review: {cards.get('high_quality_review', 0)}")
        lines.append(f"- review_manually: {cards.get('review_manually', 0)}")
        lines.append(
            f"- needs_live_quote_recheck: {cards.get('needs_live_quote_recheck', 0)}"
        )
        lines.append(f"- blocked: {cards.get('blocked', 0)}")
        lines.append("- markdown: reports/trade_candidate_cards_latest.md")
        lines.append("- json: reports/trade_candidate_cards_latest.json")
        lines.append("- Fichas de revision manual; no son entrada automatica.")

    lines.append("")

    lines.append("## Decision gate")
    lines.append("")

    if status == "FAIL":
        lines.append("- Estado FAIL: no usar candidatos operativamente hasta corregir errores requeridos.")
    elif status == "WARN":
        lines.append("- Estado WARN: flujo utilizable solo con revisión manual reforzada.")
    elif status == "PASS":
        lines.append("- Estado PASS: flujo diario completo sin fallos requeridos.")
    else:
        lines.append("- Estado UNKNOWN: revisar daily_validation_summary antes de operar.")

    if recheck_count > 0:
        lines.append(f"- Hay {recheck_count} candidatos RECHECK_LIVE_QUOTE: no operar sin validar quote en vivo.")

    if trigger_count > 0:
        lines.append(f"- Hay {trigger_count} TRIGGER_CONFIRMED: revisar gráfico, quote, R/R, stop y target.")

    if watchlist_count > 0:
        lines.append(f"- Hay {watchlist_count} WATCHLIST: monitoreo, no compra automática.")

    lines.append("")

    lines.append("## Abrir primero")
    lines.append("")
    lines.append("1. `reports/daily_validation_summary.txt`")
    lines.append("2. `reports/daily_quality_gate_latest.md`")
    lines.append("3. `reports/daily_run_manifest_latest.md`")
    lines.append("4. `reports/project_preflight_latest.md`")
    lines.append("5. `reports/encoding_audit_latest.md`")
    lines.append("6. `reports/manual_review_top.md`")
    lines.append("7. `reports/manual_review_latest.md`")
    lines.append("8. `reports/open_trades_snapshot_latest.md`")
    lines.append("9. `reports/trade_outcome_analytics_latest.md`")
    lines.append("10. `reports/reports_cleanup_latest.md`")
    lines.append("11. `reports/latest_scan_audited.csv`")
    lines.append("12. `reports/live_quote_recheck_latest.md`")
    lines.append("13. `reports/trade_decision_checklist_latest.md`")
    lines.append("14. `reports/trade_candidate_cards_latest.md`")
    lines.append("15. `reports/simple_candidate_posttest_latest.md`")
    lines.append("16. `reports/trade_score_calibration_latest.md`")
    lines.append("17. `reports/calibration_recommendations_latest.md`")
    lines.append("18. `reports/release_readiness_latest.md`")
    lines.append("19. `reports/ui_data_contract_audit_latest.md`")
    lines.append("20. `reports/streamlit_smoke_test_latest.md`")
    lines.append("21. `reports/gui_actions_audit_latest.md`")
    lines.append("22. `reports/gui_visuals_audit_latest.md`")
    lines.append("23. `reports/gui_release_audit_latest.md`")
    lines.append("24. `reports/nasdaq_risk_regime_latest.md`")
    lines.append("")

    lines.append("## Señales")
    lines.append("")
    lines.extend(_format_counts(data.get("signals", {})))
    lines.append("")

    lines.append("## Recomendaciones")
    lines.append("")
    lines.extend(_format_counts(data.get("recommendations", {})))
    lines.append("")

    lines.append("## Prioridad quote recheck")
    lines.append("")
    lines.extend(_format_counts(data.get("quote_recheck_priority", {})))
    lines.append("")

    lines.append("## Options / institutional flow")
    lines.append("")
    lines.append("Options bias:")
    lines.extend(_format_counts(data.get("options_bias", {})))
    lines.append("")
    lines.append("Options confidence:")
    lines.extend(_format_counts(data.get("options_confidence", {})))
    lines.append("")
    lines.append("Options source:")
    lines.extend(_format_counts(data.get("options_source", {})))
    lines.append("")
    lines.append("Options available:")
    lines.extend(_format_counts(data.get("options_available", {})))
    lines.append("")
    lines.append("Options error:")
    lines.extend(_format_counts(data.get("options_error", {})))
    lines.append("")
    lines.append("- Options flow es contexto/institutional_score conservador; no es veto duro ni gatillo automatico.")
    lines.append("")

    lines.append("## Top manual review")
    lines.append("")
    lines.append(_df_to_markdown_table(data.get("top_candidates", pd.DataFrame()), max_rows=12))
    lines.append("")

    lines.append("## RECHECK_LIVE_QUOTE")
    lines.append("")
    lines.append(_df_to_markdown_table(data.get("recheck_candidates", pd.DataFrame()), max_rows=12))
    lines.append("")

    lines.append("## Trades abiertos")
    lines.append("")
    lines.append(_df_to_markdown_table(data.get("open_trades", pd.DataFrame()), max_rows=12))
    lines.append("")

    lines.append("## Analytics de trades cerrados")
    lines.append("")
    lines.append(_df_to_markdown_table(data.get("analytics_overall", pd.DataFrame()), max_rows=5))
    lines.append("")

    cleanup = data.get("cleanup", {}) or {}
    cleanup_available = bool(cleanup.get("available", False))
    cleanup_mode = str(cleanup.get("mode", "UNKNOWN"))
    cleanup_candidates = int(cleanup.get("candidate_count", 0) or 0)
    cleanup_moved = int(cleanup.get("moved_count", 0) or 0)
    cleanup_archive_dir = str(cleanup.get("archive_dir", ""))

    preflight = data.get("preflight", {}) or {}
    preflight_available = bool(preflight.get("available", False))
    preflight_status = str(preflight.get("status", "UNKNOWN")).upper()
    preflight_cwd_matches_root = bool(preflight.get("cwd_matches_root", False))
    missing_required_dirs = int(preflight.get("missing_required_dirs", 0) or 0)
    missing_required_files = int(preflight.get("missing_required_files", 0) or 0)
    missing_optional_files = int(preflight.get("missing_optional_files", 0) or 0)
    failed_write_checks = int(preflight.get("failed_write_checks", 0) or 0)

    lines.append("## Project preflight")
    lines.append("")

    if not preflight_available:
        lines.append("- No hay reporte de preflight disponible.")
        lines.append("- Ejecutar `python .\\tools\\project_preflight.py` para generar diagnóstico.")
    else:
        lines.append(f"- status: {preflight_status}")
        lines.append(f"- cwd_matches_root: {preflight_cwd_matches_root}")
        lines.append(f"- missing_required_dirs: {missing_required_dirs}")
        lines.append(f"- missing_required_files: {missing_required_files}")
        lines.append(f"- missing_optional_files: {missing_optional_files}")
        lines.append(f"- failed_write_checks: {failed_write_checks}")

        if preflight_status == "FAIL":
            lines.append("- Estado FAIL: corregir estructura del proyecto antes de operar.")
            lines.append("- Revisar `reports/project_preflight_latest.md`.")
        elif preflight_status == "WARN":
            lines.append("- Estado WARN: revisar advertencias antes de usar el flujo operativo.")
            lines.append("- Revisar `reports/project_preflight_latest.md`.")
        elif preflight_status == "PASS":
            lines.append("- Estado PASS: estructura mínima validada.")
        else:
            lines.append("- Estado desconocido: revisar `reports/project_preflight_latest.md`.")

    lines.append("")

    lines.append("## Limpieza de reportes temporales")
    lines.append("")

    if not cleanup_available:
        lines.append("- No hay reporte de limpieza disponible.")
        lines.append("- Ejecutar `python .\\tools\\reports_cleanup.py` para generar diagnóstico DRY_RUN.")
    else:
        lines.append(f"- mode: {cleanup_mode}")
        lines.append(f"- candidate_count: {cleanup_candidates}")
        lines.append(f"- moved_count: {cleanup_moved}")

        if cleanup_archive_dir:
            lines.append(f"- archive_dir: `{cleanup_archive_dir}`")

        if cleanup_mode == "DRY_RUN" and cleanup_candidates > 0:
            lines.append("- Hay reportes temporales detectados. No fueron movidos automáticamente.")
            lines.append("- Revisar `reports/reports_cleanup_latest.md`.")
            lines.append("- Si corresponde, aplicar manualmente: `python .\\tools\\reports_cleanup.py --apply`.")
        elif cleanup_mode == "DRY_RUN" and cleanup_candidates == 0:
            lines.append("- No hay reportes temporales pendientes.")
        elif cleanup_mode == "APPLY":
            lines.append("- La limpieza fue aplicada manualmente.")
        else:
            lines.append("- Revisar `reports/reports_cleanup_latest.md` para más detalle.")

    lines.append("")
    
    _append_encoding_audit_section(lines, data)

    lines.append("## Daily run manifest")
    lines.append("")
    lines.append(f"- status: {data.get('manifest_status', 'UNKNOWN')}")
    lines.append(f"- daily_validation: {data.get('validation_status', 'UNKNOWN')}")
    lines.append(f"- project_preflight: {data.get('preflight', {}).get('status', 'UNKNOWN')}")
    lines.append(f"- reports_cleanup: {data.get('cleanup', {}).get('status', 'UNKNOWN')}")
    lines.append(f"- git_dirty: {data.get('git_dirty', False)}")
    lines.append(f"- missing_script_files: {data.get('missing_script_files', 0)}")
    lines.append(f"- missing_report_files: {data.get('missing_report_files', 0)}")
    lines.append("")
    lines.append("")
    
    lines.append("## Manifiesto diario de corrida")
    lines.append("")
    lines.append("- Archivo Markdown: `reports/daily_run_manifest_latest.md`")
    lines.append("- Archivo JSON: `reports/daily_run_manifest_latest.json`")
    lines.append("- Uso: trazabilidad de entorno, Git, hashes de scripts clave y reportes generados.")
    lines.append("- Se genera al final de `daily_validation.py`, después del índice operativo.")
    lines.append("- Para confirmar el estado final de la corrida, revisar también `reports/daily_validation_summary.txt`.")
    lines.append("")

    lines.append("## Archivos monitoreados")
    lines.append("")
    lines.append(_format_report_status(data.get("report_status", [])))
    lines.append("")

    lines.append("## Recordatorio operativo")
    lines.append("")
    lines.append("- VETO y AVOID no son operables.")
    lines.append("- WATCHLIST es monitoreo, no entrada automática.")
    lines.append("- RECHECK_LIVE_QUOTE requiere validación live quote antes de cualquier decisión.")
    lines.append("- TRIGGER_CONFIRMED requiere revisión manual final.")
    lines.append("- Confirmar siempre gráfico, quote, entrada, stop, target, R/R, earnings y contexto macro.")

    return "\n".join(lines)


def save_daily_operator_index(
    root: Path = ROOT,
    output_path: Path | None = None,
) -> dict:
    output_path = output_path or root / "reports" / "daily_operator_index.md"

    data = collect_operator_index_data(root=root)
    text = build_daily_operator_index_markdown(data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")

    return {
        "status": "PASS",
        "output_path": str(output_path),
        "validation_status": data.get("validation_status"),
        "scan_rows": data.get("scan_rows"),
        "manual_review_rows": data.get("manual_review_rows"),
        "recheck_count": data.get("recheck_count"),
        "trigger_count": data.get("trigger_count"),
    }


def _normalize_gui_visuals_audit_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "charts_module_exists": False,
            "app_uses_charts": False,
            "empty_data_safe": False,
            "broker_guardrail_ok": False,
            "shell_guardrail_ok": False,
        }
    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")),
        "charts_module_exists": bool(data.get("charts_module_exists", False)),
        "app_uses_charts": bool(data.get("app_uses_charts", False)),
        "empty_data_safe": bool(data.get("empty_data_safe", False)),
        "broker_guardrail_ok": bool(data.get("broker_guardrail_ok", False)),
        "shell_guardrail_ok": bool(data.get("shell_guardrail_ok", False)),
    }


def _normalize_gui_release_audit_status(data: dict) -> dict:
    if not data:
        return {
            "available": False,
            "status": "MISSING",
            "app_exists": False,
            "guards_exists": False,
            "formatters_exists": False,
            "read_write_guardrail_ok": False,
            "broker_guardrail_ok": False,
            "shell_guardrail_ok": False,
            "confirmation_guardrail_ok": False,
        }
    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")),
        "app_exists": bool(data.get("app_exists", False)),
        "guards_exists": bool(data.get("guards_exists", False)),
        "formatters_exists": bool(data.get("formatters_exists", False)),
        "read_write_guardrail_ok": bool(data.get("read_write_guardrail_ok", False)),
        "broker_guardrail_ok": bool(data.get("broker_guardrail_ok", False)),
        "shell_guardrail_ok": bool(data.get("shell_guardrail_ok", False)),
        "confirmation_guardrail_ok": bool(data.get("confirmation_guardrail_ok", False)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera índice operativo diario de Analista.")
    parser.add_argument("--output-path", default="reports/daily_operator_index.md")
    args = parser.parse_args()

    result = save_daily_operator_index(
        root=ROOT,
        output_path=ROOT / args.output_path,
    )

    print("=== ANALISTA DAILY OPERATOR INDEX ===")
    print(f"Status: {result['status']}")
    print(f"Validation status: {result['validation_status']}")
    print(f"Scan rows: {result['scan_rows']}")
    print(f"Manual review rows: {result['manual_review_rows']}")
    print(f"RECHECK_LIVE_QUOTE: {result['recheck_count']}")
    print(f"TRIGGER_CONFIRMED: {result['trigger_count']}")
    print(f"Output: {result['output_path']}")

    return 0


def _normalize_alpaca_readonly_connectivity_status(data: dict) -> dict:
    account_check = data.get("account_check", {}) or {}
    clock_check = data.get("clock_check", {}) or {}
    quote_check = data.get("iex_quote_check", {}) or {}
    account_summary = data.get("account_summary", {}) or {}
    return {
        "available": bool(data),
        "status": str(data.get("status", "MISSING")),
        "credentials_present": bool(data.get("credentials_present", False)),
        "account_status": str(account_summary.get("status", "UNKNOWN")),
        "account_check_status": str(account_check.get("status", "MISSING")),
        "clock_check_status": str(clock_check.get("status", "MISSING")),
        "iex_quote_check_status": str(quote_check.get("status", "MISSING")),
        "read_only": bool(data.get("read_only", True)),
        "execution_enabled": bool(data.get("execution_enabled", False)),
        "orders_endpoint_called": bool(data.get("orders_endpoint_called", False)),
    }


def _normalize_secondary_data_provider_status(data: dict, *, rows_key: str = "rows") -> dict:
    value = data.get(rows_key, 0)
    if isinstance(value, list):
        rows_or_checks = len(value)
    else:
        rows_or_checks = _safe_int(value, 0)
    issues = data.get("issues", []) or []
    aggregate_context = data.get("aggregate_options_context", {}) or {}
    return {
        "available": bool(data),
        "status": str(data.get("status", "MISSING")),
        "rows_or_checks": rows_or_checks,
        "issues_count": len(issues) if isinstance(issues, list) else 0,
        "read_only": bool(data.get("read_only", True)),
        "execution_enabled": bool(data.get("execution_enabled", False)),
        "aggregate_options_status": str(aggregate_context.get("status", "")),
        "aggregate_options_bias": str(aggregate_context.get("bias", "")),
        "aggregate_put_call_usable": bool(aggregate_context.get("usable", False)),
        "aggregate_contrarian_note": str(aggregate_context.get("contrarian_note", "")),
    }


if __name__ == "__main__":
    raise SystemExit(main())
