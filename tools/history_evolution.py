from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SIGNAL_STRENGTH = {
    "VETO": 0,
    "AVOID": 1,
    "WATCHLIST": 2,
    "READY_WAIT_TRIGGER": 3,
    "TRIGGER_CONFIRMED": 4,
}


DEFAULT_SCAN_COLUMNS = [
    "ticker",
    "rank",
    "signal",
    "recommendation",
    "setup_type",
    "final_score",
    "final_trade_score",
    "setup_quality_score",
    "asset_quality_score",
    "quote_status",
    "execution_quote_quality",
    "manual_quote_check_required",
    "quote_recheck_priority",
]


def _parse_run_timestamp(run_id: str) -> datetime | None:
    try:
        return datetime.strptime(run_id, "%Y%m%d_%H%M%S")
    except Exception:
        return None


def _safe_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _safe_float(value) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _safe_int(value) -> int | None:
    try:
        if value is None or pd.isna(value):
            return None
        return int(float(value))
    except Exception:
        return None


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _path(values: list) -> str:
    cleaned = [_safe_text(v) for v in values]
    cleaned = [v for v in cleaned if v]
    if not cleaned:
        return ""
    compressed: list[str] = []
    for item in cleaned:
        if not compressed or compressed[-1] != item:
            compressed.append(item)
    return " -> ".join(compressed)


def _numeric_path(values: list, decimals: int = 2) -> str:
    out: list[str] = []
    for value in values:
        number = _safe_float(value)
        if number is None:
            continue
        out.append(f"{number:.{decimals}f}")
    return " -> ".join(out)


def _rank_path(values: list) -> str:
    out: list[str] = []
    for value in values:
        number = _safe_int(value)
        if number is None:
            continue
        out.append(str(number))
    return " -> ".join(out)


def _history_dirs(history_root: Path) -> list[Path]:
    if not history_root.exists():
        return []

    dirs = [
        path
        for path in history_root.iterdir()
        if path.is_dir() and _parse_run_timestamp(path.name) is not None
    ]

    return sorted(dirs, key=lambda p: p.name)


def _load_manual_tickers(run_dir: Path) -> set[str]:
    manual_path = run_dir / "manual_review_latest.csv"
    if not manual_path.exists():
        return set()

    try:
        df = pd.read_csv(manual_path)
    except Exception:
        return set()

    if "ticker" not in df.columns:
        return set()

    return set(df["ticker"].dropna().astype(str).str.upper())


