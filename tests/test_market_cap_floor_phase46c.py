from __future__ import annotations

import pandas as pd

from universe.equity_validator import validate_universe


def _row(market_cap: float) -> dict:
    return {
        "ticker": "TEST",
        "company": "Test Corp",
        "quote_type": "EQUITY",
        "exchange": "NMS",
        "price": 25.0,
        "market_cap": market_cap,
    }


def test_universe_rejects_market_cap_just_below_default_floor() -> None:
    result = validate_universe(pd.DataFrame([_row(2_499_999_999)]), {})

    assert result.empty


def test_universe_accepts_market_cap_at_default_floor() -> None:
    result = validate_universe(pd.DataFrame([_row(2_500_000_000)]), {})

    assert list(result["ticker"]) == ["TEST"]
