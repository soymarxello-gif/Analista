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

from tools.gui_actions_audit import collect_gui_actions_audit
from tools.gui_visuals_audit import collect_gui_visuals_audit
from tools.streamlit_smoke_test import collect_streamlit_smoke_test
from tools.ui_data_contract_audit import collect_ui_data_contract_audit


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


def _import_ok(path: Path, module_name: str) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            return False, "spec_missing"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def collect_gui_release_audit(root: Path = ROOT) -> dict:
    root = root.resolve()
    app_path = root / "app.py"
    report_loader_path = root / "ui" / "report_loader.py"
    view_models_path = root / "ui" / "view_models.py"
    actions_path = root / "ui" / "actions.py"
    charts_path = root / "ui" / "charts.py"
    guards_path = root / "ui" / "guards.py"
    formatters_path = root / "ui" / "formatters.py"
    layout_path = root / "ui" / "layout.py"

    app_text = _read_text(app_path)
    actions_text = _read_text(actions_path)
    guards_text = _read_text(guards_path)
    layout_text = _read_text(layout_path)
    combined_app_actions = f"{app_text}\n{actions_text}"

    expected_imports = [
        "ui.report_loader",
        "ui.view_models",
        "from ui import actions",
        "from ui import charts",
        "from ui import formatters",
        "from ui import guards",
    ]
    app_imports_expected_modules = all(item in app_text for item in expected_imports)

    forbidden_order_terms = ["send_order", "place_order", "buy_order", "sell_order"]
    external_api_terms = ["ibapi", "alpaca", "interactivebrokers", "robinhood"]
    app_direct_read_terms = ["pd.read_csv", "read_csv(", "json.load", "read_text(", "open(", "load_json_report", "load_csv_report"]
    app_direct_write_terms = ["to_csv(", "to_json(", "write_text(", "write_bytes(", "open("]
    data_write_terms = ["data/paper_trading_journal.csv", "data\\paper_trading_journal.csv", "data/trade_outcomes.csv", "data\\trade_outcomes.csv"]
    scoring_terms = ["signal_classifier", "scoring/", "threshold =", "thresholds =", "weights ="]
    disabled_setup = "_".join(["BUY", "SETUP", "ACTIVE"])
    trigger_state = "_".join(["TRIGGER", "CONFIRMED"])

    streamlit_smoke = collect_streamlit_smoke_test(root=root)
    gui_actions = collect_gui_actions_audit(root=root)
    gui_visuals = collect_gui_visuals_audit(root=root)
    ui_contract = collect_ui_data_contract_audit(root=root)

    app_exists = app_path.exists()
    guards_exists = guards_path.exists()
    formatters_exists = formatters_path.exists()
    layout_exists = layout_path.exists()
    required_files = {
        "app.py": app_exists,
        "ui/report_loader.py": report_loader_path.exists(),
        "ui/view_models.py": view_models_path.exists(),
        "ui/actions.py": actions_path.exists(),
        "ui/charts.py": charts_path.exists(),
        "ui/guards.py": guards_exists,
        "ui/formatters.py": formatters_exists,
    }
    guards_import_ok, guards_import_error = _import_ok(guards_path, "analista_ui_guards_audit")
    formatters_import_ok, formatters_import_error = _import_ok(formatters_path, "analista_ui_formatters_audit")

    app_order_hits = _contains_any(app_text, forbidden_order_terms)
    actions_order_hits = _contains_any(actions_text, forbidden_order_terms)
    app_api_hits = _contains_any(app_text, external_api_terms)
    actions_api_hits = _contains_any(actions_text, external_api_terms)
    read_write_guardrail_ok = (
        not _contains_any(app_text, app_direct_read_terms)
        and not _contains_any(app_text, app_direct_write_terms)
        and not _contains_any(app_text, data_write_terms)
    )
    shell_guardrail_ok = "shell=True" not in combined_app_actions
    broker_guardrail_ok = not app_order_hits and not actions_order_hits and not app_api_hits and not actions_api_hits
    confirmation_guardrail_ok = all(
        item in app_text
        for item in [
            "PAPER_ENTER",
            "Confirm manual paper close; no real order",
            "Confirm export to trade_outcomes.csv",
        ]
    )
    no_real_order_notice_present = (
        "NO_REAL_ORDER_NOTICE" in app_text
        or "NO_REAL_ORDER_NOTICE" in layout_text
        or "paper trading only; no real order" in app_text
        or "paper trading only; no real order" in layout_text
        or "paper trading only; no real order" in guards_text
    )
    signal_guardrail_ok = disabled_setup not in combined_app_actions and trigger_state not in combined_app_actions
    scoring_guardrail_ok = not _contains_any(combined_app_actions, scoring_terms)
    scanner_guardrail_ok = "run_scanner" not in combined_app_actions

    issues: list[dict] = []

    def add_issue(severity: str, source: str, message: str) -> None:
        issues.append({"severity": severity, "source": source, "message": message})

    for path_label, exists in required_files.items():
        if not exists:
            add_issue("FAIL", path_label, "required GUI release file missing")
    if not app_imports_expected_modules:
        add_issue("FAIL", "app.py", "app.py does not import all expected UI modules")
    if not guards_import_ok:
        add_issue("FAIL", "ui/guards.py", f"guards import failed:{guards_import_error}")
    if not formatters_import_ok:
        add_issue("FAIL", "ui/formatters.py", f"formatters import failed:{formatters_import_error}")
    if not read_write_guardrail_ok:
        add_issue("FAIL", "app.py", "direct read/write path detected")
    if not shell_guardrail_ok:
        add_issue("FAIL", "guardrails", "shell=True detected")
    if not broker_guardrail_ok:
        add_issue("FAIL", "guardrails", "order/API term detected")
    if not confirmation_guardrail_ok:
        add_issue("FAIL", "app.py", "required explicit confirmations missing")
    if not no_real_order_notice_present:
        add_issue("FAIL", "guardrails", "missing no-real-order notice")
    if not signal_guardrail_ok:
        add_issue("FAIL", "guardrails", "disabled setup or trigger state literal detected")
    if not scoring_guardrail_ok:
        add_issue("FAIL", "guardrails", "scoring or threshold reference detected")
    if not scanner_guardrail_ok:
        add_issue("FAIL", "guardrails", "scanner execution reference detected")

    sub_audits = {
        "streamlit_smoke_test": streamlit_smoke.get("status", "MISSING"),
        "gui_actions_audit": gui_actions.get("status", "MISSING"),
        "gui_visuals_audit": gui_visuals.get("status", "MISSING"),
        "ui_data_contract_audit": ui_contract.get("status", "MISSING"),
    }
    for name, status in sub_audits.items():
        if status == "FAIL":
            add_issue("FAIL", name, f"{name} failed")
        elif status not in {"PASS", "WARN"}:
            add_issue("WARN", name, f"{name} status {status}")
        elif status == "WARN":
            add_issue("WARN", name, f"{name} returned WARN")

    failures = [item for item in issues if item["severity"] == "FAIL"]
    warnings = [item for item in issues if item["severity"] == "WARN"]
    status = "FAIL" if failures else "WARN" if warnings else "PASS"

    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "app_exists": app_exists,
        "guards_exists": guards_exists,
        "formatters_exists": formatters_exists,
        "layout_exists": layout_exists,
        "app_imports_expected_modules": app_imports_expected_modules,
        "read_write_guardrail_ok": read_write_guardrail_ok,
        "broker_guardrail_ok": broker_guardrail_ok,
        "shell_guardrail_ok": shell_guardrail_ok,
        "confirmation_guardrail_ok": confirmation_guardrail_ok,
        "no_real_order_notice_present": no_real_order_notice_present,
        "signal_guardrail_ok": signal_guardrail_ok,
        "scoring_guardrail_ok": scoring_guardrail_ok,
        "scanner_guardrail_ok": scanner_guardrail_ok,
        "streamlit_smoke_status": streamlit_smoke.get("status", "MISSING"),
        "gui_actions_status": gui_actions.get("status", "MISSING"),
        "gui_visuals_status": gui_visuals.get("status", "MISSING"),
        "ui_data_contract_status": ui_contract.get("status", "MISSING"),
        "critical_failures": len(failures),
        "warnings": len(warnings),
        "issues": issues,
        "outputs": {
            "json": "reports/gui_release_audit_latest.json",
            "markdown": "reports/gui_release_audit_latest.md",
        },
    }


