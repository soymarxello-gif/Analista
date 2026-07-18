from __future__ import annotations

import pandas as pd

from engine.data_telemetry import TelemetryState, timed_call


def _ticker_count(df) -> int:
    if isinstance(df, pd.DataFrame) and "ticker" in df.columns:
        return int(df["ticker"].dropna().astype(str).nunique())
    return 0


def install_data_telemetry(scanner_module) -> TelemetryState:
    """Instrument scanner data clients for one run without changing outputs."""
    state = TelemetryState()
    original_screeners = scanner_module.run_screeners
    original_enrich = scanner_module.enrich_metadata
    original_download = scanner_module.download_daily_prices
    original_options = scanner_module.fetch_options_metrics

    def run_screeners(config):
        def coverage(result):
            return _ticker_count(getattr(result, "dataframe", None))

        return timed_call(
            state.source("screeners"),
            original_screeners,
            config,
            requested=1,
            coverage_fn=coverage,
        )

    def enrich(df, config):
        requested = _ticker_count(df)
        return timed_call(
            state.source("fundamentals_yahoo"),
            original_enrich,
            df,
            config,
            requested=requested,
            coverage_fn=_ticker_count,
            cache_hits_fn=lambda result: int(
                (result.get("metadata_source") == "cache").sum()
            )
            if isinstance(result, pd.DataFrame)
            and "metadata_source" in result
            else 0,
        )

    def download(tickers, *args, **kwargs):
        symbols = list(tickers)

        def coverage(result):
            return sum(
                1
                for symbol in symbols
                if result.get(symbol) is not None
                and not result.get(symbol).empty
            )

        return timed_call(
            state.source("price_history_yahoo"),
            original_download,
            symbols,
            *args,
            requested=len(symbols),
            coverage_fn=coverage,
            **kwargs,
        )

    def options(ticker, spot, config):
        result = timed_call(
            state.source("options_yahoo"),
            original_options,
            ticker,
            spot,
            config,
            requested=1,
            coverage_fn=lambda value: int(
                bool(value.get("options_data_available"))
            )
            if isinstance(value, dict)
            else 0,
        )
        source = str(result.get("options_source") or "") if isinstance(result, dict) else ""
        if source == "cache":
            state.source("options_yahoo").cache_hits += 1
        return result

    scanner_module.run_screeners = run_screeners
    scanner_module.enrich_metadata = enrich
    scanner_module.download_daily_prices = download
    scanner_module.fetch_options_metrics = options
    return state
