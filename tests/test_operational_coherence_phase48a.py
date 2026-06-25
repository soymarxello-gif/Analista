from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from tools.daily_quality_gate import collect_daily_quality_gate
from tools.daily_validation import FINAL_DERIVED_REFRESH_STEP_NAMES
from tools.manual_review_export import build_manual_review_dataframe
from tools.manual_review_top import classify_top_group
from tools.posttest_thesis_audit import (
    build_thesis_audit,
    select_canonical_daily_top_five,
)
from tools.trade_candidate_cards import (
    build_trade_candidate_cards_dataframe,
    build_trade_candidate_cards_markdown,
)
from tools.trade_decision_checklist import evaluate_checklist_row


def _operational_candidate(**overrides) -> dict:
    row = {
        "rank": 1,
        "ticker": "AAA",
        "signal": "WATCHLIST",
        "recommendation": "WATCHLIST_MONITOR",
        "setup_type": "BREAKOUT",
        "final_trade_score": 90,
        "setup_quality_score": 88,
        "setup_persistence_score": 70,
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
        "actionable_entry": 100,
        "actionable_stop": 95,
        "actionable_target": 110,
        "rr": 2.0,
        "market_cap": 5_000_000_000,
        "liquidity_pass": True,
        "scenario_status": "VALID_TRIGGER",
        "scenario_confidence": "HIGH",
        "scenario_operability": "REVIEW_VALID_SCENARIO",
        "scenario_eligible_for_backtest": True,
        "scenario_guardrail_applied": False,
        "scenario_guardrail_reason": "",
        "momentum_state": "STRONG",
        "extension_state": "HEALTHY",
        "entry_timing_status": "VALID_NOW",
        "required_confirmation": "",
        "engine_recommendation": "REVIEW_SCENARIO",
        "shadow_entry": 100,
        "shadow_stop": 94,
        "shadow_target": 110,
        "shadow_rr": 1.67,
        "shadow_level_status": "VALID",
    }
    row.update(overrides)
    return row


def test_manual_review_export_preserves_scenario_and_shadow_fields() -> None:
    out = build_manual_review_dataframe(pd.DataFrame([_operational_candidate()]))

    assert out.iloc[0]["scenario_status"] == "VALID_TRIGGER"
    assert bool(out.iloc[0]["scenario_eligible_for_backtest"]) is True
    assert out.iloc[0]["shadow_level_status"] == "VALID"
    assert out.iloc[0]["momentum_state"] == "STRONG"


def test_only_valid_scenario_can_be_high_quality_top_group() -> None:
    valid = classify_top_group(_operational_candidate())
    late = classify_top_group(
        _operational_candidate(
            scenario_status="LATE_ENTRY_OVEREXTENDED",
            scenario_eligible_for_backtest=False,
        )
    )
    waiting = classify_top_group(
        _operational_candidate(
            scenario_status="WAIT_FOR_CONFIRMATION",
            scenario_eligible_for_backtest=False,
        )
    )

    assert valid == "1_ALTA_CALIDAD_OPERATIVA"
    assert late == "4_DETERIORADO_O_DEBIL"
    assert waiting == "3_PERSISTENTE_NO_ACCIONABLE_TODAVIA"


def test_non_operable_scenario_is_blocked_even_with_high_score_and_quote() -> None:
    result = evaluate_checklist_row(
        _operational_candidate(
            scenario_status="WEAK_MOMENTUM",
            scenario_eligible_for_backtest=False,
            required_confirmation="wait_for_momentum_improvement",
        )
    )

    assert result["checklist_status"] == "BLOCKED"
    assert "scenario_not_operable_weak_momentum" in result["checklist_blockers"]
    assert "scenario_not_eligible_for_backtest" in result["checklist_blockers"]
    assert "wait_for_momentum_improvement" in result["checklist_required_actions"]


def test_invalid_shadow_levels_prevent_high_quality_without_replacing_levels() -> None:
    result = evaluate_checklist_row(
        _operational_candidate(shadow_level_status="RR_BELOW_MINIMUM")
    )

    assert result["checklist_status"] == "REVIEW_MANUALLY"
    assert "shadow_level_status_rr_below_minimum" in result["checklist_warnings"]
    assert "shadow" not in result["checklist_blockers"]


def test_candidate_card_contains_scenario_and_shadow_diagnostics() -> None:
    cards = build_trade_candidate_cards_dataframe(
        pd.DataFrame([_operational_candidate(checklist_status="REVIEW_MANUALLY")])
    )
    text = build_trade_candidate_cards_markdown(cards)

    assert "### Diagnostico de escenario" in text
    assert "scenario_status: VALID_TRIGGER" in text
    assert "momentum_state: STRONG" in text
    assert "niveles shadow:" in text


