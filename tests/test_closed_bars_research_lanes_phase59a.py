from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from data import price_client
from data.technical_bars import closed_weekly_close, derive_technical_prices
from engine import technical_assessment
from engine.candidate_funnel import select_deep_analysis_candidates
from engine.scan_audit_engine import audit_scan_dataframe
from engine.scenario_engine import calculate_shadow_levels
from scoring.operational_readiness import calculate_operational_readiness
from scoring.risk_reward_score import score_risk_reward
from tools.simple_candidate_posttest import _is_buy_now_candidate


def _daily_frame(end: str = "2026-07-29", periods: int = 90) -> pd.DataFrame:
    index = pd.bdate_range(end=end, periods=periods)
    close = pd.Series(range(100, 100 + periods), index=index, dtype=float)
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000_000.0,
            "ema20": close - 1.0,
            "sma50": close - 3.0,
            "sma200": close - 10.0,
            "rsi": 58.0,
            "relative_volume": 1.05,
            "atr": 2.0,
        },
        index=index,
    )


def test_open_daily_bar_is_excluded_before_new_york_cutoff() -> None:
    frame = _daily_frame(periods=5)
    technical, metadata = derive_technical_prices(
        frame,
        now=datetime(2026, 7, 29, 15, 0, tzinfo=timezone(timedelta(hours=-4))),
    )

    assert len(technical) == 4
    assert metadata["intraday_bar_excluded"] is True
    assert metadata["technical_as_of_date"] == "2026-07-28"


def test_closed_daily_bar_is_kept_after_new_york_cutoff() -> None:
    frame = _daily_frame(periods=5)
    technical, metadata = derive_technical_prices(
        frame,
        now=datetime(2026, 7, 29, 16, 25, tzinfo=timezone(timedelta(hours=-4))),
    )

    assert len(technical) == 5
    assert metadata["intraday_bar_excluded"] is False
    assert metadata["technical_as_of_date"] == "2026-07-29"


def test_incomplete_week_is_not_used_for_weekly_macd() -> None:
    close = _daily_frame(end="2026-07-29", periods=20)["close"]
    weekly, complete = closed_weekly_close(
        close,
        now=datetime(2026, 7, 29, 15, 0, tzinfo=timezone(timedelta(hours=-4))),
    )

    assert complete is False
    assert weekly.index[-1].date().isoformat() == "2026-07-24"


def _assessment_components(monkeypatch, *, extension_status: str = "HEALTHY") -> None:
    monkeypatch.setattr(
        technical_assessment,
        "score_structure",
        lambda df, config: {
            "setup_type": "NO_VALID_SETUP",
            "structure_score": 0.55,
            "trigger_level": None,
            "trigger_confirmed": False,
        },
    )
    monkeypatch.setattr(
        technical_assessment,
        "score_trend",
        lambda df, config: (0.80, "TREND"),
    )
    def _rr_for_setup(df, structure, config):
        if structure.get("setup_type") == "PULLBACK":
            return {
                "entry": 189.0,
                "stop": 185.0,
                "target": 197.0,
                "rr": 2.0,
                "rr_score": 0.7,
                "rr_valid": True,
                "rr_status": "VALIDATED",
                "rr_confidence": "HIGH",
            }
        return {
            "rr": None,
            "rr_score": 0.0,
            "rr_valid": False,
            "rr_status": "NOT_APPLICABLE_FORMING_SETUP",
        }

    monkeypatch.setattr(technical_assessment, "score_risk_reward", _rr_for_setup)
    monkeypatch.setattr(
        technical_assessment,
        "calculate_extension_risk",
        lambda evidence, setup: {
            "ema20_extension_status": extension_status,
            "ema20_extension_risk": 0.15,
            "ema20_extension_reasons": [],
        },
    )
    monkeypatch.setattr(
        technical_assessment,
        "calculate_setup_readiness",
        lambda *args, **kwargs: {
            "setup_readiness_score": 78.0,
            "setup_readiness_state": "FORMING",
            "setup_candidate_type": "PULLBACK",
            "setup_readiness_reason": "pullback_forming_score_78",
            "setup_readiness_components": "{}",
        },
    )


