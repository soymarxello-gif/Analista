from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.gui_decision_quality_review import NOTICE, save_review

DEFAULT_JSON_OUT = ROOT / "reports" / "gui_decision_quality_audit_latest.json"
DEFAULT_MARKDOWN_OUT = ROOT / "reports" / "gui_decision_quality_audit_latest.md"


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _contains_any(text: str, needles: list[str]) -> list[str]:
    lower = text.lower()
    return [needle for needle in needles if needle.lower() in lower]


def run_audit(*, root: Path = ROOT, json_out: Path = DEFAULT_JSON_OUT, markdown_out: Path = DEFAULT_MARKDOWN_OUT) -> dict:
    if root != ROOT and json_out == DEFAULT_JSON_OUT:
        json_out = root / "reports" / "gui_decision_quality_audit_latest.json"
    if root != ROOT and markdown_out == DEFAULT_MARKDOWN_OUT:
        markdown_out = root / "reports" / "gui_decision_quality_audit_latest.md"

    tool_path = ROOT / "tools" / "gui_decision_quality_review.py"
    save_review(root=root)
    reports = root / "reports"
    json_report = reports / "gui_decision_quality_review_latest.json"
    md_report = reports / "gui_decision_quality_review_latest.md"
    csv_report = reports / "gui_decision_quality_review_latest.csv"
    source = _read_text(tool_path)

    shell_hits = _contains_any(source, ["shell=True", "subprocess", "os.system", "Start-Process"])
    order_hits = _contains_any(source, ["send_order", "place_order", "buy_order", "sell_order"])
    api_hits = _contains_any(source, ["ibapi", "alpaca", "interactivebrokers", "robinhood", "ccxt"])
    scanner_hits = _contains_any(source, ["run_scanner_audited", "run_scan(", "swing_trading_agent.cli"])
    mutation_hits = _contains_any(
        source,
        [
            "data/paper_trading_journal.csv",
            "data/trade_outcomes.csv",
            "signal_classifier",
            "thresholds =",
            "weights =",
        ],
    )
    disabled_state_literal = "_".join(["BUY", "SETUP", "ACTIVE"]) in source
    trigger_literal = "_".join(["TRIGGER", "CONFIRMED"]) in source
    notice_present = NOTICE in source
    manual_review_only = "manual_review_only" in source or "Manual review only" in source

    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    add("review_tool_exists", tool_path.exists(), str(tool_path))
    add("review_json_generated", json_report.exists(), str(json_report))
    add("review_markdown_generated", md_report.exists(), str(md_report))
    add("review_csv_generated", csv_report.exists(), str(csv_report))
    add("shell_guardrail_ok", not shell_hits, ", ".join(shell_hits))
    add("order_guardrail_ok", not order_hits, ", ".join(order_hits))
    add("api_guardrail_ok", not api_hits, ", ".join(api_hits))
    add("scanner_guardrail_ok", not scanner_hits, ", ".join(scanner_hits))
    add("protected_mutation_guardrail_ok", not mutation_hits, ", ".join(mutation_hits))
    add("disabled_state_not_enabled", not disabled_state_literal)
    add("no_trigger_creation", not trigger_literal)
    add("observational_notice_present", notice_present)
    add("manual_review_only", manual_review_only)

    failures = [item for item in checks if item["status"] == "FAIL"]
    result = {
        "status": "FAIL" if failures else "PASS",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool_exists": tool_path.exists(),
        "review_reports_generated": json_report.exists() and md_report.exists() and csv_report.exists(),
        "critical_failures": len(failures),
        "warnings": 0,
        "observational_notice_present": notice_present,
        "manual_review_only": manual_review_only,
        "broker_connection_detected": bool(order_hits or api_hits),
        "shell_guardrail_ok": not shell_hits,
        "order_guardrail_ok": not order_hits,
        "api_guardrail_ok": not api_hits,
        "scanner_guardrail_ok": not scanner_hits,
        "protected_mutation_guardrail_ok": not mutation_hits,
        "checks": checks,
    }
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_markdown(result), encoding="utf-8")
    return result


def build_markdown(data: dict) -> str:
    lines = [
        "# Analista - GUI decision quality audit",
        "",
        f"- status: {data.get('status')}",
        f"- critical_failures: {data.get('critical_failures', 0)}",
        f"- warnings: {data.get('warnings', 0)}",
        f"- observational_notice_present: {data.get('observational_notice_present', False)}",
        f"- manual_review_only: {data.get('manual_review_only', False)}",
        "",
        "## Checks",
        "",
    ]
    for check in data.get("checks", []) or []:
        detail = f" - {check.get('detail')}" if check.get("detail") else ""
        lines.append(f"- {check.get('status')}: {check.get('name')}{detail}")
    lines.extend(["", "## Guardrails", "", f"- {NOTICE}"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita GUI decision quality review.")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()
    result = run_audit(json_out=Path(args.json_out), markdown_out=Path(args.markdown_out))
    print("=== ANALISTA GUI DECISION QUALITY AUDIT ===")
    print(f"Status: {result.get('status')}")
    print(f"Critical failures: {result.get('critical_failures')}")
    print(f"Warnings: {result.get('warnings')}")
    print(f"JSON: {Path(args.json_out)}")
    print(f"Markdown: {Path(args.markdown_out)}")
    return 0 if result.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
