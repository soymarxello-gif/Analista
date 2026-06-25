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
STEP_STATUSES = {"PENDING", "DONE", "SKIPPED", "BLOCKED"}
CHECKLIST_RESULTS = {"OPEN", "PASS", "WARN", "FAIL", "ABORTED"}

CHECKLIST_COLUMNS = [
    "checklist_id",
    "checklist_date",
    "step_id",
    "step_group",
    "step_order",
    "step_name",
    "required",
    "status",
    "marked_at",
    "note",
    "result",
    "no_real_order_notice",
]

STEP_DEFINITIONS = [
    ("Pre-run validation", "activate_venv", "Activate virtual environment", False),
    ("Pre-run validation", "git_status_review", "Review Git status", False),
    ("Pre-run validation", "pytest_pass_confirmed", "Confirm pytest passed", True),
    ("Pre-run validation", "daily_validation_pass_confirmed", "Confirm daily validation passed", True),
    ("Pre-run validation", "gui_release_audit_pass_confirmed", "Confirm GUI release audit passed", True),
    ("Pre-run validation", "supervised_session_started", "Start supervised GUI session", True),
    ("GUI launch", "streamlit_started", "Start Streamlit manually", True),
    ("GUI launch", "overview_tab_reviewed", "Review Overview tab", False),
    ("GUI launch", "quality_guardrails_reviewed", "Review quality and guardrails", True),
    ("GUI launch", "reports_status_reviewed", "Review reports status", False),
    ("Candidate review", "candidates_tab_reviewed", "Review Candidates tab", False),
    ("Candidate review", "trigger_confirmed_reviewed", "Review trigger confirmed rows", False),
    ("Candidate review", "watchlist_reviewed", "Review watchlist rows", False),
    ("Candidate review", "recheck_live_quote_reviewed", "Review live quote recheck rows", False),
    ("Candidate review", "candidate_cards_reviewed", "Review candidate cards", False),
    ("Candidate review", "checklist_tab_reviewed", "Review trade decision checklist", False),
    ("Paper trading actions", "paper_actions_reviewed", "Review paper actions", False),
    ("Paper trading actions", "candidates_imported_to_journal_if_needed", "Import candidates if needed", False),
    ("Paper trading actions", "paper_watch_decisions_recorded", "Record paper watch decisions", False),
    ("Paper trading actions", "paper_enter_decisions_recorded", "Record paper enter decisions", False),
    ("Paper trading actions", "reasons_recorded_for_all_decisions", "Record reasons for all decisions", False),
    ("Paper trading actions", "no_real_order_confirmed", "Confirm no real order", True),
    ("Follow-up", "paper_followup_refreshed", "Refresh paper follow-up", False),
    ("Follow-up", "near_stop_items_reviewed", "Review near stop items", False),
    ("Follow-up", "near_target_items_reviewed", "Review near target items", False),
    ("Follow-up", "stop_hit_review_items_reviewed", "Review stop hit items", False),
    ("Follow-up", "target_hit_review_items_reviewed", "Review target hit items", False),
    ("Closing / outcomes", "paper_closes_reviewed", "Review paper closes", False),
    ("Closing / outcomes", "manual_closes_recorded_if_needed", "Record manual closes if needed", False),
    ("Closing / outcomes", "export_outcomes_reviewed", "Review outcome export", False),
    ("Closing / outcomes", "pending_exports_reviewed", "Review pending exports", False),
    ("End-of-day", "cycle_audit_reviewed", "Review cycle audit", False),
    ("End-of-day", "supervised_session_note_added", "Add supervised session note", False),
    ("End-of-day", "checklist_summary_generated", "Generate checklist summary", True),
    ("End-of-day", "daily_operator_index_reviewed", "Review daily operator index", False),
    ("End-of-day", "no_broker_no_real_order_confirmed", "Confirm no execution connection and no real order", True),
    ("End-of-day", "checklist_closed", "Close checklist", True),
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


def empty_checklist_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=CHECKLIST_COLUMNS)


