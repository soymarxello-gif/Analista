from __future__ import annotations

import pandas as pd

from ui import formatters


def test_spanish_column_labels_are_operator_friendly():
    assert formatters.spanish_column_label("final_trade_score") == "Score operativo"
    assert formatters.spanish_column_label("execution_quote_quality") == "Calidad ejecución"
    assert formatters.spanish_column_label("actionable_entry") == "Entrada"


def test_numeric_display_uses_max_two_decimals():
    assert formatters.format_number(123.4567) == "123.46"
    assert formatters.format_score("87.345") == "87.34"
    assert formatters.format_price(101.2) == "$101.20"


def test_negative_trading_values_are_detected_for_red_styling():
    for value in ["VETO", "AVOID", "LOW", "MISSING", "INVALID", "STALE_POSSIBLE", "BLOCKED"]:
        assert formatters.is_negative_trading_value(value)
        assert formatters.trading_value_class(value) == "negative"


def test_prepare_display_dataframe_translates_headers_and_rounds_numbers():
    df = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "final_trade_score": "77.777",
                "actionable_entry": "101.234",
                "quote_status": "INVALID",
            }
        ]
    )

    display = formatters.prepare_display_dataframe(
        df,
        columns=["ticker", "final_trade_score", "actionable_entry", "quote_status"],
    )

    assert list(display.columns) == ["Ticker", "Score operativo", "Entrada", "Estado quote"]
    assert display.iloc[0]["Score operativo"] == 77.78
    assert display.iloc[0]["Entrada"] == 101.23
