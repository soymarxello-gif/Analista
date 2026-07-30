from __future__ import annotations

import pandas as pd

from tools.source_coverage_audit import build_source_coverage_report


def test_source_coverage_report_detects_metadata_missing():
    df = pd.DataFrame(
        [
            {
                "rank": 1,
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "sector": None,
                "industry": None,
                "quote_status": "MISSING",
                "execution_quote_quality": "LOW",
                "data_quality_score": 0.8,
                "core_data_quality_score": 1.0,
                "fundamental_data_quality_score": 0.6,
                "options_bias": "UNKNOWN_OPTIONS_FLOW",
            },
            {
                "rank": 2,
                "ticker": "BBB",
                "signal": "VETO",
                "recommendation": "DO_NOT_TRADE",
                "sector": "Technology",
                "industry": "Software",
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "data_quality_score": 0.95,
                "core_data_quality_score": 1.0,
                "fundamental_data_quality_score": 1.0,
                "options_bias": "BULLISH_WITH_DATA",
            },
        ]
    )

    report = build_source_coverage_report(df)

    assert report["rows"] == 2
    assert report["missing_rates"]["sector"] == 50.0
    assert report["missing_rates"]["industry"] == 50.0
    assert report["counts"]["metadata_missing"]["MISSING_SECTOR_OR_INDUSTRY"] == 1
    assert report["operable_missing_metadata"][0]["ticker"] == "AAA"


def test_source_coverage_report_handles_empty_dataframe():
    report = build_source_coverage_report(pd.DataFrame())

    assert report["rows"] == 0
    assert report["counts"] == {}


def test_source_coverage_excludes_intentionally_unrequested_metadata_from_rate():
    df = pd.DataFrame(
        [
            {
                "ticker": "RADAR",
                "sector": None,
                "industry": None,
                "market_cap": 3_000_000_000,
                "metadata_source": "NOT_REQUESTED_TECHNICAL_ASSESSMENT",
                "technical_analysis_lane": "RADAR_FORMING_SETUP",
            },
            {
                "ticker": "ADVANCE",
                "sector": "Technology",
                "industry": "Software",
                "market_cap": 10_000_000_000,
                "metadata_source": "yfinance",
                "technical_analysis_lane": "ADVANCE_DEEP_ANALYSIS",
            },
        ]
    )

    report = build_source_coverage_report(df)

    assert report["coverage_scopes"]["metadata_requested_rows"] == 1
    assert report["coverage_scopes"]["metadata_not_requested_rows"] == 1
    assert report["missing_rates"]["sector"] == 0.0
    assert report["missing_rates"]["industry"] == 0.0
    assert report["top_missing_metadata"] == []