def ensure_checklists(path: Path) -> pd.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        df = empty_checklist_dataframe()
        df.to_csv(path, index=False)
        return df
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        df = empty_checklist_dataframe()
    for column in CHECKLIST_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df[CHECKLIST_COLUMNS].copy()


def _write_checklists(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    for column in CHECKLIST_COLUMNS:
        if column not in out.columns:
            out[column] = ""
    out[CHECKLIST_COLUMNS].to_csv(path, index=False)


def _today_rows(df: pd.DataFrame, checklist_date: str | None = None) -> pd.DataFrame:
    target_date = checklist_date or _today()
    if df.empty:
        return df.copy()
    return df[df["checklist_date"].astype(str).eq(target_date)].copy()


def _latest_checklist_id(df: pd.DataFrame) -> str:
    today_rows = _today_rows(df)
    if not today_rows.empty:
        return str(today_rows.iloc[-1].get("checklist_id", ""))
    if df.empty:
        return ""
    return str(df.iloc[-1].get("checklist_id", ""))


def _active_rows(df: pd.DataFrame) -> pd.DataFrame:
    checklist_id = _latest_checklist_id(df)
    if not checklist_id:
        return pd.DataFrame(columns=CHECKLIST_COLUMNS)
    return df[df["checklist_id"].astype(str).eq(checklist_id)].copy()


def _build_rows(checklist_id: str, checklist_date: str) -> list[dict]:
    rows = []
    for index, (group, step_id, step_name, required) in enumerate(STEP_DEFINITIONS, start=1):
        rows.append(
            {
                "checklist_id": checklist_id,
                "checklist_date": checklist_date,
                "step_id": step_id,
                "step_group": group,
                "step_order": str(index),
                "step_name": step_name,
                "required": str(bool(required)),
                "status": "PENDING",
                "marked_at": "",
                "note": "",
                "result": "OPEN",
                "no_real_order_notice": NO_REAL_ORDER_NOTICE,
            }
        )
    return rows


def build_summary(df: pd.DataFrame) -> dict:
    rows = _active_rows(df)
    if rows.empty:
        return {
            "status": "PASS",
            "checklist_id": "",
            "checklist_date": "",
            "pending_steps": 0,
            "done_steps": 0,
            "blocked_steps": 0,
            "skipped_steps": 0,
            "required_pending_steps": 0,
            "latest_result": "MISSING",
            "steps": [],
            "no_real_order_notice": NO_REAL_ORDER_NOTICE,
        }
    statuses = rows["status"].astype(str).str.upper()
    required = rows["required"].astype(str).str.lower().isin({"true", "1", "yes"})
    required_pending = int((required & statuses.eq("PENDING")).sum())
    latest_result = _safe_text(rows.iloc[-1].get("result")) or "OPEN"
    return {
        "status": "WARN" if required_pending else "PASS",
        "checklist_id": str(rows.iloc[0].get("checklist_id", "")),
        "checklist_date": str(rows.iloc[0].get("checklist_date", "")),
        "pending_steps": int(statuses.eq("PENDING").sum()),
        "done_steps": int(statuses.eq("DONE").sum()),
        "blocked_steps": int(statuses.eq("BLOCKED").sum()),
        "skipped_steps": int(statuses.eq("SKIPPED").sum()),
        "required_pending_steps": required_pending,
        "latest_result": latest_result,
        "steps": rows.sort_values("step_order").to_dict(orient="records"),
        "no_real_order_notice": NO_REAL_ORDER_NOTICE,
    }


def build_markdown(summary: dict) -> str:
    lines = [
        "# Analista - GUI daily operating checklist",
        "",
        f"- status: {summary.get('status')}",
        f"- checklist_id: {summary.get('checklist_id')}",
        f"- checklist_date: {summary.get('checklist_date')}",
        f"- pending_steps: {summary.get('pending_steps')}",
        f"- done_steps: {summary.get('done_steps')}",
        f"- blocked_steps: {summary.get('blocked_steps')}",
        f"- skipped_steps: {summary.get('skipped_steps')}",
        f"- required_pending_steps: {summary.get('required_pending_steps')}",
        f"- latest_result: {summary.get('latest_result')}",
        f"- notice: {NO_REAL_ORDER_NOTICE}",
        "",
        "## Steps",
        "",
    ]
    steps = summary.get("steps", [])
    if not steps:
        lines.append("- No checklist recorded.")
    else:
        for step in steps:
            required = "required" if str(step.get("required", "")).lower() == "true" else "optional"
            lines.append(
                f"- {step.get('step_order')}. {step.get('step_id')} "
                f"[{step.get('status')}, {required}] - {step.get('note', '')}"
            )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Manual review only.",
            "- Paper trading only.",
            "- No real order.",
            "- Checklist records manual confirmation only; it does not run tools or modify trading data.",
        ]
    )
    return "\n".join(lines)


