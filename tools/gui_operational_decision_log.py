from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


NO_REAL_ORDER_NOTICE = "paper trading only; no real order"
DECISION_TYPES = {
    "CANDIDATE_REVIEW",
    "PAPER_WATCH",
    "PAPER_ENTER",
    "SKIP",
    "BLOCKED",
    "NEEDS_RECHECK",
    "PAPER_CLOSE_REVIEW",
    "EXPORT_REVIEW",
    "SESSION_NOTE",
    "CHECKLIST_NOTE",
}
DECISION_STATUSES = {"RECORDED", "NEEDS_FOLLOWUP", "REVIEWED", "INVALIDATED", "CLOSED"}
REVIEW_STATUSES = {"NOT_REVIEWED", "REVIEWED", "LESSON_ADDED", "NEEDS_MORE_DATA"}

DECISION_COLUMNS = [
    "decision_id",
    "decision_date",
    "timestamp",
    "session_id",
    "checklist_id",
    "ticker",
    "journal_id",
    "action_log_id",
    "source_tab",
    "decision_type",
    "decision_label",
    "decision_status",
    "reason",
    "context_summary",
    "risk_note",
    "followup_plan",
    "checklist_aligned",
    "quote_status",
    "execution_quote_quality",
    "signal",
    "recommendation",
    "setup_type",
    "final_trade_score",
    "checklist_status",
    "manual_review_only_confirmed",
    "no_real_order_confirmed",
    "post_session_review_status",
    "post_session_review_note",
    "lesson_learned",
    "created_by",
    "no_real_order_notice",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "null"} else text


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame()


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def empty_decisions_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=DECISION_COLUMNS)


def ensure_decisions(path: Path) -> pd.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        df = empty_decisions_dataframe()
        df.to_csv(path, index=False)
        return df
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        df = empty_decisions_dataframe()
    for column in DECISION_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df[DECISION_COLUMNS].copy()