def test_forming_setup_enters_research_without_operational_eligibility(monkeypatch) -> None:
    _assessment_components(monkeypatch)
    result = technical_assessment.evaluate_technical_opportunity(
        _daily_frame(),
        {"risk_reward": {"min_rr_absolute": 1.5}},
        liquidity={"liquidity_core_pass": True, "liquidity_score": 0.9},
        evidence={
            "technical_close": 189.0,
            "technical_sma200": 179.0,
            "technical_distance_ema20_pct": 0.02,
            "technical_distance_ema20_atr": 0.9,
            "daily_macd_trajectory_state": "ACCELERATING",
            "weekly_macd_trajectory_state": "IMPROVING_STEADY",
            "momentum_acceleration_score": 80.0,
            "momentum_persistence_score": 80.0,
        },
    )

    assert result["technical_analysis_lane"] == "ADVANCE_RESEARCH_ANALYSIS"
    assert result["deep_analysis_tier"] == "RESEARCH"
    assert result["operational_eligibility"] is False
    assert result["research_rr_data"]["entry"] == 189.0
    assert result["research_rr_data"]["rr_status"] == "DIAGNOSTIC_ONLY"
    assert result["research_rr_data"]["rr_valid"] is False


def test_forming_macd_setup_can_use_research_trend_threshold(monkeypatch) -> None:
    _assessment_components(monkeypatch)
    monkeypatch.setattr(
        technical_assessment,
        "score_trend",
        lambda df, config: (0.60, "TREND_FORMING"),
    )
    monkeypatch.setattr(
        technical_assessment,
        "calculate_setup_readiness",
        lambda *args, **kwargs: {
            "setup_readiness_score": 78.0,
            "setup_readiness_state": "FORMING",
            "setup_candidate_type": "MACD_MOMENTUM",
            "setup_readiness_reason": "macd_momentum_forming_score_78",
            "setup_readiness_components": "{}",
        },
    )
    result = technical_assessment.evaluate_technical_opportunity(
        _daily_frame(),
        {"risk_reward": {"min_rr_absolute": 1.5}},
        liquidity={"liquidity_core_pass": True, "liquidity_score": 0.9},
        evidence={
            "technical_close": 189.0,
            "technical_sma200": 179.0,
            "technical_distance_ema20_pct": 0.02,
            "technical_distance_ema20_atr": 0.9,
            "daily_macd_trajectory_state": "ACCELERATING",
            "weekly_macd_trajectory_state": "IMPROVING_STEADY",
            "momentum_acceleration_score": 80.0,
            "momentum_persistence_score": 80.0,
        },
    )

    assert result["technical_analysis_lane"] == "ADVANCE_RESEARCH_ANALYSIS"
    assert result["trend_setup_compatibility"] == "INCOMPATIBLE"
    assert result["research_trend_compatibility"] == "COMPATIBLE"


def test_research_lane_is_never_execution_ready_or_posttest_eligible() -> None:
    row = {
        "ticker": "TEST",
        "technical_analysis_lane": "ADVANCE_RESEARCH_ANALYSIS",
        "deep_analysis_tier": "RESEARCH",
        "signal": "WATCHLIST",
        "recommendation": "WATCHLIST_MONITOR",
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
        "scenario_status": "VALID_TRIGGER",
        "scenario_eligible_for_backtest": True,
        "rr": 2.0,
        "rr_status": "VALIDATED",
        "actionable_entry": 100.0,
        "actionable_stop": 95.0,
        "actionable_target": 110.0,
    }

    readiness = calculate_operational_readiness(row)
    assert readiness["execution_readiness_status"] == "NOT_OPERABLE"
    assert readiness["operational_readiness_bucket"] == "R_RESEARCH"
    assert _is_buy_now_candidate(pd.Series(row)) is False


