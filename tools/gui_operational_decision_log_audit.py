from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.gui_operational_decision_log import NO_REAL_ORDER_NOTICE, save_summary
from tools.gui_post_session_review import save_review


DEFAULT_JSON_OUT = ROOT / "reports" / "gui_operational_decision_log_audit_latest.json"
DEFAULT_MARKDOWN_OUT = ROOT / "reports" / "gui_operational_decision_log_audit_latest.md"


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
        json_out = root / "reports" / "gui_operational_decision_log_audit_latest.json"
    if root != ROOT and markdown_out == DEFAULT_MARKDOWN_OUT:
        markdown_out = root / "reports" / "gui_operational_decision_log_audit_latest.md"

    log_tool = ROOT / "tools" / "gui_operational_decision_log.py"
    review_tool = ROOT / "tools" / "gui_post_session_review.py"
    save_summary(root=root)
    save_review(root=root)

    data_path = root / "data" / "gui_operational_decisions.csv"
    log_json = root / "reports" / "gui_operational_decision_log_latest.json"
    log_md = root / "reports" / "gui_operational_decision_log_latest.md"
    review_json = root / "reports" / "gui_post_session_review_latest.json"
    review_md = root / "reports" / "gui_post_session_review_latest.md"

    source = "\n".join([_read_text(log_tool), _read_text(review_tool)])
    order_hits = _contains_any(source, ["send_order", "place_order", "buy_order", "sell_order"])
    api_hits = _contains_any(source, ["ibapi", "alpaca", "interactivebrokers", "robinhood", "ccxt"])
    shell_hits = _contains_any(source, ["shell=True", "subprocess", "os.system", "Start-Process"])
    scanner_hits = _contains_any(source, ["run_scanner_audited", "run_scan(", "swing_trading_agent.cli"])
    mutation_hits = _contains_any(
        source,
        [
            "data/trade_outcomes.csv",
            "data/paper_trading_journal.csv",
            "to_csv(root / \"data\" / \"paper_trading_journal.csv\"",
            "to_csv(root / \"data\" / \"trade_outcomes.csv\"",
            "thresholds =",
            "weights =",
            "signal_classifier",
        ],
    )
    disabled_state_literal = "_".join(["BUY", "SETUP", "ACTIVE"]) in source
    trigger_literal = "_".join(["TRIGGER", "CONFIRMED"]) in source
    notice_present = NO_REAL_ORDER_NOTICE in source
    manual_review_only = "Manual review only" in source or "manual_review_only" in source

    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    add("decision_log_tool_exists", log_tool.exists(), str(log_tool))
    add("post_session_review_tool_exists", review_tool.exists(), str(review_tool))
    add("data_file_can_be_created", data_path.exists(), str(data_path))
    add("decision_log_json_generated", log_json.exists(), str(log_json))
    add("decision_log_markdown_generated", log_md.exists(), str(log_md))
    add("post_session_json_generated", review_json.exists(), str(review_json))
    add("post_session_markdown_generated", review_md.exists(), str(review_md))
    add("shell_guardrail_ok", not shell_hits, ", ".join(shell_hits))
    add("order_guardrail_ok", not order_hits, ", ".join(order_hits))
    add("api_guardrail_ok", not api_hits, ", ".join(api_hits))
    add("scanner_guardrail_ok", not scanner_hits, ", ".join(scanner_hits))
    add("protected_mutation_guardrail_ok", not mutation_hits, ", ".join(mutation_hits))
    add("disabled_state_not_enabled", not disabled_state_literal)
    add("no_trigger_creation", not trigger_literal)
    add("no_real_order_notice_present", notice_present)
    add("manual_review_only", manual_review_only)

    failures = [item for item in checks if item["status"] == "FAIL"]
    result = {
        "status": "FAIL" if failures else "PASS",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool_exists": log_tool.exists(),
        "post_session_review_exists": review_tool.exists(),
        "data_file_can_be_created": data_path.exists(),
        "decision_log_reports_generated": log_json.exists() and log_md.exists(),
        "post_session_reports_generated": review_json.exists() and review_md.exists(),
        "critical_failures": len(failures),
        "warnings": 0,
        "no_real_order_notice_present": notice_present,
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
        "# Analista - GUI operational decision log audit",
        "",
        f"- status: {data.get('status')}",
        f"- critical_failures: {data.get('critical_failures', 0)}",
        f"- warnings: {data.get('warnings', 0)}",
        f"- no_real_order_notice_present: {data.get('no_real_order_notice_present', False)}",
        f"- manual_review_only: {data.get('manual_review_only', False)}",
        "",
        "## Checks",
        "",
    ]
    for check in data.get("checks", []) or []:
        detail = f" - {check.get('detail')}" if check.get("detail") else ""
        lines.append(f"- {check.get('status')}: {check.get('name')}{detail}")
    lines.extend(["", "## Guardrails", "", "- Manual review only.", "- Paper trading only.", "- No real order."])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita bitácora operativa GUI paper-only.")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()
    result = run_audit(json_out=Path(args.json_out), markdown_out=Path(args.markdown_out))
    print("=== ANALISTA GUI OPERATIONAL DECISION LOG AUDIT ===")
    print(f"Status: {result.get('status')}")
    print(f"Critical failures: {result.get('critical_failures')}")
    print(f"Warnings: {result.get('warnings')}")
    print(f"JSON: {Path(args.json_out)}")
    print(f"Markdown: {Path(args.markdown_out)}")
    return 0 if result.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
