from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Legacy manual paper trading flow removed; simple_candidate_posttest is the active feedback loop.")

import json
from pathlib import Path

import pandas as pd

from tools import daily_validation
from tools.daily_operator_index import build_daily_operator_index_markdown
from tools.daily_run_manifest import KEY_REPORT_PATHS, KEY_SCRIPT_PATHS, collect_daily_run_manifest
from tools.paper_trading_journal import (
    JOURNAL_COLUMNS,
    build_markdown,
    build_summary_payload,
    ensure_journal,
    import_candidates_today,
    save_paper_trading_journal,
    set_manual_decision,
)


def _candidate(**overrides) -> dict:
    row = {
        "ticker": "AAA",
        "checklist_status": "REVIEW_MANUALLY",
        "signal": "WATCHLIST",
        "recommendation": "WATCHLIST_MONITOR",
        "setup_type": "BREAKOUT",
        "sector": "Technology",
        "industry": "Software",
        "final_trade_score": 82,
        "checklist_score": 80,
        "institutional_score": 60,
        "options_score": 0.55,
        "options_bias": "NEUTRAL_WITH_DATA",
        "options_confidence": "HIGH",
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
        "actionable_entry": 100,
        "actionable_stop": 95,
        "actionable_target": 112,
        "rr": 2.4,
    }
    row.update(overrides)
    return row


def _write_cards_json(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"status": "PASS", "rows": len(rows), "cards": rows}), encoding="utf-8")


def test_missing_journal_creates_headers(tmp_path: Path):
    journal_path = tmp_path / "data" / "paper_trading_journal.csv"

    df = ensure_journal(journal_path)

    assert journal_path.exists()
    assert list(df.columns) == JOURNAL_COLUMNS
    assert df.empty


def test_import_candidates_generates_pending_review(tmp_path: Path):
    journal = ensure_journal(tmp_path / "data" / "paper_trading_journal.csv")

    out, imported = import_candidates_today(
        journal,
        pd.DataFrame([_candidate()]),
        run_date="2026-06-12",
        source_report="reports/trade_candidate_cards_latest.json",
    )

    assert imported == 1
    assert out.iloc[0]["ticker"] == "AAA"
    assert out.iloc[0]["manual_decision"] == "PENDING_REVIEW"
    assert out.iloc[0]["followup_status"] == "OPEN_MONITORING"


def test_reimport_same_day_does_not_duplicate_ticker(tmp_path: Path):
    journal = ensure_journal(tmp_path / "data" / "paper_trading_journal.csv")
    candidates = pd.DataFrame([_candidate()])

    out, imported_first = import_candidates_today(
        journal,
        candidates,
        run_date="2026-06-12",
        source_report="cards",
    )
    out, imported_second = import_candidates_today(
        out,
        candidates,
        run_date="2026-06-12",
        source_report="cards",
    )

    assert imported_first == 1
    assert imported_second == 0
    assert len(out) == 1


def test_blocked_candidate_cannot_paper_enter(tmp_path: Path):
    journal = ensure_journal(tmp_path / "data" / "paper_trading_journal.csv")
    journal, _ = import_candidates_today(
        journal,
        pd.DataFrame([_candidate(checklist_status="BLOCKED")]),
        run_date="2026-06-12",
        source_report="cards",
    )

    out, result = set_manual_decision(
        journal,
        ticker="AAA",
        decision="PAPER_ENTER",
        reason="manual paper test",
        entry=100,
        stop=95,
        target=112,
        run_date="2026-06-12",
    )

    assert result["status"] == "FAIL"
    assert result["error"] == "blocked_candidate_cannot_paper_enter"
    assert out.iloc[0]["manual_decision"] == "BLOCKED"


def test_needs_live_quote_recheck_requires_explicit_confirmation_for_paper_enter(tmp_path: Path):
    journal = ensure_journal(tmp_path / "data" / "paper_trading_journal.csv")
    journal, _ = import_candidates_today(
        journal,
        pd.DataFrame([_candidate(checklist_status="NEEDS_LIVE_QUOTE_RECHECK")]),
        run_date="2026-06-12",
        source_report="cards",
    )

    _out, result = set_manual_decision(
        journal,
        ticker="AAA",
        decision="PAPER_ENTER",
        reason="manual paper test",
        entry=100,
        stop=95,
        target=112,
        run_date="2026-06-12",
    )

    assert result["status"] == "FAIL"
    assert result["error"] == "needs_live_quote_recheck_requires_confirm_live_quote"


