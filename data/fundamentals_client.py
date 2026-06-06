\
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import math
from typing import Any

import pandas as pd
from loguru import logger

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


def _safe_number(value: Any):
    if value is None:
        return None
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    except Exception:
        return value


def _load_cache(ticker: str, ttl_minutes: int) -> dict | None:
    path = Path("cache/fundamentals") / f"{ticker}.json"
    if not path.exists():
        return None
    try:
        age_minutes = (datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) / 60
        if age_minutes > ttl_minutes:
            return None
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache(ticker: str, data: dict) -> None:
    path = Path("cache/fundamentals")
    path.mkdir(parents=True, exist_ok=True)
    with (path / f"{ticker}.json").open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _extract_earnings_date(ticker_obj) -> tuple[str | None, int | None, str]:
    """
    Best-effort earnings extraction.
    Uses upcoming earnings_dates first; calendar as fallback.
    """
    now = datetime.now(timezone.utc)
    warnings = []

    # 1) earnings_dates
    try:
        ed = ticker_obj.get_earnings_dates(limit=8)
        if ed is not None and not ed.empty:
            idx = pd.to_datetime(ed.index, errors="coerce", utc=True)
            future = idx[idx >= now]
            if len(future) > 0:
                next_dt = future.min()
                days = int((next_dt.to_pydatetime() - now).days)
                return next_dt.date().isoformat(), days, ""
    except Exception as exc:
        warnings.append(f"earnings_dates no disponible: {exc}")

    # 2) calendar
    try:
        cal = ticker_obj.calendar
        if isinstance(cal, dict):
            raw = (
                cal.get("Earnings Date")
                or cal.get("earningsDate")
                or cal.get("EarningsDate")
            )
            if isinstance(raw, (list, tuple)) and raw:
                raw = raw[0]
            if raw is not None:
                dt = pd.to_datetime(raw, errors="coerce", utc=True)
                if pd.notna(dt):
                    days = int((dt.to_pydatetime() - now).days)
                    return dt.date().isoformat(), days, ""
    except Exception as exc:
        warnings.append(f"calendar no disponible: {exc}")

    return None, None, "; ".join(warnings)


