from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools.gui_actions_audit import collect_gui_actions_audit, save_gui_actions_audit
from ui import actions

ROOT = Path(__file__).resolve().parents[1]


def _write_journal(root: Path, rows: list[dict]) -> None:
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(data / "paper_trading_journal.csv", index=False)


def test_actions_module_imports_without_error():
    assert actions.NO_REAL_ORDER_NOTICE == "paper trading only; no real order"
    assert callable(actions.import_today_candidates)
    assert callable(actions.set_paper_decision)
    assert callable(actions.refresh_paper_followup)
    assert callable(actions.close_paper_trade)
    assert callable(actions.export_closed_paper_outcomes)


def test_import_today_candidates_missing_reports_is_controlled(tmp_path: Path):
    result = actions.import_today_candidates(root=tmp_path, confirmed=True)

    assert result["status"] in {"PASS", "WARN"}
    assert result["payload"]["rows"] == 0
    assert (tmp_path / "data" / "ui_action_log.csv").exists()


def test_set_paper_decision_requires_reason(tmp_path: Path):
    _write_journal(
        tmp_path,
        [
            {
                "journal_id": "2026-06-13-AAA",
                "run_date": "2026-06-13",
                "ticker": "AAA",
                "checklist_status": "REVIEW_MANUALLY",
                "manual_decision": "PENDING_REVIEW",
                "followup_status": "OPEN_MONITORING",
            }
        ],
    )

    result = actions.set_paper_decision(
        root=tmp_path,
        ticker="AAA",
        manual_decision="PAPER_WATCH",
        reason="",
        confirmed=True,
    )

    assert result["status"] == "FAIL"
    assert result["message"] == "reason_required"


def test_paper_enter_requires_entry_stop_target(tmp_path: Path):
    _write_journal(
        tmp_path,
        [
            {
                "journal_id": "2026-06-13-AAA",
                "run_date": "2026-06-13",
                "ticker": "AAA",
                "checklist_status": "REVIEW_MANUALLY",
                "manual_decision": "PENDING_REVIEW",
                "followup_status": "OPEN_MONITORING",
            }
        ],
    )

    result = actions.set_paper_decision(
        root=tmp_path,
        ticker="AAA",
        manual_decision="PAPER_ENTER",
        reason="manual paper test",
        confirmed=True,
    )

    assert result["status"] == "FAIL"
    assert result["message"] == "paper_enter_requires_entry_stop_target"


def test_close_paper_trade_requires_exit_price_and_reason(tmp_path: Path):
    no_price = actions.close_paper_trade(
        root=tmp_path,
        journal_id="2026-06-13-AAA",
        exit_price=None,
        reason="TARGET_REACHED_MANUAL",
        confirmed=True,
    )
    no_reason = actions.close_paper_trade(
        root=tmp_path,
        journal_id="2026-06-13-AAA",
        exit_price=10,
        reason="",
        confirmed=True,
    )

    assert no_price["status"] == "FAIL"
    assert no_price["message"] == "exit_price_required"
    assert no_reason["status"] == "FAIL"
    assert no_reason["message"] == "reason_required"


def test_export_closed_paper_outcomes_does_not_duplicate(tmp_path: Path):
    _write_journal(
        tmp_path,
        [
            {
                "journal_id": "2026-06-13-AAA",
                "run_date": "2026-06-13",
                "ticker": "AAA",
                "manual_decision": "PAPER_ENTER",
                "followup_status": "CLOSED_PAPER",
                "simulated_entry_price": "10",
                "simulated_stop": "9",
                "simulated_target": "12",
                "exit_date": "2026-06-14",
                "exit_price": "12",
                "close_reason": "TARGET_REACHED_MANUAL",
                "pnl_pct": "0.2",
                "r_multiple": "2",
                "outcome_exported": "False",
            }
        ],
    )

    first = actions.export_closed_paper_outcomes(root=tmp_path, confirmed=True)
    second = actions.export_closed_paper_outcomes(root=tmp_path, confirmed=True)

    assert first["status"] == "PASS"
    assert first["payload"]["exported_count"] == 1
    assert second["status"] == "PASS"
    assert second["payload"]["exported_count"] == 0
    assert second["payload"]["skipped_already_exported"] == 1

    outcomes = pd.read_csv(tmp_path / "data" / "trade_outcomes.csv", dtype=str).fillna("")
    assert len(outcomes) == 1
    assert outcomes.loc[0, "source_journal_id"] == "2026-06-13-AAA"


def test_ui_action_log_contains_no_real_order_notice(tmp_path: Path):
    actions.import_today_candidates(root=tmp_path, confirmed=False)

    log = pd.read_csv(tmp_path / "data" / "ui_action_log.csv", dtype=str).fillna("")

    assert len(log) == 1
    assert log.loc[0, "action_type"] == "import_today_candidates"
    assert log.loc[0, "no_real_order_notice"] == actions.NO_REAL_ORDER_NOTICE


def test_app_and_actions_static_guardrails():
    app_text = (ROOT / "app.py").read_text(encoding="utf-8").lower()
    actions_text = (ROOT / "ui" / "actions.py").read_text(encoding="utf-8").lower()
    combined = app_text + "\n" + actions_text

    forbidden = ["send_order", "place_order", "buy_order", "sell_order", "shell=true"]
    assert [item for item in forbidden if item in combined] == []
    assert "run_scanner" not in combined
    assert "_".join(["BUY", "SETUP", "ACTIVE"]).lower() not in combined
    assert "_".join(["TRIGGER", "CONFIRMED"]).lower() not in combined


def test_gui_actions_audit_generates_json_and_markdown(tmp_path: Path):
    (tmp_path / "ui").mkdir()
    (tmp_path / "reports").mkdir()
    (tmp_path / "ui" / "actions.py").write_text(
        "NO_REAL_ORDER_NOTICE = 'paper trading only; no real order'\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "\n".join(
            [
                "from ui import actions as paper_actions",
                "'Confirm paper-only import; no real order'",
                "'Confirm paper-only decision; no real order'",
                "'Confirm manual paper close; no real order'",
                "'Confirm export to trade_outcomes.csv'",
            ]
        ),
        encoding="utf-8",
    )

    result = save_gui_actions_audit(
        root=tmp_path,
        json_out=tmp_path / "reports" / "gui_actions_audit_latest.json",
        markdown_out=tmp_path / "reports" / "gui_actions_audit_latest.md",
    )

    assert result["status"] in {"PASS", "WARN"}
    assert (tmp_path / "reports" / "gui_actions_audit_latest.json").exists()
    assert (tmp_path / "reports" / "gui_actions_audit_latest.md").exists()

    data = json.loads((tmp_path / "reports" / "gui_actions_audit_latest.json").read_text(encoding="utf-8"))
    assert data["actions_module_exists"] is True
    assert data["broker_guardrail_ok"] is True
    assert data["shell_guardrail_ok"] is True


def test_gui_actions_audit_current_project_has_no_critical_failure():
    data = collect_gui_actions_audit(root=ROOT)

    assert data["status"] in {"PASS", "WARN"}
    assert data["critical_failures"] == 0
