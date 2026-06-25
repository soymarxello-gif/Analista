from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from engine.posttest_engine import (
    evaluate_candidate_eligibility,
    filter_eligible_candidates,
    run_posttest,
    select_backtest_candidates,
)
from tools.posttest_thesis_audit import build_thesis_audit


def _candidate(**overrides) -> dict:
    row = {
        "scan_timestamp": "2026-06-01T20:00:00Z",
        "ticker": "AAA",
        "signal": "WATCHLIST",
        "recommendation": "WATCHLIST_MONITOR",
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
        "actionable_entry": 100,
        "actionable_stop": 95,
        "actionable_target": 110,
        "rr": 2,
        "setup_type": "PULLBACK",
        "final_trade_score": 80,
        "options_bias": "NEUTRAL_WITH_DATA",
        "options_confidence": "MEDIUM",
        "stop_atr_status": "IDEAL",
        "sector": "Technology",
    }
    row.update(overrides)
    return row


def _history(bars: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    index = pd.bdate_range("2026-06-02", periods=len(bars))
    return pd.DataFrame(bars, columns=["open", "high", "low", "close"], index=index).assign(volume=1000)


def _run(tmp_path: Path, candidate: dict, bars: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    scan = tmp_path / "scan.csv"
    pd.DataFrame([candidate]).to_csv(scan, index=False)

    def history_fn(ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        assert ticker == candidate["ticker"]
        return _history(bars)

    return run_posttest(scan, output_csv=tmp_path / "posttest.csv", history_fn=history_fn)


def test_only_operationally_valid_candidates_are_eligible() -> None:
    rows = pd.DataFrame(
        [
            _candidate(ticker="GOOD"),
            _candidate(ticker="VETO", signal="VETO"),
            _candidate(ticker="RECHECK", recommendation="RECHECK_LIVE_QUOTE"),
            _candidate(ticker="STALE", quote_status="STALE_POSSIBLE"),
            _candidate(ticker="LOW", execution_quote_quality="LOW"),
            _candidate(ticker="BAD_LEVELS", actionable_stop=105),
        ]
    )

    eligible, reasons = filter_eligible_candidates(rows)

    assert eligible["ticker"].tolist() == ["GOOD"]
    assert reasons["eligible_operational_thesis"] == 1
    assert reasons["non_operable_signal:VETO"] == 1
    assert reasons["non_operable_recommendation:RECHECK_LIVE_QUOTE"] == 1


def test_backtest_selects_top_five_valid_candidates_by_score() -> None:
    eligible = pd.DataFrame(
        [
            _candidate(ticker="SIX", final_trade_score=70),
            _candidate(ticker="ONE", final_trade_score=96),
            _candidate(ticker="THREE", final_trade_score=88),
            _candidate(ticker="TWO", final_trade_score=92),
            _candidate(ticker="FIVE", final_trade_score=80),
            _candidate(ticker="FOUR", final_trade_score=84),
        ]
    )

    selected = select_backtest_candidates(eligible)

    assert selected["ticker"].tolist() == ["ONE", "TWO", "THREE", "FOUR", "FIVE"]
    assert selected["backtest_selection_rank"].tolist() == [1, 2, 3, 4, 5]


def test_backtest_handles_legacy_candidates_without_score_column() -> None:
    eligible = pd.DataFrame(
        [
            {"ticker": "BBB"},
            {"ticker": "AAA"},
        ]
    )

    selected = select_backtest_candidates(eligible)

    assert selected["ticker"].tolist() == ["AAA", "BBB"]


def test_eligibility_uses_actionable_levels_and_p0_quote_quality() -> None:
    eligible, reason = evaluate_candidate_eligibility(pd.Series(_candidate()))
    assert eligible is True
    assert reason == "eligible_operational_thesis"

    eligible, reason = evaluate_candidate_eligibility(
        pd.Series(_candidate(execution_quote_quality="LOW"))
    )
    assert eligible is False
    assert "not_high" in reason


def test_entry_not_touched_is_not_counted_as_executed_trade(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        _candidate(),
        [
            (105, 106, 103, 105),
            (104, 105, 102, 104),
            (103, 107, 102, 106),
            (106, 108, 105, 107),
        ],
    )

    assert len(result) == 1
    assert result.iloc[0]["level_outcome"] == "POSITIVE_CLOSE"
    assert bool(result.iloc[0]["execution_entry_reached"]) is False
    assert result.iloc[0]["execution_entry_status"] == "ENTRY_NOT_TOUCHED"
    assert bool(result.iloc[0]["thesis_success"]) is False
    assert bool(result.iloc[0]["published_profitable_4d"]) is True


def test_target_hit_is_success_and_uses_exactly_four_sessions(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        _candidate(),
        [
            (101, 102, 99, 101),
            (102, 106, 101, 105),
            (105, 109, 104, 108),
            (108, 111, 107, 110),
            (110, 120, 109, 119),
        ],
    )
    row = result.iloc[0]

    assert row["evaluation_sessions"] == 4
    assert row["close_h"] == 110
    assert row["level_outcome"] == "TARGET_HIT"
    assert bool(row["thesis_success"]) is True
    assert row["calculated_rr"] == 2
    assert row["rr_error"] == 0
    assert bool(row["rr_matches_source"]) is True


def test_four_day_exit_is_measured_from_scan_not_entry_date(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        _candidate(actionable_entry=100),
        [
            (105, 106, 103, 104),
            (101, 102, 99, 101),
            (102, 104, 101, 103),
            (103, 105, 102, 104),
            (104, 120, 103, 119),
        ],
    )

    row = result.iloc[0]
    assert row["entry_date"] == "2026-06-03"
    assert row["evaluation_sessions"] == 4
    assert row["execution_evaluation_sessions"] == 3
    assert row["close_h"] == 104


def test_stop_hit_is_failed_thesis(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        _candidate(),
        [
            (100, 102, 99, 101),
            (100, 101, 94, 95),
            (95, 99, 94, 98),
            (98, 100, 97, 99),
        ],
    )
    row = result.iloc[0]

    assert row["level_outcome"] == "STOP_HIT"
    assert bool(row["thesis_success"]) is False
    assert row["thesis_reason"] == "stop_hit_within_horizon"


def test_positive_day_four_close_without_target_is_secondary_not_target_success(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        _candidate(),
        [
            (100, 102, 99, 101),
            (101, 104, 100, 103),
            (103, 106, 102, 105),
            (105, 108, 104, 107),
        ],
    )

    assert result.iloc[0]["level_outcome"] == "POSITIVE_CLOSE"
    assert bool(result.iloc[0]["thesis_success"]) is False
    assert bool(result.iloc[0]["target_success"]) is False
    assert bool(result.iloc[0]["profitable_at_4d"]) is True


def test_positive_four_day_close_is_win_but_not_target_success() -> None:
    legacy = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "scan_date": "2026-06-08",
                "horizon_days": 4,
                "setup_type": "PULLBACK",
                "level_outcome": "POSITIVE_CLOSE",
                "thesis_success": True,
                "return_close_pct": 0.02,
            },
            {
                "ticker": "BBB",
                "scan_date": "2026-06-08",
                "horizon_days": 4,
                "setup_type": "BREAKOUT",
                "level_outcome": "TARGET_HIT",
                "thesis_success": True,
                "return_close_pct": 0.04,
            },
        ]
    )

    report = build_thesis_audit(legacy, min_samples=1)

    assert report["summary"]["wins"] == 2
    assert report["summary"]["win_rate"] == 1.0
    assert report["summary"]["target_wins"] == 1
    assert report["summary"]["target_success_rate"] == 0.5
    assert report["failure_counts"]["TARGET_TOO_AMBITIOUS"] == 1


