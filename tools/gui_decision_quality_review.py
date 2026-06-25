from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


NOTICE = "observational only; no automatic trading changes"
CSV_COLUMNS = [
    "decision_id",
    "decision_date",
    "ticker",
    "journal_id",
    "decision_type",
    "decision_status",
    "signal",
    "recommendation",
    "quote_status",
    "execution_quote_quality",
    "final_trade_score",
    "checklist_status",
    "reason_present",
    "post_review_present",
    "followup_plan_present",
    "checklist_aligned",
    "no_real_order_confirmed",
    "decision_quality_score",
    "decision_quality_bucket",
    "quality_warnings",
    "quality_recommendations",
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


def _safe_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


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


def _score_bucket(score: float) -> str:
    if score >= 85:
        return "A_DISCIPLINED"
    if score >= 70:
        return "B_ACCEPTABLE"
    if score >= 50:
        return "C_NEEDS_REVIEW"
    return "D_UNDISCIPLINED"


def _bounded(value: float) -> float:
    return max(0.0, min(100.0, round(float(value), 2)))


def _ratio_score(ok: int, total: int) -> float:
    if total <= 0:
        return 100.0
    return _bounded((ok / total) * 100.0)


def _quality_for_row(row: dict, ticker_counts: Counter) -> dict:
    decision_type = _safe_text(row.get("decision_type")).upper()
    quote_status = _safe_text(row.get("quote_status")).upper()
    quote_quality = _safe_text(row.get("execution_quote_quality")).upper()
    reason_present = bool(_safe_text(row.get("reason")))
    followup_present = bool(_safe_text(row.get("followup_plan")))
    post_review = _safe_text(row.get("post_session_review_status")).upper()
    post_review_present = post_review in {"REVIEWED", "LESSON_ADDED", "NEEDS_MORE_DATA"}
    checklist_value = _safe_text(row.get("checklist_aligned")).lower()
    checklist_aligned = checklist_value not in {"false", "no", "0"} if checklist_value else True
    no_real_order_confirmed = _safe_bool(row.get("no_real_order_confirmed"))
    final_trade_score_present = bool(_safe_text(row.get("final_trade_score")))
    checklist_status_present = bool(_safe_text(row.get("checklist_status")))
    ticker = _safe_text(row.get("ticker")).upper()

    warnings: list[str] = []
    recommendations: list[str] = []
    score = 100.0

    if not reason_present and decision_type != "SESSION_NOTE":
        score -= 25
        warnings.append("missing_reason")
        recommendations.append("record_reason_before_review")
    if not post_review_present:
        score -= 15
        warnings.append("missing_post_review")
        recommendations.append("complete_post_session_review")
    if not followup_present and decision_type in {"PAPER_WATCH", "PAPER_ENTER", "NEEDS_RECHECK"}:
        score -= 10
        warnings.append("missing_followup_plan")
        recommendations.append("add_followup_plan")
    if not checklist_aligned:
        score -= 20
        warnings.append("not_checklist_aligned")
        recommendations.append("review_checklist_alignment")
    if not no_real_order_confirmed:
        score -= 30
        warnings.append("missing_no_real_order_confirmation")
        recommendations.append("confirm_paper_only_guardrail")
    if decision_type == "PAPER_ENTER" and quote_status and quote_status != "VALID":
        score -= 25
        warnings.append("paper_enter_non_valid_quote_status")
        recommendations.append("avoid_paper_enter_until_quote_validated")
    if decision_type == "PAPER_ENTER" and quote_quality == "LOW":
        score -= 30
        warnings.append("paper_enter_low_quote_quality")
        recommendations.append("avoid_paper_enter_with_low_quote_quality")
    if decision_type == "PAPER_ENTER" and not final_trade_score_present:
        score -= 10
        warnings.append("paper_enter_missing_final_trade_score")
    if decision_type == "PAPER_ENTER" and not checklist_status_present:
        score -= 10
        warnings.append("paper_enter_missing_checklist_status")
    if ticker and ticker_counts[ticker] > 1 and not _safe_text(row.get("context_summary")):
        score -= 10
        warnings.append("repeated_ticker_without_context_note")
        recommendations.append("explain_repeated_ticker_review")

    score = _bounded(score)
    return {
        "reason_present": reason_present,
        "post_review_present": post_review_present,
        "followup_plan_present": followup_present,
        "checklist_aligned": checklist_aligned,
        "no_real_order_confirmed": no_real_order_confirmed,
        "decision_quality_score": score,
        "decision_quality_bucket": _score_bucket(score),
        "quality_warnings": ";".join(warnings),
        "quality_recommendations": ";".join(recommendations),
    }


def _empty_row_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=CSV_COLUMNS)


