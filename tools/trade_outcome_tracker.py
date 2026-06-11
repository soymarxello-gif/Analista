from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


OUTCOME_COLUMNS = [
    "trade_id",
    "created_at",
    "ticker",
    "entry_date",
    "entry_price",
    "stop_price",
    "target_price",
    "rr",
    "risk_pct",
    "reward_pct",
    "status",
    "exit_date",
    "exit_price",
    "outcome",
    "pnl_pct",
    "r_multiple",
    "source_rank",
    "source_signal",
    "source_recommendation",
    "source_setup_type",
    "source_final_trade_score",
    "source_setup_quality_score",
    "source_setup_persistence_score",
    "notes",
]


VALID_STATUS = {"OPEN", "CLOSED", "CANCELLED"}
VALID_OUTCOME = {
    "",
    "WIN",
    "LOSS",
    "BREAKEVEN",
    "TIME_EXIT",
    "MANUAL_EXIT",
    "CANCELLED",
}


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


def _now_id_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def make_trade_id(ticker: str, entry_date: str) -> str:
    clean_ticker = _safe_text(ticker).upper()
    clean_date = _safe_text(entry_date).replace("-", "")
    return f"{clean_date}_{clean_ticker}_{_now_id_timestamp()}"


def calculate_trade_metrics(
    entry_price: float,
    stop_price: float,
    target_price: float,
) -> dict:
    if entry_price <= 0:
        raise ValueError("entry_price must be greater than zero")

    if stop_price <= 0:
        raise ValueError("stop_price must be greater than zero")

    if target_price <= 0:
        raise ValueError("target_price must be greater than zero")

    risk_pct = abs(entry_price - stop_price) / entry_price
    reward_pct = (target_price - entry_price) / entry_price

    rr = None
    if risk_pct > 0:
        rr = reward_pct / risk_pct

    return {
        "risk_pct": round(float(risk_pct), 6),
        "reward_pct": round(float(reward_pct), 6),
        "rr": round(float(rr), 6) if rr is not None else None,
    }


def empty_outcomes_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=OUTCOME_COLUMNS)


def load_outcomes(path: Path) -> pd.DataFrame:
    if not path.exists():
        return empty_outcomes_dataframe()

    df = pd.read_csv(path)

    for col in OUTCOME_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[OUTCOME_COLUMNS].copy()

    # Important:
    # Some columns can be entirely empty in CSV, so pandas may infer float64.
    # We keep the working dataframe dtype-flexible because this tool writes
    # both text fields and numeric fields during trade lifecycle updates.
    for col in OUTCOME_COLUMNS:
        df[col] = df[col].astype("object")

    return df