def _write_decisions(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    for column in DECISION_COLUMNS:
        if column not in out.columns:
            out[column] = ""
    out[DECISION_COLUMNS].to_csv(path, index=False)


def _find_first_match(df: pd.DataFrame, *, ticker: str = "", journal_id: str = "") -> dict:
    if df.empty:
        return {}
    matches = df
    if journal_id and "journal_id" in matches.columns:
        journal_matches = matches[matches["journal_id"].astype(str).eq(journal_id)]
        if not journal_matches.empty:
            return journal_matches.iloc[0].to_dict()
    if ticker and "ticker" in matches.columns:
        ticker_matches = matches[matches["ticker"].astype(str).str.upper().eq(ticker.upper())]
        if not ticker_matches.empty:
            return ticker_matches.iloc[0].to_dict()
    return {}


def _enrichment_sources(root: Path) -> list[pd.DataFrame]:
    reports = root / "reports"
    data = root / "data"
    frames = [
        _load_csv(reports / "manual_review_top.csv"),
        _load_csv(reports / "trade_decision_checklist_latest.csv"),
        _load_csv(reports / "paper_trade_followup_latest.csv"),
        _load_csv(data / "paper_trading_journal.csv"),
        _load_csv(data / "ui_action_log.csv"),
    ]
    cards = _load_json(reports / "trade_candidate_cards_latest.json")
    card_rows = cards.get("cards") or cards.get("rows") or cards.get("items") or []
    if isinstance(card_rows, list):
        frames.append(pd.DataFrame(card_rows))
    return frames


def enrich_decision(root: Path, *, ticker: str = "", journal_id: str = "") -> dict:
    wanted = [
        "signal",
        "recommendation",
        "setup_type",
        "quote_status",
        "execution_quote_quality",
        "final_trade_score",
        "checklist_status",
    ]
    enriched = {column: "" for column in wanted}
    for df in _enrichment_sources(root):
        match = _find_first_match(df, ticker=ticker, journal_id=journal_id)
        if not match:
            continue
        for column in wanted:
            if not enriched[column]:
                enriched[column] = _safe_text(match.get(column))
    return enriched


def _latest_id(path: Path, column: str) -> str:
    df = _load_csv(path)
    if df.empty or column not in df.columns:
        return ""
    value = _safe_text(df.iloc[-1].get(column))
    return value


def add_decision(
    *,
    root: Path = ROOT,
    decision_type: str,
    reason: str = "",
    ticker: str = "",
    journal_id: str = "",
    session_id: str = "",
    checklist_id: str = "",
    action_log_id: str = "",
    source_tab: str = "",
    context_summary: str = "",
    risk_note: str = "",
    followup_plan: str = "",
    checklist_aligned: str = "",
    decision_status: str = "RECORDED",
    created_by: str = "manual_operator",
) -> dict:
    clean_type = _safe_text(decision_type).upper()
    clean_status = _safe_text(decision_status).upper() or "RECORDED"
    clean_reason = _safe_text(reason)
    if clean_type not in DECISION_TYPES:
        return _controlled_result("FAIL", "invalid_decision_type")
    if clean_status not in DECISION_STATUSES:
        return _controlled_result("FAIL", "invalid_decision_status")
    if clean_type != "SESSION_NOTE" and not clean_reason:
        return _controlled_result("FAIL", "reason_required")

    path = root / "data" / "gui_operational_decisions.csv"
    df = ensure_decisions(path)
    ticker = _safe_text(ticker).upper()
    journal_id = _safe_text(journal_id)
    session_id = _safe_text(session_id) or _latest_id(root / "data" / "gui_supervised_sessions.csv", "session_id")
    checklist_id = _safe_text(checklist_id) or _latest_id(
        root / "data" / "gui_daily_operating_checklists.csv", "checklist_id"
    )
    enriched = enrich_decision(root, ticker=ticker, journal_id=journal_id)
    now = _utc_now()
    row = {column: "" for column in DECISION_COLUMNS}
    row.update(enriched)
    row.update(
        {
            "decision_id": uuid.uuid4().hex,
            "decision_date": _today(),
            "timestamp": now,
            "session_id": session_id,
            "checklist_id": checklist_id,
            "ticker": ticker,
            "journal_id": journal_id,
            "action_log_id": _safe_text(action_log_id),
            "source_tab": _safe_text(source_tab),
            "decision_type": clean_type,
            "decision_label": clean_type,
            "decision_status": clean_status,
            "reason": clean_reason,
            "context_summary": _safe_text(context_summary),
            "risk_note": _safe_text(risk_note),
            "followup_plan": _safe_text(followup_plan),
            "checklist_aligned": _safe_text(checklist_aligned) or "UNKNOWN",
            "manual_review_only_confirmed": "True",
            "no_real_order_confirmed": "True",
            "post_session_review_status": "NOT_REVIEWED",
            "created_by": _safe_text(created_by) or "manual_operator",
            "no_real_order_notice": NO_REAL_ORDER_NOTICE,
        }
    )
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    _write_decisions(path, df)
    summary = save_summary(root=root)
    summary["message"] = "decision_recorded"
    summary["decision_id"] = row["decision_id"]
    return summary


def review_decision(
    *,
    root: Path = ROOT,
    decision_id: str,
    outcome_note: str = "",
    lesson: str = "",
    review_status: str = "",
) -> dict:
    clean_id = _safe_text(decision_id)
    path = root / "data" / "gui_operational_decisions.csv"
    df = ensure_decisions(path)
    if df.empty or "decision_id" not in df.columns:
        return _controlled_result("FAIL", "decision_id_not_found")
    matches = df[df["decision_id"].astype(str).eq(clean_id)]
    if matches.empty:
        return _controlled_result("FAIL", "decision_id_not_found")
    status = _safe_text(review_status).upper()
    if not status:
        status = "LESSON_ADDED" if _safe_text(lesson) else "REVIEWED"
    if status not in REVIEW_STATUSES:
        return _controlled_result("FAIL", "invalid_review_status")
    index = matches.index[-1]
    df.at[index, "post_session_review_status"] = status
    if outcome_note:
        df.at[index, "post_session_review_note"] = _safe_text(outcome_note)
    if lesson:
        df.at[index, "lesson_learned"] = _safe_text(lesson)
    if status in {"REVIEWED", "LESSON_ADDED"}:
        df.at[index, "decision_status"] = "REVIEWED"
    _write_decisions(path, df)
    summary = save_summary(root=root)
    summary["message"] = "decision_reviewed"
    summary["decision_id"] = clean_id
    return summary


def _today_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "decision_date" not in df.columns:
        return pd.DataFrame(columns=DECISION_COLUMNS)
    return df[df["decision_date"].astype(str).eq(_today())].copy()


def build_summary(df: pd.DataFrame) -> dict:
    rows = _today_rows(df)
    if rows.empty:
        return {
            "status": "PASS",
            "decisions_today": 0,
            "paper_watch_decisions": 0,
            "paper_enter_decisions": 0,
            "skip_decisions": 0,
            "needs_recheck_decisions": 0,
            "decisions_without_reason": 0,
            "decisions_without_post_review": 0,
            "lessons_added": 0,
            "manual_review_only": True,
            "no_real_order_notice": NO_REAL_ORDER_NOTICE,
            "decisions": [],
        }
    types = rows["decision_type"].astype(str).str.upper()
    reasons = rows["reason"].astype(str).str.strip()
    reasons_required = ~types.eq("SESSION_NOTE")
    reviews = rows["post_session_review_status"].astype(str).str.upper()
    lessons = rows["lesson_learned"].astype(str).str.strip()
    return {
        "status": "WARN" if int((reasons_required & reasons.eq("")).sum()) else "PASS",
        "decisions_today": int(len(rows)),
        "paper_watch_decisions": int(types.eq("PAPER_WATCH").sum()),
        "paper_enter_decisions": int(types.eq("PAPER_ENTER").sum()),
        "skip_decisions": int(types.eq("SKIP").sum()),
        "needs_recheck_decisions": int(types.eq("NEEDS_RECHECK").sum()),
        "decisions_without_reason": int((reasons_required & reasons.eq("")).sum()),
        "decisions_without_post_review": int(reviews.eq("NOT_REVIEWED").sum()),
        "lessons_added": int(lessons.ne("").sum()),
        "manual_review_only": True,
        "no_real_order_notice": NO_REAL_ORDER_NOTICE,
        "decisions": rows.sort_values("timestamp").to_dict(orient="records"),
    }


def build_markdown(summary: dict) -> str:
    lines = [
        "# Analista - GUI operational decision log",
        "",
        f"- status: {summary.get('status')}",
        f"- decisions_today: {summary.get('decisions_today')}",
        f"- paper_watch_decisions: {summary.get('paper_watch_decisions')}",
        f"- paper_enter_decisions: {summary.get('paper_enter_decisions')}",
        f"- skip_decisions: {summary.get('skip_decisions')}",
        f"- needs_recheck_decisions: {summary.get('needs_recheck_decisions')}",
        f"- decisions_without_reason: {summary.get('decisions_without_reason')}",
        f"- decisions_without_post_review: {summary.get('decisions_without_post_review')}",
        f"- lessons_added: {summary.get('lessons_added')}",
        f"- notice: {NO_REAL_ORDER_NOTICE}",
        "",
        "## Decisions",
        "",
    ]
    decisions = summary.get("decisions", []) or []
    if not decisions:
        lines.append("- No decisions recorded today.")
    for item in decisions:
        label = item.get("ticker") or item.get("journal_id") or item.get("decision_id")
        lines.append(
            f"- {item.get('decision_id')} | {item.get('decision_type')} | {label} | "
            f"{item.get('decision_status')} | review={item.get('post_session_review_status')}"
        )
    lines.extend(["", "## Guardrails", "", "- Manual review only.", "- Paper trading only.", "- No real order."])
    return "\n".join(lines)


def save_summary(*, root: Path = ROOT) -> dict:
    df = ensure_decisions(root / "data" / "gui_operational_decisions.csv")
    summary = build_summary(df)
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "gui_operational_decision_log_latest.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    (reports / "gui_operational_decision_log_latest.md").write_text(build_markdown(summary), encoding="utf-8")
    return summary


def _controlled_result(status: str, message: str) -> dict:
    return {
        "status": status,
        "message": message,
        "decisions_today": 0,
        "no_real_order_notice": NO_REAL_ORDER_NOTICE,
    }


def print_summary(result: dict) -> None:
    print("=== ANALISTA GUI OPERATIONAL DECISION LOG ===")
    print(f"Status: {result.get('status')}")
    print(f"Message: {result.get('message', '')}")
    print(f"Decisions today: {result.get('decisions_today', 0)}")
    print(f"Paper enter: {result.get('paper_enter_decisions', 0)}")
    print(f"Without post review: {result.get('decisions_without_post_review', 0)}")
    if result.get("decision_id"):
        print(f"Decision id: {result.get('decision_id')}")
    print(f"Notice: {NO_REAL_ORDER_NOTICE}")
    print(f"JSON: {ROOT / 'reports' / 'gui_operational_decision_log_latest.json'}")
    print(f"Markdown: {ROOT / 'reports' / 'gui_operational_decision_log_latest.md'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Registra decisiones operativas GUI paper-only.")
    parser.add_argument("--add", action="store_true")
    parser.add_argument("--list-today", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--review", metavar="DECISION_ID")
    parser.add_argument("--decision", "--decision-type", dest="decision_type", default="")
    parser.add_argument("--ticker", default="")
    parser.add_argument("--journal-id", default="")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--checklist-id", default="")
    parser.add_argument("--action-log-id", default="")
    parser.add_argument("--source-tab", default="")
    parser.add_argument("--reason", default="")
    parser.add_argument("--context-summary", default="")
    parser.add_argument("--risk-note", default="")
    parser.add_argument("--followup-plan", default="")
    parser.add_argument("--checklist-aligned", default="")
    parser.add_argument("--decision-status", default="RECORDED")
    parser.add_argument("--outcome-note", default="")
    parser.add_argument("--lesson", default="")
    parser.add_argument("--review-status", default="")
    args = parser.parse_args()

    try:
        if args.add:
            result = add_decision(
                decision_type=args.decision_type,
                reason=args.reason,
                ticker=args.ticker,
                journal_id=args.journal_id,
                session_id=args.session_id,
                checklist_id=args.checklist_id,
                action_log_id=args.action_log_id,
                source_tab=args.source_tab,
                context_summary=args.context_summary,
                risk_note=args.risk_note,
                followup_plan=args.followup_plan,
                checklist_aligned=args.checklist_aligned,
                decision_status=args.decision_status,
            )
        elif args.review:
            result = review_decision(
                decision_id=args.review,
                outcome_note=args.outcome_note,
                lesson=args.lesson,
                review_status=args.review_status,
            )
        else:
            result = save_summary(root=ROOT)
            result["message"] = "list_today" if args.list_today else "summary"
    except Exception as exc:
        result = _controlled_result("FAIL", f"controlled_error:{type(exc).__name__}")
    print_summary(result)
    return 0 if result.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
