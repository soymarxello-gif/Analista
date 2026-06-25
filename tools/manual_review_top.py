from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


TOP_COLUMNS = [
    "_top_group",
    "rank",
    "ticker",
    "signal",
    "recommendation",
    "setup_persistence_score",
    "setup_persistence_bucket",
    "final_trade_score",
    "setup_quality_score",
    "final_score",
    "rr",
    "setup_type",
    "quote_status",
    "execution_quote_quality",
    "quote_recheck_priority",
    "stop_atr_status",
    "signal_path",
    "score_delta",
    "rank_delta",
    "persistence_bonus_reason",
    "persistence_penalty_reason",
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
    "reason_summary",
]


GROUP_ORDER = {
    "1_ALTA_CALIDAD_OPERATIVA": 0,
    "2_REQUIERE_RECHECK_QUOTE": 1,
    "3_PERSISTENTE_NO_ACCIONABLE_TODAVIA": 2,
    "4_DETERIORADO_O_DEBIL": 3,
}


def _safe_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _is_quote_recheck(row: dict) -> bool:
    recommendation = _safe_text(row.get("recommendation")).upper()
    quote_status = _safe_text(row.get("quote_status")).upper()
    execution_quote_quality = _safe_text(row.get("execution_quote_quality")).upper()
    quote_recheck_priority = _safe_text(row.get("quote_recheck_priority")).upper()
    manual_quote = _bool(row.get("manual_quote_check_required"))

    return (
        recommendation == "RECHECK_LIVE_QUOTE"
        or manual_quote
        or execution_quote_quality == "LOW"
        or quote_recheck_priority in {"HIGH", "MEDIUM", "LOW"}
        or quote_status in {"INVALID", "STALE_POSSIBLE", "MISSING", "WIDE_OR_INCOHERENT"}
    )


def _is_deteriorated(row: dict) -> bool:
    signal = _safe_text(row.get("signal")).upper()
    bucket = _safe_text(row.get("setup_persistence_bucket")).upper()
    penalty = _safe_text(row.get("persistence_penalty_reason")).lower()
    scenario_status = _safe_text(row.get("scenario_status")).upper()

    return (
        signal in {"AVOID", "VETO"}
        or bucket == "D_WEAK_OR_DETERIORATED"
        or "signal_deteriorated" in penalty
        or "disappeared_from_manual_review" in penalty
        or scenario_status
        in {
            "LATE_ENTRY_OVEREXTENDED",
            "WEAK_MOMENTUM",
            "STRUCTURE_INVALID",
            "CONTEXT_CONFLICT",
            "DATA_INSUFFICIENT",
        }
    )


def _scenario_allows_high_quality(row: dict) -> bool:
    scenario_status = _safe_text(row.get("scenario_status")).upper()
    if scenario_status and scenario_status != "VALID_TRIGGER":
        return False

    if _safe_text(row.get("scenario_eligible_for_backtest")):
        if not _bool(row.get("scenario_eligible_for_backtest")):
            return False

    shadow_status = _safe_text(row.get("shadow_level_status")).upper()
    if shadow_status and shadow_status not in {"VALID", "NOT_AVAILABLE", "NOT_ELIGIBLE"}:
        return False

    return True


def _is_high_quality(row: dict) -> bool:
    signal = _safe_text(row.get("signal")).upper()
    recommendation = _safe_text(row.get("recommendation")).upper()
    quote_status = _safe_text(row.get("quote_status")).upper()
    execution_quote_quality = _safe_text(row.get("execution_quote_quality")).upper()

    final_trade_score = _safe_float(row.get("final_trade_score"), 0.0)
    setup_quality_score = _safe_float(row.get("setup_quality_score"), 0.0)
    persistence_score = _safe_float(row.get("setup_persistence_score"), 0.0)
    rr = _safe_float(row.get("rr"), 0.0)

    valid_operational_quote = (
        quote_status == "VALID"
        and execution_quote_quality == "HIGH"
        and recommendation != "RECHECK_LIVE_QUOTE"
    )

    valid_signal = signal in {
        "TRIGGER_CONFIRMED",
        "READY_WAIT_TRIGGER",
        "WATCHLIST",
    }

    return (
        valid_signal
        and valid_operational_quote
        and _scenario_allows_high_quality(row)
        and final_trade_score >= 70
        and setup_quality_score >= 65
        and rr >= 1.7
        and persistence_score >= 50
    )


def classify_top_group(row: dict) -> str:
    if _is_deteriorated(row):
        return "4_DETERIORADO_O_DEBIL"

    if _is_quote_recheck(row):
        return "2_REQUIERE_RECHECK_QUOTE"

    if _is_high_quality(row):
        return "1_ALTA_CALIDAD_OPERATIVA"

    return "3_PERSISTENTE_NO_ACCIONABLE_TODAVIA"


