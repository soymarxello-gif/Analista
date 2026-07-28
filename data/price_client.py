from __future__ import annotations

from collections.abc import Iterable
from typing import Callable

from loguru import logger
import pandas as pd
import yfinance as yf


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    size = max(int(size), 1)
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rename = {c: c.lower().replace(" ", "_") for c in df.columns}
    df = df.rename(columns=rename)
    for col in ["open", "high", "low", "close", "volume"]:
        if col not in df.columns:
            df[col] = pd.NA
    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]

    for col in ["open", "high", "low", "close", "adj_close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    close = df["close"].replace(0, pd.NA)
    factor = (df["adj_close"] / close).replace([float("inf"), float("-inf")], pd.NA)
    factor = factor.fillna(1.0)
    df["adj_factor"] = factor
    df["adj_open"] = df["open"] * factor
    df["adj_high"] = df["high"] * factor
    df["adj_low"] = df["low"] * factor

    columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "adj_close",
        "adj_factor",
        "adj_open",
        "adj_high",
        "adj_low",
    ]
    return df[columns].dropna(subset=["close"])


def _extract_batch(raw: pd.DataFrame | None, tickers: list[str]) -> dict[str, pd.DataFrame]:
    if raw is None or raw.empty:
        return {}

    data: dict[str, pd.DataFrame] = {}
    if isinstance(raw.columns, pd.MultiIndex):
        level_zero = set(raw.columns.get_level_values(0))
        for ticker in tickers:
            if ticker not in level_zero:
                continue
            frame = _clean_ohlcv(raw[ticker].dropna(how="all").copy())
            if not frame.empty:
                data[ticker] = frame
    elif len(tickers) == 1:
        frame = _clean_ohlcv(raw.dropna(how="all").copy())
        if not frame.empty:
            data[tickers[0]] = frame
    return data


def _download_batch(
    tickers: list[str],
    *,
    period: str,
    interval: str,
    timeout_seconds: int,
) -> dict[str, pd.DataFrame]:
    raw = yf.download(
        tickers=tickers,
        period=period,
        interval=interval,
        group_by="ticker",
        auto_adjust=False,
        threads=True,
        progress=False,
        timeout=timeout_seconds,
    )
    return _extract_batch(raw, tickers)


def download_daily_prices(
    tickers: list[str],
    period: str = "1y",
    interval: str = "1d",
    *,
    batch_size: int = 150,
    retry_batch_size: int = 50,
    timeout_seconds: int = 15,
    max_individual_fallbacks: int = 10,
    stats: dict | None = None,
    progress_callback: Callable[[dict], None] | None = None,
) -> dict[str, pd.DataFrame]:
    """Download OHLCV data in bounded batches and return ticker -> DataFrame."""
    normalized = list(dict.fromkeys(str(ticker).upper().strip() for ticker in tickers if str(ticker).strip()))
    if not normalized:
        return {}

    telemetry = stats if stats is not None else {}
    telemetry.update(
        {
            "requested_tickers": len(normalized),
            "batch_calls": 0,
            "retry_batch_calls": 0,
            "individual_fallback_calls": 0,
            "download_errors": [],
        }
    )

    data: dict[str, pd.DataFrame] = {}
    def _progress() -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(dict(telemetry))
        except Exception:
            pass

    for batch in _chunks(normalized, batch_size):
        telemetry["batch_calls"] += 1
        try:
            data.update(
                _download_batch(
                    batch,
                    period=period,
                    interval=interval,
                    timeout_seconds=timeout_seconds,
                )
            )
        except Exception as exc:
            message = f"batch:{batch[0]}..{batch[-1]}:{type(exc).__name__}:{exc}"
            telemetry["download_errors"].append(message)
            logger.warning(f"yf.download batch falló: {message}")
        _progress()

    missing = [ticker for ticker in normalized if ticker not in data]
    for batch in _chunks(missing, retry_batch_size):
        telemetry["retry_batch_calls"] += 1
        try:
            data.update(
                _download_batch(
                    batch,
                    period=period,
                    interval=interval,
                    timeout_seconds=timeout_seconds,
                )
            )
        except Exception as exc:
            message = f"retry:{batch[0]}..{batch[-1]}:{type(exc).__name__}:{exc}"
            telemetry["download_errors"].append(message)
            logger.warning(f"yf.download retry falló: {message}")
        _progress()

    missing = [ticker for ticker in normalized if ticker not in data]
    fallback_limit = max(int(max_individual_fallbacks), 0)
    for ticker in missing[:fallback_limit]:
        telemetry["individual_fallback_calls"] += 1
        try:
            frame = yf.Ticker(ticker).history(
                period=period,
                interval=interval,
                auto_adjust=False,
                timeout=timeout_seconds,
            )
            if frame is not None and not frame.empty:
                data[ticker] = _clean_ohlcv(frame)
        except Exception as exc:
            message = f"individual:{ticker}:{type(exc).__name__}:{exc}"
            telemetry["download_errors"].append(message)
            logger.warning(f"No se pudo descargar precio para {ticker}: {exc}")
        _progress()

    telemetry["downloaded_tickers"] = len(data)
    telemetry["missing_tickers"] = [ticker for ticker in normalized if ticker not in data]
    telemetry["individual_fallback_skipped"] = max(len(missing) - fallback_limit, 0)
    _progress()
    return data
