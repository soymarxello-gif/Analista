from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


ALLOWED_RECOMMENDATION_TYPES = {
    "INSUFFICIENT_SAMPLE",
    "MONITOR_SCORE_BUCKET",
    "MONITOR_SETUP_TYPE",
    "MONITOR_CHECKLIST_STATUS",
    "MONITOR_OPTIONS_BIAS",
    "POSSIBLE_OVERWEIGHT",
    "POSSIBLE_UNDERWEIGHT",
    "NEED_MORE_TRADES",
    "NO_ACTION",
}

SCORE_BUCKET_GROUPS = {
    "final_trade_score_bucket",
    "checklist_score_bucket",
    "setup_quality_score_bucket",
    "institutional_score_bucket",
}

GROUP_RECOMMENDATION_TYPES = {
    "setup_type": "MONITOR_SETUP_TYPE",
    "checklist_status": "MONITOR_CHECKLIST_STATUS",
    "options_bias": "MONITOR_OPTIONS_BIAS",
}


def _safe_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(float(value))
    except Exception:
        return default


def _safe_float(value):
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _load_csv(path: Path) -> tuple[pd.DataFrame, str]:
    if not path.exists():
        return pd.DataFrame(), f"calibration_csv_not_found:{path}"
    try:
        return pd.read_csv(path), ""
    except Exception as exc:
        return pd.DataFrame(), f"calibration_csv_read_failed:{exc}"


def _load_json(path: Path) -> tuple[dict, str]:
    if not path.exists():
        return {}, f"calibration_json_not_found:{path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, f"calibration_json_read_failed:{exc}"
    return data if isinstance(data, dict) else {}, ""


def _overall_row(calibration_df: pd.DataFrame) -> dict:
    if calibration_df.empty or "group" not in calibration_df.columns:
        return {}
    mask = calibration_df["group"].fillna("").astype(str).str.upper() == "OVERALL"
    if not mask.any():
        return {}
    return calibration_df[mask].iloc[0].to_dict()


def _recommendation_type_for_group(group: str) -> str:
    if group in SCORE_BUCKET_GROUPS:
        return "MONITOR_SCORE_BUCKET"
    return GROUP_RECOMMENDATION_TYPES.get(group, "NO_ACTION")


def _build_recommendation(
    *,
    rec_type: str,
    observation: str,
    suggested_review_item: str,
    group: str = "",
    group_value: str = "",
    closed_trades: int = 0,
    avg_r_multiple=None,
    sample_size_warning: str = "",
) -> dict:
    if rec_type not in ALLOWED_RECOMMENDATION_TYPES:
        rec_type = "NO_ACTION"
    return {
        "type": rec_type,
        "group": group,
        "group_value": group_value,
        "closed_trades": int(closed_trades),
        "avg_r_multiple": avg_r_multiple if avg_r_multiple is not None else "",
        "sample_size_warning": sample_size_warning,
        "observation": observation,
        "suggested_review_item": suggested_review_item,
    }


def _infer_closed_trades(summary: dict, calibration_df: pd.DataFrame) -> int:
    value = summary.get("closed_trades")
    if value is not None:
        return _safe_int(value, 0)
    return _safe_int(_overall_row(calibration_df).get("closed_trades"), 0)


def _infer_sample_warning(summary: dict, calibration_df: pd.DataFrame, closed_trades: int) -> str:
    warning = _safe_text(summary.get("sample_size_warning"))
    if warning:
        return warning
    warning = _safe_text(_overall_row(calibration_df).get("sample_size_warning"))
    if warning:
        return warning
    return "sample too small" if closed_trades < 10 else ""


