from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


CRITICAL_REPORTS = [
    "reports/daily_validation_summary.txt",
    "reports/project_preflight_latest.json",
    "reports/latest_scan_audited.csv",
    "reports/manual_review_latest.csv",
]

SUPPORT_REPORTS = [
    "reports/daily_run_manifest_latest.json",
    "reports/encoding_audit_latest.json",
    "reports/reports_cleanup_latest.json",
    "reports/daily_operator_index.md",
    "reports/manual_review_top.csv",
    "reports/manual_review_top.md",
]

DISABLED_BUY_SETUP_SIGNAL = "BUY_" + "SETUP_ACTIVE"


def _relative(path: Path, root: Path = ROOT) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _file_status(path: Path, root: Path = ROOT) -> dict:
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
    }


def _load_json(path: Path) -> tuple[dict, str]:
    if not path.exists():
        return {}, "missing"

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, f"json_error: {exc}"

    if not isinstance(data, dict):
        return {}, "json_root_not_object"

    return data, ""


def _read_text(path: Path) -> tuple[str, str]:
    if not path.exists():
        return "", "missing"

    try:
        return path.read_text(encoding="utf-8", errors="replace"), ""
    except Exception as exc:
        return "", f"read_error: {exc}"


def _parse_status_from_text(text: str) -> str:
    for line in text.splitlines():
        clean = line.strip()
        if clean.startswith("Status:"):
            return clean.split("Status:", 1)[1].strip().upper() or "UNKNOWN"

    return "UNKNOWN"


def _safe_read_csv(path: Path) -> tuple[pd.DataFrame, str]:
    if not path.exists():
        return pd.DataFrame(), "missing"

    try:
        return pd.read_csv(path), ""
    except Exception as exc:
        return pd.DataFrame(), f"csv_error: {exc}"


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


def _add_issue(issues: list[dict], severity: str, source: str, message: str) -> None:
    issues.append(
        {
            "severity": severity.upper(),
            "source": source,
            "message": message,
        }
    )


def _derive_status(issues: list[dict]) -> str:
    severities = {str(item.get("severity", "")).upper() for item in issues}

    if "FAIL" in severities:
        return "FAIL"

    if "WARN" in severities:
        return "WARN"

    return "PASS"


def _normalize_json_status(path: Path, component_name: str) -> dict:
    data, error = _load_json(path)

    if error:
        return {
            "available": False,
            "status": "MISSING",
            "error": error,
            "path": _relative(path),
            "raw": {},
        }

    return {
        "available": True,
        "status": str(data.get("status", "UNKNOWN")).upper(),
        "error": "",
        "path": _relative(path),
        "raw": data,
    }


def _collect_scan_snapshot(scan_df: pd.DataFrame, manual_df: pd.DataFrame) -> dict:
    snapshot = {
        "latest_scan_rows": int(len(scan_df)),
        "manual_review_rows": int(len(manual_df)),
        "signals": _value_counts(scan_df, "signal"),
        "recommendations": _value_counts(scan_df, "recommendation"),
        "quote_status": _value_counts(scan_df, "quote_status"),
        "execution_quote_quality": _value_counts(scan_df, "execution_quote_quality"),
        "manual_quote_recheck_priority": _value_counts(manual_df, "quote_recheck_priority"),
        "scenario_status": _value_counts(scan_df, "scenario_status"),
    }

    return snapshot


def _collect_artifact_freshness(scan_path: Path, manual_path: Path) -> dict:
    scan_modified = scan_path.stat().st_mtime if scan_path.exists() else None
    manual_modified = manual_path.stat().st_mtime if manual_path.exists() else None
    manual_is_stale = bool(
        scan_modified is not None
        and manual_modified is not None
        and manual_modified + 1.0 < scan_modified
    )
    return {
        "scan_modified": datetime.fromtimestamp(scan_modified).isoformat(timespec="seconds")
        if scan_modified is not None
        else "",
        "manual_review_modified": datetime.fromtimestamp(manual_modified).isoformat(timespec="seconds")
        if manual_modified is not None
        else "",
        "manual_review_is_stale": manual_is_stale,
    }