def test_explicit_scenario_ineligibility_excludes_candidate() -> None:
    eligible, reason = evaluate_candidate_eligibility(
        pd.Series(_candidate(scenario_eligible_for_backtest=False))
    )

    assert eligible is False
    assert reason == "scenario_not_eligible_for_backtest"


def test_legacy_scenario_status_is_used_when_boolean_is_absent() -> None:
    eligible, reason = evaluate_candidate_eligibility(
        pd.Series(_candidate(scenario_status="WEAK_MOMENTUM"))
    )

    assert eligible is False
    assert reason == "scenario_status_not_valid:WEAK_MOMENTUM"


def test_audit_separates_published_execution_and_shadow_results() -> None:
    report = build_thesis_audit(
        pd.DataFrame(
            [
                {
                    "ticker": "AAA",
                    "scan_date": "2026-06-08",
                    "horizon_days": 4,
                    "level_outcome": "POSITIVE_CLOSE",
                    "published_return_4d_pct": 0.04,
                    "published_profitable_4d": True,
                    "execution_entry_reached": False,
                    "shadow_return_close_pct": 0.02,
                    "target_success": False,
                },
                {
                    "ticker": "BBB",
                    "scan_date": "2026-06-08",
                    "horizon_days": 4,
                    "level_outcome": "NEGATIVE_CLOSE",
                    "published_return_4d_pct": -0.02,
                    "published_profitable_4d": False,
                    "execution_entry_reached": True,
                    "execution_return_close_pct": -0.01,
                    "execution_profitable_at_4d": False,
                    "shadow_return_close_pct": 0.01,
                    "target_success": False,
                },
            ]
        ),
        min_samples=1,
    )

    summary = report["summary"]
    assert summary["win_rate"] == 0.5
    assert summary["entry_trigger_rate"] == 0.5
    assert summary["execution_win_rate"] == 0.0
    assert summary["shadow_win_rate"] == 1.0


