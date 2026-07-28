from __future__ import annotations

import pandas as pd

from universe.equity_validator import validate_universe


CONFIG = {
    "filters": {"min_price": 10, "min_market_cap_usd": 2_500_000_000},
    "universe": {
        "allowed_quote_types": ["EQUITY"],
        "exclude_name_contains": ["ETF", "ETN", "Fund", "Trust", "Preferred", "Warrant", "Unit", "Right"],
    },
}


def test_united_name_does_not_match_unit_security_type_filter() -> None:
    row = {
        "ticker": "URI",
        "company": "United Rentals, Inc.",
        "quote_type": "EQUITY",
        "exchange": "NYQ",
        "price": 1139.71,
        "market_cap": 71_000_000_000,
    }

    out = validate_universe(pd.DataFrame([row]), CONFIG, strict_metadata=True)

    assert out["ticker"].tolist() == ["URI"]


def test_unit_security_type_term_still_excludes_actual_unit() -> None:
    row = {
        "ticker": "XYZU",
        "company": "Example Acquisition Unit",
        "quote_type": "EQUITY",
        "exchange": "NYQ",
        "price": 12.00,
        "market_cap": 3_000_000_000,
    }

    out = validate_universe(pd.DataFrame([row]), CONFIG, strict_metadata=True)

    assert out.empty
