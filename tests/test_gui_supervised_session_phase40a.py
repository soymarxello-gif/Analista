from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd

from tools.gui_supervised_session import (
    add_note,
    close_session,
    session_status,
    start_session,
)
from tools.gui_supervised_session_audit import save_gui_supervised_session_audit

ROOT = Path(__file__).resolve().parents[1]


def _prepare_root(root: Path) -> None:
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "reports" / "manual_review_top.csv").write_text(
        "ticker,signal,recommendation\nAAA,WATCHLIST,RECHECK_LIVE_QUOTE\nBBB,WATCHLIST,WATCHLIST_MONITOR\n",
        encoding="utf-8",
    )
    for name, data in {
        "daily_run_manifest_latest.json": {"status": "PASS"},
        "daily_quality_gate_latest.json": {"status": "WARN", "issues": 1},
        "release_readiness_latest.json": {"status": "WARN", "warnings": 1},
        "gui_release_audit_latest.json": {"status": "WARN", "issues": [{"severity": "WARN"}]},
        "streamlit_smoke_test_latest.json": {"status": "PASS"},
        "paper_trading_journal_latest.json": {"status": "PASS", "rows": 2},
        "paper_trade_close_latest.json": {"status": "PASS", "closed_paper_trades": 0, "pending_export": 0},
        "paper_trading_cycle_audit_latest.json": {
            "status": "WARN",
            "closed_paper_count": 0,
            "pending_export_count": 0,
            "exported_count": 0,
        },
    }.items():
        (root / "reports" / name).write_text(json.dumps(data), encoding="utf-8")


def test_gui_supervised_session_imports_without_error():
    spec = importlib.util.spec_from_file_location(
        "analista_gui_supervised_session_phase40a",
        ROOT / "tools" / "gui_supervised_session.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert hasattr(module, "main")


def test_status_does_not_fail_without_prior_session(tmp_path: Path):
    result = session_status(root=tmp_path)
    assert result["status"] == "PASS"
    assert result["rows"] == 0
    assert (tmp_path / "data" / "gui_supervised_sessions.csv").exists()


def test_start_creates_open_session(tmp_path: Path):
    _prepare_root(tmp_path)
    result = start_session(root=tmp_path)
    assert result["latest_session_status"] == "OPEN"
    df = pd.read_csv(tmp_path / "data" / "gui_supervised_sessions.csv", dtype=str).fillna("")
    assert len(df) == 1
    assert df.iloc[0]["status"] == "OPEN"
    assert df.iloc[0]["no_real_order_notice"] == "paper trading only; no real order"


def test_note_adds_to_open_session(tmp_path: Path):
    _prepare_root(tmp_path)
    start_session(root=tmp_path)
    result = add_note(root=tmp_path, note="reviewed candidates")
    assert result["latest_session_status"] == "OPEN"
    df = pd.read_csv(tmp_path / "data" / "gui_supervised_sessions.csv", dtype=str).fillna("")
    assert "reviewed candidates" in df.iloc[0]["notes"]


def test_close_requires_valid_result(tmp_path: Path):
    _prepare_root(tmp_path)
    start_session(root=tmp_path)
    result = close_session(root=tmp_path, result="MAYBE")
    assert result["status"] == "FAIL"
    assert result["message"] == "invalid_result"


def test_close_changes_status_to_closed(tmp_path: Path):
    _prepare_root(tmp_path)
    start_session(root=tmp_path)
    result = close_session(root=tmp_path, result="PASS")
    assert result["latest_session_status"] == "CLOSED"
    assert result["latest_session_result"] == "PASS"
    df = pd.read_csv(tmp_path / "data" / "gui_supervised_sessions.csv", dtype=str).fillna("")
    assert df.iloc[0]["status"] == "CLOSED"
    assert df.iloc[0]["result"] == "PASS"


def test_summary_generates_json_and_markdown(tmp_path: Path):
    _prepare_root(tmp_path)
    start_session(root=tmp_path)
    result = session_status(root=tmp_path)
    assert result["rows"] == 1
    assert (tmp_path / "reports" / "gui_supervised_session_latest.json").exists()
    assert (tmp_path / "reports" / "gui_supervised_session_latest.md").exists()


def test_start_does_not_duplicate_open_session(tmp_path: Path):
    _prepare_root(tmp_path)
    first = start_session(root=tmp_path)
    second = start_session(root=tmp_path)
    assert first["latest_session_status"] == "OPEN"
    assert second["message"] == "open_session_already_exists"
    df = pd.read_csv(tmp_path / "data" / "gui_supervised_sessions.csv", dtype=str).fillna("")
    assert len(df) == 1


def test_supervised_session_tool_has_no_shell_or_order_terms():
    text = (ROOT / "tools" / "gui_supervised_session.py").read_text(encoding="utf-8")
    lower = text.lower()
    assert "shell=true" not in lower
    for term in ["send_order", "place_order", "buy_order", "sell_order"]:
        assert term not in lower
    for api in ["ibapi", "alpaca", "interactivebrokers", "robinhood"]:
        assert api not in lower


def test_gui_supervised_session_audit_generates_json_and_markdown(tmp_path: Path):
    result = save_gui_supervised_session_audit(
        root=ROOT,
        json_out=tmp_path / "reports" / "gui_supervised_session_audit_latest.json",
        markdown_out=tmp_path / "reports" / "gui_supervised_session_audit_latest.md",
    )
    assert result["status"] in {"PASS", "WARN"}
    assert result["critical_failures"] == 0
    assert (tmp_path / "reports" / "gui_supervised_session_audit_latest.json").exists()
    assert (tmp_path / "reports" / "gui_supervised_session_audit_latest.md").exists()