def _scan_logic_checks(scan_df: pd.DataFrame, issues: list[dict]) -> dict:
    checks = {
        "disabled_buy_signal_rows": 0,
        "trigger_with_low_quote_rows": 0,
        "no_valid_setup_not_veto_rows": 0,
        "veto_with_actionable_levels_rows": 0,
        "manual_recheck_quote_rows": 0,
    }

    if scan_df.empty:
        return checks

    if "signal" in scan_df.columns:
        checks["disabled_buy_signal_rows"] = int(
            scan_df["signal"].fillna("").astype(str).eq(DISABLED_BUY_SETUP_SIGNAL).sum()
        )

    if checks["disabled_buy_signal_rows"] > 0:
            _add_issue(
                issues,
                "FAIL",
                "latest_scan_audited.csv",
                f"{DISABLED_BUY_SETUP_SIGNAL} apareció en el scan, pero sigue deshabilitado.",
            )

    if {"signal", "execution_quote_quality"}.issubset(scan_df.columns):
        mask = (
            scan_df["signal"].fillna("").astype(str).eq("TRIGGER_CONFIRMED")
            & scan_df["execution_quote_quality"].fillna("").astype(str).eq("LOW")
        )
        checks["trigger_with_low_quote_rows"] = int(mask.sum())

        if checks["trigger_with_low_quote_rows"] > 0:
            _add_issue(
                issues,
                "FAIL",
                "latest_scan_audited.csv",
                "Hay TRIGGER_CONFIRMED con execution_quote_quality LOW.",
            )

    if {"setup_type", "signal"}.issubset(scan_df.columns):
        mask = (
            scan_df["setup_type"].fillna("").astype(str).eq("NO_VALID_SETUP")
            & ~scan_df["signal"].fillna("").astype(str).eq("VETO")
        )
        checks["no_valid_setup_not_veto_rows"] = int(mask.sum())

        if checks["no_valid_setup_not_veto_rows"] > 0:
            _add_issue(
                issues,
                "FAIL",
                "latest_scan_audited.csv",
                "Hay NO_VALID_SETUP que no quedaron como VETO.",
            )

    actionable_cols = {"actionable_entry", "actionable_stop", "actionable_target"}
    if "signal" in scan_df.columns and actionable_cols.issubset(scan_df.columns):
        veto = scan_df["signal"].fillna("").astype(str).eq("VETO")
        any_actionable = scan_df[list(actionable_cols)].notna().any(axis=1)
        checks["veto_with_actionable_levels_rows"] = int((veto & any_actionable).sum())

        if checks["veto_with_actionable_levels_rows"] > 0:
            _add_issue(
                issues,
                "FAIL",
                "latest_scan_audited.csv",
                "Hay VETO con niveles accionables no nulos.",
            )

    if "recommendation" in scan_df.columns:
        checks["manual_recheck_quote_rows"] = int(
            scan_df["recommendation"].fillna("").astype(str).eq("RECHECK_LIVE_QUOTE").sum()
        )

        if checks["manual_recheck_quote_rows"] > 0:
            _add_issue(
                issues,
                "WARN",
                "latest_scan_audited.csv",
                "Hay candidatos que requieren RECHECK_LIVE_QUOTE antes de revisión operativa.",
            )

    return checks


