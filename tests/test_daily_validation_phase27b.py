from __future__ import annotations

from tools.daily_validation import DEFAULT_STEPS, collect_output_status


def test_daily_validation_includes_trade_outcome_analytics_optional_step():
    matches = [
        step
        for step in DEFAULT_STEPS
        if step.get("name") == "trade_outcome_analytics"
    ]

    assert len(matches) == 1

    step = matches[0]

    assert step["required"] is False
    assert "tools/trade_outcome_analytics.py" in step["cmd"]


def test_daily_validation_tracks_trade_outcome_analytics_outputs():
    status = collect_output_status()
    paths = {item["path"] for item in status["files"]}

    assert "reports/trade_outcome_analytics_latest.csv" in paths
    assert "reports/trade_outcome_analytics_latest.json" in paths
    assert "reports/trade_outcome_analytics_latest.md" in paths
