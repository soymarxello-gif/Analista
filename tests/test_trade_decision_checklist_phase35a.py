from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools import daily_validation
from tools.daily_operator_index import build_daily_operator_index_markdown
from tools.daily_run_manifest import KEY_REPORT_PATHS, KEY_SCRIPT_PATHS
from tools.trade_decision_checklist import (
    build_trade_decision_checklist_dataframe,
    evaluate_checklist_row,
    save_trade_decision_checklist_reports,
)


def _candidate(**overrides) -> dict:
    row = {
        "ticker": "AAA",
        "signal": "WATCHLIST",
        "recommendation": "WATCHLIST_MONITOR",
        "setup_type": "BREAKOUT",
        "final_trade_score": 88,
        "setup_quality_score": 90,
        "asset_quality_score": 85,
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
        "stop_atr_status": "IDEAL",
        "price": 100,
        "market_cap": 5_000_000_000,
        "liquidity_pass": True,
        "sector": "Technology",
        "industry": "Software",
        "metadata_source": "YAHOO",
        "quote_source": "YAHOO",
    }
    row.update(overrides)
    return row


def test_veto_is_blocked():
    result = evaluate_checklist_row(_candidate(signal="VETO"))

    assert result["checklist_status"] == "BLOCKED"
    assert "signal_veto" in result["checklist_blockers"]


def test_avoid_is_blocked():
    result = evaluate_checklist_row(_candidate(signal="AVOID"))

    assert result["checklist_status"] == "BLOCKED"
    assert "signal_avoid" in result["checklist_blockers"]


def test_no_valid_setup_is_blocked():
    result = evaluate_checklist_row(_candidate(setup_type="NO_VALID_SETUP"))

    assert result["checklist_status"] == "BLOCKED"
    assert "no_valid_setup" in result["checklist_blockers"]


def test_missing_entry_stop_target_is_blocked():
    result = evaluate_checklist_row(
        _candidate(actionable_entry=None, actionable_stop=None, actionable_target=None)
    )

    assert result["checklist_status"] == "BLOCKED"
    assert "missing_actionable_entry_stop_or_target" in result["checklist_blockers"]


def test_bad_quote_status_needs_live_quote_recheck():
    for status in ["MISSING", "INVALID", "STALE_POSSIBLE"]:
        result = evaluate_checklist_row(_candidate(quote_status=status))

        assert result["checklist_status"] == "NEEDS_LIVE_QUOTE_RECHECK"
        assert "review_live_quote_recheck_latest" in result["checklist_required_actions"]


def test_low_execution_quality_needs_live_quote_recheck():
    result = evaluate_checklist_row(_candidate(execution_quote_quality="LOW"))

    assert result["checklist_status"] == "NEEDS_LIVE_QUOTE_RECHECK"
    assert "execution_quote_quality_low" in result["checklist_warnings"]


def test_recheck_recommendation_needs_live_quote_recheck():
    result = evaluate_checklist_row(_candidate(recommendation="RECHECK_LIVE_QUOTE"))

    assert result["checklist_status"] == "NEEDS_LIVE_QUOTE_RECHECK"


def test_watchlist_with_valid_quote_is_review_or_high_quality():
    result = evaluate_checklist_row(_candidate(signal="WATCHLIST", final_trade_score=82))

    assert result["checklist_status"] in {"REVIEW_MANUALLY", "HIGH_QUALITY_REVIEW"}
    assert result["checklist_status"] != "BLOCKED"


def test_market_cap_below_two_point_five_billion_is_blocked():
    result = evaluate_checklist_row(_candidate(market_cap=2_499_999_999))

    assert result["checklist_status"] == "BLOCKED"
    assert "market_cap_below_minimum" in result["checklist_blockers"]


def test_market_cap_at_two_point_five_billion_is_allowed():
    result = evaluate_checklist_row(_candidate(market_cap=2_500_000_000))

    assert result["checklist_status"] != "BLOCKED"
    assert "market_cap_below_minimum" not in result["checklist_blockers"]


