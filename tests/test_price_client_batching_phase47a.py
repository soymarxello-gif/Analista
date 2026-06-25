from __future__ import annotations

import pandas as pd

from data import price_client


def _frame(ticker: str, value: float = 20.0) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=3, freq="D")
    columns = pd.MultiIndex.from_product(
        [[ticker], ["Open", "High", "Low", "Close", "Volume"]]
    )
    return pd.DataFrame(
        [[value, value + 1, value - 1, value, 1_000_000]] * 3,
        index=index,
        columns=columns,
    )


def test_bulk_download_retries_missing_tickers_in_group(monkeypatch):
    calls: list[tuple[str, ...]] = []

    def fake_download(*, tickers, **kwargs):
        requested = tuple(tickers)
        calls.append(requested)
        if requested == ("AAA", "BBB"):
            return _frame("AAA")
        if requested == ("BBB",):
            return _frame("BBB")
        raise AssertionError(requested)

    monkeypatch.setattr(price_client.yf, "download", fake_download)
    stats: dict = {}

    result = price_client.download_daily_prices(
        ["AAA", "BBB"],
        batch_size=10,
        retry_batch_size=10,
        max_individual_fallbacks=0,
        stats=stats,
    )

    assert set(result) == {"AAA", "BBB"}
    assert calls == [("AAA", "BBB"), ("BBB",)]
    assert stats["batch_calls"] == 1
    assert stats["retry_batch_calls"] == 1
    assert stats["individual_fallback_calls"] == 0


def test_individual_fallback_is_capped(monkeypatch):
    monkeypatch.setattr(
        price_client.yf,
        "download",
        lambda **kwargs: pd.DataFrame(),
    )
    individual_calls: list[str] = []

    class FakeTicker:
        def __init__(self, ticker):
            self.ticker = ticker

        def history(self, **kwargs):
            individual_calls.append(self.ticker)
            return _frame(self.ticker).droplevel(0, axis=1)

    monkeypatch.setattr(price_client.yf, "Ticker", FakeTicker)
    stats: dict = {}

    result = price_client.download_daily_prices(
        ["AAA", "BBB", "CCC"],
        batch_size=10,
        retry_batch_size=10,
        max_individual_fallbacks=1,
        stats=stats,
    )

    assert set(result) == {"AAA"}
    assert individual_calls == ["AAA"]
    assert stats["individual_fallback_calls"] == 1
    assert stats["individual_fallback_skipped"] == 2
    assert stats["missing_tickers"] == ["BBB", "CCC"]
