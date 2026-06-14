from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.gui_operational_decision_log import DECISION_COLUMNS, NO_REAL_ORDER_NOTICE, ensure_decisions


def _today() -> str:
    return date.today().isoformat()


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame()


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def collect_review(*, root: Path = ROOT) -> dict:
    decisions_path = root / "data" / "gui_operational_decisions.csv"
    decisions = ensure_decisions(decisions_path)
    today_rows = decisions[decisions["decision_date"].astype(str).eq(_today())].copy() if not decisions.empty else decisions
    actions = _load_csv(root / "data" / "ui_action_log.csv")

    if today_rows.empty:
        return {
            "status": "PASS",
            "decisions_today": 0,
            "decisions_without_post_review": 0,
            "paper_enter_decisions": 0,
            "skip_decisions": 0,
            "needs_recheck_decisions": 0,
            "high_risk_notes": 0,
            "decisions_without_reason": 0,
            "not_checklist_aligned": 0,
            "lessons_added": 0,
            "paper_actions_logged": int(len(actions)),
            "action_log_consistency": "NO_DECISIONS",
            "no_real_order_notice_present": True,
            "manual_review_only": True,
            "decisions": [],
        }

    types = today_rows["decision_type"].astype(str).str.upper()
    reasons = today_rows["reason"].astype(str).str.strip()
    reviews = today_rows["post_session_review_status"].astype(str).str.upper()
    lessons = today_rows["lesson_learned"].astype(str).str.strip()
    risk_notes = today_rows["risk_note"].astype(str).str.lower()
    aligned = today_rows["checklist_aligned"].astype(str).str.lower()
    action_ids = set(today_rows["action_log_id"].astype(str).str.strip()) - {""}
    logged_action_ids = set()
    if not actions.empty and "action_log_id" in actions.columns:
        logged_action_ids = set(actions["action_log_id"].astype(str).str.strip()) - {""}
    missing_action_refs = sorted(action_ids - logged_action_ids)
    status = "WARN" if reasons.eq("").any() or reviews.eq("NOT_REVIEWED").any() or missing_action_refs else "PASS"

    return {
        "status": status,
        "decisions_today": int(len(today_rows)),
        "decisions_without_post_review": int(reviews.eq("NOT_REVIEWED").sum()),
        "paper_enter_decisions": int(types.eq("PAPER_ENTER").sum()),
        "paper_watch_decisions": int(types.eq("PAPER_WATCH").sum()),
        "skip_decisions": int(types.eq("SKIP").sum()),
        "needs_recheck_decisions": int(types.eq("NEEDS_RECHECK").sum()),
        "high_risk_notes": int(risk_notes.str.contains("high|alto|elevado|severe", regex=True).sum()),
        "decisions_without_reason": int(reasons.eq("").sum()),
        "not_checklist_aligned": int(aligned.isin({"false", "no", "0"}).sum()),
        "lessons_added": int(lessons.ne("").sum()),
        "paper_actions_logged": int(len(actions)),
        "action_log_consistency": "WARN_MISSING_ACTION_REFS" if missing_action_refs else "PASS",
        "missing_action_log_refs": missing_action_refs,
        "no_real_order_notice_present": bool(
            today_rows["no_real_order_notice"].astype(str).str.contains("no real order", case=False, regex=False).all()
        ),
        "manual_review_only": True,
        "decisions": today_rows.sort_values("timestamp").to_dict(orient="records"),
    }


def build_markdown(data: dict) -> str:
    lines = [
        "# Analista - GUI post-session review",
        "",
        f"- status: {data.get('status')}",
        f"- decisions_today: {data.get('decisions_today', 0)}",
        f"- decisions_without_post_review: {data.get('decisions_without_post_review', 0)}",
        f"- paper_enter_decisions: {data.get('paper_enter_decisions', 0)}",
        f"- skip_decisions: {data.get('skip_decisions', 0)}",
        f"- needs_recheck_decisions: {data.get('needs_recheck_decisions', 0)}",
        f"- high_risk_notes: {data.get('high_risk_notes', 0)}",
        f"- decisions_without_reason: {data.get('decisions_without_reason', 0)}",
        f"- not_checklist_aligned: {data.get('not_checklist_aligned', 0)}",
        f"- lessons_added: {data.get('lessons_added', 0)}",
        f"- paper_actions_logged: {data.get('paper_actions_logged', 0)}",
        f"- action_log_consistency: {data.get('action_log_consistency', 'UNKNOWN')}",
        f"- no_real_order_notice_present: {data.get('no_real_order_notice_present', False)}",
        "",
        "## Lessons",
        "",
    ]
    lessons = [
        item.get("lesson_learned", "")
        for item in data.get("decisions", []) or []
        if str(item.get("lesson_learned", "")).strip()
    ]
    if lessons:
        lines.extend(f"- {lesson}" for lesson in lessons)
    else:
        lines.append("- No lessons recorded.")
    lines.extend(["", "## Guardrails", "", "- Manual review only.", "- Paper trading only.", "- No real order."])
    return "\n".join(lines)


def save_review(*, root: Path = ROOT, json_out: Path | None = None, markdown_out: Path | None = None) -> dict:
    data = collect_review(root=root)
    reports = root / "reports"
    json_out = json_out or reports / "gui_post_session_review_latest.json"
    markdown_out = markdown_out or reports / "gui_post_session_review_latest.md"
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    markdown_out.write_text(build_markdown(data), encoding="utf-8")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Resume revisión post-sesión GUI paper-only.")
    parser.add_argument("--json-out", default="")
    parser.add_argument("--markdown-out", default="")
    args = parser.parse_args()
    try:
        data = save_review(
            json_out=Path(args.json_out) if args.json_out else None,
            markdown_out=Path(args.markdown_out) if args.markdown_out else None,
        )
    except Exception as exc:
        data = {"status": "FAIL", "message": f"controlled_error:{type(exc).__name__}"}
    print("=== ANALISTA GUI POST-SESSION REVIEW ===")
    print(f"Status: {data.get('status')}")
    print(f"Decisions today: {data.get('decisions_today', 0)}")
    print(f"Without post review: {data.get('decisions_without_post_review', 0)}")
    print(f"Lessons added: {data.get('lessons_added', 0)}")
    print(f"Notice: {NO_REAL_ORDER_NOTICE}")
    return 0 if data.get("status") in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
