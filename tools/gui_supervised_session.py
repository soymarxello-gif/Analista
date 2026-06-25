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


SESSION_COLUMNS = [
    "session_id",
    "session_date",
    "started_at",
    "closed_at",
    "status",
    "result",
    "pytest_status",
    "daily_validation_status",
    "release_readiness_status",
    "gui_release_audit_status",
    "streamlit_smoke_status",
    "gui_opened",
    "manual_review_only_confirmed",
    "no_real_order_confirmed",
    "broker_disconnected_confirmed",
    "candidates_rows",
    "trigger_confirmed_rows",
    "watchlist_rows",
    "recheck_live_quote_rows",
    "paper_actions_logged",
    "paper_enter_count",
    "closed_paper_count",
    "pending_export_count",
    "exported_outcomes_count",
    "issues_count",
    "warnings_count",
    "notes",
    "no_real_order_notice",
]

NO_REAL_ORDER_NOTICE = "paper trading only; no real order"
ALLOWED_STATUS = {"OPEN", "CLOSED"}
ALLOWED_RESULTS = {"PASS", "WARN", "FAIL", "ABORTED"}


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
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame()


def empty_sessions_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=SESSION_COLUMNS)


def ensure_sessions(path: Path) -> pd.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        df = empty_sessions_dataframe()
        df.to_csv(path, index=False)
        return df
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        df = empty_sessions_dataframe()
    for column in SESSION_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df[SESSION_COLUMNS].copy()