def test_canonical_backtest_uses_latest_run_and_at_most_five_ranks() -> None:
    rows = []
    for hour, prefix in [("100000", "OLD"), ("160000", "NEW")]:
        for rank in range(1, 7):
            rows.append(
                {
                    "scan_date": "2026-06-20",
                    "ticker": f"{prefix}{rank}",
                    "_source_file": f"posttest_20260620_{hour}.csv",
                    "backtest_selection_rank": rank,
                    "scenario_eligible_for_backtest": True,
                }
            )

    selected = select_canonical_daily_top_five(pd.DataFrame(rows))

    assert selected["ticker"].tolist() == ["NEW1", "NEW2", "NEW3", "NEW4", "NEW5"]
    assert len(selected) == 5


def test_canonical_backtest_does_not_backfill_ineligible_rank() -> None:
    rows = [
        {
            "scan_date": "2026-06-20",
            "ticker": f"AAA{rank}",
            "_source_file": "posttest_20260620_160000.csv",
            "backtest_selection_rank": rank,
            "scenario_eligible_for_backtest": rank != 3,
        }
        for rank in range(1, 6)
    ]

    selected = select_canonical_daily_top_five(pd.DataFrame(rows))

    assert len(selected) == 4
    assert "AAA3" not in set(selected["ticker"])


def test_thesis_audit_reports_payoff_profit_factor_and_canonical_counts() -> None:
    data = pd.DataFrame(
        [
            {
                "scan_date": "2026-06-20",
                "ticker": "AAA",
                "_source_file": "posttest_20260620_160000.csv",
                "backtest_selection_rank": 1,
                "horizon_days": 4,
                "published_return_4d_pct": 0.04,
                "published_profitable_4d": True,
                "execution_entry_reached": True,
                "level_outcome": "POSITIVE_CLOSE",
            },
            {
                "scan_date": "2026-06-20",
                "ticker": "BBB",
                "_source_file": "posttest_20260620_160000.csv",
                "backtest_selection_rank": 2,
                "horizon_days": 4,
                "published_return_4d_pct": -0.02,
                "published_profitable_4d": False,
                "execution_entry_reached": True,
                "level_outcome": "NEGATIVE_CLOSE",
            },
        ]
    )

    report = build_thesis_audit(data, min_samples=1)
    summary = report["summary"]

    assert summary["canonical_dates"] == 1
    assert summary["max_candidates_per_canonical_day"] == 2
    assert summary["payoff_ratio"] == 2.0
    assert summary["profit_factor"] == 2.0
    assert summary["expectancy_4d_pct"] == 0.01


def test_quality_gate_uses_scan_recommendations_and_warns_on_stale_manual(
    tmp_path: Path,
) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "daily_validation_summary.txt").write_text("Status: PASS\n", encoding="utf-8")
    for name, payload in [
        ("project_preflight_latest.json", '{"status":"PASS"}'),
        ("daily_run_manifest_latest.json", '{"status":"PASS"}'),
        ("reports_cleanup_latest.json", '{"status":"PASS","candidate_count":0}'),
        (
            "encoding_audit_latest.json",
            '{"status":"PASS","summary":{"warn_files":0,"error_files":0,"total_marker_hits":0}}',
        ),
    ]:
        (reports / name).write_text(payload, encoding="utf-8")
    (reports / "daily_operator_index.md").write_text("# index\n", encoding="utf-8")
    (reports / "manual_review_top.csv").write_text("ticker\nAAA\n", encoding="utf-8")
    (reports / "manual_review_top.md").write_text("# top\n", encoding="utf-8")

    scan_path = reports / "latest_scan_audited.csv"
    manual_path = reports / "manual_review_latest.csv"
    pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "signal": "WATCHLIST",
                "recommendation": "WATCHLIST_MONITOR",
                "scenario_status": "VALID_TRIGGER",
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
            }
        ]
    ).to_csv(scan_path, index=False)
    pd.DataFrame(
        [{"ticker": "AAA", "recommendation": "MISSING"}]
    ).to_csv(manual_path, index=False)
    scan_mtime = scan_path.stat().st_mtime
    os.utime(manual_path, (scan_mtime - 10, scan_mtime - 10))

    report = collect_daily_quality_gate(root=tmp_path)

    assert report["scan_snapshot"]["recommendations"] == {"WATCHLIST_MONITOR": 1}
    assert report["scan_snapshot"]["scenario_status"] == {"VALID_TRIGGER": 1}
    assert report["artifact_freshness"]["manual_review_is_stale"] is True
    assert report["status"] == "WARN"


def test_daily_validation_refreshes_scenario_dependent_reports_in_final_order() -> None:
    assert FINAL_DERIVED_REFRESH_STEP_NAMES.index("trade_decision_checklist") < (
        FINAL_DERIVED_REFRESH_STEP_NAMES.index("trade_candidate_cards")
    )
    assert FINAL_DERIVED_REFRESH_STEP_NAMES.index("trade_candidate_cards") < (
        FINAL_DERIVED_REFRESH_STEP_NAMES.index("daily_quality_gate")
    )
    assert FINAL_DERIVED_REFRESH_STEP_NAMES.index("daily_quality_gate") < (
        FINAL_DERIVED_REFRESH_STEP_NAMES.index("daily_operator_index")
    )
    assert FINAL_DERIVED_REFRESH_STEP_NAMES[-1] == "daily_run_manifest"