def collect_quality(root: Path = ROOT) -> tuple[dict, pd.DataFrame]:
    data_dir = root / "data"
    reports = root / "reports"
    decisions = _load_csv(data_dir / "gui_operational_decisions.csv")
    sessions = _load_csv(data_dir / "gui_supervised_sessions.csv")
    checklists = _load_csv(data_dir / "gui_daily_operating_checklists.csv")
    actions = _load_csv(data_dir / "ui_action_log.csv")
    _load_csv(data_dir / "paper_trading_journal.csv")
    post_session = _load_json(reports / "gui_post_session_review_latest.json")
    cycle = _load_json(reports / "paper_trading_cycle_audit_latest.json")
    outcome = _load_json(reports / "trade_outcome_analytics_latest.json")
    calibration = _load_json(reports / "calibration_recommendations_latest.json")

    if decisions.empty:
        rows = _empty_row_frame()
        summary = _summary_from_rows(
            rows,
            decisions=pd.DataFrame(),
            sessions=sessions,
            checklists=checklists,
            actions=actions,
            post_session=post_session,
            cycle=cycle,
            outcome=outcome,
            calibration=calibration,
        )
        return summary, rows

    for column in [
        "decision_id",
        "decision_date",
        "ticker",
        "journal_id",
        "decision_type",
        "decision_status",
        "signal",
        "recommendation",
        "quote_status",
        "execution_quote_quality",
        "final_trade_score",
        "checklist_status",
        "reason",
        "followup_plan",
        "checklist_aligned",
        "no_real_order_confirmed",
        "post_session_review_status",
        "lesson_learned",
        "context_summary",
    ]:
        if column not in decisions.columns:
            decisions[column] = ""

    ticker_counts = Counter(
        value
        for value in decisions["ticker"].fillna("").astype(str).str.upper().tolist()
        if value
    )
    rows: list[dict] = []
    for _, series in decisions.iterrows():
        source = series.to_dict()
        quality = _quality_for_row(source, ticker_counts)
        row = {column: _safe_text(source.get(column)) for column in CSV_COLUMNS}
        row.update(quality)
        rows.append(row)
    row_df = pd.DataFrame(rows, columns=CSV_COLUMNS)
    summary = _summary_from_rows(
        row_df,
        decisions=decisions,
        sessions=sessions,
        checklists=checklists,
        actions=actions,
        post_session=post_session,
        cycle=cycle,
        outcome=outcome,
        calibration=calibration,
    )
    return summary, row_df


