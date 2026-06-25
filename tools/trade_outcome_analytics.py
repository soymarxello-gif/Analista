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


ANALYTICS_COLUMNS = [
    "group",
    "group_value",
    "total_trades",
    "wins",
    "losses",
    "breakeven",
    "time_exit",
    "manual_exit",
    "cancelled",
    "win_rate",
    "avg_pnl_pct",
    "median_pnl_pct",
    "avg_r_multiple",
    "median_r_multiple",
    "total_r_multiple",
    "best_trade_r",
    "worst_trade_r",
]


def _safe_text(value) -> str:
    if value is None:
        return ""
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


def load_trade_outcomes(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def filter_closed_trades(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "status" not in df.columns:
        return pd.DataFrame()

    status = df["status"].fillna("").astype(str).str.upper()
    closed = df[status == "CLOSED"].copy()

    if closed.empty:
        return pd.DataFrame()

    if "outcome" not in closed.columns:
        closed["outcome"] = ""

    if "pnl_pct" not in closed.columns:
        closed["pnl_pct"] = ""

    if "r_multiple" not in closed.columns:
        closed["r_multiple"] = ""

    closed["outcome"] = closed["outcome"].fillna("").astype(str).str.upper()
    closed["pnl_pct_num"] = pd.to_numeric(closed["pnl_pct"], errors="coerce")
    closed["r_multiple_num"] = pd.to_numeric(closed["r_multiple"], errors="coerce")

    return closed


def score_bucket(value) -> str:
    score = _safe_float(value, None)

    if score is None:
        return "UNKNOWN"

    if score >= 90:
        return "90_PLUS"

    if score >= 80:
        return "80_TO_89"

    if score >= 70:
        return "70_TO_79"

    if score >= 60:
        return "60_TO_69"

    return "BELOW_60"


def add_score_buckets(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "source_final_trade_score" in out.columns:
        out["source_final_trade_score_bucket"] = out["source_final_trade_score"].apply(score_bucket)
    else:
        out["source_final_trade_score_bucket"] = "UNKNOWN"

    if "source_setup_persistence_score" in out.columns:
        out["source_setup_persistence_score_bucket"] = out["source_setup_persistence_score"].apply(score_bucket)
    else:
        out["source_setup_persistence_score_bucket"] = "UNKNOWN"

    return out


def calculate_group_metrics(
    closed_df: pd.DataFrame,
    group: str,
    group_value: str,
) -> dict:
    if closed_df.empty:
        return {
            "group": group,
            "group_value": group_value,
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "breakeven": 0,
            "time_exit": 0,
            "manual_exit": 0,
            "cancelled": 0,
            "win_rate": "",
            "avg_pnl_pct": "",
            "median_pnl_pct": "",
            "avg_r_multiple": "",
            "median_r_multiple": "",
            "total_r_multiple": "",
            "best_trade_r": "",
            "worst_trade_r": "",
        }

    outcome = closed_df["outcome"].fillna("").astype(str).str.upper()

    wins = int((outcome == "WIN").sum())
    losses = int((outcome == "LOSS").sum())
    breakeven = int((outcome == "BREAKEVEN").sum())
    time_exit = int((outcome == "TIME_EXIT").sum())
    manual_exit = int((outcome == "MANUAL_EXIT").sum())
    cancelled = int((outcome == "CANCELLED").sum())

    decisive = wins + losses
    win_rate = wins / decisive if decisive > 0 else None

    pnl = pd.to_numeric(closed_df.get("pnl_pct_num"), errors="coerce")
    r_multiple = pd.to_numeric(closed_df.get("r_multiple_num"), errors="coerce")

    return {
        "group": group,
        "group_value": group_value,
        "total_trades": int(len(closed_df)),
        "wins": wins,
        "losses": losses,
        "breakeven": breakeven,
        "time_exit": time_exit,
        "manual_exit": manual_exit,
        "cancelled": cancelled,
        "win_rate": _round_or_blank(win_rate),
        "avg_pnl_pct": _round_or_blank(pnl.mean()),
        "median_pnl_pct": _round_or_blank(pnl.median()),
        "avg_r_multiple": _round_or_blank(r_multiple.mean()),
        "median_r_multiple": _round_or_blank(r_multiple.median()),
        "total_r_multiple": _round_or_blank(r_multiple.sum()),
        "best_trade_r": _round_or_blank(r_multiple.max()),
        "worst_trade_r": _round_or_blank(r_multiple.min()),
    }


def _safe_group_value(value) -> str:
    text = _safe_text(value)
    return text if text else "MISSING"


def build_trade_outcome_analytics_dataframe(outcomes_df: pd.DataFrame) -> pd.DataFrame:
    closed = filter_closed_trades(outcomes_df)

    if closed.empty:
        return pd.DataFrame(columns=ANALYTICS_COLUMNS)

    closed = add_score_buckets(closed)

    rows: list[dict] = []

    rows.append(
        calculate_group_metrics(
            closed_df=closed,
            group="OVERALL",
            group_value="ALL_CLOSED",
        )
    )

    group_columns = [
        "source_signal",
        "source_recommendation",
        "source_setup_type",
        "source_final_trade_score_bucket",
        "source_setup_persistence_score_bucket",
    ]

    for col in group_columns:
        if col not in closed.columns:
            continue

        temp = closed.copy()
        temp[col] = temp[col].apply(_safe_group_value)

        for value, group_df in temp.groupby(col, dropna=False):
            rows.append(
                calculate_group_metrics(
                    closed_df=group_df,
                    group=col,
                    group_value=str(value),
                )
            )

    out = pd.DataFrame(rows)

    for col in ANALYTICS_COLUMNS:
        if col not in out.columns:
            out[col] = ""

    out = out[ANALYTICS_COLUMNS]

    sort_cols = ["group", "total_trades", "avg_r_multiple"]
    ascending = [True, False, False]
    sort_cols = [c for c in sort_cols if c in out.columns]
    ascending = ascending[: len(sort_cols)]

    return out.sort_values(sort_cols, ascending=ascending).reset_index(drop=True)


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_Sin datos._"

    columns = list(df.columns)
    lines = []
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")

    for _, row in df.iterrows():
        values = []
        for col in columns:
            value = row.get(col)
            if pd.isna(value):
                value = ""
            values.append(str(value).replace("\n", " ").replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")

    return "\n".join(lines)


def build_trade_outcome_analytics_markdown(analytics_df: pd.DataFrame) -> str:
    lines: list[str] = []

    lines.append("# Analista — trade outcome analytics")
    lines.append("")
    lines.append(f"- generated_at: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- rows: {len(analytics_df)}")
    lines.append("")

    if analytics_df.empty:
        lines.append("_No hay operaciones cerradas para analizar._")
        return "\n".join(lines)

    overall = analytics_df[
        (analytics_df["group"] == "OVERALL")
        & (analytics_df["group_value"] == "ALL_CLOSED")
    ].copy()

    lines.append("## Overall")
    lines.append("")

    if overall.empty:
        lines.append("_Sin métricas overall._")
    else:
        display_cols = [
            "total_trades",
            "wins",
            "losses",
            "breakeven",
            "time_exit",
            "manual_exit",
            "win_rate",
            "avg_pnl_pct",
            "avg_r_multiple",
            "total_r_multiple",
            "best_trade_r",
            "worst_trade_r",
        ]
        display_cols = [col for col in display_cols if col in overall.columns]
        lines.append(_df_to_markdown_table(overall[display_cols]))

    lines.append("")

    for group_name in [
        "source_signal",
        "source_recommendation",
        "source_setup_type",
        "source_final_trade_score_bucket",
        "source_setup_persistence_score_bucket",
    ]:
        group_df = analytics_df[analytics_df["group"] == group_name].copy()

        lines.append(f"## {group_name}")
        lines.append("")

        if group_df.empty:
            lines.append("_Sin datos._")
            lines.append("")
            continue

        display_cols = [
            "group_value",
            "total_trades",
            "wins",
            "losses",
            "breakeven",
            "time_exit",
            "manual_exit",
            "win_rate",
            "avg_pnl_pct",
            "avg_r_multiple",
            "total_r_multiple",
            "best_trade_r",
            "worst_trade_r",
        ]
        display_cols = [col for col in display_cols if col in group_df.columns]

        lines.append(_df_to_markdown_table(group_df[display_cols]))
        lines.append("")

    return "\n".join(lines)


def save_trade_outcome_analytics_reports(
    outcomes_path: Path,
    csv_out: Path,
    markdown_out: Path,
    json_out: Path | None = None,
) -> dict:
    outcomes_df = load_trade_outcomes(outcomes_path)
    analytics_df = build_trade_outcome_analytics_dataframe(outcomes_df)

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)

    analytics_df.to_csv(csv_out, index=False)
    markdown_out.write_text(
        build_trade_outcome_analytics_markdown(analytics_df),
        encoding="utf-8",
    )

    payload = {
        "status": "PASS",
        "rows": int(len(analytics_df)),
        "closed_trades": int(
            len(filter_closed_trades(outcomes_df))
            if not outcomes_df.empty
            else 0
        ),
        "csv_out": str(csv_out),
        "markdown_out": str(markdown_out),
        "json_out": str(json_out or ""),
    }
    if json_out is not None:
        json_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Analiza resultados cerrados de trade_outcomes.csv.")
    parser.add_argument("--outcomes-path", default="reports/trade_outcomes.csv")
    parser.add_argument("--csv-out", default="reports/trade_outcome_analytics_latest.csv")
    parser.add_argument("--json-out", default="reports/trade_outcome_analytics_latest.json")
    parser.add_argument("--markdown-out", default="reports/trade_outcome_analytics_latest.md")
    args = parser.parse_args()

    result = save_trade_outcome_analytics_reports(
        outcomes_path=ROOT / args.outcomes_path,
        csv_out=ROOT / args.csv_out,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
    )

    print("=== ANALISTA TRADE OUTCOME ANALYTICS ===")
    print(f"Status: {result['status']}")
    print(f"Closed trades: {result['closed_trades']}")
    print(f"Rows: {result['rows']}")
    print(f"CSV: {result['csv_out']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
