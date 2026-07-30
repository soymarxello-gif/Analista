from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from data.earnings_context import normalize_earnings_context
from scoring import risk_reward_score
from tools import daily_validation
from tools.live_quote_recheck import (
    build_live_quote_recheck_dataframe,
    build_recheck_input,
)
from tools.portfolio_concentration_audit import collect_audit
from tools.simple_candidate_posttest import persist_daily_candidate_memory


def test_earnings_days_are_recomputed_from_absolute_date():
    result = normalize_earnings_context(
        {
            "earnings_date": "2026-08-05",
            "days_to_earnings": 99,
            "earnings_cache_status": "HIT",
            "earnings_cache_age_minutes": 30,
        },
        as_of="2026-07-30",
    )

    assert result["days_to_earnings"] == 6
    assert result["earnings_days_recomputed"] is True
    assert result["earnings_event_status"] == "UPCOMING"
    assert result["earnings_consistency_status"] == "PASS"


def test_past_earnings_never_keep_positive_relative_days():
    result = normalize_earnings_context(
        {
            "earnings_date": "2026-07-20",
            "days_to_earnings": 12,
            "earnings_cache_status": "STALE_FALLBACK",
            "earnings_cache_age_minutes": 900,
        },
        as_of="2026-07-30",
    )

    assert result["days_to_earnings"] == -10
    assert result["earnings_event_status"] == "PAST_STALE"
    assert result["earnings_data_confidence"] == "LOW"
    assert result["earnings_refresh_required"] is True


def test_execution_candidate_blocked_by_quote_is_prioritized_for_recheck():
    scan = pd.DataFrame(
        [
            {
                "ticker": "GLPI",
                "decision_lane": "EXECUTION_CANDIDATE",
                "signal": "AVOID",
                "recommendation": "AVOID_FOR_NOW",
                "quote_status": "WIDE_OR_INCOHERENT",
                "execution_quote_quality": "LOW",
                "scenario_entry": 50.0,
                "scenario_stop": 48.0,
                "scenario_target": 54.0,
            },
            {
                "ticker": "LOWQ",
                "decision_lane": "TACTICAL_RESEARCH",
                "signal": "WATCHLIST",
                "quote_status": "MISSING",
                "execution_quote_quality": "LOW",
            },
        ]
    )
    manual = pd.DataFrame(
        [
            {
                "ticker": "LOWQ",
                "recommendation": "RECHECK_LIVE_QUOTE",
                "quote_status": "MISSING",
                "execution_quote_quality": "LOW",
            }
        ]
    )

    selected = build_recheck_input(manual, scan)

    assert list(selected["ticker"]) == ["GLPI", "LOWQ"]
    assert int(selected.iloc[0]["recheck_priority"]) == 0
    assert selected.iloc[0]["selection_origin"] == "LATEST_SCAN"


def test_scenario_levels_remain_diagnostic_in_live_recheck():
    input_df = pd.DataFrame(
        [
            {
                "ticker": "GLPI",
                "decision_lane": "EXECUTION_CANDIDATE",
                "signal": "AVOID",
                "recommendation": "AVOID_FOR_NOW",
                "quote_status": "WIDE_OR_INCOHERENT",
                "execution_quote_quality": "LOW",
                "scenario_entry": 50.0,
                "scenario_stop": 48.0,
                "scenario_target": 54.0,
            }
        ]
    )
    output = build_live_quote_recheck_dataframe(
        input_df,
        fetcher=lambda _ticker: {
            "live_fetch_status": "PASS",
            "live_price": 50.0,
            "live_bid": 49.95,
            "live_ask": 50.05,
            "live_quote_source": "MOCK",
        },
    )

    assert output.iloc[0]["prior_level_type"] == "SCENARIO_DIAGNOSTIC"
    assert output.iloc[0]["recheck_decision"] == "EXECUTION_OK_REVIEW_MANUALLY"
    assert "TRIGGER_CONFIRMED" not in output.astype(str).to_string()


def test_research_or_reset_lane_cannot_receive_execution_ok():
    input_df = pd.DataFrame(
        [
            {
                "ticker": "RADAR",
                "prior_decision_lane": "LEADERSHIP_RESET_WATCH",
                "recommendation": "RECHECK_LIVE_QUOTE",
                "quote_status": "MISSING",
                "execution_quote_quality": "LOW",
                "entry": 100.0,
                "stop": 98.0,
                "target": 104.0,
            }
        ]
    )
    output = build_live_quote_recheck_dataframe(
        input_df,
        fetcher=lambda _ticker: {
            "live_fetch_status": "PASS",
            "live_price": 100.0,
            "live_bid": 99.95,
            "live_ask": 100.05,
            "live_quote_source": "MOCK",
        },
    )

    assert output.iloc[0]["recheck_decision"] == "WATCHLIST_MONITOR"
    assert "technical_lane_not_execution_eligible" in output.iloc[0]["recheck_reason"]


