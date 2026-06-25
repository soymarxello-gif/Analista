from __future__ import annotations

from engine.options_selection import select_options_tickers


def candidate(ticker: str, **overrides):
    data = {
        "ticker": ticker,
        "spot": 100.0,
        "preliminary_signal": "AVOID",
        "preliminary_trade_score": 60.0,
        "preliminary_final_score": 60.0,
        "setup_type": "PULLBACK",
        "liquidity_pass": True,
        "earnings_veto": False,
        "rr": 2.0,
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
    }
    data.update(overrides)
    return data


def test_options_selection_prioritizes_watchlist_over_high_scoring_veto() -> None:
    selected, audit = select_options_tickers(
        [
            candidate(
                "VETO1",
                preliminary_signal="VETO",
                preliminary_trade_score=95,
                setup_type="NO_VALID_SETUP",
            ),
            candidate(
                "WATCH",
                preliminary_signal="WATCHLIST",
                preliminary_trade_score=75,
            ),
        ],
        max_tickers=1,
    )

    assert selected == ["WATCH"]
    assert audit["WATCH"]["options_priority_reason"] == "preliminary_watchlist"


def test_options_selection_prefers_ready_and_trigger_states() -> None:
    selected, _ = select_options_tickers(
        [
            candidate("WATCH", preliminary_signal="WATCHLIST", preliminary_trade_score=90),
            candidate("READY", preliminary_signal="READY_WAIT_TRIGGER", preliminary_trade_score=80),
            candidate("TRIGGER", preliminary_signal="TRIGGER_CONFIRMED", preliminary_trade_score=70),
        ],
        max_tickers=3,
    )

    assert selected == ["TRIGGER", "READY", "WATCH"]


def test_options_selection_uses_quote_quality_within_same_signal() -> None:
    selected, _ = select_options_tickers(
        [
            candidate(
                "LOWQ",
                preliminary_signal="WATCHLIST",
                preliminary_trade_score=90,
                quote_status="STALE_POSSIBLE",
                execution_quote_quality="LOW",
            ),
            candidate(
                "HIGHQ",
                preliminary_signal="WATCHLIST",
                preliminary_trade_score=80,
            ),
        ],
        max_tickers=2,
    )

    assert selected == ["HIGHQ", "LOWQ"]


def test_options_selection_respects_budget_and_is_deterministic() -> None:
    selected, audit = select_options_tickers(
        [candidate(f"T{i:03d}", preliminary_signal="WATCHLIST") for i in range(100)],
        max_tickers=75,
    )

    assert len(selected) == 75
    assert selected[0] == "T000"
    assert selected[-1] == "T074"
    assert audit["T074"]["options_priority_rank"] == 75


def test_options_selection_skips_missing_spot() -> None:
    selected, audit = select_options_tickers(
        [candidate("NO_SPOT", spot=None)],
        max_tickers=10,
    )

    assert selected == []
    assert audit == {}
