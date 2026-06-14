from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.gui_supervised_session import NO_REAL_ORDER_NOTICE, ensure_sessions, session_status


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _contains_any(text: str, patterns: list[str]) -> list[str]:
    lower = text.lower()
    return [pattern for pattern in patterns if pattern.lower() in lower]


def _import_ok(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    try:
        spec = importlib.util.spec_from_file_location("analista_gui_supervised_session_audit_import", path)
        if spec is None or spec.loader is None:
            return False, "spec_missing"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def collect_gui_supervised_session_audit(root: Path = ROOT) -> dict:
    root = root.resolve()
    tool_path = root / "tools" / "gui_supervised_session.py"
    data_path = root / "data" / "gui_supervised_sessions.csv"
    json_path = root / "reports" / "gui_supervised_session_latest.json"
    markdown_path = root / "reports" / "gui_supervised_session_latest.md"
    text = _read_text(tool_path)

    import_ok, import_error = _import_ok(tool_path)
    data_can_be_created = False
    reports_generated = False
    try:
        ensure_sessions(data_path)
        data_can_be_created = data_path.exists()
        session_status(root=root)
        reports_generated = json_path.exists() and markdown_path.exists()
    except Exception:
        data_can_be_created = False
        reports_generated = False

    order_hits = _contains_any(text, ["send_order", "place_order", "buy_order", "sell_order"])
    api_hits = _contains_any(text, ["ibapi", "alpaca", "interactivebrokers", "robinhood"])
    shell_guardrail_ok = "shell=True" not in text
    scanner_guardrail_ok = "run_scanner" not in text
    scoring_guardrail_ok = not _contains_any(text, ["signal_classifier", "scoring/", "weights =", "threshold =", "thresholds ="])
    disabled_setup = "_".join(["BUY", "SETUP", "ACTIVE"])
    trigger_state = "_".join(["TRIGGER", "CONFIRMED"])
    signal_guardrail_ok = disabled_setup not in text and trigger_state not in text
    no_real_order_notice_present = NO_REAL_ORDER_NOTICE in text
    manual_review_only_present = "manual_review_only_confirmed" in text
    broker_guardrail_ok = not order_hits and not api_hits

    issues: list[dict] = []

    def add_issue(severity: str, source: str, message: str) -> None:
        issues.append({"severity": severity, "source": source, "message": message})

    if not tool_path.exists():
        add_issue("FAIL", "tools/gui_supervised_session.py", "tool missing")
    if not import_ok:
        add_issue("FAIL", "tools/gui_supervised_session.py", f"import failed:{import_error}")
    if not data_can_be_created:
        add_issue("FAIL", "data/gui_supervised_sessions.csv", "data file cannot be created")
    if not reports_generated:
        add_issue("FAIL", "reports", "latest supervised session reports not generated")
    if not shell_guardrail_ok:
        add_issue("FAIL", "guardrails", "shell=True detected")
    if not broker_guardrail_ok:
        add_issue("FAIL", "guardrails", "order or execution API term detected")
    if not scanner_guardrail_ok:
        add_issue("FAIL", "guardrails", "scanner execution reference detected")
    if not scoring_guardrail_ok:
        add_issue("FAIL", "guardrails", "scoring or threshold reference detected")
    if not signal_guardrail_ok:
        add_issue("FAIL", "guardrails", "disabled setup or trigger state literal detected")
    if not no_real_order_notice_present:
        add_issue("FAIL", "guardrails", "missing no-real-order notice")
    if not manual_review_only_present:
        add_issue("FAIL", "guardrails", "manual review confirmation field missing")

    failures = [item for item in issues if item["severity"] == "FAIL"]
    warnings = [item for item in issues if item["severity"] == "WARN"]
    status = "FAIL" if failures else "WARN" if warnings else "PASS"

    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool_exists": tool_path.exists(),
        "import_ok": import_ok,
        "data_file_can_be_created": data_can_be_created,
        "latest_json_generated": json_path.exists(),
        "latest_markdown_generated": markdown_path.exists(),
        "shell_guardrail_ok": shell_guardrail_ok,
        "broker_guardrail_ok": broker_guardrail_ok,
        "scanner_guardrail_ok": scanner_guardrail_ok,
        "scoring_guardrail_ok": scoring_guardrail_ok,
        "signal_guardrail_ok": signal_guardrail_ok,
        "no_real_order_notice_present": no_real_order_notice_present,
        "manual_review_only_present": manual_review_only_present,
        "order_hits": order_hits,
        "api_hits": api_hits,
        "critical_failures": len(failures),
        "warnings": len(warnings),
        "issues": issues,
        "outputs": {
            "json": "reports/gui_supervised_session_audit_latest.json",
            "markdown": "reports/gui_supervised_session_audit_latest.md",
        },
    }


def build_gui_supervised_session_audit_markdown(data: dict) -> str:
    lines = [
        "# Analista - GUI supervised session audit",
        "",
        f"- status: {data.get('status')}",
        f"- tool_exists: {data.get('tool_exists')}",
        f"- import_ok: {data.get('import_ok')}",
        f"- data_file_can_be_created: {data.get('data_file_can_be_created')}",
        f"- latest_json_generated: {data.get('latest_json_generated')}",
        f"- latest_markdown_generated: {data.get('latest_markdown_generated')}",
        f"- shell_guardrail_ok: {data.get('shell_guardrail_ok')}",
        f"- broker_guardrail_ok: {data.get('broker_guardrail_ok')}",
        f"- scanner_guardrail_ok: {data.get('scanner_guardrail_ok')}",
        f"- scoring_guardrail_ok: {data.get('scoring_guardrail_ok')}",
        f"- signal_guardrail_ok: {data.get('signal_guardrail_ok')}",
        "",
        "## Issues",
        "",
    ]
    issues = data.get("issues", [])
    if not issues:
        lines.append("- None")
    else:
        for item in issues:
            lines.append(f"- {item.get('severity')}: {item.get('source')} - {item.get('message')}")
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Manual review only.",
            "- Paper trading only.",
            "- No real order.",
            "- Session audit does not run scanner or alter scoring.",
        ]
    )
    return "\n".join(lines)


def save_gui_supervised_session_audit(
    *,
    root: Path = ROOT,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict:
    json_out = json_out or root / "reports" / "gui_supervised_session_audit_latest.json"
    markdown_out = markdown_out or root / "reports" / "gui_supervised_session_audit_latest.md"
    data = collect_gui_supervised_session_audit(root=root)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_gui_supervised_session_audit_markdown(data), encoding="utf-8")
    return {
        "status": data["status"],
        "critical_failures": data["critical_failures"],
        "warnings": data["warnings"],
        "json_out": str(json_out),
        "markdown_out": str(markdown_out),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita la herramienta de sesión GUI supervisada.")
    parser.add_argument("--json-out", default="reports/gui_supervised_session_audit_latest.json")
    parser.add_argument("--markdown-out", default="reports/gui_supervised_session_audit_latest.md")
    args = parser.parse_args()

    result = save_gui_supervised_session_audit(
        root=ROOT,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
    )
    print("=== ANALISTA GUI SUPERVISED SESSION AUDIT ===")
    print(f"Status: {result['status']}")
    print(f"Critical failures: {result['critical_failures']}")
    print(f"Warnings: {result['warnings']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")
    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
