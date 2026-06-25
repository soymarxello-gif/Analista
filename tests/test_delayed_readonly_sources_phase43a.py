from __future__ import annotations

from pathlib import Path

from tools.daily_validation import POST_SUMMARY_STEPS, collect_output_status


def test_daily_validation_runs_secondary_provider_audits_as_optional_steps() -> None:
    steps = {step["name"]: step for step in POST_SUMMARY_STEPS}

    for name in [
        "webull_readonly_market_data_audit",
        "cboe_market_statistics_audit",
        "google_sheets_data_source_audit",
    ]:
        assert name in steps
        assert steps[name]["required"] is False
        assert steps[name]["timeout_seconds"] == 60


def test_daily_validation_tracks_secondary_provider_outputs() -> None:
    status = collect_output_status()
    paths = {item["path"] for item in status["files"]}

    assert "reports/webull_readonly_market_data_latest.json" in paths
    assert "reports/webull_readonly_market_data_latest.md" in paths
    assert "reports/cboe_market_statistics_latest.json" in paths
    assert "reports/cboe_market_statistics_latest.md" in paths
    assert "reports/google_sheets_data_source_latest.json" in paths
    assert "reports/google_sheets_data_source_latest.md" in paths


def test_scanner_analysis_quote_fields_are_informational_only() -> None:
    source = Path("engine/scanner_engine.py").read_text(encoding="utf-8")

    for field in [
        "analysis_price",
        "analysis_bid",
        "analysis_ask",
        "analysis_spread_pct",
        "analysis_quote_source",
        "analysis_quote_timestamp",
        "analysis_quote_freshness",
        "analysis_quote_confidence",
        "secondary_data_sources_used",
        "secondary_data_notes",
    ]:
        assert field in source

    assert 'row["quote_status"] = row["analysis_quote_status"]' not in source
    assert 'row["execution_quote_quality"] = row["analysis_quote_quality"]' not in source
    assert 'row["execution_quote_quality"] = row["analysis_quote_confidence"]' not in source
    assert "apply_analysis_quote_fallback" in source
    assert "select_analysis_quote_fallback_tickers" in source
    assert "secondary providers are audited read-only" in source
