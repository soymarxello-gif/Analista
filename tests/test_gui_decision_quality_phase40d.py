from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from tools import gui_decision_quality_audit as audit
from tools import gui_decision_quality_review as review


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def test_imports_without_error() -> None:
    assert review.NOTICE == "observational only; no automatic trading changes"


def test_default_generates_outputs_without_decisions(tmp_path: Path) -> None:
    result = review.save_review(root=tmp_path)

    assert result["status"] == "PASS"
    assert result["total_decisions"] == 0
    assert (tmp_path / "reports" / "gui_decision_quality_review_latest.json").exists()
    assert (tmp_path / "reports" / "gui_decision_quality_review_latest.md").exists()
    assert (tmp_path / "reports" / "gui_decision_quality_review_latest.csv").exists()


def test_empty_decisions_file_is_controlled(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    pd.DataFrame(columns=["decision_id"]).to_csv(data / "gui_operational_decisions.csv", index=False)

    result = review.save_review(root=tmp_path)

    assert result["status"] == "PASS"
    assert result["total_decisions"] == 0


def test_detects_missing_reason_and_post_review(tmp_path: Path) -> None:
    _write_decisions(
        tmp_path,
        [
            {
                "decision_id": "D1",
                "decision_date": "2026-06-14",
                "decision_type": "PAPER_WATCH",
                "decision_status": "RECORDED",
                "reason": "",
                "post_session_review_status": "NOT_REVIEWED",
                "no_real_order_confirmed": "True",
            }
        ],
    )

    result = review.save_review(root=tmp_path)

    assert result["status"] == "WARN"
    assert result["decisions_without_reason"] == 1
    assert result["decisions_without_post_review"] == 1


def test_detects_paper_enter_quote_discipline_failures(tmp_path: Path) -> None:
    _write_decisions(
        tmp_path,
        [
            {
                "decision_id": "D2",
                "decision_date": "2026-06-14",
                "ticker": "AAA",
                "decision_type": "PAPER_ENTER",
                "decision_status": "RECORDED",
                "reason": "paper validation",
                "post_session_review_status": "REVIEWED",
                "followup_plan": "watch",
                "quote_status": "STALE_POSSIBLE",
                "execution_quote_quality": "LOW",
                "no_real_order_confirmed": "True",
            }
        ],
    )

    result, rows = review.collect_quality(root=tmp_path)

    assert result["paper_enter_count"] == 1
    assert result["paper_enter_with_low_quote_quality"] == 1
    assert rows.iloc[0]["decision_quality_score"] < 85
    assert "paper_enter_low_quote_quality" in rows.iloc[0]["quality_warnings"]


def test_score_between_zero_and_one_hundred_and_bucket_assignment(tmp_path: Path) -> None:
    _write_decisions(
        tmp_path,
        [
            {
                "decision_id": "D3",
                "decision_date": "2026-06-14",
                "decision_type": "PAPER_WATCH",
                "decision_status": "REVIEWED",
                "reason": "complete",
                "followup_plan": "monitor",
                "post_session_review_status": "LESSON_ADDED",
                "lesson_learned": "wait",
                "checklist_aligned": "True",
                "no_real_order_confirmed": "True",
                "execution_quote_quality": "HIGH",
            }
        ],
    )

    result = review.save_review(root=tmp_path)

    assert 0 <= result["decision_quality_score"] <= 100
    assert result["decision_quality_bucket"] == "A_DISCIPLINED"


def test_does_not_modify_inputs(tmp_path: Path) -> None:
    _write_decisions(
        tmp_path,
        [
            {
                "decision_id": "D4",
                "decision_type": "SKIP",
                "reason": "skip",
                "no_real_order_confirmed": "True",
            }
        ],
    )
    journal = tmp_path / "data" / "paper_trading_journal.csv"
    outcomes = tmp_path / "data" / "trade_outcomes.csv"
    journal.write_text("journal_id,ticker\nJ1,AAA\n", encoding="utf-8")
    outcomes.write_text("source_journal_id,ticker\nJ1,AAA\n", encoding="utf-8")
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
    assert result["observational_notice_present"] is True
    assert result["manual_review_only"] is True
    assert (tmp_path / "reports" / "gui_decision_quality_audit_latest.json").exists()
    assert (tmp_path / "reports" / "gui_decision_quality_audit_latest.md").exists()


def _write_decisions(tmp_path: Path, rows: list[dict]) -> None:
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(data / "gui_operational_decisions.csv", index=False)
