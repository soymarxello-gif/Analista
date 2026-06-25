from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


NO_REAL_ORDER_NOTICE = "paper trading only; no real order"

CLOSE_COLUMNS = [
    "exit_date",
    "exit_price",
    "close_reason",
    "closed_at",
    "pnl_pct",
    "r_multiple",
    "outcome_exported",
    "outcome_exported_at",
]

REPORT_COLUMNS = [
    "journal_id",
    "ticker",
    "run_date",
    "manual_decision",
    "followup_status",
    "simulated_entry_price",
    "simulated_stop",
    "simulated_target",
    "exit_date",
    "exit_price",
    "close_reason",
    "pnl_pct",
    "r_multiple",
    "outcome_exported",
    "paper_close_action",
    "paper_close_reason",
    "no_real_order_notice",
]

OUTCOME_COLUMNS = [
    "trade_id",
    "ticker",
    "entry_date",
    "run_date",
    "exit_date",
    "entry_price",
    "exit_price",
    "stop_price",
    "target_price",
    "pnl_pct",
    "r_multiple",
    "holding_days",
    "status",
    "outcome",
    "setup_type",
    "checklist_status",
    "signal",
    "recommendation",
    "final_trade_score",
    "checklist_score",
    "setup_quality_score",
    "institutional_score",
    "options_bias",
    "options_confidence",
    "close_reason",
    "source",
    "source_journal_id",
]

CLOSE_REASONS = {
    "TARGET_REACHED_MANUAL",
    "STOP_REACHED_MANUAL",
    "TECHNICAL_INVALIDATION",
    "TIME_EXIT",
    "MANUAL_RISK_REDUCTION",
    "DATA_QUALITY_EXIT",
    "OTHER",
}


def _ensure_object_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].astype("object")
    return df


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


def _safe_float(value):
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None

def _metric_to_text(value) -> str:
    if value is None or value == "":
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    try:
        return str(round(float(value), 6))
    except Exception:
        return ""

def _safe_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _today() -> str:
    return date.today().isoformat()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_report_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=REPORT_COLUMNS)


def _fill_missing_text(df: pd.DataFrame) -> pd.DataFrame:
    return df.astype(object).where(pd.notna(df), "")


def load_journal(path: Path) -> tuple[pd.DataFrame, str]:
    if not path.exists():
        return pd.DataFrame(), "journal_csv_not_found"
    try:
        df = _fill_missing_text(pd.read_csv(path, dtype=str))
    except Exception as exc:
        return pd.DataFrame(), f"journal_csv_read_failed:{exc}"

    for col in CLOSE_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    if "no_real_order_notice" not in df.columns:
        df["no_real_order_notice"] = NO_REAL_ORDER_NOTICE
    return df.copy(), ""