def collect_daily_quality_gate(root: Path = ROOT) -> dict:
    root = root.resolve()
    reports = root / "reports"

    issues: list[dict] = []

    daily_summary_path = reports / "daily_validation_summary.txt"
    scan_path = reports / "latest_scan_audited.csv"
    manual_path = reports / "manual_review_latest.csv"

    files = {
        "critical": [_file_status(root / path, root=root) for path in CRITICAL_REPORTS],
        "support": [_file_status(root / path, root=root) for path in SUPPORT_REPORTS],
    }

    for item in files["critical"]:
        if not item["exists"]:
            _add_issue(
                issues,
                "FAIL",
                item["path"],
                "Falta reporte crítico requerido para validar la corrida diaria.",
            )

    for item in files["support"]:
        if not item["exists"]:
            _add_issue(
                issues,
                "WARN",
                item["path"],
                "Falta reporte de soporte; no bloquea, pero reduce trazabilidad.",
            )

    daily_text, daily_error = _read_text(daily_summary_path)
    daily_status = _parse_status_from_text(daily_text) if not daily_error else "MISSING"

    if daily_error:
        _add_issue(
            issues,
            "FAIL",
            "daily_validation_summary.txt",
            f"No se pudo leer daily_validation_summary.txt: {daily_error}",
        )
    elif daily_status == "FAIL":
        _add_issue(
            issues,
            "FAIL",
            "daily_validation_summary.txt",
            "daily_validation terminó en FAIL.",
        )
    elif daily_status == "WARN":
        _add_issue(
            issues,
            "WARN",
            "daily_validation_summary.txt",
            "daily_validation terminó en WARN.",
        )
    elif daily_status not in {"PASS", "WARN", "FAIL"}:
        _add_issue(
            issues,
            "WARN",
            "daily_validation_summary.txt",
            f"Estado de daily_validation desconocido: {daily_status}.",
        )

    preflight = _normalize_json_status(reports / "project_preflight_latest.json", "project_preflight")
    manifest = _normalize_json_status(reports / "daily_run_manifest_latest.json", "daily_run_manifest")
    cleanup = _normalize_json_status(reports / "reports_cleanup_latest.json", "reports_cleanup")
    encoding = _normalize_json_status(reports / "encoding_audit_latest.json", "encoding_audit")

    if preflight["status"] == "FAIL":
        _add_issue(
            issues,
            "FAIL",
            "project_preflight",
            "project_preflight terminó en FAIL.",
        )
    elif preflight["status"] == "WARN":
        _add_issue(
            issues,
            "WARN",
            "project_preflight",
            "project_preflight terminó en WARN.",
        )
    elif preflight["status"] == "MISSING":
        _add_issue(
            issues,
            "FAIL",
            "project_preflight",
            "Falta project_preflight_latest.json.",
        )

    if manifest["status"] == "FAIL":
        _add_issue(
            issues,
            "WARN",
            "daily_run_manifest",
            "daily_run_manifest terminó en FAIL; revisar trazabilidad.",
        )
    elif manifest["status"] in {"WARN", "MISSING"}:
        _add_issue(
            issues,
            "WARN",
            "daily_run_manifest",
            f"daily_run_manifest terminó en {manifest['status']}.",
        )

    cleanup_raw = cleanup.get("raw", {}) or {}
    cleanup_candidate_count = _safe_int(cleanup_raw.get("candidate_count"), 0)

    if cleanup["status"] == "FAIL":
        _add_issue(
            issues,
            "WARN",
            "reports_cleanup",
            "reports_cleanup terminó en FAIL; revisar limpieza de temporales.",
        )
    elif cleanup["status"] == "MISSING":
        _add_issue(
            issues,
            "WARN",
            "reports_cleanup",
            "Falta reports_cleanup_latest.json.",
        )

    if cleanup_candidate_count > 0:
        _add_issue(
            issues,
            "WARN",
            "reports_cleanup",
            f"Hay {cleanup_candidate_count} reportes temporales candidatos a limpieza.",
        )

    encoding_raw = encoding.get("raw", {}) or {}
    encoding_summary = encoding_raw.get("summary", {}) or {}
    encoding_warn_files = _safe_int(encoding_summary.get("warn_files"), 0)
    encoding_error_files = _safe_int(encoding_summary.get("error_files"), 0)
    encoding_marker_hits = _safe_int(encoding_summary.get("total_marker_hits"), 0)

    if encoding["status"] == "FAIL":
        _add_issue(
            issues,
            "WARN",
            "encoding_audit",
            "encoding_audit terminó en FAIL; hay archivos que no pudieron leerse.",
        )
    elif encoding["status"] == "MISSING":
        _add_issue(
            issues,
            "WARN",
            "encoding_audit",
            "Falta encoding_audit_latest.json.",
        )

    if encoding_warn_files > 0 or encoding_error_files > 0 or encoding_marker_hits > 0:
        _add_issue(
            issues,
            "WARN",
            "encoding_audit",
            "Hay posibles problemas de encoding/mojibake en reportes.",
        )

    scan_df, scan_error = _safe_read_csv(scan_path)
    manual_df, manual_error = _safe_read_csv(manual_path)

    if scan_error:
        _add_issue(
            issues,
            "FAIL",
            "latest_scan_audited.csv",
            f"No se pudo leer latest_scan_audited.csv: {scan_error}",
        )

    if manual_error:
        _add_issue(
            issues,
            "FAIL",
            "manual_review_latest.csv",
            f"No se pudo leer manual_review_latest.csv: {manual_error}",
        )

    if not scan_error and scan_df.empty:
        _add_issue(
            issues,
            "FAIL",
            "latest_scan_audited.csv",
            "El scan auditado está vacío.",
        )

    if not manual_error and manual_df.empty:
        _add_issue(
            issues,
            "WARN",
            "manual_review_latest.csv",
            "manual_review_latest.csv no tiene candidatos.",
        )

    logic_checks = _scan_logic_checks(scan_df, issues)
    snapshot = _collect_scan_snapshot(scan_df, manual_df)
    artifact_freshness = _collect_artifact_freshness(scan_path, manual_path)
    if artifact_freshness["manual_review_is_stale"]:
        _add_issue(
            issues,
            "WARN",
            "manual_review_latest.csv",
            "manual_review_latest.csv es anterior al scan actual; regenerar reportes derivados.",
        )

    status = _derive_status(issues)

    return {
        "status": status,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": root.as_posix(),
        "manual_review_allowed": status != "FAIL",
        "manual_review_mode": "BLOCKED" if status == "FAIL" else "REINFORCED" if status == "WARN" else "NORMAL",
        "components": {
            "daily_validation": {
                "status": daily_status,
                "path": _relative(daily_summary_path, root),
                "error": daily_error,
            },
            "project_preflight": {
                "status": preflight["status"],
                "available": preflight["available"],
                "path": preflight["path"],
                "error": preflight["error"],
            },
            "daily_run_manifest": {
                "status": manifest["status"],
                "available": manifest["available"],
                "path": manifest["path"],
                "error": manifest["error"],
            },
            "reports_cleanup": {
                "status": cleanup["status"],
                "available": cleanup["available"],
                "path": cleanup["path"],
                "candidate_count": cleanup_candidate_count,
                "error": cleanup["error"],
            },
            "encoding_audit": {
                "status": encoding["status"],
                "available": encoding["available"],
                "path": encoding["path"],
                "warn_files": encoding_warn_files,
                "error_files": encoding_error_files,
                "total_marker_hits": encoding_marker_hits,
                "error": encoding["error"],
            },
        },
        "scan_snapshot": snapshot,
        "artifact_freshness": artifact_freshness,
        "logic_checks": logic_checks,
        "issues": issues,
        "files": files,
    }


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


