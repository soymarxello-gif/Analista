from __future__ import annotations

from datetime import datetime, timedelta, timezone

from institutional.models import DecisionState, PriceBar, SignalEvent
from institutional.outcomes import OutcomeEvaluator
from institutional.store import InstitutionalStore
from institutional.walkforward import ResearchObservation, RollingWalkForward, WalkForwardConfig

NOW = datetime(2026, 1, 2, 21, tzinfo=timezone.utc)


def signal(symbol: str = "OLD") -> SignalEvent:
    return SignalEvent(
        signal_id=f"sig-{symbol}",
        symbol=symbol,
        decision_time=NOW,
        available_at=NOW,
        setup_type="BREAKOUT",
        state=DecisionState.READY_FOR_NEXT_SESSION,
        setup_quality=80,
        data_confidence=100,
        regime_risk=30,
        execution_readiness=50,
        trigger_price=101,
        stop_price=98,
        target_price=107,
        maximum_entry=102,
        expiration_sessions=21,
        model_version="test",
        configuration_hash="c",
        universe_snapshot_hash="u",
        feature_hash="f",
    )


def future_bars(symbol: str = "OLD") -> list[PriceBar]:
    output = []
    for index in range(25):
        session = NOW + timedelta(days=index + 1)
        close = 101 + index * 0.25
        output.append(
            PriceBar(symbol, session, 100.5, close + 0.5, 99.5, close, 1_000_000, session + timedelta(hours=8), "TEST", "SIP", True)
        )
    return output


def test_outcome_evaluates_symbol_even_when_absent_from_current_universe():
    store = InstitutionalStore()
    store.put_signal(signal())
    store.put_price_bars(future_bars())
    outcome = OutcomeEvaluator(store).evaluate_all()[0]
    assert outcome.triggered
    assert outcome.return_5d_pct is not None
    assert store.outcomes()[0].signal_id == "sig-OLD"


def test_markout_counts_complete_sessions_after_entry_not_entry_bar():
    store = InstitutionalStore()
    store.put_price_bars(future_bars())
    outcome = OutcomeEvaluator(store).evaluate(signal())
    entry = outcome.entry_fill
    expected_session = future_bars()[5].close
    assert outcome.return_5d_pct == round((expected_session / entry - 1) * 100, 4)
    assert outcome.return_10d_pct is not None
    assert outcome.return_20d_pct is not None


def observation(index: int, return_r: float = 0.5) -> ResearchObservation:
    return ResearchObservation(
        observation_id=f"obs-{index}",
        decision_time=NOW + timedelta(days=index),
        setup_type="BREAKOUT" if index % 2 else "PULLBACK",
        regime="RISK_ON" if index % 3 else "RISK_OFF",
        sector="TECH",
        return_r=return_r,
    )


def test_walkforward_uses_multiple_rolling_folds_and_embargo():
    rows = [observation(index) for index in range(360)]
    engine = RollingWalkForward(
        WalkForwardConfig(
            train_size=100,
            validation_size=40,
            test_size=40,
            step_size=40,
            embargo_sessions=21,
            minimum_oos_closed=1,
            minimum_dominant_cell=1,
            bootstrap_samples=200,
        )
    )
    folds = engine.split(rows)
    assert len(folds) > 1
    assert all(fold.train[-1].decision_time < fold.validation[0].decision_time - timedelta(days=21) for fold in folds)
    assert all(fold.validation[-1].decision_time < fold.test[0].decision_time - timedelta(days=21) for fold in folds)


def test_promotion_requires_positive_confidence_interval_and_sample():
    rows = [observation(index, 0.5 if index % 5 else 0.2) for index in range(420)]
    report = RollingWalkForward(
        WalkForwardConfig(
            train_size=100,
            validation_size=40,
            test_size=40,
            step_size=40,
            embargo_sessions=5,
            minimum_oos_closed=200,
            minimum_dominant_cell=40,
            bootstrap_samples=400,
        )
    ).evaluate(rows)
    assert report.metrics.closed >= 200
    assert report.metrics.expectancy_ci95[0] > 0
    assert report.eligible_for_promotion
