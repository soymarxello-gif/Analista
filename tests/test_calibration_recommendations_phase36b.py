from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools import daily_validation
from tools.calibration_recommendations import (
    build_calibration_recommendations,
    build_calibration_recommendations_markdown,
    save_calibration_recommendations_reports,
)
from tools.daily_operator_index import build_daily_operator_index_markdown
from tools.daily_run_manifest import KEY_REPORT_PATHS, KEY_SCRIPT_PATHS


def _calibration_row(**overrides) -> dict:
    row = {
        "group": "OVERALL",
        "group_value": "ALL_CLOSED",
        "closed_trades": 0,
        "wins": 0,
        "losses": 0,
        "breakeven": 0,
        "win_rate": "",
        "avg_pnl_pct": "",
        "median_pnl_pct": "",
        "avg_r_multiple": "",
        "median_r_multiple": "",
        "total_r_multiple": "",
        "best_trade_r": "",
        "worst_trade_r": "",
        "avg_holding_days": "",
        "sample_size_warning": "sample too small",
    }
    row.update(overrides)
    return row


def _write_calibration(reports: Path, rows: list[dict], summary: dict) -> None:
    reports.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(reports / "trade_score_calibration_latest.csv", index=False)
    (reports / "trade_score_calibration_latest.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )


def test_missing_calibration_files_returns_controlled_warning(tmp_path: Path):
    reports = tmp_path / "reports"

    result = save_calibration_recommendations_reports(
        calibration_csv=reports / "missing.csv",
        calibration_json=reports / "missing.json",
        markdown_out=reports / "calibration_recommendations_latest.md",
        json_out=reports / "calibration_recommendations_latest.json",
        root=tmp_path,
    )

    assert result["status"] == "WARN"
    assert result["errors"]
    assert (reports / "calibration_recommendations_latest.md").exists()
    assert (reports / "calibration_recommendations_latest.json").exists()


def test_zero_closed_trades_generates_insufficient_sample(tmp_path: Path):
    reports = tmp_path / "reports"
    _write_calibration(
        reports,
        [_calibration_row()],
        {"status": "WARN", "closed_trades": 0, "sample_size_warning": "sample too small"},
    )

    result = save_calibration_recommendations_reports(
        calibration_csv=reports / "trade_score_calibration_latest.csv",
        calibration_json=reports / "trade_score_calibration_latest.json",
        markdown_out=reports / "calibration_recommendations_latest.md",
        json_out=reports / "calibration_recommendations_latest.json",
        root=tmp_path,
    )

    assert result["status"] == "WARN"
    assert result["closed_trades"] == 0
    assert result["recommendations"][0]["type"] == "INSUFFICIENT_SAMPLE"


def test_less_than_ten_closed_trades_does_not_suggest_weight_changes(tmp_path: Path):
    reports = tmp_path / "reports"
    _write_calibration(
        reports,
        [_calibration_row(closed_trades=4)],
        {"status": "WARN", "closed_trades": 4, "sample_size_warning": "sample too small"},
    )

    result = save_calibration_recommendations_reports(
        calibration_csv=reports / "trade_score_calibration_latest.csv",
        calibration_json=reports / "trade_score_calibration_latest.json",
        markdown_out=reports / "calibration_recommendations_latest.md",
        json_out=reports / "calibration_recommendations_latest.json",
        root=tmp_path,
    )

    types = {item["type"] for item in result["recommendations"]}
    assert "POSSIBLE_OVERWEIGHT" not in types
    assert "POSSIBLE_UNDERWEIGHT" not in types
    assert "NEED_MORE_TRADES" in types


def test_ten_or_more_closed_trades_allows_group_observations_without_automatic_changes():
    df = pd.DataFrame(
        [
            _calibration_row(closed_trades=12, sample_size_warning=""),
            _calibration_row(
                group="setup_type",
                group_value="PULLBACK",
                closed_trades=6,
                avg_r_multiple=0.9,
                sample_size_warning="",
            ),
            _calibration_row(
                group="final_trade_score_bucket",
                group_value="85_PLUS",
                closed_trades=6,
                avg_r_multiple=-0.4,
                sample_size_warning="",
            ),
        ]
    )

    result = build_calibration_recommendations(
        df,
        {"status": "PASS", "closed_trades": 12, "sample_size_warning": ""},
    )

    assert result["status"] == "PASS"
    assert result["do_not_change_automatically"] is True
    assert result["recommendation_count"] >= 2
    assert all("change weight to" not in item["suggested_review_item"].lower() for item in result["recommendations"])


def test_low_sample_groups_are_marked_insufficient():
    df = pd.DataFrame(
        [
            _calibration_row(closed_trades=12, sample_size_warning=""),
            _calibration_row(
                group="setup_type",
                group_value="BREAKOUT",
                closed_trades=3,
                avg_r_multiple=1.0,
                sample_size_warning="sample too small",
            ),
        ]
    )

    result = build_calibration_recommendations(
        df,
        {"status": "PASS", "closed_trades": 12, "sample_size_warning": ""},
    )

    assert any(item["sample_size_warning"] == "group sample too small" for item in result["recommendations"])


def test_json_payload_contains_do_not_change_automatically(tmp_path: Path):
    reports = tmp_path / "reports"
    _write_calibration(
        reports,
        [_calibration_row()],
        {"status": "WARN", "closed_trades": 0, "sample_size_warning": "sample too small"},
    )

    save_calibration_recommendations_reports(
        calibration_csv=reports / "trade_score_calibration_latest.csv",
        calibration_json=reports / "trade_score_calibration_latest.json",
        markdown_out=reports / "calibration_recommendations_latest.md",
        json_out=reports / "calibration_recommendations_latest.json",
        root=tmp_path,
    )

    payload = json.loads((reports / "calibration_recommendations_latest.json").read_text(encoding="utf-8"))
    assert payload["do_not_change_automatically"] is True


def test_markdown_contains_no_automatic_scoring_changes():
    data = build_calibration_recommendations(
        pd.DataFrame([_calibration_row()]),
        {"status": "WARN", "closed_trades": 0, "sample_size_warning": "sample too small"},
    )

    text = build_calibration_recommendations_markdown(data)

    assert "No automatic scoring changes" in text


def test_daily_validation_has_optional_recommendations_after_calibration():
    names = [item["name"] for item in daily_validation.DEFAULT_STEPS + daily_validation.POST_SUMMARY_STEPS]

    assert "calibration_recommendations" in names
    assert names.index("trade_score_calibration") < names.index("calibration_recommendations")

    step = next(
        item
        for item in daily_validation.DEFAULT_STEPS + daily_validation.POST_SUMMARY_STEPS
        if item["name"] == "calibration_recommendations"
    )
    assert step["required"] is False
    assert "tools/calibration_recommendations.py" in step["cmd"]
    assert "reports/calibration_recommendations_latest.md" in step["cmd"]
    assert "reports/calibration_recommendations_latest.json" in step["cmd"]


def test_daily_operator_index_renders_calibration_recommendations_summary():
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
            "trade_score_calibration": {"available": False},
            "calibration_recommendations": {
                "available": True,
                "status": "WARN",
                "closed_trades": 0,
                "recommendation_count": 2,
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

    assert "## Calibration recommendations" in text
    assert "- recommendation_count: 2" in text
    assert "reports/calibration_recommendations_latest.md" in text


def test_daily_run_manifest_tracks_calibration_recommendation_outputs():
    assert "tools/calibration_recommendations.py" in KEY_SCRIPT_PATHS
    assert "reports/calibration_recommendations_latest.md" in KEY_REPORT_PATHS
    assert "reports/calibration_recommendations_latest.json" in KEY_REPORT_PATHS


def test_outputs_do_not_create_disabled_signal_or_entry_signal():
    data = build_calibration_recommendations(
        pd.DataFrame([_calibration_row()]),
        {"status": "WARN", "closed_trades": 0, "sample_size_warning": "sample too small"},
    )
    rendered = json.dumps(data, ensure_ascii=False) + build_calibration_recommendations_markdown(data)
    disabled_buy_signal = "_".join(["BUY", "SETUP", "ACTIVE"])

    assert disabled_buy_signal not in rendered
    assert "TRIGGER_CONFIRMED" not in rendered