def test_forming_setup_levels_remain_shadow_only() -> None:
    levels = calculate_shadow_levels(
        _daily_frame(),
        scenario={"scenario_status": "WAIT_FOR_CONFIRMATION"},
        setup_type="PULLBACK",
        rr_data={"stop": 186.0, "target": 197.0},
        config={},
        diagnostic_only=True,
    )

    assert levels["shadow_entry"] is not None
    assert levels["shadow_stop"] is not None
    assert levels["shadow_target"] is not None
    assert levels["shadow_level_status"] == "DIAGNOSTIC_ONLY"


def test_candidate_funnel_keeps_operational_and_research_without_quota() -> None:
    candidates = [
        {
            "ticker": "AAA",
            "technical_analysis_lane": "ADVANCE_DEEP_ANALYSIS",
            "technical_opportunity_score": 80,
        },
        {
            "ticker": "BBB",
            "technical_analysis_lane": "ADVANCE_RESEARCH_ANALYSIS",
            "technical_opportunity_score": 90,
        },
        {
            "ticker": "CCC",
            "technical_analysis_lane": "RADAR_FORMING_SETUP",
            "technical_opportunity_score": 95,
        },
    ]

    selected, audit = select_deep_analysis_candidates(
        candidates,
        target_tickers=1,
        min_tickers=1,
        max_tickers=1,
    )

    assert selected == ["AAA", "BBB"]
    assert audit["AAA"]["deep_analysis_tier"] == "OPERATIONAL"
    assert audit["BBB"]["deep_analysis_tier"] == "RESEARCH"
    assert audit["CCC"]["deep_analysis_selected"] is False


def test_atr_only_target_is_diagnostic_not_operational(monkeypatch) -> None:
    frame = _daily_frame()
    structure = {
        "setup_type": "PULLBACK",
        "trigger_level": float(frame["close"].iloc[-1]),
    }
    result = score_risk_reward(
        frame,
        structure,
        {"risk_reward": {"min_rr_absolute": 1.5}},
    )

    assert result["rr_status"] in {"DIAGNOSTIC_ONLY", "VALIDATED"}
    if result["target_validation_source"] == "ATR_PROJECTION":
        assert result["rr_valid"] is False


def test_stale_ohlcv_cache_is_auditable_fallback(tmp_path, monkeypatch) -> None:
    frame = _daily_frame(periods=5)
    cache_path = price_client._cache_path(tmp_path, "AAA")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    pd.to_pickle(
        {
            "fetched_at": (
                datetime.now(timezone.utc) - timedelta(hours=2)
            ).isoformat(),
            "frame": frame,
        },
        cache_path,
    )
    monkeypatch.setattr(price_client, "_download_batch", lambda *args, **kwargs: {})

    class _EmptyTicker:
        def history(self, **kwargs):
            return pd.DataFrame()

    monkeypatch.setattr(price_client.yf, "Ticker", lambda ticker: _EmptyTicker())
    stats: dict = {}
    result = price_client.download_daily_prices(
        ["AAA"],
        cache_dir=tmp_path,
        cache_ttl_minutes=1,
        max_stale_hours=4,
        max_individual_fallbacks=1,
        stats=stats,
    )

    assert "AAA" in result
    assert stats["cache_status_by_ticker"]["AAA"] == "STALE_FALLBACK"
    assert stats["missing_tickers"] == []


def test_scan_audit_does_not_require_rr_for_rows_outside_deep_analysis() -> None:
    rows = []
    for index in range(10):
        rows.append(
            {
                "ticker": f"T{index}",
                "signal": "AVOID",
                "final_score": 0.0,
                "entry": None,
                "stop": None,
                "target": None,
                "rr": None,
                "rr_status": "NOT_APPLICABLE_FORMING_SETUP",
                "setup_type": "NO_VALID_SETUP",
                "trend_score": 0.5,
                "liquidity_pass": True,
                "deep_analysis_selected": False,
                "technical_prefilter_status": "FAIL",
                "data_quality_score": 0.0,
                "data_quality_confidence": "LOW",
                "veto_reasons": "",
            }
        )

    report = audit_scan_dataframe(pd.DataFrame(rows))

    assert not any("rr faltante" in issue for issue in report["issues"])
