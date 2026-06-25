from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.report_loader import SOURCE_SPECS, load_all_ui_sources, load_json_report
from ui.view_models import (
    VIEW_STATUSES,
    build_calibration_model,
    build_candidate_table_model,
    build_cycle_audit_model,
    build_followup_model,
    build_paper_trading_model,
    build_quality_gate_model,
    build_status_overview,
)

NO_REAL_ORDER_NOTICE = "paper trading only; no real order"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _scan_ui_files(root: Path) -> dict:
    ui_dir = root / "ui"
    files = [
        ui_dir / "report_loader.py",
        ui_dir / "view_models.py",
    ]
    text = "\n".join(_read_text(path) for path in files)
    disabled_signal = "_".join(["BUY", "SETUP", "ACTIVE"])
    trigger_signal = "_".join(["TRIGGER", "CONFIRMED"])
    lower = text.lower()
    return {
        "disabled_signal_detected": disabled_signal in text.upper(),
        "trigger_signal_detected": trigger_signal in text.upper(),
        "broker_or_order_reference_detected": any(
            pattern in lower
            for pattern in [
                "broker",
                "send_order",
                "submit_order",
                "place_order",
                "real_order",
                "order execution",
            ]
        ),
    }


def collect_ui_data_contract_audit(root: Path = ROOT) -> dict:
    root = root.resolve()
    issues: list[str] = []
    warnings: list[str] = []

    loader_path = root / "ui" / "report_loader.py"
    view_models_path = root / "ui" / "view_models.py"
    if not loader_path.exists():
        issues.append("missing_ui_report_loader")
    if not view_models_path.exists():
        issues.append("missing_ui_view_models")

    with tempfile.TemporaryDirectory() as tmp:
        missing_json = load_json_report(Path(tmp) / "missing.json")
        empty_sources = load_all_ui_sources(Path(tmp))
    if missing_json.get("status") != "MISSING":
        issues.append("load_json_missing_not_controlled")
    if empty_sources.get("summary", {}).get("total_sources") != len(SOURCE_SPECS):
        issues.append("load_all_ui_sources_missing_contract")

    sources = load_all_ui_sources(root)
    summary = sources.get("summary", {})
    models = {
        "status_overview": build_status_overview(sources),
        "candidate_table": build_candidate_table_model(sources),
        "quality_gate": build_quality_gate_model(sources),
        "paper_trading": build_paper_trading_model(sources),
        "followup": build_followup_model(sources),
        "cycle_audit": build_cycle_audit_model(sources),
        "calibration": build_calibration_model(sources),
    }

    for name, model in models.items():
        if model.get("status") not in VIEW_STATUSES:
            issues.append(f"invalid_view_model_status:{name}:{model.get('status')}")

    scan = _scan_ui_files(root)
    if scan["disabled_signal_detected"]:
        issues.append("disabled_signal_detected_in_ui_contract")
    if scan["trigger_signal_detected"]:
        issues.append("trigger_signal_detected_in_ui_contract")
    if scan["broker_or_order_reference_detected"]:
        issues.append("broker_or_order_reference_detected_in_ui_contract")

    if summary.get("missing_sources", 0):
        warnings.append(f"missing_sources:{summary.get('missing_sources')}")
    if summary.get("invalid_sources", 0):
        issues.append(f"invalid_sources:{summary.get('invalid_sources')}")

    candidate_rows = int(models["candidate_table"].get("rows_count", 0) or 0)
    paper_summary = models["paper_trading"].get("summary", {})

    status = "PASS"
    if issues:
        status = "FAIL"
    elif warnings:
        status = "WARN"

    return {
        "status": status,
        "generated_at": _utc_now(),
        "available_sources": int(summary.get("available_sources", 0) or 0),
        "missing_sources": int(summary.get("missing_sources", 0) or 0),
        "invalid_sources": int(summary.get("invalid_sources", 0) or 0),
        "empty_sources": int(summary.get("empty_sources", 0) or 0),
        "candidate_rows": candidate_rows,
        "paper_journal_rows": int(paper_summary.get("journal_rows", 0) or 0),
        "models": models,
        "issues": issues,
        "warnings": warnings,
        "guardrails": {
            "read_only": True,
            "no_operational_writes": True,
            "broker_or_order_reference_detected": scan["broker_or_order_reference_detected"],
            "disabled_signal_detected": scan["disabled_signal_detected"],
            "trigger_signal_detected": scan["trigger_signal_detected"],
        },
        "no_real_order_notice": NO_REAL_ORDER_NOTICE,
    }