def _summary_from_rows(
    rows: pd.DataFrame,
    *,
    decisions: pd.DataFrame,
    sessions: pd.DataFrame,
    checklists: pd.DataFrame,
    actions: pd.DataFrame,
    post_session: dict,
    cycle: dict,
    outcome: dict,
    calibration: dict,
) -> dict:
    total = int(len(rows))
    types = decisions.get("decision_type", pd.Series(dtype=str)).astype(str).str.upper() if not decisions.empty else pd.Series(dtype=str)
    statuses = decisions.get("decision_status", pd.Series(dtype=str)).astype(str).str.upper() if not decisions.empty else pd.Series(dtype=str)
    warnings_count = 0
    global_score = 100.0
    if total:
        scores = pd.to_numeric(rows["decision_quality_score"], errors="coerce").fillna(0)
        global_score = _bounded(float(scores.mean()))
        warnings_count = int(rows["quality_warnings"].astype(str).str.strip().ne("").sum())

    lessons = decisions.get("lesson_learned", pd.Series(dtype=str)).astype(str).str.strip() if not decisions.empty else pd.Series(dtype=str)
    required_pending = 0
    checklist_completion_rate = 100.0
    if not checklists.empty and {"status", "required"}.issubset(checklists.columns):
        required = checklists["required"].astype(str).str.lower().isin({"true", "1", "yes"})
        pending = checklists["status"].astype(str).str.upper().eq("PENDING")
        required_pending = int((required & pending).sum())
        checklist_completion_rate = _ratio_score(int(checklists["status"].astype(str).str.upper().eq("DONE").sum()), len(checklists))

    sessions_reviewed = 0
    if not sessions.empty and "status" in sessions.columns:
        sessions_reviewed = int(sessions["status"].astype(str).str.upper().eq("CLOSED").sum())

    action_consistency = "PASS"
    if total and not actions.empty and "action_log_id" in decisions.columns:
        decision_action_ids = set(decisions["action_log_id"].astype(str).str.strip()) - {""}
        if decision_action_ids and "action_log_id" in actions.columns:
            action_ids = set(actions["action_log_id"].astype(str).str.strip()) - {""}
            if decision_action_ids - action_ids:
                action_consistency = "WARN_MISSING_ACTION_REFS"

    components = _component_scores(rows, decisions)
    recommendations = _observational_recommendations(rows, total)
    return {
        "status": "PASS" if warnings_count == 0 else "WARN",
        "notice": NOTICE,
        "manual_review_only": True,
        "total_decisions": total,
        "decisions_by_type": dict(Counter(types.tolist())),
        "decisions_by_status": dict(Counter(statuses.tolist())),
        "paper_watch_count": int(types.eq("PAPER_WATCH").sum()) if total else 0,
        "paper_enter_count": int(types.eq("PAPER_ENTER").sum()) if total else 0,
        "skip_count": int(types.eq("SKIP").sum()) if total else 0,
        "blocked_count": int(types.eq("BLOCKED").sum()) if total else 0,
        "needs_recheck_count": int(types.eq("NEEDS_RECHECK").sum()) if total else 0,
        "decisions_without_reason": _count_false(rows, "reason_present"),
        "decisions_without_post_review": _count_false(rows, "post_review_present"),
        "decisions_without_followup_plan": _count_false(rows, "followup_plan_present"),
        "decisions_not_checklist_aligned": _count_false(rows, "checklist_aligned"),
        "decisions_missing_no_real_order_confirmation": _count_false(rows, "no_real_order_confirmed"),
        "decisions_with_low_quote_quality": _count_value(rows, "execution_quote_quality", "LOW"),
        "paper_enter_with_low_quote_quality": _count_type_and_value(rows, "PAPER_ENTER", "execution_quote_quality", "LOW"),
        "paper_enter_without_final_trade_score": _paper_enter_missing(rows, "final_trade_score"),
        "paper_enter_without_checklist_status": _paper_enter_missing(rows, "checklist_status"),
        "repeated_tickers_count": _repeated_ticker_count(decisions),
        "lessons_added_count": int(lessons.ne("").sum()) if total else 0,
        "sessions_reviewed_count": sessions_reviewed,
        "checklist_completion_rate": checklist_completion_rate,
        "required_checklist_pending_count": required_pending,
        "gui_action_log_consistency": action_consistency,
        "decision_quality_score": global_score,
        "decision_quality_bucket": _score_bucket(global_score),
        "quality_warnings_count": warnings_count,
        "components": components,
        "observational_recommendations": recommendations,
        "post_session_status": post_session.get("status", "MISSING"),
        "paper_cycle_status": cycle.get("status", "MISSING"),
        "outcome_analytics_status": outcome.get("status", "MISSING"),
        "calibration_recommendations_status": calibration.get("status", "MISSING"),
    }