def load_history_scans(history_root: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    for run_dir in _history_dirs(history_root):
        scan_path = run_dir / "latest_scan_audited.csv"
        if not scan_path.exists():
            continue

        try:
            df = pd.read_csv(scan_path)
        except Exception:
            continue

        if df.empty or "ticker" not in df.columns:
            continue

        run_id = run_dir.name
        run_ts = _parse_run_timestamp(run_id)
        manual_tickers = _load_manual_tickers(run_dir)

        for col in DEFAULT_SCAN_COLUMNS:
            if col not in df.columns:
                df[col] = pd.NA

        out = df[DEFAULT_SCAN_COLUMNS].copy()
        out["ticker"] = out["ticker"].astype(str).str.upper()
        out["run_id"] = run_id
        out["run_timestamp"] = run_ts.isoformat(timespec="seconds") if run_ts else run_id
        out["run_date"] = run_ts.date().isoformat() if run_ts else ""
        out["archive_dir"] = str(run_dir)
        out["in_manual_review"] = out["ticker"].isin(manual_tickers)

        frames.append(out)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def _manual_recheck_mask(group: pd.DataFrame) -> pd.Series:
    manual_required = (
        group.get("manual_quote_check_required", pd.Series(False, index=group.index))
        .fillna(False)
        .map(_bool)
    )

    recommendation = (
        group.get("recommendation", pd.Series("", index=group.index))
        .fillna("")
        .astype(str)
        .str.upper()
    )

    priority = (
        group.get("quote_recheck_priority", pd.Series("", index=group.index))
        .fillna("")
        .astype(str)
        .str.upper()
    )

    return (
        manual_required
        | recommendation.eq("RECHECK_LIVE_QUOTE")
        | priority.isin(["HIGH", "MEDIUM", "LOW"])
    )


def summarize_ticker_history(history_df: pd.DataFrame) -> pd.DataFrame:
    if history_df.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    history_df = history_df.copy()
    history_df["signal"] = history_df["signal"].fillna("").astype(str).str.upper()
    history_df["recommendation"] = history_df["recommendation"].fillna("").astype(str).str.upper()

    for ticker, group in history_df.groupby("ticker", sort=False):
        group = group.sort_values("run_id").reset_index(drop=True)

        first = group.iloc[0]
        latest = group.iloc[-1]

        first_signal = _safe_text(first.get("signal")).upper()
        latest_signal = _safe_text(latest.get("signal")).upper()

        signal_values = group["signal"].fillna("").astype(str).str.upper().tolist()

        first_rank = _safe_int(first.get("rank"))
        latest_rank = _safe_int(latest.get("rank"))

        first_score = _safe_float(first.get("final_trade_score"))
        latest_score = _safe_float(latest.get("final_trade_score"))

        was_trigger_confirmed = "TRIGGER_CONFIRMED" in signal_values
        promoted_to_trigger = (
            latest_signal == "TRIGGER_CONFIRMED"
            and any(s != "TRIGGER_CONFIRMED" for s in signal_values[:-1])
        )

        persistent_watchlist = (
            len(group) >= 3
            and latest_signal in {"WATCHLIST", "READY_WAIT_TRIGGER", "TRIGGER_CONFIRMED"}
            and any(s in {"WATCHLIST", "READY_WAIT_TRIGGER", "TRIGGER_CONFIRMED"} for s in signal_values)
        )

        deteriorated_signal = (
            SIGNAL_STRENGTH.get(latest_signal, -1)
            < SIGNAL_STRENGTH.get(first_signal, -1)
        )

        in_manual_path = group["in_manual_review"].fillna(False).map(_bool).tolist()
        disappeared_from_manual_review = bool(any(in_manual_path[:-1]) and not in_manual_path[-1])

        manual_recheck_count = int(_manual_recheck_mask(group).sum())

        rows.append(
            {
                "ticker": ticker,
                "appearances": int(group["run_id"].nunique()),
                "first_seen": _safe_text(first.get("run_timestamp")),
                "last_seen": _safe_text(latest.get("run_timestamp")),
                "days_seen": int(group["run_date"].nunique()),
                "latest_signal": latest_signal,
                "latest_recommendation": _safe_text(latest.get("recommendation")).upper(),
                "latest_setup_type": _safe_text(latest.get("setup_type")).upper(),
                "latest_rank": latest_rank,
                "latest_final_trade_score": latest_score,
                "latest_setup_quality_score": _safe_float(latest.get("setup_quality_score")),
                "latest_quote_status": _safe_text(latest.get("quote_status")).upper(),
                "latest_execution_quote_quality": _safe_text(latest.get("execution_quote_quality")).upper(),
                "latest_quote_recheck_priority": _safe_text(latest.get("quote_recheck_priority")).upper(),
                "signal_path": _path(signal_values),
                "recommendation_path": _path(group["recommendation"].tolist()),
                "rank_path": _rank_path(group["rank"].tolist()),
                "final_trade_score_path": _numeric_path(group["final_trade_score"].tolist()),
                "setup_quality_score_path": _numeric_path(group["setup_quality_score"].tolist()),
                "score_delta": round(latest_score - first_score, 2)
                if latest_score is not None and first_score is not None
                else None,
                # Positive rank_delta means improvement because rank 1 is better than rank 10.
                "rank_delta": first_rank - latest_rank
                if latest_rank is not None and first_rank is not None
                else None,
                "was_trigger_confirmed": was_trigger_confirmed,
                "promoted_to_trigger": promoted_to_trigger,
                "persistent_watchlist": persistent_watchlist,
                "deteriorated_signal": deteriorated_signal,
                "disappeared_from_manual_review": disappeared_from_manual_review,
                "manual_quote_recheck_count": manual_recheck_count,
                "latest_in_manual_review": bool(in_manual_path[-1]),
            }
        )

    out = pd.DataFrame(rows)

    if out.empty:
        return out

    bool_cols = [
        "promoted_to_trigger",
        "persistent_watchlist",
        "deteriorated_signal",
        "disappeared_from_manual_review",
        "was_trigger_confirmed",
        "latest_in_manual_review",
    ]

    for col in bool_cols:
        if col in out.columns:
            out[col] = out[col].astype(bool)

    return out.sort_values(
        [
            "promoted_to_trigger",
            "persistent_watchlist",
            "latest_in_manual_review",
            "appearances",
            "latest_final_trade_score",
        ],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)


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


def build_history_markdown(evolution_df: pd.DataFrame, history_df: pd.DataFrame) -> str:
    lines: list[str] = []

    lines.append("# Analista — evolución histórica de setups")
    lines.append("")
    lines.append(f"Generado: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")

    if history_df.empty:
        lines.append("No hay corridas históricas disponibles.")
        return "\n".join(lines)

    run_count = int(history_df["run_id"].nunique())
    ticker_count = int(evolution_df["ticker"].nunique()) if not evolution_df.empty else 0

    lines.append("## Resumen")
    lines.append("")
    lines.append(f"- Corridas históricas leídas: {run_count}")
    lines.append(f"- Tickers únicos observados: {ticker_count}")

    if not evolution_df.empty:
        lines.append(f"- Promovidos a TRIGGER_CONFIRMED: {int(evolution_df['promoted_to_trigger'].sum())}")
        lines.append(f"- Watchlist persistentes: {int(evolution_df['persistent_watchlist'].sum())}")
        lines.append(f"- Señales deterioradas: {int(evolution_df['deteriorated_signal'].sum())}")
        lines.append(
            f"- Desaparecidos del reporte manual: {int(evolution_df['disappeared_from_manual_review'].sum())}"
        )

    lines.append("")
    lines.append("## Promovidos a TRIGGER_CONFIRMED")
    promoted = evolution_df[evolution_df["promoted_to_trigger"]].head(20)
    promoted_cols = [
        "ticker",
        "appearances",
        "latest_rank",
        "latest_final_trade_score",
        "signal_path",
        "recommendation_path",
        "rank_delta",
    ]
    lines.append(_df_to_markdown_table(promoted[promoted_cols] if not promoted.empty else promoted))
    lines.append("")

    lines.append("## Watchlist persistentes")
    persistent = evolution_df[
        evolution_df["persistent_watchlist"] & ~evolution_df["promoted_to_trigger"]
    ].head(30)
    persistent_cols = [
        "ticker",
        "appearances",
        "latest_signal",
        "latest_recommendation",
        "latest_rank",
        "latest_final_trade_score",
        "score_delta",
        "signal_path",
    ]
    lines.append(_df_to_markdown_table(persistent[persistent_cols] if not persistent.empty else persistent))
    lines.append("")

    lines.append("## Deterioros")
    deteriorated = evolution_df[evolution_df["deteriorated_signal"]].head(30)
    deteriorated_cols = [
        "ticker",
        "appearances",
        "latest_signal",
        "latest_recommendation",
        "score_delta",
        "rank_delta",
        "signal_path",
    ]
    lines.append(_df_to_markdown_table(deteriorated[deteriorated_cols] if not deteriorated.empty else deteriorated))
    lines.append("")

    lines.append("## Desaparecidos del reporte manual")
    disappeared = evolution_df[evolution_df["disappeared_from_manual_review"]].head(30)
    disappeared_cols = [
        "ticker",
        "appearances",
        "latest_signal",
        "latest_recommendation",
        "signal_path",
        "recommendation_path",
    ]
    lines.append(_df_to_markdown_table(disappeared[disappeared_cols] if not disappeared.empty else disappeared))
    lines.append("")

    return "\n".join(lines)


def build_history_evolution_dataframe(history_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    history_df = load_history_scans(history_root)

    if history_df.empty:
        return pd.DataFrame(), history_df, "FAIL"

    run_count = int(history_df["run_id"].nunique())
    evolution_df = summarize_ticker_history(history_df)

    if run_count < 2:
        return evolution_df, history_df, "WARN"

    return evolution_df, history_df, "PASS"


def save_history_evolution_reports(
    history_root: Path,
    csv_out: Path,
    markdown_out: Path,
) -> dict:
    evolution_df, history_df, status = build_history_evolution_dataframe(history_root)

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    evolution_df.to_csv(csv_out, index=False)

    markdown = build_history_markdown(evolution_df, history_df)
    markdown_out.write_text(markdown, encoding="utf-8")

    return {
        "status": status,
        "history_runs": int(history_df["run_id"].nunique()) if not history_df.empty else 0,
        "tickers": int(evolution_df["ticker"].nunique()) if not evolution_df.empty else 0,
        "csv_out": str(csv_out),
        "markdown_out": str(markdown_out),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compara corridas históricas de Analista.")
    parser.add_argument("--history-root", default="reports/history")
    parser.add_argument("--csv-out", default="reports/history_evolution_latest.csv")
    parser.add_argument("--markdown-out", default="reports/history_evolution_latest.md")
    args = parser.parse_args()

    result = save_history_evolution_reports(
        history_root=ROOT / args.history_root,
        csv_out=ROOT / args.csv_out,
        markdown_out=ROOT / args.markdown_out,
    )

    print("=== ANALISTA HISTORY EVOLUTION ===")
    print(f"Status: {result['status']}")
    print(f"History runs: {result['history_runs']}")
    print(f"Tickers: {result['tickers']}")
    print(f"CSV: {result['csv_out']}")
    print(f"Markdown: {result['markdown_out']}")

    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())