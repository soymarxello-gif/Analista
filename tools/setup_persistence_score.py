from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(float(value))
    except Exception:
        return default


def _safe_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def calculate_setup_persistence_score(row: dict | pd.Series) -> dict:
    """
    Audit-only persistence score.

    It answers:
        "Has this setup persisted, improved, or deteriorated across historical runs?"

    It must not affect:
    - signal
    - recommendation
    - final_trade_score
    - operational_rank
    """

    appearances = _safe_int(row.get("appearances"), 0)
    latest_signal = _safe_text(row.get("latest_signal")).upper()
    latest_recommendation = _safe_text(row.get("latest_recommendation")).upper()
    latest_quote_status = _safe_text(row.get("latest_quote_status")).upper()
    latest_execution_quote_quality = _safe_text(row.get("latest_execution_quote_quality")).upper()
    latest_in_manual_review = _bool(row.get("latest_in_manual_review"))

    promoted_to_trigger = _bool(row.get("promoted_to_trigger"))
    persistent_watchlist = _bool(row.get("persistent_watchlist"))
    deteriorated_signal = _bool(row.get("deteriorated_signal"))
    disappeared_from_manual_review = _bool(row.get("disappeared_from_manual_review"))
    was_trigger_confirmed = _bool(row.get("was_trigger_confirmed"))

    score_delta = _safe_float(row.get("score_delta"), 0.0)
    rank_delta = _safe_float(row.get("rank_delta"), 0.0)
    manual_quote_recheck_count = _safe_int(row.get("manual_quote_recheck_count"), 0)

    score = 50.0
    bonus_reasons: list[str] = []
    penalty_reasons: list[str] = []

    # Appearance / persistence base.
    if appearances >= 5:
        score += 20
        bonus_reasons.append("appeared_5_or_more_runs")
    elif appearances >= 3:
        score += 15
        bonus_reasons.append("appeared_3_or_more_runs")
    elif appearances >= 2:
        score += 8
        bonus_reasons.append("appeared_multiple_runs")
    else:
        score -= 5
        penalty_reasons.append("single_run_only")

    # Latest signal state.
    if latest_signal == "TRIGGER_CONFIRMED":
        score += 20
        bonus_reasons.append("latest_trigger_confirmed")
    elif latest_signal == "READY_WAIT_TRIGGER":
        score += 14
        bonus_reasons.append("latest_ready_wait_trigger")
    elif latest_signal == "WATCHLIST":
        score += 10
        bonus_reasons.append("latest_watchlist")
    elif latest_signal == "AVOID":
        score -= 15
        penalty_reasons.append("latest_avoid")
    elif latest_signal == "VETO":
        score -= 25
        penalty_reasons.append("latest_veto")

    # Historical transition.
    if promoted_to_trigger:
        score += 20
        bonus_reasons.append("promoted_to_trigger")
    elif persistent_watchlist:
        score += 12
        bonus_reasons.append("persistent_watchlist")

    if was_trigger_confirmed:
        score += 5
        bonus_reasons.append("was_trigger_confirmed")

    # Manual review presence.
    if latest_in_manual_review:
        score += 8
        bonus_reasons.append("still_in_manual_review")
    else:
        score -= 8
        penalty_reasons.append("not_in_latest_manual_review")

    # Score delta.
    if score_delta > 0:
        score += min(10, score_delta * 0.50)
        bonus_reasons.append("final_trade_score_improved")
    elif score_delta < 0:
        score += max(-12, score_delta * 0.50)
        penalty_reasons.append("final_trade_score_deteriorated")

    # Rank delta: positive means improved because rank 1 is better than rank 10.
    if rank_delta > 0:
        score += min(10, rank_delta * 0.50)
        bonus_reasons.append("rank_improved")
    elif rank_delta < 0:
        score += max(-10, rank_delta * 0.35)
        penalty_reasons.append("rank_deteriorated")

    # Execution/quote quality.
    if latest_execution_quote_quality == "HIGH":
        score += 5
        bonus_reasons.append("execution_quote_quality_high")
    elif latest_execution_quote_quality == "LOW":
        score -= 8
        penalty_reasons.append("execution_quote_quality_low")

    if latest_quote_status == "VALID":
        score += 5
        bonus_reasons.append("quote_valid")
    elif latest_quote_status in {"INVALID", "STALE_POSSIBLE", "MISSING", "WIDE_OR_INCOHERENT"}:
        score -= 6
        penalty_reasons.append(f"quote_{latest_quote_status.lower()}")

    # Repeated manual quote recheck.
    if manual_quote_recheck_count >= 3:
        score -= 12
        penalty_reasons.append("repeated_quote_rechecks")
    elif manual_quote_recheck_count > 0:
        score -= min(8, manual_quote_recheck_count * 3)
        penalty_reasons.append("quote_recheck_required")

    # Hard deterioration flags.
    if deteriorated_signal:
        score -= 20
        penalty_reasons.append("signal_deteriorated")

    if disappeared_from_manual_review:
        score -= 20
        penalty_reasons.append("disappeared_from_manual_review")

    # Operational caps: persistence should not hide execution problems.
    if latest_recommendation == "RECHECK_LIVE_QUOTE":
        score = min(score, 79)
        penalty_reasons.append("score_capped_by_quote_recheck")

    if latest_execution_quote_quality == "LOW":
        score = min(score, 79)
        penalty_reasons.append("score_capped_by_low_execution_quote_quality")

    if latest_quote_status in {"INVALID", "STALE_POSSIBLE", "MISSING", "WIDE_OR_INCOHERENT"}:
        score = min(score, 79)
        penalty_reasons.append("score_capped_by_quote_status")

    if latest_signal == "WATCHLIST" and latest_recommendation == "WATCHLIST_MONITOR":
        score = min(score, 89)
        penalty_reasons.append("score_capped_by_watchlist_state")

    if latest_signal in {"AVOID", "VETO"}:
        score = min(score, 49)
        penalty_reasons.append("score_capped_by_non_operable_signal")

    score = round(_clip(score), 2)

    if (
        score >= 80
        and latest_signal in {"TRIGGER_CONFIRMED", "READY_WAIT_TRIGGER", "WATCHLIST"}
        and latest_recommendation != "RECHECK_LIVE_QUOTE"
        and latest_execution_quote_quality != "LOW"
        and latest_quote_status == "VALID"
    ):
        bucket = "A_PERSISTENT_HIGH_QUALITY"
    elif score >= 65:
        bucket = "B_PERSISTENT_WATCHLIST_OR_RECHECK"
    elif score >= 50:
        bucket = "C_MONITOR"
    else:
        bucket = "D_WEAK_OR_DETERIORATED"

    return {
        "setup_persistence_score": score,
        "setup_persistence_bucket": bucket,
        "persistence_bonus_reason": ", ".join(dict.fromkeys(bonus_reasons)),
        "persistence_penalty_reason": ", ".join(dict.fromkeys(penalty_reasons)),
    }


