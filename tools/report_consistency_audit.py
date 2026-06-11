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
    "recommendation",
    "live_recheck_decision",
    "live_quote_status",
    "live_execution_quote_quality",
]


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

    empty_recommendation = _empty_text_count(df, "recommendation")
    if empty_recommendation > 0:
        result["issues"].append(f"empty_recommendation_rows:{empty_recommendation}")

    if "live_recheck_decision" in df.columns:
        allowed = {
            "QUOTE_OK_FOR_MANUAL_REVIEW",
            "QUOTE_STILL_UNCONFIRMED",
            "QUOTE_FETCH_FAILED",
        }
       
        invalid_values = [
            value
            for value in df["live_recheck_decision"].fillna("").astype(str).unique().tolist()
            if value not in allowed
        ]
        if invalid_values:
            result["issues"].append("invalid_live_recheck_decision:" + ",".join(invalid_values))

    return result


def build_report_consistency_audit(
    reports_dir: Path,
) -> dict:
    manual_path = reports_dir / "manual_review_latest.csv"
    top_path = reports_dir / "manual_review_top.csv"
    live_path = reports_dir / "live_quote_recheck_latest.csv"

    checks = [
        audit_manual_review_latest(manual_path),
        audit_manual_review_top(top_path, manual_path),
        audit_live_quote_recheck(live_path),
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