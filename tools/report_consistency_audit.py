from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


MANUAL_REQUIRED_COLUMNS = [
    "ticker",
    "rank",
    "signal",
    "recommendation",
    "quote_status",
    "execution_quote_quality",
    "setup_persistence_score",
    "setup_persistence_bucket",
]

TOP_REQUIRED_COLUMNS = [
    "_top_group",
    "ticker",
    "rank",
    "signal",
    "recommendation",
]

LIVE_RECHECK_REQUIRED_COLUMNS = [
    "ticker",
    "prior_recommendation",
    "recheck_decision",
    "live_quote_status",
    "live_execution_quote_quality",
]

CHECKLIST_REQUIRED_COLUMNS = [
    "ticker",
    "signal",
    "recommendation",
    "checklist_status",
    "checklist_score",
    "checklist_blockers",
    "checklist_warnings",
]

CHECKLIST_ALLOWED_STATUSES = {
    "BLOCKED",
    "NEEDS_LIVE_QUOTE_RECHECK",
    "REVIEW_MANUALLY",
    "HIGH_QUALITY_REVIEW",
}

CALIBRATION_REQUIRED_COLUMNS = [
    "group",
    "group_value",
    "closed_trades",
    "wins",
    "losses",
    "breakeven",
    "win_rate",
    "avg_r_multiple",
    "total_r_multiple",
    "sample_size_warning",
]

