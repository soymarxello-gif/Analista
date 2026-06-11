from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PERSISTENCE_COLUMNS = [
    "setup_persistence_score",
    "setup_persistence_bucket",
    "appearances",
    "signal_path",
    "score_delta",
    "rank_delta",
    "persistence_bonus_reason",
    "persistence_penalty_reason",
]

BAD_QUOTE_STATUSES = {
    "INVALID",
    "STALE_POSSIBLE",
    "MISSING",
    "WIDE_OR_INCOHERENT",
}


def _safe_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def infer_recommendation_from_row(row: dict) -> str:
    signal = _safe_text(row.get("signal")).upper()
    quote_status = _safe_text(row.get("quote_status")).upper()
    execution_quote_quality = _safe_text(row.get("execution_quote_quality")).upper()

    if signal == "VETO":
        return "DO_NOT_TRADE"

    if signal == "AVOID":
        return "AVOID_FOR_NOW"

    if signal == "TRIGGER_CONFIRMED":
        if execution_quote_quality == "LOW" or quote_status in BAD_QUOTE_STATUSES:
            return "RECHECK_LIVE_QUOTE"
        return "MANUAL_REVIEW_TRIGGER_CONFIRMED"

    if signal == "READY_WAIT_TRIGGER":
        if execution_quote_quality == "LOW" or quote_status in BAD_QUOTE_STATUSES:
            return "RECHECK_LIVE_QUOTE"
        return "WAIT_FOR_TRIGGER"

    if signal == "WATCHLIST":
        if execution_quote_quality == "LOW" or quote_status in BAD_QUOTE_STATUSES:
            return "RECHECK_LIVE_QUOTE"
        return "WATCHLIST_MONITOR"

    return "REVIEW_MANUALLY"


