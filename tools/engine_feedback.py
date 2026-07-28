from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NOTICE = "observational diagnostics only; no automatic scoring changes"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def collect_feedback(audit_json: Path, simple_json: Path | None = None) -> dict[str, Any]:
    audit = _load_json(audit_json)
    simple = _load_json(simple_json or ROOT / "reports" / "simple_candidate_posttest_latest.json")
    rows = int(simple.get("rows", 0) or 0)
    horizon_summary = simple.get("horizon_summary", {}) if isinstance(simple.get("horizon_summary"), dict) else {}
    recommendations: list[str] = []
    for item in simple.get("recommendations", []) or []:
        if str(item).upper() != "NO_ACTION":
            recommendations.append(str(item))
    for item in audit.get("recommendations", []) or []:
        recommendations.append(str(item))
    if rows < 10:
        recommendations.append("NEED_MORE_POSTTEST_OBSERVATIONS")
    unique = list(dict.fromkeys(recommendations)) or ["NO_ACTION"]
    status = "WARN" if rows < 10 else "PASS"
    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "canonical_rows": rows,
        "canonical_dates": len(horizon_summary),
        "recommendation_count": len(unique),
        "recommendations": unique,
        "sample_size_warning": "sample too small" if rows < 10 else "",
        "observations": [
            "Backtest simple debe guiar revision humana del motor.",
            "No se cambian pesos, thresholds ni señales automaticamente.",
        ],
        "notice": NOTICE,
        "do_not_change_automatically": True,
        "broker_execution": False,
        "creates_trigger_confirmed": False,
    }


def save_reports(data: dict[str, Any], *, json_out: Path, markdown_out: Path) -> dict[str, Any]:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    lines = [
        "# Analista - Engine feedback",
        "",
        f"- status: {data.get('status')}",
        f"- canonical_rows: {data.get('canonical_rows')}",
        f"- canonical_dates: {data.get('canonical_dates')}",
        f"- recommendation_count: {data.get('recommendation_count')}",
        f"- sample_size_warning: {data.get('sample_size_warning')}",
        f"- notice: {NOTICE}",
        "",
        "## Recommendations",
    ]
    for item in data.get("recommendations", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Guardrails", "", "- No automatic scoring changes.", "- No real order.", "- No trigger creation."])
    markdown_out.write_text("\n".join(lines), encoding="utf-8")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-json", default=str(ROOT / "reports" / "posttest_thesis_audit_latest.json"))
    parser.add_argument("--json-out", default=str(ROOT / "reports" / "engine_feedback_latest.json"))
    parser.add_argument("--markdown-out", default=str(ROOT / "reports" / "engine_feedback_latest.md"))
    args = parser.parse_args()
    data = collect_feedback(Path(args.audit_json))
    save_reports(data, json_out=Path(args.json_out), markdown_out=Path(args.markdown_out))
    print("=== ANALISTA ENGINE FEEDBACK ===")
    print(f"Status: {data.get('status')}")
    print(f"Canonical rows: {data.get('canonical_rows')}")
    print(f"Recommendations: {data.get('recommendation_count')}")
    return 0 if data.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
