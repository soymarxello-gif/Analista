from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.manual_review_top import (
    build_manual_review_top_dataframe,
    classify_top_group,
    save_manual_review_top_reports,
)


def test_classify_high_quality_operational_candidate():
    row = {
        "signal": "WATCHLIST",
        "recommendation": "WATCHLIST_MONITOR",
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
        "final_trade_score": 78,
        "setup_quality_score": 75,
        "setup_persistence_score": 70,
        "rr": 2.1,
    }

    assert classify_top_group(row) == "1_ALTA_CALIDAD_OPERATIVA"


def test_classify_quote_recheck_candidate():
    row = {
        "signal": "WATCHLIST",
        "recommendation": "RECHECK_LIVE_QUOTE",
        "quote_status": "STALE_POSSIBLE",
        "execution_quote_quality": "LOW",
        "final_trade_score": 85,
        "setup_quality_score": 90,
        "setup_persistence_score": 79,
        "rr": 2.5,
    }

    assert classify_top_group(row) == "2_REQUIERE_RECHECK_QUOTE"


def test_classify_deteriorated_candidate():
    row = {
        "signal": "AVOID",
        "recommendation": "AVOID_FOR_NOW",
        "setup_persistence_bucket": "D_WEAK_OR_DETERIORATED",
        "persistence_penalty_reason": "signal_deteriorated",
    }

    assert classify_top_group(row) == "4_DETERIORADO_O_DEBIL"


def test_build_manual_review_top_preserves_group_order():
    df = pd.DataFrame(
        [
            {
                "rank": 2,
                "ticker": "BBB",
                "signal": "WATCHLIST",
                "recommendation": "RECHECK_LIVE_QUOTE",
                "quote_status": "STALE_POSSIBLE",
                "execution_quote_quality": "LOW",
                "setup_persistence_score": 79,
                "final_trade_score": 85,
                "setup_quality_score": 80,
                "rr": 2.0,
            },
            {
                "rank": 1,
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "setup_persistence_score": 75,
                "final_trade_score": 80,
                "setup_quality_score": 78,
                "rr": 2.2,
            },
        ]
    )

    out = build_manual_review_top_dataframe(df)

    assert out.iloc[0]["ticker"] == "AAA"
    assert out.iloc[0]["_top_group"] == "1_ALTA_CALIDAD_OPERATIVA"
    assert out.iloc[1]["ticker"] == "BBB"
    assert out.iloc[1]["_top_group"] == "2_REQUIERE_RECHECK_QUOTE"


def test_save_manual_review_top_reports_writes_files(tmp_path: Path):
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
                "setup_persistence_score": 75,
                "final_trade_score": 80,
                "setup_quality_score": 78,
                "rr": 2.2,
            }
        ]
    ).to_csv(manual_csv, index=False)

    result = save_manual_review_top_reports(
        manual_csv=manual_csv,
        csv_out=reports / "manual_review_top.csv",
        markdown_out=reports / "manual_review_top.md",
    )

    assert result["status"] == "PASS"
    assert (reports / "manual_review_top.csv").exists()
    assert (reports / "manual_review_top.md").exists()