def fill_missing_recommendations(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "recommendation" not in out.columns:
        out["recommendation"] = ""

    # Important: if the whole column is NaN, pandas may infer float64.
    # Convert to object/string-compatible before assigning text labels.
    out["recommendation"] = out["recommendation"].astype("object")

    missing_mask = out["recommendation"].apply(_safe_text).eq("")

    if missing_mask.any():
        inferred = out.loc[missing_mask].apply(
            lambda row: infer_recommendation_from_row(row.to_dict()),
            axis=1,
        )

        # Force compatible dtype before assignment.
        out.loc[missing_mask, "recommendation"] = inferred.astype("object").values

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


def _select_existing_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    return [col for col in columns if col in df.columns]


def enrich_manual_review_with_persistence(
    manual_csv: Path,
    persistence_csv: Path,
) -> tuple[pd.DataFrame, dict]:
    if not manual_csv.exists():
        return pd.DataFrame(), {
            "status": "FAIL",
            "rows": 0,
            "matched": 0,
            "missing": 0,
            "reason": f"missing_manual_csv:{manual_csv}",
        }

    manual_df = pd.read_csv(manual_csv)
    manual_df = fill_missing_recommendations(manual_df)

    if manual_df.empty:
        return manual_df, {
            "status": "WARN",
            "rows": 0,
            "matched": 0,
            "missing": 0,
            "reason": "empty_manual_review",
        }

    if "ticker" not in manual_df.columns:
        return manual_df, {
            "status": "FAIL",
            "rows": int(len(manual_df)),
            "matched": 0,
            "missing": int(len(manual_df)),
            "reason": "manual_review_missing_ticker_column",
        }

    out = manual_df.copy()
    out["_manual_order"] = range(len(out))
    out["ticker"] = out["ticker"].astype(str).str.upper()

    if not persistence_csv.exists():
        for col in PERSISTENCE_COLUMNS:
            if col not in out.columns:
                out[col] = pd.NA

        out = out.sort_values("_manual_order").drop(columns=["_manual_order"])

        return out, {
            "status": "WARN",
            "rows": int(len(out)),
            "matched": 0,
            "missing": int(len(out)),
            "reason": f"missing_persistence_csv:{persistence_csv}",
        }

    persistence_df = pd.read_csv(persistence_csv)

    if persistence_df.empty or "ticker" not in persistence_df.columns:
        for col in PERSISTENCE_COLUMNS:
            if col not in out.columns:
                out[col] = pd.NA

        out = out.sort_values("_manual_order").drop(columns=["_manual_order"])

        return out, {
            "status": "WARN",
            "rows": int(len(out)),
            "matched": 0,
            "missing": int(len(out)),
            "reason": "empty_or_invalid_persistence_csv",
        }

    persistence_df = persistence_df.copy()
    persistence_df["ticker"] = persistence_df["ticker"].astype(str).str.upper()

    merge_cols = ["ticker"] + _select_existing_columns(persistence_df, PERSISTENCE_COLUMNS)
    persistence_df = (
        persistence_df[merge_cols]
        .drop_duplicates(subset=["ticker"], keep="first")
        .copy()
    )

    # Remove old persistence columns if the manual report already had them.
    for col in PERSISTENCE_COLUMNS:
        if col in out.columns:
            out = out.drop(columns=[col])

    out = out.merge(
        persistence_df,
        on="ticker",
        how="left",
        validate="many_to_one",
    )

    matched = int(out["setup_persistence_score"].notna().sum()) if "setup_persistence_score" in out.columns else 0
    missing = int(len(out) - matched)

    for col in PERSISTENCE_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA

    out = out.sort_values("_manual_order").drop(columns=["_manual_order"])

    return out, {
        "status": "PASS" if matched > 0 else "WARN",
        "rows": int(len(out)),
        "matched": matched,
        "missing": missing,
        "reason": "",
    }


def build_manual_review_persistence_markdown(df: pd.DataFrame, result: dict) -> str:
    lines: list[str] = []

    lines.append("# Analista — revisión manual con persistencia")
    lines.append("")
    lines.append("> Modo auditado: la persistencia no cambia ranking, señal ni recomendación.")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    lines.append(f"- status: {result.get('status')}")
    lines.append(f"- rows: {result.get('rows')}")
    lines.append(f"- matched: {result.get('matched')}")
    lines.append(f"- missing: {result.get('missing')}")

    if result.get("reason"):
        lines.append(f"- reason: {result.get('reason')}")

    lines.append("")

    if df.empty:
        lines.append("_Sin candidatos en revisión manual._")
        return "\n".join(lines)

    preferred_cols = [
        "rank",
        "ticker",
        "signal",
        "recommendation",
        "setup_persistence_score",
        "setup_persistence_bucket",
        "appearances",
        "latest_final_trade_score",
        "final_trade_score",
        "score_delta",
        "rank_delta",
        "quote_status",
        "execution_quote_quality",
        "quote_recheck_priority",
        "rr",
        "stop_atr_status",
        "signal_path",
        "persistence_bonus_reason",
        "persistence_penalty_reason",
    ]

    cols = [col for col in preferred_cols if col in df.columns]

    lines.append("## Candidatos")
    lines.append("")
    lines.append(_df_to_markdown_table(df[cols] if cols else df))

    return "\n".join(lines)


def save_enriched_manual_review_reports(
    manual_csv: Path,
    persistence_csv: Path,
    csv_out: Path,
    markdown_out: Path,
) -> dict:
    enriched_df, result = enrich_manual_review_with_persistence(
        manual_csv=manual_csv,
        persistence_csv=persistence_csv,
    )

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    enriched_df.to_csv(csv_out, index=False)

    markdown = build_manual_review_persistence_markdown(enriched_df, result)
    markdown_out.write_text(markdown, encoding="utf-8")

    result = dict(result)
    result["csv_out"] = str(csv_out)
    result["markdown_out"] = str(markdown_out)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Enriquece manual_review_latest con setup persistence.")
    parser.add_argument("--manual-csv", default="reports/manual_review_latest.csv")
    parser.add_argument("--persistence-csv", default="reports/setup_persistence_latest.csv")
    parser.add_argument("--csv-out", default="reports/manual_review_latest.csv")
    parser.add_argument("--markdown-out", default="reports/manual_review_latest.md")
    args = parser.parse_args()

    result = save_enriched_manual_review_reports(
        manual_csv=ROOT / args.manual_csv,
        persistence_csv=ROOT / args.persistence_csv,
        csv_out=ROOT / args.csv_out,
        markdown_out=ROOT / args.markdown_out,
    )

    print("=== ANALISTA MANUAL REVIEW PERSISTENCE ENRICHER ===")
    print(f"Status: {result['status']}")
    print(f"Rows: {result['rows']}")
    print(f"Matched: {result['matched']}")
    print(f"Missing: {result['missing']}")
    print(f"CSV: {result['csv_out']}")
    print(f"Markdown: {result['markdown_out']}")

    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())