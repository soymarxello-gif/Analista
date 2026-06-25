from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _counts(df: pd.DataFrame, column: str) -> dict:
    if df.empty or column not in df.columns:
        return {}
    return (
        df[column]
        .fillna("MISSING")
        .astype(str)
        .replace("", "MISSING")
        .value_counts()
        .to_dict()
    )


def _contradiction_counts(df: pd.DataFrame) -> dict:
    counter: Counter[str] = Counter()
    if "scenario_contradictions" not in df.columns:
        return {}
    for value in df["scenario_contradictions"].fillna("").astype(str):
        try:
            items = json.loads(value)
        except Exception:
            items = [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]
        if isinstance(items, list):
            counter.update(str(item) for item in items if str(item).strip())
    return dict(counter.most_common())


def build_scenario_audit(df: pd.DataFrame) -> dict:
    selected = df[
        df.get("deep_analysis_selected", pd.Series(False, index=df.index))
        .astype(str)
        .str.lower()
        .isin({"true", "1", "yes"})
    ].copy() if not df.empty else pd.DataFrame()
    statuses = _counts(selected, "scenario_status")
    contradictions = _contradiction_counts(selected)
    guardrail_applied = (
        selected.get("scenario_guardrail_applied", pd.Series(False, index=selected.index))
        .astype(str)
        .str.lower()
        .isin({"true", "1", "yes"})
    )
    eligible_for_backtest = (
        selected.get("scenario_eligible_for_backtest", pd.Series(False, index=selected.index))
        .astype(str)
        .str.lower()
        .isin({"true", "1", "yes"})
    )
    guardrail_available = "scenario_guardrail_applied" in selected.columns
    recommendations: list[str] = []
    if statuses.get("LATE_ENTRY_OVEREXTENDED", 0):
        recommendations.append("Review late-entry and extension guards; do not chase valid structures.")
    if statuses.get("WEAK_MOMENTUM", 0):
        recommendations.append("Require momentum stabilization before advancing weak scenarios.")
    if statuses.get("WAIT_FOR_CONFIRMATION", 0):
        recommendations.append("Keep unconfirmed setups in monitoring until their explicit trigger appears.")
    if contradictions.get("no_bullish_rejection_confirmation", 0):
        recommendations.append("Pullbacks need rejection/recovery evidence rather than proximity to a moving average alone.")
    if contradictions.get("breakout_volume_below_1_3", 0):
        recommendations.append("Breakouts below 1.3 relative volume should remain unconfirmed.")

    target = 50
    status = "PASS" if 40 <= len(selected) <= 60 else "WARN"
    return {
        "status": status,
        "rows": int(len(df)),
        "deep_analysis_rows": int(len(selected)),
        "target_deep_analysis_rows": target,
        "within_target_band": bool(40 <= len(selected) <= 60),
        "scenario_status": statuses,
        "momentum_state": _counts(selected, "momentum_state"),
        "extension_state": _counts(selected, "extension_state"),
        "engine_recommendation": _counts(selected, "engine_recommendation"),
        "scenario_operability": _counts(selected, "scenario_operability"),
        "guardrail_applied_rows": int(guardrail_applied.sum()),
        "backtest_eligible_rows": int(eligible_for_backtest.sum()),
        "top_contradictions": contradictions,
        "recommendations": recommendations,
        "shadow_mode": not guardrail_available,
        "guardrail_mode": "CONSERVATIVE_DEMOTION_ONLY" if guardrail_available else "SHADOW",
        "signals_modified": bool(guardrail_applied.any()),
        "automatic_promotions": False,
        "automatic_changes": False,
    }


def build_markdown(report: dict) -> str:
    lines = [
        "# Analista - Scenario engine audit",
        "",
        f"- status: {report.get('status')}",
        f"- rows: {report.get('rows')}",
        f"- deep_analysis_rows: {report.get('deep_analysis_rows')}",
        f"- target_deep_analysis_rows: {report.get('target_deep_analysis_rows')}",
        f"- within_target_band: {report.get('within_target_band')}",
        f"- shadow_mode: {report.get('shadow_mode')}",
        f"- guardrail_mode: {report.get('guardrail_mode')}",
        f"- guardrail_applied_rows: {report.get('guardrail_applied_rows')}",
        f"- backtest_eligible_rows: {report.get('backtest_eligible_rows')}",
        "",
    ]
    for title, key in [
        ("Scenario status", "scenario_status"),
        ("Momentum state", "momentum_state"),
        ("Extension state", "extension_state"),
        ("Engine recommendation", "engine_recommendation"),
        ("Scenario operability", "scenario_operability"),
        ("Top contradictions", "top_contradictions"),
    ]:
        lines.extend([f"## {title}", ""])
        values = report.get(key, {}) or {}
        lines.extend([f"- {name}: {count}" for name, count in values.items()] or ["- none"])
        lines.append("")
    lines.extend(["## Recommendations", ""])
    lines.extend([f"- {item}" for item in report.get("recommendations", [])] or ["- none"])
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Conservative demotion only; scenarios never promote signals.",
            "- No score, threshold or execution-quality changes.",
        ]
    )
    return "\n".join(lines)


def save_reports(
    *,
    input_csv: Path,
    json_out: Path,
    markdown_out: Path,
) -> dict:
    try:
        df = pd.read_csv(input_csv) if input_csv.exists() else pd.DataFrame()
        report = build_scenario_audit(df)
        if not input_csv.exists():
            report["status"] = "WARN"
            report["error"] = "input_csv_not_found"
    except Exception as exc:
        report = build_scenario_audit(pd.DataFrame())
        report["status"] = "WARN"
        report["error"] = f"input_read_failed:{exc}"
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_out.write_text(build_markdown(report), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita el motor de escenarios y su guardrail conservador.")
    parser.add_argument("--input-csv", default="reports/latest_scan_audited.csv")
    parser.add_argument("--json-out", default="reports/scenario_engine_audit_latest.json")
    parser.add_argument("--markdown-out", default="reports/scenario_engine_audit_latest.md")
    args = parser.parse_args()
    report = save_reports(
        input_csv=Path(args.input_csv),
        json_out=Path(args.json_out),
        markdown_out=Path(args.markdown_out),
    )
    print("=== ANALISTA SCENARIO ENGINE AUDIT ===")
    print(f"Status: {report.get('status')}")
    print(f"Deep analysis rows: {report.get('deep_analysis_rows')}")
    print(f"Within target band: {report.get('within_target_band')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
