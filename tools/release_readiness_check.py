from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


CRITICAL_FILES = [
    "tools/daily_validation.py",
    "tools/daily_operator_index.py",
    "tools/daily_quality_gate.py",
    "tools/daily_run_manifest.py",
    "tools/encoding_audit.py",
    "tools/project_preflight.py",
    "tools/reports_cleanup.py",
    "reports/daily_validation_summary.txt",
    "reports/daily_quality_gate_latest.json",
    "reports/daily_quality_gate_latest.md",
    "reports/daily_operator_index.md",
    "reports/daily_run_manifest_latest.json",
    "reports/daily_run_manifest_latest.md",
    "reports/encoding_audit_latest.json",
    "reports/encoding_audit_latest.md",
    "reports/project_preflight_latest.json",
    "reports/project_preflight_latest.md",
    "reports/latest_scan_audited.csv",
    "reports/manual_review_latest.csv",
    "reports/manual_review_top.csv",
]


def _relative(path: Path, root: Path = ROOT) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _file_status(path: Path, root: Path = ROOT) -> dict:
    exists = path.exists()
    is_file = path.is_file() if exists else False

    return {
        "path": _relative(path, root),
        "exists": exists,
        "is_file": is_file,
        "size_bytes": path.stat().st_size if exists and is_file else 0,
        "modified": (
            datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
            if exists
            else ""
        ),
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


def _run_command(cmd: list[str], timeout_seconds: int, root: Path) -> dict:
    started_at = datetime.now().isoformat(timespec="seconds")

    try:
        completed = subprocess.run(
            cmd,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )

        return {
            "cmd": cmd,
            "started_at": started_at,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "timeout_seconds": timeout_seconds,
            "timed_out": False,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "passed": completed.returncode == 0,
        }

    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": cmd,
            "started_at": started_at,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "timeout_seconds": timeout_seconds,
            "timed_out": True,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "passed": False,
        }


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


def _check_daily_operator_index(text: str, issues: list[dict]) -> dict:
    checks = {
        "contains_daily_quality_gate_section": "## Daily quality gate" in text,
        "contains_quality_gate_file": "reports/daily_quality_gate_latest.md" in text,
        "contains_manual_review_allowed": "manual_review_allowed" in text,
        "contains_manual_review_mode": "manual_review_mode" in text,
    }

    for key, passed in checks.items():
        if not passed:
            _add_issue(
                issues,
                "FAIL",
                "daily_operator_index.md",
                f"Falta condición requerida en daily_operator_index: {key}.",
            )

    return checks


