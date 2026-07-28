from __future__ import annotations

from engine.data_sources import analysis_quotes


def test_alpaca_iex_batch_quote_normalizes_delayed_analysis_fields() -> None:
    def fake_request(url: str, headers: dict[str, str], timeout_seconds: int):
        assert headers["APCA-API-KEY-ID"] == "KEY"
        assert headers["APCA-API-SECRET-KEY"] == "SECRET"
        if "quotes/latest" in url:
            return 200, {
                "quotes": {
                    "AAPL": {
                        "bp": 199.10,
                        "ap": 199.30,
                        "t": "2026-06-23T18:00:00Z",
                    }
                }
            }
        if "trades/latest" in url:
            return 200, {
                "trades": {
                    "AAPL": {
                        "p": 199.20,
                        "t": "2026-06-23T18:00:01Z",
                    }
                }
            }
        raise AssertionError(f"unexpected url: {url}")

    quotes = analysis_quotes.fetch_alpaca_iex_analysis_quotes(
        ["AAPL"],
        timeout_seconds=3,
        request_fn=fake_request,
        credentials={"key": "KEY", "secret": "SECRET"},
    )

    row = quotes["AAPL"]
    assert row["analysis_price"] == 199.20
    assert row["analysis_bid"] == 199.10
    assert row["analysis_ask"] == 199.30
    assert row["analysis_quote_source"] == "ALPACA_IEX_READ_ONLY"
    assert row["analysis_quote_freshness"] == "DELAYED_15_MIN"
    assert row["analysis_quote_confidence"] == "MEDIUM"


def test_alpaca_iex_batches_large_symbol_lists() -> None:
    tickers = [f"T{i:03d}" for i in range(205)]
    quote_calls: list[str] = []
    trade_calls: list[str] = []

    def fake_request(url: str, headers: dict[str, str], timeout_seconds: int):
        assert headers["APCA-API-KEY-ID"] == "KEY"
        symbols = url.split("symbols=", 1)[1].split("&", 1)[0].split(",")
        if "quotes/latest" in url:
            quote_calls.append(url)
            return 200, {
                "quotes": {
                    symbol: {"bp": 99.9, "ap": 100.1, "t": "2026-06-23T18:00:00Z"}
                    for symbol in symbols
                }
            }
        if "trades/latest" in url:
            trade_calls.append(url)
            return 200, {
                "trades": {
                    symbol: {"p": 100.0, "t": "2026-06-23T18:00:01Z"}
                    for symbol in symbols
                }
            }
        raise AssertionError(f"unexpected url: {url}")

    quotes = analysis_quotes.fetch_alpaca_iex_analysis_quotes(
        tickers,
        timeout_seconds=3,
        batch_size=100,
        request_fn=fake_request,
        credentials={"key": "KEY", "secret": "SECRET"},
    )

    assert len(quotes) == 205
    assert len(quote_calls) == 3
    assert len(trade_calls) == 3
    assert quotes["T204"]["analysis_quote_source"] == "ALPACA_IEX_READ_ONLY"


def test_alpaca_missing_credentials_returns_empty(monkeypatch) -> None:
    for name in ["APCA_API_KEY_ID", "ALPACA_API_KEY_ID", "APCA_API_SECRET_KEY", "ALPACA_API_SECRET_KEY"]:
        monkeypatch.delenv(name, raising=False)

    result = analysis_quotes.build_analysis_quote_fallbacks(["AAPL"], {"data_sources": {}})

    assert result == {}


def test_default_alpaca_fallback_covers_beyond_legacy_75_limit(monkeypatch) -> None:
    tickers = [f"T{i:03d}" for i in range(100)]
    selected: list[str] = []
    monkeypatch.setattr(analysis_quotes, "alpaca_credentials_present", lambda: True)

    def fake_fetch(tickers_arg, **kwargs):
        selected.extend(tickers_arg)
        return {
            ticker: {
                "analysis_price": 100.0,
                "analysis_quote_source": "ALPACA_IEX_READ_ONLY",
            }
            for ticker in tickers_arg
        }

    monkeypatch.setattr(analysis_quotes, "fetch_alpaca_iex_analysis_quotes", fake_fetch)

    result = analysis_quotes.build_analysis_quote_fallbacks(
        tickers,
        {
            "data_sources": {
                "analysis_quotes": {"enabled": True},
                "providers": {"alpaca_iex": {"enabled": True}},
            }
        },
    )

    assert len(selected) == 100
    assert result["T099"]["analysis_quote_source"] == "ALPACA_IEX_READ_ONLY"


