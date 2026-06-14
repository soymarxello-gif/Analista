from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools import gui_daily_operating_checklist as checklist
from tools import gui_daily_operating_checklist_audit as audit


def test_import_tool() -> None:
    assert checklist.NO_REAL_ORDER_NOTICE == "paper trading only; no real order"


def test_init_today_creates_minimum_steps(tmp_path: Path) -> None:
    result = checklist.init_today(root=tmp_path)

    assert result["status"] == "WARN"
    assert result["pending_steps"] >= 35
    assert (tmp_path / "data" / "gui_daily_operating_checklists.csv").exists()
    assert (tmp_path / "reports" / "gui_daily_operating_checklist_latest.json").exists()
    assert (tmp_path / "reports" / "gui_daily_operating_checklist_latest.md").exists()


def test_init_today_does_not_duplicate_same_day(tmp_path: Path) -> None:
    first = checklist.init_today(root=tmp_path)
    second = checklist.init_today(root=tmp_path)
    df = pd.read_csv(tmp_path / "data" / "gui_daily_operating_checklists.csv")

    assert second["message"] == "checklist_already_exists"
    assert df["checklist_id"].nunique() == 1
    assert len(df) == first["pending_steps"]


def test_status_without_checklist_is_controlled(tmp_path: Path) -> None:
    result = checklist.checklist_status(root=tmp_path)

    assert result["status"] == "PASS"
    assert result["latest_result"] == "MISSING"


def test_mark_invalid_step_fails(tmp_path: Path) -> None:
    checklist.init_today(root=tmp_path)

    result = checklist.mark_step(root=tmp_path, step_id="missing_step", status="DONE")

    assert result["status"] == "FAIL"
    assert result["message"] == "invalid_step_id"


def test_mark_accepts_done_skipped_blocked_and_records_note(tmp_path: Path) -> None:
    checklist.init_today(root=tmp_path)

    done = checklist.mark_step(root=tmp_path, step_id="activate_venv", status="DONE", note="ok")
    skipped = checklist.mark_step(root=tmp_path, step_id="git_status_review", status="SKIPPED", note="clean earlier")
    blocked = checklist.mark_step(root=tmp_path, step_id="overview_tab_reviewed", status="BLOCKED", note="gui unavailable")
    df = pd.read_csv(tmp_path / "data" / "gui_daily_operating_checklists.csv")

    assert done["message"] == "step_marked"
    assert skipped["message"] == "step_marked"
    assert blocked["message"] == "step_marked"
    assert df.loc[df["step_id"].eq("activate_venv"), "status"].iloc[0] == "DONE"
    assert df.loc[df["step_id"].eq("git_status_review"), "status"].iloc[0] == "SKIPPED"
    assert df.loc[df["step_id"].eq("overview_tab_reviewed"), "status"].iloc[0] == "BLOCKED"
    assert df.loc[df["step_id"].eq("activate_venv"), "note"].iloc[0] == "ok"


def test_close_requires_valid_result(tmp_path: Path) -> None:
    checklist.init_today(root=tmp_path)

    result = checklist.close_checklist(root=tmp_path, result="MAYBE")

    assert result["status"] == "FAIL"
    assert result["message"] == "invalid_result"


def test_close_pass_warns_when_required_steps_pending(tmp_path: Path) -> None:
    checklist.init_today(root=tmp_path)

    result = checklist.close_checklist(root=tmp_path, result="PASS")

    assert result["status"] == "WARN"
    assert result["message"] == "required_steps_pending"


def test_summary_generates_json_and_markdown(tmp_path: Path) -> None:
    checklist.init_today(root=tmp_path)

    result = checklist.checklist_status(root=tmp_path)
    md = (tmp_path / "reports" / "gui_daily_operating_checklist_latest.md").read_text(encoding="utf-8")

    assert result["status"] == "WARN"
    assert "Manual review only" in md
    assert "No real order" in md


def test_source_has_no_shell_or_order_api() -> None:
    source = Path(checklist.__file__).read_text(encoding="utf-8")

    assert "shell=True" not in source
    assert "subprocess" not in source
    assert "send_order" not in source
    assert "place_order" not in source
    assert "buy_order" not in source
    assert "sell_order" not in source
    assert "BUY_SETUP_ACTIVE" not in source
    assert "TRIGGER_CONFIRMED" not in source


def test_audit_generates_json_and_markdown(tmp_path: Path) -> None:
    checklist.init_today(root=tmp_path)

    result = audit.run_audit(root=tmp_path)

    assert result["status"] == "PASS"
    assert result["tool_exists"] is True
    assert result["data_file_can_be_created"] is True
    assert result["no_real_order_notice_present"] is True
    assert result["manual_review_only"] is True
    assert (tmp_path / "reports" / "gui_daily_operating_checklist_audit_latest.json").exists()
    assert (tmp_path / "reports" / "gui_daily_operating_checklist_audit_latest.md").exists()
