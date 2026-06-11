from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.setup_persistence_score import (
    build_setup_persistence_dataframe,
    calculate_setup_persistence_score,
    save_setup_persistence_reports,
)


def test_promoted_trigger_gets_high_persistence_score():
    row = {
        "ticker": "AAA",
        "appearances": 3,
        "latest_signal": "TRIGGER_CONFIRMED",
        "latest_recommendation": "MANUAL_REVIEW_TRIGGER_CONFIRMED",
        "latest_quote_status": "VALID",
        "latest_execution_quote_quality": "HIGH",
        "latest_in_manual_review": True,
        "promoted_to_trigger": True,
        "persistent_watchlist": True,
        "was_trigger_confirmed": True,
        "score_delta": 12,
        "rank_delta": 8,
        "manual_quote_recheck_count": 0,
        "deteriorated_signal": False,
        "disappeared_from_manual_review": False,
    }

    result = calculate_setup_persistence_score(row)

    assert result["setup_persistence_score"] >= 80
    assert result["setup_persistence_bucket"] == "A_PERSISTENT_HIGH_QUALITY"
    assert "promoted_to_trigger" in result["persistence_bonus_reason"]


def test_deteriorated_disappeared_setup_gets_low_score():
    row = {
        "ticker": "BBB",
        "appearances": 2,
        "latest_signal": "AVOID",
        "latest_recommendation": "AVOID_FOR_NOW",
        "latest_quote_status": "STALE_POSSIBLE",
        "latest_execution_quote_quality": "LOW",
        "latest_in_manual_review": False,
        "promoted_to_trigger": False,
        "persistent_watchlist": False,
        "was_trigger_confirmed": False,
        "score_delta": -20,
        "rank_delta": -50,
        "manual_quote_recheck_count": 3,
        "deteriorated_signal": True,
        "disappeared_from_manual_review": True,
    }

    result = calculate_setup_persistence_score(row)

    assert result["setup_persistence_score"] < 50
    assert result["setup_persistence_bucket"] == "D_WEAK_OR_DETERIORATED"
    assert "signal_deteriorated" in result["persistence_penalty_reason"]


def test_build_setup_persistence_dataframe_adds_columns():
    evolution = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "appearances": 3,
                "latest_signal": "TRIGGER_CONFIRMED",
                "latest_recommendation": "MANUAL_REVIEW_TRIGGER_CONFIRMED",
                "latest_quote_status": "VALID",
                "latest_execution_quote_quality": "HIGH",
                "latest_in_manual_review": True,
                "promoted_to_trigger": True,
                "persistent_watchlist": True,
                "was_trigger_confirmed": True,
                "score_delta": 10,
                "rank_delta": 5,
                "manual_quote_recheck_count": 0,
                "deteriorated_signal": False,
                "disappeared_from_manual_review": False,
            }
        ]
    )

    out = build_setup_persistence_dataframe(evolution)

    assert "setup_persistence_score" in out.columns
    assert "setup_persistence_bucket" in out.columns
    assert "persistence_bonus_reason" in out.columns
    assert "persistence_penalty_reason" in out.columns
    assert len(out) == 1


def test_save_setup_persistence_reports_writes_files(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()

    evolution_csv = reports / "history_evolution_latest.csv"
    pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "appearances": 3,
                "latest_signal": "TRIGGER_CONFIRMED",
                "latest_recommendation": "MANUAL_REVIEW_TRIGGER_CONFIRMED",
                "latest_quote_status": "VALID",
                "latest_execution_quote_quality": "HIGH",
                "latest_in_manual_review": True,
                "promoted_to_trigger": True,
                "persistent_watchlist": True,
                "was_trigger_confirmed": True,
                "score_delta": 10,
                "rank_delta": 5,
                "manual_quote_recheck_count": 0,
                "deteriorated_signal": False,
                "disappeared_from_manual_review": False,
            }
        ]
    ).to_csv(evolution_csv, index=False)

    result = save_setup_persistence_reports(
        evolution_csv=evolution_csv,
        csv_out=reports / "setup_persistence_latest.csv",
        markdown_out=reports / "setup_persistence_latest.md",
    )

    assert result["status"] == "PASS"
    assert (reports / "setup_persistence_latest.csv").exists()
    assert (reports / "setup_persistence_latest.md").exists()


def test_recheck_live_quote_caps_persistence_score_below_a_bucket():
    row = {
        "ticker": "AAA",
        "appearances": 7,
        "latest_signal": "WATCHLIST",
        "latest_recommendation": "RECHECK_LIVE_QUOTE",
        "latest_quote_status": "STALE_POSSIBLE",
        "latest_execution_quote_quality": "LOW",
        "latest_in_manual_review": True,
        "promoted_to_trigger": False,
        "persistent_watchlist": True,
        "was_trigger_confirmed": False,
        "score_delta": 35,
        "rank_delta": 250,
        "manual_quote_recheck_count": 2,
        "deteriorated_signal": False,
        "disappeared_from_manual_review": False,
    }

    result = calculate_setup_persistence_score(row)

    assert result["setup_persistence_score"] <= 79
    assert result["setup_persistence_bucket"] == "B_PERSISTENT_WATCHLIST_OR_RECHECK"
    assert "score_capped_by_quote_recheck" in result["persistence_penalty_reason"]