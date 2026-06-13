from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools import daily_validation
from tools.daily_operator_index import build_daily_operator_index_markdown
from tools.daily_run_manifest import KEY_REPORT_PATHS, KEY_SCRIPT_PATHS
from tools.paper_trade_close import (
    close_paper_trade,
    list_open_paper_trades,
    save_paper_trade_close_reports,
)


def _journal_row(**overrides) -> dict:
    row = {
        "journal_id": "J-AAA-001",
        "run_date": "2026-06-12",
        "ticker": "AAA",
        "checklist_status": "HIGH_QUALITY_REVIEW",
        "signal": "WATCHLIST",
        "recommendation": "WATCHLIST_MONITOR",
        "setup_type": "PULLBACK",
        "manual_decision": "PAPER_ENTER",
        "followup_status": "ENTERED_PAPER",
        "simulated_entry_price": "100",
        "simulated_stop": "90",
        "simulated_target": "120",
        "final_trade_score": "82",
        "checklist_score": "88",
        "setup_quality_score": "80",
        "institutional_score": "60",
        "options_bias": "NEUTRAL_WITH_DATA",
        "options_confidence": "MEDIUM",
        "no_real_order_notice": "paper trading only; no real order",
    }
    row.update(overrides)
    return row


def _paths(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    journal = tmp_path / "data" / "paper_trading_journal.csv"
    outcomes = tmp_path / "data" / "trade_outcomes.csv"
    csv_out = tmp_path / "reports" / "paper_trade_close_latest.csv"
    json_out = tmp_path / "reports" / "paper_trade_close_latest.json"
    md_out = tmp_path / "reports" / "paper_trade_close_latest.md"
    return journal, outcomes, csv_out, json_out, md_out


def _write_journal(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=list(_journal_row().keys()))
    df.to_csv(path, index=False)


def test_missing_journal_returns_controlled_warning(tmp_path: Path):
    journal, outcomes, csv_out, json_out, md_out = _paths(tmp_path)

    result = save_paper_trade_close_reports(
        root=tmp_path,
        journal_path=journal,
        outcomes_path=outcomes,
        csv_out=csv_out,
        json_out=json_out,
        markdown_out=md_out,
        summary=True,
    )

    assert result["status"] == "WARN"
    assert result["rows"] == 0
    assert result["error"] == "journal_csv_not_found"
    assert csv_out.exists()
    assert json_out.exists()
    assert md_out.exists()


def test_empty_journal_passes_rows_zero(tmp_path: Path):
    journal, outcomes, csv_out, json_out, md_out = _paths(tmp_path)
    _write_journal(journal, [])

    result = save_paper_trade_close_reports(
        root=tmp_path,
        journal_path=journal,
        outcomes_path=outcomes,
        csv_out=csv_out,
        json_out=json_out,
        markdown_out=md_out,
        summary=True,
    )

    assert result["status"] == "PASS"
    assert result["rows"] == 0
    assert result["open_paper_trades"] == 0


def test_list_open_only_includes_paper_enter_or_entered_paper():
    df = pd.DataFrame(
        [
            _journal_row(journal_id="J1", manual_decision="PAPER_ENTER", followup_status=""),
            _journal_row(journal_id="J2", manual_decision="PAPER_WATCH", followup_status="ENTERED_PAPER"),
            _journal_row(journal_id="J3", manual_decision="PAPER_WATCH", followup_status="OPEN_MONITORING"),
        ]
    )

    open_df = list_open_paper_trades(df)

    assert open_df["journal_id"].tolist() == ["J1", "J2"]


def test_close_requires_exit_price():
    df = pd.DataFrame([_journal_row()])

    _, result = close_paper_trade(df, identifier="J-AAA-001", exit_price=None, exit_date=None, reason="OTHER")

    assert result["status"] == "FAIL"
    assert result["error"] == "exit_price_required"


def test_close_requires_reason():
    df = pd.DataFrame([_journal_row()])

    _, result = close_paper_trade(df, identifier="J-AAA-001", exit_price=101, exit_date=None, reason="")

    assert result["status"] == "FAIL"
    assert result["error"] == "close_reason_required"


def test_close_updates_status_and_metrics(tmp_path: Path):
    journal, outcomes, csv_out, json_out, md_out = _paths(tmp_path)
    _write_journal(journal, [_journal_row()])

    result = save_paper_trade_close_reports(
        root=tmp_path,
        journal_path=journal,
        outcomes_path=outcomes,
        csv_out=csv_out,
        json_out=json_out,
        markdown_out=md_out,
        close_identifier="J-AAA-001",
        exit_price="115",
        exit_date="2026-06-13",
        reason="TARGET_REACHED_MANUAL",
    )

    saved = pd.read_csv(journal, dtype=str).fillna("")
    assert result["status"] == "PASS"
    assert saved.loc[0, "followup_status"] == "CLOSED_PAPER"
    assert saved.loc[0, "close_reason"] == "TARGET_REACHED_MANUAL"
    assert float(saved.loc[0, "pnl_pct"]) == 0.15
    assert float(saved.loc[0, "r_multiple"]) == 1.5


def test_r_multiple_blank_when_entry_or_stop_missing():
    df = pd.DataFrame([_journal_row(simulated_stop="")])

    closed_df, result = close_paper_trade(
        df,
        identifier="J-AAA-001",
        exit_price=110,
        exit_date="2026-06-13",
        reason="OTHER",
    )

    assert result["status"] == "PASS"
    assert closed_df.loc[0, "r_multiple"] == ""


def test_non_open_trade_requires_force():
    df = pd.DataFrame(
        [_journal_row(manual_decision="PAPER_WATCH", followup_status="OPEN_MONITORING")]
    )

    _, result = close_paper_trade(
        df,
        identifier="J-AAA-001",
        exit_price=101,
        exit_date="2026-06-13",
        reason="OTHER",
    )

    assert result["status"] == "FAIL"
    assert result["error"] == "paper_trade_not_open_requires_force"


def test_export_outcomes_appends_closed_trade_and_no_duplicates(tmp_path: Path):
    journal, outcomes, csv_out, json_out, md_out = _paths(tmp_path)
    _write_journal(journal, [_journal_row()])

    save_paper_trade_close_reports(
        root=tmp_path,
        journal_path=journal,
        outcomes_path=outcomes,
        csv_out=csv_out,
        json_out=json_out,
        markdown_out=md_out,
        close_identifier="J-AAA-001",
        exit_price="115",
        reason="TARGET_REACHED_MANUAL",
    )

    first_export = save_paper_trade_close_reports(
        root=tmp_path,
        journal_path=journal,
        outcomes_path=outcomes,
        csv_out=csv_out,
        json_out=json_out,
        markdown_out=md_out,
        export_outcomes=True,
    )
    second_export = save_paper_trade_close_reports(
        root=tmp_path,
        journal_path=journal,
        outcomes_path=outcomes,
        csv_out=csv_out,
        json_out=json_out,
        markdown_out=md_out,
        export_outcomes=True,
    )

    outcomes_df = pd.read_csv(outcomes, dtype=str).fillna("")
    saved_journal = pd.read_csv(journal, dtype=str).fillna("")
    assert first_export["exported_outcomes"] == 1
    assert second_export["exported_outcomes"] == 0
    assert len(outcomes_df) == 1
    assert outcomes_df.loc[0, "status"] == "CLOSED"
    assert outcomes_df.loc[0, "source_journal_id"] == "J-AAA-001"
    assert saved_journal.loc[0, "outcome_exported"] == "True"


def test_summary_does_not_modify_journal(tmp_path: Path):
    journal, outcomes, csv_out, json_out, md_out = _paths(tmp_path)
    _write_journal(journal, [_journal_row()])
    before = journal.read_bytes()

    result = save_paper_trade_close_reports(
        root=tmp_path,
        journal_path=journal,
        outcomes_path=outcomes,
        csv_out=csv_out,
        json_out=json_out,
        markdown_out=md_out,
        summary=True,
    )

    assert result["status"] == "PASS"
    assert journal.read_bytes() == before


def test_daily_validation_has_optional_close_summary_after_followup():
    post_names = [item["name"] for item in daily_validation.POST_SUMMARY_STEPS]

    assert "paper_trade_close" in post_names
    assert post_names.index("paper_trade_followup") < post_names.index("paper_trade_close")

    step = next(item for item in daily_validation.POST_SUMMARY_STEPS if item["name"] == "paper_trade_close")
    assert step["required"] is False
    assert "tools/paper_trade_close.py" in step["cmd"]
    assert "--summary" in step["cmd"]
    assert "--close" not in step["cmd"]
    assert "--export-outcomes" not in step["cmd"]


def test_daily_operator_index_renders_close_section():
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
            "paper_trading_journal": {"available": False},
            "paper_trade_followup": {"available": False},
            "paper_trade_close": {
                "available": True,
                "status": "PASS",
                "rows": 1,
                "open_paper_trades": 1,
                "closed_paper_trades": 0,
                "pending_export": 0,
                "exported_outcomes": 0,
            },
            "trade_score_calibration": {"available": False},
            "calibration_recommendations": {"available": False},
            "release_readiness": {"available": False},
            "manifest_status": "PASS",
            "git_dirty": False,
            "missing_script_files": 0,
            "missing_report_files": 0,
            "report_status": [],
        }
    )

    assert "## Paper trade close" in text
    assert "reports/paper_trade_close_latest.md" in text
    assert "flags manuales" in text


