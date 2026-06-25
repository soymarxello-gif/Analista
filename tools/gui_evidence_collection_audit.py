from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.gui_evidence_collection_window import MANUAL_NOTICE, NOTICE, save_window

DEFAULT_JSON_OUT = ROOT / "reports" / "gui_evidence_collection_audit_latest.json"
DEFAULT_MARKDOWN_OUT = ROOT / "reports" / "gui_evidence_collection_audit_latest.md"


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() and path.is_file() else ""


def _contains_any(text: str, needles: list[str]) -> list[str]:
    lower = text.lower()
    return [needle for needle in needles if needle.lower() in lower]


def _guard_terms() -> dict[str, list[str]]:
    return {
        "shell": ["shell=True", "subprocess", "os.system", "Start-Process"],
        "order": ["send_" + "order", "place_" + "order", "buy_" + "order", "sell_" + "order"],
        "api": ["ibapi", "al" + "paca", "interactive" + "brokers", "robinhood", "ccxt"],
        "scanner": ["run_scanner_audited", "run_scan(", "swing_trading_agent.cli"],
        "protected_mutation": [
            "data/paper_trading_journal.csv\"",
            "data/trade_outcomes.csv\"",
            "signal_classifier",
            "thresholds =",
            "weights =",
        ],
    }


def run_audit(
    *,
    root: Path = ROOT,
    json_out: Path = DEFAULT_JSON_OUT,
    markdown_out: Path = DEFAULT_MARKDOWN_OUT,
) -> dict:
    if root != ROOT and json_out == DEFAULT_JSON_OUT:
        json_out = root / "reports" / "gui_evidence_collection_audit_latest.json"
    if root != ROOT and markdown_out == DEFAULT_MARKDOWN_OUT:
        markdown_out = root / "reports" / "gui_evidence_collection_audit_latest.md"

    tool_path = ROOT / "tools" / "gui_evidence_collection_window.py"
    reports = root / "reports"
    data = root / "data"
    protected_before = {
        "decisions": _sha(data / "gui_operational_decisions.csv"),
        "journal": _sha(data / "paper_trading_journal.csv"),
        "outcomes": _sha(data / "trade_outcomes.csv"),
    }
    window = save_window(root=root)
    protected_after = {
        "decisions": _sha(data / "gui_operational_decisions.csv"),
        "journal": _sha(data / "paper_trading_journal.csv"),
        "outcomes": _sha(data / "trade_outcomes.csv"),
    }
    json_report = reports / "gui_evidence_collection_window_latest.json"
    md_report = reports / "gui_evidence_collection_window_latest.md"
    csv_report = reports / "gui_evidence_collection_window_latest.csv"
    history_csv = data / "gui_evidence_collection_windows.csv"
    source = _read_text(tool_path)
    md_text = _read_text(md_report)
    terms = _guard_terms()

    shell_hits = _contains_any(source, terms["shell"])
    order_hits = _contains_any(source, terms["order"])
    api_hits = _contains_any(source, terms["api"])
    scanner_hits = _contains_any(source, terms["scanner"])
    mutation_hits = _contains_any(source, terms["protected_mutation"])
    disabled_state_literal = "_".join(["BUY", "SETUP", "ACTIVE"]) in source
    trigger_literal = "_".join(["TRIGGER", "CONFIRMED"]) in source
    notices_present = all(
        phrase in md_text
        for phrase in [
            "observational only",
            "no automatic trading changes",
            "manual review only",
            "paper trading only",
            "no real orders",
        ]
    )

    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    add("window_tool_exists", tool_path.exists(), str(tool_path))
    add("history_csv_can_be_created", history_csv.exists(), str(history_csv))
    add("window_json_generated", json_report.exists(), str(json_report))
    add("window_markdown_generated", md_report.exists(), str(md_report))
    add("window_csv_generated", csv_report.exists(), str(csv_report))
    add("shell_guardrail_ok", not shell_hits, ", ".join(shell_hits))
    add("order_guardrail_ok", not order_hits, ", ".join(order_hits))
    add("api_guardrail_ok", not api_hits, ", ".join(api_hits))
    add("scanner_guardrail_ok", not scanner_hits, ", ".join(scanner_hits))
    add("protected_data_unchanged", protected_before == protected_after)
    add("protected_mutation_guardrail_ok", not mutation_hits, ", ".join(mutation_hits))
    add("disabled_state_not_enabled", not disabled_state_literal)
    add("no_trigger_creation", not trigger_literal)
    add("guardrail_notices_present", notices_present)
    add("manual_review_only", bool(window.get("manual_review_only", False)))
    add("paper_trading_only", bool(window.get("paper_trading_only", False)))
    add("no_real_order_notice", bool(window.get("no_real_order_notice_present", False)))

    failures = [item for item in checks if item["status"] == "FAIL"]
    result = {
        "status": "FAIL" if failures else "PASS",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool_exists": tool_path.exists(),
        "data_file_can_be_created": history_csv.exists(),
        "window_reports_generated": json_report.exists() and md_report.exists() and csv_report.exists(),
        "critical_failures": len(failures),
        "warnings": 0,
        "readiness_status": window.get("readiness_status"),
        "calibration_readiness_score": window.get("calibration_readiness_score"),
        "readiness_bucket": window.get("readiness_bucket"),
        "manual_review_only": bool(window.get("manual_review_only", False)),
        "paper_trading_only": bool(window.get("paper_trading_only", False)),
        "no_real_order_notice": bool(window.get("no_real_order_notice_present", False)),
        "shell_guardrail_ok": not shell_hits,
        "order_guardrail_ok": not order_hits,
        "api_guardrail_ok": not api_hits,
        "scanner_guardrail_ok": not scanner_hits,
        "protected_data_unchanged": protected_before == protected_after,
        "execution_connection_detected": bool(api_hits),
        "real_order_detected": bool(order_hits),
        "checks": checks,
        "notice": NOTICE,
        "manual_notice": MANUAL_NOTICE,
    }
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_markdown(result), encoding="utf-8")
    return result


def build_markdown(data: dict) -> str:
    lines = [
        "# Analista - GUI evidence collection audit",
        "",
        f"- status: {data.get('status')}",
        f"- critical_failures: {data.get('critical_failures', 0)}",
        f"- warnings: {data.get('warnings', 0)}",
        f"- readiness_status: {data.get('readiness_status')}",
        f"- calibration_readiness_score: {data.get('calibration_readiness_score')}",
        f"- readiness_bucket: {data.get('readiness_bucket')}",
        f"- manual_review_only: {data.get('manual_review_only')}",
        f"- paper_trading_only: {data.get('paper_trading_only')}",
        f"- no_real_order_notice: {data.get('no_real_order_notice')}",
        "",
        "## Checks",
        "",
    ]
    for check in data.get("checks", []) or []:
        detail = f" - {check.get('detail')}" if check.get("detail") else ""
        lines.append(f"- {check.get('status')}: {check.get('name')}{detail}")
    lines.extend(["", "## Guardrails", "", f"- {NOTICE}", f"- {MANUAL_NOTICE}"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita GUI evidence collection window.")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()
    result = run_audit(json_out=Path(args.json_out), markdown_out=Path(args.markdown_out))
    print("=== ANALISTA GUI EVIDENCE COLLECTION AUDIT ===")
    print(f"Status: {result.get('status')}")
    print(f"Critical failures: {result.get('critical_failures')}")
    print(f"Warnings: {result.get('warnings')}")
    print(f"JSON: {Path(args.json_out)}")
    print(f"Markdown: {Path(args.markdown_out)}")
    return 0 if result.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
