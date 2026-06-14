from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
NO_REAL_ORDER_NOTICE = "paper trading only; no real order"


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _file_exists(root: Path, relative_path: str) -> bool:
    return (root / relative_path).exists()


def _contains_any(text: str, patterns: list[str]) -> list[str]:
    lower = text.lower()
    return [pattern for pattern in patterns if pattern.lower() in lower]


def _load_action_log(root: Path) -> tuple[bool, int, list[str]]:
    path = root / "data" / "ui_action_log.csv"
    if not path.exists():
        return False, 0, []
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return True, 0, []
    actions = []
    if "action_type" in df.columns:
        actions = sorted(value for value in df["action_type"].astype(str).unique() if value)
    return True, int(len(df)), actions


def collect_gui_actions_audit(root: Path = ROOT) -> dict:
    root = root.resolve()
    app_path = root / "app.py"
    actions_path = root / "ui" / "actions.py"
    guards_path = root / "ui" / "guards.py"
    app_text = _read_text(app_path)
    actions_text = _read_text(actions_path)
    guards_text = _read_text(guards_path)
    combined = f"{app_text}\n{actions_text}"
    action_log_exists, logged_actions, action_types = _load_action_log(root)

    forbidden_order_terms = ["send_order", "place_order", "buy_order", "sell_order"]
    external_api_terms = ["alpaca", "ibapi", "interactivebrokers", "ccxt"]
    arbitrary_command_terms = ["subprocess.run", "subprocess.Popen", "os.system", "eval(", "exec("]
    trigger_state = "_".join(["TRIGGER", "CONFIRMED"])
    disabled_setup = "_".join(["BUY", "SETUP", "ACTIVE"])

    order_hits = _contains_any(combined, forbidden_order_terms)
    api_hits = _contains_any(combined, external_api_terms)
    arbitrary_command_hits = _contains_any(actions_text, arbitrary_command_terms)
    app_action_import_ok = "from ui import actions as paper_actions" in app_text
    actions_module_exists = actions_path.exists()
    app_exists = app_path.exists()
    shell_guardrail_ok = "shell=True" not in combined
    command_guardrail_ok = not arbitrary_command_hits
    broker_guardrail_ok = not order_hits and not api_hits
    no_real_order_notice_present = NO_REAL_ORDER_NOTICE in actions_text or NO_REAL_ORDER_NOTICE in guards_text
    confirmations = [
        "Confirm paper-only import; no real order",
        "Confirm paper-only decision; no real order",
        "Confirm manual paper close; no real order",
        "Confirm export to trade_outcomes.csv",
    ]
    confirmations_present = all(item in app_text for item in confirmations)
    scanner_guardrail_ok = "run_scanner" not in combined
    scoring_guardrail_ok = "signal_classifier" not in combined and "scoring/" not in combined
    thresholds_guardrail_ok = "threshold" not in actions_text.lower() and "weights" not in actions_text.lower()
    signal_guardrail_ok = trigger_state not in combined and disabled_setup not in combined

    issues: list[dict] = []

    def add_issue(severity: str, source: str, message: str) -> None:
        issues.append({"severity": severity, "source": source, "message": message})

    if not app_exists:
        add_issue("FAIL", "app.py", "app.py missing")
    if not actions_module_exists:
        add_issue("FAIL", "ui/actions.py", "ui/actions.py missing")
    if not app_action_import_ok:
        add_issue("FAIL", "app.py", "app.py does not use ui.actions for GUI actions")
    if not broker_guardrail_ok:
        add_issue("FAIL", "guardrails", "Forbidden order/API references detected")
    if not shell_guardrail_ok:
        add_issue("FAIL", "guardrails", "shell=True detected")
    if not command_guardrail_ok:
        add_issue("FAIL", "guardrails", "Arbitrary command execution primitive detected in ui/actions.py")
    if not no_real_order_notice_present:
        add_issue("FAIL", "guardrails", "Missing paper-only no-real-order notice")
    if not confirmations_present:
        add_issue("FAIL", "app.py", "Missing explicit confirmation controls")
    if not scanner_guardrail_ok:
        add_issue("FAIL", "guardrails", "Scanner execution reference detected")
    if not scoring_guardrail_ok:
        add_issue("FAIL", "guardrails", "Scoring or signal classifier reference detected")
    if not thresholds_guardrail_ok:
        add_issue("FAIL", "guardrails", "Weights or thresholds reference detected in ui/actions.py")
    if not signal_guardrail_ok:
        add_issue("FAIL", "guardrails", "Disabled setup or trigger state literal detected")
    if not action_log_exists:
        add_issue("WARN", "action_log", "data/ui_action_log.csv not created yet")

    failures = [item for item in issues if item["severity"] == "FAIL"]
    warnings = [item for item in issues if item["severity"] == "WARN"]
    status = "FAIL" if failures else "WARN" if warnings else "PASS"

    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "actions_module_exists": actions_module_exists,
        "app_exists": app_exists,
        "app_uses_actions_module": app_action_import_ok,
        "action_log_exists": action_log_exists,
        "logged_actions": logged_actions,
        "action_types": action_types,
        "broker_guardrail_ok": broker_guardrail_ok,
        "shell_guardrail_ok": shell_guardrail_ok,
        "command_guardrail_ok": command_guardrail_ok,
        "confirmations_present": confirmations_present,
        "no_real_order_notice_present": no_real_order_notice_present,
        "scanner_guardrail_ok": scanner_guardrail_ok,
        "scoring_guardrail_ok": scoring_guardrail_ok,
        "thresholds_guardrail_ok": thresholds_guardrail_ok,
        "signal_guardrail_ok": signal_guardrail_ok,
        "order_hits": order_hits,
        "api_hits": api_hits,
        "arbitrary_command_hits": arbitrary_command_hits,
        "critical_failures": len(failures),
        "warnings": len(warnings),
        "issues": issues,
        "outputs": {
            "json": "reports/gui_actions_audit_latest.json",
            "markdown": "reports/gui_actions_audit_latest.md",
        },
    }