def test_daily_run_manifest_tracks_close_script_and_reports():
    assert "tools/paper_trade_close.py" in KEY_SCRIPT_PATHS
    assert "reports/paper_trade_close_latest.csv" in KEY_REPORT_PATHS
    assert "reports/paper_trade_close_latest.json" in KEY_REPORT_PATHS
    assert "reports/paper_trade_close_latest.md" in KEY_REPORT_PATHS


def test_outputs_do_not_create_disabled_signal_or_trigger_confirmed(tmp_path: Path):
    journal, outcomes, csv_out, json_out, md_out = _paths(tmp_path)
    _write_journal(journal, [_journal_row()])

    save_paper_trade_close_reports(
        root=tmp_path,
        journal_path=journal,
        outcomes_path=outcomes,
        csv_out=csv_out,
        json_out=json_out,
        markdown_out=md_out,
        summary=True,
    )

    combined = csv_out.read_text(encoding="utf-8") + json_out.read_text(encoding="utf-8") + md_out.read_text(encoding="utf-8")
    disabled_signal = "_".join(["BUY", "SETUP", "ACTIVE"])
    trigger_signal = "_".join(["TRIGGER", "CONFIRMED"])
    assert disabled_signal not in combined
    assert trigger_signal not in combined


def test_markdown_states_no_broker_or_real_orders(tmp_path: Path):
    journal, outcomes, csv_out, json_out, md_out = _paths(tmp_path)
    _write_journal(journal, [_journal_row()])

    save_paper_trade_close_reports(
        root=tmp_path,
        journal_path=journal,
        outcomes_path=outcomes,
        csv_out=csv_out,
        json_out=json_out,
        markdown_out=md_out,
        summary=True,
    )

    text = md_out.read_text(encoding="utf-8")
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert "No broker connection is used." in text
    assert "No real orders are sent." in text
    assert payload["no_real_order_notice"] == "paper trading only; no real order"
