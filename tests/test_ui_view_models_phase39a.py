from __future__ import annotations

import pandas as pd

from ui.view_models import (
    build_calibration_model,
    build_candidate_table_model,
    build_macro_context_model,
    build_quality_gate_model,
    build_status_overview,
)


def _csv_source(name: str, df: pd.DataFrame, status: str = "AVAILABLE") -> dict:
    return {
        "name": name,
        "kind": "csv",
        "status": status,
        "dataframe": df,
        "rows_count": len(df),
        "columns": list(df.columns),
    }


def _json_source(name: str, data: dict, status: str = "AVAILABLE") -> dict:
    return {
        "name": name,
        "kind": "json",
        "status": status,
        "data": data,
        "rows_count": int(data.get("rows", 0) or 0),
    }


def test_build_status_overview_works_with_empty_sources():
    model = build_status_overview({"sources": {}, "summary": {}})

    assert model["status"] == "PASS"
    assert model["title"] == "Status overview"


def test_candidate_table_model_works_without_manual_review_top():
    model = build_candidate_table_model({"sources": {}})

    assert model["status"] == "EMPTY"
    assert model["rows_count"] == 0


def test_candidate_table_model_preserves_critical_columns_when_present():
    df = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "checklist_status": "REVIEW_MANUALLY",
                "setup_type": "PULLBACK",
                "final_trade_score": "80",
                "checklist_score": "85",
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
                "actionable_entry": "100",
                "actionable_stop": "90",
                "actionable_target": "120",
                "rr": "2",
                "extra": "ignored",
            }
        ]
    )
    sources = {"sources": {"manual_review_top": _csv_source("manual_review_top", df)}}

    model = build_candidate_table_model(sources)

    assert model["status"] == "PASS"
    assert model["data"]["columns"] == [
        "ticker",
        "signal",
        "recommendation",
        "checklist_status",
        "setup_type",
        "final_trade_score",
        "checklist_score",
        "quote_status",
        "execution_quote_quality",
        "actionable_entry",
        "actionable_stop",
        "actionable_target",
        "rr",
    ]
    assert model["data"]["rows"][0]["ticker"] == "AAA"


def test_macro_context_model_exposes_fred_series_and_events():
    sources = {
        "sources": {
            "macro_event_context": _json_source(
                "macro_event_context",
                {
                    "status": "PASS",
                    "source": "FRED_AND_AUDITABLE_ECONOMIC_CALENDAR",
                    "data_freshness": "MIXED_OFFICIAL_RELEASE_FREQUENCIES",
                    "next_critical_event": "FOMC policy decision",
                    "next_critical_event_date": "2026-07-29",
                    "days_to_critical_event": 10,
                    "event_risk_status": "CLEAR",
                    "liquidity_context": "MIXED",
                    "us10y_official": 4.41,
                    "fred_series": {
                        "DGS10": {
                            "status": "PASS",
                            "latest_value": 4.41,
                            "latest_date": "2026-06-24",
                            "age_days": 2,
                            "change_value": -0.07,
                            "provider": "PANDAS_DATAREADER_FRED",
                            "cache_status": "REFRESHED",
                            "fallback_used": False,
                        }
                    },
                    "economic_calendar": {
                        "upcoming_events": [
                            {
                                "event_date": "2026-07-29",
                                "event_time": "14:00",
                                "timezone": "America/New_York",
                                "event_type": "FOMC",
                                "event_name": "FOMC policy decision",
                                "importance": "HIGH",
                                "source_url": "https://www.federalreserve.gov/",
                            }
                        ]
                    },
                },
            )
        }
    }

    model = build_macro_context_model(sources)

    assert model["status"] == "PASS"
    assert model["summary"]["liquidity_context"] == "MIXED"
    assert model["data"]["series_rows"][0]["series"] == "US10Y"
    assert model["data"]["series_rows"][0]["latest"] == 4.41
    assert model["data"]["event_rows"][0]["event"] == "FOMC"


def test_calibration_model_requires_observational_recommendations():
    sources = {
        "sources": {
            "trade_score_calibration": _json_source("trade_score_calibration", {"status": "WARN"}),
            "calibration_recommendations": _json_source(
                "calibration_recommendations",
                {"status": "WARN", "do_not_change_automatically": True},
            ),
        }
    }

    model = build_calibration_model(sources)

    assert model["summary"]["recommendations_are_observational"] is True
    assert model["summary"]["no_auto_weight_change"] is True


def test_quality_gate_model_exposes_freshness_status():
    quality = build_quality_gate_model(
        {
            "sources": {
                "daily_quality_gate": _json_source(
                    "daily_quality_gate",
                    {
                        "status": "PASS",
                        "scan_freshness_status": "PASS",
                        "scan_age_hours": 0.5,
                        "manual_review_age_hours": 0.4,
                        "macro_age_hours": 1.2,
                        "scan_is_current_local_date": True,
                    },
                )
            }
        }
    )

    assert quality["status"] == "PASS"
    assert quality["summary"]["scan_freshness_status"] == "PASS"
    assert quality["summary"]["scan_age_hours"] == 0.5
    assert quality["summary"]["scan_is_current_local_date"] is True