def build_gui_actions_audit_markdown(data: dict) -> str:
    lines = [
        "# Analista - GUI actions audit",
        "",
        f"- status: {data.get('status')}",
        f"- actions_module_exists: {data.get('actions_module_exists')}",
        f"- app_uses_actions_module: {data.get('app_uses_actions_module')}",
        f"- action_log_exists: {data.get('action_log_exists')}",
        f"- logged_actions: {data.get('logged_actions')}",
        f"- broker_guardrail_ok: {data.get('broker_guardrail_ok')}",
        f"- shell_guardrail_ok: {data.get('shell_guardrail_ok')}",
        f"- command_guardrail_ok: {data.get('command_guardrail_ok')}",
        f"- confirmations_present: {data.get('confirmations_present')}",
        f"- no_real_order_notice_present: {data.get('no_real_order_notice_present')}",
        "",
        "## Logged Action Types",
        "",
    ]
    action_types = data.get("action_types", [])
    lines.extend([f"- {item}" for item in action_types] if action_types else ["- None"])
    lines.extend(["", "## Issues", ""])
    issues = data.get("issues", [])
    if not issues:
        lines.append("- None")
    else:
        for item in issues:
            lines.append(
                f"- {item.get('severity')}: {item.get('source')} - {item.get('message')}"
            )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Paper trading only; no real order.",
            "- GUI actions do not send real orders.",
            "- GUI actions use existing paper trading tools only.",
        ]
    )
    return "\n".join(lines)


def save_gui_actions_audit(
    *,
    root: Path = ROOT,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict:
    json_out = json_out or root / "reports" / "gui_actions_audit_latest.json"
    markdown_out = markdown_out or root / "reports" / "gui_actions_audit_latest.md"
    data = collect_gui_actions_audit(root=root)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_gui_actions_audit_markdown(data), encoding="utf-8")
    return {
        "status": data["status"],
        "critical_failures": data["critical_failures"],
        "warnings": data["warnings"],
        "json_out": str(json_out),
        "markdown_out": str(markdown_out),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita acciones GUI controladas de paper trading.")
    parser.add_argument("--json-out", default="reports/gui_actions_audit_latest.json")
    parser.add_argument("--markdown-out", default="reports/gui_actions_audit_latest.md")
    args = parser.parse_args()

    result = save_gui_actions_audit(
        root=ROOT,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
    )
    print("=== ANALISTA GUI ACTIONS AUDIT ===")
    print(f"Status: {result['status']}")
    print(f"Critical failures: {result['critical_failures']}")
    print(f"Warnings: {result['warnings']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")
    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