CALIBRATION_RECOMMENDATION_TYPES = {
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


def _safe_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _missing_columns(df: pd.DataFrame, required: list[str]) -> list[str]:
    return [col for col in required if col not in df.columns]


def _empty_text_count(df: pd.DataFrame, col: str) -> int:
    if col not in df.columns:
        return len(df)
    return int(df[col].apply(_safe_text).eq("").sum())


def _load_csv(path: Path) -> tuple[pd.DataFrame, str]:
    if not path.exists():
        return pd.DataFrame(), f"missing_file:{path}"

    try:
        return pd.read_csv(path), ""
    except Exception as exc:
        return pd.DataFrame(), f"read_error:{path}:{exc}"


def _load_json(path: Path) -> tuple[dict, str]:
    if not path.exists():
        return {}, f"missing_file:{path}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except Exception as exc:
        return {}, f"read_error:{path}:{exc}"


def audit_manual_review_latest(path: Path) -> dict:
    df, error = _load_csv(path)

    result = {
        "name": "manual_review_latest",
        "path": str(path),
        "rows": int(len(df)),
        "issues": [],
        "warnings": [],
    }

    if error:
        result["issues"].append(error)
        return result

    if df.empty:
        result["warnings"].append("manual_review_latest_empty")
        return result

    missing = _missing_columns(df, MANUAL_REQUIRED_COLUMNS)
    if missing:
        result["issues"].append("missing_columns:" + ",".join(missing))

    if "recommendation" in df.columns:
        empty_count = _empty_text_count(df, "recommendation")
        if empty_count > 0:
            result["issues"].append(f"empty_recommendation_rows:{empty_count}")

    if "setup_persistence_score" in df.columns:
        missing_persistence = int(pd.to_numeric(df["setup_persistence_score"], errors="coerce").isna().sum())
        if missing_persistence > 0:
            result["warnings"].append(f"missing_setup_persistence_score_rows:{missing_persistence}")

    if "rank" in df.columns:
        duplicated_rank_count = int(df["rank"].duplicated().sum())
        if duplicated_rank_count > 0:
            result["warnings"].append(f"duplicated_rank_rows:{duplicated_rank_count}")

    return result


def audit_manual_review_top(top_path: Path, manual_path: Path) -> dict:
    top_df, top_error = _load_csv(top_path)
    manual_df, manual_error = _load_csv(manual_path)

    result = {
        "name": "manual_review_top",
        "path": str(top_path),
        "rows": int(len(top_df)),
        "issues": [],
        "warnings": [],
    }

    if top_error:
        result["issues"].append(top_error)
        return result

    if top_df.empty:
        result["warnings"].append("manual_review_top_empty")
        return result

    missing = _missing_columns(top_df, TOP_REQUIRED_COLUMNS)
    if missing:
        result["issues"].append("missing_columns:" + ",".join(missing))

    empty_recommendation = _empty_text_count(top_df, "recommendation")
    if empty_recommendation > 0:
        result["issues"].append(f"empty_recommendation_rows:{empty_recommendation}")

    if manual_error:
        result["warnings"].append(f"manual_reference_unavailable:{manual_error}")
        return result

    if manual_df.empty:
        result["warnings"].append("manual_reference_empty")
        return result

    required_compare = {"ticker", "rank", "signal"}
    if required_compare.issubset(set(top_df.columns)) and required_compare.issubset(set(manual_df.columns)):
        top_cmp = top_df[["ticker", "rank", "signal"]].copy()
        manual_cmp = manual_df[["ticker", "rank", "signal"]].copy()

        top_cmp["ticker"] = top_cmp["ticker"].astype(str).str.upper()
        manual_cmp["ticker"] = manual_cmp["ticker"].astype(str).str.upper()

        merged = top_cmp.merge(
            manual_cmp,
            on="ticker",
            how="left",
            suffixes=("_top", "_manual"),
            validate="many_to_one",
        )

        missing_reference = int(merged["rank_manual"].isna().sum())
        if missing_reference > 0:
            result["issues"].append(f"top_tickers_missing_in_manual:{missing_reference}")

        rank_mismatch = int(
            (
                merged["rank_manual"].notna()
                & (merged["rank_top"].astype(str) != merged["rank_manual"].astype(str))
            ).sum()
        )
        if rank_mismatch > 0:
            result["issues"].append(f"rank_mismatch_vs_manual:{rank_mismatch}")

        signal_mismatch = int(
            (
                merged["signal_manual"].notna()
                & (
                    merged["signal_top"].astype(str).str.upper()
                    != merged["signal_manual"].astype(str).str.upper()
                )
            ).sum()
        )
        if signal_mismatch > 0:
            result["issues"].append(f"signal_mismatch_vs_manual:{signal_mismatch}")
    else:
        result["warnings"].append("comparison_skipped_missing_rank_signal_or_ticker")

    return result


def audit_live_quote_recheck(path: Path) -> dict:
    df, error = _load_csv(path)

    result = {
        "name": "live_quote_recheck_latest",
        "path": str(path),
        "rows": int(len(df)),
        "issues": [],
        "warnings": [],
        "optional": True,
    }

    if error:
        result["warnings"].append(f"optional_live_recheck_unavailable:{error}")
        return result

    if df.empty:
        result["warnings"].append("optional_live_recheck_empty")
        return result

    missing = _missing_columns(df, LIVE_RECHECK_REQUIRED_COLUMNS)
    if missing:
        result["issues"].append("missing_columns:" + ",".join(missing))

    decision_col = "recheck_decision" if "recheck_decision" in df.columns else "live_recheck_decision"
    if decision_col in df.columns:
        allowed = {
            "KEEP_RECHECK",
            "WATCHLIST_MONITOR",
            "EXECUTION_OK_REVIEW_MANUALLY",
            "AVOID_EXECUTION_RISK",
            "DATA_UNAVAILABLE",
        }
       
        invalid_values = [
            value
            for value in df[decision_col].fillna("").astype(str).unique().tolist()
            if value not in allowed
        ]
        if invalid_values:
            result["issues"].append("invalid_recheck_decision:" + ",".join(invalid_values))

    return result


def audit_trade_decision_checklist(path: Path) -> dict:
    df, error = _load_csv(path)

    result = {
        "name": "trade_decision_checklist_latest",
        "path": str(path),
        "rows": int(len(df)),
        "issues": [],
        "warnings": [],
        "optional": True,
    }

    if error:
        result["warnings"].append(f"optional_trade_decision_checklist_unavailable:{error}")
        return result

    if df.empty:
        result["warnings"].append("optional_trade_decision_checklist_empty")
        return result

    missing = _missing_columns(df, CHECKLIST_REQUIRED_COLUMNS)
    if missing:
        result["issues"].append("missing_columns:" + ",".join(missing))

    if "checklist_status" in df.columns:
        invalid_values = [
            value
            for value in df["checklist_status"].fillna("").astype(str).unique().tolist()
            if value not in CHECKLIST_ALLOWED_STATUSES
        ]
        if invalid_values:
            result["issues"].append("invalid_checklist_status:" + ",".join(invalid_values))

    return result


def audit_trade_candidate_cards(path: Path) -> dict:
    data, error = _load_json(path)

    cards = data.get("cards", []) if isinstance(data, dict) else []
    result = {
        "name": "trade_candidate_cards_latest",
        "path": str(path),
        "rows": int(data.get("rows", 0) or 0) if isinstance(data, dict) else 0,
        "issues": [],
        "warnings": [],
        "optional": True,
    }

    if error:
        result["warnings"].append(f"optional_trade_candidate_cards_unavailable:{error}")
        return result

    if not isinstance(cards, list):
        result["issues"].append("cards_not_list")
        return result

    if int(data.get("rows", 0) or 0) != len(cards):
        result["issues"].append("rows_mismatch_cards_length")

    invalid_statuses = [
        str(card.get("checklist_status", ""))
        for card in cards
        if str(card.get("checklist_status", "")) not in CHECKLIST_ALLOWED_STATUSES
    ]
    if invalid_statuses:
        result["issues"].append("invalid_card_checklist_status:" + ",".join(sorted(set(invalid_statuses))))

    disabled_buy_signal = "_".join(["BUY", "SETUP", "ACTIVE"])
    rendered = json.dumps(cards, ensure_ascii=False).upper()
    if disabled_buy_signal in rendered:
        result["issues"].append("disabled_buy_signal_present")

    return result


def audit_trade_score_calibration(csv_path: Path, json_path: Path) -> dict:
    df, csv_error = _load_csv(csv_path)
    data, json_error = _load_json(json_path)

    result = {
        "name": "trade_score_calibration_latest",
        "path": str(csv_path),
        "rows": int(len(df)),
        "issues": [],
        "warnings": [],
        "optional": True,
    }

    if csv_error:
        result["warnings"].append(f"optional_trade_score_calibration_csv_unavailable:{csv_error}")
        return result

    missing = _missing_columns(df, CALIBRATION_REQUIRED_COLUMNS)
    if missing:
        result["issues"].append("missing_columns:" + ",".join(missing))

    if json_error:
        result["warnings"].append(f"optional_trade_score_calibration_json_unavailable:{json_error}")
        return result

    if "status" not in data:
        result["issues"].append("json_missing_status")

    if "closed_trades" not in data:
        result["issues"].append("json_missing_closed_trades")

    return result


def audit_calibration_recommendations(path: Path) -> dict:
    data, error = _load_json(path)

    recommendations = data.get("recommendations", []) if isinstance(data, dict) else []
    result = {
        "name": "calibration_recommendations_latest",
        "path": str(path),
        "rows": int(data.get("recommendation_count", 0) or 0) if isinstance(data, dict) else 0,
        "issues": [],
        "warnings": [],
        "optional": True,
    }

    if error:
        result["warnings"].append(f"optional_calibration_recommendations_unavailable:{error}")
        return result

    for required_key in [
        "status",
        "closed_trades",
        "sample_size_warning",
        "recommendation_count",
        "observations",
        "suggested_review_items",
        "do_not_change_automatically",
        "insufficient_sample_notice",
    ]:
        if required_key not in data:
            result["issues"].append(f"json_missing_{required_key}")

    if data.get("do_not_change_automatically") is not True:
        result["issues"].append("automatic_change_guard_missing")

    if not isinstance(recommendations, list):
        result["issues"].append("recommendations_not_list")
        return result

    if int(data.get("recommendation_count", 0) or 0) != len(recommendations):
        result["issues"].append("recommendation_count_mismatch")

    invalid_types = [
        str(item.get("type", ""))
        for item in recommendations
        if str(item.get("type", "")) not in CALIBRATION_RECOMMENDATION_TYPES
    ]
    if invalid_types:
        result["issues"].append("invalid_recommendation_type:" + ",".join(sorted(set(invalid_types))))

    disabled_buy_signal = "_".join(["BUY", "SETUP", "ACTIVE"])
    rendered = json.dumps(data, ensure_ascii=False).upper()
    if disabled_buy_signal in rendered:
        result["issues"].append("disabled_buy_signal_present")
    if "TRIGGER_CONFIRMED" in rendered:
        result["issues"].append("entry_signal_present")

    return result


def build_report_consistency_audit(
    reports_dir: Path,
) -> dict:
    manual_path = reports_dir / "manual_review_latest.csv"
    top_path = reports_dir / "manual_review_top.csv"
    live_path = reports_dir / "live_quote_recheck_latest.csv"
    checklist_path = reports_dir / "trade_decision_checklist_latest.csv"
    cards_path = reports_dir / "trade_candidate_cards_latest.json"
    calibration_csv_path = reports_dir / "trade_score_calibration_latest.csv"
    calibration_json_path = reports_dir / "trade_score_calibration_latest.json"
    calibration_recommendations_path = reports_dir / "calibration_recommendations_latest.json"

    checks = [
        audit_manual_review_latest(manual_path),
        audit_manual_review_top(top_path, manual_path),
        audit_live_quote_recheck(live_path),
        audit_trade_decision_checklist(checklist_path),
        audit_trade_candidate_cards(cards_path),
        audit_trade_score_calibration(calibration_csv_path, calibration_json_path),
        audit_calibration_recommendations(calibration_recommendations_path),
    ]

    issues = []
    warnings = []

    for check in checks:
        for issue in check.get("issues", []):
            issues.append(f"{check['name']}:{issue}")
        for warning in check.get("warnings", []):
            warnings.append(f"{check['name']}:{warning}")

    status = "PASS"
    if issues:
        status = "FAIL"
    elif warnings:
        status = "WARN"

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "checks": checks,
        "issues": issues,
        "warnings": warnings,
    }


