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


JOURNAL_COLUMNS = [
    "journal_id",
    "run_date",
    "generated_at",
    "ticker",
    "checklist_status",
    "signal",
    "recommendation",
    "setup_type",
    "sector",
    "industry",
    "final_trade_score",
    "operational_readiness_score",
    "operational_readiness_bucket",
    "scenario_status",
    "scenario_confidence",
    "scenario_operability",
    "scenario_eligible_for_backtest",
    "momentum_state",
    "extension_state",
    "entry_timing_status",
    "engine_recommendation",
    "execution_readiness_status",
    "macro_regime_mode",
    "macro_event_risk",
    "portfolio_concentration_flag",
    "checklist_score",
    "institutional_score",
    "options_score",
    "options_bias",
    "options_confidence",
    "quote_status",
    "execution_quote_quality",
    "actionable_entry",
    "actionable_stop",
    "actionable_target",
    "rr",
    "manual_decision",
    "manual_decision_reason",
    "simulated_entry_planned",
    "simulated_entry_price",
    "simulated_stop",
    "simulated_target",
    "simulated_risk_pct",
    "followup_status",
    "followup_notes",
    "source_report",
    "no_real_order_notice",
]

IMPORT_FIELDS = [
    "ticker",
    "checklist_status",
    "signal",
    "recommendation",
    "setup_type",
    "sector",
    "industry",
    "final_trade_score",
    "operational_readiness_score",
    "operational_readiness_bucket",
    "scenario_status",
    "scenario_confidence",
    "scenario_operability",
    "scenario_eligible_for_backtest",
    "momentum_state",
    "extension_state",
    "entry_timing_status",
    "engine_recommendation",
    "execution_readiness_status",
    "macro_regime_mode",
    "macro_event_risk",
    "portfolio_concentration_flag",
    "checklist_score",
    "institutional_score",
    "options_score",
    "options_bias",
    "options_confidence",
    "quote_status",
    "execution_quote_quality",
    "actionable_entry",
    "actionable_stop",
    "actionable_target",
    "rr",
]

MANUAL_DECISIONS = {
    "PENDING_REVIEW",
    "PAPER_WATCH",
    "PAPER_ENTER",
    "SKIP",
    "BLOCKED",
    "NEEDS_LIVE_QUOTE_RECHECK",
}

FOLLOWUP_STATUSES = {
    "OPEN_MONITORING",
    "NOT_ENTERED",
    "ENTERED_PAPER",
    "CLOSED_PAPER",
    "INVALIDATED",
    "EXPIRED",
}

NO_REAL_ORDER_NOTICE = "paper trading only; no real order"


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


def _today() -> str:
    return date.today().isoformat()


def empty_journal_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=JOURNAL_COLUMNS)


def ensure_journal(path: Path) -> pd.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        df = empty_journal_dataframe()
        df.to_csv(path, index=False)
        return df
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        df = empty_journal_dataframe()
    for col in JOURNAL_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[JOURNAL_COLUMNS].copy()


