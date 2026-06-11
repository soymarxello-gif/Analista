from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools import daily_validation
from tools.daily_operator_index import build_daily_operator_index_markdown
from tools.daily_run_manifest import KEY_REPORT_PATHS, KEY_SCRIPT_PATHS
from tools.live_quote_recheck import (
    OUTPUT_COLUMNS,
    build_live_quote_recheck_dataframe,
    save_live_quote_recheck_reports,
)


def _candidate(**overrides) -> dict:
    row = {
        "rank": 1,
        "ticker": "AAA",
        "signal": "WATCHLIST",
        "recommendation": "RECHECK_LIVE_QUOTE",
        "quote_status": "MISSING",
        "execution_quote_quality": "LOW",
        "actionable_entry": 100.0,
        "actionable_stop": 95.0,
        "actionable_target": 112.0,
        "rr": 2.4,
    }
    row.update(overrides)
    return row


def _quote(price=100.0, bid=99.9, ask=100.1, status="PASS") -> dict:
    return {
        "live_fetch_status": status,
        "live_fetch_error": "" if status == "PASS" else "quote_unavailable",
        "live_price": price,
        "live_bid": bid,
        "live_ask": ask,
        "live_quote_source": "MOCK",
    }


def test_missing_input_returns_controlled_fail_and_outputs(tmp_path: Path):
    reports = tmp_path / "reports"

    result = save_live_quote_recheck_reports(
        input_csv=reports / "missing.csv",
        csv_out=reports / "live_quote_recheck_latest.csv",
        markdown_out=reports / "live_quote_recheck_latest.md",
        json_out=reports / "live_quote_recheck_latest.json",
    )

    assert result["status"] == "FAIL"
    assert result["rows"] == 0
    assert result["error"] == "input_csv_not_found"
    assert (reports / "live_quote_recheck_latest.csv").exists()
    assert (reports / "live_quote_recheck_latest.md").exists()
    assert (reports / "live_quote_recheck_latest.json").exists()


def test_input_without_recheck_candidates_passes_rows_zero(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()
    input_csv = reports / "manual_review_latest.csv"
    pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "recommendation": "WATCHLIST_MONITOR",
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
            }
        ]
    ).to_csv(input_csv, index=False)

    result = save_live_quote_recheck_reports(
        input_csv=input_csv,
        csv_out=reports / "live_quote_recheck_latest.csv",
        markdown_out=reports / "live_quote_recheck_latest.md",
        json_out=reports / "live_quote_recheck_latest.json",
        fetcher=lambda _ticker: _quote(),
    )

    out = pd.read_csv(reports / "live_quote_recheck_latest.csv")
    payload = json.loads((reports / "live_quote_recheck_latest.json").read_text(encoding="utf-8"))

    assert result["status"] == "PASS"
    assert result["rows"] == 0
    assert payload["rows"] == 0
    assert list(out.columns) == OUTPUT_COLUMNS


def test_valid_live_quote_low_spread_near_entry_is_execution_ok_manual_only():
    df = pd.DataFrame([_candidate()])

    out = build_live_quote_recheck_dataframe(df, fetcher=lambda _ticker: _quote())

    row = out.iloc[0]
    assert row["recheck_decision"] == "EXECUTION_OK_REVIEW_MANUALLY"
    assert row["live_quote_status"] == "VALID"
    assert row["live_execution_quote_quality"] == "HIGH"
    assert row["manual_review_required"] is True or str(row["manual_review_required"]).lower() == "true"
    assert "signal" not in out.columns
    assert "TRIGGER_CONFIRMED" not in set(out["recheck_decision"].astype(str))


def test_live_quote_missing_returns_data_unavailable():
    df = pd.DataFrame([_candidate()])

    out = build_live_quote_recheck_dataframe(
        df,
        fetcher=lambda _ticker: _quote(price=None, bid=None, ask=None, status="FAIL"),
    )

    assert out.iloc[0]["recheck_decision"] == "DATA_UNAVAILABLE"
    assert out.iloc[0]["live_quote_status"] == "MISSING"