def fetch_ticker_metadata(ticker: str, config: dict) -> dict:
    """
    Enrich ticker with metadata and tactical fundamentals from yfinance.
    It is intentionally best-effort; missing fields are returned as None.
    """
    ttl = (
        config.get("data_sources", {})
        .get("cache_ttl_minutes", {})
        .get("fundamentals", 1440)
    )

    cached = _load_cache(ticker, ttl)
    if cached is not None:
        cached["metadata_source"] = "cache"
        return cached

    if yf is None:
        return {
            "ticker": ticker,
            "metadata_source": "none",
            "fundamental_warning": "yfinance no disponible",
        }

    data = {"ticker": ticker, "metadata_source": "yfinance"}
    warnings = []

    try:
        tk = yf.Ticker(ticker)
        info = {}
        try:
            info = tk.get_info() or {}
        except Exception as exc:
            warnings.append(f"get_info falló: {exc}")
            try:
                info = tk.info or {}
            except Exception as exc2:
                warnings.append(f"info falló: {exc2}")
                info = {}

        # Identity / universe
        data.update({
            "company": info.get("shortName") or info.get("longName") or info.get("displayName"),
            "quote_type": info.get("quoteType"),
            "exchange": info.get("exchange"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "currency": info.get("currency"),
            "market_cap": _safe_number(info.get("marketCap")),
            "enterprise_value": _safe_number(info.get("enterpriseValue")),
            "shares_outstanding": _safe_number(info.get("sharesOutstanding")),
        })

        # Liquidity / market microstructure available from quote summary
        data.update({
            "average_volume": _safe_number(info.get("averageVolume")),
            "average_volume_10d": _safe_number(info.get("averageVolume10days")),
            "bid": _safe_number(info.get("bid")),
            "ask": _safe_number(info.get("ask")),
            "bid_size": _safe_number(info.get("bidSize")),
            "ask_size": _safe_number(info.get("askSize")),
            "regular_market_volume": _safe_number(info.get("regularMarketVolume") or info.get("volume")),
        })

        bid = data.get("bid")
        ask = data.get("ask")
        if isinstance(bid, (int, float)) and isinstance(ask, (int, float)) and bid > 0 and ask > 0 and ask >= bid:
            mid = (bid + ask) / 2
            data["spread_pct"] = (ask - bid) / mid if mid else None
        else:
            data["spread_pct"] = None

        # Valuation and profitability
        data.update({
            "trailing_pe": _safe_number(info.get("trailingPE")),
            "forward_pe": _safe_number(info.get("forwardPE")),
            "price_to_book": _safe_number(info.get("priceToBook")),
            "price_to_sales_ttm": _safe_number(info.get("priceToSalesTrailing12Months")),
            "enterprise_to_ebitda": _safe_number(info.get("enterpriseToEbitda")),
            "gross_margins": _safe_number(info.get("grossMargins")),
            "operating_margins": _safe_number(info.get("operatingMargins")),
            "profit_margins": _safe_number(info.get("profitMargins")),
            "return_on_equity": _safe_number(info.get("returnOnEquity")),
            "return_on_assets": _safe_number(info.get("returnOnAssets")),
            "debt_to_equity": _safe_number(info.get("debtToEquity")),
            "total_debt": _safe_number(info.get("totalDebt")),
            "total_cash": _safe_number(info.get("totalCash")),
            "free_cashflow": _safe_number(info.get("freeCashflow")),
            "operating_cashflow": _safe_number(info.get("operatingCashflow")),
        })

        # Growth / revisions proxy
        data.update({
            "revenue_growth": _safe_number(info.get("revenueGrowth")),
            "earnings_growth": _safe_number(info.get("earningsGrowth")),
            "earnings_quarterly_growth": _safe_number(info.get("earningsQuarterlyGrowth")),
            "eps_trailing_twelve_months": _safe_number(info.get("trailingEps")),
            "eps_forward": _safe_number(info.get("forwardEps")),
            "peg_ratio": _safe_number(info.get("pegRatio")),
        })

        # Ownership / positioning
        data.update({
            "held_percent_institutions": _safe_number(info.get("heldPercentInstitutions")),
            "held_percent_insiders": _safe_number(info.get("heldPercentInsiders")),
            "short_percent_float": _safe_number(info.get("shortPercentOfFloat")),
            "short_ratio": _safe_number(info.get("shortRatio")),
        })

        earnings_date, days_to_earnings, ew = _extract_earnings_date(tk)
        data["earnings_date"] = earnings_date
        data["days_to_earnings"] = days_to_earnings
        if ew:
            warnings.append(ew)

    except Exception as exc:
        warnings.append(f"metadata general falló: {exc}")

    data["fundamental_warning"] = "; ".join([w for w in warnings if w])
    _save_cache(ticker, data)
    return data


def enrich_metadata(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Fill missing sector/industry/company/earnings/fundamental columns.
    Limit can be configured to avoid making the scanner too slow.
    """
    if df.empty:
        return df

    enabled = config.get("fundamentals", {}).get("metadata_enrichment", {}).get("enabled", True)
    if not enabled:
        return df

    max_tickers = config.get("fundamentals", {}).get("metadata_enrichment", {}).get("max_tickers", 300)
    out = df.copy()
    tickers = out["ticker"].dropna().astype(str).str.upper().unique().tolist()[:max_tickers]

    rows = []
    for i, ticker in enumerate(tickers, start=1):
        try:
            rows.append(fetch_ticker_metadata(ticker, config))
        except Exception as exc:
            logger.warning(f"Metadata falló para {ticker}: {exc}")
            rows.append({"ticker": ticker, "fundamental_warning": str(exc), "metadata_source": "error"})

    meta = pd.DataFrame(rows)
    if meta.empty:
        return out

    # Merge with suffix, then coalesce original columns with enriched columns.
    merged = out.merge(meta, on="ticker", how="left", suffixes=("", "_enriched"))
    for col in ["company", "exchange", "quote_type", "sector", "industry", "market_cap", "price", "spread_pct"]:
        enriched_col = f"{col}_enriched"
        if enriched_col in merged.columns:
            if col not in merged.columns:
                merged[col] = merged[enriched_col]
            else:
                merged[col] = merged[col].where(merged[col].notna() & (merged[col].astype(str) != ""), merged[enriched_col])
            merged = merged.drop(columns=[enriched_col])

    return merged