def build_markdown(result: dict) -> str:
    lines: list[str] = []

    lines.append("# Analista — report consistency audit")
    lines.append("")
    lines.append(f"- timestamp: {result['timestamp']}")
    lines.append(f"- status: {result['status']}")
    lines.append(f"- issues: {len(result.get('issues', []))}")
    lines.append(f"- warnings: {len(result.get('warnings', []))}")
    lines.append("")

    lines.append("## Checks")
    lines.append("")

    for check in result.get("checks", []):
        lines.append(f"### {check['name']}")
        lines.append("")
        lines.append(f"- path: {check['path']}")
        lines.append(f"- rows: {check['rows']}")

        if check.get("issues"):
            lines.append("- issues:")
            for issue in check["issues"]:
                lines.append(f"  - {issue}")
        else:
            lines.append("- issues: none")

        if check.get("warnings"):
            lines.append("- warnings:")
            for warning in check["warnings"]:
                lines.append(f"  - {warning}")
        else:
            lines.append("- warnings: none")

        lines.append("")

    return "\n".join(lines)


def save_report_consistency_audit(
    reports_dir: Path,
    json_out: Path,
    markdown_out: Path,
) -> dict:
    result = build_report_consistency_audit(reports_dir=reports_dir)

    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    json_out.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    markdown_out.write_text(build_markdown(result), encoding="utf-8")

    result["json_out"] = str(json_out)
    result["markdown_out"] = str(markdown_out)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Audita consistencia de reportes derivados.")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--json-out", default="reports/report_consistency_latest.json")
    parser.add_argument("--markdown-out", default="reports/report_consistency_latest.md")
    args = parser.parse_args()

    result = save_report_consistency_audit(
        reports_dir=ROOT / args.reports_dir,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
    )

    print("=== ANALISTA REPORT CONSISTENCY AUDIT ===")
    print(f"Status: {result['status']}")
    print(f"Issues: {len(result['issues'])}")
    print(f"Warnings: {len(result['warnings'])}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")

    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
