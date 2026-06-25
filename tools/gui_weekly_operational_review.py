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


NOTICE = "observational only; no automatic trading changes; no scoring changes; no threshold changes"
MANUAL_NOTICE = "manual review only; paper trading only; no real orders"
NO_REAL_ORDER_NOTICE = "paper trading only; no real order"

SUMMARY_COLUMNS = [
    "review_id",
    "review_start_date",
    "review_end_date",
    "status",
    "sessions_count",
    "closed_sessions_count",
    "checklist_count",
    "checklist_pass_count",
    "checklist_warn_count",
    "checklist_fail_count",
    "checklist_completion_rate",
    "required_steps_pending_total",
    "total_decisions",
    "paper_watch_decisions",
    "paper_enter_decisions",
    "skip_decisions",
    "blocked_decisions",
    "needs_recheck_decisions",
    "decisions_without_reason",
    "decisions_without_post_review",
    "lessons_added_count",
    "avg_decision_quality_score",
    "decision_quality_bucket",
    "paper_actions_logged",
    "paper_enter_action_count",
    "paper_close_action_count",
    "exported_outcomes_count",
    "open_paper_count",
    "closed_paper_count",
    "pending_export_count",
    "outcomes_rows",
    "completed_outcomes_count",
    "avg_r_multiple",
    "median_r_multiple",
    "win_rate_paper",
    "losing_trade_count",
    "winning_trade_count",
    "data_quality_issues_count",
    "guardrail_violations_count",
    "observational_recommendations_count",
    "weekly_operational_score",
    "weekly_operational_bucket",
    "weekly_recommendation",
    "ready_for_calibration_review",
    "session_discipline_score",
    "checklist_completion_score",
    "decision_quality_score",
    "paper_action_consistency_score",
    "post_session_review_score",
    "outcome_export_discipline_score",
    "guardrail_compliance_score",
    "lesson_capture_score",
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


def _ratio_score(ok: int, total: int) -> float:
    if total <= 0:
        return 100.0
    return _bounded((ok / total) * 100.0)


def _rate(ok: int, total: int) -> float:
    if total <= 0:
        return 1.0
    return round(ok / total, 4)


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


def _latest_source_date(frames: list[tuple[pd.DataFrame, list[str]]]) -> date:
    latest: date | None = None
    for frame, candidates in frames:
        if frame.empty:
            continue
        dates = _parse_date_series(frame, candidates).dropna()
        if dates.empty:
            continue
        frame_latest = max(dates)
        latest = frame_latest if latest is None else max(latest, frame_latest)
    return latest or date.today()


def _value_counts(df: pd.DataFrame, column: str) -> Counter:
    if df.empty or column not in df.columns:
        return Counter()
    return Counter(df[column].astype(str).str.upper().str.strip().tolist())


def _review_bucket(score: float) -> str:
    if score >= 85:
        return "A_READY_FOR_EXTENDED_PAPER"
    if score >= 70:
        return "B_ACCEPTABLE_CONTINUE"
    if score >= 50:
        return "C_NEEDS_PROCESS_REVIEW"
    return "D_NOT_READY"


def _quality_bucket(score: float) -> str:
    if score >= 85:
        return "A_DISCIPLINED"
    if score >= 70:
        return "B_ACCEPTABLE"
    if score >= 50:
        return "C_NEEDS_REVIEW"
    return "D_UNDISCIPLINED"


def _r_multiple_column(outcomes: pd.DataFrame) -> str:
    for column in ["r_multiple", "realized_r_multiple", "r", "pnl_r"]:
        if column in outcomes.columns:
            return column
    return ""


def _paper_status_counts(journal: pd.DataFrame) -> dict:
    if journal.empty:
        return {"open": 0, "closed": 0, "pending_export": 0, "exported": 0}
    status = journal.get("followup_status", pd.Series(dtype=str)).astype(str).str.upper()
    decision = journal.get("manual_decision", pd.Series(dtype=str)).astype(str).str.upper()
    exported = journal.get("outcome_exported", pd.Series(dtype=str)).map(_safe_bool)
    open_mask = decision.eq("PAPER_ENTER") | status.isin({"OPEN_MONITORING", "ENTERED_PAPER"})
    closed_mask = status.eq("CLOSED_PAPER")
    return {
        "open": int((open_mask & ~closed_mask).sum()),
        "closed": int(closed_mask.sum()),
        "pending_export": int((closed_mask & ~exported).sum()) if len(exported) else 0,
        "exported": int((closed_mask & exported).sum()) if len(exported) else 0,
    }


def _checklist_metrics(checklists: pd.DataFrame) -> dict:
    if checklists.empty:
        return {
            "checklist_count": 0,
            "pass": 0,
            "warn": 0,
            "fail": 0,
            "completion_rate": 1.0,
            "required_pending": 0,
        }
    ids = checklists["checklist_id"].astype(str) if "checklist_id" in checklists.columns else pd.Series(range(len(checklists)))
    result = checklists.get("result", pd.Series(dtype=str)).astype(str).str.upper()
    status = checklists.get("status", pd.Series(dtype=str)).astype(str).str.upper()
    required = checklists.get("required", pd.Series(dtype=str)).astype(str).str.lower().isin({"true", "1", "yes"})
    done = int(status.eq("DONE").sum())
    total_steps = int(len(checklists))
    required_pending = int((required & status.eq("PENDING")).sum())
    latest_by_id = checklists.assign(_result=result).groupby(ids, dropna=False)["_result"].last()
    return {
        "checklist_count": int(ids.nunique()),
        "pass": int(latest_by_id.eq("PASS").sum()),
        "warn": int(latest_by_id.eq("WARN").sum()),
        "fail": int(latest_by_id.isin({"FAIL", "ABORTED"}).sum()),
        "completion_rate": _rate(done, total_steps),
        "required_pending": required_pending,
    }


def _outcome_metrics(outcomes: pd.DataFrame) -> dict:
    if outcomes.empty:
        return {
            "outcomes_rows": 0,
            "completed_outcomes_count": 0,
            "avg_r_multiple": 0.0,
            "median_r_multiple": 0.0,
            "win_rate_paper": 0.0,
            "losing_trade_count": 0,
            "winning_trade_count": 0,
        }
    r_column = _r_multiple_column(outcomes)
    r_values = pd.to_numeric(outcomes[r_column], errors="coerce").dropna() if r_column else pd.Series(dtype=float)
    completed = len(r_values)
    winning = int((r_values > 0).sum()) if completed else 0
    losing = int((r_values < 0).sum()) if completed else 0
    return {
        "outcomes_rows": int(len(outcomes)),
        "completed_outcomes_count": int(completed),
        "avg_r_multiple": round(float(r_values.mean()), 4) if completed else 0.0,
        "median_r_multiple": round(float(r_values.median()), 4) if completed else 0.0,
        "win_rate_paper": round(winning / completed, 4) if completed else 0.0,
        "losing_trade_count": losing,
        "winning_trade_count": winning,
    }


def _decision_metrics(decisions: pd.DataFrame, quality: dict) -> dict:
    types = _value_counts(decisions, "decision_type")
    total = int(len(decisions))
    no_reason = 0
    no_review = 0
    lessons = 0
    guardrail_violations = 0
    if not decisions.empty:
        reason = decisions.get("reason", pd.Series(dtype=str)).astype(str).str.strip()
        review = decisions.get("post_session_review_status", pd.Series(dtype=str)).astype(str).str.upper()
        lessons_text = decisions.get("lesson_learned", pd.Series(dtype=str)).astype(str).str.strip()
        no_order = decisions.get("no_real_order_confirmed", pd.Series(dtype=str)).map(_safe_bool)
        quote_status = decisions.get("quote_status", pd.Series(dtype=str)).astype(str).str.upper()
        quote_quality = decisions.get("execution_quote_quality", pd.Series(dtype=str)).astype(str).str.upper()
        dtype = decisions.get("decision_type", pd.Series(dtype=str)).astype(str).str.upper()
        no_reason = int((reason.eq("") & ~dtype.eq("SESSION_NOTE")).sum())
        no_review = int((~review.isin({"REVIEWED", "LESSON_ADDED", "NEEDS_MORE_DATA"})).sum())
        lessons = int(lessons_text.ne("").sum())
        guardrail_violations = int((~no_order).sum()) if len(no_order) else 0
        guardrail_violations += int((dtype.eq("PAPER_ENTER") & quote_status.ne("") & ~quote_status.eq("VALID")).sum())
        guardrail_violations += int((dtype.eq("PAPER_ENTER") & quote_quality.eq("LOW")).sum())
    avg_score = _safe_float(quality.get("decision_quality_score"), 100.0 if total == 0 else 0.0)
    return {
        "total": total,
        "paper_watch": types.get("PAPER_WATCH", 0),
        "paper_enter": types.get("PAPER_ENTER", 0),
        "skip": types.get("SKIP", 0),
        "blocked": types.get("BLOCKED", 0),
        "needs_recheck": types.get("NEEDS_RECHECK", 0),
        "without_reason": no_reason,
        "without_post_review": no_review,
        "lessons": lessons,
        "avg_quality": _bounded(avg_score),
        "quality_bucket": str(quality.get("decision_quality_bucket") or _quality_bucket(avg_score)),
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


def _score_components(
    *,
    sessions_count: int,
    closed_sessions_count: int,
    checklist_completion_rate: float,
    required_pending: int,
    total_decisions: int,
    avg_decision_quality: float,
    decisions_without_post_review: int,
    paper_actions_logged: int,
    paper_enter_decisions: int,
    pending_export_count: int,
    guardrail_violations_count: int,
    lessons_added_count: int,
) -> dict:
    return {
        "session_discipline_score": _ratio_score(closed_sessions_count, sessions_count),
        "checklist_completion_score": _bounded((checklist_completion_rate * 100.0) - min(required_pending * 5.0, 50.0)),
        "decision_quality_score": _bounded(avg_decision_quality),
        "paper_action_consistency_score": _ratio_score(paper_actions_logged, max(paper_enter_decisions, paper_actions_logged)),
        "post_session_review_score": _ratio_score(total_decisions - decisions_without_post_review, total_decisions),
        "outcome_export_discipline_score": _bounded(100.0 - min(pending_export_count * 20.0, 100.0)),
        "guardrail_compliance_score": _bounded(100.0 - min(guardrail_violations_count * 25.0, 100.0)),
        "lesson_capture_score": _ratio_score(lessons_added_count, total_decisions),
    }


def _ready_for_calibration(summary: dict) -> bool:
    return (
        summary["sessions_count"] >= 5
        and summary["total_decisions"] >= 20
        and summary["paper_enter_decisions"] >= 5
        and summary["avg_decision_quality_score"] >= 75
        and summary["checklist_completion_rate"] >= 0.85
        and summary["guardrail_violations_count"] == 0
        and bool(summary.get("no_real_order_notice_present"))
        and not bool(summary.get("execution_connection_detected"))
        and not bool(summary.get("real_order_detected"))
    )


def _weekly_recommendation(summary: dict) -> str:
    if _ready_for_calibration(summary):
        return "READY_FOR_CALIBRATION_REVIEW"
    if summary["sessions_count"] < 5 or summary["total_decisions"] < 20 or summary["paper_enter_decisions"] < 5:
        return "EXTEND_SAMPLE_SIZE"
    if summary["decisions_without_reason"] or summary["decisions_without_post_review"]:
        return "REVIEW_DECISION_DISCIPLINE"
    if summary["checklist_completion_rate"] < 0.85 or summary["required_steps_pending_total"]:
        return "REVIEW_CHECKLIST_DISCIPLINE"
    if summary["guardrail_violations_count"]:
        return "REVIEW_QUOTE_DISCIPLINE"
    return "CONTINUE_PAPER_COLLECTION"


def _recent_warnings(summary: dict) -> list[str]:
    warnings: list[str] = []
    if summary["sessions_count"] < 5:
        warnings.append("fewer_than_5_sessions")
    if summary["total_decisions"] < 20:
        warnings.append("fewer_than_20_decisions")
    if summary["paper_enter_decisions"] < 5:
        warnings.append("fewer_than_5_paper_enter_decisions")
    if summary["decisions_without_reason"]:
        warnings.append("decisions_without_reason")
    if summary["decisions_without_post_review"]:
        warnings.append("decisions_without_post_review")
    if summary["required_steps_pending_total"]:
        warnings.append("required_checklist_steps_pending")
    if summary["pending_export_count"]:
        warnings.append("closed_paper_pending_export")
    if summary["guardrail_violations_count"]:
        warnings.append("guardrail_violations_for_manual_review")
    return warnings


def collect_weekly_review(root: Path = ROOT, *, days: int = 7) -> tuple[dict, pd.DataFrame]:
    data = root / "data"
    reports = root / "reports"

    sessions_raw = _load_csv(data / "gui_supervised_sessions.csv")
    checklists_raw = _load_csv(data / "gui_daily_operating_checklists.csv")
    decisions_raw = _load_csv(data / "gui_operational_decisions.csv")
    actions_raw = _load_csv(data / "ui_action_log.csv")

    end = _latest_source_date(
        [
            (sessions_raw, ["session_date", "started_at"]),
            (checklists_raw, ["checklist_date", "marked_at"]),
            (decisions_raw, ["decision_date", "timestamp"]),
            (actions_raw, ["action_date", "timestamp", "created_at"]),
        ]
    )
    start = end - timedelta(days=max(1, days) - 1)

    sessions = _window(sessions_raw, ["session_date", "started_at"], start, end)
    checklists = _window(checklists_raw, ["checklist_date", "marked_at"], start, end)
    decisions = _window(decisions_raw, ["decision_date", "timestamp"], start, end)
    actions = _window(actions_raw, ["action_date", "timestamp", "created_at"], start, end)
    journal = _load_csv(data / "paper_trading_journal.csv")
    outcomes = _load_csv(data / "trade_outcomes.csv")

    decision_quality = _load_json(reports / "gui_decision_quality_review_latest.json")
    post_session = _load_json(reports / "gui_post_session_review_latest.json")
    cycle = _load_json(reports / "paper_trading_cycle_audit_latest.json")
    outcome_analytics = _load_json(reports / "trade_outcome_analytics_latest.json")
    score_calibration = _load_json(reports / "trade_score_calibration_latest.json")
    calibration_recs = _load_json(reports / "calibration_recommendations_latest.json")

    sessions_status = _value_counts(sessions, "status")
    checklist = _checklist_metrics(checklists)
    decision = _decision_metrics(decisions, decision_quality)
    actions_summary = _action_metrics(actions)
    paper_counts = _paper_status_counts(journal)
    outcome = _outcome_metrics(outcomes)

    if cycle:
        paper_counts["open"] = _safe_int(cycle.get("open_paper_count"), paper_counts["open"])
        paper_counts["closed"] = _safe_int(cycle.get("closed_paper_count"), paper_counts["closed"])
        paper_counts["pending_export"] = _safe_int(cycle.get("pending_export_count"), paper_counts["pending_export"])
        paper_counts["exported"] = _safe_int(cycle.get("exported_count"), paper_counts["exported"])
    if outcome_analytics:
        outcome["avg_r_multiple"] = _safe_float(outcome_analytics.get("avg_r_multiple"), outcome["avg_r_multiple"])
        outcome["win_rate_paper"] = _safe_float(outcome_analytics.get("win_rate"), outcome["win_rate_paper"])

    no_real_order_notice_present = True
    if not decisions.empty and "no_real_order_notice" in decisions.columns:
        no_real_order_notice_present = decisions["no_real_order_notice"].astype(str).str.lower().str.contains("no real order").any()

    data_quality_issues = 0
    for frame, required_columns in [
        (sessions, ["session_id", "status"]),
        (checklists, ["checklist_id", "status"]),
        (decisions, ["decision_id", "decision_type", "reason"]),
    ]:
        if not frame.empty:
            data_quality_issues += sum(1 for column in required_columns if column not in frame.columns)
    data_quality_issues += _safe_int(score_calibration.get("sample_size_warning"), 0) if isinstance(score_calibration.get("sample_size_warning"), int) else 0

    summary: dict[str, Any] = {
        "review_id": uuid.uuid5(uuid.NAMESPACE_URL, f"analista-weekly-{start}-{end}").hex,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "review_start_date": start.isoformat(),
        "review_end_date": end.isoformat(),
        "status": "PASS",
        "notice": NOTICE,
        "manual_notice": MANUAL_NOTICE,
        "manual_review_only": True,
        "paper_trading_only": True,
        "no_real_order_notice_present": bool(no_real_order_notice_present),
        "execution_connection_detected": False,
        "real_order_detected": False,
        "sessions_count": int(len(sessions)),
        "closed_sessions_count": int(sessions_status.get("CLOSED", 0)),
        "checklist_count": checklist["checklist_count"],
        "checklist_pass_count": checklist["pass"],
        "checklist_warn_count": checklist["warn"],
        "checklist_fail_count": checklist["fail"],
        "checklist_completion_rate": checklist["completion_rate"],
        "required_steps_pending_total": checklist["required_pending"],
        "total_decisions": decision["total"],
        "paper_watch_decisions": decision["paper_watch"],
        "paper_enter_decisions": decision["paper_enter"],
        "skip_decisions": decision["skip"],
        "blocked_decisions": decision["blocked"],
        "needs_recheck_decisions": decision["needs_recheck"],
        "decisions_without_reason": decision["without_reason"],
        "decisions_without_post_review": decision["without_post_review"],
        "lessons_added_count": decision["lessons"],
        "avg_decision_quality_score": decision["avg_quality"],
        "decision_quality_bucket": decision["quality_bucket"],
        "paper_actions_logged": actions_summary["paper_actions_logged"],
        "paper_enter_action_count": actions_summary["paper_enter_action_count"],
        "paper_close_action_count": actions_summary["paper_close_action_count"],
        "exported_outcomes_count": paper_counts["exported"],
        "open_paper_count": paper_counts["open"],
        "closed_paper_count": paper_counts["closed"],
        "pending_export_count": paper_counts["pending_export"],
        **outcome,
        "data_quality_issues_count": data_quality_issues,
        "guardrail_violations_count": decision["guardrail_violations"],
        "post_session_status": post_session.get("status", "MISSING"),
        "paper_cycle_status": cycle.get("status", "MISSING"),
        "trade_score_calibration_status": score_calibration.get("status", "MISSING"),
        "calibration_recommendations_status": calibration_recs.get("status", "MISSING"),
    }
    components = _score_components(
        sessions_count=summary["sessions_count"],
        closed_sessions_count=summary["closed_sessions_count"],
        checklist_completion_rate=summary["checklist_completion_rate"],
        required_pending=summary["required_steps_pending_total"],
        total_decisions=summary["total_decisions"],
        avg_decision_quality=summary["avg_decision_quality_score"],
        decisions_without_post_review=summary["decisions_without_post_review"],
        paper_actions_logged=summary["paper_actions_logged"],
        paper_enter_decisions=summary["paper_enter_decisions"],
        pending_export_count=summary["pending_export_count"],
        guardrail_violations_count=summary["guardrail_violations_count"],
        lessons_added_count=summary["lessons_added_count"],
    )
    summary.update(components)
    summary["weekly_operational_score"] = _bounded(sum(components.values()) / len(components))
    summary["weekly_operational_bucket"] = _review_bucket(summary["weekly_operational_score"])
    summary["weekly_recommendation"] = _weekly_recommendation(summary)
    summary["ready_for_calibration_review"] = _ready_for_calibration(summary)
    summary["recurrent_problems"] = _recent_warnings(summary)
    summary["observational_recommendations"] = _recommendation_notes(summary)
    summary["observational_recommendations_count"] = len(summary["observational_recommendations"])
    if summary["guardrail_violations_count"] or summary["data_quality_issues_count"]:
        summary["status"] = "WARN"
    elif summary["sessions_count"] == 0 or summary["total_decisions"] == 0:
        summary["status"] = "WARN"

    row = {column: summary.get(column, "") for column in SUMMARY_COLUMNS}
    row["notice"] = NOTICE
    row["manual_notice"] = MANUAL_NOTICE
    return summary, pd.DataFrame([row], columns=SUMMARY_COLUMNS)


def _recommendation_notes(summary: dict) -> list[str]:
    recommendation = summary.get("weekly_recommendation")
    notes = [str(recommendation)]
    if recommendation == "EXTEND_SAMPLE_SIZE":
        notes.append("Continue collecting supervised GUI and paper trading evidence before calibration review.")
    if summary.get("decisions_without_reason"):
        notes.append("Review decision discipline: some decisions are missing reasons.")
    if summary.get("decisions_without_post_review"):
        notes.append("Complete post-session review before relying on weekly conclusions.")
    if summary.get("required_steps_pending_total"):
        notes.append("Review checklist discipline: required steps remain pending.")
    if summary.get("pending_export_count"):
        notes.append("Review outcome export discipline for closed paper trades.")
    if summary.get("guardrail_violations_count"):
        notes.append("Review quote and paper-only guardrails manually.")
    if recommendation == "READY_FOR_CALIBRATION_REVIEW":
        notes.append("Evidence is sufficient for human calibration review; no automatic scoring changes.")
    return notes


def build_markdown(summary: dict) -> str:
    lines = [
        "# Analista - GUI weekly operational review",
        "",
        "## Weekly Executive Summary",
        "",
        f"- status: {summary.get('status')}",
        f"- review_start_date: {summary.get('review_start_date')}",
        f"- review_end_date: {summary.get('review_end_date')}",
        f"- notice: {NOTICE}",
        f"- manual_notice: {MANUAL_NOTICE}",
        "",
        "## Score",
        "",
        f"- weekly_operational_score: {summary.get('weekly_operational_score')}",
        f"- weekly_operational_bucket: {summary.get('weekly_operational_bucket')}",
        f"- weekly_recommendation: {summary.get('weekly_recommendation')}",
        f"- ready_for_calibration_review: {summary.get('ready_for_calibration_review')}",
        "",
        "## Sessions Reviewed",
        "",
        f"- sessions_count: {summary.get('sessions_count')}",
        f"- closed_sessions_count: {summary.get('closed_sessions_count')}",
        f"- session_discipline_score: {summary.get('session_discipline_score')}",
        "",
        "## Checklists Reviewed",
        "",
        f"- checklist_count: {summary.get('checklist_count')}",
        f"- checklist_completion_rate: {summary.get('checklist_completion_rate')}",
        f"- required_steps_pending_total: {summary.get('required_steps_pending_total')}",
        "",
        "## Decision Quality",
        "",
        f"- total_decisions: {summary.get('total_decisions')}",
        f"- paper_watch_decisions: {summary.get('paper_watch_decisions')}",
        f"- paper_enter_decisions: {summary.get('paper_enter_decisions')}",
        f"- decisions_without_reason: {summary.get('decisions_without_reason')}",
        f"- decisions_without_post_review: {summary.get('decisions_without_post_review')}",
        f"- avg_decision_quality_score: {summary.get('avg_decision_quality_score')}",
        f"- decision_quality_bucket: {summary.get('decision_quality_bucket')}",
        "",
        "## Paper Actions",
        "",
        f"- paper_actions_logged: {summary.get('paper_actions_logged')}",
        f"- paper_enter_action_count: {summary.get('paper_enter_action_count')}",
        f"- paper_close_action_count: {summary.get('paper_close_action_count')}",
        f"- open_paper_count: {summary.get('open_paper_count')}",
        f"- closed_paper_count: {summary.get('closed_paper_count')}",
        f"- pending_export_count: {summary.get('pending_export_count')}",
        "",
        "## Paper Outcomes",
        "",
        f"- outcomes_rows: {summary.get('outcomes_rows')}",
        f"- completed_outcomes_count: {summary.get('completed_outcomes_count')}",
        f"- avg_r_multiple: {summary.get('avg_r_multiple')}",
        f"- median_r_multiple: {summary.get('median_r_multiple')}",
        f"- win_rate_paper: {summary.get('win_rate_paper')}",
        f"- winning_trade_count: {summary.get('winning_trade_count')}",
        f"- losing_trade_count: {summary.get('losing_trade_count')}",
        "",
        "## Recurrent Problems",
        "",
    ]
    problems = summary.get("recurrent_problems") or []
    lines.extend([f"- {item}" for item in problems] if problems else ["- none"])
    lines.extend(["", "## Lessons", ""])
    lines.append(f"- lessons_added_count: {summary.get('lessons_added_count')}")
    if summary.get("lessons_added_count", 0):
        lines.append("- Continue capturing concise lessons from reviewed decisions.")
    else:
        lines.append("- Add lessons during post-session review when evidence supports it.")
    lines.extend(["", "## Guardrails", ""])
    lines.append("- observational only")
    lines.append("- no automatic trading changes")
    lines.append("- no scoring changes")
    lines.append("- no threshold changes")
    lines.append("- manual review only")
    lines.append("- paper trading only")
    lines.append("- no real orders")
    lines.extend(["", "## Decision To Continue Evidence Or Review Process", ""])
    lines.extend(f"- {item}" for item in summary.get("observational_recommendations", []))
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
    review_id = _safe_text(row_df.iloc[0].get("review_id"))
    if review_id and "review_id" in history.columns:
        history = history[history["review_id"].astype(str).ne(review_id)]
    if history.empty:
        out = row_df[SUMMARY_COLUMNS].copy()
    else:
        out = pd.concat([history[SUMMARY_COLUMNS], row_df[SUMMARY_COLUMNS]], ignore_index=True)
    out.to_csv(csv_path, index=False)


def save_review(
    *,
    root: Path = ROOT,
    days: int = 7,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
    csv_out: Path | None = None,
    history_csv: Path | None = None,
) -> dict:
    summary, row_df = collect_weekly_review(root=root, days=days)
    reports = root / "reports"
    json_out = json_out or reports / "gui_weekly_operational_review_latest.json"
    markdown_out = markdown_out or reports / "gui_weekly_operational_review_latest.md"
    csv_out = csv_out or reports / "gui_weekly_operational_review_latest.csv"
    history_csv = history_csv or root / "data" / "gui_weekly_operational_reviews.csv"
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    row_df.to_csv(csv_out, index=False)
    _write_history(history_csv, row_df)
    json_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_markdown(summary), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera review semanal operacional GUI paper-only.")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--json-out", default="")
    parser.add_argument("--markdown-out", default="")
    parser.add_argument("--csv-out", default="")
    args = parser.parse_args()
    try:
        result = save_review(
            days=args.days,
            json_out=Path(args.json_out) if args.json_out else None,
            markdown_out=Path(args.markdown_out) if args.markdown_out else None,
            csv_out=Path(args.csv_out) if args.csv_out else None,
        )
    except Exception as exc:
        result = {"status": "FAIL", "message": f"controlled_error:{type(exc).__name__}", "notice": NOTICE}
    print("=== ANALISTA GUI WEEKLY OPERATIONAL REVIEW ===")
    print(f"Status: {result.get('status')}")
    print(f"Weekly operational score: {result.get('weekly_operational_score', '')}")
    print(f"Weekly operational bucket: {result.get('weekly_operational_bucket', '')}")
    print(f"Weekly recommendation: {result.get('weekly_recommendation', '')}")
    print(f"Notice: {NOTICE}")
    if args.summary:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0 if result.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