def build_gui_release_audit_markdown(data: dict) -> str:
    lines = [
        "# Analista - GUI release audit",
        "",
        f"- status: {data.get('status')}",
        f"- app_exists: {data.get('app_exists')}",
        f"- guards_exists: {data.get('guards_exists')}",
        f"- formatters_exists: {data.get('formatters_exists')}",
        f"- read_write_guardrail_ok: {data.get('read_write_guardrail_ok')}",
        f"- broker_guardrail_ok: {data.get('broker_guardrail_ok')}",
        f"- shell_guardrail_ok: {data.get('shell_guardrail_ok')}",
        f"- confirmation_guardrail_ok: {data.get('confirmation_guardrail_ok')}",
        f"- streamlit_smoke_status: {data.get('streamlit_smoke_status')}",
        f"- gui_actions_status: {data.get('gui_actions_status')}",
        f"- gui_visuals_status: {data.get('gui_visuals_status')}",
        f"- ui_data_contract_status: {data.get('ui_data_contract_status')}",
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
            "## Release guardrails",
            "",
            "- Manual review only.",
            "- Paper trading only.",
            "- No real orders.",
            "- GUI does not execute scanner or scoring changes.",
        ]
    )
    return "\n".join(lines)


def save_gui_release_audit(
    *,
    root: Path = ROOT,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict:
    json_out = json_out or root / "reports" / "gui_release_audit_latest.json"
    markdown_out = markdown_out or root / "reports" / "gui_release_audit_latest.md"
    data = collect_gui_release_audit(root=root)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_gui_release_audit_markdown(data), encoding="utf-8")
    return {
        "status": data["status"],
        "critical_failures": data["critical_failures"],
        "warnings": data["warnings"],
        "json_out": str(json_out),
        "markdown_out": str(markdown_out),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita release candidate de GUI Streamlit.")
    parser.add_argument("--json-out", default="reports/gui_release_audit_latest.json")
    parser.add_argument("--markdown-out", default="reports/gui_release_audit_latest.md")
    args = parser.parse_args()

    result = save_gui_release_audit(
        root=ROOT,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
    )
    print("=== ANALISTA GUI RELEASE AUDIT ===")
    print(f"Status: {result['status']}")
    print(f"Critical failures: {result['critical_failures']}")
    print(f"Warnings: {result['warnings']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")
    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
