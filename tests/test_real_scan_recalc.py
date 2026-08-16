from datetime import date

from tools.recalculate_real_scans_backtest import Bar, Contract, evaluate_backtest


def contract(expiration=20):
    return Contract(
        observation_id="run-TEST",
        run_id="run",
        ticker="TEST",
        decision_date=date(2026, 1, 1),
        decision_timestamp_utc=1,
        setup_type="BREAKOUT",
        macro_regime="RISK_ON",
        sector="TECHNOLOGY",
        signal="TRIGGER_CONFIRMED",
        legacy_rank=1,
        proposed_rank=1,
        p0_valid=True,
        trigger_price=105.0,
        maximum_entry=105.0 * 1.0005,
        stop_price=95.0,
        target_price=115.0,
        expiration_sessions=expiration,
    )


def bar(day, open_, high, low, close):
    return Bar(date(2026, 1, day), open_, high, low, close)


def test_late_entry_expires_at_end_of_decision_window():
    result = evaluate_backtest(
        contract(expiration=4),
        [
            bar(2, 100.0, 104.0, 99.0, 103.0),
            bar(3, 101.0, 104.5, 100.0, 104.0),
            bar(4, 104.0, 106.0, 103.0, 105.0),
            bar(5, 106.0, 110.0, 104.0, 109.0),
        ],
    )
    assert result.activated is True
    assert result.status == "CLOSED_EXPIRED"
    assert result.exit_reason == "EXPIRED"
    assert result.holding_sessions == 2
    assert result.exit_session == "2026-01-05"


def test_intraday_entry_does_not_use_pretrigger_low_for_mae():
    result = evaluate_backtest(
        contract(expiration=2),
        [
            bar(2, 100.0, 107.0, 96.0, 106.0),
            bar(3, 106.0, 110.0, 103.0, 109.0),
        ],
    )
    assert result.activated is True
    assert result.mae_pct is not None
    assert -2.1 < result.mae_pct < -1.8
    assert result.mfe_pct is not None
    assert result.mfe_pct > 4.0


def test_entry_stop_same_bar_withholds_excursions():
    result = evaluate_backtest(
        contract(expiration=2),
        [bar(2, 100.0, 107.0, 94.0, 102.0), bar(3, 102.0, 104.0, 98.0, 101.0)],
    )
    assert result.activated is True
    assert result.status == "CLOSED_AMBIGUOUS"
    assert result.exit_reason == "AMBIGUOUS_ENTRY_STOP_SAME_BAR"
    assert result.mfe_pct is None
    assert result.mae_pct is None
    assert result.trade_return_r is None