def test_high_spread_returns_avoid_execution_risk():
    df = pd.DataFrame([_candidate()])

    out = build_live_quote_recheck_dataframe(
        df,
        fetcher=lambda _ticker: _quote(price=100.0, bid=97.0, ask=103.0),
        max_spread_pct=0.03,
    )

    assert out.iloc[0]["recheck_decision"] == "AVOID_EXECUTION_RISK"
    assert out.iloc[0]["live_quote_status"] == "WIDE_OR_INCOHERENT"


def test_price_too_far_from_entry_returns_monitor_or_avoid():
    df = pd.DataFrame([_candidate()])

    out = build_live_quote_recheck_dataframe(
        df,
        fetcher=lambda _ticker: _quote(price=103.0, bid=102.95, ask=103.05),
        entry_band_pct=0.02,
        avoid_price_distance_pct=0.05,
    )

    assert out.iloc[0]["recheck_decision"] in {"WATCHLIST_MONITOR", "AVOID_EXECUTION_RISK"}
    assert bool(out.iloc[0]["price_within_entry_band"]) is False


def test_missing_entry_stop_target_never_execution_ok():
    df = pd.DataFrame(
        [
            _candidate(
                actionable_entry=None,
                actionable_stop=None,
                actionable_target=None,
            )
        ]
    )

    out = build_live_quote_recheck_dataframe(df, fetcher=lambda _ticker: _quote())

    assert out.iloc[0]["recheck_decision"] != "EXECUTION_OK_REVIEW_MANUALLY"
    assert out.iloc[0]["recheck_decision"] in {"KEEP_RECHECK", "DATA_UNAVAILABLE"}


def test_invalid_live_rr_never_execution_ok():
    df = pd.DataFrame(
        [
            _candidate(
                actionable_entry=100.0,
                actionable_stop=99.0,
                actionable_target=100.5,
            )
        ]
    )

    out = build_live_quote_recheck_dataframe(df, fetcher=lambda _ticker: _quote(), min_live_rr=1.5)

    assert out.iloc[0]["recheck_decision"] == "KEEP_RECHECK"
    assert "live_rr_invalid_or_below_min" in out.iloc[0]["recheck_reason"]


def test_daily_validation_has_optional_live_quote_recheck_step():
    step = next(
        item for item in daily_validation.POST_SUMMARY_STEPS if item["name"] == "live_quote_recheck"
    )

    assert step["required"] is False
    assert "tools/live_quote_recheck.py" in step["cmd"]
    assert "reports/live_quote_recheck_latest.csv" in step["cmd"]
    assert "reports/live_quote_recheck_latest.md" in step["cmd"]
    assert "reports/live_quote_recheck_latest.json" in step["cmd"]


def test_daily_operator_index_renders_live_quote_recheck_summary():
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
            "recheck_count": 1,
            "signals": {"WATCHLIST": 1},
            "recommendations": {"RECHECK_LIVE_QUOTE": 1},
            "quote_recheck_priority": {},
            "quality_gate": {"available": False},
            "live_quote_recheck": {
                "available": True,
                "status": "PASS",
                "rows": 3,
                "execution_ok_review_manually": 1,
                "keep_recheck": 1,
                "watchlist_monitor": 0,
                "avoid_execution_risk": 1,
                "data_unavailable": 0,
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

    assert "## Live quote recheck" in text
    assert "- rows: 3" in text
    assert "- execution_ok_review_manually: 1" in text
    assert "EXECUTION_OK_REVIEW_MANUALLY no equivale a TRIGGER_CONFIRMED" in text


def test_daily_run_manifest_tracks_live_quote_recheck_outputs():
    assert "tools/live_quote_recheck.py" in KEY_SCRIPT_PATHS
    assert "reports/live_quote_recheck_latest.csv" in KEY_REPORT_PATHS
    assert "reports/live_quote_recheck_latest.md" in KEY_REPORT_PATHS
    assert "reports/live_quote_recheck_latest.json" in KEY_REPORT_PATHS