def test_set_decision_updates_manual_reason_and_followup(tmp_path: Path):
    journal = ensure_journal(tmp_path / "data" / "paper_trading_journal.csv")
    journal, _ = import_candidates_today(
        journal,
        pd.DataFrame([_candidate()]),
        run_date="2026-06-12",
        source_report="cards",
    )

    out, result = set_manual_decision(
        journal,
        ticker="AAA",
        decision="PAPER_WATCH",
        reason="monitor volume confirmation",
        run_date="2026-06-12",
    )

    assert result["status"] == "PASS"
    assert out.iloc[0]["manual_decision"] == "PAPER_WATCH"
    assert out.iloc[0]["manual_decision_reason"] == "monitor volume confirmation"
    assert out.iloc[0]["followup_status"] == "OPEN_MONITORING"


def test_paper_enter_requires_entry_stop_target(tmp_path: Path):
    journal = ensure_journal(tmp_path / "data" / "paper_trading_journal.csv")
    journal, _ = import_candidates_today(
        journal,
        pd.DataFrame([_candidate()]),
        run_date="2026-06-12",
        source_report="cards",
    )

    _out, result = set_manual_decision(
        journal,
        ticker="AAA",
        decision="PAPER_ENTER",
        reason="manual paper test",
        entry=100,
        stop=None,
        target=112,
        run_date="2026-06-12",
    )

    assert result["status"] == "FAIL"
    assert result["error"] == "paper_enter_requires_entry_stop_target"


def test_save_generates_csv_json_markdown_outputs(tmp_path: Path):
    reports = tmp_path / "reports"
    _write_cards_json(reports / "trade_candidate_cards_latest.json", [_candidate()])

    result = save_paper_trading_journal(
        root=tmp_path,
        journal_path=tmp_path / "data" / "paper_trading_journal.csv",
        cards_json=reports / "trade_candidate_cards_latest.json",
        checklist_csv=reports / "trade_decision_checklist_latest.csv",
        manual_top_csv=reports / "manual_review_top.csv",
        csv_out=reports / "paper_trading_journal_latest.csv",
        json_out=reports / "paper_trading_journal_latest.json",
        markdown_out=reports / "paper_trading_journal_latest.md",
        import_today=True,
        run_date="2026-06-12",
    )

    assert result["status"] == "PASS"
    assert result["rows"] == 1
    assert result["imported_rows"] == 1
    assert (reports / "paper_trading_journal_latest.csv").exists()
    assert (reports / "paper_trading_journal_latest.json").exists()
    assert (reports / "paper_trading_journal_latest.md").exists()


def test_markdown_contains_paper_only_guardrails():
    journal = pd.DataFrame([_candidate(ticker="AAA")])
    journal["run_date"] = "2026-06-12"
    journal["manual_decision"] = "PENDING_REVIEW"
    journal["followup_status"] = "OPEN_MONITORING"
    payload = build_summary_payload(journal)

    text = build_markdown(payload, journal)

    assert "paper trading only; no real order" in text
    assert "No broker connection is used." in text
    assert "signals, scores, config, weights, or thresholds" in text


def test_daily_validation_has_optional_paper_step_after_candidate_cards():
    post_names = [item["name"] for item in daily_validation.POST_SUMMARY_STEPS]

    assert "paper_trading_journal" in post_names
    assert post_names.index("trade_candidate_cards") < post_names.index("paper_trading_journal")

    step = next(item for item in daily_validation.POST_SUMMARY_STEPS if item["name"] == "paper_trading_journal")
    assert step["required"] is False
    assert "tools/paper_trading_journal.py" in step["cmd"]
    assert "--import-today" in step["cmd"]


