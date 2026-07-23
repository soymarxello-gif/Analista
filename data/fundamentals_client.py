from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


CACHE_SCHEMA_VERSION = "2.0"
CACHE_DIR = Path("cache/fundamentals")


def _safe_number(value: Any):
    if value is None:
        return None
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    except Exception:
        return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _cache_path(ticker: str) -> Path:
    safe_ticker = str(ticker).strip().upper().replace("/", "-")
    return CACHE_DIR / f"{safe_ticker}.json"


def _load_cache(ticker: str, ttl_minutes: int) -> dict | None:
    path = _cache_path(ticker)
    if not path.exists():
        return None
    try:
        age_minutes = (_utc_now().timestamp() - path.stat().st_mtime) / 60
        if age_minutes > ttl_minutes:
            return None
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict):
            return None
        if payload.get("_cache_schema_version") != CACHE_SCHEMA_VERSION:
            return None
        data = payload.get("data")
        if not isinstance(data, dict):
            return None
        result = dict(data)
        result["cache_schema_version"] = CACHE_SCHEMA_VERSION
        result["cache_saved_at"] = payload.get("_cache_saved_at")
        return result
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _save_cache(ticker: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "_cache_schema_version": CACHE_SCHEMA_VERSION,
        "_cache_saved_at": _utc_now().isoformat(),
        "data": data,
    }
    with _cache_path(ticker).open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2, default=str)


def _normalize_market_session(value: Any) -> str:
    text = str(value or "UNKNOWN").strip().upper().replace("_", "").replace("-", "")
    aliases = {
        "PRE": "PRE",
        "PREPRE": "PRE",
        "PREMARKET": "PRE",
        "REGULAR": "REGULAR",
        "REGULARMARKET": "REGULAR",
        "POST": "POST",
        "POSTPOST": "POST",
        "POSTMARKET": "POST",
        "CLOSED": "CLOSED",
    }
    return aliases.get(text, "UNKNOWN")


def _extract_quote_context(info: dict, *, fetched_at: datetime | None = None) -> dict:
    """Extract quote time and market session from Yahoo quote-summary fields."""
    now = fetched_at or _utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    raw_state = info.get("marketState")
    session = _normalize_market_session(raw_state)
    regular_time = _safe_number(info.get("regularMarketTime"))
    pre_time = _safe_number(info.get("preMarketTime"))
    post_time = _safe_number(info.get("postMarketTime"))

    if session == "PRE":
        quote_timestamp = pre_time or regular_time
    elif session == "POST":
        quote_timestamp = post_time or regular_time
    else:
        quote_timestamp = regular_time or post_time or pre_time

    return {
        "quote_timestamp": quote_timestamp,
        "regular_market_time": regular_time,
        "pre_market_time": pre_time,
        "post_market_time": post_time,
        "market_session": session,
        "market_state_raw": raw_state,
        "metadata_fetched_at": now.isoformat(),
        "quote_timestamp_source": "yahoo_quote_summary" if quote_timestamp is not None else None,
    }


def _extract_earnings_date(ticker_obj) -> tuple[str | None, int | None, str]:
    """Best-effort upcoming earnings date extraction."""
    now = _utc_now()
    warnings = []

    try:
        earnings_dates = ticker_obj.get_earnings_dates(limit=8)
        if earnings_dates is not None and not earnings_dates.empty:
            index = pd.to_datetime(earnings_dates.index, errors="coerce", utc=True)
            future = index[index >= now]
            if len(future) > 0:
                next_dt = future.min()
                days = int((next_dt.to_pydatetime() - now).days)
                return next_dt.date().isoformat(), days, ""
    except Exception as exc:
        warnings.append(f"earnings_dates no disponible: {exc}")

    try:
        calendar = ticker_obj.calendar
        if isinstance(calendar, dict):
            raw = (
                calendar.get("Earnings Date")
                or calendar.get("earningsDate")
                or calendar.get("EarningsDate")
            )
            if isinstance(raw, (list, tuple)) and raw:
                raw = raw[0]
            if raw is not None:
                parsed = pd.to_datetime(raw, errors="coerce", utc=True)
                if pd.notna(parsed):
                    days = int((parsed.to_pydatetime() - now).days)
                    return parsed.date().isoformat(), days, ""
    except Exception as exc:
        warnings.append(f"calendar no disponible: {exc}")

    return None, None, "; ".join(warnings)


