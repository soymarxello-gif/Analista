from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


CRITICAL_DOCS = [
    "docs/OPERATING_MANUAL.md",
    "docs/DAILY_WORKFLOW.md",
    "docs/REPORTS_REFERENCE.md",
    "docs/SAFETY_RULES.md",
    "docs/CALIBRATION_GUIDE.md",
]

CRITICAL_TOOLS = [
    "tools/daily_validation.py",
    "tools/live_quote_recheck.py",
    "tools/trade_decision_checklist.py",
    "tools/trade_candidate_cards.py",
    "tools/trade_score_calibration.py",
    "tools/calibration_recommendations.py",
    "tools/daily_operator_index.py",
    "tools/daily_run_manifest.py",
    "tools/project_preflight.py",
    "tools/report_consistency_audit.py",
]

CRITICAL_TESTS = [
    "tests/test_live_quote_recheck_phase33b.py",
    "tests/test_options_flow_phase34a.py",
    "tests/test_options_scoring_phase34b.py",
    "tests/test_trade_decision_checklist_phase35a.py",
    "tests/test_trade_candidate_cards_phase35b.py",
    "tests/test_trade_score_calibration_phase36a.py",
    "tests/test_calibration_recommendations_phase36b.py",
    "tests/test_docs_phase37a.py",
]

OPTIONAL_REPORTS = [
    "reports/daily_validation_summary.txt",
    "reports/daily_operator_index.md",
    "reports/daily_quality_gate_latest.json",
    "reports/daily_quality_gate_latest.md",
    "reports/daily_run_manifest_latest.json",
    "reports/daily_run_manifest_latest.md",
    "reports/project_preflight_latest.json",
    "reports/project_preflight_latest.md",
    "reports/encoding_audit_latest.json",
    "reports/encoding_audit_latest.md",
    "reports/latest_scan_audited.csv",
    "reports/latest_scan_audited.json",
    "reports/manual_review_latest.csv",
    "reports/manual_review_latest.md",
    "reports/manual_review_top.csv",
    "reports/manual_review_top.md",
    "reports/live_quote_recheck_latest.csv",
    "reports/live_quote_recheck_latest.md",
    "reports/live_quote_recheck_latest.json",
    "reports/trade_decision_checklist_latest.csv",
    "reports/trade_decision_checklist_latest.md",
    "reports/trade_decision_checklist_latest.json",
    "reports/trade_candidate_cards_latest.md",
    "reports/trade_candidate_cards_latest.json",
    "reports/trade_score_calibration_latest.csv",
    "reports/trade_score_calibration_latest.json",
    "reports/trade_score_calibration_latest.md",
    "reports/calibration_recommendations_latest.md",
    "reports/calibration_recommendations_latest.json",
    "reports/trade_outcome_analytics_latest.csv",
    "reports/trade_outcome_analytics_latest.md",
    "reports/reports_cleanup_latest.json",
    "reports/reports_cleanup_latest.md",
]

RECENT_DAILY_VALIDATION_STEPS = [
    "live_quote_recheck",
    "trade_decision_checklist",
    "trade_candidate_cards",
    "trade_score_calibration",
    "calibration_recommendations",
]

OPERATOR_INDEX_REPORT_REFERENCES = [
    "reports/live_quote_recheck_latest.md",
    "reports/trade_decision_checklist_latest.md",
    "reports/trade_candidate_cards_latest.md",
    "reports/trade_score_calibration_latest.md",
    "reports/calibration_recommendations_latest.md",
]

MANIFEST_REFERENCES = [
    "tools/live_quote_recheck.py",
    "tools/trade_decision_checklist.py",
    "tools/trade_candidate_cards.py",
    "tools/trade_score_calibration.py",
    "tools/calibration_recommendations.py",
    "reports/live_quote_recheck_latest.json",
    "reports/trade_decision_checklist_latest.json",
    "reports/trade_candidate_cards_latest.json",
    "reports/trade_score_calibration_latest.json",
    "reports/calibration_recommendations_latest.json",
]