def build_manual_review_top_dataframe(
    manual_df: pd.DataFrame,
    per_group_limit: int = 20,
) -> pd.DataFrame:
    if manual_df.empty:
        return pd.DataFrame()

    out = manual_df.copy()
    out["_manual_order"] = range(len(out))

    if "ticker" in out.columns:
        out["ticker"] = out["ticker"].astype(str).str.upper()

    out["_top_group"] = out.apply(lambda row: classify_top_group(row.to_dict()), axis=1)
    out["_top_group_order"] = out["_top_group"].map(GROUP_ORDER).fillna(99).astype(int)

    sort_cols = [
        "_top_group_order",
        "rank",
        "setup_persistence_score",
        "final_trade_score",
        "_manual_order",
    ]

    sort_cols = [c for c in sort_cols if c in out.columns]

    ascending = []
    for col in sort_cols:
        if col in {"setup_persistence_score", "final_trade_score"}:
            ascending.append(False)
        else:
            ascending.append(True)

    out = out.sort_values(sort_cols, ascending=ascending).reset_index(drop=True)

    selected_frames = []
    for _, group_df in out.groupby("_top_group", sort=False):
        selected_frames.append(group_df.head(per_group_limit))

    if not selected_frames:
        return pd.DataFrame()

    top = pd.concat(selected_frames, ignore_index=True)

    cols = [c for c in TOP_COLUMNS if c in top.columns]
    return top[cols]


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_Sin candidatos._"

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


def build_manual_review_top_markdown(top_df: pd.DataFrame) -> str:
    lines: list[str] = []

    lines.append("# Analista — manual review top")
    lines.append("")
    lines.append("> Vista corta. No modifica ranking, señales ni recomendaciones.")
    lines.append("")

    if top_df.empty:
        lines.append("_Sin candidatos para revisión manual._")
        return "\n".join(lines)

    lines.append("## Resumen")
    lines.append("")

    counts = top_df["_top_group"].value_counts().to_dict() if "_top_group" in top_df.columns else {}
    for group in GROUP_ORDER:
        lines.append(f"- {group}: {int(counts.get(group, 0))}")

    lines.append("")

    for group in GROUP_ORDER:
        group_df = top_df[top_df["_top_group"] == group].copy()
        lines.append(f"## {group}")
        lines.append("")

        if group_df.empty:
            lines.append("_Sin candidatos._")
            lines.append("")
            continue

        display_cols = [
            "rank",
            "ticker",
            "signal",
            "recommendation",
            "setup_persistence_score",
            "setup_persistence_bucket",
            "final_trade_score",
            "setup_quality_score",
            "rr",
            "setup_type",
            "quote_status",
            "execution_quote_quality",
            "quote_recheck_priority",
            "scenario_status",
            "scenario_operability",
            "momentum_state",
            "extension_state",
            "entry_timing_status",
            "shadow_level_status",
            "signal_path",
            "persistence_penalty_reason",
        ]
        display_cols = [c for c in display_cols if c in group_df.columns]

        lines.append(_df_to_markdown_table(group_df[display_cols]))
        lines.append("")

    return "\n".join(lines)


def save_manual_review_top_reports(
    manual_csv: Path,
    csv_out: Path,
    markdown_out: Path,
    per_group_limit: int = 20,
) -> dict:
    if not manual_csv.exists():
        csv_out.parent.mkdir(parents=True, exist_ok=True)
        markdown_out.parent.mkdir(parents=True, exist_ok=True)

        pd.DataFrame().to_csv(csv_out, index=False)
        markdown_out.write_text(
            "# Analista — manual review top\n\nNo existe manual_review_latest.csv.\n",
            encoding="utf-8",
        )

        return {
            "status": "FAIL",
            "rows": 0,
            "groups": {},
            "csv_out": str(csv_out),
            "markdown_out": str(markdown_out),
        }

    manual_df = pd.read_csv(manual_csv)
    top_df = build_manual_review_top_dataframe(
        manual_df,
        per_group_limit=per_group_limit,
    )

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    top_df.to_csv(csv_out, index=False)

    markdown = build_manual_review_top_markdown(top_df)
    markdown_out.write_text(markdown, encoding="utf-8")

    groups = top_df["_top_group"].value_counts().to_dict() if "_top_group" in top_df.columns else {}

    return {
        "status": "PASS" if not top_df.empty else "WARN",
        "rows": int(len(top_df)),
        "groups": groups,
        "csv_out": str(csv_out),
        "markdown_out": str(markdown_out),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera reporte corto de revisión manual.")
    parser.add_argument("--manual-csv", default="reports/manual_review_latest.csv")
    parser.add_argument("--csv-out", default="reports/manual_review_top.csv")
    parser.add_argument("--markdown-out", default="reports/manual_review_top.md")
    parser.add_argument("--per-group-limit", type=int, default=20)
    args = parser.parse_args()

    result = save_manual_review_top_reports(
        manual_csv=ROOT / args.manual_csv,
        csv_out=ROOT / args.csv_out,
        markdown_out=ROOT / args.markdown_out,
        per_group_limit=args.per_group_limit,
    )

    print("=== ANALISTA MANUAL REVIEW TOP ===")
    print(f"Status: {result['status']}")
    print(f"Rows: {result['rows']}")
    print(f"Groups: {result['groups']}")
    print(f"CSV: {result['csv_out']}")
    print(f"Markdown: {result['markdown_out']}")

    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
