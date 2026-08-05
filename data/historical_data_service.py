from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from config_loader import load_config
from data.price_client import download_daily_prices as download_yahoo_daily_prices
from engine.data_sources.market_data_engine import (
    MARKET_DATA_ENGINE_SOURCE,
    inspect_market_database,
    load_current_universe_from_database,
    load_daily_bars_from_database,
)


def _provider_config(config: dict) -> dict:
    return config.get("data_sources", {}).get("providers", {}).get("market_data_engine", {}) or {}


def configured_local_database(config: dict) -> Path:
    cfg = _provider_config(config)
    return Path(cfg.get("local_cache_path", "cache/market_data_engine/us_market_5y.db"))


def load_historical_prices(
    tickers: list[str],
    period: str = "1y",
    interval: str = "1d",
    *,
    config: dict | None = None,
    stats: dict | None = None,
    yahoo_fn=download_yahoo_daily_prices,
    **yahoo_kwargs,
) -> dict[str, pd.DataFrame]:
    config = config or load_config()
    telemetry = stats if stats is not None else {}
    normalized = list(dict.fromkeys(str(value).upper().strip() for value in tickers if str(value).strip()))
    cfg = _provider_config(config)
    db_path = configured_local_database(config)
    output: dict[str, pd.DataFrame] = {}
    db_health = {"status": "DISABLED"}
    if cfg.get("enabled", False) and interval == "1d" and db_path.is_file():
        db_health = inspect_market_database(db_path, max_stale_days=int(cfg.get("max_stale_days", 7)))
        if db_health.get("status") in {"PASS", "WARN"}:
            days = {"1y": 370, "2y": 735, "5y": 1835}.get(str(period).lower(), 370)
            start = (pd.Timestamp(date.today()) - pd.Timedelta(days=days)).date()
            output = load_daily_bars_from_database(db_path, normalized, start=start)

    missing = [ticker for ticker in normalized if ticker not in output or output[ticker].empty]
    yahoo_stats: dict = {}
    if missing:
        fallback = yahoo_fn(
            missing,
            period=period,
            interval=interval,
            stats=yahoo_stats,
            **yahoo_kwargs,
        )
        output.update(fallback)
    telemetry.update(
        {
            "provider": MARKET_DATA_ENGINE_SOURCE,
            "database_health": db_health,
            "database_tickers": sorted(set(normalized) - set(missing)),
            "database_ticker_count": len(set(normalized) - set(missing)),
            "yahoo_fallback_tickers": missing,
            "yahoo_fallback_count": len(missing),
            "yahoo_stats": yahoo_stats,
            "source_by_ticker": {
                ticker: MARKET_DATA_ENGINE_SOURCE if ticker not in missing else "YAHOO_FINANCE"
                for ticker in output
            },
            "cache_status_by_ticker": {
                ticker: "MARKET_DATA_ENGINE_LOCAL" if ticker not in missing else "YAHOO_FALLBACK"
                for ticker in output
            },
            "stale_fallback_tickers": [],
        }
    )
    return output


def load_market_data_universe(config: dict | None = None) -> tuple[pd.DataFrame, dict]:
    config = config or load_config()
    cfg = _provider_config(config)
    db_path = configured_local_database(config)
    if not cfg.get("enabled", False) or not db_path.is_file():
        return pd.DataFrame(), {"status": "DISABLED" if not cfg.get("enabled", False) else "MISSING"}
    health = inspect_market_database(db_path, max_stale_days=int(cfg.get("max_stale_days", 7)))
    if health.get("status") not in {"PASS", "WARN"}:
        return pd.DataFrame(), health
    return load_current_universe_from_database(db_path), health