def fetch_ticker_metadata(ticker: str, config: dict) -> dict:
    """Enrich a ticker with identity, quote context and tactical fundamentals."""
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
            "cache_schema_version": CACHE_SCHEMA_VERSION,
        }

    data = {
        "ticker": ticker,
        "metadata_source": "yfinance",
        "cache_schema_version": CACHE_SCHEMA_VERSION,
    }
    warnings: list[str] = []

    try:
        ticker_obj = yf.Ticker(ticker)
        info: dict = {}
        try:
            info = ticker_obj.get_info() or {}
        except Exception as exc:
            warnings.append(f"get_info falló: {exc}")
            try:
                info = ticker_obj.info or {}
            except Exception as fallback_exc:
                warnings.append(f"info falló: {fallback_exc}")
                info = {}

        data.update(_extract_quote_context(info))
        data.update(
            {
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
            }
        )
        data.update(
            {
                "average_volume": _safe_number(info.get("averageVolume")),
                "average_volume_10d": _safe_number(info.get("averageVolume10days")),
                "bid": _safe_number(info.get("bid")),
                "ask": _safe_number(info.get("ask")),
                "bid_size": _safe_number(info.get("bidSize")),
                "ask_size": _safe_number(info.get("askSize")),
                "regular_market_volume": _safe_number(info.get("regularMarketVolume") or info.get("volume")),
            }
        )

        bid = data.get("bid")
        ask = data.get("ask")
        if isinstance(bid, (int, float)) and isinstance(ask, (int, float)) and bid > 0 and ask > 0 and ask >= bid:
            midpoint = (bid + ask) / 2
            data["spread_pct"] = (ask - bid) / midpoint if midpoint else None
        else:
            data["spread_pct"] = None

        data.update(
            {
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
            }
        )
        data.update(
            {
                "revenue_growth": _safe_number(info.get("revenueGrowth")),
                "earnings_growth": _safe_number(info.get("earningsGrowth")),
                "earnings_quarterly_growth": _safe_number(info.get("earningsQuarterlyGrowth")),
                "eps_trailing_twelve_months": _safe_number(info.get("trailingEps")),
                "eps_forward": _safe_number(info.get("forwardEps")),
                "peg_ratio": _safe_number(info.get("pegRatio")),
            }
        )
        data.update(
            {
                "held_percent_institutions": _safe_number(info.get("heldPercentInstitutions")),
                "held_percent_insiders": _safe_number(info.get("heldPercentInsiders")),
                "short_percent_float": _safe_number(info.get("shortPercentOfFloat")),
                "short_ratio": _safe_number(info.get("shortRatio")),
            }
        )

        earnings_date, days_to_earnings, earnings_warning = _extract_earnings_date(ticker_obj)
        data["earnings_date"] = earnings_date
        data["days_to_earnings"] = days_to_earnings
        if earnings_warning:
            warnings.append(earnings_warning)
    except Exception as exc:
        warnings.append(f"metadata general falló: {exc}")

    data["fundamental_warning"] = "; ".join(warning for warning in warnings if warning)
    _save_cache(ticker, data)
    return data


def enrich_metadata(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Fill missing metadata and tactical fundamental columns."""
    if df.empty:
        return df

    enabled = config.get("fundamentals", {}).get("metadata_enrichment", {}).get("enabled", True)
    if not enabled:
        return df

    max_tickers = config.get("fundamentals", {}).get("metadata_enrichment", {}).get("max_tickers", 300)
    out = df.copy()
    tickers = out["ticker"].dropna().astype(str).str.upper().unique().tolist()[:max_tickers]

    rows: list[dict] = []
    for ticker in tickers:
        try:
            rows.append(fetch_ticker_metadata(ticker, config))
        except Exception as exc:
            logger.warning(f"Metadata falló para {ticker}: {exc}")
            rows.append({"ticker": ticker, "fundamental_warning": str(exc), "metadata_source": "error"})

    metadata = pd.DataFrame(rows)
    if metadata.empty:
        return out

    merged = out.merge(metadata, on="ticker", how="left", suffixes=("", "_enriched"))
    coalesce_columns = [
        "company",
        "exchange",
        "quote_type",
        "sector",
        "industry",
        "market_cap",
        "price",
        "spread_pct",
        "bid",
        "ask",
        "quote_timestamp",
        "regular_market_time",
        "pre_market_time",
        "post_market_time",
        "market_session",
        "market_state_raw",
        "metadata_fetched_at",
        "quote_timestamp_source",
    ]
    for column in coalesce_columns:
        enriched_column = f"{column}_enriched"
        if enriched_column in merged.columns:
            if column not in merged.columns:
                merged[column] = merged[enriched_column]
            else:
                has_original = merged[column].notna() & (merged[column].astype(str) != "")
                merged[column] = merged[column].where(has_original, merged[enriched_column])
            merged = merged.drop(columns=[enriched_column])

    return merged
