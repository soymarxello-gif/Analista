\
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_liquidity(ticker: str, df: pd.DataFrame, config: dict, metadata: dict | None = None) -> dict:
    cfg = config.get("liquidity", {})
    metadata = metadata or {}

    if df is None or df.empty or len(df) < 60:
        return {
            "ticker": ticker,
            "liquidity_pass": False,
            "liquidity_score": 0.0,
            "liquidity_warning": "historial insuficiente",
        }

    close = float(df["close"].iloc[-1])
    avg20 = float(df["volume"].tail(20).mean())
    avg60 = float(df["volume"].tail(60).mean())
    med20 = float(df["volume"].tail(20).median())
    mean20 = float(df["volume"].tail(20).mean())
    dollar20 = close * avg20
    ratio = med20 / mean20 if mean20 else 0

    spread_pct = metadata.get("spread_pct")
    max_spread = cfg.get("max_bid_ask_spread_pct", None)

    checks = [
        close >= cfg.get("min_price", 5),
        avg20 >= cfg.get("min_avg_volume_20d", 300000),
        avg60 >= cfg.get("min_avg_volume_60d", 250000),
        dollar20 >= cfg.get("min_dollar_volume_20d", 10000000),
        ratio >= cfg.get("min_median_to_mean_volume_ratio", 0.5),
    ]

    spread_warning = ""
    if spread_pct is not None and max_spread is not None:
        checks.append(spread_pct <= max_spread)
    elif max_spread is not None:
        spread_warning = "spread bid/ask no disponible; no se veta por spread"

    score = float(np.mean(checks))

    return {
        "ticker": ticker,
        "price": close,
        "avg_volume_20d": avg20,
        "avg_volume_60d": avg60,
        "dollar_volume_20d": dollar20,
        "median_volume_20d": med20,
        "mean_volume_20d": mean20,
        "median_to_mean_volume_ratio": ratio,
        "spread_pct": spread_pct,
        "bid": metadata.get("bid"),
        "ask": metadata.get("ask"),
        "average_volume_yf": metadata.get("average_volume"),
        "average_volume_10d_yf": metadata.get("average_volume_10d"),
        "regular_market_volume_yf": metadata.get("regular_market_volume"),
        "liquidity_pass": bool(all(checks)),
        "liquidity_score": score,
        "liquidity_warning": "" if all(checks) else "falló uno o más filtros de liquidez" + (f"; {spread_warning}" if spread_warning else ""),
    }