def collect_release_readiness(
    root: Path = ROOT,
    run_pytest: bool = True,
    run_project_consistency: bool = True,
    pytest_timeout_seconds: int = 300,
    consistency_timeout_seconds: int = 120,
) -> dict:
    root = root.resolve()
    reports = root / "reports"

    issues: list[dict] = []

    file_statuses = [_file_status(root / path, root=root) for path in CRITICAL_FILES]

    for item in file_statuses:
        if not item["exists"]:
            _add_issue(
                issues,
                "FAIL",
                item["path"],
                "Falta archivo crítico requerido para declarar release listo.",
            )

    daily_summary_text, daily_summary_error = _read_text(
        reports / "daily_validation_summary.txt"
    )
    daily_validation_status = (
        _parse_status_from_text(daily_summary_text)
        if not daily_summary_error
        else "MISSING"
    )

    if daily_validation_status == "FAIL":
        _add_issue(
            issues,
            "FAIL",
            "daily_validation_summary.txt",
            "daily_validation está en FAIL.",
        )
    elif daily_validation_status == "WARN":
        _add_issue(
            issues,
            "WARN",
            "daily_validation_summary.txt",
            "daily_validation está en WARN; release posible con advertencia documentada.",
        )
    elif daily_validation_status not in {"PASS", "WARN", "FAIL"}:
        _add_issue(
            issues,
            "FAIL",
            "daily_validation_summary.txt",
            f"daily_validation tiene estado desconocido: {daily_validation_status}.",
        )

    quality_gate_json, quality_gate_error = _load_json(
        reports / "daily_quality_gate_latest.json"
    )

    quality_gate_status = (
        str(quality_gate_json.get("status", "UNKNOWN")).upper()
        if not quality_gate_error
        else "MISSING"
    )
    manual_review_allowed = bool(quality_gate_json.get("manual_review_allowed", False))
    manual_review_mode = str(
        quality_gate_json.get("manual_review_mode", "UNKNOWN")
    ).upper()

    if quality_gate_error:
        _add_issue(
            issues,
            "FAIL",
            "daily_quality_gate_latest.json",
            f"No se pudo leer quality gate: {quality_gate_error}.",
        )
    elif quality_gate_status == "FAIL":
        _add_issue(
            issues,
            "FAIL",
            "daily_quality_gate_latest.json",
            "daily_quality_gate está en FAIL.",
        )
    elif quality_gate_status == "WARN":
        _add_issue(
            issues,
            "WARN",
            "daily_quality_gate_latest.json",
            "daily_quality_gate está en WARN; release posible con validación reforzada.",
        )
    elif quality_gate_status != "PASS":
        _add_issue(
            issues,
            "FAIL",
            "daily_quality_gate_latest.json",
            f"daily_quality_gate tiene estado desconocido: {quality_gate_status}.",
        )

    if not manual_review_allowed:
        _add_issue(
            issues,
            "FAIL",
            "daily_quality_gate_latest.json",
            "manual_review_allowed es False.",
        )

    encoding_json, encoding_error = _load_json(reports / "encoding_audit_latest.json")
    encoding_status = (
        str(encoding_json.get("status", "UNKNOWN")).upper()
        if not encoding_error
        else "MISSING"
    )

    if encoding_error:
        _add_issue(
            issues,
            "WARN",
            "encoding_audit_latest.json",
            f"No se pudo leer encoding audit: {encoding_error}.",
        )
    elif encoding_status == "FAIL":
        _add_issue(
            issues,
            "WARN",
            "encoding_audit_latest.json",
            "encoding_audit está en FAIL; revisar antes de publicar reportes.",
        )

    operator_index_text, operator_index_error = _read_text(
        reports / "daily_operator_index.md"
    )

    operator_index_checks = {}

    if operator_index_error:
        _add_issue(
            issues,
            "FAIL",
            "daily_operator_index.md",
            f"No se pudo leer daily_operator_index.md: {operator_index_error}.",
        )
    else:
        operator_index_checks = _check_daily_operator_index(operator_index_text, issues)

    command_results = {}

    if run_project_consistency:
        command_results["project_consistency_audit"] = _run_command(
            [sys.executable, "tools/project_consistency_audit.py"],
            timeout_seconds=consistency_timeout_seconds,
            root=root,
        )

        if not command_results["project_consistency_audit"]["passed"]:
            _add_issue(
                issues,
                "FAIL",
                "project_consistency_audit",
                "project_consistency_audit no pasó.",
            )
    else:
        command_results["project_consistency_audit"] = {
            "skipped": True,
            "passed": None,
        }
        _add_issue(
            issues,
            "WARN",
            "project_consistency_audit",
            "project_consistency_audit fue omitido.",
        )

    if run_pytest:
        command_results["pytest"] = _run_command(
            [sys.executable, "-m", "pytest", "-q"],
            timeout_seconds=pytest_timeout_seconds,
            root=root,
        )

        if not command_results["pytest"]["passed"]:
            _add_issue(
                issues,
                "FAIL",
                "pytest",
                "pytest general no pasó.",
            )
    else:
        command_results["pytest"] = {
            "skipped": True,
            "passed": None,
        }
        _add_issue(
            issues,
            "WARN",
            "pytest",
            "pytest general fue omitido.",
        )

    status = _derive_status(issues)

    return {
        "status": status,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": root.as_posix(),
        "release_ready": status != "FAIL",
        "release_mode": "BLOCKED" if status == "FAIL" else "READY_WITH_WARNINGS" if status == "WARN" else "READY",
        "components": {
            "daily_validation": {
                "status": daily_validation_status,
                "path": "reports/daily_validation_summary.txt",
                "error": daily_summary_error,
            },
            "daily_quality_gate": {
                "status": quality_gate_status,
                "manual_review_allowed": manual_review_allowed,
                "manual_review_mode": manual_review_mode,
                "path": "reports/daily_quality_gate_latest.json",
                "error": quality_gate_error,
            },
            "encoding_audit": {
                "status": encoding_status,
                "path": "reports/encoding_audit_latest.json",
                "error": encoding_error,
            },
        },
        "operator_index_checks": operator_index_checks,
        "command_results": command_results,
        "issues": issues,
        "files": file_statuses,
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


def build_release_readiness_markdown(data: dict) -> str:
    components = data.get("components", {})
    command_results = data.get("command_results", {})
    issues = data.get("issues", [])

    lines: list[str] = []

    lines.append("# Analista - release readiness check")
    lines.append("")
    lines.append(f"- generated_at: {data.get('generated_at')}")
    lines.append(f"- status: {data.get('status')}")
    lines.append(f"- release_ready: {data.get('release_ready')}")
    lines.append(f"- release_mode: {data.get('release_mode')}")
    lines.append("")

    lines.append("## Decision gate")
    lines.append("")

    if data.get("status") == "FAIL":
        lines.append("- Estado FAIL: no declarar release listo hasta corregir errores.")
    elif data.get("status") == "WARN":
        lines.append("- Estado WARN: release posible con advertencias documentadas.")
    else:
        lines.append("- Estado PASS: release listo.")

    lines.append("")

    lines.append("## Componentes")
    lines.append("")
    for name, component in components.items():
        fields = ", ".join(f"{key}={value}" for key, value in component.items())
        lines.append(f"- {name}: {fields}")
    lines.append("")

    lines.append("## Comandos de validación")
    lines.append("")

    for name, result in command_results.items():
        lines.append(f"### {name}")
        lines.append("")
        lines.append(f"- passed: {result.get('passed')}")
        lines.append(f"- returncode: {result.get('returncode')}")
        lines.append(f"- timed_out: {result.get('timed_out')}")
        lines.append(f"- timeout_seconds: {result.get('timeout_seconds')}")
        lines.append("")

        stdout = str(result.get("stdout", "") or "").strip()
        stderr = str(result.get("stderr", "") or "").strip()

        if stdout:
            lines.append("stdout:")
            lines.append("```text")
            lines.append(stdout[-4000:])
            lines.append("```")
            lines.append("")

        if stderr:
            lines.append("stderr:")
            lines.append("```text")
            lines.append(stderr[-4000:])
            lines.append("```")
            lines.append("")

    lines.append("## Operator index checks")
    lines.append("")
    for key, value in data.get("operator_index_checks", {}).items():
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
            data.get("files", []),
            ["path", "exists", "size_bytes", "modified"],
        )
    )

    return "\n".join(lines)


