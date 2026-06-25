from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools.scenario_engine_audit import build_scenario_audit, save_reports


def test_audit_counts_fifty_selected_and_contradictions() -> None:
    rows = []
    for index in range(70):
        rows.append(
            {
                "ticker": f"T{index}",
                "deep_analysis_selected": index < 50,
                "scenario_status": "VALID_TRIGGER" if index < 10 else "WAIT_FOR_CONFIRMATION",
                "momentum_state": "STRONG" if index < 10 else "NEUTRAL",
                "extension_state": "HEALTHY",
                "engine_recommendation": "REVIEW_VALID_SCENARIO" if index < 10 else "WAIT_FOR_CONFIRMATION",
                "scenario_contradictions": '["no_bullish_rejection_confirmation"]' if 10 <= index < 20 else "[]",
            }
        )

    report = build_scenario_audit(pd.DataFrame(rows))

    assert report["status"] == "PASS"
    assert report["deep_analysis_rows"] == 50
    assert report["scenario_status"]["VALID_TRIGGER"] == 10
    assert report["top_contradictions"]["no_bullish_rejection_confirmation"] == 10
    assert report["signals_modified"] is False


def test_audit_reports_conservative_guardrail_usage() -> None:
    report = build_scenario_audit(
        pd.DataFrame(
            [
                {
                    "ticker": "AAA",
                    "deep_analysis_selected": True,
                    "scenario_status": "WEAK_MOMENTUM",
                    "scenario_guardrail_applied": True,
                    "scenario_eligible_for_backtest": False,
                    "scenario_operability": "MONITOR_MOMENTUM",
                },
                {
                    "ticker": "BBB",
                    "deep_analysis_selected": True,
                    "scenario_status": "VALID_TRIGGER",
                    "scenario_guardrail_applied": False,
                    "scenario_eligible_for_backtest": True,
                    "scenario_operability": "REVIEW_VALID_SCENARIO",
                },
            ]
        )
    )

    assert report["shadow_mode"] is False
    assert report["guardrail_mode"] == "CONSERVATIVE_DEMOTION_ONLY"
    assert report["guardrail_applied_rows"] == 1
    assert report["backtest_eligible_rows"] == 1
    assert report["automatic_promotions"] is False


def test_missing_input_is_controlled_warn(tmp_path: Path) -> None:
    result = save_reports(
        input_csv=tmp_path / "missing.csv",
        json_out=tmp_path / "report.json",
        markdown_out=tmp_path / "report.md",
    )

    assert result["status"] == "WARN"
    assert result["error"] == "input_csv_not_found"
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["automatic_changes"] is False