def save_summary(*, df: pd.DataFrame, json_out: Path, markdown_out: Path) -> dict:
    summary = build_summary(df)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_markdown(summary), encoding="utf-8")
    return summary


def init_today(*, root: Path = ROOT) -> dict:
    path = root / "data" / "gui_daily_operating_checklists.csv"
    df = ensure_checklists(path)
    today_rows = _today_rows(df)
    if not today_rows.empty:
        summary = save_summary(
            df=df,
            json_out=root / "reports" / "gui_daily_operating_checklist_latest.json",
            markdown_out=root / "reports" / "gui_daily_operating_checklist_latest.md",
        )
        summary["message"] = "checklist_already_exists"
        return summary
    checklist_id = uuid.uuid4().hex
    rows = _build_rows(checklist_id, _today())
    df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
    _write_checklists(path, df)
    summary = save_summary(
        df=df,
        json_out=root / "reports" / "gui_daily_operating_checklist_latest.json",
        markdown_out=root / "reports" / "gui_daily_operating_checklist_latest.md",
    )
    summary["message"] = "checklist_created"
    return summary


def checklist_status(*, root: Path = ROOT) -> dict:
    df = ensure_checklists(root / "data" / "gui_daily_operating_checklists.csv")
    summary = save_summary(
        df=df,
        json_out=root / "reports" / "gui_daily_operating_checklist_latest.json",
        markdown_out=root / "reports" / "gui_daily_operating_checklist_latest.md",
    )
    summary["message"] = "status"
    return summary


def mark_step(*, root: Path = ROOT, step_id: str, status: str, note: str = "") -> dict:
    clean_step_id = _safe_text(step_id)
    clean_status = _safe_text(status).upper()
    path = root / "data" / "gui_daily_operating_checklists.csv"
    df = ensure_checklists(path)
    rows = _active_rows(df)
    if rows.empty:
        summary = checklist_status(root=root)
        summary["status"] = "WARN"
        summary["message"] = "no_checklist"
        return summary
    if clean_status not in STEP_STATUSES - {"PENDING"}:
        summary = checklist_status(root=root)
        summary["status"] = "FAIL"
        summary["message"] = "invalid_step_status"
        return summary
    matches = rows[rows["step_id"].astype(str).eq(clean_step_id)]
    if matches.empty:
        summary = checklist_status(root=root)
        summary["status"] = "FAIL"
        summary["message"] = "invalid_step_id"
        return summary
    row_index = matches.index[-1]
    df.at[row_index, "status"] = clean_status
    df.at[row_index, "marked_at"] = _utc_now()
    if note:
        df.at[row_index, "note"] = _safe_text(note)
    _write_checklists(path, df)
    summary = save_summary(
        df=df,
        json_out=root / "reports" / "gui_daily_operating_checklist_latest.json",
        markdown_out=root / "reports" / "gui_daily_operating_checklist_latest.md",
    )
    summary["message"] = "step_marked"
    return summary