def build_calibration_recommendations(
    calibration_df: pd.DataFrame,
    calibration_summary: dict | None = None,
    *,
    csv_error: str = "",
    json_error: str = "",
    min_closed_trades: int = 10,
    min_group_trades: int = 5,
) -> dict:
    calibration_summary = calibration_summary or {}
    errors = [error for error in [csv_error, json_error] if error]

    closed_trades = _infer_closed_trades(calibration_summary, calibration_df)
    sample_size_warning = _infer_sample_warning(calibration_summary, calibration_df, closed_trades)

    recommendations: list[dict] = []
    insufficient_sample_notice = ""

    if errors:
        insufficient_sample_notice = (
            "Calibration report unavailable or incomplete; run trade_score_calibration first."
        )
        recommendations.append(
            _build_recommendation(
                rec_type="INSUFFICIENT_SAMPLE",
                closed_trades=closed_trades,
                sample_size_warning=sample_size_warning or "calibration unavailable",
                observation=insufficient_sample_notice,
                suggested_review_item="Need more complete calibration data before reviewing scores.",
            )
        )

    elif closed_trades < min_closed_trades:
        insufficient_sample_notice = "sample too small; need more trades before reviewing scoring weights."
        recommendations.append(
            _build_recommendation(
                rec_type="INSUFFICIENT_SAMPLE",
                closed_trades=closed_trades,
                sample_size_warning=sample_size_warning or "sample too small",
                observation="No statistical basis is available for score calibration yet.",
                suggested_review_item="Need more trades before considering any score-weight review.",
            )
        )
        recommendations.append(
            _build_recommendation(
                rec_type="NEED_MORE_TRADES",
                closed_trades=closed_trades,
                sample_size_warning=sample_size_warning or "sample too small",
                observation="Closed-trade sample remains below the minimum calibration threshold.",
                suggested_review_item="Continue logging closed outcomes and monitor this report after more trades.",
            )
        )

    else:
        if calibration_df.empty:
            recommendations.append(
                _build_recommendation(
                    rec_type="NO_ACTION",
                    closed_trades=closed_trades,
                    observation="Calibration summary has enough closed trades but no group rows were found.",
                    suggested_review_item="Review the calibration CSV format before drawing conclusions.",
                )
            )
        else:
            for _, row in calibration_df.iterrows():
                group = _safe_text(row.get("group"))
                group_value = _safe_text(row.get("group_value"))
                if group.upper() == "OVERALL" or not group or not group_value:
                    continue

                group_closed = _safe_int(row.get("closed_trades"), 0)
                avg_r = _safe_float(row.get("avg_r_multiple"))
                rec_type = _recommendation_type_for_group(group)
                if rec_type == "NO_ACTION":
                    continue

                if group_closed < min_group_trades:
                    recommendations.append(
                        _build_recommendation(
                            rec_type=rec_type,
                            group=group,
                            group_value=group_value,
                            closed_trades=group_closed,
                            avg_r_multiple=avg_r,
                            sample_size_warning="group sample too small",
                            observation=f"{group}={group_value} has insufficient sample size.",
                            suggested_review_item="Monitor this group; do not infer score changes yet.",
                        )
                    )
                    continue

                if avg_r is not None and avg_r <= -0.25 and rec_type == "MONITOR_SCORE_BUCKET":
                    recommendations.append(
                        _build_recommendation(
                            rec_type="POSSIBLE_OVERWEIGHT",
                            group=group,
                            group_value=group_value,
                            closed_trades=group_closed,
                            avg_r_multiple=avg_r,
                            observation=(
                                f"{group}={group_value} shows weak average R with enough sample to monitor."
                            ),
                            suggested_review_item=(
                                "Review whether this score bucket may be receiving too much emphasis."
                            ),
                        )
                    )
                elif avg_r is not None and avg_r >= 0.75 and rec_type == "MONITOR_SCORE_BUCKET":
                    recommendations.append(
                        _build_recommendation(
                            rec_type="POSSIBLE_UNDERWEIGHT",
                            group=group,
                            group_value=group_value,
                            closed_trades=group_closed,
                            avg_r_multiple=avg_r,
                            observation=(
                                f"{group}={group_value} shows strong average R with enough sample to monitor."
                            ),
                            suggested_review_item=(
                                "Review whether this score bucket may deserve closer human attention."
                            ),
                        )
                    )
                else:
                    recommendations.append(
                        _build_recommendation(
                            rec_type=rec_type,
                            group=group,
                            group_value=group_value,
                            closed_trades=group_closed,
                            avg_r_multiple=avg_r,
                            observation=f"{group}={group_value} should continue to be monitored.",
                            suggested_review_item="Review this group in future calibration runs; no automatic action.",
                        )
                    )

        if not recommendations:
            recommendations.append(
                _build_recommendation(
                    rec_type="NO_ACTION",
                    closed_trades=closed_trades,
                    observation="No actionable calibration observation was produced.",
                    suggested_review_item="Continue monitoring closed-trade outcomes.",
                )
            )

    status = "WARN" if errors or closed_trades < min_closed_trades else "PASS"
    observations = [item["observation"] for item in recommendations]
    suggested_review_items = [item["suggested_review_item"] for item in recommendations]

    return {
        "status": status,
        "closed_trades": int(closed_trades),
        "sample_size_warning": sample_size_warning,
        "recommendation_count": int(len(recommendations)),
        "observations": observations,
        "suggested_review_items": suggested_review_items,
        "do_not_change_automatically": True,
        "insufficient_sample_notice": insufficient_sample_notice,
        "recommendations": recommendations,
        "errors": errors,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_calibration_recommendations_markdown(data: dict) -> str:
    lines: list[str] = []
    lines.append("# Analista - calibration recommendations")
    lines.append("")
    lines.append("- Observational calibration review only.")
    lines.append("- No automatic scoring changes.")
    lines.append("- No thresholds, weights, scanner logic, or entry signals are modified.")
    lines.append(f"- generated_at: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- status: {data.get('status', 'UNKNOWN')}")
    lines.append(f"- closed_trades: {data.get('closed_trades', 0)}")
    lines.append(f"- sample_size_warning: {data.get('sample_size_warning', '')}")
    lines.append(f"- recommendation_count: {data.get('recommendation_count', 0)}")
    lines.append(f"- do_not_change_automatically: {data.get('do_not_change_automatically', True)}")
    notice = _safe_text(data.get("insufficient_sample_notice"))
    if notice:
        lines.append(f"- insufficient_sample_notice: {notice}")
    if data.get("errors"):
        lines.append(f"- errors: {', '.join(data.get('errors', []))}")
    lines.append("")

    lines.append("## Observations")
    lines.append("")
    observations = data.get("observations", []) or []
    if observations:
        for item in observations:
            lines.append(f"- {item}")
    else:
        lines.append("- No observations.")
    lines.append("")

    lines.append("## Suggested review items")
    lines.append("")
    review_items = data.get("suggested_review_items", []) or []
    if review_items:
        for item in review_items:
            lines.append(f"- {item}")
    else:
        lines.append("- No review items.")
    lines.append("")

    lines.append("## Recommendations")
    lines.append("")
    rows = data.get("recommendations", []) or []
    if not rows:
        lines.append("_Sin datos._")
    else:
        columns = [
            "type",
            "group",
            "group_value",
            "closed_trades",
            "avg_r_multiple",
            "sample_size_warning",
        ]
        lines.append("| " + " | ".join(columns) + " |")
        lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
        for row in rows:
            values = [str(row.get(col, "")).replace("\n", " ").replace("|", "\\|") for col in columns]
            lines.append("| " + " | ".join(values) + " |")
    lines.append("")

    lines.append("## Guardrails")
    lines.append("")
    lines.append("- Recommendations are review prompts, not system changes.")
    lines.append("- Insufficient samples must remain explicitly marked.")
    lines.append("- Closed-trade calibration must not create scanner signals.")

    return "\n".join(lines)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def save_calibration_recommendations_reports(
    *,
    calibration_csv: Path | None = None,
    calibration_json: Path | None = None,
    markdown_out: Path | None = None,
    json_out: Path | None = None,
    root: Path = ROOT,
) -> dict:
    calibration_csv = calibration_csv or root / "reports" / "trade_score_calibration_latest.csv"
    calibration_json = calibration_json or root / "reports" / "trade_score_calibration_latest.json"
    markdown_out = markdown_out or root / "reports" / "calibration_recommendations_latest.md"
    json_out = json_out or root / "reports" / "calibration_recommendations_latest.json"

    calibration_df, csv_error = _load_csv(calibration_csv)
    calibration_summary, json_error = _load_json(calibration_json)

    result = build_calibration_recommendations(
        calibration_df,
        calibration_summary,
        csv_error=csv_error,
        json_error=json_error,
    )
    result["calibration_csv"] = str(calibration_csv)
    result["calibration_json"] = str(calibration_json)
    result["markdown_out"] = str(markdown_out)
    result["json_out"] = str(json_out)

    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(build_calibration_recommendations_markdown(result), encoding="utf-8")
    _write_json(json_out, result)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera recomendaciones observacionales de calibracion.")
    parser.add_argument("--calibration-csv", default="reports/trade_score_calibration_latest.csv")
    parser.add_argument("--calibration-json", default="reports/trade_score_calibration_latest.json")
    parser.add_argument("--markdown-out", default="reports/calibration_recommendations_latest.md")
    parser.add_argument("--json-out", default="reports/calibration_recommendations_latest.json")
    args = parser.parse_args()

    result = save_calibration_recommendations_reports(
        calibration_csv=ROOT / args.calibration_csv,
        calibration_json=ROOT / args.calibration_json,
        markdown_out=ROOT / args.markdown_out,
        json_out=ROOT / args.json_out,
        root=ROOT,
    )

    print("=== ANALISTA CALIBRATION RECOMMENDATIONS ===")
    print(f"Status: {result['status']}")
    print(f"Closed trades: {result['closed_trades']}")
    print(f"Recommendation count: {result['recommendation_count']}")
    print(f"Sample size warning: {result.get('sample_size_warning', '')}")
    print(f"Markdown: {result['markdown_out']}")
    print(f"JSON: {result['json_out']}")
    if result.get("errors"):
        print(f"Errors: {', '.join(result['errors'])}")

    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
