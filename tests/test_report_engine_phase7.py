from __future__ import annotations

from pathlib import Path

import pandas as pd

from engine.report_engine import add_recommendations, recommendation_for_row, save_reports


def test_recommendation_for_veto():
    row = {
        "signal": "VETO",
        "execution_quote_quality": "HIGH",
        "quote_status": "VALID",
        "setup_type": "PULLBACK",
        "trigger_confirmed": True,
    }

    assert recommendation_for_row(row) == "DO_NOT_TRADE"


def test_recommendation_for_low_quote_confirmed_trigger():
    row = {
        "signal": "WATCHLIST",
        "execution_quote_quality": "LOW",
        "quote_status": "STALE_POSSIBLE",
        "setup_type": "PULLBACK",
        "trigger_confirmed": True,
    }

    assert recommendation_for_row(row) == "RECHECK_LIVE_QUOTE"


def test_recommendation_for_watchlist_valid_setup():
    row = {
        "signal": "WATCHLIST",
        "execution_quote_quality": "HIGH",
        "quote_status": "VALID",
        "setup_type": "PULLBACK",
        "trigger_confirmed": False,
    }

    assert recommendation_for_row(row) == "WATCHLIST_MONITOR"


def test_add_recommendations_adds_column():
    df = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "signal": "VETO",
                "execution_quote_quality": "LOW",
                "quote_status": "MISSING",
                "setup_type": "NO_VALID_SETUP",
                "trigger_confirmed": False,
            }
        ]
    )

    out = add_recommendations(df)

    assert "recommendation" in out.columns
    assert out.loc[0, "recommendation"] == "DO_NOT_TRADE"


def test_save_reports_creates_csv_json_markdown_html(tmp_path: Path):
    df = pd.DataFrame(
        [
            {
                "rank": 1,
                "ticker": "AAA",
                "company": "AAA Corp",
                "sector": "Technology",
                "signal": "WATCHLIST",
                "setup_type": "PULLBACK",
                "trigger_confirmed": False,
                "execution_quote_quality": "HIGH",
                "quote_status": "VALID",
                "final_trade_score": 72.5,
                "asset_quality_score": 80.0,
                "setup_quality_score": 70.0,
                "final_score": 75.0,
                "rr": 2.4,
                "actionable_entry": 100.0,
                "actionable_stop": 95.0,
                "actionable_target": 112.0,
                "reason_summary": "PULLBACK | score 75 | R:R 2.4",
            }
        ]
    )

    json_path = tmp_path / "latest.json"
    csv_path = tmp_path / "latest.csv"
    md_path = tmp_path / "latest.md"
    html_path = tmp_path / "latest.html"

    save_reports(
        df,
        {"outputs": {"files": {"history_dir": str(tmp_path / "history")}}},
        json_out=str(json_path),
        csv_out=str(csv_path),
        markdown_out=str(md_path),
        html_out=str(html_path),
    )

    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()
    assert html_path.exists()

    csv_df = pd.read_csv(csv_path)
    assert "recommendation" in csv_df.columns
    assert csv_df.loc[0, "recommendation"] == "WATCHLIST_MONITOR"

    assert "Analista" in md_path.read_text(encoding="utf-8")
    assert "<html" in html_path.read_text(encoding="utf-8").lower()