def save_outcomes(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    out = df.copy()

    for col in OUTCOME_COLUMNS:
        if col not in out.columns:
            out[col] = ""

    out = out[OUTCOME_COLUMNS]
    out.to_csv(path, index=False)


def build_trade_record(
    ticker: str,
    entry_date: str,
    entry_price: float,
    stop_price: float,
    target_price: float,
    source_rank=None,
    source_signal: str = "",
    source_recommendation: str = "",
    source_setup_type: str = "",
    source_final_trade_score=None,
    source_setup_quality_score=None,
    source_setup_persistence_score=None,
    notes: str = "",
) -> dict:
    ticker = _safe_text(ticker).upper()
    entry_date = _safe_text(entry_date)

    if not ticker:
        raise ValueError("ticker is required")

    if not entry_date:
        raise ValueError("entry_date is required")

    metrics = calculate_trade_metrics(
        entry_price=entry_price,
        stop_price=stop_price,
        target_price=target_price,
    )

    return {
        "trade_id": make_trade_id(ticker=ticker, entry_date=entry_date),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "ticker": ticker,
        "entry_date": entry_date,
        "entry_price": float(entry_price),
        "stop_price": float(stop_price),
        "target_price": float(target_price),
        "rr": metrics["rr"],
        "risk_pct": metrics["risk_pct"],
        "reward_pct": metrics["reward_pct"],
        "status": "OPEN",
        "exit_date": "",
        "exit_price": "",
        "outcome": "",
        "pnl_pct": "",
        "r_multiple": "",
        "source_rank": source_rank if source_rank is not None else "",
        "source_signal": _safe_text(source_signal).upper(),
        "source_recommendation": _safe_text(source_recommendation).upper(),
        "source_setup_type": _safe_text(source_setup_type),
        "source_final_trade_score": source_final_trade_score if source_final_trade_score is not None else "",
        "source_setup_quality_score": source_setup_quality_score if source_setup_quality_score is not None else "",
        "source_setup_persistence_score": (
            source_setup_persistence_score if source_setup_persistence_score is not None else ""
        ),
        "notes": _safe_text(notes),
    }


def _first_available(row: dict, keys: list[str]):
    for key in keys:
        value = row.get(key)
        if _safe_text(value) != "":
            return value
    return None


def find_manual_review_row(manual_csv: Path, ticker: str) -> dict:
    ticker = _safe_text(ticker).upper()

    if not ticker:
        raise ValueError("ticker is required")

    if not manual_csv.exists():
        raise FileNotFoundError(f"manual review file not found: {manual_csv}")

    df = pd.read_csv(manual_csv)

    if "ticker" not in df.columns:
        raise ValueError("manual review file missing ticker column")

    df["ticker"] = df["ticker"].astype(str).str.upper()

    matches = df[df["ticker"] == ticker].copy()

    if matches.empty:
        raise ValueError(f"ticker not found in manual review: {ticker}")

    return matches.iloc[0].to_dict()


def build_trade_record_from_manual_review(
    manual_csv: Path,
    ticker: str,
    entry_date: str,
    entry_price: float | None = None,
    stop_price: float | None = None,
    target_price: float | None = None,
    notes: str = "",
) -> dict:
    row = find_manual_review_row(manual_csv=manual_csv, ticker=ticker)

    report_entry = _first_available(
        row,
        ["actionable_entry", "theoretical_entry", "entry"],
    )
    report_stop = _first_available(
        row,
        ["actionable_stop", "theoretical_stop", "stop"],
    )
    report_target = _first_available(
        row,
        ["actionable_target", "theoretical_target", "target"],
    )

    final_entry = entry_price if entry_price is not None else _safe_float(report_entry)
    final_stop = stop_price if stop_price is not None else _safe_float(report_stop)
    final_target = target_price if target_price is not None else _safe_float(report_target)

    if final_entry is None:
        raise ValueError("entry price missing. Provide --entry or ensure report has actionable/theoretical entry.")

    if final_stop is None:
        raise ValueError("stop price missing. Provide --stop or ensure report has actionable/theoretical stop.")

    if final_target is None:
        raise ValueError("target price missing. Provide --target or ensure report has actionable/theoretical target.")

    return build_trade_record(
        ticker=ticker,
        entry_date=entry_date,
        entry_price=float(final_entry),
        stop_price=float(final_stop),
        target_price=float(final_target),
        source_rank=row.get("rank"),
        source_signal=row.get("signal", ""),
        source_recommendation=row.get("recommendation", ""),
        source_setup_type=row.get("setup_type", ""),
        source_final_trade_score=row.get("final_trade_score", ""),
        source_setup_quality_score=row.get("setup_quality_score", ""),
        source_setup_persistence_score=row.get("setup_persistence_score", ""),
        notes=notes,
    )


def append_trade_from_manual_review(
    outcomes_path: Path,
    manual_csv: Path,
    ticker: str,
    entry_date: str,
    entry_price: float | None = None,
    stop_price: float | None = None,
    target_price: float | None = None,
    notes: str = "",
) -> dict:
    record = build_trade_record_from_manual_review(
        manual_csv=manual_csv,
        ticker=ticker,
        entry_date=entry_date,
        entry_price=entry_price,
        stop_price=stop_price,
        target_price=target_price,
        notes=notes,
    )

    return append_trade(outcomes_path=outcomes_path, record=record)


def append_trade(
    outcomes_path: Path,
    record: dict,
) -> dict:
    df = load_outcomes(outcomes_path)

    new_row = pd.DataFrame([record])

    out = pd.concat([df, new_row], ignore_index=True)
    save_outcomes(out, outcomes_path)

    return {
        "status": "PASS",
        "trade_id": record["trade_id"],
        "rows": int(len(out)),
        "outcomes_path": str(outcomes_path),
    }


def close_trade(
    outcomes_path: Path,
    trade_id: str,
    exit_date: str,
    exit_price: float,
    outcome: str,
    notes: str = "",
) -> dict:
    trade_id = _safe_text(trade_id)
    outcome = _safe_text(outcome).upper()

    if outcome not in VALID_OUTCOME:
        raise ValueError(f"Invalid outcome: {outcome}")

    df = load_outcomes(outcomes_path)

    if df.empty:
        return {
            "status": "FAIL",
            "reason": "empty_outcomes_file",
            "trade_id": trade_id,
            "rows": 0,
        }

    mask = df["trade_id"].astype(str).eq(trade_id)

    if not mask.any():
        return {
            "status": "FAIL",
            "reason": "trade_id_not_found",
            "trade_id": trade_id,
            "rows": int(len(df)),
        }

    idx = df.index[mask][0]

    entry_price = _safe_float(df.loc[idx, "entry_price"])
    risk_pct = _safe_float(df.loc[idx, "risk_pct"])
    exit_price = float(exit_price)

    pnl_pct = None
    r_multiple = None

    if entry_price and entry_price > 0:
        pnl_pct = (exit_price - entry_price) / entry_price

    if pnl_pct is not None and risk_pct and risk_pct > 0:
        r_multiple = pnl_pct / risk_pct

    df.loc[idx, "status"] = "CLOSED"
    df.loc[idx, "exit_date"] = _safe_text(exit_date)
    df.loc[idx, "exit_price"] = exit_price
    df.loc[idx, "outcome"] = outcome
    df.loc[idx, "pnl_pct"] = round(float(pnl_pct), 6) if pnl_pct is not None else ""
    df.loc[idx, "r_multiple"] = round(float(r_multiple), 6) if r_multiple is not None else ""

    existing_notes = _safe_text(df.loc[idx, "notes"])
    new_notes = _safe_text(notes)

    if new_notes:
        df.loc[idx, "notes"] = (existing_notes + " | " + new_notes).strip(" | ")

    save_outcomes(df, outcomes_path)

    return {
        "status": "PASS",
        "trade_id": trade_id,
        "rows": int(len(df)),
        "pnl_pct": df.loc[idx, "pnl_pct"],
        "r_multiple": df.loc[idx, "r_multiple"],
    }


def build_outcomes_summary_markdown(df: pd.DataFrame) -> str:
    lines: list[str] = []

    lines.append("# Analista — trade outcomes summary")
    lines.append("")
    lines.append(f"- generated_at: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- rows: {len(df)}")
    lines.append("")

    if df.empty:
        lines.append("_No hay operaciones registradas._")
        return "\n".join(lines)

    status_counts = df["status"].fillna("").astype(str).value_counts().to_dict()
    outcome_counts = df["outcome"].fillna("").astype(str).value_counts().to_dict()

    lines.append("## Status")
    lines.append("")

    for key in ["OPEN", "CLOSED", "CANCELLED"]:
        lines.append(f"- {key}: {int(status_counts.get(key, 0))}")

    lines.append("")
    lines.append("## Outcomes")
    lines.append("")

    for key in ["WIN", "LOSS", "BREAKEVEN", "TIME_EXIT", "MANUAL_EXIT", "CANCELLED"]:
        lines.append(f"- {key}: {int(outcome_counts.get(key, 0))}")

    closed = df[df["status"].fillna("").astype(str).str.upper() == "CLOSED"].copy()

    if not closed.empty:
        closed["pnl_pct_num"] = pd.to_numeric(closed["pnl_pct"], errors="coerce")
        closed["r_multiple_num"] = pd.to_numeric(closed["r_multiple"], errors="coerce")

        avg_pnl = closed["pnl_pct_num"].mean()
        avg_r = closed["r_multiple_num"].mean()

        lines.append("")
        lines.append("## Closed trade stats")
        lines.append("")
        lines.append(f"- avg_pnl_pct: {round(float(avg_pnl), 6) if pd.notna(avg_pnl) else ''}")
        lines.append(f"- avg_r_multiple: {round(float(avg_r), 6) if pd.notna(avg_r) else ''}")

    open_df = df[df["status"].fillna("").astype(str).str.upper() == "OPEN"].copy()

    lines.append("")
    lines.append("## Open trades")
    lines.append("")

    if open_df.empty:
        lines.append("_No hay operaciones abiertas._")
    else:
        display_cols = [
            "trade_id",
            "ticker",
            "entry_date",
            "entry_price",
            "stop_price",
            "target_price",
            "rr",
            "source_signal",
            "source_recommendation",
            "source_final_trade_score",
            "source_setup_persistence_score",
            "notes",
        ]
        display_cols = [col for col in display_cols if col in open_df.columns]

        lines.append("| " + " | ".join(display_cols) + " |")
        lines.append("| " + " | ".join(["---"] * len(display_cols)) + " |")

        for _, row in open_df.iterrows():
            values = []
            for col in display_cols:
                value = row.get(col)
                if pd.isna(value):
                    value = ""
                values.append(str(value).replace("\n", " ").replace("|", "\\|"))
            lines.append("| " + " | ".join(values) + " |")

    return "\n".join(lines)


def save_outcomes_summary(
    outcomes_path: Path,
    markdown_out: Path,
) -> dict:
    df = load_outcomes(outcomes_path)

    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(build_outcomes_summary_markdown(df), encoding="utf-8")

    return {
        "status": "PASS",
        "rows": int(len(df)),
        "markdown_out": str(markdown_out),
    }


def init_outcomes(
    outcomes_path: Path,
    markdown_out: Path,
) -> dict:
    df = load_outcomes(outcomes_path)
    save_outcomes(df, outcomes_path)
    summary = save_outcomes_summary(outcomes_path, markdown_out)

    return {
        "status": "PASS",
        "rows": summary["rows"],
        "outcomes_path": str(outcomes_path),
        "markdown_out": str(markdown_out),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bitácora manual de resultados de trades Analista.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser.add_argument("--outcomes-path", default="reports/trade_outcomes.csv")
    parser.add_argument("--summary-out", default="reports/trade_outcomes_summary.md")

    subparsers.add_parser("init", help="Crea el archivo de outcomes si no existe.")

    add_parser = subparsers.add_parser("add", help="Agrega una operación abierta.")
    add_parser.add_argument("--ticker", required=True)
    add_parser.add_argument("--entry-date", required=True)
    add_parser.add_argument("--entry", type=float, required=True)
    add_parser.add_argument("--stop", type=float, required=True)
    add_parser.add_argument("--target", type=float, required=True)
    add_parser.add_argument("--source-rank")
    add_parser.add_argument("--source-signal", default="")
    add_parser.add_argument("--source-recommendation", default="")
    add_parser.add_argument("--source-setup-type", default="")
    add_parser.add_argument("--source-final-trade-score")
    add_parser.add_argument("--source-setup-quality-score")
    add_parser.add_argument("--source-setup-persistence-score")
    add_parser.add_argument("--notes", default="")

    add_manual_parser = subparsers.add_parser(
        "add-from-manual",
        help="Agrega una operación copiando metadata desde manual_review_latest.csv.",
    )
    add_manual_parser.add_argument("--manual-csv", default="reports/manual_review_latest.csv")
    add_manual_parser.add_argument("--ticker", required=True)
    add_manual_parser.add_argument("--entry-date", required=True)
    add_manual_parser.add_argument("--entry", type=float)
    add_manual_parser.add_argument("--stop", type=float)
    add_manual_parser.add_argument("--target", type=float)
    add_manual_parser.add_argument("--notes", default="")

    close_parser = subparsers.add_parser("close", help="Cierra una operación existente.")
    close_parser.add_argument("--trade-id", required=True)
    close_parser.add_argument("--exit-date", required=True)
    close_parser.add_argument("--exit-price", type=float, required=True)
    close_parser.add_argument("--outcome", required=True)
    close_parser.add_argument("--notes", default="")

    subparsers.add_parser("summary", help="Genera resumen Markdown.")

    args = parser.parse_args()

    outcomes_path = ROOT / args.outcomes_path
    summary_out = ROOT / args.summary_out

    if args.command == "init":
        result = init_outcomes(outcomes_path, summary_out)

    elif args.command == "add":
        record = build_trade_record(
            ticker=args.ticker,
            entry_date=args.entry_date,
            entry_price=args.entry,
            stop_price=args.stop,
            target_price=args.target,
            source_rank=args.source_rank,
            source_signal=args.source_signal,
            source_recommendation=args.source_recommendation,
            source_setup_type=args.source_setup_type,
            source_final_trade_score=args.source_final_trade_score,
            source_setup_quality_score=args.source_setup_quality_score,
            source_setup_persistence_score=args.source_setup_persistence_score,
            notes=args.notes,
        )
        result = append_trade(outcomes_path, record)
        save_outcomes_summary(outcomes_path, summary_out)

    elif args.command == "add-from-manual":
        result = append_trade_from_manual_review(
            outcomes_path=outcomes_path,
            manual_csv=ROOT / args.manual_csv,
            ticker=args.ticker,
            entry_date=args.entry_date,
            entry_price=args.entry,
            stop_price=args.stop,
            target_price=args.target,
            notes=args.notes,
        )
        save_outcomes_summary(outcomes_path, summary_out)

    elif args.command == "close":
        result = close_trade(
            outcomes_path=outcomes_path,
            trade_id=args.trade_id,
            exit_date=args.exit_date,
            exit_price=args.exit_price,
            outcome=args.outcome,
            notes=args.notes,
        )
        save_outcomes_summary(outcomes_path, summary_out)

    elif args.command == "summary":
        result = save_outcomes_summary(outcomes_path, summary_out)

    else:
        raise ValueError(f"Unknown command: {args.command}")

    print("=== ANALISTA TRADE OUTCOME TRACKER ===")
    print(f"Status: {result['status']}")
    print(f"Rows: {result.get('rows', '')}")
    print(f"Outcomes: {outcomes_path}")
    print(f"Summary: {summary_out}")

    if "trade_id" in result:
        print(f"Trade ID: {result['trade_id']}")

    if "reason" in result:
        print(f"Reason: {result['reason']}")

    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())