def test_alpaca_delayed_is_corroboration_and_never_execution_high():
    input_df = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "recommendation": "RECHECK_LIVE_QUOTE",
                "quote_status": "MISSING",
                "execution_quote_quality": "LOW",
            }
        ]
    )
    output = build_live_quote_recheck_dataframe(
        input_df,
        fetcher=lambda _ticker: {
            "live_fetch_status": "FAIL",
            "live_price": None,
            "live_bid": None,
            "live_ask": None,
            "live_quote_source": "YAHOO_FINANCE",
        },
        alpaca_fetcher=lambda _tickers: {
            "AAA": {
                "status": "PASS",
                "analysis_price": 100.0,
                "analysis_bid": 99.9,
                "analysis_ask": 100.1,
                "analysis_quote_source": "ALPACA_IEX_READ_ONLY",
                "analysis_quote_timestamp": "2026-07-30T12:00:00+00:00",
                "analysis_quote_freshness": "DELAYED_15_MIN",
            }
        },
    )

    row = output.iloc[0]
    assert row["corroboration_source"] == "ALPACA_IEX_READ_ONLY"
    assert row["live_execution_quote_quality"] == "LOW"
    assert row["recheck_decision"] == "DATA_UNAVAILABLE"


def test_aggressive_stop_rr_becomes_fragile(monkeypatch):
    index = pd.date_range("2026-01-01", periods=80, freq="B")
    frame = pd.DataFrame(
        {
            "open": 100.0,
            "high": 100.5,
            "low": 99.5,
            "close": 100.0,
            "atr": 1.0,
            "ma20": 99.8,
            "ma50": 99.0,
        },
        index=index,
    )
    monkeypatch.setattr(
        risk_reward_score,
        "_structural_support",
        lambda _entry, _df: (99.8, "fixture_support"),
    )
    monkeypatch.setattr(
        risk_reward_score,
        "_select_model_target",
        lambda _candidates, **_kwargs: (101.2, "FIXTURE", "HIGH", True, ["FIXTURE"]),
    )
    result = risk_reward_score.score_risk_reward(
        frame,
        {"setup_type": "PULLBACK"},
        {
            "risk_reward": {
                "atr_stop_multiplier": 1.5,
                "min_rr_absolute": 1.5,
                "min_rr_acceptable": 1.7,
            },
            "risk_profile": {
                "stop_atr_multiple": {
                    "hard_min": 0.6,
                    "preferred_min": 1.0,
                    "preferred_max": 2.5,
                }
            },
        },
    )

    assert result["rr_valid"] is True
    assert result["stop_atr_status"] == "AGGRESSIVE_TIGHT"
    assert result["rr_stressed"] < 1.5
    assert result["risk_geometry_status"] == "FRAGILE"


def test_concentration_reads_current_scan_cohorts(tmp_path: Path):
    scan = tmp_path / "latest_scan_audited.csv"
    pd.DataFrame(
        [
            {"ticker": "A", "decision_lane": "EXECUTION_CANDIDATE", "sector": "Technology"},
            {"ticker": "B", "decision_lane": "TACTICAL_RESEARCH", "sector": "Industrials"},
            {"ticker": "C", "decision_lane": "LEADERSHIP_RESET_WATCH", "sector": "Technology"},
            {"ticker": "D", "decision_lane": "REJECT_RISK", "sector": "Energy"},
        ]
    ).to_csv(scan, index=False)

    result = collect_audit(scan)

    assert result["rows"] == 3
    assert result["input_rows"] == 4
    assert result["cohort_rows"] == {
        "EXECUTION": 1,
        "TACTICAL_RESEARCH": 1,
        "LEADERS_WAITING_RESET": 1,
    }


def test_posttest_records_empty_buy_now_session(tmp_path: Path):
    source = tmp_path / "latest_scan_audited.csv"
    pd.DataFrame(
        [
            {
                "ticker": "RADAR",
                "decision_lane": "TACTICAL_RESEARCH",
                "signal": "WATCHLIST",
            }
        ]
    ).to_csv(source, index=False)

    payload = persist_daily_candidate_memory(
        source_csv=source,
        memory_root=tmp_path / "memory",
        session_date="2026-07-30",
    )

    assert payload["buy_now_rows"] == 0
    assert payload["empty_session_recorded"] is True
    manifest = json.loads(
        (tmp_path / "memory" / "2026-07-30" / "session_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["primary_memory"] == "BUY_NOW_ONLY"


def test_daily_validation_defers_dependency_sensitive_reports():
    final = daily_validation.FINAL_DERIVED_REFRESH_STEP_NAMES
    assert final.index("simple_candidate_posttest") < final.index("live_quote_recheck")
    assert final.index("live_quote_recheck") < final.index("trade_decision_checklist")
    assert "portfolio_concentration_audit" in final
    assert "live_quote_recheck" in daily_validation.DEFERRED_POST_SUMMARY_STEP_NAMES
