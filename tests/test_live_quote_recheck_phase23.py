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
    assert result["live_recheck_decision"] == "EXECUTION_OK_REVIEW_MANUALLY"


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
    assert result["live_recheck_decision"] == "KEEP_RECHECK"


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
                "actionable_entry": 100,
                "actionable_stop": 95,
                "actionable_target": 112,
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
            "live_quote_source": "FAKE",
        }

    out = build_live_quote_recheck_dataframe(df, fetcher=fake_fetcher)

    assert len(out) == 1
    assert out.iloc[0]["ticker"] == "AAA"
    assert out.iloc[0]["recheck_decision"] == "EXECUTION_OK_REVIEW_MANUALLY"
    assert out.iloc[0]["live_quote_status"] == "VALID"
    assert out.iloc[0]["prior_signal"] == "WATCHLIST"


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
        input_csv=manual_csv,
        csv_out=reports / "live_quote_recheck_latest.csv",
        markdown_out=reports / "live_quote_recheck_latest.md",
        json_out=reports / "live_quote_recheck_latest.json",
        max_tickers=10,
    )

    assert result["status"] == "PASS"
    assert result["rows"] == 0
    assert (reports / "live_quote_recheck_latest.csv").exists()
    assert (reports / "live_quote_recheck_latest.md").exists()
    assert (reports / "live_quote_recheck_latest.json").exists()


def _candidate(**overrides):
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


def test_missing_input_returns_controlled_fail_without_traceback(tmp_path: Path):
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
    assert "Input no encontrado" in (reports / "live_quote_recheck_latest.md").read_text(encoding="utf-8")


def test_quote_live_missing_returns_data_unavailable():
    df = pd.DataFrame([_candidate()])

    def fake_fetcher(_ticker: str) -> dict:
        return {
            "live_fetch_status": "FAIL",
            "live_fetch_error": "network_blocked",
            "live_price": None,
            "live_bid": None,
            "live_ask": None,
            "live_quote_source": "FAKE",
        }

    out = build_live_quote_recheck_dataframe(df, fetcher=fake_fetcher)

    assert out.iloc[0]["recheck_decision"] == "DATA_UNAVAILABLE"
    assert out.iloc[0]["live_quote_status"] == "MISSING"
    assert bool(out.iloc[0]["manual_review_required"]) is True


def test_spread_high_returns_avoid_execution_risk():
    df = pd.DataFrame([_candidate()])

    def fake_fetcher(_ticker: str) -> dict:
        return {
            "live_fetch_status": "PASS",
            "live_fetch_error": "",
            "live_price": 100.0,
            "live_bid": 97.0,
            "live_ask": 103.0,
            "live_quote_source": "FAKE",
        }

    out = build_live_quote_recheck_dataframe(df, fetcher=fake_fetcher, max_spread_pct=0.03)

    assert out.iloc[0]["recheck_decision"] == "AVOID_EXECUTION_RISK"
    assert out.iloc[0]["live_quote_status"] == "WIDE_OR_INCOHERENT"


def test_price_far_from_entry_returns_watchlist_or_avoid():
    df = pd.DataFrame([_candidate()])

    def fake_fetcher(_ticker: str) -> dict:
        return {
            "live_fetch_status": "PASS",
            "live_fetch_error": "",
            "live_price": 103.0,
            "live_bid": 102.95,
            "live_ask": 103.05,
            "live_quote_source": "FAKE",
        }

    out = build_live_quote_recheck_dataframe(
        df,
        fetcher=fake_fetcher,
        entry_band_pct=0.02,
        avoid_price_distance_pct=0.05,
    )

    assert out.iloc[0]["recheck_decision"] == "WATCHLIST_MONITOR"
    assert bool(out.iloc[0]["price_within_entry_band"]) is False


def test_missing_entry_stop_target_never_execution_ok():
    df = pd.DataFrame([_candidate(actionable_entry=None, actionable_stop=None, actionable_target=None)])

    def fake_fetcher(_ticker: str) -> dict:
        return {
            "live_fetch_status": "PASS",
            "live_fetch_error": "",
            "live_price": 100.0,
            "live_bid": 99.9,
            "live_ask": 100.1,
            "live_quote_source": "FAKE",
        }

    out = build_live_quote_recheck_dataframe(df, fetcher=fake_fetcher)

    assert out.iloc[0]["recheck_decision"] != "EXECUTION_OK_REVIEW_MANUALLY"
    assert out.iloc[0]["recheck_decision"] in {"KEEP_RECHECK", "DATA_UNAVAILABLE"}


def test_invalid_live_rr_never_execution_ok():
    df = pd.DataFrame([_candidate(actionable_entry=100, actionable_stop=99, actionable_target=100.5)])

    def fake_fetcher(_ticker: str) -> dict:
        return {
            "live_fetch_status": "PASS",
            "live_fetch_error": "",
            "live_price": 100.0,
            "live_bid": 99.95,
            "live_ask": 100.05,
            "live_quote_source": "FAKE",
        }

    out = build_live_quote_recheck_dataframe(df, fetcher=fake_fetcher, min_live_rr=1.5)

    assert out.iloc[0]["recheck_decision"] == "KEEP_RECHECK"
    assert "live_rr_invalid_or_below_min" in out.iloc[0]["recheck_reason"]
    assert "TRIGGER_CONFIRMED" not in set(out.columns)
