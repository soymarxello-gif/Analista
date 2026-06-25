from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from tools.gui_release_audit import collect_gui_release_audit, save_gui_release_audit
from ui import formatters, guards

ROOT = Path(__file__).resolve().parents[1]


def test_guards_and_formatters_import_without_error():
    assert guards.NO_REAL_ORDER_NOTICE == "paper trading only; no real order"
    assert formatters.format_status_badge("pass") == "PASS"


def test_validate_paper_enter_payload_requires_entry_stop_target():
    result = guards.validate_paper_enter_payload(
        manual_decision="PAPER_ENTER",
        entry="",
        stop=None,
        target=0,
        confirmed=True,
    )
    assert result["ok"] is False
    assert "entry_required" in result["errors"]
    assert "stop_required" in result["errors"]
    assert "target_required" in result["errors"]


def test_validate_close_payload_requires_exit_price_and_reason():
    result = guards.validate_close_payload(
        journal_id="J1",
        exit_price="",
        reason="",
        confirmed=True,
    )
    assert result["ok"] is False
    assert "exit_price_required" in result["errors"]
    assert "reason_required" in result["errors"]


def test_validate_export_confirmation_requires_confirmation():
    result = guards.validate_export_confirmation(False)
    assert result["ok"] is False
    assert result["errors"] == ["confirmation_required"]


def test_scan_file_for_forbidden_terms_detects_terms(tmp_path: Path):
    path = tmp_path / "bad.txt"
    path.write_text("send_order and alpaca", encoding="utf-8")
    result = guards.scan_file_for_forbidden_terms(path)
    assert result["ok"] is False
    assert "send_order" in result["hits"]
    assert "alpaca" in result["hits"]


@pytest.mark.parametrize("value", [None, float("nan"), "", "nan", 12, 12.345])
def test_formatters_tolerate_missing_strings_and_numbers(value):
    assert isinstance(formatters.safe_display_text(value), str)
    assert isinstance(formatters.format_number(value), str)
    assert isinstance(formatters.format_percent(value), str)
    assert isinstance(formatters.format_price(value), str)
    assert isinstance(formatters.format_score(value), str)


def test_app_imports_without_error():
    spec = importlib.util.spec_from_file_location("analista_app_phase39e", ROOT / "app.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert hasattr(module, "main")


def test_app_uses_expected_ui_modules_and_has_no_direct_writes_or_order_terms():
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    lower = text.lower()
    assert "from ui import guards as ui_guards" in text
    assert "from ui import formatters as ui_formatters" in text
    assert "from ui import layout as ui_layout" in text
    assert "shell=true" not in lower
    assert "to_csv(" not in lower
    assert "write_text(" not in lower
    assert "open(" not in lower
    assert "pd.read_csv" not in lower
    for term in ["send_order", "place_order", "buy_order", "sell_order"]:
        assert term not in lower
    assert "broker" not in lower


def test_actions_no_shell_and_registers_notice():
    text = (ROOT / "ui" / "actions.py").read_text(encoding="utf-8")
    assert "shell=True" not in text
    assert "NO_REAL_ORDER_NOTICE" in text


def test_gui_release_audit_generates_json_and_markdown(tmp_path: Path):
    reports = tmp_path / "reports"
    result = save_gui_release_audit(
        root=ROOT,
        json_out=reports / "gui_release_audit_latest.json",
        markdown_out=reports / "gui_release_audit_latest.md",
    )
    assert result["status"] in {"PASS", "WARN"}
    assert (reports / "gui_release_audit_latest.json").exists()
    assert (reports / "gui_release_audit_latest.md").exists()
    data = json.loads((reports / "gui_release_audit_latest.json").read_text(encoding="utf-8"))
    assert data["app_exists"] is True
    assert data["guards_exists"] is True
    assert data["formatters_exists"] is True
    assert data["critical_failures"] == 0


def test_current_project_gui_release_audit_has_no_critical_failure():
    data = collect_gui_release_audit(root=ROOT)
    assert data["critical_failures"] == 0
    assert data["status"] in {"PASS", "WARN"}