ALLOWED_DISABLED_SIGNAL_PATHS = {
    "scoring/signal_classifier.py",
    "engine/scanner_engine.py",
    "engine/scan_audit_engine.py",
    "scoring/operational_priority.py",
    "tools/project_consistency_audit.py",
    "validate_latest_scan_p0.py",
}


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _file_status(root: Path, path: str) -> dict:
    file_path = root / path
    exists = file_path.exists()
    return {
        "path": path,
        "exists": exists,
        "size_bytes": file_path.stat().st_size if exists and file_path.is_file() else 0,
        "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(timespec="seconds")
        if exists
        else "",
    }


def _add_issue(items: list[dict], severity: str, source: str, message: str) -> None:
    items.append(
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


def _check_required_files(root: Path, issues: list[dict], label: str, paths: list[str]) -> list[dict]:
    statuses = [_file_status(root, path) for path in paths]
    for item in statuses:
        if not item["exists"]:
            _add_issue(issues, "FAIL", label, f"Missing critical file: {item['path']}")
    return statuses


def _check_optional_reports(root: Path, issues: list[dict]) -> list[dict]:
    statuses = [_file_status(root, path) for path in OPTIONAL_REPORTS]
    for item in statuses:
        if not item["exists"]:
            _add_issue(issues, "WARN", "optional_reports", f"Missing generated report: {item['path']}")
    return statuses


def _check_gitignore(root: Path, issues: list[dict]) -> dict:
    text = _read_text(root / ".gitignore")
    checks = {
        "reports_latest": "reports/*_latest.*" in text
        or all(pattern in text for pattern in ["reports/*_latest.csv", "reports/*_latest.json", "reports/*_latest.md"]),
        "reports_generated": "reports/*.csv" in text and "reports/*.json" in text,
        "cache": "cache/" in text,
        "tmp": "reports/tmp/" in text or "tmp/" in text,
        "zip": "*.zip" in text,
        "pytest_cache": ".pytest_cache/" in text,
    }

    if not text:
        _add_issue(issues, "FAIL", ".gitignore", ".gitignore is missing or unreadable.")
        return checks

    for key, passed in checks.items():
        if not passed:
            severity = "WARN" if key == "reports_latest" else "FAIL"
            _add_issue(issues, severity, ".gitignore", f"Missing ignore rule for {key}.")

    return checks


def _check_disabled_signal_usage(root: Path, issues: list[dict]) -> dict:
    disabled_signal = "_".join(["BUY", "SETUP", "ACTIVE"])
    findings: list[str] = []

    for path in root.rglob("*.py"):
        rel = _relative(path, root)
        if rel.startswith(
            (
                "tests/",
                "reports/",
                "cache/",
                ".venv/",
                ".git/",
                "__pycache__/",
                ".pytest_cache/",
            )
        ):
            continue
        text = _read_text(path)
        if disabled_signal in text and rel not in ALLOWED_DISABLED_SIGNAL_PATHS:
            findings.append(rel)

    for rel in findings:
        _add_issue(
            issues,
            "FAIL",
            "disabled_signal",
            f"Disabled signal literal found in active code: {rel}",
        )

    return {
        "disabled_signal": disabled_signal,
        "active_code_findings": findings,
        "allowed_paths": sorted(ALLOWED_DISABLED_SIGNAL_PATHS),
    }


def _check_signal_classifier_guard(root: Path, issues: list[dict]) -> dict:
    path = root / "scoring" / "signal_classifier.py"
    text = _read_text(path)
    checks = {
        "file_exists": path.exists(),
        "trigger_guard_present": "TRIGGER_CONFIRMED" in text,
        "quote_status_checked": "quote_status" in text and "VALID" in text,
        "execution_quality_checked": "execution_quote_quality" in text and "HIGH" in text,
        "downgrade_to_watchlist": "WATCHLIST" in text,
    }

    if not checks["file_exists"]:
        _add_issue(issues, "FAIL", "signal_classifier", "Missing scoring/signal_classifier.py")
        return checks

    if not checks["trigger_guard_present"]:
        _add_issue(issues, "FAIL", "signal_classifier", "Missing trigger-confirmed guard.")
    if not checks["quote_status_checked"]:
        _add_issue(
            issues,
            "FAIL",
            "signal_classifier",
            "No quote_status VALID condition found for trigger-confirmed state.",
        )
    if not checks["execution_quality_checked"]:
        _add_issue(
            issues,
            "FAIL",
            "signal_classifier",
            "No execution_quote_quality HIGH condition found for trigger-confirmed state.",
        )
    if not checks["downgrade_to_watchlist"]:
        _add_issue(
            issues,
            "FAIL",
            "signal_classifier",
            "No safe downgrade state found for unsafe trigger-confirmed state.",
        )

    return checks


def _check_text_references(
    root: Path,
    issues: list[dict],
    path: str,
    required_tokens: list[str],
    *,
    severity: str = "FAIL",
) -> dict:
    text = _read_text(root / path)
    checks = {token: token in text for token in required_tokens}
    if not text:
        _add_issue(issues, "FAIL", path, f"{path} is missing or unreadable.")
        return checks
    for token, passed in checks.items():
        if not passed:
            _add_issue(issues, severity, path, f"Missing reference: {token}")
    return checks


def _check_structural_report_status(root: Path, issues: list[dict], report: str) -> dict:
    data = _load_json(root / report)
    status = str(data.get("status", "MISSING")).upper() if data else "MISSING"
    if status == "FAIL":
        _add_issue(issues, "FAIL", report, f"{report} status is FAIL.")
    elif status == "MISSING":
        _add_issue(issues, "WARN", report, f"{report} is not available.")
    return {"path": report, "status": status}


def _run_git(root: Path, args: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            text=True,
            capture_output=True,
            shell=False,
            timeout=10,
        )
    except Exception as exc:
        return -1, str(exc)
    return result.returncode, result.stdout.strip()


def _check_tracked_generated_reports(root: Path, issues: list[dict]) -> dict:
    git_dir = root / ".git"
    if not git_dir.exists():
        return {"available": False, "tracked_generated_reports": []}

    returncode, stdout = _run_git(root, ["ls-files", "reports"])
    if returncode != 0:
        _add_issue(issues, "WARN", "git", "Could not inspect tracked report files.")
        return {"available": False, "tracked_generated_reports": []}

    tracked = [
        line.strip()
        for line in stdout.splitlines()
        if line.strip()
        and (
            line.strip().startswith("reports/")
            and (
                "_latest." in line
                or line.strip().endswith((".csv", ".json", ".md", ".txt"))
                or "/audits/" in line
                or "/history/" in line
            )
        )
    ]

    if tracked:
        _add_issue(
            issues,
            "WARN",
            "git",
            "Generated report files appear to be tracked: " + ", ".join(tracked[:20]),
        )

    return {"available": True, "tracked_generated_reports": tracked}


def collect_release_readiness_audit(root: Path = ROOT) -> dict:
    root = root.resolve()
    issues: list[dict] = []

    docs = _check_required_files(root, issues, "docs", CRITICAL_DOCS)
    tools = _check_required_files(root, issues, "tools", CRITICAL_TOOLS)
    tests = _check_required_files(root, issues, "tests", CRITICAL_TESTS)
    optional_reports = _check_optional_reports(root, issues)

    checks = {
        "gitignore": _check_gitignore(root, issues),
        "disabled_signal_usage": _check_disabled_signal_usage(root, issues),
        "signal_classifier_guard": _check_signal_classifier_guard(root, issues),
        "daily_validation_steps": _check_text_references(
            root,
            issues,
            "tools/daily_validation.py",
            RECENT_DAILY_VALIDATION_STEPS,
        ),
        "daily_operator_index_reports": _check_text_references(
            root,
            issues,
            "tools/daily_operator_index.py",
            OPERATOR_INDEX_REPORT_REFERENCES,
        ),
        "daily_run_manifest_outputs": _check_text_references(
            root,
            issues,
            "tools/daily_run_manifest.py",
            MANIFEST_REFERENCES,
        ),
        "project_preflight_status": _check_structural_report_status(
            root,
            issues,
            "reports/project_preflight_latest.json",
        ),
        "report_consistency_status": _check_structural_report_status(
            root,
            issues,
            "reports/report_consistency_latest.json",
        ),
        "tracked_generated_reports": _check_tracked_generated_reports(root, issues),
    }

    critical_failures = [
        item for item in issues if str(item.get("severity", "")).upper() == "FAIL"
    ]
    warnings = [
        item for item in issues if str(item.get("severity", "")).upper() == "WARN"
    ]
    status = _derive_status(issues)

    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": root.as_posix(),
        "critical_failures": len(critical_failures),
        "warnings": len(warnings),
        "critical_failure_items": critical_failures,
        "warning_items": warnings,
        "issues": issues,
        "checks": checks,
        "files": {
            "docs": docs,
            "tools": tools,
            "tests": tests,
            "optional_reports": optional_reports,
        },
        "outputs": {
            "markdown": "reports/release_readiness_latest.md",
            "json": "reports/release_readiness_latest.json",
        },
    }


