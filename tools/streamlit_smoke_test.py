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

from ui.report_loader import load_all_ui_sources
from ui.view_models import (
    build_calibration_model,
    build_candidate_table_model,
    build_cycle_audit_model,
    build_followup_model,
    build_paper_trading_model,
    build_quality_gate_model,
    build_status_overview,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _import_app(app_path: Path) -> tuple[bool, str]:
    if not app_path.exists():
        return False, "app_py_missing"
    try:
        spec = importlib.util.spec_from_file_location("analista_streamlit_app_smoke", app_path)
        if spec is None or spec.loader is None:
            return False, "app_import_spec_missing"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _scan_app_guardrails(app_path: Path) -> dict:
    text = app_path.read_text(encoding="utf-8", errors="ignore") if app_path.exists() else ""
    lower = text.lower()
    disabled_signal = "_".join(["BUY", "SETUP", "ACTIVE"])
    trigger_signal = "_".join(["TRIGGER", "CONFIRMED"])
    forbidden = [
        "broker",
        "send_order",
        "place_order",
        "buy_order",
        "sell_order",
        "data/paper_trading_journal.csv",
        "data/trade_outcomes.csv",
        "run_scanner",
        "to_csv(",
        "write_text(",
        "open(",
    ]
    hits = [item for item in forbidden if item in lower]
    return {
        "forbidden_hits": hits,
        "disabled_signal_detected": disabled_signal in text.upper(),
        "trigger_signal_detected": trigger_signal in text.upper(),
        "uses_report_loader": "load_all_ui_sources" in text,
        "uses_view_models": "build_candidate_table_model" in text,
    }


def collect_streamlit_smoke_test(root: Path = ROOT) -> dict:
    root = root.resolve()
    app_path = root / "app.py"
    import_ok, import_error = _import_app(app_path)
    sources_ok = True
    view_models_ok = True
    errors: list[str] = []

    try:
        sources = load_all_ui_sources(root)
    except Exception as exc:
        sources_ok = False
        sources = {"sources": {}, "summary": {}}
        errors.append(f"load_all_ui_sources_failed:{exc}")

    models = {}
    if sources_ok:
        builders = {
            "status_overview": build_status_overview,
            "candidate_table": build_candidate_table_model,
            "quality_gate": build_quality_gate_model,
            "paper_trading": build_paper_trading_model,
            "followup": build_followup_model,
            "cycle_audit": build_cycle_audit_model,
            "calibration": build_calibration_model,
        }
        for name, builder in builders.items():
            try:
                models[name] = builder(sources)
            except Exception as exc:
                view_models_ok = False
                errors.append(f"view_model_failed:{name}:{exc}")

    guardrails = _scan_app_guardrails(app_path)
    if not import_ok:
        errors.append(f"app_import_failed:{import_error}")
    if guardrails["forbidden_hits"]:
        errors.append("forbidden_app_references:" + ",".join(guardrails["forbidden_hits"]))
    if guardrails["disabled_signal_detected"]:
        errors.append("disabled_signal_literal_detected")
    if guardrails["trigger_signal_detected"]:
        errors.append("trigger_signal_literal_detected")
    if not guardrails["uses_report_loader"]:
        errors.append("app_does_not_use_report_loader")
    if not guardrails["uses_view_models"]:
        errors.append("app_does_not_use_view_models")

    status = "PASS" if not errors else "FAIL"
    return {
        "status": status,
        "generated_at": _utc_now(),
        "app_exists": app_path.exists(),
        "import_ok": import_ok,
        "import_error": import_error,
        "sources_ok": sources_ok,
        "view_models_ok": view_models_ok,
        "read_only": not guardrails["forbidden_hits"],
        "available_sources": int(sources.get("summary", {}).get("available_sources", 0) or 0),
        "missing_sources": int(sources.get("summary", {}).get("missing_sources", 0) or 0),
        "candidate_rows": int(models.get("candidate_table", {}).get("rows_count", 0) or 0),
        "paper_journal_rows": int(
            models.get("paper_trading", {}).get("summary", {}).get("journal_rows", 0) or 0
        ),
        "guardrails": guardrails,
        "errors": errors,
    }


def build_streamlit_smoke_markdown(data: dict) -> str:
    lines = [
        "# Analista - Streamlit smoke test",
        "",
        f"- status: {data.get('status')}",
        f"- app_exists: {data.get('app_exists')}",
        f"- import_ok: {data.get('import_ok')}",
        f"- view_models_ok: {data.get('view_models_ok')}",
        f"- read_only: {data.get('read_only')}",
        f"- available_sources: {data.get('available_sources')}",
        f"- missing_sources: {data.get('missing_sources')}",
        f"- candidate_rows: {data.get('candidate_rows')}",
        f"- paper_journal_rows: {data.get('paper_journal_rows')}",
        "",
        "## Errors",
        "",
    ]
    errors = data.get("errors", [])
    lines.extend([f"- {error}" for error in errors] if errors else ["- None"])
    return "\n".join(lines)


def save_streamlit_smoke_test(
    *,
    root: Path = ROOT,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict:
    json_out = json_out or root / "reports" / "streamlit_smoke_test_latest.json"
    markdown_out = markdown_out or root / "reports" / "streamlit_smoke_test_latest.md"
    data = collect_streamlit_smoke_test(root=root)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_streamlit_smoke_markdown(data), encoding="utf-8")
    data["json_out"] = str(json_out)
    data["markdown_out"] = str(markdown_out)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test read-only Streamlit dashboard.")
    parser.add_argument("--json-out", default="reports/streamlit_smoke_test_latest.json")
    parser.add_argument("--markdown-out", default="reports/streamlit_smoke_test_latest.md")
    args = parser.parse_args()

    result = save_streamlit_smoke_test(
        root=ROOT,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
    )
    print("=== ANALISTA STREAMLIT SMOKE TEST ===")
    print(f"Status: {result['status']}")
    print(f"App exists: {result['app_exists']}")
    print(f"Import OK: {result['import_ok']}")
    print(f"View models OK: {result['view_models_ok']}")
    print(f"Read only: {result['read_only']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")
    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