def close_checklist(*, root: Path = ROOT, result: str) -> dict:
    clean_result = _safe_text(result).upper()
    path = root / "data" / "gui_daily_operating_checklists.csv"
    df = ensure_checklists(path)
    if clean_result not in CHECKLIST_RESULTS - {"OPEN"}:
        summary = checklist_status(root=root)
        summary["status"] = "FAIL"
        summary["message"] = "invalid_result"
        return summary
    rows = _active_rows(df)
    if rows.empty:
        summary = checklist_status(root=root)
        summary["status"] = "WARN"
        summary["message"] = "no_checklist"
        return summary
    required = rows["required"].astype(str).str.lower().isin({"true", "1", "yes"})
    pending = rows["status"].astype(str).str.upper().eq("PENDING")
    closable_pending = rows["step_id"].astype(str).ne("checklist_closed")
    required_pending_before_close = int((required & pending & closable_pending).sum())
    if clean_result == "PASS" and required_pending_before_close > 0:
        summary = save_summary(
            df=df,
            json_out=root / "reports" / "gui_daily_operating_checklist_latest.json",
            markdown_out=root / "reports" / "gui_daily_operating_checklist_latest.md",
        )
        summary["status"] = "WARN"
        summary["message"] = "required_steps_pending"
        return summary
    for index in rows.index:
        df.at[index, "result"] = clean_result
    close_matches = rows[rows["step_id"].astype(str).eq("checklist_closed")]
    if not close_matches.empty:
        close_index = close_matches.index[-1]
        df.at[close_index, "status"] = "DONE"
        df.at[close_index, "marked_at"] = _utc_now()
    _write_checklists(path, df)
    summary = save_summary(
        df=df,
        json_out=root / "reports" / "gui_daily_operating_checklist_latest.json",
        markdown_out=root / "reports" / "gui_daily_operating_checklist_latest.md",
    )
    summary["message"] = "checklist_closed"
    return summary


def print_summary(result: dict) -> None:
    print("=== ANALISTA GUI DAILY OPERATING CHECKLIST ===")
    print(f"Status: {result.get('status')}")
    print(f"Message: {result.get('message', '')}")
    print(f"Checklist: {result.get('checklist_id', '')}")
    print(f"Date: {result.get('checklist_date', '')}")
    print(f"Pending: {result.get('pending_steps', 0)}")
    print(f"Required pending: {result.get('required_pending_steps', 0)}")
    print(f"Latest result: {result.get('latest_result', '')}")
    print(f"Notice: {NO_REAL_ORDER_NOTICE}")
    print(f"JSON: {ROOT / 'reports' / 'gui_daily_operating_checklist_latest.json'}")
    print(f"Markdown: {ROOT / 'reports' / 'gui_daily_operating_checklist_latest.md'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Registra checklist operativo diario GUI paper-only.")
    parser.add_argument("--init-today", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--mark", nargs=2, metavar=("STEP_ID", "STATUS"))
    parser.add_argument("--note", default="")
    parser.add_argument("--close", action="store_true")
    parser.add_argument("--result", default="")
    args = parser.parse_args()

    selected = sum(bool(value) for value in [args.init_today, args.status, args.summary, bool(args.mark), args.close])
    if selected == 0:
        result = checklist_status(root=ROOT)
    elif selected > 1 and not args.note:
        result = checklist_status(root=ROOT)
        result["status"] = "FAIL"
        result["message"] = "choose_one_action"
    elif args.init_today:
        result = init_today(root=ROOT)
    elif args.mark:
        result = mark_step(root=ROOT, step_id=args.mark[0], status=args.mark[1], note=args.note)
    elif args.close:
        result = close_checklist(root=ROOT, result=args.result)
    else:
        result = checklist_status(root=ROOT)

    print_summary(result)
    return 0 if result.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
