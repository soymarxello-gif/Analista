from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Legacy manual paper trading flow removed; simple_candidate_posttest is the active feedback loop.")

import json
from pathlib import Path

import pandas as pd

from tools import daily_validation
from tools.daily_operator_index import build_daily_operator_index_markdown
from tools.daily_run_manifest import KEY_REPORT_PATHS, KEY_SCRIPT_PATHS
from tools.paper_trade_followup import (
    build_paper_trade_followup_dataframe,
    decide_followup,
    save_paper_trade_followup_reports,
)


def _journal_row(**overrides) -> dict:
    row = {
        "journal_id": "2026-06-12-AAA",
        "run_date": "2026-06-12",
        "ticker": "AAA",
        "manual_decision": "PAPER_ENTER",
        "followup_status": "ENTERED_PAPER",
        "simulated_entry_price": 100,
        "simulated_stop": 90,
        "simulated_target": 120,
        "no_real_order_notice": "paper trading only; no real order",
    }
    row.update(overrides)
    return row


def _quote(price, status: str = "VALID") -> dict:
    return {
        "latest_price": price,
        "latest_quote_source": "MOCK",
        "latest_quote_status": status,
        "latest_quote_error": "" if price is not None else "missing_mock_price",
    }


def test_missing_journal_returns_controlled_warning(tmp_path: Path):
    reports = tmp_path / "reports"

    result = save_paper_trade_followup_reports(
        root=tmp_path,
        journal_path=tmp_path / "data" / "missing.csv",
        csv_out=reports / "paper_trade_followup_latest.csv",
        json_out=reports / "paper_trade_followup_latest.json",
        markdown_out=reports / "paper_trade_followup_latest.md",
        fetcher=lambda ticker: _quote(105),
    )

    assert result["status"] == "WARN"
    assert result["rows"] == 0
    assert result["error"] == "journal_csv_not_found"
    assert (reports / "paper_trade_followup_latest.csv").exists()
    assert (reports / "paper_trade_followup_latest.json").exists()
    assert (reports / "paper_trade_followup_latest.md").exists()


def test_empty_journal_passes_rows_zero(tmp_path: Path):
    data_dir = tmp_path / "data"
    reports = tmp_path / "reports"
    data_dir.mkdir()
    pd.DataFrame(columns=["ticker", "manual_decision", "followup_status"]).to_csv(
        data_dir / "paper_trading_journal.csv",
        index=False,
    )

    result = save_paper_trade_followup_reports(
        root=tmp_path,
        journal_path=data_dir / "paper_trading_journal.csv",
        csv_out=reports / "paper_trade_followup_latest.csv",
        json_out=reports / "paper_trade_followup_latest.json",
        markdown_out=reports / "paper_trade_followup_latest.md",
        fetcher=lambda ticker: _quote(105),
    )

    assert result["status"] == "PASS"
    assert result["rows"] == 0
    assert result["no_open_paper_trades"] == 1


def test_no_open_paper_trades_passes_rows_zero(tmp_path: Path):
    reports = tmp_path / "reports"
    journal = tmp_path / "data" / "paper_trading_journal.csv"
    journal.parent.mkdir()
    pd.DataFrame(
        [
            _journal_row(
                manual_decision="PENDING_REVIEW",
                followup_status="OPEN_MONITORING",
                simulated_entry_price="",
                simulated_stop="",
                simulated_target="",
            )
        ]
    ).to_csv(journal, index=False)

    result = save_paper_trade_followup_reports(
        root=tmp_path,
        journal_path=journal,
        csv_out=reports / "paper_trade_followup_latest.csv",
        json_out=reports / "paper_trade_followup_latest.json",
        markdown_out=reports / "paper_trade_followup_latest.md",
        fetcher=lambda ticker: _quote(105),
    )

    assert result["status"] == "PASS"
    assert result["rows"] == 0
    assert result["no_open_paper_trades"] == 1


def test_paper_enter_between_levels_holds_paper():
    df = build_paper_trade_followup_dataframe(
        pd.DataFrame([_journal_row()]),
        fetcher=lambda ticker: _quote(105),
    )

    assert df.iloc[0]["followup_decision"] == "HOLD_PAPER"
    assert bool(df.iloc[0]["manual_review_required"]) is False


def test_price_near_stop_flags_review_near_stop():
    decision = decide_followup(_journal_row(), _quote(92), near_stop_pct=0.03)

    assert decision["followup_decision"] == "REVIEW_NEAR_STOP"