def build_daily_quality_gate_markdown(data: dict) -> str:
    components = data.get("components", {})
    snapshot = data.get("scan_snapshot", {})
    freshness = data.get("artifact_freshness", {})
    logic_checks = data.get("logic_checks", {})
    issues = data.get("issues", [])

    lines: list[str] = []

    lines.append("# Analista - daily quality gate")
    lines.append("")
    lines.append(f"- generated_at: {data.get('generated_at')}")
    lines.append(f"- status: {data.get('status')}")
    lines.append(f"- manual_review_allowed: {data.get('manual_review_allowed')}")
    lines.append(f"- manual_review_mode: {data.get('manual_review_mode')}")
    lines.append("")

    lines.append("## Decision gate")
    lines.append("")

    if data.get("status") == "FAIL":
        lines.append("- Estado FAIL: no usar esta corrida para revisión manual hasta corregir errores.")
    elif data.get("status") == "WARN":
        lines.append("- Estado WARN: se puede revisar manualmente, pero con validación reforzada.")
    else:
        lines.append("- Estado PASS: corrida apta para revisión manual normal.")

    lines.append("")

    lines.append("## Componentes")
    lines.append("")
    for name, component in components.items():
        lines.append(f"- {name}: {component.get('status')}")
    lines.append("")

    lines.append("## Scan snapshot")
    lines.append("")
    lines.append(f"- latest_scan_rows: {snapshot.get('latest_scan_rows')}")
    lines.append(f"- manual_review_rows: {snapshot.get('manual_review_rows')}")
    lines.append("")
    lines.append("Signals:")
    lines.extend(_format_counts(snapshot.get("signals", {})))
    lines.append("")
    lines.append("Recommendations:")
    lines.extend(_format_counts(snapshot.get("recommendations", {})))
    lines.append("")
    lines.append("Quote status:")
    lines.extend(_format_counts(snapshot.get("quote_status", {})))
    lines.append("")
    lines.append("Execution quote quality:")
    lines.extend(_format_counts(snapshot.get("execution_quote_quality", {})))
    lines.append("")
    lines.append("Scenario status:")
    lines.extend(_format_counts(snapshot.get("scenario_status", {})))
    lines.append("")

    lines.append("## Artifact freshness")
    lines.append("")
    lines.append(f"- scan_modified: {freshness.get('scan_modified', '')}")
    lines.append(f"- manual_review_modified: {freshness.get('manual_review_modified', '')}")
    lines.append(f"- manual_review_is_stale: {freshness.get('manual_review_is_stale', False)}")
    lines.append("")

    lines.append("## Logical checks")
    lines.append("")
    for key, value in logic_checks.items():
        lines.append(f"- {key}: {value}")
    lines.append("")

    lines.append("## Issues")
    lines.append("")
    lines.append(_markdown_table(issues, ["severity", "source", "message"]))
    lines.append("")

    lines.append("## Archivos críticos")
    lines.append("")
    lines.append(
        _markdown_table(
            data.get("files", {}).get("critical", []),
            ["path", "exists", "size_bytes", "modified"],
        )
    )
    lines.append("")

    lines.append("## Archivos de soporte")
    lines.append("")
    lines.append(
        _markdown_table(
            data.get("files", {}).get("support", []),
            ["path", "exists", "size_bytes", "modified"],
        )
    )

    return "\n".join(lines)