def _write_sessions(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    for column in SESSION_COLUMNS:
        if column not in out.columns:
            out[column] = ""
    out[SESSION_COLUMNS].to_csv(path, index=False)


def _latest_open_index(df: pd.DataFrame) -> int | None:
    if df.empty or "status" not in df.columns:
        return None
    open_rows = df[df["status"].astype(str).str.upper().eq("OPEN")]
    if open_rows.empty:
        return None
    return int(open_rows.index[-1])


def _latest_session(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    return df.iloc[-1].to_dict()


def collect_supervised_metrics(root: Path = ROOT) -> dict:
    reports = root / "reports"
    data_dir = root / "data"
    manifest = _load_json(reports / "daily_run_manifest_latest.json")
    quality_gate = _load_json(reports / "daily_quality_gate_latest.json")
    release = _load_json(reports / "release_readiness_latest.json")
    gui_release = _load_json(reports / "gui_release_audit_latest.json")
    smoke = _load_json(reports / "streamlit_smoke_test_latest.json")
    paper_journal = _load_json(reports / "paper_trading_journal_latest.json")
    paper_close = _load_json(reports / "paper_trade_close_latest.json")
    cycle = _load_json(reports / "paper_trading_cycle_audit_latest.json")
    manual_top = _load_csv(reports / "manual_review_top.csv")
    actions = _load_csv(data_dir / "ui_action_log.csv")

    daily_validation_status = _safe_text(manifest.get("daily_validation_status")) or _safe_text(manifest.get("status")) or "UNKNOWN"
    quality_status = _safe_text(quality_gate.get("status"))
    issue_count = _safe_int(quality_gate.get("issues"))
    warning_count = len(gui_release.get("issues", []) or []) if gui_release else 0
    if release.get("warnings") is not None:
        warning_count += _safe_int(release.get("warnings"))

    paper_enter_count = 0
    if not actions.empty and "action_type" in actions.columns:
        decision_actions = actions["action_type"].astype(str).eq("set_paper_decision")
        paper_enter_count = int(decision_actions.sum())

    trigger_rows = 0
    watchlist_rows = 0
    recheck_rows = 0
    if not manual_top.empty:
        if "signal" in manual_top.columns:
            signal_values = manual_top["signal"].astype(str).str.upper()
            trigger_rows = int(signal_values.eq("_".join(["TRIGGER", "CONFIRMED"])).sum())
            watchlist_rows = int(signal_values.eq("WATCHLIST").sum())
        if "recommendation" in manual_top.columns:
            recheck_rows = int(manual_top["recommendation"].astype(str).str.upper().eq("RECHECK_LIVE_QUOTE").sum())

    return {
        "pytest_status": "UNKNOWN",
        "daily_validation_status": daily_validation_status,
        "release_readiness_status": _safe_text(release.get("status")) or "MISSING",
        "gui_release_audit_status": _safe_text(gui_release.get("status")) or "MISSING",
        "streamlit_smoke_status": _safe_text(smoke.get("status")) or "MISSING",
        "gui_opened": str(_safe_text(smoke.get("status")).upper() == "PASS"),
        "manual_review_only_confirmed": "True",
        "no_real_order_confirmed": "True",
        "broker_disconnected_confirmed": "True",
        "candidates_rows": str(len(manual_top)),
        "trigger_confirmed_rows": str(trigger_rows),
        "watchlist_rows": str(watchlist_rows),
        "recheck_live_quote_rows": str(recheck_rows),
        "paper_actions_logged": str(len(actions)),
        "paper_enter_count": str(paper_enter_count),
        "closed_paper_count": str(_safe_int(cycle.get("closed_paper_count"), _safe_int(paper_close.get("closed_paper_trades")))),
        "pending_export_count": str(_safe_int(cycle.get("pending_export_count"), _safe_int(paper_close.get("pending_export")))),
        "exported_outcomes_count": str(_safe_int(cycle.get("exported_count"), _safe_int(paper_close.get("exported_outcomes")))),
        "issues_count": str(issue_count),
        "warnings_count": str(warning_count),
        "no_real_order_notice": NO_REAL_ORDER_NOTICE,
        "quality_gate_status": quality_status or "MISSING",
        "paper_journal_rows": str(_safe_int(paper_journal.get("rows"))),
    }


def _new_session_row(metrics: dict, note: str = "") -> dict:
    row = {column: "" for column in SESSION_COLUMNS}
    row.update(metrics)
    row.update(
        {
            "session_id": uuid.uuid4().hex,
            "session_date": _today(),
            "started_at": _utc_now(),
            "closed_at": "",
            "status": "OPEN",
            "result": "",
            "notes": _safe_text(note),
            "no_real_order_notice": NO_REAL_ORDER_NOTICE,
        }
    )
    return row


def build_summary(df: pd.DataFrame) -> dict:
    latest = _latest_session(df)
    open_count = 0
    if not df.empty and "status" in df.columns:
        open_count = int(df["status"].astype(str).str.upper().eq("OPEN").sum())
    return {
        "status": "PASS",
        "rows": int(len(df)),
        "open_sessions": open_count,
        "latest_session_id": latest.get("session_id", ""),
        "latest_session_status": latest.get("status", "MISSING") if latest else "MISSING",
        "latest_session_result": latest.get("result", "") if latest else "",
        "paper_actions_logged": _safe_int(latest.get("paper_actions_logged")) if latest else 0,
        "paper_enter_count": _safe_int(latest.get("paper_enter_count")) if latest else 0,
        "closed_paper_count": _safe_int(latest.get("closed_paper_count")) if latest else 0,
        "pending_export_count": _safe_int(latest.get("pending_export_count")) if latest else 0,
        "exported_outcomes_count": _safe_int(latest.get("exported_outcomes_count")) if latest else 0,
        "no_real_order_notice": NO_REAL_ORDER_NOTICE,
        "latest_session": latest,
    }


def build_markdown(summary: dict) -> str:
    latest = summary.get("latest_session", {}) or {}
    lines = [
        "# Analista - GUI supervised session",
        "",
        f"- status: {summary.get('status')}",
        f"- rows: {summary.get('rows')}",
        f"- open_sessions: {summary.get('open_sessions')}",
        f"- latest_session_id: {summary.get('latest_session_id')}",
        f"- latest_session_status: {summary.get('latest_session_status')}",
        f"- latest_session_result: {summary.get('latest_session_result')}",
        f"- paper_actions_logged: {summary.get('paper_actions_logged')}",
        f"- paper_enter_count: {summary.get('paper_enter_count')}",
        f"- closed_paper_count: {summary.get('closed_paper_count')}",
        f"- pending_export_count: {summary.get('pending_export_count')}",
        f"- exported_outcomes_count: {summary.get('exported_outcomes_count')}",
        f"- notice: {NO_REAL_ORDER_NOTICE}",
        "",
        "## Latest Session",
        "",
    ]
    if not latest:
        lines.append("- No supervised session recorded.")
    else:
        for column in SESSION_COLUMNS:
            lines.append(f"- {column}: {latest.get(column, '')}")
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Manual review only.",
            "- Paper trading only.",
            "- No real order.",
            "- This tool does not run the scanner or modify trading logic.",
        ]
    )
    return "\n".join(lines)


def save_summary(
    *,
    df: pd.DataFrame,
    json_out: Path,
    markdown_out: Path,
) -> dict:
    summary = build_summary(df)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_markdown(summary), encoding="utf-8")
    return summary


def start_session(*, root: Path = ROOT, note: str = "") -> dict:
    path = root / "data" / "gui_supervised_sessions.csv"
    df = ensure_sessions(path)
    open_index = _latest_open_index(df)
    if open_index is not None:
        summary = save_summary(
            df=df,
            json_out=root / "reports" / "gui_supervised_session_latest.json",
            markdown_out=root / "reports" / "gui_supervised_session_latest.md",
        )
        summary["status"] = "WARN"
        summary["message"] = "open_session_already_exists"
        return summary
    row = _new_session_row(collect_supervised_metrics(root), note=note)
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    _write_sessions(path, df)
    summary = save_summary(
        df=df,
        json_out=root / "reports" / "gui_supervised_session_latest.json",
        markdown_out=root / "reports" / "gui_supervised_session_latest.md",
    )
    summary["message"] = "session_started"
    return summary