def build_ui_data_contract_markdown(data: dict) -> str:
    lines: list[str] = []
    lines.append("# Analista - UI data contract audit")
    lines.append("")
    lines.append(f"- status: {data.get('status')}")
    lines.append(f"- generated_at: {data.get('generated_at')}")
    lines.append(f"- available_sources: {data.get('available_sources')}")
    lines.append(f"- missing_sources: {data.get('missing_sources')}")
    lines.append(f"- invalid_sources: {data.get('invalid_sources')}")
    lines.append(f"- candidate_rows: {data.get('candidate_rows')}")
    lines.append(f"- paper_journal_rows: {data.get('paper_journal_rows')}")
    lines.append(f"- notice: {NO_REAL_ORDER_NOTICE}")
    lines.append("")
    lines.append("## Guardrails")
    lines.append("")
    guardrails = data.get("guardrails", {})
    lines.append(f"- read_only: {guardrails.get('read_only')}")
    lines.append(f"- no_operational_writes: {guardrails.get('no_operational_writes')}")
    lines.append(
        f"- broker_or_order_reference_detected: {guardrails.get('broker_or_order_reference_detected')}"
    )
    lines.append(f"- disabled_signal_detected: {guardrails.get('disabled_signal_detected')}")
    lines.append(f"- trigger_signal_detected: {guardrails.get('trigger_signal_detected')}")
    lines.append("")
    lines.append("## Issues")
    lines.append("")
    issues = data.get("issues", [])
    lines.extend([f"- {issue}" for issue in issues] if issues else ["- None"])
    lines.append("")
    lines.append("## Warnings")
    lines.append("")
    warnings = data.get("warnings", [])
    lines.extend([f"- {warning}" for warning in warnings] if warnings else ["- None"])
    lines.append("")
    lines.append("## View Models")
    lines.append("")
    for name, model in (data.get("models", {}) or {}).items():
        lines.append(f"- {name}: {model.get('status')} rows={model.get('rows_count', 0)}")
    return "\n".join(lines)


def save_ui_data_contract_audit(
    *,
    root: Path = ROOT,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict:
    json_out = json_out or root / "reports" / "ui_data_contract_audit_latest.json"
    markdown_out = markdown_out or root / "reports" / "ui_data_contract_audit_latest.md"
    data = collect_ui_data_contract_audit(root=root)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_ui_data_contract_markdown(data), encoding="utf-8")
    data["json_out"] = str(json_out)
    data["markdown_out"] = str(markdown_out)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita el contrato de datos UI read-only.")
    parser.add_argument("--json-out", default="reports/ui_data_contract_audit_latest.json")
    parser.add_argument("--markdown-out", default="reports/ui_data_contract_audit_latest.md")
    args = parser.parse_args()

    result = save_ui_data_contract_audit(
        root=ROOT,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
    )
    print("=== ANALISTA UI DATA CONTRACT AUDIT ===")
    print(f"Status: {result['status']}")
    print(f"Available sources: {result['available_sources']}")
    print(f"Missing sources: {result['missing_sources']}")
    print(f"Invalid sources: {result['invalid_sources']}")
    print(f"Candidate rows: {result['candidate_rows']}")
    print(f"Paper journal rows: {result['paper_journal_rows']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")
    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
