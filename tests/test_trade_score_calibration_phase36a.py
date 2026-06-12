from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools import daily_validation
from tools.daily_operator_index import build_daily_operator_index_markdown
from tools.daily_run_manifest import KEY_REPORT_PATHS, KEY_SCRIPT_PATHS
from tools.trade_score_calibration import (
    build_trade_score_calibration_dataframe,
    save_trade_score_calibration_reports,
    score_bucket,
)


def _trade(**overrides) -> dict:
    row = {
        "trade_id": "T1",
        "ticker": "AAA",
        "status": "CLOSED",
        "entry_date": "2026-01-01",
        "exit_date": "2026-01-06",
        "outcome": "WIN",
        "pnl_pct": 0.05,
        "r_multiple": 2.0,
        "source_signal": "WATCHLIST",
        "source_recommendation": "WATCHLIST_MONITOR",
        "source_setup_type": "BREAKOUT",
        "source_final_trade_score": 86,
        "source_setup_quality_score": 82,
        "source_setup_persistence_score": 75,
        "checklist_status": "REVIEW_MANUALLY",
        "checklist_score": 81,
        "institutional_score": 70,
        "options_bias": "NEUTRAL_WITH_DATA",
        "options_confidence": "HIGH",
        "sector": "Technology",
    }
    row.update(overrides)
    return row


def test_missing_outcomes_file_returns_controlled_warning_and_outputs(tmp_path: Path):
    reports = tmp_path / "reports"

    result = save_trade_score_calibration_reports(
        outcomes_path=tmp_path / "missing.csv",
        csv_out=reports / "trade_score_calibration_latest.csv",
        json_out=reports / "trade_score_calibration_latest.json",
        markdown_out=reports / "trade_score_calibration_latest.md",
        root=tmp_path,
    )

    assert result["status"] == "WARN"
    assert result["closed_trades"] == 0
    assert result["error"] == "input_csv_not_found"
    assert (reports / "trade_score_calibration_latest.csv").exists()
    assert (reports / "trade_score_calibration_latest.json").exists()
    assert (reports / "trade_score_calibration_latest.md").exists()


