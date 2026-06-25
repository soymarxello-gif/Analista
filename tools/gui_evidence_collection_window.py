from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


NOTICE = "observational only; no automatic trading changes"
MANUAL_NOTICE = "manual review only; paper trading only; no real orders"
SUMMARY_COLUMNS = [
    "window_id",
    "window_start_date",
    "window_end_date",
    "window_days",
    "status",
    "sessions_count",
    "closed_sessions_count",
    "checklist_count",
    "checklist_completion_rate",
    "weekly_reviews_count",
    "total_decisions",
    "paper_watch_decisions",
    "paper_enter_decisions",
    "skip_decisions",
    "blocked_decisions",
    "needs_recheck_decisions",
    "decisions_without_reason",
    "decisions_without_post_review",
    "avg_decision_quality_score",
    "latest_weekly_operational_score",
    "avg_weekly_operational_score",
    "paper_actions_logged",
    "paper_enter_action_count",
    "paper_close_action_count",
    "journal_rows",
    "open_paper_count",
    "closed_paper_count",
    "pending_export_count",
    "exported_outcomes_count",
    "outcomes_rows",
    "completed_outcomes_count",
    "avg_r_multiple",
    "median_r_multiple",
    "win_rate_paper",
    "winning_trade_count",
    "losing_trade_count",
    "guardrail_violations_count",
    "data_quality_issues_count",
    "evidence_sample_score",
    "evidence_quality_score",
    "calibration_readiness_score",
    "readiness_bucket",
    "readiness_status",
    "readiness_reason",
    "sample_size_score",
    "session_consistency_score",
    "checklist_discipline_score",
    "decision_quality_score",
    "paper_outcome_sample_score",
    "export_discipline_score",
    "guardrail_compliance_score",
    "post_review_score",
    "manual_review_only",
    "paper_trading_only",
    "no_real_order_notice_present",
    "notice",
    "manual_notice",
]


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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        text = _safe_text(value)
        return int(float(text)) if text else default
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        text = _safe_text(value)
        return float(text) if text else default
    except Exception:
        return default


def _safe_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _bounded(value: float) -> float:
    return max(0.0, min(100.0, round(float(value), 2)))


def _rate(ok: int, total: int) -> float:
    if total <= 0:
        return 1.0
    return round(ok / total, 4)


def _ratio_score(ok: int, total: int) -> float:
    if total <= 0:
        return 100.0
    return _bounded((ok / total) * 100.0)


def _progress_score(value: int, target: int) -> float:
    if target <= 0:
        return 100.0
    return _bounded((value / target) * 100.0)


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


