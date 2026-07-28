from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Legacy manual GUI weekly review flow removed from active product.")

import hashlib
from pathlib import Path

import pandas as pd

from tools import gui_weekly_operational_review as review
from tools import gui_weekly_operational_review_audit as audit


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def test_imports_without_error() -> None:
    assert "observational only" in review.NOTICE
    assert "manual review only" in review.MANUAL_NOTICE


def test_default_execution_generates_json_markdown_csv(tmp_path: Path) -> None:
    result = review.save_review(root=tmp_path)

    assert result["status"] == "WARN"
    assert (tmp_path / "reports" / "gui_weekly_operational_review_latest.json").exists()
    assert (tmp_path / "reports" / "gui_weekly_operational_review_latest.md").exists()
    assert (tmp_path / "reports" / "gui_weekly_operational_review_latest.csv").exists()
    assert (tmp_path / "data" / "gui_weekly_operational_reviews.csv").exists()


def test_works_with_empty_sessions(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    pd.DataFrame(columns=["session_id", "session_date", "status"]).to_csv(
        data / "gui_supervised_sessions.csv",
        index=False,
    )

    result = review.save_review(root=tmp_path)

    assert result["sessions_count"] == 0
    assert result["weekly_recommendation"] == "EXTEND_SAMPLE_SIZE"


def test_score_range_and_bucket_assignment() -> None:
    assert review._review_bucket(90) == "A_READY_FOR_EXTENDED_PAPER"
    assert review._review_bucket(75) == "B_ACCEPTABLE_CONTINUE"
    assert review._review_bucket(60) == "C_NEEDS_PROCESS_REVIEW"
    assert review._review_bucket(40) == "D_NOT_READY"


def test_insufficient_sample_is_not_ready_for_calibration(tmp_path: Path) -> None:
    _write_sessions(tmp_path, [{"session_id": "S1", "session_date": "2026-06-14", "status": "CLOSED"}])
    _write_decisions(
        tmp_path,
        [{"decision_id": "D1", "decision_date": "2026-06-14", "decision_type": "PAPER_ENTER", "reason": "test", "post_session_review_status": "REVIEWED", "no_real_order_confirmed": "True"}],
    )

    result = review.save_review(root=tmp_path)

    assert result["ready_for_calibration_review"] is False
    assert result["weekly_recommendation"] == "EXTEND_SAMPLE_SIZE"


def test_detects_decisions_without_reason_and_post_review(tmp_path: Path) -> None:
    _write_decisions(
        tmp_path,
        [
            {
                "decision_id": "D2",
                "decision_date": "2026-06-14",
                "decision_type": "PAPER_WATCH",
                "reason": "",
                "post_session_review_status": "NOT_REVIEWED",
                "no_real_order_confirmed": "True",
            }
        ],
    )

    result = review.save_review(root=tmp_path)

    assert result["decisions_without_reason"] == 1
    assert result["decisions_without_post_review"] == 1


def test_detects_guardrail_violations(tmp_path: Path) -> None:
    _write_decisions(
        tmp_path,
        [
            {
                "decision_id": "D3",
                "decision_date": "2026-06-14",
                "decision_type": "PAPER_ENTER",
                "reason": "test",
                "post_session_review_status": "REVIEWED",
                "quote_status": "STALE_POSSIBLE",
                "execution_quote_quality": "LOW",
                "no_real_order_confirmed": "False",
            }
        ],
    )

    result = review.save_review(root=tmp_path)

    assert result["guardrail_violations_count"] >= 3
    assert result["weekly_recommendation"] == "EXTEND_SAMPLE_SIZE"


def test_calculates_checklist_completion_rate(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    pd.DataFrame(
        [
            {"checklist_id": "C1", "checklist_date": "2026-06-14", "status": "DONE", "required": "True", "result": "PASS"},
            {"checklist_id": "C1", "checklist_date": "2026-06-14", "status": "PENDING", "required": "True", "result": "WARN"},
        ]
    ).to_csv(data / "gui_daily_operating_checklists.csv", index=False)

    result = review.save_review(root=tmp_path)

    assert result["checklist_completion_rate"] == 0.5
    assert result["required_steps_pending_total"] == 1


def test_uses_decision_quality_score_from_report(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "gui_decision_quality_review_latest.json").write_text(
        '{"decision_quality_score": 82, "decision_quality_bucket": "B_ACCEPTABLE"}',
        encoding="utf-8",
    )
    _write_decisions(
        tmp_path,
        [{"decision_id": "D4", "decision_date": "2026-06-14", "decision_type": "PAPER_WATCH", "reason": "watch", "post_session_review_status": "REVIEWED", "no_real_order_confirmed": "True"}],
    )

    result = review.save_review(root=tmp_path)

    assert result["avg_decision_quality_score"] == 82
    assert result["decision_quality_bucket"] == "B_ACCEPTABLE"


def test_does_not_modify_protected_inputs(tmp_path: Path) -> None:
    _write_decisions(
        tmp_path,
        [{"decision_id": "D5", "decision_date": "2026-06-14", "decision_type": "SKIP", "reason": "skip", "post_session_review_status": "REVIEWED", "no_real_order_confirmed": "True"}],
    )
    journal = tmp_path / "data" / "paper_trading_journal.csv"
    outcomes = tmp_path / "data" / "trade_outcomes.csv"
    journal.write_text("journal_id,ticker,followup_status,outcome_exported\nJ1,AAA,CLOSED_PAPER,False\n", encoding="utf-8")
    outcomes.write_text("source_journal_id,ticker,r_multiple\nJ1,AAA,1.5\n", encoding="utf-8")
    before = {
        "decisions": _sha(tmp_path / "data" / "gui_operational_decisions.csv"),
        "journal": _sha(journal),
        "outcomes": _sha(outcomes),
    }

    review.save_review(root=tmp_path)

    assert before["decisions"] == _sha(tmp_path / "data" / "gui_operational_decisions.csv")
    assert before["journal"] == _sha(journal)
    assert before["outcomes"] == _sha(outcomes)


def test_source_has_no_execution_or_p0_literals() -> None:
    source = Path(review.__file__).read_text(encoding="utf-8")

    assert "shell=True" not in source
    assert "send_order" not in source
    assert "place_order" not in source
    assert "buy_order" not in source
    assert "sell_order" not in source
    assert "ibapi" not in source.lower()
    assert "alpaca" not in source.lower()
    assert "_".join(["BUY", "SETUP", "ACTIVE"]) not in source
    assert "_".join(["TRIGGER", "CONFIRMED"]) not in source


def test_audit_generates_json_and_markdown(tmp_path: Path) -> None:
    result = audit.run_audit(root=tmp_path)

    assert result["status"] == "PASS"
    assert result["tool_exists"] is True
    assert result["review_reports_generated"] is True
    assert result["manual_review_only"] is True
    assert result["paper_trading_only"] is True
    assert (tmp_path / "reports" / "gui_weekly_operational_review_audit_latest.json").exists()
    assert (tmp_path / "reports" / "gui_weekly_operational_review_audit_latest.md").exists()


def _write_sessions(tmp_path: Path, rows: list[dict]) -> None:
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(data / "gui_supervised_sessions.csv", index=False)


def _write_decisions(tmp_path: Path, rows: list[dict]) -> None:
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(data / "gui_operational_decisions.csv", index=False)
