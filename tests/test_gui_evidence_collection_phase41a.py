from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Legacy manual GUI evidence collection flow removed from active product.")

import hashlib
from pathlib import Path

import pandas as pd

from tools import gui_evidence_collection_audit as audit
from tools import gui_evidence_collection_window as window


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def test_imports_without_error() -> None:
    assert window.NOTICE == "observational only; no automatic trading changes"


def test_default_execution_generates_outputs(tmp_path: Path) -> None:
    result = window.save_window(root=tmp_path)

    assert result["status"] == "WARN"
    assert (tmp_path / "reports" / "gui_evidence_collection_window_latest.json").exists()
    assert (tmp_path / "reports" / "gui_evidence_collection_window_latest.md").exists()
    assert (tmp_path / "reports" / "gui_evidence_collection_window_latest.csv").exists()
    assert (tmp_path / "data" / "gui_evidence_collection_windows.csv").exists()


def test_works_without_prior_data_and_empty_sessions(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    pd.DataFrame(columns=["session_id", "session_date", "status"]).to_csv(
        data / "gui_supervised_sessions.csv",
        index=False,
    )

    result = window.save_window(root=tmp_path)

    assert result["sessions_count"] == 0
    assert result["readiness_status"] == "INSUFFICIENT_SAMPLE"


def test_score_range_and_bucket_assignment() -> None:
    assert window._readiness_bucket(90) == "A_READY_FOR_REVIEW"
    assert window._readiness_bucket(75) == "B_ALMOST_READY"
    assert window._readiness_bucket(60) == "C_NEEDS_MORE_EVIDENCE"
    assert window._readiness_bucket(40) == "D_NOT_READY"


def test_collect_more_evidence_with_progress_but_small_sample(tmp_path: Path) -> None:
    _write_sessions(tmp_path, [{"session_id": "S1", "session_date": "2026-06-14", "status": "CLOSED"}])
    _write_decisions(
        tmp_path,
        [
            {
                "decision_id": "D1",
                "decision_date": "2026-06-14",
                "decision_type": "PAPER_ENTER",
                "reason": "paper evidence",
                "post_session_review_status": "REVIEWED",
                "no_real_order_confirmed": "True",
                "no_real_order_notice": "paper trading only; no real order",
            }
        ],
    )
    _write_quality(tmp_path, 82)
    _write_weekly(tmp_path, 80)

    result = window.save_window(root=tmp_path)

    assert result["readiness_status"] == "COLLECT_MORE_EVIDENCE"
    assert result["calibration_readiness_score"] >= 0
    assert result["calibration_readiness_score"] <= 100


def test_not_ready_guardrail_failure(tmp_path: Path) -> None:
    _write_sessions(tmp_path, [{"session_id": "S1", "session_date": "2026-06-14", "status": "CLOSED"}])
    _write_decisions(
        tmp_path,
        [
            {
                "decision_id": "D2",
                "decision_date": "2026-06-14",
                "decision_type": "PAPER_ENTER",
                "reason": "paper evidence",
                "post_session_review_status": "REVIEWED",
                "quote_status": "STALE_POSSIBLE",
                "execution_quote_quality": "LOW",
                "no_real_order_confirmed": "False",
            }
        ],
    )
    _write_quality(tmp_path, 80)
    _write_weekly(tmp_path, 80)

    result = window.save_window(root=tmp_path)

    assert result["guardrail_violations_count"] >= 3
    assert result["readiness_status"] == "NOT_READY_GUARDRAIL_FAILURE"


def test_detects_missing_reason_and_post_review(tmp_path: Path) -> None:
    _write_decisions(
        tmp_path,
        [
            {
                "decision_id": "D3",
                "decision_date": "2026-06-14",
                "decision_type": "PAPER_WATCH",
                "reason": "",
                "post_session_review_status": "NOT_REVIEWED",
                "no_real_order_confirmed": "True",
                "no_real_order_notice": "paper trading only; no real order",
            }
        ],
    )

    result = window.save_window(root=tmp_path)

    assert result["decisions_without_reason"] == 1
    assert result["decisions_without_post_review"] == 1


def test_calculates_checklist_completion_rate(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    pd.DataFrame(
        [
            {"checklist_id": "C1", "checklist_date": "2026-06-14", "status": "DONE"},
            {"checklist_id": "C1", "checklist_date": "2026-06-14", "status": "PENDING"},
        ]
    ).to_csv(data / "gui_daily_operating_checklists.csv", index=False)

    result = window.save_window(root=tmp_path)

    assert result["checklist_completion_rate"] == 0.5


def test_uses_avg_decision_quality_score_from_report(tmp_path: Path) -> None:
    _write_decisions(
        tmp_path,
        [
            {
                "decision_id": "D4",
                "decision_date": "2026-06-14",
                "decision_type": "PAPER_WATCH",
                "reason": "watch",
                "post_session_review_status": "REVIEWED",
                "no_real_order_confirmed": "True",
                "no_real_order_notice": "paper trading only; no real order",
            }
        ],
    )
    _write_quality(tmp_path, 77)

    result = window.save_window(root=tmp_path)

    assert result["avg_decision_quality_score"] == 77


def test_does_not_modify_protected_inputs(tmp_path: Path) -> None:
    _write_decisions(
        tmp_path,
        [
            {
                "decision_id": "D5",
                "decision_date": "2026-06-14",
                "decision_type": "SKIP",
                "reason": "skip",
                "post_session_review_status": "REVIEWED",
                "no_real_order_confirmed": "True",
            }
        ],
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

    window.save_window(root=tmp_path)

    assert before["decisions"] == _sha(tmp_path / "data" / "gui_operational_decisions.csv")
    assert before["journal"] == _sha(journal)
    assert before["outcomes"] == _sha(outcomes)


def test_source_has_no_execution_or_p0_literals() -> None:
    source = Path(window.__file__).read_text(encoding="utf-8")

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
    assert result["window_reports_generated"] is True
    assert result["manual_review_only"] is True
    assert result["paper_trading_only"] is True
    assert (tmp_path / "reports" / "gui_evidence_collection_audit_latest.json").exists()
    assert (tmp_path / "reports" / "gui_evidence_collection_audit_latest.md").exists()


def _write_sessions(tmp_path: Path, rows: list[dict]) -> None:
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(data / "gui_supervised_sessions.csv", index=False)


def _write_decisions(tmp_path: Path, rows: list[dict]) -> None:
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(data / "gui_operational_decisions.csv", index=False)


def _write_quality(tmp_path: Path, score: int) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "gui_decision_quality_review_latest.json").write_text(
        f'{{"decision_quality_score": {score}}}',
        encoding="utf-8",
    )


def _write_weekly(tmp_path: Path, score: int) -> None:
    data = tmp_path / "data"
    reports = tmp_path / "reports"
    data.mkdir(exist_ok=True)
    reports.mkdir(exist_ok=True)
    pd.DataFrame(
        [
            {
                "review_id": "W1",
                "review_start_date": "2026-06-08",
                "review_end_date": "2026-06-14",
                "weekly_operational_score": str(score),
            }
        ]
    ).to_csv(data / "gui_weekly_operational_reviews.csv", index=False)
    (reports / "gui_weekly_operational_review_latest.json").write_text(
        f'{{"weekly_operational_score": {score}}}',
        encoding="utf-8",
    )