def _component_scores(rows: pd.DataFrame, decisions: pd.DataFrame) -> dict:
    total = len(rows)
    return {
        "reason_completeness_score": _ratio_score(total - _count_false(rows, "reason_present"), total),
        "checklist_alignment_score": _ratio_score(total - _count_false(rows, "checklist_aligned"), total),
        "post_review_score": _ratio_score(total - _count_false(rows, "post_review_present"), total),
        "quote_discipline_score": _ratio_score(total - _count_value(rows, "execution_quote_quality", "LOW"), total),
        "followup_plan_score": _ratio_score(total - _count_false(rows, "followup_plan_present"), total),
        "no_real_order_discipline_score": _ratio_score(total - _count_false(rows, "no_real_order_confirmed"), total),
        "lesson_capture_score": _ratio_score(
            int(decisions.get("lesson_learned", pd.Series(dtype=str)).astype(str).str.strip().ne("").sum())
            if not decisions.empty
            else 0,
            total,
        ),
    }


def _count_false(rows: pd.DataFrame, column: str) -> int:
    if rows.empty or column not in rows.columns:
        return 0
    return int(~rows[column].astype(bool).sum()) if False else int(rows[column].astype(str).str.lower().isin({"false", "0", ""}).sum())


def _count_value(rows: pd.DataFrame, column: str, value: str) -> int:
    if rows.empty or column not in rows.columns:
        return 0
    return int(rows[column].astype(str).str.upper().eq(value).sum())


def _count_type_and_value(rows: pd.DataFrame, decision_type: str, column: str, value: str) -> int:
    if rows.empty:
        return 0
    return int(
        (
            rows["decision_type"].astype(str).str.upper().eq(decision_type)
            & rows[column].astype(str).str.upper().eq(value)
        ).sum()
    )


def _paper_enter_missing(rows: pd.DataFrame, column: str) -> int:
    if rows.empty or column not in rows.columns:
        return 0
    return int(
        (
            rows["decision_type"].astype(str).str.upper().eq("PAPER_ENTER")
            & rows[column].astype(str).str.strip().eq("")
        ).sum()
    )


def _repeated_ticker_count(decisions: pd.DataFrame) -> int:
    if decisions.empty or "ticker" not in decisions.columns:
        return 0
    counts = decisions["ticker"].astype(str).str.upper().replace("", pd.NA).dropna().value_counts()
    return int((counts > 1).sum())


def _observational_recommendations(rows: pd.DataFrame, total: int) -> list[str]:
    recommendations: list[str] = []
    if total == 0:
        return ["No decisions recorded yet; continue collecting operator evidence."]
    if _count_false(rows, "reason_present"):
        recommendations.append("Review decisions missing reasons before relying on the session notes.")
    if _count_false(rows, "post_review_present"):
        recommendations.append("Complete post-session review for open decisions.")
    if _count_type_and_value(rows, "PAPER_ENTER", "execution_quote_quality", "LOW"):
        recommendations.append("Monitor paper-enter decisions made with low quote quality.")
    if _count_false(rows, "checklist_aligned"):
        recommendations.append("Review checklist alignment for non-aligned decisions.")
    if not recommendations:
        recommendations.append("Maintain current operating discipline and keep adding lessons.")
    return recommendations