def save_daily_quality_gate(
    root: Path = ROOT,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict:
    json_out = json_out or root / "reports" / "daily_quality_gate_latest.json"
    markdown_out = markdown_out or root / "reports" / "daily_quality_gate_latest.md"

    data = collect_daily_quality_gate(root=root)

    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    json_out.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    markdown_out.write_text(
        build_daily_quality_gate_markdown(data),
        encoding="utf-8",
    )

    return {
        "status": data["status"],
        "manual_review_allowed": data["manual_review_allowed"],
        "manual_review_mode": data["manual_review_mode"],
        "json_out": _relative(json_out, root),
        "markdown_out": _relative(markdown_out, root),
        "issue_count": len(data["issues"]),
        "latest_scan_rows": data["scan_snapshot"]["latest_scan_rows"],
        "manual_review_rows": data["scan_snapshot"]["manual_review_rows"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera gate diario de calidad operacional.")
    parser.add_argument("--json-out", default="reports/daily_quality_gate_latest.json")
    parser.add_argument("--markdown-out", default="reports/daily_quality_gate_latest.md")
    args = parser.parse_args()

    result = save_daily_quality_gate(
        root=ROOT,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
    )

    print("=== ANALISTA DAILY QUALITY GATE ===")
    print(f"Status: {result['status']}")
    print(f"Manual review allowed: {result['manual_review_allowed']}")
    print(f"Manual review mode: {result['manual_review_mode']}")
    print(f"Issues: {result['issue_count']}")
    print(f"Latest scan rows: {result['latest_scan_rows']}")
    print(f"Manual review rows: {result['manual_review_rows']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")

    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
