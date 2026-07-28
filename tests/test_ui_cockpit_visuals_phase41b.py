from __future__ import annotations

import pandas as pd

from ui import formatters


def test_spanish_column_labels_are_operator_friendly():
    assert formatters.spanish_column_label("signal") == "Señal interna"
    assert formatters.spanish_column_label("execution_readiness_status") == "Estado operativo"
    assert formatters.spanish_column_label("scenario_status") == "Diagnóstico escenario"
    assert formatters.spanish_column_label("final_trade_score") == "Score operativo"
    assert formatters.spanish_column_label("execution_quote_quality") == "Calidad ejecución"
    assert formatters.spanish_column_label("actionable_entry") == "Entrada"
    assert formatters.spanish_column_label("latest_date") == "Fecha dato"


def test_numeric_display_uses_max_two_decimals():
    assert formatters.format_number(123.4567) == "123.46"
    assert formatters.format_score("87.345") == "87.34"
    assert formatters.format_price(101.2) == "$101.20"
    assert formatters.format_metric_value("Candidatos", 44.0) == "44"


def test_negative_trading_values_are_detected_for_red_styling():
    for value in [
        "VETO",
        "AVOID",
        "LOW",
        "MISSING",
        "INVALID",
        "STALE_POSSIBLE",
        "BLOCKED",
        "LATE_ENTRY_OVEREXTENDED",
        "WEAK_MOMENTUM",
        "STRUCTURE_INVALID",
        "LATE_ENTRY",
        "OVEREXTENDED",
        "MACD_HIST_DETERIORATING",
    ]:
        assert formatters.is_negative_trading_value(value)
        assert formatters.trading_value_class(value) == "negative"
    assert formatters.is_negative_trading_value("RISK_ON_SUPPORTIVE") is False


def test_new_timing_and_macd_labels_are_translated():
    assert formatters.display_status_label("LATE_ENTRY") == "Entrada tardía"
    assert formatters.display_status_label("HEALTHY") == "Sano"
    assert (
        formatters.display_status_label("MACD_HIST_BULLISH_INFLECTION_BELOW_ZERO")
        == "Histograma MACD girando bajo cero"
    )


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


def test_watchlist_default_columns_avoid_redundant_statuses():
    from app import WATCHLIST_DEFAULT_COLUMNS

    assert "execution_readiness_status" in WATCHLIST_DEFAULT_COLUMNS
    assert "operational_state" not in WATCHLIST_DEFAULT_COLUMNS
    assert "scenario_status" not in WATCHLIST_DEFAULT_COLUMNS
    assert "signal" not in WATCHLIST_DEFAULT_COLUMNS
    assert "recommendation" not in WATCHLIST_DEFAULT_COLUMNS


def test_unix_timestamp_is_rendered_as_readable_santiago_time():
    rendered = formatters.format_timestamp(1782432290.0995958)
    assert rendered != "1782432290.0995958"
    assert len(rendered) == 16
