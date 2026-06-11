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

    trigger_count = int(signals.get("TRIGGER_CONFIRMED", 0) or 0)
    watchlist_count = int(signals.get("WATCHLIST", 0) or 0)
    recheck_count = int(recommendations.get("RECHECK_LIVE_QUOTE", 0) or 0)

    report_paths = [
        reports / "daily_validation_summary.txt",
        reports / "daily_operator_index.md",
        reports / "daily_quality_gate_latest.json",
        reports / "daily_quality_gate_latest.md",
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
        "quality_gate": quality_gate_data,
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

        if quality_status == "FAIL":
            lines.append("- Estado FAIL: no usar candidatos operativamente hasta corregir errores.")
            lines.append("- Abrir `reports/daily_quality_gate_latest.md`.")
        elif quality_status == "WARN":
            lines.append("- Estado WARN: revisión manual permitida, pero con validación reforzada.")
            lines.append("- Abrir `reports/daily_quality_gate_latest.md`.")
        elif quality_status == "PASS":
            lines.append("- Estado PASS: corrida apta para revisión manual normal.")
        else:
            lines.append("- Estado desconocido: revisar `reports/daily_quality_gate_latest.md`.")

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
    
    encoding_audit = data.get("encoding_audit", {}) or {}
    encoding_available = bool(encoding_audit.get("available", False))
    encoding_status = str(encoding_audit.get("status", "UNKNOWN")).upper()
    encoding_files_scanned = int(encoding_audit.get("files_scanned", 0) or 0)
    encoding_warn_files = int(encoding_audit.get("warn_files", 0) or 0)
    encoding_error_files = int(encoding_audit.get("error_files", 0) or 0)
    encoding_total_marker_hits = int(encoding_audit.get("total_marker_hits", 0) or 0)

    lines.append("## Auditoría de encoding")
    lines.append("")

    if not encoding_available:
        lines.append("- No hay reporte de encoding disponible.")
        lines.append("- Ejecutar `python .\\tools\\encoding_audit.py` para generar diagnóstico.")
    else:
        lines.append(f"- status: {encoding_status}")
        lines.append(f"- files_scanned: {encoding_files_scanned}")
        lines.append(f"- warn_files: {encoding_warn_files}")
        lines.append(f"- error_files: {encoding_error_files}")
        lines.append(f"- total_marker_hits: {encoding_total_marker_hits}")

        if encoding_status == "FAIL":
            lines.append("- Estado FAIL: revisar archivos que no pudieron leerse correctamente.")
            lines.append("- Abrir `reports/encoding_audit_latest.md`.")
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


if __name__ == "__main__":
    raise SystemExit(main())
