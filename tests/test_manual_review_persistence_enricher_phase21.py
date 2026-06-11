from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.manual_review_persistence_enricher import (
    enrich_manual_review_with_persistence,
    save_enriched_manual_review_reports,
)


def test_enrich_manual_review_preserves_order_and_adds_persistence(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    manual_csv = reports / "manual_review_latest.csv"
    persistence_csv = reports / "setup_persistence_latest.csv"

    pd.DataFrame(
        [
            {"rank": 2, "ticker": "BBB", "signal": "WATCHLIST"},
            {"rank": 1, "ticker": "AAA", "signal": "WATCHLIST"},
        ]
    ).to_csv(manual_csv, index=False)

    pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "setup_persistence_score": 90,
                "setup_persistence_bucket": "A_PERSISTENT_HIGH_QUALITY",
                "appearances": 5,
                "signal_path": "WATCHLIST",
                "score_delta": 10,
                "rank_delta": 3,
                "persistence_bonus_reason": "persistent_watchlist",
                "persistence_penalty_reason": "",
            },
            {
                "ticker": "BBB",
                "setup_persistence_score": 70,
                "setup_persistence_bucket": "B_PERSISTENT_WATCHLIST_OR_RECHECK",
                "appearances": 3,
                "signal_path": "AVOID -> WATCHLIST",
                "score_delta": 5,
                "rank_delta": 1,
                "persistence_bonus_reason": "rank_improved",
                "persistence_penalty_reason": "quote_recheck_required",
            },
        ]
    ).to_csv(persistence_csv, index=False)

    out, result = enrich_manual_review_with_persistence(
        manual_csv=manual_csv,
        persistence_csv=persistence_csv,
    )

    assert result["status"] == "PASS"
    assert result["rows"] == 2
    assert result["matched"] == 2
    assert out["ticker"].tolist() == ["BBB", "AAA"]
    assert "setup_persistence_score" in out.columns
    assert "setup_persistence_bucket" in out.columns
    assert out.loc[out["ticker"] == "AAA", "setup_persistence_score"].iloc[0] == 90


def test_enrich_manual_review_missing_persistence_is_warn(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    manual_csv = reports / "manual_review_latest.csv"
    persistence_csv = reports / "setup_persistence_latest.csv"

    pd.DataFrame(
        [
            {"rank": 1, "ticker": "AAA", "signal": "WATCHLIST"},
        ]
    ).to_csv(manual_csv, index=False)

    out, result = enrich_manual_review_with_persistence(
        manual_csv=manual_csv,
        persistence_csv=persistence_csv,
    )

    assert result["status"] == "WARN"
    assert result["rows"] == 1
    assert result["matched"] == 0
    assert "setup_persistence_score" in out.columns


def test_save_enriched_manual_review_reports_writes_files(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    manual_csv = reports / "manual_review_latest.csv"
    persistence_csv = reports / "setup_persistence_latest.csv"

    pd.DataFrame(
        [
            {"rank": 1, "ticker": "AAA", "signal": "WATCHLIST"},
        ]
    ).to_csv(manual_csv, index=False)

    pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "setup_persistence_score": 90,
                "setup_persistence_bucket": "A_PERSISTENT_HIGH_QUALITY",
            },
        ]
    ).to_csv(persistence_csv, index=False)

    result = save_enriched_manual_review_reports(
        manual_csv=manual_csv,
        persistence_csv=persistence_csv,
        csv_out=reports / "manual_review_latest.csv",
        markdown_out=reports / "manual_review_latest.md",
    )

    assert result["status"] == "PASS"
    assert (reports / "manual_review_latest.csv").exists()
    assert (reports / "manual_review_latest.md").exists()

    saved = pd.read_csv(reports / "manual_review_latest.csv")
    assert "setup_persistence_score" in saved.columns


from tools.manual_review_persistence_enricher import fill_missing_recommendations


def test_fill_missing_recommendations_from_signal_and_quote_status():
    df = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": None,
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
            },
            {
                "ticker": "BBB",
                "signal": "WATCHLIST",
                "recommendation": None,
                "quote_status": "STALE_POSSIBLE",
                "execution_quote_quality": "LOW",
            },
            {
                "ticker": "CCC",
                "signal": "TRIGGER_CONFIRMED",
                "recommendation": None,
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
            },
        ]
    )

    out = fill_missing_recommendations(df)

    assert out.loc[out["ticker"] == "AAA", "recommendation"].iloc[0] == "WATCHLIST_MONITOR"
    assert out.loc[out["ticker"] == "BBB", "recommendation"].iloc[0] == "RECHECK_LIVE_QUOTE"
    assert (
        out.loc[out["ticker"] == "CCC", "recommendation"].iloc[0]
        == "MANUAL_REVIEW_TRIGGER_CONFIRMED"
    )    