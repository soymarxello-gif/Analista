from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools.gui_actions_audit import collect_gui_actions_audit, save_gui_actions_audit
from ui import actions

ROOT = Path(__file__).resolve().parents[1]


def test_actions_module_exposes_only_current_ui_actions():
    assert actions.NO_REAL_ORDER_NOTICE == "manual review only; no real order"
    assert callable(actions.refresh_all_data)
    assert callable(actions.run_single_ticker_deep_dive)
    for legacy_name in [
        "import_today_candidates",
        "set_paper_decision",
        "refresh_paper_followup",
        "close_paper_trade",
        "export_closed_paper_outcomes",
    ]:
        assert not hasattr(actions, legacy_name)


def test_refresh_all_data_runs_daily_validation_controlled(tmp_path: Path, monkeypatch):
    def fake_run_daily_validation(summary_out: Path) -> int:
        summary_out.parent.mkdir(parents=True, exist_ok=True)
        summary_out.write_text("Status: WARN\n", encoding="utf-8")
        return 0

    monkeypatch.setattr(actions, "run_daily_validation", fake_run_daily_validation)

    result = actions.refresh_all_data(root=tmp_path, confirmed=True)

    assert result["status"] == "WARN"
    assert result["payload"]["summary_status"] == "WARN"
    assert result["payload"]["reports_refreshed"] is True
    assert result["payload"]["creates_trading_signal"] is False

    log = pd.read_csv(tmp_path / "data" / "ui_action_log.csv", dtype=str).fillna("")
    assert log.loc[0, "action_type"] == "refresh_all_data"
    assert log.loc[0, "no_real_order_notice"] == actions.NO_REAL_ORDER_NOTICE


def test_single_ticker_deep_dive_is_logged_and_diagnostic_only(tmp_path: Path, monkeypatch):
    def fake_save_single_ticker_deep_dive_reports(*args, **kwargs):
        return {
            "status": "PASS",
            "ticker": "AAA",
            "json_out": "reports/single_ticker_deep_dive_latest.json",
            "markdown_out": "reports/single_ticker_deep_dive_latest.md",
            "row": {
                "ticker": "AAA",
                "manual_deep_dive_decision": "DIAGNOSTIC_REVIEW_ONLY",
                "scenario_status": "WAIT_FOR_CONFIRMATION",
                "final_trade_score": 77,
                "quote_status": "MISSING",
                "execution_quote_quality": "LOW",
            },
        }

    monkeypatch.setattr(
        actions,
        "save_single_ticker_deep_dive_reports",
        fake_save_single_ticker_deep_dive_reports,
    )
    monkeypatch.setattr(actions, "load_config", lambda *args, **kwargs: {})

    result = actions.run_single_ticker_deep_dive(root=tmp_path, ticker="aaa", confirmed=True)

    assert result["status"] == "PASS"
    assert result["payload"]["manual_review_only"] is True
    assert result["payload"]["creates_trading_signal"] is False
    assert result["payload"]["execution_quote_quality"] == "LOW"

    log = pd.read_csv(tmp_path / "data" / "ui_action_log.csv", dtype=str).fillna("")
    assert log.loc[0, "action_type"] == "single_ticker_deep_dive"
    assert log.loc[0, "ticker"] == "AAA"


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
        "\n".join(
            [
                "NO_REAL_ORDER_NOTICE = 'manual review only; no real order'",
                "def refresh_all_data(): pass",
                "def run_single_ticker_deep_dive(): pass",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "\n".join(
            [
                "from ui import actions as ui_actions",
                "ui_actions.refresh_all_data(",
                "ui_actions.run_single_ticker_deep_dive(",
                "manual review only; no real order",
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
    assert data["controlled_actions_present"] is True


def test_gui_actions_audit_current_project_has_no_critical_failure():
    data = collect_gui_actions_audit(root=ROOT)

    assert data["status"] in {"PASS", "WARN"}
    assert data["critical_failures"] == 0