def test_empty_file_generates_controlled_zero_closed(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()
    outcomes = reports / "trade_outcomes.csv"
    pd.DataFrame(columns=["status", "outcome", "pnl_pct", "r_multiple"]).to_csv(outcomes, index=False)

    result = save_trade_score_calibration_reports(
        outcomes_path=outcomes,
        csv_out=reports / "trade_score_calibration_latest.csv",
        json_out=reports / "trade_score_calibration_latest.json",
        markdown_out=reports / "trade_score_calibration_latest.md",
        root=tmp_path,
    )

    assert result["status"] == "WARN"
    assert result["closed_trades"] == 0
    assert result["sample_size_warning"] == "sample too small"


def test_closed_trades_calculates_win_rate():
    df = pd.DataFrame(
        [
            _trade(outcome="WIN", r_multiple=2.0),
            _trade(trade_id="T2", outcome="LOSS", r_multiple=-1.0),
            _trade(trade_id="T3", outcome="BREAKEVEN", r_multiple=0.0),
        ]
    )

    out, _closed = build_trade_score_calibration_dataframe(df)
    overall = out[out["group"] == "OVERALL"].iloc[0]

    assert overall["closed_trades"] == 3
    assert overall["wins"] == 1
    assert overall["losses"] == 1
    assert overall["breakeven"] == 1
    assert overall["win_rate"] == 0.5


def test_calculates_avg_and_total_r_multiple():
    df = pd.DataFrame(
        [
            _trade(r_multiple=2.0),
            _trade(trade_id="T2", outcome="LOSS", r_multiple=-1.0),
            _trade(trade_id="T3", outcome="WIN", r_multiple=1.0),
        ]
    )

    out, _closed = build_trade_score_calibration_dataframe(df)
    overall = out[out["group"] == "OVERALL"].iloc[0]

    assert overall["avg_r_multiple"] == round((2.0 - 1.0 + 1.0) / 3, 6)
    assert overall["total_r_multiple"] == 2.0


def test_groups_by_checklist_status():
    df = pd.DataFrame(
        [
            _trade(checklist_status="REVIEW_MANUALLY"),
            _trade(trade_id="T2", checklist_status="NEEDS_LIVE_QUOTE_RECHECK", outcome="LOSS"),
        ]
    )

    out, _closed = build_trade_score_calibration_dataframe(df)
    grouped = out[out["group"] == "checklist_status"]

    assert set(grouped["group_value"]) == {"REVIEW_MANUALLY", "NEEDS_LIVE_QUOTE_RECHECK"}


def test_groups_by_setup_type():
    df = pd.DataFrame(
        [
            _trade(source_setup_type="BREAKOUT"),
            _trade(trade_id="T2", source_setup_type="PULLBACK", outcome="LOSS"),
        ]
    )

    out, _closed = build_trade_score_calibration_dataframe(df)
    grouped = out[out["group"] == "setup_type"]

    assert set(grouped["group_value"]) == {"BREAKOUT", "PULLBACK"}


def test_score_buckets_and_grouping():
    assert score_bucket(90) == "85_PLUS"
    assert score_bucket(80) == "75_TO_84"
    assert score_bucket(70) == "65_TO_74"
    assert score_bucket(50) == "BELOW_65"
    assert score_bucket("") == "MISSING"

    df = pd.DataFrame(
        [
            _trade(source_final_trade_score=90),
            _trade(trade_id="T2", source_final_trade_score=70, outcome="LOSS"),
        ]
    )
    out, _closed = build_trade_score_calibration_dataframe(df)
    grouped = out[out["group"] == "final_trade_score_bucket"]

    assert {"85_PLUS", "65_TO_74"}.issubset(set(grouped["group_value"]))


def test_insufficient_sample_sets_warning():
    df = pd.DataFrame([_trade()])

    out, _closed = build_trade_score_calibration_dataframe(df)
    overall = out[out["group"] == "OVERALL"].iloc[0]

    assert overall["sample_size_warning"] == "sample too small"


def test_save_does_not_modify_input_file(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()
    outcomes = reports / "trade_outcomes.csv"
    pd.DataFrame([_trade()]).to_csv(outcomes, index=False)
    before = outcomes.read_bytes()

    save_trade_score_calibration_reports(
        outcomes_path=outcomes,
        csv_out=reports / "trade_score_calibration_latest.csv",
        json_out=reports / "trade_score_calibration_latest.json",
        markdown_out=reports / "trade_score_calibration_latest.md",
        root=tmp_path,
    )

    assert outcomes.read_bytes() == before


def test_json_payload_contains_overall_metrics(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()
    outcomes = reports / "trade_outcomes.csv"
    pd.DataFrame([_trade(), _trade(trade_id="T2", outcome="LOSS", r_multiple=-1.0)]).to_csv(
        outcomes,
        index=False,
    )

    result = save_trade_score_calibration_reports(
        outcomes_path=outcomes,
        csv_out=reports / "trade_score_calibration_latest.csv",
        json_out=reports / "trade_score_calibration_latest.json",
        markdown_out=reports / "trade_score_calibration_latest.md",
        root=tmp_path,
    )
    payload = json.loads((reports / "trade_score_calibration_latest.json").read_text(encoding="utf-8"))

    assert result["closed_trades"] == 2
    assert payload["wins"] == 1
    assert payload["losses"] == 1


def test_daily_validation_has_optional_calibration_after_outcome_analytics():
    post_names = [item["name"] for item in daily_validation.DEFAULT_STEPS + daily_validation.POST_SUMMARY_STEPS]

    assert "trade_score_calibration" in post_names
    assert post_names.index("trade_outcome_analytics") < post_names.index("trade_score_calibration")

    step = next(
        item
        for item in daily_validation.DEFAULT_STEPS + daily_validation.POST_SUMMARY_STEPS
        if item["name"] == "trade_score_calibration"
    )
    assert step["required"] is False
    assert "tools/trade_score_calibration.py" in step["cmd"]
    assert "reports/trade_score_calibration_latest.csv" in step["cmd"]
    assert "reports/trade_score_calibration_latest.json" in step["cmd"]
    assert "reports/trade_score_calibration_latest.md" in step["cmd"]


def test_daily_operator_index_renders_calibration_summary():
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
            "trade_score_calibration": {
                "available": True,
                "status": "WARN",
                "closed_trades": 3,
                "win_rate": 0.5,
                "avg_r_multiple": 0.25,
                "sample_size_warning": "sample too small",
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

    assert "## Trade score calibration" in text
    assert "- closed_trades: 3" in text
    assert "sample too small" in text


def test_daily_run_manifest_tracks_calibration_outputs():
    assert "tools/trade_score_calibration.py" in KEY_SCRIPT_PATHS
    assert "reports/trade_score_calibration_latest.csv" in KEY_REPORT_PATHS
    assert "reports/trade_score_calibration_latest.json" in KEY_REPORT_PATHS
    assert "reports/trade_score_calibration_latest.md" in KEY_REPORT_PATHS


def test_outputs_do_not_create_disabled_signal_or_trigger():
    df = pd.DataFrame([_trade()])
    out, _closed = build_trade_score_calibration_dataframe(df)
    text = out.to_csv(index=False)
    disabled_buy_signal = "_".join(["BUY", "SETUP", "ACTIVE"])

    assert disabled_buy_signal not in text
    assert "TRIGGER_CONFIRMED" not in set(out["group_value"].astype(str))