def test_crowded_bullish_adds_contrarian_warning():
    result = evaluate_checklist_row(_candidate(options_bias="CROWDED_BULLISH"))

    assert "crowded_bullish_contrarian" in result["checklist_warnings"]


def test_unknown_options_flow_does_not_block():
    result = evaluate_checklist_row(_candidate(options_bias="UNKNOWN_OPTIONS_FLOW"))

    assert result["checklist_status"] != "BLOCKED"
    assert "options_unknown_non_blocking" in result["checklist_warnings"]


def test_build_dataframe_never_creates_buy_or_trigger():
    df = pd.DataFrame(
        [
            _candidate(ticker="AAA", signal="WATCHLIST"),
            _candidate(ticker="BBB", signal="VETO"),
        ]
    )

    out = build_trade_decision_checklist_dataframe(df, root=Path("unused"))

    assert "BUY_SETUP_ACTIVE" not in set(out["signal"].astype(str))
    assert set(out["signal"].astype(str)) == {"WATCHLIST", "VETO"}
    assert "TRIGGER_CONFIRMED" not in set(out["checklist_status"].astype(str))


def test_save_trade_decision_checklist_reports_writes_csv_json_md(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()
    input_csv = reports / "manual_review_top.csv"
    pd.DataFrame([_candidate()]).to_csv(input_csv, index=False)

    result = save_trade_decision_checklist_reports(
        input_path=input_csv,
        csv_out=reports / "trade_decision_checklist_latest.csv",
        markdown_out=reports / "trade_decision_checklist_latest.md",
        json_out=reports / "trade_decision_checklist_latest.json",
        root=tmp_path,
    )

    assert result["status"] == "PASS"
    assert result["rows"] == 1
    assert (reports / "trade_decision_checklist_latest.csv").exists()
    assert (reports / "trade_decision_checklist_latest.md").exists()
    assert (reports / "trade_decision_checklist_latest.json").exists()

    payload = json.loads((reports / "trade_decision_checklist_latest.json").read_text(encoding="utf-8"))
    assert payload["high_quality_review"] + payload["review_manually"] == 1


def test_daily_validation_has_optional_trade_decision_checklist_after_live_recheck():
    post_names = [item["name"] for item in daily_validation.POST_SUMMARY_STEPS]

    assert "trade_decision_checklist" in post_names
    assert post_names.index("live_quote_recheck") < post_names.index("trade_decision_checklist")

    step = next(item for item in daily_validation.POST_SUMMARY_STEPS if item["name"] == "trade_decision_checklist")
    assert step["required"] is False
    assert "tools/trade_decision_checklist.py" in step["cmd"]
    assert "reports/trade_decision_checklist_latest.csv" in step["cmd"]
    assert "reports/trade_decision_checklist_latest.md" in step["cmd"]
    assert "reports/trade_decision_checklist_latest.json" in step["cmd"]


def test_daily_operator_index_renders_trade_decision_checklist_summary():
    text = build_daily_operator_index_markdown(
        {
            "generated_at": "2026-06-11T00:00:00",
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
            "trade_decision_checklist": {
                "available": True,
                "status": "PASS",
                "rows": 4,
                "blocked": 1,
                "needs_live_quote_recheck": 1,
                "review_manually": 1,
                "high_quality_review": 1,
            },
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

    assert "## Trade decision checklist" in text
    assert "- high_quality_review: 1" in text
    assert "HIGH_QUALITY_REVIEW no equivale a compra automatica" in text


def test_daily_run_manifest_tracks_trade_decision_checklist_outputs():
    assert "tools/trade_decision_checklist.py" in KEY_SCRIPT_PATHS
    assert "reports/trade_decision_checklist_latest.csv" in KEY_REPORT_PATHS
    assert "reports/trade_decision_checklist_latest.md" in KEY_REPORT_PATHS
    assert "reports/trade_decision_checklist_latest.json" in KEY_REPORT_PATHS