def _markdown_table(items: list[dict], columns: list[str]) -> str:
    if not items:
        return "_Sin datos._"
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for item in items:
        values = [str(item.get(col, "")).replace("\n", " ").replace("|", "\\|") for col in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def build_release_readiness_audit_markdown(data: dict) -> str:
    lines: list[str] = []
    lines.append("# Analista - release readiness audit")
    lines.append("")
    lines.append(f"- generated_at: {data.get('generated_at')}")
    lines.append(f"- status: {data.get('status')}")
    lines.append(f"- critical_failures: {data.get('critical_failures')}")
    lines.append(f"- warnings: {data.get('warnings')}")
    lines.append("- scope: structural release audit; no trading logic changes.")
    lines.append("")

    lines.append("## Decision Gate")
    lines.append("")
    if data.get("status") == "FAIL":
        lines.append("- FAIL: do not close the release until critical failures are fixed.")
    elif data.get("status") == "WARN":
        lines.append("- WARN: code/docs/tests are structurally usable, but warnings require review.")
    else:
        lines.append("- PASS: release readiness checks passed.")
    lines.append("")

    lines.append("## Critical Failures")
    lines.append("")
    lines.append(_markdown_table(data.get("critical_failure_items", []), ["severity", "source", "message"]))
    lines.append("")

    lines.append("## Warnings")
    lines.append("")
    lines.append(_markdown_table(data.get("warning_items", []), ["severity", "source", "message"]))
    lines.append("")

    lines.append("## Required Files")
    lines.append("")
    for group in ["docs", "tools", "tests"]:
        lines.append(f"### {group}")
        lines.append("")
        lines.append(_markdown_table(data.get("files", {}).get(group, []), ["path", "exists", "size_bytes", "modified"]))
        lines.append("")

    lines.append("## Optional Generated Reports")
    lines.append("")
    lines.append(
        _markdown_table(
            data.get("files", {}).get("optional_reports", []),
            ["path", "exists", "size_bytes", "modified"],
        )
    )
    lines.append("")

    lines.append("## Guardrails")
    lines.append("")
    lines.append("- No automatic trading is enabled.")
    lines.append("- Trigger-confirmed state remains guarded by quote and execution quality.")
    lines.append("- Calibration remains observational.")

    return "\n".join(lines)


def save_release_readiness_audit(
    *,
    root: Path = ROOT,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict:
    json_out = json_out or root / "reports" / "release_readiness_latest.json"
    markdown_out = markdown_out or root / "reports" / "release_readiness_latest.md"

    data = collect_release_readiness_audit(root=root)

    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    markdown_out.write_text(build_release_readiness_audit_markdown(data), encoding="utf-8")

    return {
        "status": data["status"],
        "critical_failures": data["critical_failures"],
        "warnings": data["warnings"],
        "json_out": _relative(json_out, root),
        "markdown_out": _relative(markdown_out, root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita release readiness de Analista.")
    parser.add_argument("--json-out", default="reports/release_readiness_latest.json")
    parser.add_argument("--markdown-out", default="reports/release_readiness_latest.md")
    args = parser.parse_args()

    result = save_release_readiness_audit(
        root=ROOT,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
    )

    print("=== ANALISTA RELEASE READINESS AUDIT ===")
    print(f"Status: {result['status']}")
    print(f"Critical failures: {result['critical_failures']}")
    print(f"Warnings: {result['warnings']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")

    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
