from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


MANUAL_REVIEW_COLUMNS = [
    "rank",
    "ticker",
    "signal",
    "recommendation",
    "manual_quote_check_required",
    "quote_recheck_priority",
    "quote_recheck_reason",
    "final_trade_score",
    "setup_quality_score",
    "final_score",
    "setup_type",
    "entry",
    "stop",
    "target",
    "actionable_entry",
    "actionable_stop",
    "actionable_target",
    "rr",
    "stop_atr_multiple",
    "stop_atr_status",
    "quote_status",
    "execution_quote_quality",
    "options_bias",
    "options_confidence",
    "sector",
    "industry",
    "penalty_reasons",
    "all_veto_reasons",
    "reason_summary",
    "deep_analysis_selected",
    "scenario_status",
    "scenario_confidence",
    "scenario_operability",
    "scenario_eligible_for_backtest",
    "scenario_guardrail_applied",
    "scenario_guardrail_reason",
    "momentum_state",
    "extension_state",
    "entry_timing_status",
    "required_confirmation",
    "engine_recommendation",
    "shadow_entry",
    "shadow_stop",
    "shadow_target",
    "shadow_rr",
    "shadow_stop_atr_multiple",
    "shadow_level_status",
]


REVIEW_GROUP_ORDER = {
    "TRIGGER_CONFIRMED": 0,
    "RECHECK_LIVE_QUOTE": 1,
    "READY_WAIT_TRIGGER": 2,
    "WATCHLIST_MONITOR": 3,
    "WATCHLIST": 4,
}


def _bool_series(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(str).str.lower().isin({"true", "1", "yes", "y"})


def _review_group(row: dict) -> str:
    signal = str(row.get("signal") or "").upper().strip()
    recommendation = str(row.get("recommendation") or "").upper().strip()
    manual_quote = str(row.get("manual_quote_check_required") or "").lower().strip() in {
        "true",
        "1",
        "yes",
        "y",
    }

    if signal == "TRIGGER_CONFIRMED":
        return "TRIGGER_CONFIRMED"

    if manual_quote or recommendation == "RECHECK_LIVE_QUOTE":
        return "RECHECK_LIVE_QUOTE"

    if signal == "READY_WAIT_TRIGGER":
        return "READY_WAIT_TRIGGER"

    if recommendation == "WATCHLIST_MONITOR":
        return "WATCHLIST_MONITOR"

    if signal == "WATCHLIST":
        return "WATCHLIST"

    return "OTHER"


def build_manual_review_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    out = df.copy()

    if "manual_quote_check_required" not in out.columns:
        out["manual_quote_check_required"] = False

    if "recommendation" not in out.columns:
        out["recommendation"] = ""

    out["_review_group"] = out.apply(lambda row: _review_group(row.to_dict()), axis=1)

    keep_groups = {
        "TRIGGER_CONFIRMED",
        "RECHECK_LIVE_QUOTE",
        "READY_WAIT_TRIGGER",
        "WATCHLIST_MONITOR",
        "WATCHLIST",
    }

    out = out[out["_review_group"].isin(keep_groups)].copy()

    if out.empty:
        return out

    out["_review_group_order"] = out["_review_group"].map(REVIEW_GROUP_ORDER).fillna(99).astype(int)

    sort_cols = [
        "_review_group_order",
        "rank",
        "final_trade_score",
        "setup_quality_score",
    ]
    sort_cols = [c for c in sort_cols if c in out.columns]

    ascending = []
    for col in sort_cols:
        if col in {"final_trade_score", "setup_quality_score"}:
            ascending.append(False)
        else:
            ascending.append(True)

    out = out.sort_values(sort_cols, ascending=ascending).reset_index(drop=True)

    cols = ["_review_group"] + [c for c in MANUAL_REVIEW_COLUMNS if c in out.columns]

    return out[cols]


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_Sin candidatos para revisión manual._\n"

    headers = list(df.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for _, row in df.iterrows():
        values = []
        for col in headers:
            value = row.get(col, "")
            if pd.isna(value):
                value = ""
            text = str(value).replace("\n", " ").replace("|", "/")
            values.append(text)
        lines.append("| " + " | ".join(values) + " |")

    return "\n".join(lines) + "\n"


def save_manual_review_reports(
    df: pd.DataFrame,
    csv_out: Path,
    markdown_out: Path,
) -> None:
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    review_df = build_manual_review_dataframe(df)

    review_df.to_csv(csv_out, index=False)

    sections = []
    sections.append("# Analista — revisión manual diaria\n")

    if review_df.empty:
        sections.append("_Sin candidatos para revisión manual._\n")
    else:
        for group, group_df in review_df.groupby("_review_group", sort=False):
            sections.append(f"\n## {group}\n")
            display_df = group_df.drop(columns=["_review_group"], errors="ignore")
            sections.append(_df_to_markdown_table(display_df))

    markdown_out.write_text("\n".join(sections), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporta reporte operativo de revisión manual.")
    parser.add_argument("--csv", default="reports/latest_scan_audited.csv")
    parser.add_argument("--csv-out", default="reports/manual_review_latest.csv")
    parser.add_argument("--markdown-out", default="reports/manual_review_latest.md")
    args = parser.parse_args()

    csv_path = ROOT / args.csv
    if not csv_path.exists():
        raise FileNotFoundError(f"No existe CSV: {csv_path}")

    df = pd.read_csv(csv_path)

    save_manual_review_reports(
        df,
        csv_out=ROOT / args.csv_out,
        markdown_out=ROOT / args.markdown_out,
    )

    print(f"CSV escrito en: {ROOT / args.csv_out}")
    print(f"Markdown escrito en: {ROOT / args.markdown_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
