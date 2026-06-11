from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.live_quote_recheck import (
    build_live_quote_recheck_dataframe,
    is_quote_recheck_candidate,
    save_live_quote_recheck_reports,
    select_recheck_candidates,
    validate_live_quote,
)


def test_is_quote_recheck_candidate_by_recommendation():
    row = {
        "recommendation": "RECHECK_LIVE_QUOTE",
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
    }

    assert is_quote_recheck_candidate(row) is True


def test_validate_live_quote_valid():
    result = validate_live_quote(
        last_price=100.0,
        bid=99.9,
        ask=100.1,
        max_quote_distance_pct=0.10,
        max_spread_pct=0.03,
    )

    assert result["live_quote_status"] == "VALID"
    assert result["live_execution_quote_quality"] == "HIGH"
    assert result["live_recheck_decision"] == "QUOTE_OK_FOR_MANUAL_REVIEW"


def test_validate_live_quote_stale():
    result = validate_live_quote(
        last_price=100.0,
        bid=80.0,
        ask=81.0,
        max_quote_distance_pct=0.10,
        max_spread_pct=0.03,
    )

    assert result["live_quote_status"] == "STALE_POSSIBLE"
    assert result["live_execution_quote_quality"] == "LOW"
    assert result["live_recheck_decision"] == "QUOTE_STILL_UNCONFIRMED"


def test_select_recheck_candidates_filters_manual_review():
    df = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "recommendation": "WATCHLIST_MONITOR",
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
            },
            {
                "ticker": "BBB",
                "recommendation": "RECHECK_LIVE_QUOTE",
                "quote_status": "STALE_POSSIBLE",
                "execution_quote_quality": "LOW",
            },
        ]
    )

    out = select_recheck_candidates(df)

    assert out["ticker"].tolist() == ["BBB"]


def test_build_live_quote_recheck_dataframe_with_fake_fetcher():
    df = pd.DataFrame(
        [
            {
                "rank": 1,
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "RECHECK_LIVE_QUOTE",
                "quote_status": "STALE_POSSIBLE",
                "execution_quote_quality": "LOW",
                "setup_persistence_score": 79,
                "final_trade_score": 84,
                "rr": 2.0,
            }
        ]
    )

    def fake_fetcher(ticker: str) -> dict:
        return {
            "ticker": ticker,
            "live_fetch_status": "PASS",
            "live_fetch_error": "",
            "live_price": 100.0,
            "live_bid": 99.9,
            "live_ask": 100.1,
            "live_source": "fake",
        }

    out = build_live_quote_recheck_dataframe(df, fetcher=fake_fetcher)

    assert len(out) == 1
    assert out.iloc[0]["ticker"] == "AAA"
    assert out.iloc[0]["live_recheck_decision"] == "QUOTE_OK_FOR_MANUAL_REVIEW"
    assert out.iloc[0]["live_quote_status"] == "VALID"


def test_save_live_quote_recheck_reports_writes_files(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    manual_csv = reports / "manual_review_latest.csv"

    pd.DataFrame(
        [
            {
                "rank": 1,
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
            }
        ]
    ).to_csv(manual_csv, index=False)

    result = save_live_quote_recheck_reports(
        manual_csv=manual_csv,
        csv_out=reports / "live_quote_recheck_latest.csv",
        markdown_out=reports / "live_quote_recheck_latest.md",
        max_tickers=10,
    )

    assert result["status"] in {"PASS", "WARN"}
    assert (reports / "live_quote_recheck_latest.csv").exists()
    assert (reports / "live_quote_recheck_latest.md").exists()