def build_markdown(summary: dict, rows: pd.DataFrame) -> str:
    lines = [
        "# Analista - GUI decision quality review",
        "",
        "## Executive Summary",
        "",
        f"- status: {summary.get('status')}",
        f"- total_decisions: {summary.get('total_decisions')}",
        f"- decision_quality_score: {summary.get('decision_quality_score')}",
        f"- decision_quality_bucket: {summary.get('decision_quality_bucket')}",
        f"- quality_warnings_count: {summary.get('quality_warnings_count')}",
        f"- notice: {NOTICE}",
        "",
        "## Components",
        "",
    ]
    for key, value in (summary.get("components", {}) or {}).items():
        lines.append(f"- {key}: {value}")

    problem_rows = rows[rows["quality_warnings"].astype(str).str.strip().ne("")] if not rows.empty else rows
    paper_enter_rows = rows[rows["decision_type"].astype(str).str.upper().eq("PAPER_ENTER")] if not rows.empty else rows
    lines.extend(["", "## Problematic Decisions", ""])
    lines.extend(_table_lines(problem_rows, ["decision_id", "ticker", "decision_type", "decision_quality_score", "quality_warnings"]))
    lines.extend(["", "## PAPER_ENTER Decisions", ""])
    lines.extend(_table_lines(paper_enter_rows, ["decision_id", "ticker", "quote_status", "execution_quote_quality", "decision_quality_score"]))
    lines.extend(["", "## Top Recurrent Warnings", ""])
    warning_counter: Counter[str] = Counter()
    if not rows.empty:
        for text in rows["quality_warnings"].astype(str):
            warning_counter.update(item for item in text.split(";") if item)
    if warning_counter:
        for warning, count in warning_counter.most_common(10):
            lines.append(f"- {warning}: {count}")
    else:
        lines.append("- none")
    lines.extend(["", "## Observational Recommendations", ""])
    lines.extend(f"- {item}" for item in summary.get("observational_recommendations", []))
    lines.extend(["", "## Guardrails", "", "- observational only; no automatic trading changes"])
    return "\n".join(lines)


def _table_lines(df: pd.DataFrame, columns: list[str]) -> list[str]:
    if df.empty:
        return ["- none"]
    available = [column for column in columns if column in df.columns]
    lines = ["|" + "|".join(available) + "|", "|" + "|".join(["---"] * len(available)) + "|"]
    for _, row in df.head(20).iterrows():
        lines.append("|" + "|".join(_safe_text(row.get(column)).replace("|", "/") for column in available) + "|")
    return lines


def save_review(
    *,
    root: Path = ROOT,
    json_out: Path | None = None,
    markdown_out: Path | None = None,
    csv_out: Path | None = None,
) -> dict:
    summary, rows = collect_quality(root=root)
    reports = root / "reports"
    json_out = json_out or reports / "gui_decision_quality_review_latest.json"
    markdown_out = markdown_out or reports / "gui_decision_quality_review_latest.md"
    csv_out = csv_out or reports / "gui_decision_quality_review_latest.csv"
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(csv_out, index=False)
    json_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_markdown(summary, rows), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Evalúa calidad observacional de decisiones GUI paper-only.")
    parser.add_argument("--json-out", default="")
    parser.add_argument("--markdown-out", default="")
    parser.add_argument("--csv-out", default="")
    args = parser.parse_args()
    try:
        result = save_review(
            json_out=Path(args.json_out) if args.json_out else None,
            markdown_out=Path(args.markdown_out) if args.markdown_out else None,
            csv_out=Path(args.csv_out) if args.csv_out else None,
        )
    except Exception as exc:
        result = {"status": "FAIL", "message": f"controlled_error:{type(exc).__name__}", "notice": NOTICE}
    print("=== ANALISTA GUI DECISION QUALITY REVIEW ===")
    print(f"Status: {result.get('status')}")
    print(f"Total decisions: {result.get('total_decisions', 0)}")
    print(f"Decision quality score: {result.get('decision_quality_score', '')}")
    print(f"Decision quality bucket: {result.get('decision_quality_bucket', '')}")
    print(f"Notice: {NOTICE}")
    return 0 if result.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