def test_target_and_stop_same_daily_window_is_not_assumed_win(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        _candidate(),
        [
            (100, 111, 94, 102),
            (102, 104, 100, 103),
            (103, 104, 101, 102),
            (102, 103, 100, 101),
        ],
    )

    assert result.iloc[0]["level_outcome"] == "BOTH_HIT_DAILY_UNKNOWN_SEQUENCE"
    assert bool(result.iloc[0]["thesis_success"]) is False


def test_thesis_audit_calculates_ticker_win_rate_and_common_patterns() -> None:
    data = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "horizon_days": 4,
                "level_outcome": "TARGET_HIT",
                "thesis_success": True,
                "hit_target": True,
                "hit_stop": False,
                "return_close_pct": 0.08,
                "realized_r_at_close": 1.6,
                "calculated_rr": 2.0,
                "rr_error": 0.0,
                "rr_matches_source": True,
                "target_capture_ratio": 1.1,
                "stop_buffer_ratio": 0.4,
                "setup_type": "PULLBACK",
                "score_bucket": "75_TO_84",
            },
            {
                "ticker": "AAA",
                "horizon_days": 4,
                "level_outcome": "POSITIVE_CLOSE",
                "thesis_success": True,
                "hit_target": False,
                "hit_stop": False,
                "return_close_pct": 0.03,
                "realized_r_at_close": 0.6,
                "calculated_rr": 2.0,
                "rr_error": 0.0,
                "rr_matches_source": True,
                "target_capture_ratio": 0.8,
                "stop_buffer_ratio": 0.3,
                "setup_type": "PULLBACK",
                "score_bucket": "75_TO_84",
            },
            {
                "ticker": "BBB",
                "horizon_days": 4,
                "level_outcome": "STOP_HIT",
                "thesis_success": False,
                "hit_target": False,
                "hit_stop": True,
                "return_close_pct": -0.05,
                "realized_r_at_close": -1.0,
                "calculated_rr": 2.0,
                "rr_error": 0.0,
                "rr_matches_source": True,
                "target_capture_ratio": 0.2,
                "stop_buffer_ratio": 1.2,
                "setup_type": "BREAKOUT",
                "score_bucket": "65_TO_74",
            },
            {
                "ticker": "CCC",
                "horizon_days": 4,
                "level_outcome": "NO_ENTRY_TRIGGER",
                "thesis_success": False,
                "setup_type": "BREAKOUT",
                "score_bucket": "65_TO_74",
            },
        ]
    )

    report = build_thesis_audit(data, min_samples=1)

    assert report["summary"]["executed_entries"] == 3
    assert report["summary"]["no_entry_triggers"] == 1
    assert report["summary"]["win_rate"] == round(2 / 3, 6)
    assert report["summary"]["rr_match_rate"] == 1.0
    aaa = next(row for row in report["ticker_win_rates"] if row["value"] == "AAA")
    assert aaa["win_rate"] == 1.0
    assert report["automatic_changes_allowed"] is False


def test_default_horizon_is_four_days() -> None:
    from engine.posttest_engine import DEFAULT_HORIZONS

    assert DEFAULT_HORIZONS == [4]


def test_daily_pipeline_tracks_thesis_audit() -> None:
    from tools import daily_validation
    from tools.daily_run_manifest import KEY_REPORT_PATHS, KEY_SCRIPT_PATHS

    names = [step["name"] for step in daily_validation.DEFAULT_STEPS + daily_validation.POST_SUMMARY_STEPS]
    assert "posttest_thesis_audit" in names
    posttest_step = next(
        step for step in daily_validation.DEFAULT_STEPS if step["name"] == "posttest_thesis_audit"
    )
    assert "reports/posttests/**/*.csv" in posttest_step["cmd"]
    assert "tools/posttest_thesis_audit.py" in KEY_SCRIPT_PATHS
    assert "reports/posttest_thesis_audit_latest.json" in KEY_REPORT_PATHS
    assert "reports/posttest_thesis_audit_latest.md" in KEY_REPORT_PATHS
