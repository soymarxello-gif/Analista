from __future__ import annotations

from datetime import datetime, timedelta, timezone

from institutional.decision import DecisionEngine, DecisionInput
from institutional.features import DiscoveryEngine, calendar_weekly_closes
from institutional.models import DataStatus, DecisionState, PriceBar

NOW = datetime(2026, 7, 21, 20, tzinfo=timezone.utc)


def bar(session: datetime, close: float, volume: int = 1_000_000) -> PriceBar:
    return PriceBar("AAA", session, close, close + 1, close - 1, close, volume, session + timedelta(hours=8), "TEST", "SIP", True)


def test_weekly_bars_use_calendar_weeks_not_arbitrary_chunks_of_five():
    sessions = [
        datetime(2026, 6, 29, 20, tzinfo=timezone.utc),
        datetime(2026, 6, 30, 20, tzinfo=timezone.utc),
        datetime(2026, 7, 1, 20, tzinfo=timezone.utc),
        datetime(2026, 7, 2, 20, tzinfo=timezone.utc),  # Friday holiday week: four sessions.
        datetime(2026, 7, 6, 20, tzinfo=timezone.utc),
        datetime(2026, 7, 7, 20, tzinfo=timezone.utc),
    ]
    weekly = calendar_weekly_closes([bar(session, 100 + index) for index, session in enumerate(sessions)])
    assert weekly == [103.0, 105.0]


def test_discovery_enforces_canonical_rsi_filters_before_ranking():
    bars = []
    for index in range(240):
        session = NOW - timedelta(days=350 - index)
        close = 100 + index * 0.03 + ((index % 10) - 5) * 0.4
        bars.append(bar(session, close))
    result = DiscoveryEngine().evaluate("AAA", bars, NOW)
    assert result.eligible == (25 <= result.rsi14 <= 65 and result.rsi6 > result.rsi14)
    assert result.feature_hash


def test_closed_market_preserves_valid_setup_for_next_session():
    result = DecisionEngine().decide(
        DecisionInput(
            setup_valid=True,
            setup_quality=82,
            required_data_statuses=(DataStatus.COMPLETE, DataStatus.COMPLETE),
            market_session_open=False,
            quote_fresh=False,
            risk_plan_valid=True,
        )
    )
    assert result.state == DecisionState.READY_FOR_NEXT_SESSION
    assert "market_closed_setup_preserved" in result.reasons


def test_unknown_required_data_is_not_neutral_score_and_blocks_execution():
    result = DecisionEngine().decide(
        DecisionInput(
            setup_valid=True,
            setup_quality=90,
            required_data_statuses=(DataStatus.COMPLETE, DataStatus.UNAVAILABLE),
            market_session_open=True,
            quote_fresh=True,
            trigger_confirmed=True,
        )
    )
    assert result.data_confidence == 50
    assert result.state == DecisionState.DATA_BLOCKED


def test_hard_veto_is_distinct_from_missing_data():
    result = DecisionEngine().decide(
        DecisionInput(
            setup_valid=True,
            setup_quality=95,
            hard_vetoes=("price_below_minimum",),
            required_data_statuses=(DataStatus.COMPLETE,),
        )
    )
    assert result.state == DecisionState.HARD_VETO
