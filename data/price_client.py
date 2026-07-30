from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, time, timezone
from pathlib import Path
import re
from typing import Callable
from zoneinfo import ZoneInfo

from loguru import logger
import pandas as pd
import yfinance as yf

NEW_YORK = ZoneInfo("America/New_York")


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


def _cache_path(cache_dir: Path, ticker: str) -> Path:
    safe = re.sub(r"[^A-Z0-9._-]+", "_", ticker.upper())
    return cache_dir / f"{safe}.pkl"


def _read_cache(path: Path) -> tuple[pd.DataFrame | None, datetime | None]:
    try:
        payload = pd.read_pickle(path)
        if not isinstance(payload, dict):
            return None, None
        frame = payload.get("frame")
        fetched_at = pd.to_datetime(payload.get("fetched_at"), utc=True, errors="coerce")
        if not isinstance(frame, pd.DataFrame) or frame.empty or pd.isna(fetched_at):
            return None, None
        return frame, fetched_at.to_pydatetime()
    except Exception:
        return None, None


def _write_cache(path: Path, frame: pd.DataFrame, fetched_at: datetime) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.to_pickle(
            {"fetched_at": fetched_at.isoformat(), "frame": frame},
            path,
        )
    except Exception as exc:
        logger.warning(f"No se pudo guardar caché OHLCV {path.name}: {exc}")


def _cache_is_fresh(
    fetched_at: datetime,
    *,
    now: datetime,
    ttl_minutes: int,
) -> bool:
    age_minutes = max((now - fetched_at).total_seconds() / 60.0, 0.0)
    if age_minutes > max(int(ttl_minutes), 0):
        return False
    fetched_ny = fetched_at.astimezone(NEW_YORK)
    now_ny = now.astimezone(NEW_YORK)
    session_cutoff = time(16, 20)
    crossed_close = bool(
        fetched_ny.date() == now_ny.date()
        and fetched_ny.time() < session_cutoff <= now_ny.time()
    )
    return not crossed_close


def download_daily_prices(
    tickers: list[str],
    period: str = "1y",
    interval: str = "1d",
    *,
    batch_size: int = 150,
    retry_batch_size: int = 50,
    timeout_seconds: int = 15,
    max_individual_fallbacks: int = 10,
    cache_dir: str | Path | None = None,
    cache_ttl_minutes: int = 30,
    max_stale_hours: int = 72,
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
            "fresh_cache_tickers": [],
            "stale_fallback_tickers": [],
            "network_tickers": [],
            "cache_status_by_ticker": {},
        }
    )

    data: dict[str, pd.DataFrame] = {}
    stale_cache: dict[str, tuple[pd.DataFrame, datetime]] = {}
    cache_root = Path(cache_dir) if cache_dir else None
    now = datetime.now(timezone.utc)
    if cache_root is not None:
        for ticker in normalized:
            frame, fetched_at = _read_cache(_cache_path(cache_root, ticker))
            if frame is None or fetched_at is None:
                continue
            if _cache_is_fresh(
                fetched_at,
                now=now,
                ttl_minutes=cache_ttl_minutes,
            ):
                data[ticker] = frame
                telemetry["fresh_cache_tickers"].append(ticker)
                telemetry["cache_status_by_ticker"][ticker] = "FRESH_CACHE"
            elif (now - fetched_at).total_seconds() <= max(int(max_stale_hours), 0) * 3600:
                stale_cache[ticker] = (frame, fetched_at)

    network_tickers = [ticker for ticker in normalized if ticker not in data]
    telemetry["network_tickers"] = list(network_tickers)

    def _progress() -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(dict(telemetry))
        except Exception:
            pass

    for batch in _chunks(network_tickers, batch_size):
        telemetry["batch_calls"] += 1
        try:
            downloaded = _download_batch(
                    batch,
                    period=period,
                    interval=interval,
                    timeout_seconds=timeout_seconds,
                )
            data.update(downloaded)
            if cache_root is not None:
                fetched_at = datetime.now(timezone.utc)
                for ticker, frame in downloaded.items():
                    _write_cache(_cache_path(cache_root, ticker), frame, fetched_at)
                    telemetry["cache_status_by_ticker"][ticker] = "NETWORK"
        except Exception as exc:
            message = f"batch:{batch[0]}..{batch[-1]}:{type(exc).__name__}:{exc}"
            telemetry["download_errors"].append(message)
            logger.warning(f"yf.download batch falló: {message}")
        _progress()

    missing = [ticker for ticker in network_tickers if ticker not in data]
    for batch in _chunks(missing, retry_batch_size):
        telemetry["retry_batch_calls"] += 1
        try:
            downloaded = _download_batch(
                    batch,
                    period=period,
                    interval=interval,
                    timeout_seconds=timeout_seconds,
                )
            data.update(downloaded)
            if cache_root is not None:
                fetched_at = datetime.now(timezone.utc)
                for ticker, frame in downloaded.items():
                    _write_cache(_cache_path(cache_root, ticker), frame, fetched_at)
                    telemetry["cache_status_by_ticker"][ticker] = "NETWORK_RETRY"
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
                if cache_root is not None:
                    fetched_at = datetime.now(timezone.utc)
                    _write_cache(_cache_path(cache_root, ticker), data[ticker], fetched_at)
                    telemetry["cache_status_by_ticker"][ticker] = "NETWORK_INDIVIDUAL"
        except Exception as exc:
            message = f"individual:{ticker}:{type(exc).__name__}:{exc}"
            telemetry["download_errors"].append(message)
            logger.warning(f"No se pudo descargar precio para {ticker}: {exc}")
        _progress()

    still_missing = [ticker for ticker in normalized if ticker not in data]
    for ticker in still_missing:
        cached = stale_cache.get(ticker)
        if cached is None:
            continue
        data[ticker] = cached[0]
        telemetry["stale_fallback_tickers"].append(ticker)
        telemetry["cache_status_by_ticker"][ticker] = "STALE_FALLBACK"

    telemetry["downloaded_tickers"] = len(data)
    telemetry["missing_tickers"] = [ticker for ticker in normalized if ticker not in data]
    telemetry["individual_fallback_skipped"] = max(len(missing) - fallback_limit, 0)
    telemetry["provider_empty_tickers"] = list(telemetry["missing_tickers"])
    _progress()
    return data