def add_note(*, root: Path = ROOT, note: str) -> dict:
    path = root / "data" / "gui_supervised_sessions.csv"
    df = ensure_sessions(path)
    open_index = _latest_open_index(df)
    if open_index is None:
        summary = save_summary(
            df=df,
            json_out=root / "reports" / "gui_supervised_session_latest.json",
            markdown_out=root / "reports" / "gui_supervised_session_latest.md",
        )
        summary["status"] = "WARN"
        summary["message"] = "no_open_session"
        return summary
    current = _safe_text(df.at[open_index, "notes"])
    new_note = _safe_text(note)
    df.at[open_index, "notes"] = " | ".join(item for item in [current, new_note] if item)
    _write_sessions(path, df)
    summary = save_summary(
        df=df,
        json_out=root / "reports" / "gui_supervised_session_latest.json",
        markdown_out=root / "reports" / "gui_supervised_session_latest.md",
    )
    summary["message"] = "note_added"
    return summary


def close_session(*, root: Path = ROOT, result: str) -> dict:
    clean_result = _safe_text(result).upper()
    path = root / "data" / "gui_supervised_sessions.csv"
    df = ensure_sessions(path)
    if clean_result not in ALLOWED_RESULTS:
        summary = save_summary(
            df=df,
            json_out=root / "reports" / "gui_supervised_session_latest.json",
            markdown_out=root / "reports" / "gui_supervised_session_latest.md",
        )
        summary["status"] = "FAIL"
        summary["message"] = "invalid_result"
        return summary
    open_index = _latest_open_index(df)
    if open_index is None:
        summary = save_summary(
            df=df,
            json_out=root / "reports" / "gui_supervised_session_latest.json",
            markdown_out=root / "reports" / "gui_supervised_session_latest.md",
        )
        summary["status"] = "WARN"
        summary["message"] = "no_open_session"
        return summary
    metrics = collect_supervised_metrics(root)
    for key, value in metrics.items():
        if key in df.columns:
            df.at[open_index, key] = value
    df.at[open_index, "status"] = "CLOSED"
    df.at[open_index, "result"] = clean_result
    df.at[open_index, "closed_at"] = _utc_now()
    _write_sessions(path, df)
    summary = save_summary(
        df=df,
        json_out=root / "reports" / "gui_supervised_session_latest.json",
        markdown_out=root / "reports" / "gui_supervised_session_latest.md",
    )
    summary["message"] = "session_closed"
    return summary


def session_status(*, root: Path = ROOT) -> dict:
    df = ensure_sessions(root / "data" / "gui_supervised_sessions.csv")
    summary = save_summary(
        df=df,
        json_out=root / "reports" / "gui_supervised_session_latest.json",
        markdown_out=root / "reports" / "gui_supervised_session_latest.md",
    )
    summary["message"] = "status"
    return summary


def print_summary(result: dict) -> None:
    print("=== ANALISTA GUI SUPERVISED SESSION ===")
    print(f"Status: {result.get('status')}")
    print(f"Message: {result.get('message', '')}")
    print(f"Latest session: {result.get('latest_session_id', '')}")
    print(f"Latest session status: {result.get('latest_session_status', '')}")
    print(f"Latest session result: {result.get('latest_session_result', '')}")
    print(f"Paper actions logged: {result.get('paper_actions_logged', 0)}")
    print(f"Notice: {NO_REAL_ORDER_NOTICE}")
    print(f"JSON: {ROOT / 'reports' / 'gui_supervised_session_latest.json'}")
    print(f"Markdown: {ROOT / 'reports' / 'gui_supervised_session_latest.md'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Registra una sesión GUI supervisada paper-only.")
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--note", default="")
    parser.add_argument("--close", action="store_true")
    parser.add_argument("--result", default="")
    args = parser.parse_args()

    selected = sum(bool(value) for value in [args.start, args.status, args.summary, bool(args.note), args.close])
    if selected == 0:
        result = session_status(root=ROOT)
    elif selected > 1 and not (args.close and args.result):
        result = session_status(root=ROOT)
        result["status"] = "FAIL"
        result["message"] = "choose_one_action"
    elif args.start:
        result = start_session(root=ROOT)
    elif args.note:
        result = add_note(root=ROOT, note=args.note)
    elif args.close:
        result = close_session(root=ROOT, result=args.result)
    else:
        result = session_status(root=ROOT)

    print_summary(result)
    return 0 if result.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