def test_price_near_target_flags_review_near_target():
    decision = decide_followup(_journal_row(), _quote(118), near_target_pct=0.03)

    assert decision["followup_decision"] == "REVIEW_NEAR_TARGET"


def test_price_below_stop_flags_stop_hit_review_close():
    decision = decide_followup(_journal_row(), _quote(89))

    assert decision["followup_decision"] == "STOP_HIT_REVIEW_CLOSE"
    assert decision["stop_hit_intraday"] is True


def test_price_above_target_flags_target_hit_review_close():
    decision = decide_followup(_journal_row(), _quote(121))

    assert decision["followup_decision"] == "TARGET_HIT_REVIEW_CLOSE"
    assert decision["target_hit_intraday"] is True


def test_missing_quote_flags_data_unavailable():
    decision = decide_followup(_journal_row(), _quote(None, status="MISSING"))

    assert decision["followup_decision"] == "DATA_UNAVAILABLE"
    assert decision["manual_review_required"] is True


def test_followup_does_not_modify_journal(tmp_path: Path):
    reports = tmp_path / "reports"
    journal = tmp_path / "data" / "paper_trading_journal.csv"
    journal.parent.mkdir()
    pd.DataFrame([_journal_row()]).to_csv(journal, index=False)
    before = journal.read_bytes()

    result = save_paper_trade_followup_reports(
        root=tmp_path,
        journal_path=journal,
        csv_out=reports / "paper_trade_followup_latest.csv",
        json_out=reports / "paper_trade_followup_latest.json",
        markdown_out=reports / "paper_trade_followup_latest.md",
        fetcher=lambda ticker: _quote(105),
    )
    after = journal.read_bytes()

    assert result["status"] == "PASS"
    assert before == after


def test_daily_validation_has_optional_followup_after_journal():
    post_names = [item["name"] for item in daily_validation.POST_SUMMARY_STEPS]

    assert "paper_trade_followup" in post_names
    assert post_names.index("paper_trading_journal") < post_names.index("paper_trade_followup")

    step = next(item for item in daily_validation.POST_SUMMARY_STEPS if item["name"] == "paper_trade_followup")
    assert step["required"] is False
    assert "tools/paper_trade_followup.py" in step["cmd"]
    assert "reports/paper_trade_followup_latest.md" in step["cmd"]


def test_daily_operator_index_renders_followup_section():
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
            "paper_trade_followup": {
                "available": True,
                "status": "PASS",
                "rows": 1,
                "hold_paper": 1,
                "review_near_stop": 0,
                "review_near_target": 0,
                "stop_hit_review_close": 0,
                "target_hit_review_close": 0,
                "data_unavailable": 0,
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

    assert "## Paper trade follow-up" in text
    assert "- hold_paper: 1" in text
    assert "reports/paper_trade_followup_latest.md" in text


def test_daily_run_manifest_tracks_followup_outputs():
    assert "tools/paper_trade_followup.py" in KEY_SCRIPT_PATHS
    assert "reports/paper_trade_followup_latest.csv" in KEY_REPORT_PATHS
    assert "reports/paper_trade_followup_latest.json" in KEY_REPORT_PATHS
    assert "reports/paper_trade_followup_latest.md" in KEY_REPORT_PATHS


def test_output_contains_no_disabled_signal_or_trigger(tmp_path: Path):
    reports = tmp_path / "reports"
    journal = tmp_path / "data" / "paper_trading_journal.csv"
    journal.parent.mkdir()
    pd.DataFrame([_journal_row()]).to_csv(journal, index=False)
    disabled_signal = "_".join(["BUY", "SETUP", "ACTIVE"])

    save_paper_trade_followup_reports(
        root=tmp_path,
        journal_path=journal,
        csv_out=reports / "paper_trade_followup_latest.csv",
        json_out=reports / "paper_trade_followup_latest.json",
        markdown_out=reports / "paper_trade_followup_latest.md",
        fetcher=lambda ticker: _quote(105),
    )
    text = (reports / "paper_trade_followup_latest.md").read_text(encoding="utf-8")
    payload = json.loads((reports / "paper_trade_followup_latest.json").read_text(encoding="utf-8"))
    trigger_text = "_".join(["TRIGGER", "CONFIRMED"])

    assert disabled_signal not in text
    assert trigger_text not in text
    assert payload["no_real_order_notice"] == "paper trading only; no real order"