def save_release_readiness(
    root: Path = ROOT,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
    run_pytest: bool = True,
    run_project_consistency: bool = True,
    pytest_timeout_seconds: int = 300,
    consistency_timeout_seconds: int = 120,
) -> dict:
    json_out = json_out or root / "reports" / "release_readiness_latest.json"
    markdown_out = markdown_out or root / "reports" / "release_readiness_latest.md"

    data = collect_release_readiness(
        root=root,
        run_pytest=run_pytest,
        run_project_consistency=run_project_consistency,
        pytest_timeout_seconds=pytest_timeout_seconds,
        consistency_timeout_seconds=consistency_timeout_seconds,
    )

    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    json_out.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    markdown_out.write_text(
        build_release_readiness_markdown(data),
        encoding="utf-8",
    )

    return {
        "status": data["status"],
        "release_ready": data["release_ready"],
        "release_mode": data["release_mode"],
        "json_out": _relative(json_out, root),
        "markdown_out": _relative(markdown_out, root),
        "issue_count": len(data["issues"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Chequea preparación de release profesional.")
    parser.add_argument("--json-out", default="reports/release_readiness_latest.json")
    parser.add_argument("--markdown-out", default="reports/release_readiness_latest.md")
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--skip-project-consistency", action="store_true")
    parser.add_argument("--pytest-timeout-seconds", type=int, default=300)
    parser.add_argument("--consistency-timeout-seconds", type=int, default=120)
    args = parser.parse_args()

    result = save_release_readiness(
        root=ROOT,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
        run_pytest=not args.skip_pytest,
        run_project_consistency=not args.skip_project_consistency,
        pytest_timeout_seconds=args.pytest_timeout_seconds,
        consistency_timeout_seconds=args.consistency_timeout_seconds,
    )

    print("=== ANALISTA RELEASE READINESS CHECK ===")
    print(f"Status: {result['status']}")
    print(f"Release ready: {result['release_ready']}")
    print(f"Release mode: {result['release_mode']}")
    print(f"Issues: {result['issue_count']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")

    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())