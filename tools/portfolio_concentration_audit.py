from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
NOTICE = "read-only concentration context; no automatic trading"


def _counts(df: pd.DataFrame, column: str) -> dict[str, int]:
    if column not in df.columns or df.empty:
        return {}
    return df[column].fillna("MISSING").astype(str).replace("", "MISSING").value_counts().to_dict()


def _theme(row: pd.Series) -> str:
    text = " ".join(str(row.get(col, "")) for col in ["sector", "industry", "setup_type"]).lower()
    if any(token in text for token in ["semiconductor", "software", "technology"]):
        return "technology_growth"
    if any(token in text for token in ["bank", "financial", "capital markets", "insurance"]):
        return "rates_sensitive_financials"
    if any(token in text for token in ["oil", "gas", "energy"]):
        return "oil_sensitive"
    if any(token in text for token in ["biotech", "pharma", "medical"]):
        return "biotech_healthcare"
    return "general_equity"


def collect_audit(input_csv: Path) -> dict[str, Any]:
    if not input_csv.exists():
        return {
            "status": "WARN",
            "rows": 0,
            "issue": "input_missing",
            "notice": NOTICE,
            "broker_execution": False,
            "creates_trigger_confirmed": False,
        }
    try:
        df = pd.read_csv(input_csv)
    except Exception as exc:
        return {
            "status": "WARN",
            "rows": 0,
            "issue": f"input_read_error:{type(exc).__name__}",
            "notice": NOTICE,
            "broker_execution": False,
            "creates_trigger_confirmed": False,
        }
    if df.empty:
        return {
            "status": "PASS",
            "rows": 0,
            "sector_counts": {},
            "notice": NOTICE,
            "broker_execution": False,
            "creates_trigger_confirmed": False,
        }
    work = df.copy()
    work["theme"] = work.apply(_theme, axis=1)
    sector_counts = _counts(work, "sector")
    top_sector_weight = max(sector_counts.values()) / len(work) if sector_counts else 0.0
    warnings = []
    if top_sector_weight >= 0.4:
        warnings.append("sector_concentration_above_40pct")
    status = "WARN" if warnings else "PASS"
    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": int(len(work)),
        "input_csv": str(input_csv),
        "sector_counts": sector_counts,
        "industry_counts": _counts(work, "industry"),
        "setup_type_counts": _counts(work, "setup_type"),
        "scenario_status_counts": _counts(work, "scenario_status"),
        "options_bias_counts": _counts(work, "options_bias"),
        "quote_status_counts": _counts(work, "quote_status"),
        "sector_weekly_macd_state_counts": _counts(work, "sector_weekly_macd_state"),
        "sector_context_status_counts": _counts(work, "sector_context_status"),
        "theme_counts": _counts(work, "theme"),
        "top_sector_weight": round(float(top_sector_weight), 4),
        "warnings": warnings,
        "notice": NOTICE,
        "broker_execution": False,
        "creates_trigger_confirmed": False,
    }


def save_reports(data: dict[str, Any], *, json_out: Path, markdown_out: Path) -> dict[str, Any]:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    lines = [
        "# Analista - Portfolio concentration audit",
        "",
        f"- status: {data.get('status')}",
        f"- rows: {data.get('rows', 0)}",
        f"- top_sector_weight: {data.get('top_sector_weight', 0)}",
        f"- notice: {NOTICE}",
        "",
        "## Sector counts",
    ]
    for key, value in (data.get("sector_counts") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Theme counts"])
    for key, value in (data.get("theme_counts") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Sector weekly MACD"])
    for key, value in (data.get("sector_weekly_macd_state_counts") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Sector context"])
    for key, value in (data.get("sector_context_status_counts") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Guardrails", "", "- No automatic trading.", "- No broker execution."])
    markdown_out.write_text("\n".join(lines), encoding="utf-8")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", default=str(ROOT / "reports" / "manual_review_top.csv"))
    parser.add_argument("--json-out", default=str(ROOT / "reports" / "portfolio_concentration_latest.json"))
    parser.add_argument("--markdown-out", default=str(ROOT / "reports" / "portfolio_concentration_latest.md"))
    args = parser.parse_args()
    data = collect_audit(Path(args.input_csv))
    save_reports(data, json_out=Path(args.json_out), markdown_out=Path(args.markdown_out))
    print("=== ANALISTA PORTFOLIO CONCENTRATION AUDIT ===")
    print(f"Status: {data.get('status')}")
    print(f"Rows: {data.get('rows', 0)}")
    return 0 if data.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
