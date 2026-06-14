from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REQUIRED_DIRS = [
    "tools",
    "tests",
    "reports",
]


REQUIRED_FILES = [
    "tools/daily_validation.py",
    "tools/daily_operator_index.py",
    "tools/reports_cleanup.py",
]


OPTIONAL_FILES = [
    "config.yaml",
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
    "reports/paper_trading_journal_latest.md",
    "reports/paper_trading_journal_latest.json",
    "reports/paper_trade_followup_latest.csv",
    "reports/paper_trade_followup_latest.md",
    "reports/paper_trade_followup_latest.json",
    "reports/paper_trade_close_latest.csv",
    "reports/paper_trade_close_latest.md",
    "reports/paper_trade_close_latest.json",
    "reports/paper_trading_cycle_audit_latest.md",
    "reports/paper_trading_cycle_audit_latest.json",
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
    "reports/gui_daily_operating_checklist_latest.json",
    "reports/gui_daily_operating_checklist_latest.md",
    "reports/gui_daily_operating_checklist_audit_latest.json",
    "reports/gui_daily_operating_checklist_audit_latest.md",
    "reports/alpaca_readonly_connectivity_latest.json",
    "reports/alpaca_readonly_connectivity_latest.md",
    "reports/gui_operational_decision_log_latest.json",
    "reports/gui_operational_decision_log_latest.md",
    "reports/gui_post_session_review_latest.json",
    "reports/gui_post_session_review_latest.md",
    "reports/gui_operational_decision_log_audit_latest.json",
    "reports/gui_operational_decision_log_audit_latest.md",
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


def _path_status(path: Path, root: Path = ROOT) -> dict:
    exists = path.exists()

    return {
        "path": _relative(path, root),
        "exists": exists,
        "is_file": path.is_file() if exists else False,
        "is_dir": path.is_dir() if exists else False,
        "size_bytes": path.stat().st_size if exists and path.is_file() else 0,
        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        if exists
        else "",
    }


def _check_writeable_dir(path: Path) -> dict:
    result = {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir() if path.exists() else False,
        "writeable": False,
        "error": "",
    }

    if not path.exists() or not path.is_dir():
        result["error"] = "directory_missing"
        return result

    test_file = path / ".preflight_write_test"

    try:
        test_file.write_text("ok\n", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        result["writeable"] = True
    except Exception as exc:
        result["error"] = str(exc)

    return result


def _overall_status(
    required_dirs: list[dict],
    required_files: list[dict],
    optional_files: list[dict],
    write_checks: list[dict],
    cwd_matches_root: bool,
) -> str:
    missing_required_dirs = [item for item in required_dirs if not item["exists"] or not item["is_dir"]]
    missing_required_files = [item for item in required_files if not item["exists"] or not item["is_file"]]
    failed_write_checks = [item for item in write_checks if not item["writeable"]]

    if missing_required_dirs or missing_required_files or failed_write_checks:
        return "FAIL"

    missing_optional_files = [item for item in optional_files if not item["exists"]]

    if missing_optional_files or not cwd_matches_root:
        return "WARN"

    return "PASS"


def collect_project_preflight(
    root: Path = ROOT,
    required_dirs: list[str] | None = None,
    required_files: list[str] | None = None,
    optional_files: list[str] | None = None,
) -> dict:
    required_dirs = required_dirs or REQUIRED_DIRS
    required_files = required_files or REQUIRED_FILES
    optional_files = optional_files or OPTIONAL_FILES

    root = root.resolve()
    reports_dir = root / "reports"

    required_dir_status = [_path_status(root / path, root=root) for path in required_dirs]
    required_file_status = [_path_status(root / path, root=root) for path in required_files]
    optional_file_status = [_path_status(root / path, root=root) for path in optional_files]

    cwd = Path.cwd().resolve()
    cwd_matches_root = cwd == root

    write_checks = [
        _check_writeable_dir(reports_dir),
    ]

    status = _overall_status(
        required_dirs=required_dir_status,
        required_files=required_file_status,
        optional_files=optional_file_status,
        write_checks=write_checks,
        cwd_matches_root=cwd_matches_root,
    )

    return {
        "status": status,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": root.as_posix(),
        "cwd": cwd.as_posix(),
        "cwd_matches_root": cwd_matches_root,
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
        "required_dirs": required_dir_status,
        "required_files": required_file_status,
        "optional_files": optional_file_status,
        "write_checks": write_checks,
        "summary": {
            "missing_required_dirs": [
                item["path"] for item in required_dir_status if not item["exists"] or not item["is_dir"]
            ],
            "missing_required_files": [
                item["path"] for item in required_file_status if not item["exists"] or not item["is_file"]
            ],
            "missing_optional_files": [
                item["path"] for item in optional_file_status if not item["exists"]
            ],
            "failed_write_checks": [
                item["path"] for item in write_checks if not item["writeable"]
            ],
        },
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


def build_project_preflight_markdown(data: dict) -> str:
    summary = data.get("summary", {})

    lines: list[str] = []

    lines.append("# Analista - project preflight")
    lines.append("")
    lines.append(f"- generated_at: {data.get('generated_at')}")
    lines.append(f"- status: {data.get('status')}")
    lines.append(f"- root: `{data.get('root')}`")
    lines.append(f"- cwd: `{data.get('cwd')}`")
    lines.append(f"- cwd_matches_root: {data.get('cwd_matches_root')}")
    lines.append(f"- python_executable: `{data.get('python', {}).get('executable', '')}`")
    lines.append(f"- virtual_env: `{data.get('environment', {}).get('virtual_env', '')}`")
    lines.append("")

    lines.append("## Decision gate")
    lines.append("")

    if data.get("status") == "FAIL":
        lines.append("- Estado FAIL: corregir antes de ejecutar el flujo diario.")
    elif data.get("status") == "WARN":
        lines.append("- Estado WARN: el flujo puede ejecutarse, pero hay advertencias operativas.")
    else:
        lines.append("- Estado PASS: preflight sin problemas relevantes.")

    if summary.get("missing_required_dirs"):
        lines.append("- Faltan carpetas requeridas.")
    if summary.get("missing_required_files"):
        lines.append("- Faltan scripts requeridos.")
    if summary.get("failed_write_checks"):
        lines.append("- Hay problemas de escritura.")
    if summary.get("missing_optional_files"):
        lines.append("- Hay reportes opcionales faltantes.")

    lines.append("")

    lines.append("## Required dirs")
    lines.append("")
    lines.append(
        _markdown_table(
            data.get("required_dirs", []),
            ["path", "exists", "is_dir", "modified"],
        )
    )
    lines.append("")

    lines.append("## Required files")
    lines.append("")
    lines.append(
        _markdown_table(
            data.get("required_files", []),
            ["path", "exists", "is_file", "size_bytes", "modified"],
        )
    )
    lines.append("")

    lines.append("## Optional files")
    lines.append("")
    lines.append(
        _markdown_table(
            data.get("optional_files", []),
            ["path", "exists", "is_file", "size_bytes", "modified"],
        )
    )
    lines.append("")

    lines.append("## Write checks")
    lines.append("")
    lines.append(
        _markdown_table(
            data.get("write_checks", []),
            ["path", "exists", "is_dir", "writeable", "error"],
        )
    )
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- missing_required_dirs: {len(summary.get('missing_required_dirs', []))}")
    lines.append(f"- missing_required_files: {len(summary.get('missing_required_files', []))}")
    lines.append(f"- missing_optional_files: {len(summary.get('missing_optional_files', []))}")
    lines.append(f"- failed_write_checks: {len(summary.get('failed_write_checks', []))}")

    return "\n".join(lines)


def save_project_preflight(
    root: Path = ROOT,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict:
    json_out = json_out or root / "reports" / "project_preflight_latest.json"
    markdown_out = markdown_out or root / "reports" / "project_preflight_latest.md"

    data = collect_project_preflight(root=root)

    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    json_out.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    markdown_out.write_text(
        build_project_preflight_markdown(data),
        encoding="utf-8",
    )

    return {
        "status": data["status"],
        "json_out": _relative(json_out, root),
        "markdown_out": _relative(markdown_out, root),
        "missing_required_dirs": len(data["summary"]["missing_required_dirs"]),
        "missing_required_files": len(data["summary"]["missing_required_files"]),
        "missing_optional_files": len(data["summary"]["missing_optional_files"]),
        "failed_write_checks": len(data["summary"]["failed_write_checks"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verificación previa del proyecto Analista.")
    parser.add_argument("--json-out", default="reports/project_preflight_latest.json")
    parser.add_argument("--markdown-out", default="reports/project_preflight_latest.md")
    args = parser.parse_args()

    result = save_project_preflight(
        root=ROOT,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
    )

    print("=== ANALISTA PROJECT PREFLIGHT ===")
    print(f"Status: {result['status']}")
    print(f"Missing required dirs: {result['missing_required_dirs']}")
    print(f"Missing required files: {result['missing_required_files']}")
    print(f"Missing optional files: {result['missing_optional_files']}")
    print(f"Failed write checks: {result['failed_write_checks']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")

    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