def _write_journal(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    for col in JOURNAL_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    out[JOURNAL_COLUMNS].to_csv(path, index=False)


def _load_cards_json(path: Path) -> tuple[pd.DataFrame, str]:
    if not path.exists():
        return pd.DataFrame(), "cards_json_not_found"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return pd.DataFrame(), f"cards_json_read_failed:{exc}"
    cards = data.get("cards", []) if isinstance(data, dict) else []
    if not isinstance(cards, list):
        return pd.DataFrame(), "cards_json_cards_not_list"
    return pd.DataFrame(cards), ""


def _load_csv(path: Path) -> tuple[pd.DataFrame, str]:
    if not path.exists():
        return pd.DataFrame(), f"csv_not_found:{path}"
    try:
        return pd.read_csv(path), ""
    except Exception as exc:
        return pd.DataFrame(), f"csv_read_failed:{exc}"


def load_import_candidates(
    *,
    cards_json: Path,
    checklist_csv: Path,
    manual_top_csv: Path,
    live_quote_csv: Path | None = None,
) -> tuple[pd.DataFrame, str, str]:
    cards_df, cards_error = _load_cards_json(cards_json)
    if not cards_df.empty:
        return cards_df, str(cards_json), ""

    checklist_df, checklist_error = _load_csv(checklist_csv)
    if not checklist_df.empty:
        return checklist_df, str(checklist_csv), cards_error

    manual_df, manual_error = _load_csv(manual_top_csv)
    if not manual_df.empty:
        return manual_df, str(manual_top_csv), "; ".join([cards_error, checklist_error])

    errors = [cards_error, checklist_error, manual_error]
    if live_quote_csv:
        _live_df, live_error = _load_csv(live_quote_csv)
        if live_error:
            errors.append(live_error)
    return pd.DataFrame(), "", "; ".join(error for error in errors if error)


def _manual_decision_for_status(checklist_status: str) -> str:
    status = _safe_text(checklist_status).upper()
    if status == "BLOCKED":
        return "BLOCKED"
    if status == "NEEDS_LIVE_QUOTE_RECHECK":
        return "NEEDS_LIVE_QUOTE_RECHECK"
    return "PENDING_REVIEW"


def _followup_for_decision(decision: str) -> str:
    if decision == "PAPER_WATCH":
        return "OPEN_MONITORING"
    if decision == "PAPER_ENTER":
        return "ENTERED_PAPER"
    if decision in {"SKIP", "BLOCKED", "NEEDS_LIVE_QUOTE_RECHECK"}:
        return "NOT_ENTERED"
    return "OPEN_MONITORING"


def _new_journal_id(run_date: str, ticker: str) -> str:
    return f"{run_date}-{ticker.upper()}"


def _candidate_to_journal_row(row: dict, *, run_date: str, source_report: str) -> dict:
    ticker = _safe_text(row.get("ticker")).upper()
    checklist_status = _safe_text(row.get("checklist_status")).upper()
    decision = _manual_decision_for_status(checklist_status)
    out = {col: "" for col in JOURNAL_COLUMNS}
    out.update(
        {
            "journal_id": _new_journal_id(run_date, ticker),
            "run_date": run_date,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ticker": ticker,
            "manual_decision": decision,
            "manual_decision_reason": "",
            "simulated_entry_planned": "False",
            "followup_status": _followup_for_decision(decision),
            "followup_notes": "",
            "source_report": source_report,
            "no_real_order_notice": NO_REAL_ORDER_NOTICE,
        }
    )
    for field in IMPORT_FIELDS:
        out[field] = _safe_text(row.get(field))
    out["ticker"] = ticker
    out["checklist_status"] = checklist_status
    out["signal"] = _safe_text(row.get("signal")).upper()
    out["recommendation"] = _safe_text(row.get("recommendation")).upper()
    return out


def import_candidates_today(
    journal_df: pd.DataFrame,
    candidates_df: pd.DataFrame,
    *,
    run_date: str,
    source_report: str,
) -> tuple[pd.DataFrame, int]:
    journal = journal_df.copy()
    for col in JOURNAL_COLUMNS:
        if col not in journal.columns:
            journal[col] = ""

    if candidates_df.empty:
        return journal[JOURNAL_COLUMNS].copy(), 0

    existing_keys = {
        (str(row.get("ticker", "")).upper(), str(row.get("run_date", "")))
        for _, row in journal.iterrows()
    }
    rows: list[dict] = []
    for _, item in candidates_df.iterrows():
        row = item.to_dict()
        ticker = _safe_text(row.get("ticker")).upper()
        if not ticker:
            continue
        key = (ticker, run_date)
        if key in existing_keys:
            continue
        rows.append(_candidate_to_journal_row(row, run_date=run_date, source_report=source_report))
        existing_keys.add(key)

    if rows:
        journal = pd.concat([journal, pd.DataFrame(rows)], ignore_index=True)

    return journal[JOURNAL_COLUMNS].fillna("").copy(), len(rows)


def _latest_row_index(df: pd.DataFrame, ticker: str, run_date: str | None = None):
    ticker = ticker.upper()
    mask = df["ticker"].fillna("").astype(str).str.upper() == ticker
    if run_date:
        mask &= df["run_date"].fillna("").astype(str) == run_date
    matches = df[mask]
    if matches.empty:
        return None
    matches = matches.sort_values(["run_date", "generated_at"])
    return matches.index[-1]


def _require_paper_enter_levels(entry, stop, target) -> tuple[bool, str]:
    entry_f = _safe_float(entry)
    stop_f = _safe_float(stop)
    target_f = _safe_float(target)
    if entry_f is None or stop_f is None or target_f is None:
        return False, "paper_enter_requires_entry_stop_target"
    if entry_f <= 0 or stop_f <= 0 or target_f <= 0:
        return False, "paper_enter_requires_positive_entry_stop_target"
    return True, ""


def set_manual_decision(
    journal_df: pd.DataFrame,
    *,
    ticker: str,
    decision: str,
    reason: str,
    entry=None,
    stop=None,
    target=None,
    run_date: str | None = None,
    confirm_live_quote: bool = False,
) -> tuple[pd.DataFrame, dict]:
    decision = _safe_text(decision).upper()
    if decision not in MANUAL_DECISIONS:
        return journal_df, {"status": "FAIL", "error": "invalid_manual_decision"}
    if decision != "PENDING_REVIEW" and not _safe_text(reason):
        return journal_df, {"status": "FAIL", "error": "manual_decision_reason_required"}

    df = journal_df.copy()
    idx = _latest_row_index(df, ticker, run_date=run_date)
    if idx is None:
        return journal_df, {"status": "FAIL", "error": "ticker_not_found"}

    checklist_status = _safe_text(df.at[idx, "checklist_status"]).upper()
    if decision == "PAPER_ENTER":
        if checklist_status == "BLOCKED":
            return journal_df, {"status": "FAIL", "error": "blocked_candidate_cannot_paper_enter"}
        if checklist_status == "NEEDS_LIVE_QUOTE_RECHECK" and not confirm_live_quote:
            return journal_df, {
                "status": "FAIL",
                "error": "needs_live_quote_recheck_requires_confirm_live_quote",
            }
        ok, error = _require_paper_enter_levels(entry, stop, target)
        if not ok:
            return journal_df, {"status": "FAIL", "error": error}

    df.at[idx, "manual_decision"] = decision
    df.at[idx, "manual_decision_reason"] = reason
    df.at[idx, "generated_at"] = datetime.now(timezone.utc).isoformat()
    if decision == "PAPER_ENTER":
        entry_f = _safe_float(entry)
        stop_f = _safe_float(stop)
        target_f = _safe_float(target)
        df.at[idx, "simulated_entry_planned"] = "True"
        df.at[idx, "simulated_entry_price"] = entry_f
        df.at[idx, "simulated_stop"] = stop_f
        df.at[idx, "simulated_target"] = target_f
        df.at[idx, "simulated_risk_pct"] = round(abs(entry_f - stop_f) / entry_f * 100, 6)
    elif decision in {"SKIP", "BLOCKED", "NEEDS_LIVE_QUOTE_RECHECK"}:
        df.at[idx, "simulated_entry_planned"] = "False"
    df.at[idx, "followup_status"] = _followup_for_decision(decision)
    df.at[idx, "no_real_order_notice"] = NO_REAL_ORDER_NOTICE

    return df[JOURNAL_COLUMNS].fillna("").copy(), {"status": "PASS", "error": ""}


def set_followup_status(
    journal_df: pd.DataFrame,
    *,
    ticker: str,
    followup_status: str,
    notes: str = "",
    run_date: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    followup_status = _safe_text(followup_status).upper()
    if followup_status not in FOLLOWUP_STATUSES:
        return journal_df, {"status": "FAIL", "error": "invalid_followup_status"}
    df = journal_df.copy()
    idx = _latest_row_index(df, ticker, run_date=run_date)
    if idx is None:
        return journal_df, {"status": "FAIL", "error": "ticker_not_found"}
    df.at[idx, "followup_status"] = followup_status
    df.at[idx, "followup_notes"] = notes
    df.at[idx, "generated_at"] = datetime.now(timezone.utc).isoformat()
    df.at[idx, "no_real_order_notice"] = NO_REAL_ORDER_NOTICE
    return df[JOURNAL_COLUMNS].fillna("").copy(), {"status": "PASS", "error": ""}


def build_summary_payload(
    journal_df: pd.DataFrame,
    *,
    status: str = "PASS",
    imported_rows: int = 0,
    error: str = "",
    journal_path: Path | None = None,
    csv_out: Path | None = None,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
) -> dict:
    df = journal_df.copy()
    for col in JOURNAL_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    decisions = df["manual_decision"].fillna("").astype(str).str.upper().value_counts().to_dict() if not df.empty else {}
    followups = df["followup_status"].fillna("").astype(str).str.upper().value_counts().to_dict() if not df.empty else {}
    return {
        "status": status,
        "rows": int(len(df)),
        "imported_rows": int(imported_rows),
        "pending_review": int(decisions.get("PENDING_REVIEW", 0)),
        "paper_watch": int(decisions.get("PAPER_WATCH", 0)),
        "paper_enter": int(decisions.get("PAPER_ENTER", 0)),
        "skip": int(decisions.get("SKIP", 0)),
        "blocked": int(decisions.get("BLOCKED", 0)),
        "needs_live_quote_recheck": int(decisions.get("NEEDS_LIVE_QUOTE_RECHECK", 0)),
        "decisions": decisions,
        "followups": followups,
        "error": error,
        "journal_path": str(journal_path or ""),
        "csv_out": str(csv_out or ""),
        "json_out": str(json_out or ""),
        "markdown_out": str(markdown_out or ""),
        "no_real_order_notice": NO_REAL_ORDER_NOTICE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_markdown(payload: dict, journal_df: pd.DataFrame) -> str:
    lines: list[str] = []
    lines.append("# Analista - paper trading journal")
    lines.append("")
    lines.append(f"- status: {payload.get('status')}")
    lines.append(f"- rows: {payload.get('rows')}")
    lines.append(f"- imported_rows: {payload.get('imported_rows')}")
    lines.append(f"- pending_review: {payload.get('pending_review')}")
    lines.append(f"- paper_watch: {payload.get('paper_watch')}")
    lines.append(f"- paper_enter: {payload.get('paper_enter')}")
    lines.append(f"- blocked: {payload.get('blocked')}")
    lines.append(f"- needs_live_quote_recheck: {payload.get('needs_live_quote_recheck')}")
    lines.append(f"- notice: {NO_REAL_ORDER_NOTICE}")
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    lines.append("")
    lines.append("## Guardrails")
    lines.append("")
    lines.append("- Paper trading only; no real order.")
    lines.append("- No broker connection is used.")
    lines.append("- Journal updates do not modify scanner signals, scores, config, weights, or thresholds.")
    lines.append("")
    lines.append("## Latest rows")
    lines.append("")
    if journal_df.empty:
        lines.append("_Sin filas en journal._")
    else:
        columns = [
            "run_date",
            "ticker",
            "checklist_status",
            "manual_decision",
            "followup_status",
            "simulated_entry_price",
            "simulated_stop",
            "simulated_target",
        ]
        display = journal_df.tail(25).copy()
        lines.append("| " + " | ".join(columns) + " |")
        lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
        for _, row in display.iterrows():
            values = [str(row.get(col, "")).replace("\n", " ").replace("|", "/") for col in columns]
            lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_reports(
    journal_df: pd.DataFrame,
    *,
    payload: dict,
    csv_out: Path,
    json_out: Path,
    markdown_out: Path,
) -> None:
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    journal_df[JOURNAL_COLUMNS].fillna("").to_csv(csv_out, index=False)
    json_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    markdown_out.write_text(build_markdown(payload, journal_df), encoding="utf-8")


def save_paper_trading_journal(
    *,
    journal_path: Path | None = None,
    cards_json: Path | None = None,
    checklist_csv: Path | None = None,
    manual_top_csv: Path | None = None,
    live_quote_csv: Path | None = None,
    csv_out: Path | None = None,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
    root: Path = ROOT,
    import_today: bool = False,
    summary: bool = False,
    run_date: str | None = None,
    set_decision: tuple[str, str] | None = None,
    reason: str = "",
    entry=None,
    stop=None,
    target=None,
    confirm_live_quote: bool = False,
    set_followup: tuple[str, str] | None = None,
    notes: str = "",
) -> dict:
    journal_path = journal_path or root / "data" / "paper_trading_journal.csv"
    cards_json = cards_json or root / "reports" / "trade_candidate_cards_latest.json"
    checklist_csv = checklist_csv or root / "reports" / "trade_decision_checklist_latest.csv"
    manual_top_csv = manual_top_csv or root / "reports" / "manual_review_top.csv"
    live_quote_csv = live_quote_csv or root / "reports" / "live_quote_recheck_latest.csv"
    csv_out = csv_out or root / "reports" / "paper_trading_journal_latest.csv"
    json_out = json_out or root / "reports" / "paper_trading_journal_latest.json"
    markdown_out = markdown_out or root / "reports" / "paper_trading_journal_latest.md"
    run_date = run_date or _today()

    journal = ensure_journal(journal_path)
    imported_rows = 0
    status = "PASS"
    error = ""

    if import_today:
        candidates, source_report, load_warning = load_import_candidates(
            cards_json=cards_json,
            checklist_csv=checklist_csv,
            manual_top_csv=manual_top_csv,
            live_quote_csv=live_quote_csv,
        )
        journal, imported_rows = import_candidates_today(
            journal,
            candidates,
            run_date=run_date,
            source_report=source_report,
        )
        if load_warning and candidates.empty:
            status = "WARN"
            error = load_warning

    if set_decision:
        ticker, decision = set_decision
        journal, result = set_manual_decision(
            journal,
            ticker=ticker,
            decision=decision,
            reason=reason,
            entry=entry,
            stop=stop,
            target=target,
            run_date=run_date,
            confirm_live_quote=confirm_live_quote,
        )
        status = result["status"]
        error = result.get("error", "")

    if set_followup:
        ticker, followup_status = set_followup
        journal, result = set_followup_status(
            journal,
            ticker=ticker,
            followup_status=followup_status,
            notes=notes,
            run_date=run_date,
        )
        status = result["status"]
        error = result.get("error", "")

    _write_journal(journal_path, journal)
    payload = build_summary_payload(
        journal,
        status=status,
        imported_rows=imported_rows,
        error=error,
        journal_path=journal_path,
        csv_out=csv_out,
        json_out=json_out,
        markdown_out=markdown_out,
    )
    write_reports(journal, payload=payload, csv_out=csv_out, json_out=json_out, markdown_out=markdown_out)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Mantiene journal auditado de paper trading.")
    parser.add_argument("--journal-path", default="data/paper_trading_journal.csv")
    parser.add_argument("--cards-json", default="reports/trade_candidate_cards_latest.json")
    parser.add_argument("--checklist-csv", default="reports/trade_decision_checklist_latest.csv")
    parser.add_argument("--manual-top-csv", default="reports/manual_review_top.csv")
    parser.add_argument("--live-quote-csv", default="reports/live_quote_recheck_latest.csv")
    parser.add_argument("--csv-out", default="reports/paper_trading_journal_latest.csv")
    parser.add_argument("--json-out", default="reports/paper_trading_journal_latest.json")
    parser.add_argument("--markdown-out", default="reports/paper_trading_journal_latest.md")
    parser.add_argument("--run-date", default=None)
    parser.add_argument("--import-today", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--set-decision", nargs=2, metavar=("TICKER", "DECISION"))
    parser.add_argument("--reason", default="")
    parser.add_argument("--entry", default=None)
    parser.add_argument("--stop", default=None)
    parser.add_argument("--target", default=None)
    parser.add_argument("--confirm-live-quote", action="store_true")
    parser.add_argument("--set-followup", nargs=2, metavar=("TICKER", "FOLLOWUP_STATUS"))
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    result = save_paper_trading_journal(
        journal_path=ROOT / args.journal_path,
        cards_json=ROOT / args.cards_json,
        checklist_csv=ROOT / args.checklist_csv,
        manual_top_csv=ROOT / args.manual_top_csv,
        live_quote_csv=ROOT / args.live_quote_csv,
        csv_out=ROOT / args.csv_out,
        json_out=ROOT / args.json_out,
        markdown_out=ROOT / args.markdown_out,
        root=ROOT,
        import_today=args.import_today,
        summary=args.summary,
        run_date=args.run_date,
        set_decision=tuple(args.set_decision) if args.set_decision else None,
        reason=args.reason,
        entry=args.entry,
        stop=args.stop,
        target=args.target,
        confirm_live_quote=args.confirm_live_quote,
        set_followup=tuple(args.set_followup) if args.set_followup else None,
        notes=args.notes,
    )

    print("=== ANALISTA PAPER TRADING JOURNAL ===")
    print(f"Status: {result['status']}")
    print(f"Rows: {result['rows']}")
    print(f"Imported rows: {result['imported_rows']}")
    print(f"Pending review: {result['pending_review']}")
    print(f"Paper watch: {result['paper_watch']}")
    print(f"Paper enter: {result['paper_enter']}")
    print(f"Blocked: {result['blocked']}")
    print(f"Needs live quote recheck: {result['needs_live_quote_recheck']}")
    print(f"Notice: {result['no_real_order_notice']}")
    print(f"Journal: {result['journal_path']}")
    print(f"CSV: {result['csv_out']}")
    print(f"JSON: {result['json_out']}")
    print(f"Markdown: {result['markdown_out']}")
    if result.get("error"):
        print(f"Error: {result['error']}")

    return 0 if result["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
