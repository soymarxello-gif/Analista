from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from engine.options_flow import LEGACY_OPTIONS_COLUMNS, build_options_flow_fields
from scoring.options_score import score_options_flow
from scoring.signal_classifier import classify_signal
from tools.daily_operator_index import build_daily_operator_index_markdown
from tools.daily_run_manifest import build_daily_run_manifest_markdown, collect_daily_run_manifest
from tools.source_coverage_audit import build_source_coverage_report


def _config() -> dict:
    return {
        "options_flow": {
            "enabled": True,
            "min_total_option_volume": 100,
            "min_total_option_open_interest": 1000,
            "medium_total_option_volume": 300,
            "medium_total_option_open_interest": 1000,
            "high_total_option_volume": 1000,
            "high_total_option_open_interest": 5000,
            "extreme_bullish_put_call_below": 0.35,
            "extreme_bearish_put_call_above": 1.80,
            "crowded_bullish_score_cap": 0.60,
            "weights": {
                "put_call_volume_ratio": 0.25,
                "call_volume_share": 0.20,
                "near_call_oi_share": 0.20,
                "call_wall_position": 0.15,
                "iv_risk": 0.10,
                "options_liquidity": 0.10,
            },
        }
    }


def _metrics(**overrides) -> dict:
    data = {
        "options_data_available": True,
        "options_available": True,
        "options_source": "yfinance",
        "put_call_volume_ratio": 1.0,
        "put_call_oi_ratio": 1.0,
        "options_put_call_oi_ratio": 1.0,
        "call_volume_share": 0.50,
        "near_call_oi_share": 0.50,
        "max_call_oi_strike": 105.0,
        "atm_implied_volatility": 0.40,
        "total_option_volume": 800,
        "total_option_open_interest": 3000,
        "call_open_interest": 1500,
        "put_open_interest": 1500,
        "near_call_open_interest": 700,
        "near_put_open_interest": 700,
        "near_put_call_oi_ratio": 1.0,
    }
    data.update(overrides)
    return data


def test_no_options_available_is_distinct_from_unknown():
    result = score_options_flow(
        {
            "options_available": False,
            "options_data_available": False,
            "options_source": "yfinance",
            "options_error": "no_options_listed",
        },
        100,
        _config(),
    )

    assert result["options_bias"] == "NO_OPTIONS_AVAILABLE"
    assert result["options_confidence"] == "UNKNOWN"
    assert result["options_score"] == 0.5


def test_empty_chain_is_unknown_not_no_options_available():
    result = score_options_flow(
        {
            "options_available": False,
            "options_data_available": False,
            "options_source": "yfinance",
            "options_error": "empty_option_chain",
            "options_warning": "option_chain vacio",
        },
        100,
        _config(),
    )

    assert result["options_bias"] == "UNKNOWN_OPTIONS_FLOW"
    assert result["options_confidence"] == "UNKNOWN"


def test_balanced_oi_is_neutral_with_data():
    result = score_options_flow(_metrics(), 100, _config())

    assert result["options_bias"] == "NEUTRAL_WITH_DATA"
    assert result["options_confidence"] in {"MEDIUM", "HIGH"}


def test_very_high_put_oi_is_crowded_bearish_with_contrarian_notes():
    result = score_options_flow(
        _metrics(
            put_call_oi_ratio=2.4,
            options_put_call_oi_ratio=2.4,
            put_call_volume_ratio=1.1,
            call_volume_share=0.35,
            near_call_oi_share=0.35,
        ),
        100,
        _config(),
    )

    assert result["options_bias"] == "CROWDED_BEARISH"
    assert result["options_crowded_bearish"] is True
    assert "contrarian" in result["options_notes"].lower()


def test_very_low_put_oi_is_crowded_bullish_with_score_cap():
    result = score_options_flow(
        _metrics(
            put_call_oi_ratio=0.20,
            options_put_call_oi_ratio=0.20,
            put_call_volume_ratio=0.55,
            call_volume_share=0.85,
            near_call_oi_share=0.85,
        ),
        100,
        _config(),
    )

    assert result["options_bias"] == "CROWDED_BULLISH"
    assert result["options_crowded_bullish"] is True
    assert result["options_score"] <= 0.60


def test_low_liquidity_data_is_low_confidence_neutral():
    result = score_options_flow(
        _metrics(
            total_option_volume=40,
            total_option_open_interest=200,
            call_open_interest=100,
            put_open_interest=100,
            put_call_oi_ratio=2.4,
            options_put_call_oi_ratio=2.4,
        ),
        100,
        _config(),
    )

    assert result["options_bias"] == "NEUTRAL_WITH_DATA"
    assert result["options_confidence"] == "LOW"
    assert result["options_score"] == 0.5


def test_sufficient_data_has_medium_or_high_confidence():
    result = score_options_flow(
        _metrics(total_option_volume=1200, total_option_open_interest=7000),
        100,
        _config(),
    )

    assert result["options_confidence"] == "HIGH"
    assert result["options_liquidity_score"] > 0


def test_options_field_builder_preserves_legacy_columns_and_adds_auditable_columns():
    score = score_options_flow(_metrics(), 100, _config())
    fields = build_options_flow_fields(_metrics(), score)

    for col in LEGACY_OPTIONS_COLUMNS:
        assert col in fields

    assert fields["options_available"] is True
    assert fields["options_total_call_oi"] == 1500
    assert fields["options_total_put_oi"] == 1500
    assert fields["options_put_call_oi_ratio"] == 1.0
    assert fields["options_bias"] == "NEUTRAL_WITH_DATA"
    assert "options_notes" in fields


