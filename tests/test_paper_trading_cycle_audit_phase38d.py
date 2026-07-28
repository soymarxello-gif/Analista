from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Legacy manual paper trading flow removed; simple_candidate_posttest is the active feedback loop.")

import json
from pathlib import Path

import pandas as pd

from tools import daily_validation
from tools.daily_operator_index import build_daily_operator_index_markdown
from tools.daily_run_manifest import KEY_REPORT_PATHS, KEY_SCRIPT_PATHS
from tools.paper_trading_cycle_audit import save_paper_trading_cycle_audit


def _journal_row(**overrides) -> dict:
    row = {
        "journal_id": "J-AAA-001",
        "run_date": "2026-06-12",
        "ticker": "AAA",
        "manual_decision": "PENDING_REVIEW",
        "followup_status": "OPEN_MONITORING",
        "simulated_entry_price": "",
        "simulated_stop": "",
        "simulated_target": "",
        "no_real_order_notice": "paper trading only; no real order",
    }
    row.update(overrides)
    return row


def _outcome_row(**overrides) -> dict:
    row = {
        "trade_id": "PAPER_J-AAA-001",
        "ticker": "AAA",
        "status": "CLOSED",
        "source": "PAPER_TRADING_JOURNAL",
        "source_journal_id": "J-AAA-001",
        "pnl_pct": "0.10",
        "r_multiple": "1.0",
    }
    row.update(overrides)
    return row


