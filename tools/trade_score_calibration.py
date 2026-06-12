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


CALIBRATION_COLUMNS = [
    "group",
    "group_value",
    "closed_trades",
    "wins",
    "losses",
    "breakeven",
    "win_rate",
    "avg_pnl_pct",
    "median_pnl_pct",
    "avg_r_multiple",
    "median_r_multiple",
    "total_r_multiple",
    "best_trade_r",
    "worst_trade_r",
    "avg_holding_days",
    "sample_size_warning",
]

GROUP_COLUMNS = [
    "checklist_status",
    "setup_type",
    "signal",
    "recommendation",
    "final_trade_score_bucket",
    "checklist_score_bucket",
    "setup_quality_score_bucket",
    "institutional_score_bucket",
    "options_bias",
    "options_confidence",
    "sector",
]


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


def _safe_float(value, default=None):
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _round_or_blank(value, decimals: int = 6):
    if value is None or pd.isna(value):
        return ""
    return round(float(value), decimals)


def _first_existing(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def resolve_default_input(root: Path = ROOT) -> Path:
    data_path = root / "data" / "trade_outcomes.csv"
    reports_path = root / "reports" / "trade_outcomes.csv"
    return data_path if data_path.exists() else reports_path


def load_trade_outcomes(path: Path) -> tuple[pd.DataFrame, str]:
    if not path.exists():
        return pd.DataFrame(), "input_csv_not_found"
    try:
        return pd.read_csv(path), ""
    except Exception as exc:
        return pd.DataFrame(), f"input_csv_read_failed:{exc}"


def score_bucket(value) -> str:
    score = _safe_float(value, None)
    if score is None:
        return "MISSING"
    if score >= 85:
        return "85_PLUS"
    if score >= 75:
        return "75_TO_84"
    if score >= 65:
        return "65_TO_74"
    return "BELOW_65"


def _series_or_missing(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    col = _first_existing(df, candidates)
    if col is None:
        return pd.Series(["MISSING"] * len(df), index=df.index)
    return df[col].apply(lambda value: _safe_text(value).upper() or "MISSING")


def _numeric_series_or_missing(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    col = _first_existing(df, candidates)
    if col is None:
        return pd.Series([None] * len(df), index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def filter_closed_trades(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "status" not in df.columns:
        return pd.DataFrame()

    status = df["status"].fillna("").astype(str).str.upper()
    closed = df[status == "CLOSED"].copy()
    if closed.empty:
        return pd.DataFrame()

    closed["outcome_norm"] = _series_or_missing(closed, ["outcome"])
    closed["pnl_pct_num"] = _numeric_series_or_missing(closed, ["pnl_pct", "pnl_percent"])
    closed["r_multiple_num"] = _numeric_series_or_missing(closed, ["r_multiple", "r"])

    entry_dates = pd.to_datetime(closed.get("entry_date"), errors="coerce")
    exit_dates = pd.to_datetime(closed.get("exit_date"), errors="coerce")
    closed["holding_days_num"] = (exit_dates - entry_dates).dt.days

    closed["signal"] = _series_or_missing(closed, ["signal", "source_signal"])
    closed["recommendation"] = _series_or_missing(
        closed,
        ["recommendation", "source_recommendation"],
    )
    closed["setup_type"] = _series_or_missing(closed, ["setup_type", "source_setup_type"])
    closed["checklist_status"] = _series_or_missing(
        closed,
        ["checklist_status", "source_checklist_status"],
    )
    closed["options_bias"] = _series_or_missing(closed, ["options_bias", "source_options_bias"])
    closed["options_confidence"] = _series_or_missing(
        closed,
        ["options_confidence", "source_options_confidence"],
    )
    closed["sector"] = _series_or_missing(closed, ["sector", "source_sector"])

    bucket_sources = {
        "final_trade_score_bucket": ["final_trade_score", "source_final_trade_score"],
        "checklist_score_bucket": ["checklist_score", "source_checklist_score"],
        "setup_quality_score_bucket": ["setup_quality_score", "source_setup_quality_score"],
        "institutional_score_bucket": ["institutional_score", "source_institutional_score"],
    }

    for bucket_col, source_cols in bucket_sources.items():
        source = _first_existing(closed, source_cols)
        if source is None:
            closed[bucket_col] = "MISSING"
        else:
            closed[bucket_col] = closed[source].apply(score_bucket)

    return closed


def calculate_metrics(closed_df: pd.DataFrame, group: str, group_value: str) -> dict:
    sample_warning = "sample too small" if len(closed_df) < 10 else ""

    if closed_df.empty:
        return {
            "group": group,
            "group_value": group_value,
            "closed_trades": 0,
            "wins": 0,
            "losses": 0,
            "breakeven": 0,
            "win_rate": "",
            "avg_pnl_pct": "",
            "median_pnl_pct": "",
            "avg_r_multiple": "",
            "median_r_multiple": "",
            "total_r_multiple": "",
            "best_trade_r": "",
            "worst_trade_r": "",
            "avg_holding_days": "",
            "sample_size_warning": sample_warning,
        }

    outcome = closed_df["outcome_norm"].fillna("").astype(str).str.upper()
    wins = int((outcome == "WIN").sum())
    losses = int((outcome == "LOSS").sum())
    breakeven = int((outcome == "BREAKEVEN").sum())
    decisive = wins + losses

    pnl = pd.to_numeric(closed_df["pnl_pct_num"], errors="coerce")
    r_multiple = pd.to_numeric(closed_df["r_multiple_num"], errors="coerce")
    holding_days = pd.to_numeric(closed_df["holding_days_num"], errors="coerce")

    return {
        "group": group,
        "group_value": group_value,
        "closed_trades": int(len(closed_df)),
        "wins": wins,
        "losses": losses,
        "breakeven": breakeven,
        "win_rate": _round_or_blank(wins / decisive if decisive else None),
        "avg_pnl_pct": _round_or_blank(pnl.mean()),
        "median_pnl_pct": _round_or_blank(pnl.median()),
        "avg_r_multiple": _round_or_blank(r_multiple.mean()),
        "median_r_multiple": _round_or_blank(r_multiple.median()),
        "total_r_multiple": _round_or_blank(r_multiple.sum()),
        "best_trade_r": _round_or_blank(r_multiple.max()),
        "worst_trade_r": _round_or_blank(r_multiple.min()),
        "avg_holding_days": _round_or_blank(holding_days.mean()),
        "sample_size_warning": sample_warning,
    }


def build_trade_score_calibration_dataframe(outcomes_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    closed = filter_closed_trades(outcomes_df)

    if closed.empty:
        empty = pd.DataFrame(
            [
                calculate_metrics(
                    pd.DataFrame(),
                    group="OVERALL",
                    group_value="ALL_CLOSED",
                )
            ]
        )
        return empty[CALIBRATION_COLUMNS], closed

    rows = [
        calculate_metrics(
            closed,
            group="OVERALL",
            group_value="ALL_CLOSED",
        )
    ]

    for col in GROUP_COLUMNS:
        temp = closed.copy()
        temp[col] = temp[col].apply(lambda value: _safe_text(value).upper() or "MISSING")
        for value, group_df in temp.groupby(col, dropna=False):
            rows.append(calculate_metrics(group_df, group=col, group_value=str(value)))

    out = pd.DataFrame(rows)
    for col in CALIBRATION_COLUMNS:
        if col not in out.columns:
            out[col] = ""

    out = out[CALIBRATION_COLUMNS]
    out["_group_rank"] = out["group"].apply(lambda value: 0 if value == "OVERALL" else 1)
    out["_avg_r_sort"] = pd.to_numeric(out["avg_r_multiple"], errors="coerce").fillna(-999)
    out = out.sort_values(
        ["_group_rank", "group", "closed_trades", "_avg_r_sort", "group_value"],
        ascending=[True, True, False, False, True],
    ).drop(columns=["_group_rank", "_avg_r_sort"])

    return out.reset_index(drop=True), closed


def _df_to_markdown_table(df: pd.DataFrame, max_rows: int = 50) -> str:
    if df.empty:
        return "_Sin datos._"

    display = df.head(max_rows).copy()
    lines = []
    lines.append("| " + " | ".join(display.columns) + " |")
    lines.append("| " + " | ".join(["---"] * len(display.columns)) + " |")
    for _, row in display.iterrows():
        values = []
        for col in display.columns:
            value = row.get(col)
            if pd.isna(value):
                value = ""
            values.append(str(value).replace("\n", " ").replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def build_trade_score_calibration_markdown(
    calibration_df: pd.DataFrame,
    *,
    status: str,
    closed_trades: int,
    sample_size_warning: str,
    error: str = "",
) -> str:
    lines: list[str] = []
    lines.append("# Analista - trade score calibration")
    lines.append("")
    lines.append("- Analisis de trades cerrados. No modifica pesos, thresholds, scanner ni senales.")
    lines.append(f"- generated_at: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- status: {status}")
    lines.append(f"- closed_trades: {closed_trades}")
    if sample_size_warning:
        lines.append(f"- sample_size_warning: {sample_size_warning}")
    if error:
        lines.append(f"- error: {error}")
    lines.append("")

    overall = calibration_df[calibration_df["group"] == "OVERALL"].copy()
    lines.append("## Overall")
    lines.append("")
    lines.append(_df_to_markdown_table(overall))
    lines.append("")

    for group_name in GROUP_COLUMNS:
        group_df = calibration_df[calibration_df["group"] == group_name].copy()
        lines.append(f"## {group_name}")
        lines.append("")
        lines.append(_df_to_markdown_table(group_df))
        lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("- Calibration is observational only.")
    lines.append("- No automatic scoring changes are proposed.")
    lines.append("- No trade entry recommendation is generated.")

    return "\n".join(lines)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def save_trade_score_calibration_reports(
    outcomes_path: Path | None = None,
    *,
    csv_out: Path | None = None,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
    root: Path = ROOT,
) -> dict:
    outcomes_path = outcomes_path or resolve_default_input(root)
    csv_out = csv_out or root / "reports" / "trade_score_calibration_latest.csv"
    json_out = json_out or root / "reports" / "trade_score_calibration_latest.json"
    markdown_out = markdown_out or root / "reports" / "trade_score_calibration_latest.md"

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    outcomes_df, error = load_trade_outcomes(outcomes_path)
    calibration_df, closed = build_trade_score_calibration_dataframe(outcomes_df)

    closed_trades = int(len(closed))
    sample_size_warning = "sample too small" if closed_trades < 10 else ""
    status = "WARN" if error or sample_size_warning else "PASS"

    calibration_df.to_csv(csv_out, index=False)

    markdown_out.write_text(
        build_trade_score_calibration_markdown(
            calibration_df,
            status=status,
            closed_trades=closed_trades,
            sample_size_warning=sample_size_warning,
            error=error,
        ),
        encoding="utf-8",
    )

    overall = calibration_df[calibration_df["group"] == "OVERALL"].iloc[0].to_dict()
    result = {
        "status": status,
        "rows": int(len(calibration_df)),
        "closed_trades": closed_trades,
        "wins": int(overall.get("wins", 0) or 0),
        "losses": int(overall.get("losses", 0) or 0),
        "breakeven": int(overall.get("breakeven", 0) or 0),
        "win_rate": overall.get("win_rate", ""),
        "avg_pnl_pct": overall.get("avg_pnl_pct", ""),
        "median_pnl_pct": overall.get("median_pnl_pct", ""),
        "avg_r_multiple": overall.get("avg_r_multiple", ""),
        "median_r_multiple": overall.get("median_r_multiple", ""),
        "total_r_multiple": overall.get("total_r_multiple", ""),
        "best_trade_r": overall.get("best_trade_r", ""),
        "worst_trade_r": overall.get("worst_trade_r", ""),
        "avg_holding_days": overall.get("avg_holding_days", ""),
        "sample_size_warning": sample_size_warning,
        "error": error,
        "outcomes_path": str(outcomes_path),
        "csv_out": str(csv_out),
        "json_out": str(json_out),
        "markdown_out": str(markdown_out),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    _write_json(json_out, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibra scores contra trades cerrados.")
    parser.add_argument("--outcomes-path", default=None)
    parser.add_argument("--csv-out", default="reports/trade_score_calibration_latest.csv")
    parser.add_argument("--json-out", default="reports/trade_score_calibration_latest.json")
    parser.add_argument("--markdown-out", default="reports/trade_score_calibration_latest.md")
    args = parser.parse_args()

    result = save_trade_score_calibration_reports(
        outcomes_path=ROOT / args.outcomes_path if args.outcomes_path else None,
        csv_out=ROOT / args.csv_out,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
        root=ROOT,
    )

    print("=== ANALISTA TRADE SCORE CALIBRATION ===")
    print(f"Status: {result['status']}")
    print(f"Closed trades: {result['closed_trades']}")
    print(f"Win rate: {result.get('win_rate', '')}")
    print(f"Avg R multiple: {result.get('avg_r_multiple', '')}")
    print(f"Sample size warning: {result.get('sample_size_warning', '')}")
    print(f"CSV: {result['csv_out']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")
    if result.get("error"):
        print(f"Error: {result['error']}")

    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
