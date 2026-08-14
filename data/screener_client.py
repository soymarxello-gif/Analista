from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


@dataclass
class ScreenerResult:
    dataframe: pd.DataFrame
    used_fallback: bool
    warnings: list[str]


def _extract_quotes(payload: Any) -> list[dict]:
    """Best-effort parser for yfinance.screen responses."""
    if payload is None:
        return []
    if isinstance(payload, dict):
        if "quotes" in payload and isinstance(payload["quotes"], list):
            return payload["quotes"]
        if "finance" in payload:
            return payload.get("finance", {}).get("result", [{}])[0].get("quotes", [])
        if "body" in payload and isinstance(payload["body"], dict):
            return payload["body"].get("quotes", [])
    if isinstance(payload, list):
        return payload
    return []


def run_screeners(config: dict) -> ScreenerResult:
    warnings: list[str] = []
    rows: list[dict] = []
    used_fallback = False

    screener_cfg = config.get("screener", {})
    channels = screener_cfg.get("channels", {})
    cache_dir = Path("cache/screener")
    cache_dir.mkdir(parents=True, exist_ok=True)

    if yf is None:
        warnings.append("yfinance no está disponible. Se usará lista fallback.")
    else:
        for channel_name, channel_cfg in channels.items():
            if not channel_cfg or not channel_cfg.get("enabled", False):
                continue
            try:
                payload = yf.screen(channel_name, count=screener_cfg.get("max_results_per_query", 250))
                if config.get("development", {}).get("save_raw_screener_response", True):
                    with (cache_dir / f"{channel_name}.json").open("w", encoding="utf-8") as f:
                        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

                quotes = _extract_quotes(payload)
                for q in quotes:
                    symbol = q.get("symbol") or q.get("ticker")
                    if not symbol:
                        continue
                    rows.append({
                        "ticker": symbol,
                        "company": q.get("shortName") or q.get("longName") or q.get("name"),
                        "exchange": q.get("exchange"),
                        "quote_type": q.get("quoteType"),
                        "sector": q.get("sector"),
                        "industry": q.get("industry"),
                        "price": q.get("regularMarketPrice") or q.get("intradayprice"),
                        "market_cap": q.get("marketCap") or q.get("intradaymarketcap"),
                        "source_channel": channel_name,
                    })
            except Exception as exc:
                warnings.append(f"Fallo screener '{channel_name}': {exc}")

    if not rows:
        used_fallback = True
        tickers = screener_cfg.get("legacy_research_fallback_tickers", [])
        rows = [{"ticker": t, "source_channel": "manual_fallback"} for t in tickers]
        warnings.append("Se usó lista fallback manual de tickers.")

    df = pd.DataFrame(rows)
    if df.empty:
        return ScreenerResult(df, used_fallback, warnings)

    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df = df.drop_duplicates(subset=["ticker"], keep="first").reset_index(drop=True)
    return ScreenerResult(df, used_fallback, warnings)