def _paths(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    journal = tmp_path / "data" / "paper_trading_journal.csv"
    outcomes = tmp_path / "data" / "trade_outcomes.csv"
    json_out = tmp_path / "reports" / "paper_trading_cycle_audit_latest.json"
    md_out = tmp_path / "reports" / "paper_trading_cycle_audit_latest.md"
    return journal, outcomes, json_out, md_out


def _write_csv(path: Path, rows: list[dict], columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    if df.empty and columns:
        df = pd.DataFrame(columns=columns)
    df.to_csv(path, index=False)


def _write_optional_reports(root: Path) -> None:
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    for name, status in {
        "paper_trading_journal_latest.json": "PASS",
        "paper_trade_followup_latest.json": "PASS",
        "paper_trade_close_latest.json": "PASS",
        "trade_outcome_analytics_latest.json": "PASS",
        "trade_score_calibration_latest.json": "PASS",
        "calibration_recommendations_latest.json": "WARN",
    }.items():
        payload = {"status": status}
        if name == "calibration_recommendations_latest.json":
            payload["do_not_change_automatically"] = True
        (reports / name).write_text(json.dumps(payload), encoding="utf-8")


def _run_audit(tmp_path: Path) -> dict:
    journal, outcomes, json_out, md_out = _paths(tmp_path)
    return save_paper_trading_cycle_audit(
        root=tmp_path,
        journal_path=journal,
        outcomes_path=outcomes,
        json_out=json_out,
        markdown_out=md_out,
    )


def test_missing_journal_warns_without_traceback(tmp_path: Path):
    _write_optional_reports(tmp_path)

    result = _run_audit(tmp_path)

    assert result["status"] == "WARN"
    assert result["journal_rows"] == 0
    assert any("journal_unavailable" in warning for warning in result["warnings"])


def test_empty_journal_controlled_status(tmp_path: Path):
    journal, outcomes, _, _ = _paths(tmp_path)
    _write_optional_reports(tmp_path)
    _write_csv(journal, [], columns=list(_journal_row().keys()))
    _write_csv(outcomes, [], columns=list(_outcome_row().keys()))

    result = _run_audit(tmp_path)

    assert result["status"] in {"PASS", "WARN"}
    assert result["journal_rows"] == 0


def test_open_paper_trade_is_counted(tmp_path: Path):
    journal, outcomes, _, _ = _paths(tmp_path)
    _write_optional_reports(tmp_path)
    _write_csv(
        journal,
        [
            _journal_row(
                manual_decision="PAPER_ENTER",
                followup_status="ENTERED_PAPER",
                simulated_entry_price="100",
                simulated_stop="90",
                simulated_target="120",
            )
        ],
    )
    _write_csv(outcomes, [], columns=list(_outcome_row().keys()))

    result = _run_audit(tmp_path)

    assert result["open_paper_count"] == 1
    assert result["closed_paper_count"] == 0


def test_closed_paper_not_exported_is_pending_export(tmp_path: Path):
    journal, outcomes, _, _ = _paths(tmp_path)
    _write_optional_reports(tmp_path)
    _write_csv(
        journal,
        [
            _journal_row(
                manual_decision="PAPER_ENTER",
                followup_status="CLOSED_PAPER",
                outcome_exported="False",
            )
        ],
    )
    _write_csv(outcomes, [], columns=list(_outcome_row().keys()))

    result = _run_audit(tmp_path)

    assert result["closed_paper_count"] == 1
    assert result["pending_export_count"] == 1


def test_closed_exported_with_matching_outcome_passes(tmp_path: Path):
    journal, outcomes, _, _ = _paths(tmp_path)
    _write_optional_reports(tmp_path)
    _write_csv(
        journal,
        [
            _journal_row(
                manual_decision="PAPER_ENTER",
                followup_status="CLOSED_PAPER",
                outcome_exported="True",
            )
        ],
    )
    _write_csv(outcomes, [_outcome_row()])

    result = _run_audit(tmp_path)

    assert result["status"] == "PASS"
    assert result["exported_count"] == 1
    assert result["missing_outcome_exports"] == []


def test_exported_journal_without_matching_outcome_fails(tmp_path: Path):
    journal, outcomes, _, _ = _paths(tmp_path)
    _write_optional_reports(tmp_path)
    _write_csv(
        journal,
        [
            _journal_row(
                manual_decision="PAPER_ENTER",
                followup_status="CLOSED_PAPER",
                outcome_exported="True",
            )
        ],
    )
    _write_csv(outcomes, [], columns=list(_outcome_row().keys()))

    result = _run_audit(tmp_path)

    assert result["status"] == "FAIL"
    assert result["missing_outcome_exports"] == ["J-AAA-001"]


def test_duplicate_source_journal_id_fails(tmp_path: Path):
    journal, outcomes, _, _ = _paths(tmp_path)
    _write_optional_reports(tmp_path)
    _write_csv(
        journal,
        [
            _journal_row(
                manual_decision="PAPER_ENTER",
                followup_status="CLOSED_PAPER",
                outcome_exported="True",
            )
        ],
    )
    _write_csv(outcomes, [_outcome_row(trade_id="P1"), _outcome_row(trade_id="P2")])

    result = _run_audit(tmp_path)

    assert result["status"] == "FAIL"
    assert result["duplicate_outcome_ids"] == ["J-AAA-001"]


def test_audit_does_not_modify_journal_or_outcomes(tmp_path: Path):
    journal, outcomes, _, _ = _paths(tmp_path)
    _write_optional_reports(tmp_path)
    _write_csv(journal, [_journal_row()])
    _write_csv(outcomes, [], columns=list(_outcome_row().keys()))
    before_journal = journal.read_bytes()
    before_outcomes = outcomes.read_bytes()

    _run_audit(tmp_path)

    assert journal.read_bytes() == before_journal
    assert outcomes.read_bytes() == before_outcomes


def test_daily_validation_has_optional_cycle_audit_after_close():
    post_names = [item["name"] for item in daily_validation.POST_SUMMARY_STEPS]

    assert "paper_trading_cycle_audit" in post_names
    assert post_names.index("paper_trade_close") < post_names.index("paper_trading_cycle_audit")

    step = next(
        item for item in daily_validation.POST_SUMMARY_STEPS if item["name"] == "paper_trading_cycle_audit"
    )
    assert step["required"] is False
    assert "tools/paper_trading_cycle_audit.py" in step["cmd"]


def test_daily_operator_index_renders_cycle_audit_section():
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
            "paper_trade_close": {"available": False},
            "paper_trading_cycle_audit": {
                "available": True,
                "status": "WARN",
                "journal_rows": 1,
                "open_paper_count": 1,
                "closed_paper_count": 0,
                "pending_export_count": 0,
                "exported_count": 0,
                "duplicate_outcome_ids": 0,
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

    assert "## Paper trading cycle audit" in text
    assert "reports/paper_trading_cycle_audit_latest.md" in text


def test_daily_run_manifest_tracks_cycle_audit_outputs():
    assert "tools/paper_trading_cycle_audit.py" in KEY_SCRIPT_PATHS
    assert "reports/paper_trading_cycle_audit_latest.json" in KEY_REPORT_PATHS
    assert "reports/paper_trading_cycle_audit_latest.md" in KEY_REPORT_PATHS


def test_outputs_do_not_create_disabled_signal_or_trigger(tmp_path: Path):
    journal, outcomes, json_out, md_out = _paths(tmp_path)
    _write_optional_reports(tmp_path)
    _write_csv(journal, [_journal_row()])
    _write_csv(outcomes, [], columns=list(_outcome_row().keys()))

    _run_audit(tmp_path)

    combined = json_out.read_text(encoding="utf-8") + md_out.read_text(encoding="utf-8")
    disabled_signal = "_".join(["BUY", "SETUP", "ACTIVE"])
    trigger_signal = "_".join(["TRIGGER", "CONFIRMED"])
    assert disabled_signal not in combined
    assert trigger_signal not in combined


def test_no_broker_connection_or_orders_in_outputs(tmp_path: Path):
    journal, outcomes, json_out, md_out = _paths(tmp_path)
    _write_optional_reports(tmp_path)
    _write_csv(journal, [_journal_row()])
    _write_csv(outcomes, [], columns=list(_outcome_row().keys()))

    result = _run_audit(tmp_path)

    text = md_out.read_text(encoding="utf-8")
    assert result["broker_connection_detected"] is False
    assert "No broker connection is used." in text
    assert "No real orders are sent." in text
    assert json.loads(json_out.read_text(encoding="utf-8"))["no_real_order_notice"] == (
        "paper trading only; no real order"
    )
