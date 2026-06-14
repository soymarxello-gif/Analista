from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools import gui_operational_decision_log as log
from tools import gui_operational_decision_log_audit as audit
from tools import gui_post_session_review as review


def test_imports_without_error() -> None:
    assert "PAPER_WATCH" in log.DECISION_TYPES


def test_add_requires_valid_decision_type(tmp_path: Path) -> None:
    result = log.add_decision(root=tmp_path, decision_type="", reason="x")

    assert result["status"] == "FAIL"
    assert result["message"] == "invalid_decision_type"


def test_add_requires_reason_except_session_note(tmp_path: Path) -> None:
    failed = log.add_decision(root=tmp_path, decision_type="PAPER_WATCH", reason="")
    ok = log.add_decision(root=tmp_path, decision_type="SESSION_NOTE", reason="")

    assert failed["status"] == "FAIL"
    assert failed["message"] == "reason_required"
    assert ok["status"] == "PASS"


def test_add_creates_csv_without_reports(tmp_path: Path) -> None:
    result = log.add_decision(
        root=tmp_path,
        decision_type="PAPER_WATCH",
        ticker="TEST",
        reason="paper-only validation",
    )

    assert result["status"] == "PASS"
    assert (tmp_path / "data" / "gui_operational_decisions.csv").exists()
    assert (tmp_path / "reports" / "gui_operational_decision_log_latest.json").exists()
    df = pd.read_csv(tmp_path / "data" / "gui_operational_decisions.csv")
    assert df.iloc[0]["ticker"] == "TEST"
    assert df.iloc[0]["no_real_order_confirmed"] is True or str(df.iloc[0]["no_real_order_confirmed"]) == "True"


def test_add_enriches_from_manual_review_top(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "setup_type": "PULLBACK",
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "final_trade_score": "77.5",
            }
        ]
    ).to_csv(reports / "manual_review_top.csv", index=False)

    log.add_decision(root=tmp_path, decision_type="PAPER_WATCH", ticker="AAA", reason="watch only")
    df = pd.read_csv(tmp_path / "data" / "gui_operational_decisions.csv")

    assert df.iloc[0]["signal"] == "WATCHLIST"
    assert df.iloc[0]["recommendation"] == "WATCHLIST_MONITOR"
    assert df.iloc[0]["setup_type"] == "PULLBACK"
    assert df.iloc[0]["quote_status"] == "VALID"


def test_list_today_summary_no_decisions_is_controlled(tmp_path: Path) -> None:
    result = log.save_summary(root=tmp_path)

    assert result["status"] == "PASS"
    assert result["decisions_today"] == 0


def test_review_requires_valid_decision_id(tmp_path: Path) -> None:
    result = log.review_decision(root=tmp_path, decision_id="missing", outcome_note="x")

    assert result["status"] == "FAIL"
    assert result["message"] == "decision_id_not_found"


def test_review_adds_note_and_lesson(tmp_path: Path) -> None:
    added = log.add_decision(root=tmp_path, decision_type="PAPER_WATCH", ticker="AAA", reason="watch")
    decision_id = added["decision_id"]

    result = log.review_decision(
        root=tmp_path,
        decision_id=decision_id,
        outcome_note="worked as expected",
        lesson="wait for spread confirmation",
    )
    df = pd.read_csv(tmp_path / "data" / "gui_operational_decisions.csv")

    assert result["status"] == "PASS"
    assert df.iloc[0]["post_session_review_note"] == "worked as expected"
    assert df.iloc[0]["lesson_learned"] == "wait for spread confirmation"
    assert df.iloc[0]["post_session_review_status"] == "LESSON_ADDED"


def test_summary_generates_json_and_markdown(tmp_path: Path) -> None:
    log.add_decision(root=tmp_path, decision_type="PAPER_WATCH", ticker="AAA", reason="watch")
    result = log.save_summary(root=tmp_path)

    assert result["decisions_today"] == 1
    assert (tmp_path / "reports" / "gui_operational_decision_log_latest.json").exists()
    assert (tmp_path / "reports" / "gui_operational_decision_log_latest.md").exists()


def test_post_session_review_generates_outputs_and_detects_gaps(tmp_path: Path) -> None:
    log.add_decision(root=tmp_path, decision_type="SESSION_NOTE", reason="")
    result = review.save_review(root=tmp_path)

    assert result["status"] == "WARN"
    assert result["decisions_without_reason"] == 1
    assert result["decisions_without_post_review"] == 1
    assert (tmp_path / "reports" / "gui_post_session_review_latest.json").exists()
    assert (tmp_path / "reports" / "gui_post_session_review_latest.md").exists()


def test_audit_generates_json_and_markdown(tmp_path: Path) -> None:
    result = audit.run_audit(root=tmp_path)

    assert result["status"] == "PASS"
    assert result["tool_exists"] is True
    assert result["post_session_review_exists"] is True
    assert result["data_file_can_be_created"] is True
    assert result["decision_log_reports_generated"] is True
    assert result["post_session_reports_generated"] is True
    assert (tmp_path / "reports" / "gui_operational_decision_log_audit_latest.json").exists()
    assert (tmp_path / "reports" / "gui_operational_decision_log_audit_latest.md").exists()


def test_sources_have_no_execution_or_p0_literals() -> None:
    source = Path(log.__file__).read_text(encoding="utf-8") + Path(review.__file__).read_text(encoding="utf-8")

    assert "shell=True" not in source
    assert "send_order" not in source
    assert "place_order" not in source
    assert "buy_order" not in source
    assert "sell_order" not in source
    assert "ibapi" not in source.lower()
    assert "alpaca" not in source.lower()
    assert "_".join(["BUY", "SETUP", "ACTIVE"]) not in source
    assert "_".join(["TRIGGER", "CONFIRMED"]) not in source
