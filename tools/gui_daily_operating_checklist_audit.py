from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.gui_daily_operating_checklist import checklist_status

DEFAULT_JSON_OUT = ROOT / "reports" / "gui_daily_operating_checklist_audit_latest.json"
DEFAULT_MARKDOWN_OUT = ROOT / "reports" / "gui_daily_operating_checklist_audit_latest.md"


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _write_reports(result: dict, json_out: Path, markdown_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_markdown(result), encoding="utf-8")


def _contains_any(text: str, needles: list[str]) -> list[str]:
    lower = text.lower()
    return [needle for needle in needles if needle.lower() in lower]


def run_audit(*, root: Path = ROOT, json_out: Path = DEFAULT_JSON_OUT, markdown_out: Path = DEFAULT_MARKDOWN_OUT) -> dict:
    if root != ROOT and json_out == DEFAULT_JSON_OUT:
        json_out = root / "reports" / "gui_daily_operating_checklist_audit_latest.json"
    if root != ROOT and markdown_out == DEFAULT_MARKDOWN_OUT:
        markdown_out = root / "reports" / "gui_daily_operating_checklist_audit_latest.md"
    tool_path = root / "tools" / "gui_daily_operating_checklist.py"
    if not tool_path.exists():
        tool_path = ROOT / "tools" / "gui_daily_operating_checklist.py"
    source = _read_text(tool_path)
    report_summary = checklist_status(root=root)

    checks: list[dict] = []

    def add(name: str, status: str, detail: str = "") -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    data_path = root / "data" / "gui_daily_operating_checklists.csv"
    json_report_path = root / "reports" / "gui_daily_operating_checklist_latest.json"
    md_report_path = root / "reports" / "gui_daily_operating_checklist_latest.md"

    tool_exists = tool_path.exists()
    data_file_can_be_created = data_path.exists()
    reports_generated = json_report_path.exists() and md_report_path.exists()

    add("tool_exists", "PASS" if tool_exists else "FAIL", str(tool_path))
    add("data_file_can_be_created", "PASS" if data_file_can_be_created else "FAIL", str(data_path))
    add("latest_reports_generated", "PASS" if reports_generated else "FAIL", "json and markdown")

    shell_hits = _contains_any(source, ["subprocess", "os.system", "shell=True", "Start-Process"])
    order_hits = _contains_any(source, ["send_order", "place_order", "buy_order", "sell_order", "execute_order"])
    api_hits = _contains_any(source, ["ibapi", "alpaca", "interactivebrokers", "robinhood"])
    scanner_hits = _contains_any(source, ["run_scanner_audited", "run_scanner(", "swing_trading_agent.cli"])
    scoring_hits = _contains_any(source, ["signal_classifier", "final_trade_score =", "thresholds =", "weights ="])
    protected_data_hits = _contains_any(source, ["data/paper_trading_journal.csv", "data/trade_outcomes.csv"])
    disabled_state_literal = "_".join(["BUY", "SETUP", "ACTIVE"]) in source
    trigger_literal = "_".join(["TRIGGER", "CONFIRMED"]) in source
    no_real_order_notice_present = "paper trading only; no real order" in source
    manual_review_only = "Manual review only" in source or "manual_review_only" in source

    add("shell_guardrail_ok", "PASS" if not shell_hits else "FAIL", ", ".join(shell_hits))
    add("order_guardrail_ok", "PASS" if not order_hits else "FAIL", ", ".join(order_hits))
    add("api_guardrail_ok", "PASS" if not api_hits else "FAIL", ", ".join(api_hits))
    add("scanner_guardrail_ok", "PASS" if not scanner_hits else "FAIL", ", ".join(scanner_hits))
    add("scoring_guardrail_ok", "PASS" if not scoring_hits else "FAIL", ", ".join(scoring_hits))
    add("protected_data_guardrail_ok", "PASS" if not protected_data_hits else "FAIL", ", ".join(protected_data_hits))
    add("disabled_state_not_enabled", "PASS" if not disabled_state_literal else "FAIL", "no active disabled setup literal")
    add("no_trigger_creation", "PASS" if not trigger_literal else "FAIL", "no trigger state literal")
    add("no_real_order_notice_present", "PASS" if no_real_order_notice_present else "FAIL")
    add("manual_review_only", "PASS" if manual_review_only else "FAIL")

    failures = [check for check in checks if check["status"] == "FAIL"]
    warnings = [check for check in checks if check["status"] == "WARN"]

    result = {
        "status": "FAIL" if failures else "WARN" if warnings else "PASS",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool_exists": tool_exists,
        "data_file_can_be_created": data_file_can_be_created,
        "latest_reports_generated": reports_generated,
        "checklist_id": report_summary.get("checklist_id", ""),
        "checklist_date": report_summary.get("checklist_date", ""),
        "pending_steps": int(report_summary.get("pending_steps", 0) or 0),
        "done_steps": int(report_summary.get("done_steps", 0) or 0),
        "blocked_steps": int(report_summary.get("blocked_steps", 0) or 0),
        "skipped_steps": int(report_summary.get("skipped_steps", 0) or 0),
        "required_pending_steps": int(report_summary.get("required_pending_steps", 0) or 0),
        "latest_result": report_summary.get("latest_result", "MISSING"),
        "no_real_order_notice_present": no_real_order_notice_present,
        "manual_review_only": manual_review_only,
        "broker_connection_detected": bool(api_hits or order_hits),
        "shell_guardrail_ok": not shell_hits,
        "order_guardrail_ok": not order_hits,
        "api_guardrail_ok": not api_hits,
        "scanner_guardrail_ok": not scanner_hits,
        "scoring_guardrail_ok": not scoring_hits,
        "protected_data_guardrail_ok": not protected_data_hits,
        "critical_failures": len(failures),
        "warnings": len(warnings),
        "checks": checks,
    }
    _write_reports(result, json_out, markdown_out)
    return result


def build_markdown(result: dict) -> str:
    lines = [
        "# Analista - GUI daily operating checklist audit",
        "",
        f"- status: {result.get('status')}",
        f"- critical_failures: {result.get('critical_failures', 0)}",
        f"- warnings: {result.get('warnings', 0)}",
        f"- checklist_id: {result.get('checklist_id', '')}",
        f"- checklist_date: {result.get('checklist_date', '')}",
        f"- pending_steps: {result.get('pending_steps', 0)}",
        f"- required_pending_steps: {result.get('required_pending_steps', 0)}",
        f"- latest_result: {result.get('latest_result', 'MISSING')}",
        f"- no_real_order_notice_present: {result.get('no_real_order_notice_present', False)}",
        f"- manual_review_only: {result.get('manual_review_only', False)}",
        "",
        "## Checks",
        "",
    ]
    for check in result.get("checks", []):
        detail = f" - {check.get('detail')}" if check.get("detail") else ""
        lines.append(f"- {check.get('status')}: {check.get('name')}{detail}")
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Paper trading only; no real order.",
            "- Manual review only.",
            "- No scanner, scoring, threshold, journal, or outcome mutation.",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita el checklist operativo diario GUI paper-only.")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    result = run_audit(json_out=Path(args.json_out), markdown_out=Path(args.markdown_out))
    print("=== ANALISTA GUI DAILY OPERATING CHECKLIST AUDIT ===")
    print(f"Status: {result.get('status')}")
    print(f"Critical failures: {result.get('critical_failures')}")
    print(f"Warnings: {result.get('warnings')}")
    print(f"JSON: {Path(args.json_out)}")
    print(f"Markdown: {Path(args.markdown_out)}")
    return 0 if result.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