def _parse_date_series(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    for column in candidates:
        if column in df.columns:
            values = pd.to_datetime(df[column], errors="coerce", utc=True)
            if values.notna().any():
                return values.dt.date
    return pd.Series([pd.NaT] * len(df), index=df.index)


def _window(df: pd.DataFrame, candidates: list[str], start: date, end: date) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    dates = _parse_date_series(df, candidates)
    if dates.notna().any():
        return df[(dates >= start) & (dates <= end)].copy()
    return df.copy()


def _counts(df: pd.DataFrame, column: str) -> Counter:
    if df.empty or column not in df.columns:
        return Counter()
    return Counter(df[column].astype(str).str.upper().str.strip().tolist())


def _readiness_bucket(score: float) -> str:
    if score >= 85:
        return "A_READY_FOR_REVIEW"
    if score >= 70:
        return "B_ALMOST_READY"
    if score >= 50:
        return "C_NEEDS_MORE_EVIDENCE"
    return "D_NOT_READY"


def _checklist_completion(checklists: pd.DataFrame) -> tuple[int, float]:
    if checklists.empty:
        return 0, 1.0
    ids = checklists["checklist_id"].astype(str) if "checklist_id" in checklists.columns else pd.Series(range(len(checklists)))
    status = checklists.get("status", pd.Series(dtype=str)).astype(str).str.upper()
    return int(ids.nunique()), _rate(int(status.eq("DONE").sum()), len(checklists))


def _decision_metrics(decisions: pd.DataFrame, decision_quality: dict) -> dict:
    types = _counts(decisions, "decision_type")
    total = int(len(decisions))
    without_reason = 0
    without_review = 0
    guardrail_violations = 0
    if not decisions.empty:
        dtype = decisions.get("decision_type", pd.Series(dtype=str)).astype(str).str.upper()
        reason = decisions.get("reason", pd.Series(dtype=str)).astype(str).str.strip()
        review = decisions.get("post_session_review_status", pd.Series(dtype=str)).astype(str).str.upper()
        no_order = decisions.get("no_real_order_confirmed", pd.Series(dtype=str)).map(_safe_bool)
        quote_status = decisions.get("quote_status", pd.Series(dtype=str)).astype(str).str.upper()
        quote_quality = decisions.get("execution_quote_quality", pd.Series(dtype=str)).astype(str).str.upper()
        without_reason = int((reason.eq("") & ~dtype.eq("SESSION_NOTE")).sum())
        without_review = int((~review.isin({"REVIEWED", "LESSON_ADDED", "NEEDS_MORE_DATA"})).sum())
        guardrail_violations = int((~no_order).sum()) if len(no_order) else 0
        guardrail_violations += int((dtype.eq("PAPER_ENTER") & quote_status.ne("") & ~quote_status.eq("VALID")).sum())
        guardrail_violations += int((dtype.eq("PAPER_ENTER") & quote_quality.eq("LOW")).sum())
    return {
        "total": total,
        "paper_watch": int(types.get("PAPER_WATCH", 0)),
        "paper_enter": int(types.get("PAPER_ENTER", 0)),
        "skip": int(types.get("SKIP", 0)),
        "blocked": int(types.get("BLOCKED", 0)),
        "needs_recheck": int(types.get("NEEDS_RECHECK", 0)),
        "without_reason": without_reason,
        "without_review": without_review,
        "avg_quality": _bounded(_safe_float(decision_quality.get("decision_quality_score"), 100.0 if total == 0 else 0.0)),
        "guardrail_violations": guardrail_violations,
    }


def _action_metrics(actions: pd.DataFrame) -> dict:
    if actions.empty:
        return {"paper_actions_logged": 0, "paper_enter_action_count": 0, "paper_close_action_count": 0}
    action_text = pd.Series([""] * len(actions), index=actions.index)
    for column in ["action_type", "action", "event_type"]:
        if column in actions.columns:
            action_text = action_text.str.cat(actions[column].astype(str), sep=" ").str.upper()
    return {
        "paper_actions_logged": int(action_text.str.contains("PAPER", na=False).sum()),
        "paper_enter_action_count": int(action_text.str.contains("PAPER_ENTER|ENTERED_PAPER", regex=True, na=False).sum()),
        "paper_close_action_count": int(action_text.str.contains("PAPER_CLOSE|CLOSED_PAPER|CLOSE", regex=True, na=False).sum()),
    }


def _paper_counts(journal: pd.DataFrame) -> dict:
    if journal.empty:
        return {"journal_rows": 0, "open": 0, "closed": 0, "pending_export": 0, "exported": 0}
    status = journal.get("followup_status", pd.Series(dtype=str)).astype(str).str.upper()
    decision = journal.get("manual_decision", pd.Series(dtype=str)).astype(str).str.upper()
    exported = journal.get("outcome_exported", pd.Series(dtype=str)).map(_safe_bool)
    open_mask = decision.eq("PAPER_ENTER") | status.isin({"OPEN_MONITORING", "ENTERED_PAPER"})
    closed_mask = status.eq("CLOSED_PAPER")
    return {
        "journal_rows": int(len(journal)),
        "open": int((open_mask & ~closed_mask).sum()),
        "closed": int(closed_mask.sum()),
        "pending_export": int((closed_mask & ~exported).sum()) if len(exported) else 0,
        "exported": int((closed_mask & exported).sum()) if len(exported) else 0,
    }


def _r_multiple_column(outcomes: pd.DataFrame) -> str:
    for column in ["r_multiple", "realized_r_multiple", "r", "pnl_r"]:
        if column in outcomes.columns:
            return column
    return ""


def _outcome_metrics(outcomes: pd.DataFrame) -> dict:
    if outcomes.empty:
        return {
            "outcomes_rows": 0,
            "completed_outcomes_count": 0,
            "avg_r_multiple": 0.0,
            "median_r_multiple": 0.0,
            "win_rate_paper": 0.0,
            "winning_trade_count": 0,
            "losing_trade_count": 0,
        }
    column = _r_multiple_column(outcomes)
    values = pd.to_numeric(outcomes[column], errors="coerce").dropna() if column else pd.Series(dtype=float)
    completed = int(len(values))
    wins = int((values > 0).sum()) if completed else 0
    losses = int((values < 0).sum()) if completed else 0
    return {
        "outcomes_rows": int(len(outcomes)),
        "completed_outcomes_count": completed,
        "avg_r_multiple": round(float(values.mean()), 4) if completed else 0.0,
        "median_r_multiple": round(float(values.median()), 4) if completed else 0.0,
        "win_rate_paper": round(wins / completed, 4) if completed else 0.0,
        "winning_trade_count": wins,
        "losing_trade_count": losses,
    }


def _weekly_metrics(weekly: pd.DataFrame, latest_weekly: dict) -> dict:
    scores = pd.to_numeric(weekly.get("weekly_operational_score", pd.Series(dtype=str)), errors="coerce").dropna()
    latest_score = _safe_float(latest_weekly.get("weekly_operational_score"), float(scores.iloc[-1]) if len(scores) else 0.0)
    avg_score = round(float(scores.mean()), 2) if len(scores) else latest_score
    return {
        "weekly_reviews_count": int(len(weekly)),
        "latest_weekly_operational_score": _bounded(latest_score),
        "avg_weekly_operational_score": _bounded(avg_score),
    }


def _component_scores(summary: dict, minimums: dict) -> dict:
    sample_size_score = _bounded(
        (
            _progress_score(summary["sessions_count"], minimums["min_sessions"])
            + _progress_score(summary["total_decisions"], minimums["min_decisions"])
            + _progress_score(summary["paper_enter_decisions"], minimums["min_paper_enters"])
            + _progress_score(summary["closed_paper_count"], minimums["min_closed_trades"])
        )
        / 4.0
    )
    return {
        "sample_size_score": sample_size_score,
        "session_consistency_score": _ratio_score(summary["closed_sessions_count"], summary["sessions_count"]),
        "checklist_discipline_score": _bounded(summary["checklist_completion_rate"] * 100.0),
        "decision_quality_score": _bounded(summary["avg_decision_quality_score"]),
        "paper_outcome_sample_score": _progress_score(summary["closed_paper_count"], minimums["min_closed_trades"]),
        "export_discipline_score": _bounded(100.0 - min(summary["pending_export_count"] * 20.0, 100.0)),
        "guardrail_compliance_score": _bounded(100.0 - min(summary["guardrail_violations_count"] * 25.0, 100.0)),
        "post_review_score": _ratio_score(summary["total_decisions"] - summary["decisions_without_post_review"], summary["total_decisions"]),
    }


def _readiness_status(summary: dict, minimums: dict) -> tuple[str, str]:
    sample_gaps = []
    if summary["sessions_count"] < minimums["min_sessions"]:
        sample_gaps.append("sessions_count below minimum")
    if summary["total_decisions"] < minimums["min_decisions"]:
        sample_gaps.append("total_decisions below minimum")
    if summary["paper_enter_decisions"] < minimums["min_paper_enters"]:
        sample_gaps.append("paper_enter_decisions below minimum")
    if summary["closed_paper_count"] < minimums["min_closed_trades"]:
        sample_gaps.append("closed_paper_count below minimum")

    if summary["guardrail_violations_count"] > 0 or not summary["no_real_order_notice_present"]:
        return "NOT_READY_GUARDRAIL_FAILURE", "Guardrail issues require manual review before calibration review."
    if summary["avg_decision_quality_score"] < 75 or summary["checklist_completion_rate"] < 0.85 or summary["decisions_without_reason"] > 0:
        return "PROCESS_REVIEW_REQUIRED", "Decision quality, checklist discipline, or missing reasons require process review."
    if sample_gaps:
        if summary["sessions_count"] == 0:
            return "INSUFFICIENT_SAMPLE", "No supervised sessions are available in the evidence window."
        return "COLLECT_MORE_EVIDENCE", "; ".join(sample_gaps)
    if summary["avg_weekly_operational_score"] < 75:
        return "PROCESS_REVIEW_REQUIRED", "Average weekly operational score is below calibration review threshold."
    return "READY_FOR_CALIBRATION_REVIEW", "Minimum evidence and discipline criteria are met for human calibration review."


def collect_evidence_window(
    root: Path = ROOT,
    *,
    days: int = 20,
    min_sessions: int = 10,
    min_decisions: int = 40,
    min_paper_enters: int = 10,
    min_closed_trades: int = 5,
) -> tuple[dict, pd.DataFrame]:
    end = date.today()
    start = end - timedelta(days=max(1, days) - 1)
    data = root / "data"
    reports = root / "reports"
    minimums = {
        "min_sessions": min_sessions,
        "min_decisions": min_decisions,
        "min_paper_enters": min_paper_enters,
        "min_closed_trades": min_closed_trades,
    }

    sessions = _window(_load_csv(data / "gui_supervised_sessions.csv"), ["session_date", "started_at"], start, end)
    checklists = _window(_load_csv(data / "gui_daily_operating_checklists.csv"), ["checklist_date", "marked_at"], start, end)
    decisions = _window(_load_csv(data / "gui_operational_decisions.csv"), ["decision_date", "timestamp"], start, end)
    weekly = _window(_load_csv(data / "gui_weekly_operational_reviews.csv"), ["review_end_date", "review_start_date"], start, end)
    actions = _window(_load_csv(data / "ui_action_log.csv"), ["action_date", "timestamp", "created_at"], start, end)
    journal = _load_csv(data / "paper_trading_journal.csv")
    outcomes = _load_csv(data / "trade_outcomes.csv")

    latest_weekly = _load_json(reports / "gui_weekly_operational_review_latest.json")
    decision_quality = _load_json(reports / "gui_decision_quality_review_latest.json")
    _load_json(reports / "gui_post_session_review_latest.json")
    cycle = _load_json(reports / "paper_trading_cycle_audit_latest.json")
    outcome_analytics = _load_json(reports / "trade_outcome_analytics_latest.json")
    calibration = _load_json(reports / "trade_score_calibration_latest.json")
    recommendations = _load_json(reports / "calibration_recommendations_latest.json")

    session_counts = _counts(sessions, "status")
    checklist_count, checklist_completion_rate = _checklist_completion(checklists)
    decision = _decision_metrics(decisions, decision_quality)
    weekly_summary = _weekly_metrics(weekly, latest_weekly)
    action = _action_metrics(actions)
    paper = _paper_counts(journal)
    outcome = _outcome_metrics(outcomes)

    if cycle:
        paper["open"] = _safe_int(cycle.get("open_paper_count"), paper["open"])
        paper["closed"] = _safe_int(cycle.get("closed_paper_count"), paper["closed"])
        paper["pending_export"] = _safe_int(cycle.get("pending_export_count"), paper["pending_export"])
        paper["exported"] = _safe_int(cycle.get("exported_count"), paper["exported"])
    if outcome_analytics:
        outcome["avg_r_multiple"] = _safe_float(outcome_analytics.get("avg_r_multiple"), outcome["avg_r_multiple"])
        outcome["win_rate_paper"] = _safe_float(outcome_analytics.get("win_rate"), outcome["win_rate_paper"])

    no_real_order_notice = True
    if not decisions.empty and "no_real_order_notice" in decisions.columns:
        no_real_order_notice = decisions["no_real_order_notice"].astype(str).str.lower().str.contains("no real order").any()

    data_quality_issues = 0
    for frame, columns in [
        (sessions, ["session_id", "status"]),
        (checklists, ["checklist_id", "status"]),
        (decisions, ["decision_id", "decision_type", "reason"]),
        (weekly, ["review_id", "weekly_operational_score"]),
    ]:
        if not frame.empty:
            data_quality_issues += sum(1 for column in columns if column not in frame.columns)
    data_quality_issues += 1 if calibration.get("status") == "FAIL" else 0
    data_quality_issues += 1 if recommendations.get("status") == "FAIL" else 0

    summary: dict[str, Any] = {
        "window_id": uuid.uuid5(uuid.NAMESPACE_URL, f"analista-evidence-{start}-{end}-{days}").hex,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_start_date": start.isoformat(),
        "window_end_date": end.isoformat(),
        "window_days": int(days),
        "status": "PASS",
        "sessions_count": int(len(sessions)),
        "closed_sessions_count": int(session_counts.get("CLOSED", 0)),
        "checklist_count": checklist_count,
        "checklist_completion_rate": checklist_completion_rate,
        "total_decisions": decision["total"],
        "paper_watch_decisions": decision["paper_watch"],
        "paper_enter_decisions": decision["paper_enter"],
        "skip_decisions": decision["skip"],
        "blocked_decisions": decision["blocked"],
        "needs_recheck_decisions": decision["needs_recheck"],
        "decisions_without_reason": decision["without_reason"],
        "decisions_without_post_review": decision["without_review"],
        "avg_decision_quality_score": decision["avg_quality"],
        **weekly_summary,
        **action,
        "journal_rows": paper["journal_rows"],
        "open_paper_count": paper["open"],
        "closed_paper_count": paper["closed"],
        "pending_export_count": paper["pending_export"],
        "exported_outcomes_count": paper["exported"],
        **outcome,
        "guardrail_violations_count": decision["guardrail_violations"],
        "data_quality_issues_count": data_quality_issues,
        "manual_review_only": True,
        "paper_trading_only": True,
        "no_real_order_notice_present": bool(no_real_order_notice),
        "execution_connection_detected": False,
        "real_order_detected": False,
        "notice": NOTICE,
        "manual_notice": MANUAL_NOTICE,
    }
    components = _component_scores(summary, minimums)
    summary.update(components)
    summary["evidence_sample_score"] = components["sample_size_score"]
    summary["evidence_quality_score"] = _bounded(
        (
            components["checklist_discipline_score"]
            + components["decision_quality_score"]
            + components["guardrail_compliance_score"]
            + components["post_review_score"]
        )
        / 4.0
    )
    summary["calibration_readiness_score"] = _bounded(sum(components.values()) / len(components))
    summary["readiness_bucket"] = _readiness_bucket(summary["calibration_readiness_score"])
    readiness_status, readiness_reason = _readiness_status(summary, minimums)
    summary["readiness_status"] = readiness_status
    summary["readiness_reason"] = readiness_reason
    summary["observational_next_steps"] = _next_steps(summary)
    if readiness_status != "READY_FOR_CALIBRATION_REVIEW":
        summary["status"] = "WARN"
    if data_quality_issues:
        summary["status"] = "WARN"

    row = {column: summary.get(column, "") for column in SUMMARY_COLUMNS}
    return summary, pd.DataFrame([row], columns=SUMMARY_COLUMNS)


def _next_steps(summary: dict) -> list[str]:
    steps = []
    if summary["readiness_status"] in {"INSUFFICIENT_SAMPLE", "COLLECT_MORE_EVIDENCE"}:
        steps.append("Continue supervised GUI sessions and paper-only evidence collection.")
    if summary["decisions_without_reason"]:
        steps.append("Review decisions missing reasons before calibration review.")
    if summary["decisions_without_post_review"]:
        steps.append("Complete post-session reviews for recorded decisions.")
    if summary["pending_export_count"]:
        steps.append("Review pending exports from closed paper trades.")
    if summary["guardrail_violations_count"]:
        steps.append("Resolve paper-only and quote discipline guardrail issues manually.")
    if not steps:
        steps.append("Evidence is ready for human calibration review; apply no automatic changes.")
    return steps


def build_markdown(summary: dict) -> str:
    lines = [
        "# Analista - GUI evidence collection window",
        "",
        "## Executive Summary",
        "",
        f"- status: {summary.get('status')}",
        f"- readiness_status: {summary.get('readiness_status')}",
        f"- calibration_readiness_score: {summary.get('calibration_readiness_score')}",
        f"- readiness_bucket: {summary.get('readiness_bucket')}",
        f"- readiness_reason: {summary.get('readiness_reason')}",
        f"- notice: {NOTICE}",
        "",
        "## Sample Metrics",
        "",
        f"- window_days: {summary.get('window_days')}",
        f"- sessions_count: {summary.get('sessions_count')}",
        f"- closed_sessions_count: {summary.get('closed_sessions_count')}",
        f"- weekly_reviews_count: {summary.get('weekly_reviews_count')}",
        f"- total_decisions: {summary.get('total_decisions')}",
        f"- paper_enter_decisions: {summary.get('paper_enter_decisions')}",
        "",
        "## Discipline Metrics",
        "",
        f"- checklist_count: {summary.get('checklist_count')}",
        f"- checklist_completion_rate: {summary.get('checklist_completion_rate')}",
        f"- decisions_without_reason: {summary.get('decisions_without_reason')}",
        f"- decisions_without_post_review: {summary.get('decisions_without_post_review')}",
        f"- avg_decision_quality_score: {summary.get('avg_decision_quality_score')}",
        f"- avg_weekly_operational_score: {summary.get('avg_weekly_operational_score')}",
        "",
        "## Paper Trading",
        "",
        f"- paper_actions_logged: {summary.get('paper_actions_logged')}",
        f"- paper_enter_action_count: {summary.get('paper_enter_action_count')}",
        f"- paper_close_action_count: {summary.get('paper_close_action_count')}",
        f"- journal_rows: {summary.get('journal_rows')}",
        f"- open_paper_count: {summary.get('open_paper_count')}",
        f"- closed_paper_count: {summary.get('closed_paper_count')}",
        f"- pending_export_count: {summary.get('pending_export_count')}",
        f"- exported_outcomes_count: {summary.get('exported_outcomes_count')}",
        "",
        "## Paper Outcomes",
        "",
        f"- outcomes_rows: {summary.get('outcomes_rows')}",
        f"- completed_outcomes_count: {summary.get('completed_outcomes_count')}",
        f"- avg_r_multiple: {summary.get('avg_r_multiple')}",
        f"- median_r_multiple: {summary.get('median_r_multiple')}",
        f"- win_rate_paper: {summary.get('win_rate_paper')}",
        "",
        "## Guardrails",
        "",
        f"- guardrail_violations_count: {summary.get('guardrail_violations_count')}",
        f"- no_real_order_notice_present: {summary.get('no_real_order_notice_present')}",
        "- observational only; no automatic trading changes",
        "- manual review only",
        "- paper trading only",
        "- no real orders",
        "",
        "## No-Readiness Reasons",
        "",
        f"- {summary.get('readiness_reason')}",
        "",
        "## Observational Next Steps",
        "",
    ]
    lines.extend(f"- {item}" for item in summary.get("observational_next_steps", []))
    return "\n".join(lines)


def _write_history(csv_path: Path, row_df: pd.DataFrame) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if csv_path.exists():
        try:
            history = pd.read_csv(csv_path, dtype=str).fillna("")
        except Exception:
            history = pd.DataFrame(columns=SUMMARY_COLUMNS)
    else:
        history = pd.DataFrame(columns=SUMMARY_COLUMNS)
    for column in SUMMARY_COLUMNS:
        if column not in history.columns:
            history[column] = ""
    window_id = _safe_text(row_df.iloc[0].get("window_id"))
    if window_id and "window_id" in history.columns:
        history = history[history["window_id"].astype(str).ne(window_id)]
    if history.empty:
        out = row_df[SUMMARY_COLUMNS].copy()
    else:
        out = pd.concat([history[SUMMARY_COLUMNS], row_df[SUMMARY_COLUMNS]], ignore_index=True)
    out.to_csv(csv_path, index=False)


def save_window(
    *,
    root: Path = ROOT,
    days: int = 20,
    min_sessions: int = 10,
    min_decisions: int = 40,
    min_paper_enters: int = 10,
    min_closed_trades: int = 5,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
    csv_out: Path | None = None,
    history_csv: Path | None = None,
) -> dict:
    summary, row_df = collect_evidence_window(
        root=root,
        days=days,
        min_sessions=min_sessions,
        min_decisions=min_decisions,
        min_paper_enters=min_paper_enters,
        min_closed_trades=min_closed_trades,
    )
    reports = root / "reports"
    json_out = json_out or reports / "gui_evidence_collection_window_latest.json"
    markdown_out = markdown_out or reports / "gui_evidence_collection_window_latest.md"
    csv_out = csv_out or reports / "gui_evidence_collection_window_latest.csv"
    history_csv = history_csv or root / "data" / "gui_evidence_collection_windows.csv"
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    row_df.to_csv(csv_out, index=False)
    _write_history(history_csv, row_df)
    json_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_markdown(summary), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolida ventana de evidencia GUI paper-only.")
    parser.add_argument("--days", type=int, default=20)
    parser.add_argument("--min-sessions", type=int, default=10)
    parser.add_argument("--min-decisions", type=int, default=40)
    parser.add_argument("--min-paper-enters", type=int, default=10)
    parser.add_argument("--min-closed-trades", type=int, default=5)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--json-out", default="")
    parser.add_argument("--markdown-out", default="")
    parser.add_argument("--csv-out", default="")
    args = parser.parse_args()
    try:
        result = save_window(
            days=args.days,
            min_sessions=args.min_sessions,
            min_decisions=args.min_decisions,
            min_paper_enters=args.min_paper_enters,
            min_closed_trades=args.min_closed_trades,
            json_out=Path(args.json_out) if args.json_out else None,
            markdown_out=Path(args.markdown_out) if args.markdown_out else None,
            csv_out=Path(args.csv_out) if args.csv_out else None,
        )
    except Exception as exc:
        result = {"status": "FAIL", "message": f"controlled_error:{type(exc).__name__}", "notice": NOTICE}
    print("=== ANALISTA GUI EVIDENCE COLLECTION WINDOW ===")
    print(f"Status: {result.get('status')}")
    print(f"Readiness: {result.get('readiness_status', '')}")
    print(f"Calibration readiness score: {result.get('calibration_readiness_score', '')}")
    print(f"Bucket: {result.get('readiness_bucket', '')}")
    print(f"Notice: {NOTICE}")
    if args.summary:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0 if result.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
