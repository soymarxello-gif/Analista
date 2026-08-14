from __future__ import annotations

import pandas as pd
import yfinance as yf
from loguru import logger


def download_daily_prices(tickers: list[str], period: str = "1y", interval: str = "1d") -> dict[str, pd.DataFrame]:
    """Download OHLCV data and return a dict ticker -> DataFrame."""
    if not tickers:
        return {}

    data: dict[str, pd.DataFrame] = {}
    try:
        raw = yf.download(
            tickers=tickers,
            period=period,
            interval=interval,
            group_by="ticker",
            auto_adjust=False,
            threads=True,
            progress=False,
        )
    except Exception as exc:
        logger.warning(f"yf.download batch falló: {exc}. Intentando ticker por ticker.")
        raw = None

    if raw is not None and not raw.empty:
        if isinstance(raw.columns, pd.MultiIndex):
            for t in tickers:
                if t in raw.columns.get_level_values(0):
                    df = raw[t].dropna(how="all").copy()
                    if not df.empty:
                        data[t] = _clean_ohlcv(df)
        else:
            # Single ticker case
            t = tickers[0]
            data[t] = _clean_ohlcv(raw.dropna(how="all").copy())

    missing = [t for t in tickers if t not in data]
    for t in missing:
        try:
            df = yf.Ticker(t).history(period=period, interval=interval, auto_adjust=False)
            if not df.empty:
                data[t] = _clean_ohlcv(df)
        except Exception as exc:
            logger.warning(f"No se pudo descargar precio para {t}: {exc}")

    return data


def _clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rename = {c: c.lower().replace(" ", "_") for c in df.columns}
    df = df.rename(columns=rename)
    for col in ["open", "high", "low", "close", "volume"]:
        if col not in df.columns:
            df[col] = pd.NA
    return df[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
