from __future__ import annotations

import pandas as pd

from ui.view_models import (
    build_calibration_model,
    build_candidate_table_model,
    build_cycle_audit_model,
    build_followup_model,
    build_paper_trading_model,
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
        "rows_count": int(data.get("rows", 0) or data.get("journal_rows", 0) or 0),
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


def test_paper_trading_model_counts_manual_decisions():
    journal = pd.DataFrame(
        [
            {"manual_decision": "PENDING_REVIEW", "followup_status": "OPEN_MONITORING"},
            {"manual_decision": "PAPER_WATCH", "followup_status": "OPEN_MONITORING"},
            {"manual_decision": "PAPER_ENTER", "followup_status": "ENTERED_PAPER"},
            {"manual_decision": "BLOCKED", "followup_status": "CLOSED_PAPER"},
        ]
    )
    close = pd.DataFrame(
        [
            {"followup_status": "CLOSED_PAPER", "outcome_exported": "False"},
            {"followup_status": "CLOSED_PAPER", "outcome_exported": "True"},
        ]
    )
    sources = {
        "sources": {
            "paper_trading_journal": _csv_source("paper_trading_journal", journal),
            "paper_trade_close": _csv_source("paper_trade_close", close),
        }
    }

    model = build_paper_trading_model(sources)

    assert model["summary"]["journal_rows"] == 4
    assert model["summary"]["pending_review"] == 1
    assert model["summary"]["paper_watch"] == 1
    assert model["summary"]["paper_enter"] == 1
    assert model["summary"]["blocked"] == 1
    assert model["summary"]["closed_paper"] == 1
    assert model["summary"]["pending_export"] == 1
    assert model["summary"]["exported_outcomes"] == 1


def test_cycle_audit_model_detects_warn_fail_without_traceback():
    sources = {
        "sources": {
            "paper_trading_cycle_audit": _json_source(
                "paper_trading_cycle_audit",
                {
                    "status": "WARN",
                    "journal_rows": 3,
                    "open_paper_count": 1,
                    "closed_paper_count": 0,
                    "pending_export_count": 0,
                    "exported_count": 0,
                    "duplicate_outcome_ids": [],
                    "warnings": ["sample incomplete"],
                    "issues": [],
                },
            )
        }
    }

    model = build_cycle_audit_model(sources)

    assert model["status"] == "WARN"
    assert model["summary"]["journal_rows"] == 3
    assert model["summary"]["guardrail_status"] == "PASS"


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


def test_quality_gate_and_followup_models_have_controlled_statuses():
    quality = build_quality_gate_model(
        {"sources": {"daily_quality_gate": _json_source("daily_quality_gate", {"status": "PASS"})}}
    )
    followup = build_followup_model(
        {"sources": {"paper_trade_followup": _csv_source("paper_trade_followup", pd.DataFrame())}}
    )

    assert quality["status"] == "PASS"
    assert followup["status"] == "EMPTY"