def build_setup_persistence_dataframe(evolution_df: pd.DataFrame) -> pd.DataFrame:
    if evolution_df.empty:
        return pd.DataFrame()

    out = evolution_df.copy()

    score_rows = [
        calculate_setup_persistence_score(row)
        for _, row in out.iterrows()
    ]

    score_df = pd.DataFrame(score_rows)
    out = pd.concat([out.reset_index(drop=True), score_df], axis=1)

    sort_cols = [
        "setup_persistence_score",
        "latest_in_manual_review",
        "promoted_to_trigger",
        "persistent_watchlist",
        "appearances",
        "latest_final_trade_score",
    ]

    existing_sort_cols = [c for c in sort_cols if c in out.columns]

    if existing_sort_cols:
        out = out.sort_values(
            existing_sort_cols,
            ascending=[False] * len(existing_sort_cols),
        ).reset_index(drop=True)

    return out


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
            values.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")

    return "\n".join(lines)


def build_setup_persistence_markdown(df: pd.DataFrame) -> str:
    lines: list[str] = []

    lines.append("# Analista — setup persistence score")
    lines.append("")
    lines.append(f"Generado: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("> Modo auditado: este score no cambia ranking, señales ni recomendaciones.")
    lines.append("")

    if df.empty:
        lines.append("No hay datos de evolución histórica.")
        return "\n".join(lines)

    lines.append("## Resumen")
    lines.append("")
    lines.append(f"- Tickers evaluados: {len(df)}")

    if "setup_persistence_bucket" in df.columns:
        bucket_counts = df["setup_persistence_bucket"].fillna("MISSING").astype(str).value_counts()
        for bucket, count in bucket_counts.items():
            lines.append(f"- {bucket}: {int(count)}")

    lines.append("")
    lines.append("## Top persistencia")
    top_cols = [
        "ticker",
        "setup_persistence_score",
        "setup_persistence_bucket",
        "appearances",
        "latest_signal",
        "latest_recommendation",
        "latest_rank",
        "latest_final_trade_score",
        "score_delta",
        "rank_delta",
        "signal_path",
        "persistence_bonus_reason",
        "persistence_penalty_reason",
    ]
    top_cols = [c for c in top_cols if c in df.columns]
    lines.append(_df_to_markdown_table(df[top_cols].head(30)))
    lines.append("")

    lines.append("## Deteriorados o débiles")
    weak = df[
        df["setup_persistence_bucket"].isin(
            ["D_WEAK_OR_DETERIORATED"]
        )
    ].head(30)

    weak_cols = [
        "ticker",
        "setup_persistence_score",
        "latest_signal",
        "latest_recommendation",
        "appearances",
        "score_delta",
        "rank_delta",
        "signal_path",
        "persistence_penalty_reason",
    ]
    weak_cols = [c for c in weak_cols if c in df.columns]
    lines.append(_df_to_markdown_table(weak[weak_cols] if not weak.empty else weak))
    lines.append("")

    return "\n".join(lines)


def save_setup_persistence_reports(
    evolution_csv: Path,
    csv_out: Path,
    markdown_out: Path,
) -> dict:
    if not evolution_csv.exists():
        csv_out.parent.mkdir(parents=True, exist_ok=True)
        markdown_out.parent.mkdir(parents=True, exist_ok=True)

        empty_df = pd.DataFrame()
        empty_df.to_csv(csv_out, index=False)
        markdown_out.write_text(
            "# Analista — setup persistence score\n\nNo existe history_evolution_latest.csv.\n",
            encoding="utf-8",
        )

        return {
            "status": "FAIL",
            "rows": 0,
            "csv_out": str(csv_out),
            "markdown_out": str(markdown_out),
        }

    evolution_df = pd.read_csv(evolution_csv)
    persistence_df = build_setup_persistence_dataframe(evolution_df)

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    persistence_df.to_csv(csv_out, index=False)

    markdown = build_setup_persistence_markdown(persistence_df)
    markdown_out.write_text(markdown, encoding="utf-8")

    return {
        "status": "PASS" if not persistence_df.empty else "WARN",
        "rows": int(len(persistence_df)),
        "csv_out": str(csv_out),
        "markdown_out": str(markdown_out),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Calcula setup_persistence_score en modo auditado.")
    parser.add_argument("--evolution-csv", default="reports/history_evolution_latest.csv")
    parser.add_argument("--csv-out", default="reports/setup_persistence_latest.csv")
    parser.add_argument("--markdown-out", default="reports/setup_persistence_latest.md")
    args = parser.parse_args()

    result = save_setup_persistence_reports(
        evolution_csv=ROOT / args.evolution_csv,
        csv_out=ROOT / args.csv_out,
        markdown_out=ROOT / args.markdown_out,
    )

    print("=== ANALISTA SETUP PERSISTENCE ===")
    print(f"Status: {result['status']}")
    print(f"Rows: {result['rows']}")
    print(f"CSV: {result['csv_out']}")
    print(f"Markdown: {result['markdown_out']}")

    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())