def test_daily_operator_index_renders_paper_trading_journal_section():
    text = build_daily_operator_index_markdown(
        {
            "generated_at": "2026-06-12T00:00:00",
            "validation_status": "PASS",
            "scan_rows": 1,
            "manual_review_rows": 1,
            "manual_top_rows": 1,
            "open_trades_rows": 0,
            "analytics_rows": 0,
            "trigger_count": 0,
            "watchlist_count": 1,
            "recheck_count": 0,
            "signals": {"WATCHLIST": 1},
            "recommendations": {"WATCHLIST_MONITOR": 1},
            "quote_recheck_priority": {},
            "quality_gate": {"available": False},
            "live_quote_recheck": {"available": False},
            "trade_decision_checklist": {"available": False},
            "trade_candidate_cards": {"available": False},
            "paper_trading_journal": {
                "available": True,
                "status": "PASS",
                "rows": 2,
                "pending_review": 1,
                "paper_watch": 1,
                "paper_enter": 0,
                "blocked": 0,
                "needs_live_quote_recheck": 0,
            },
            "trade_score_calibration": {"available": False},
            "calibration_recommendations": {"available": False},
            "release_readiness": {"available": False},
            "top_candidates": pd.DataFrame(),
            "recheck_candidates": pd.DataFrame(),
            "open_trades": pd.DataFrame(),
            "analytics_overall": pd.DataFrame(),
            "cleanup": {},
            "preflight": {},
            "encoding_audit": {},
            "report_status": [],
        }
    )

    assert "## Paper trading journal" in text
    assert "- pending_review: 1" in text
    assert "reports/paper_trading_journal_latest.md" in text
    assert "no real order" in text


def test_daily_run_manifest_tracks_paper_trading_journal_outputs(tmp_path: Path):
    assert "tools/paper_trading_journal.py" in KEY_SCRIPT_PATHS
    assert "reports/paper_trading_journal_latest.csv" in KEY_REPORT_PATHS
    assert "reports/paper_trading_journal_latest.json" in KEY_REPORT_PATHS
    assert "reports/paper_trading_journal_latest.md" in KEY_REPORT_PATHS

    root = tmp_path
    (root / "tools").mkdir()
    (root / "reports").mkdir()
    for script in KEY_SCRIPT_PATHS:
        path = root / script
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# script\n", encoding="utf-8")
    (root / "reports" / "daily_validation_summary.txt").write_text("Status: PASS\n", encoding="utf-8")
    (root / "reports" / "project_preflight_latest.json").write_text(
        json.dumps({"status": "PASS", "summary": {}}),
        encoding="utf-8",
    )
    (root / "reports" / "reports_cleanup_latest.json").write_text(
        json.dumps({"status": "PASS", "mode": "DRY_RUN"}),
        encoding="utf-8",
    )
    (root / "reports" / "paper_trading_journal_latest.json").write_text(
        json.dumps({"status": "PASS", "rows": 1, "pending_review": 1}),
        encoding="utf-8",
    )

    data = collect_daily_run_manifest(root=root)

    assert data["scan_snapshot"]["paper_trading_journal"]["rows"] == 1


def test_journal_output_does_not_create_disabled_signal_or_trigger_confirmed(tmp_path: Path):
    reports = tmp_path / "reports"
    _write_cards_json(reports / "trade_candidate_cards_latest.json", [_candidate()])
    disabled_signal = "_".join(["BUY", "SETUP", "ACTIVE"])

    result = save_paper_trading_journal(
        root=tmp_path,
        journal_path=tmp_path / "data" / "paper_trading_journal.csv",
        cards_json=reports / "trade_candidate_cards_latest.json",
        checklist_csv=reports / "trade_decision_checklist_latest.csv",
        manual_top_csv=reports / "manual_review_top.csv",
        csv_out=reports / "paper_trading_journal_latest.csv",
        json_out=reports / "paper_trading_journal_latest.json",
        markdown_out=reports / "paper_trading_journal_latest.md",
        import_today=True,
        run_date="2026-06-12",
    )
    text = (reports / "paper_trading_journal_latest.md").read_text(encoding="utf-8")
    payload = json.loads((reports / "paper_trading_journal_latest.json").read_text(encoding="utf-8"))

    assert result["status"] == "PASS"
    assert disabled_signal not in text
    assert "TRIGGER_CONFIRMED" not in text
    assert payload["paper_enter"] == 0