def test_analysis_quote_fallback_does_not_overwrite_valid_yahoo_quote() -> None:
    row = {
        "ticker": "AAPL",
        "quote_status": "VALID",
        "execution_quote_quality": "HIGH",
        "analysis_price": 200.0,
        "analysis_bid": 199.9,
        "analysis_ask": 200.1,
        "analysis_quote_source": "yfinance",
        "secondary_data_sources_used": "",
    }
    quote = {
        "analysis_price": 201.0,
        "analysis_bid": 200.9,
        "analysis_ask": 201.1,
        "analysis_spread_pct": 0.001,
        "analysis_quote_source": "ALPACA_IEX_READ_ONLY",
        "analysis_quote_timestamp": "2026-06-23T18:00:01Z",
        "analysis_quote_freshness": "DELAYED_15_MIN",
        "analysis_quote_confidence": "MEDIUM",
    }

    out = analysis_quotes.apply_analysis_quote_fallback(row, quote)

    assert out["analysis_price"] == 200.0
    assert out["analysis_quote_source"] == "yfinance"
    assert out["secondary_data_sources_used"] == ""


def test_analysis_quote_fallback_fills_missing_without_touching_execution_fields() -> None:
    row = {
        "ticker": "AAPL",
        "quote_status": "MISSING",
        "execution_quote_quality": "LOW",
        "analysis_price": None,
        "analysis_bid": None,
        "analysis_ask": None,
        "analysis_quote_source": "yfinance",
        "analysis_quote_confidence": "UNKNOWN",
        "secondary_data_sources_used": "",
        "secondary_data_notes": "",
    }
    quote = {
        "analysis_price": 199.20,
        "analysis_bid": 199.10,
        "analysis_ask": 199.30,
        "analysis_spread_pct": 0.001004,
        "analysis_quote_source": "ALPACA_IEX_READ_ONLY",
        "analysis_quote_timestamp": "2026-06-23T18:00:01Z",
        "analysis_quote_freshness": "DELAYED_15_MIN",
        "analysis_quote_confidence": "MEDIUM",
    }

    out = analysis_quotes.apply_analysis_quote_fallback(row, quote)

    assert out["analysis_price"] == 199.20
    assert out["analysis_quote_source"] == "ALPACA_IEX_READ_ONLY"
    assert out["analysis_quote_freshness"] == "DELAYED_15_MIN"
    assert out["secondary_data_sources_used"] == "ALPACA_IEX_READ_ONLY"
    assert out["quote_status"] == "MISSING"
    assert out["execution_quote_quality"] == "LOW"


def test_disabled_analysis_quote_config_skips_fetch(monkeypatch) -> None:
    monkeypatch.setenv("APCA_API_KEY_ID", "KEY")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "SECRET")

    result = analysis_quotes.build_analysis_quote_fallbacks(
        ["AAPL"],
        {"data_sources": {"analysis_quotes": {"enabled": False}}},
    )

    assert result == {}


def test_fallback_ticker_selection_prioritizes_only_bad_execution_quotes() -> None:
    selected = analysis_quotes.select_analysis_quote_fallback_tickers(
        [
            {
                "ticker": "GOOD",
                "quote_status": "VALID",
                "execution_quote_quality": "HIGH",
            },
            {
                "ticker": "MISS",
                "quote_status": "MISSING",
                "execution_quote_quality": "LOW",
            },
            {
                "ticker": "STALE",
                "quote_status": "STALE_POSSIBLE",
                "execution_quote_quality": "LOW",
            },
            {
                "ticker": "MISS",
                "quote_status": "MISSING",
                "execution_quote_quality": "LOW",
            },
        ]
    )

    assert selected == ["MISS", "STALE"]