def save_journal(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    for col in CLOSE_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    if "no_real_order_notice" not in out.columns:
        out["no_real_order_notice"] = NO_REAL_ORDER_NOTICE
    out.to_csv(path, index=False)


def is_open_paper_trade(row: dict) -> bool:
    manual_decision = _safe_text(row.get("manual_decision")).upper()
    followup_status = _safe_text(row.get("followup_status")).upper()

    if followup_status in {"CLOSED_PAPER", "INVALIDATED", "EXPIRED"}:
        return False

    return manual_decision == "PAPER_ENTER" or followup_status == "ENTERED_PAPER"


def list_open_paper_trades(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    mask = df.apply(lambda row: is_open_paper_trade(row.to_dict()), axis=1)
    return df[mask].copy().reset_index(drop=True)


def _closed_paper_mask(df: pd.DataFrame) -> pd.Series:
    if df.empty or "followup_status" not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    return df["followup_status"].fillna("").astype(str).str.upper().eq("CLOSED_PAPER")


def _normalize_close_reason(reason: str) -> str:
    text = _safe_text(reason).upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "TARGET_REACHED": "TARGET_REACHED_MANUAL",
        "TARGET_REACHED_MANUALLY": "TARGET_REACHED_MANUAL",
        "TARGET_REACHED_MANUAL": "TARGET_REACHED_MANUAL",
        "STOP_REACHED": "STOP_REACHED_MANUAL",
        "STOP_REACHED_MANUALLY": "STOP_REACHED_MANUAL",
        "STOP_REACHED_MANUAL": "STOP_REACHED_MANUAL",
        "MANUAL_CLOSE": "OTHER",
    }
    text = aliases.get(text, text)
    return text if text in CLOSE_REASONS else "OTHER"


def _find_trade_index(df: pd.DataFrame, identifier: str, *, force: bool = False):
    identifier_text = _safe_text(identifier)
    if df.empty or not identifier_text:
        return None

    journal_id_match = pd.Series([False] * len(df), index=df.index)
    if "journal_id" in df.columns:
        journal_id_match = df["journal_id"].fillna("").astype(str).eq(identifier_text)

    ticker_match = pd.Series([False] * len(df), index=df.index)
    if "ticker" in df.columns:
        ticker_match = df["ticker"].fillna("").astype(str).str.upper().eq(identifier_text.upper())

    matches = df[journal_id_match | ticker_match].copy()
    if matches.empty:
        return None

    if not force:
        open_mask = matches.apply(lambda row: is_open_paper_trade(row.to_dict()), axis=1)
        matches = matches[open_mask].copy()
        if matches.empty:
            return "not_open"

    sort_cols = [col for col in ["run_date", "generated_at", "closed_at"] if col in matches.columns]
    if sort_cols:
        matches = matches.sort_values(sort_cols)
    return matches.index[-1]


def calculate_close_metrics(row: dict, exit_price: float) -> tuple[float | str, float | str]:
    entry = _safe_float(row.get("simulated_entry_price") or row.get("actionable_entry"))
    stop = _safe_float(row.get("simulated_stop") or row.get("actionable_stop"))
    if entry is None or entry <= 0:
        return "", ""

    pnl_pct = (exit_price - entry) / entry
    r_multiple = ""
    if stop is not None:
        risk = entry - stop
        if risk > 0:
            r_multiple = (exit_price - entry) / risk

    return round(float(pnl_pct), 6), round(float(r_multiple), 6) if r_multiple != "" else ""


def close_paper_trade(
    journal_df: pd.DataFrame,
    *,
    identifier: str,
    exit_price,
    exit_date: str | None,
    reason: str,
    force: bool = False,
) -> tuple[pd.DataFrame, dict]:
    if exit_price is None:
        return journal_df, {"status": "FAIL", "error": "exit_price_required"}
    if not _safe_text(reason):
        return journal_df, {"status": "FAIL", "error": "close_reason_required"}

    price = _safe_float(exit_price)
    if price is None or price <= 0:
        return journal_df, {"status": "FAIL", "error": "exit_price_invalid"}

    idx = _find_trade_index(journal_df, identifier, force=force)
    if idx is None:
        return journal_df, {"status": "FAIL", "error": "paper_trade_not_found"}
    if idx == "not_open":
        return journal_df, {"status": "FAIL", "error": "paper_trade_not_open_requires_force"}

    df = journal_df.copy()
    for col in CLOSE_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    row = df.loc[idx].to_dict()
    if not force and not is_open_paper_trade(row):
        return journal_df, {"status": "FAIL", "error": "paper_trade_not_open_requires_force"}

    pnl_pct, r_multiple = calculate_close_metrics(row, price)
    close_reason = _normalize_close_reason(reason)

    df = _ensure_object_columns(
        df,
        [
            "exit_date",
            "exit_price",
            "close_reason",
            "closed_at",
            "pnl_pct",
            "r_multiple",
            "outcome_exported",
            "outcome_exported_at",
            "followup_status",
            "manual_decision",
            "no_real_order_notice",
        ],
    )

    closed_at = _utc_now()
    exit_date_value = _safe_text(exit_date) or _today()

    df.loc[idx, "exit_price"] = str(price)
    df.loc[idx, "exit_date"] = exit_date_value
    df.loc[idx, "close_reason"] = close_reason
    df.loc[idx, "closed_at"] = closed_at
    df.loc[idx, "followup_status"] = "CLOSED_PAPER"
    df.loc[idx, "pnl_pct"] = _metric_to_text(pnl_pct)
    df.loc[idx, "r_multiple"] = _metric_to_text(r_multiple)
    df.loc[idx, "manual_decision"] = "PAPER_ENTER"
    df.loc[idx, "no_real_order_notice"] = NO_REAL_ORDER_NOTICE

    return _fill_missing_text(df).copy(), {
        "status": "PASS",
        "error": "",
        "closed_journal_id": _safe_text(df.loc[idx].get("journal_id")),
        "ticker": _safe_text(df.loc[idx].get("ticker")).upper(),
        "pnl_pct": pnl_pct,
        "r_multiple": r_multiple,
        "close_reason": close_reason,
    }


def _outcome_from_close(row: dict) -> str:
    pnl = _safe_float(row.get("pnl_pct"))
    reason = _safe_text(row.get("close_reason")).upper()
    if reason == "TIME_EXIT":
        return "TIME_EXIT"
    if pnl is None:
        return "MANUAL_EXIT"
    if pnl > 0:
        return "WIN"
    if pnl < 0:
        return "LOSS"
    return "BREAKEVEN"


def _holding_days(entry_date: str, exit_date: str):
    try:
        start = pd.to_datetime(entry_date)
        end = pd.to_datetime(exit_date)
        if pd.isna(start) or pd.isna(end):
            return ""
        return int((end - start).days)
    except Exception:
        return ""


def _build_outcome_record(row: dict) -> dict:
    journal_id = _safe_text(row.get("journal_id"))
    ticker = _safe_text(row.get("ticker")).upper()
    entry_date = _safe_text(row.get("run_date"))
    exit_date = _safe_text(row.get("exit_date"))
    return {
        "trade_id": f"PAPER_{journal_id}" if journal_id else f"PAPER_{ticker}_{entry_date}",
        "ticker": ticker,
        "entry_date": entry_date,
        "run_date": entry_date,
        "exit_date": exit_date,
        "entry_price": row.get("simulated_entry_price") or row.get("actionable_entry"),
        "exit_price": row.get("exit_price"),
        "stop_price": row.get("simulated_stop") or row.get("actionable_stop"),
        "target_price": row.get("simulated_target") or row.get("actionable_target"),
        "pnl_pct": row.get("pnl_pct"),
        "r_multiple": row.get("r_multiple"),
        "holding_days": _holding_days(entry_date, exit_date),
        "status": "CLOSED",
        "outcome": _outcome_from_close(row),
        "setup_type": row.get("setup_type", ""),
        "checklist_status": row.get("checklist_status", ""),
        "signal": row.get("signal", ""),
        "recommendation": row.get("recommendation", ""),
        "final_trade_score": row.get("final_trade_score", ""),
        "checklist_score": row.get("checklist_score", ""),
        "setup_quality_score": row.get("setup_quality_score", ""),
        "institutional_score": row.get("institutional_score", ""),
        "options_bias": row.get("options_bias", ""),
        "options_confidence": row.get("options_confidence", ""),
        "close_reason": row.get("close_reason", ""),
        "source": "PAPER_TRADING_JOURNAL",
        "source_journal_id": journal_id,
    }


def _load_outcomes(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=OUTCOME_COLUMNS)
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        df = pd.DataFrame(columns=OUTCOME_COLUMNS)
    for col in OUTCOME_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df.copy()


def export_closed_to_outcomes(
    journal_df: pd.DataFrame,
    *,
    outcomes_path: Path,
) -> tuple[pd.DataFrame, dict]:
    df = journal_df.copy()
    for col in CLOSE_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    if df.empty:
        return df, {"status": "PASS", "exported_outcomes": 0, "skipped_already_exported": 0}

    closed_mask = _closed_paper_mask(df)
    not_exported_mask = ~df["outcome_exported"].apply(_safe_bool)
    export_df = df[closed_mask & not_exported_mask].copy()
    skipped = int((closed_mask & ~not_exported_mask).sum())

    if export_df.empty:
        return df, {
            "status": "PASS",
            "exported_outcomes": 0,
            "skipped_already_exported": skipped,
        }

    outcomes = _load_outcomes(outcomes_path)
    existing_journal_ids = set()
    if "source_journal_id" in outcomes.columns:
        existing_journal_ids = {
            _safe_text(value)
            for value in outcomes["source_journal_id"].fillna("").astype(str).tolist()
            if _safe_text(value)
        }

    records: list[dict] = []
    exported_indexes: list[int] = []
    duplicate_indexes: list[int] = []
    for idx, row in export_df.iterrows():
        row_dict = row.to_dict()
        journal_id = _safe_text(row_dict.get("journal_id"))
        if journal_id and journal_id in existing_journal_ids:
            skipped += 1
            duplicate_indexes.append(idx)
            continue
        records.append(_build_outcome_record(row_dict))
        exported_indexes.append(idx)
        if journal_id:
            existing_journal_ids.add(journal_id)

    if records:
        outcomes = pd.concat([outcomes, pd.DataFrame(records)], ignore_index=True)
        for col in OUTCOME_COLUMNS:
            if col not in outcomes.columns:
                outcomes[col] = ""
        outcomes_path.parent.mkdir(parents=True, exist_ok=True)
        outcomes.to_csv(outcomes_path, index=False)

        exported_at = _utc_now()
        for idx in exported_indexes:
            df.loc[idx, "outcome_exported"] = "True"
            df.loc[idx, "outcome_exported_at"] = exported_at

    if duplicate_indexes:
        exported_at = _utc_now()
        for idx in duplicate_indexes:
            df.loc[idx, "outcome_exported"] = "True"
            df.loc[idx, "outcome_exported_at"] = exported_at

    return _fill_missing_text(df).copy(), {
        "status": "PASS",
        "exported_outcomes": len(records),
        "skipped_already_exported": skipped,
        "marked_duplicate_exports": len(duplicate_indexes),
        "outcomes_path": str(outcomes_path),
    }


def build_report_dataframe(journal_df: pd.DataFrame, *, action: str, reason: str = "") -> pd.DataFrame:
    if journal_df.empty:
        return _empty_report_dataframe()

    out = journal_df.copy()
    for col in REPORT_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    out["paper_close_action"] = action
    out["paper_close_reason"] = reason
    out["no_real_order_notice"] = NO_REAL_ORDER_NOTICE

    if action == "LIST_OPEN":
        out = list_open_paper_trades(out)
    elif action == "SUMMARY":
        pass
    elif action in {"CLOSE", "EXPORT_OUTCOMES"}:
        closed = _closed_paper_mask(out)
        opened = out.apply(lambda row: is_open_paper_trade(row.to_dict()), axis=1)
        out = out[closed | opened].copy()

    return _fill_missing_text(out[REPORT_COLUMNS]).copy()


def build_summary_payload(
    report_df: pd.DataFrame,
    journal_df: pd.DataFrame,
    *,
    status: str = "PASS",
    action: str = "SUMMARY",
    error: str = "",
    closed_result: dict | None = None,
    export_result: dict | None = None,
    journal_path: Path | None = None,
    outcomes_path: Path | None = None,
    csv_out: Path | None = None,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict:
    open_count = int(len(list_open_paper_trades(journal_df))) if not journal_df.empty else 0
    closed_count = int(_closed_paper_mask(journal_df).sum()) if not journal_df.empty else 0
    pending_export = 0
    exported_count = 0
    if not journal_df.empty:
        exported = journal_df.get("outcome_exported", pd.Series([""] * len(journal_df))).apply(_safe_bool)
        closed = _closed_paper_mask(journal_df)
        pending_export = int((closed & ~exported).sum())
        exported_count = int((closed & exported).sum())

    return {
        "status": status,
        "action": action,
        "rows": int(len(report_df)),
        "open_paper_trades": open_count,
        "closed_paper_trades": closed_count,
        "pending_export": pending_export,
        "exported_outcomes": int((export_result or {}).get("exported_outcomes", 0) or 0),
        "total_exported_outcomes": exported_count,
        "error": error,
        "closed_result": closed_result or {},
        "export_result": export_result or {},
        "journal_path": str(journal_path or ""),
        "outcomes_path": str(outcomes_path or ""),
        "csv_out": str(csv_out or ""),
        "json_out": str(json_out or ""),
        "markdown_out": str(markdown_out or ""),
        "no_real_order_notice": NO_REAL_ORDER_NOTICE,
        "generated_at": _utc_now(),
    }


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_Sin filas._"
    columns = list(df.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in df.iterrows():
        values = []
        for col in columns:
            value = row.get(col)
            if pd.isna(value):
                value = ""
            values.append(str(value).replace("\n", " ").replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def build_markdown(payload: dict, report_df: pd.DataFrame) -> str:
    lines: list[str] = []
    lines.append("# Analista - paper trade close")
    lines.append("")
    lines.append(f"- status: {payload.get('status')}")
    lines.append(f"- action: {payload.get('action')}")
    lines.append(f"- open_paper_trades: {payload.get('open_paper_trades')}")
    lines.append(f"- closed_paper_trades: {payload.get('closed_paper_trades')}")
    lines.append(f"- pending_export: {payload.get('pending_export')}")
    lines.append(f"- exported_outcomes: {payload.get('exported_outcomes')}")
    lines.append(f"- total_exported_outcomes: {payload.get('total_exported_outcomes')}")
    lines.append(f"- notice: {NO_REAL_ORDER_NOTICE}")
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    lines.append("")
    lines.append("## Guardrails")
    lines.append("")
    lines.append("- Paper trading only; no real order.")
    lines.append("- No broker connection is used.")
    lines.append("- No real orders are sent.")
    lines.append("- Close and export require explicit CLI flags.")
    lines.append("")
    lines.append("## Rows")
    lines.append("")
    display_cols = [
        "journal_id",
        "ticker",
        "run_date",
        "manual_decision",
        "followup_status",
        "simulated_entry_price",
        "exit_date",
        "exit_price",
        "close_reason",
        "pnl_pct",
        "r_multiple",
        "outcome_exported",
    ]
    display_cols = [col for col in display_cols if col in report_df.columns]
    lines.append(_df_to_markdown_table(report_df[display_cols] if display_cols else report_df))
    return "\n".join(lines)


def write_reports(report_df: pd.DataFrame, payload: dict, *, csv_out: Path, json_out: Path, markdown_out: Path) -> None:
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    report_df.to_csv(csv_out, index=False)
    json_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_markdown(payload, report_df), encoding="utf-8")


def save_paper_trade_close_reports(
    *,
    journal_path: Path | None = None,
    outcomes_path: Path | None = None,
    csv_out: Path | None = None,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
    root: Path = ROOT,
    list_open: bool = False,
    summary: bool = False,
    close_identifier: str | None = None,
    exit_price=None,
    exit_date: str | None = None,
    reason: str = "",
    export_outcomes: bool = False,
    force: bool = False,
) -> dict:
    journal_path = journal_path or root / "data" / "paper_trading_journal.csv"
    outcomes_path = outcomes_path or root / "data" / "trade_outcomes.csv"
    csv_out = csv_out or root / "reports" / "paper_trade_close_latest.csv"
    json_out = json_out or root / "reports" / "paper_trade_close_latest.json"
    markdown_out = markdown_out or root / "reports" / "paper_trade_close_latest.md"

    journal_df, load_error = load_journal(journal_path)
    action = "LIST_OPEN" if list_open else "SUMMARY"
    status = "PASS"
    error = ""
    closed_result: dict = {}
    export_result: dict = {}
    journal_changed = False

    if load_error:
        status = "WARN" if load_error == "journal_csv_not_found" else "FAIL"
        error = load_error
        report_df = _empty_report_dataframe()
        payload = build_summary_payload(
            report_df,
            journal_df,
            status=status,
            action=action,
            error=error,
            journal_path=journal_path,
            outcomes_path=outcomes_path,
            csv_out=csv_out,
            json_out=json_out,
            markdown_out=markdown_out,
        )
        write_reports(report_df, payload, csv_out=csv_out, json_out=json_out, markdown_out=markdown_out)
        return payload

    if close_identifier:
        action = "CLOSE"
        journal_df, closed_result = close_paper_trade(
            journal_df,
            identifier=close_identifier,
            exit_price=exit_price,
            exit_date=exit_date,
            reason=reason,
            force=force,
        )
        status = closed_result.get("status", "FAIL")
        error = closed_result.get("error", "")
        journal_changed = status == "PASS"

    if export_outcomes and status != "FAIL":
        action = "EXPORT_OUTCOMES" if not close_identifier else "CLOSE_AND_EXPORT"
        journal_df, export_result = export_closed_to_outcomes(journal_df, outcomes_path=outcomes_path)
        if export_result.get("status") == "FAIL":
            status = "FAIL"
            error = export_result.get("error", "")
        journal_changed = journal_changed or bool(
            export_result.get("exported_outcomes", 0)
            or export_result.get("marked_duplicate_exports", 0)
        )

    if journal_changed:
        save_journal(journal_path, journal_df)

    report_df = build_report_dataframe(
        journal_df,
        action=action,
        reason=error or closed_result.get("close_reason", "") or "",
    )
    payload = build_summary_payload(
        report_df,
        journal_df,
        status=status,
        action=action,
        error=error,
        closed_result=closed_result,
        export_result=export_result,
        journal_path=journal_path,
        outcomes_path=outcomes_path,
        csv_out=csv_out,
        json_out=json_out,
        markdown_out=markdown_out,
    )
    write_reports(report_df, payload, csv_out=csv_out, json_out=json_out, markdown_out=markdown_out)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Cierre manual de paper trades y export controlado.")
    parser.add_argument("--journal-path", default="data/paper_trading_journal.csv")
    parser.add_argument("--outcomes-path", default="data/trade_outcomes.csv")
    parser.add_argument("--csv-out", default="reports/paper_trade_close_latest.csv")
    parser.add_argument("--json-out", default="reports/paper_trade_close_latest.json")
    parser.add_argument("--markdown-out", default="reports/paper_trade_close_latest.md")
    parser.add_argument("--list-open", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--close", dest="close_identifier")
    parser.add_argument("--exit-price")
    parser.add_argument("--exit-date")
    parser.add_argument("--reason", default="")
    parser.add_argument("--export-outcomes", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    result = save_paper_trade_close_reports(
        root=ROOT,
        journal_path=ROOT / args.journal_path,
        outcomes_path=ROOT / args.outcomes_path,
        csv_out=ROOT / args.csv_out,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
        list_open=args.list_open,
        summary=args.summary,
        close_identifier=args.close_identifier,
        exit_price=args.exit_price,
        exit_date=args.exit_date,
        reason=args.reason,
        export_outcomes=args.export_outcomes,
        force=args.force,
    )

    print("=== ANALISTA PAPER TRADE CLOSE ===")
    print(f"Status: {result['status']}")
    print(f"Action: {result['action']}")
    print(f"Open paper trades: {result['open_paper_trades']}")
    print(f"Closed paper trades: {result['closed_paper_trades']}")
    print(f"Pending export: {result['pending_export']}")
    print(f"Exported outcomes: {result['exported_outcomes']}")
    print(f"Notice: {result['no_real_order_notice']}")
    print(f"CSV: {result['csv_out']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")
    if result.get("error"):
        print(f"Error: {result['error']}")

    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