def test_options_flow_does_not_create_trigger_confirmed_when_quote_is_not_valid():
    row = {
        "final_score": 99,
        "rr": 3.0,
        "trigger_confirmed": True,
        "price": 100,
        "market_cap": 5_000_000_000,
        "quote_type": "EQUITY",
        "liquidity_pass": True,
        "trend_score": 0.90,
        "setup_type": "BREAKOUT",
        "quote_status": "MISSING",
        "execution_quote_quality": "LOW",
        "options_bias": "CROWDED_BEARISH",
        "options_confidence": "HIGH",
    }
    config = {
        "signals": {
            "buy_setup_active_enabled": False,
            "allowed_states": [
                "VETO",
                "AVOID",
                "WATCHLIST",
                "READY_WAIT_TRIGGER",
                "TRIGGER_CONFIRMED",
            ],
        },
        "signal_thresholds": {
            "buy_setup_active": {"enabled": False, "min_score": 85, "min_rr": 2.0, "require_trigger": True},
            "trigger_confirmed": {"min_score": 85, "min_rr": 2.0, "require_trigger": True},
            "ready_wait_trigger": {"min_score": 80, "min_rr": 1.7},
            "watchlist": {"min_score": 70},
        },
        "risk_reward": {"min_rr_absolute": 1.5},
        "veto_rules": {"thresholds": {"min_trend_score": 0.55}, "data_quality": {}},
        "filters": {"min_price": 10, "min_market_cap_usd": 1_500_000_000},
        "universe": {"allowed_quote_types": ["EQUITY", "ETF"]},
    }

    signal, veto = classify_signal(row, config)

    assert veto == []
    assert signal == "WATCHLIST"
    assert signal != "TRIGGER_CONFIRMED"


def test_source_coverage_reports_options_flow_counts():
    df = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "options_bias": "NEUTRAL_WITH_DATA",
                "options_confidence": "MEDIUM",
                "options_source": "yfinance",
                "options_available": True,
                "options_error": "",
                "options_priority_selected": True,
                "options_priority_reason": "preliminary_watchlist",
                "options_preliminary_signal": "WATCHLIST",
            },
            {
                "ticker": "BBB",
                "options_bias": "NO_OPTIONS_AVAILABLE",
                "options_confidence": "UNKNOWN",
                "options_source": "yfinance",
                "options_available": False,
                "options_error": "no_options_listed",
                "options_priority_selected": False,
                "options_priority_reason": "not_selected_by_priority_budget",
                "options_preliminary_signal": "AVOID",
            },
        ]
    )

    report = build_source_coverage_report(df)

    assert report["options_flow"]["options_bias"]["NEUTRAL_WITH_DATA"] == 1
    assert report["options_flow"]["options_bias"]["NO_OPTIONS_AVAILABLE"] == 1
    assert report["options_flow"]["options_error"]["no_options_listed"] == 1
    assert report["options_flow"]["options_priority_selected"]["True"] == 1
    assert report["options_flow"]["options_priority_reason"]["preliminary_watchlist"] == 1


def test_daily_operator_index_renders_options_flow_summary():
    text = build_daily_operator_index_markdown(
        {
            "generated_at": "2026-06-11T00:00:00",
            "validation_status": "PASS",
            "scan_rows": 2,
            "manual_review_rows": 0,
            "manual_top_rows": 0,
            "open_trades_rows": 0,
            "analytics_rows": 0,
            "trigger_count": 0,
            "watchlist_count": 0,
            "recheck_count": 0,
            "signals": {},
            "recommendations": {},
            "quote_recheck_priority": {},
            "quality_gate": {"available": False},
            "live_quote_recheck": {"available": False},
            "options_bias": {"NEUTRAL_WITH_DATA": 1, "NO_OPTIONS_AVAILABLE": 1},
            "options_confidence": {"MEDIUM": 1, "UNKNOWN": 1},
            "options_source": {"yfinance": 2},
            "options_available": {"True": 1, "False": 1},
            "options_error": {"no_options_listed": 1},
            "top_candidates": pd.DataFrame(),
            "recheck_candidates": pd.DataFrame(),
            "open_trades": pd.DataFrame(),
            "analytics_overall": pd.DataFrame(),
            "cleanup": {},
            "preflight": {},
            "encoding_audit": {},
            "report_status": [],
        }
    )

    assert "## Options / institutional flow" in text
    assert "- NEUTRAL_WITH_DATA: 1" in text
    assert "- NO_OPTIONS_AVAILABLE: 1" in text
    assert "no es veto duro ni gatillo automatico" in text


def test_daily_run_manifest_tracks_options_flow_counts(tmp_path: Path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "daily_validation_summary.txt").write_text("Status: PASS\n", encoding="utf-8")
    (reports / "project_preflight_latest.json").write_text(
        json.dumps({"status": "PASS", "summary": {}}),
        encoding="utf-8",
    )
    (reports / "reports_cleanup_latest.json").write_text(
        json.dumps({"status": "PASS", "mode": "DRY_RUN"}),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "options_bias": "CROWDED_BULLISH",
                "options_confidence": "HIGH",
                "options_source": "yfinance",
                "options_available": True,
                "options_error": "",
            }
        ]
    ).to_csv(reports / "latest_scan_audited.csv", index=False)
    pd.DataFrame([{"ticker": "AAA", "recommendation": "WATCHLIST_MONITOR"}]).to_csv(
        reports / "manual_review_latest.csv",
        index=False,
    )

    data = collect_daily_run_manifest(
        root=tmp_path,
        key_script_paths=[],
        key_report_paths=[],
    )
    text = build_daily_run_manifest_markdown(data)

    assert data["scan_snapshot"]["options_bias"]["CROWDED_BULLISH"] == 1
    assert data["scan_snapshot"]["options_confidence"]["HIGH"] == 1
    assert "Options / institutional flow:" in text
