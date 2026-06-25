from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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


def _empty_data_safe() -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        charts = importlib.import_module("ui.charts")
        builders = [
            charts.build_signal_distribution_chart_data,
            charts.build_recommendation_distribution_chart_data,
            charts.build_quote_quality_chart_data,
            charts.build_candidate_score_chart_data,
            charts.build_paper_status_chart_data,
            charts.build_followup_decision_chart_data,
            charts.build_closed_outcomes_chart_data,
            charts.build_r_multiple_chart_data,
            charts.build_calibration_bucket_chart_data,
        ]
        for builder in builders:
            for model in ({}, {"data": {"rows": [{}]}}, {"summary": {}}):
                result = builder(model)
                if not isinstance(result, dict):
                    errors.append(f"{builder.__name__}: non-dict result")
                    continue
                if "status" not in result or "dataframe" not in result:
                    errors.append(f"{builder.__name__}: missing chart contract")
    except Exception as exc:
        errors.append(str(exc))
    return not errors, errors


def collect_gui_visuals_audit(root: Path = ROOT) -> dict:
    root = root.resolve()
    app_path = root / "app.py"
    charts_path = root / "ui" / "charts.py"
    app_text = _read_text(app_path)
    charts_text = _read_text(charts_path)
    combined = f"{app_text}\n{charts_text}"

    forbidden_order_terms = ["send_order", "place_order", "buy_order", "sell_order"]
    external_api_terms = ["alpaca", "ibapi", "interactivebrokers", "ccxt"]
    chart_write_terms = ["to_csv(", "to_json(", "write_text(", "write_bytes(", "open("]
    app_direct_read_terms = ["pd.read_csv", "read_csv(", "json.load", "read_text(", "open(", "load_json_report", "load_csv_report"]
    score_change_terms = ["signal_classifier", "threshold =", "thresholds =", "weights =", "scoring/"]
    trigger_state = "_".join(["TRIGGER", "CONFIRMED"])
    disabled_setup = "_".join(["BUY", "SETUP", "ACTIVE"])

    empty_safe, empty_errors = _empty_data_safe()
    charts_module_exists = charts_path.exists()
    app_exists = app_path.exists()
    app_uses_charts = "from ui import charts as ui_charts" in app_text and "ui_charts." in app_text
    charts_no_writes = not _contains_any(charts_text, chart_write_terms)
    app_no_direct_report_reads = not _contains_any(app_text, app_direct_read_terms)
    shell_guardrail_ok = "shell=True" not in combined
    broker_guardrail_ok = not _contains_any(combined, forbidden_order_terms + external_api_terms)
    signal_guardrail_ok = trigger_state not in combined and disabled_setup not in combined
    scoring_guardrail_ok = not _contains_any(combined, score_change_terms)

    issues: list[dict] = []

    def add_issue(severity: str, source: str, message: str) -> None:
        issues.append({"severity": severity, "source": source, "message": message})

    if not app_exists:
        add_issue("FAIL", "app.py", "app.py missing")
    if not charts_module_exists:
        add_issue("FAIL", "ui/charts.py", "ui/charts.py missing")
    if not app_uses_charts:
        add_issue("FAIL", "app.py", "app.py does not import and use ui.charts")
    if not charts_no_writes:
        add_issue("FAIL", "ui/charts.py", "Chart module contains write primitives")
    if not app_no_direct_report_reads:
        add_issue("FAIL", "app.py", "Direct report reads detected in app.py")
    if not empty_safe:
        add_issue("FAIL", "ui/charts.py", "Chart builders are not empty-data safe")
    if not shell_guardrail_ok:
        add_issue("FAIL", "guardrails", "shell=True detected")
    if not broker_guardrail_ok:
        add_issue("FAIL", "guardrails", "Order/API reference detected")
    if not signal_guardrail_ok:
        add_issue("FAIL", "guardrails", "Disabled setup or trigger state literal detected")
    if not scoring_guardrail_ok:
        add_issue("FAIL", "guardrails", "Scoring or threshold change reference detected")

    failures = [item for item in issues if item["severity"] == "FAIL"]
    warnings = [item for item in issues if item["severity"] == "WARN"]
    status = "FAIL" if failures else "WARN" if warnings else "PASS"

    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "charts_module_exists": charts_module_exists,
        "app_exists": app_exists,
        "app_uses_charts": app_uses_charts,
        "charts_no_writes": charts_no_writes,
        "app_no_direct_report_reads": app_no_direct_report_reads,
        "empty_data_safe": empty_safe,
        "empty_data_errors": empty_errors,
        "broker_guardrail_ok": broker_guardrail_ok,
        "shell_guardrail_ok": shell_guardrail_ok,
        "signal_guardrail_ok": signal_guardrail_ok,
        "scoring_guardrail_ok": scoring_guardrail_ok,
        "critical_failures": len(failures),
        "warnings": len(warnings),
        "issues": issues,
        "outputs": {
            "json": "reports/gui_visuals_audit_latest.json",
            "markdown": "reports/gui_visuals_audit_latest.md",
        },
    }


def build_gui_visuals_audit_markdown(data: dict) -> str:
    lines = [
        "# Analista - GUI visuals audit",
        "",
        f"- status: {data.get('status')}",
        f"- charts_module_exists: {data.get('charts_module_exists')}",
        f"- app_uses_charts: {data.get('app_uses_charts')}",
        f"- charts_no_writes: {data.get('charts_no_writes')}",
        f"- app_no_direct_report_reads: {data.get('app_no_direct_report_reads')}",
        f"- empty_data_safe: {data.get('empty_data_safe')}",
        f"- broker_guardrail_ok: {data.get('broker_guardrail_ok')}",
        f"- shell_guardrail_ok: {data.get('shell_guardrail_ok')}",
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
            "- GUI visuals are read-only.",
            "- Charts use loaded UI view models only.",
            "- No automatic trading or real order path is introduced.",
        ]
    )
    return "\n".join(lines)


def save_gui_visuals_audit(
    *,
    root: Path = ROOT,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict:
    json_out = json_out or root / "reports" / "gui_visuals_audit_latest.json"
    markdown_out = markdown_out or root / "reports" / "gui_visuals_audit_latest.md"
    data = collect_gui_visuals_audit(root=root)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_gui_visuals_audit_markdown(data), encoding="utf-8")
    return {
        "status": data["status"],
        "critical_failures": data["critical_failures"],
        "warnings": data["warnings"],
        "json_out": str(json_out),
        "markdown_out": str(markdown_out),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita visualizaciones read-only del dashboard GUI.")
    parser.add_argument("--json-out", default="reports/gui_visuals_audit_latest.json")
    parser.add_argument("--markdown-out", default="reports/gui_visuals_audit_latest.md")
    args = parser.parse_args()

    result = save_gui_visuals_audit(
        root=ROOT,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
    )
    print("=== ANALISTA GUI VISUALS AUDIT ===")
    print(f"Status: {result['status']}")
    print(f"Critical failures: {result['critical_failures']}")
    print(f"Warnings: {result['warnings']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")
    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
