\
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import math
from typing import Any

import pandas as pd
from loguru import logger

from engine.data_sources.metadata_fallback import apply_metadata_fallback, build_metadata_providers

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


def _cache_path(ticker: str) -> Path:
    return Path("cache/fundamentals") / f"{ticker}.json"


def _load_cache(ticker: str) -> tuple[dict | None, float | None]:
    path = _cache_path(ticker)
    if not path.exists():
        return None, None
    try:
        age_minutes = (datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) / 60
        with path.open("r", encoding="utf-8") as f:
            return json.load(f), max(age_minutes, 0.0)
    except Exception:
        return None, None


def _save_cache(ticker: str, data: dict) -> None:
    path = Path("cache/fundamentals")
    path.mkdir(parents=True, exist_ok=True)
    with (path / f"{ticker}.json").open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _timestamp_age_minutes(value: Any, fallback_age: float | None) -> float | None:
    if value:
        try:
            timestamp = pd.to_datetime(value, errors="raise", utc=True)
            return max((datetime.now(timezone.utc) - timestamp.to_pydatetime()).total_seconds() / 60, 0.0)
        except Exception:
            pass
    return fallback_age


def _set_cache_trace(
    data: dict,
    *,
    fundamentals_status: str,
    fundamentals_age: float | None,
    earnings_status: str,
    earnings_age: float | None,
) -> dict:
    data["metadata_cache_hit"] = fundamentals_status == "HIT"
    data["fundamentals_cache_status"] = fundamentals_status
    data["fundamentals_cache_age_minutes"] = round(fundamentals_age, 2) if fundamentals_age is not None else None
    data["earnings_cache_status"] = earnings_status
    data["earnings_cache_age_minutes"] = round(earnings_age, 2) if earnings_age is not None else None
    return data


def _extract_earnings_date(ticker_obj) -> tuple[str | None, int | None, str, bool]:
    """
    Best-effort earnings extraction.
    Uses upcoming earnings_dates first; calendar as fallback.
    """
    now = datetime.now(timezone.utc)
    warnings = []
    query_succeeded = False

    # 1) earnings_dates
    try:
        ed = ticker_obj.get_earnings_dates(limit=8)
        query_succeeded = True
        if ed is not None and not ed.empty:
            idx = pd.to_datetime(ed.index, errors="coerce", utc=True)
            future = idx[idx >= now]
            if len(future) > 0:
                next_dt = future.min()
                days = int((next_dt.to_pydatetime() - now).days)
                return next_dt.date().isoformat(), days, "", True
    except Exception as exc:
        warnings.append(f"earnings_dates no disponible: {exc}")

    # 2) calendar
    try:
        cal = ticker_obj.calendar
        query_succeeded = True
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
                    return dt.date().isoformat(), days, "", True
    except Exception as exc:
        warnings.append(f"calendar no disponible: {exc}")

    return None, None, "; ".join(warnings), query_succeeded


def _metadata_from_info(ticker: str, info: dict) -> dict:
    data = {"ticker": ticker, "metadata_source": "yfinance", "quote_source": "yfinance"}
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
        "average_volume": _safe_number(info.get("averageVolume")),
        "average_volume_10d": _safe_number(info.get("averageVolume10days")),
        "bid": _safe_number(info.get("bid")),
        "ask": _safe_number(info.get("ask")),
        "bid_size": _safe_number(info.get("bidSize")),
        "ask_size": _safe_number(info.get("askSize")),
        "regular_market_volume": _safe_number(info.get("regularMarketVolume") or info.get("volume")),
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
        "revenue_growth": _safe_number(info.get("revenueGrowth")),
        "earnings_growth": _safe_number(info.get("earningsGrowth")),
        "earnings_quarterly_growth": _safe_number(info.get("earningsQuarterlyGrowth")),
        "eps_trailing_twelve_months": _safe_number(info.get("trailingEps")),
        "eps_forward": _safe_number(info.get("forwardEps")),
        "peg_ratio": _safe_number(info.get("pegRatio")),
        "held_percent_institutions": _safe_number(info.get("heldPercentInstitutions")),
        "held_percent_insiders": _safe_number(info.get("heldPercentInsiders")),
        "short_percent_float": _safe_number(info.get("shortPercentOfFloat")),
        "short_ratio": _safe_number(info.get("shortRatio")),
    })
    bid = data.get("bid")
    ask = data.get("ask")
    if isinstance(bid, (int, float)) and isinstance(ask, (int, float)) and bid > 0 and ask > 0 and ask >= bid:
        mid = (bid + ask) / 2
        data["spread_pct"] = (ask - bid) / mid if mid else None
    else:
        data["spread_pct"] = None
    return data


def fetch_ticker_metadata(ticker: str, config: dict, fallback_providers=None) -> dict:
    """
    Enrich ticker with metadata and tactical fundamentals from yfinance.
    It is intentionally best-effort; missing fields are returned as None.
    """
    fundamentals_ttl = (
        config.get("data_sources", {})
        .get("cache_ttl_minutes", {})
        .get("fundamentals", 10080)
    )
    earnings_ttl = (
        config.get("data_sources", {})
        .get("cache_ttl_minutes", {})
        .get("earnings", 720)
    )
    metadata_cfg = config.get("fundamentals", {}).get("metadata_enrichment", {})
    prefer_stale_cache = bool(metadata_cfg.get("prefer_stale_cache", False))
    network_enabled = bool(metadata_cfg.get("network_enabled", True))

    cached, file_age = _load_cache(ticker)
    fundamentals_age = _timestamp_age_minutes(
        cached.get("_fundamentals_fetched_at") if cached else None,
        file_age,
    )
    earnings_age = _timestamp_age_minutes(
        cached.get("_earnings_fetched_at") if cached else None,
        file_age,
    )
    if cached is not None:
        cached = dict(cached)
        now = datetime.now(timezone.utc)
        if not cached.get("_fundamentals_fetched_at") and fundamentals_age is not None:
            cached["_fundamentals_fetched_at"] = (
                now - timedelta(minutes=fundamentals_age)
            ).isoformat()
        if not cached.get("_earnings_fetched_at") and earnings_age is not None:
            cached["_earnings_fetched_at"] = (
                now - timedelta(minutes=earnings_age)
            ).isoformat()
    fundamentals_fresh = cached is not None and fundamentals_age is not None and fundamentals_age <= fundamentals_ttl
    earnings_fresh = cached is not None and earnings_age is not None and earnings_age <= earnings_ttl
    if fundamentals_fresh and earnings_fresh:
        result = _set_cache_trace(
            dict(cached),
            fundamentals_status="HIT",
            fundamentals_age=fundamentals_age,
            earnings_status="HIT",
            earnings_age=earnings_age,
        )
        return apply_metadata_fallback(result, config, fallback_providers)

    if cached is not None and prefer_stale_cache:
        result = _set_cache_trace(
            dict(cached),
            fundamentals_status="HIT" if fundamentals_fresh else "STALE_FALLBACK",
            fundamentals_age=fundamentals_age,
            earnings_status="HIT" if earnings_fresh else "STALE_FALLBACK",
            earnings_age=earnings_age,
        )
        result["fundamental_warning"] = "; ".join(
            value
            for value in [
                result.get("fundamental_warning"),
                "cache stale usado sin refresco de red para evitar bloqueo del scanner",
            ]
            if value
        )
        return apply_metadata_fallback(result, config, fallback_providers)

    if yf is None:
        if cached is not None:
            result = _set_cache_trace(
                dict(cached),
                fundamentals_status="STALE_FALLBACK",
                fundamentals_age=fundamentals_age,
                earnings_status="STALE_FALLBACK",
                earnings_age=earnings_age,
            )
            result["fundamental_warning"] = "yfinance no disponible; usando cache stale"
            return apply_metadata_fallback(result, config, fallback_providers)
        return apply_metadata_fallback({
            "ticker": ticker,
            "metadata_source": "none",
            "fundamental_warning": "yfinance no disponible",
            "fundamentals_cache_status": "NETWORK_MISSING",
            "earnings_cache_status": "NETWORK_MISSING",
        }, config, fallback_providers)

    if not network_enabled:
        if cached is not None:
            result = _set_cache_trace(
                dict(cached),
                fundamentals_status="STALE_FALLBACK",
                fundamentals_age=fundamentals_age,
                earnings_status="STALE_FALLBACK",
                earnings_age=earnings_age,
            )
            result["fundamental_warning"] = "network metadata disabled; usando cache stale"
            return apply_metadata_fallback(result, config, fallback_providers)
        return apply_metadata_fallback(
            {
                "ticker": ticker,
                "metadata_source": "none",
                "fundamental_warning": "network metadata disabled; sin cache local",
                "fundamentals_cache_status": "NETWORK_SKIPPED",
                "earnings_cache_status": "NETWORK_SKIPPED",
            },
            config,
            fallback_providers,
        )

    warnings = []
    now_iso = datetime.now(timezone.utc).isoformat()
    tk = yf.Ticker(ticker)

    if fundamentals_fresh and cached is not None:
        data = dict(cached)
        earnings_date, days_to_earnings, warning, query_succeeded = _extract_earnings_date(tk)
        if warning:
            warnings.append(warning)
        if query_succeeded:
            data["earnings_date"] = earnings_date
            data["days_to_earnings"] = days_to_earnings
            data["_earnings_fetched_at"] = now_iso
            earnings_status = "REFRESHED"
            earnings_age = 0.0
            _save_cache(ticker, data)
        else:
            earnings_status = "STALE_FALLBACK"
        data["fundamental_warning"] = "; ".join(
            value for value in [data.get("fundamental_warning"), *warnings] if value
        )
        result = _set_cache_trace(
            data,
            fundamentals_status="HIT",
            fundamentals_age=fundamentals_age,
            earnings_status=earnings_status,
            earnings_age=earnings_age,
        )
        return apply_metadata_fallback(result, config, fallback_providers)

    info: dict = {}
    info_succeeded = False
    try:
        try:
            info = tk.get_info() or {}
            info_succeeded = bool(info)
        except Exception as exc:
            warnings.append(f"get_info falló: {exc}")
            try:
                info = tk.info or {}
                info_succeeded = bool(info)
            except Exception as exc2:
                warnings.append(f"info falló: {exc2}")
                info = {}
    except Exception as exc:
        warnings.append(f"metadata general falló: {exc}")

    if info_succeeded:
        data = _metadata_from_info(ticker, info)
        data["_fundamentals_fetched_at"] = now_iso
        fundamentals_status = "FRESH_NETWORK"
        fundamentals_age = 0.0
    elif cached is not None:
        data = dict(cached)
        fundamentals_status = "STALE_FALLBACK"
    else:
        data = {"ticker": ticker, "metadata_source": "yfinance", "quote_source": "yfinance"}
        fundamentals_status = "NETWORK_MISSING"

    earnings_date, days_to_earnings, earnings_warning, earnings_succeeded = _extract_earnings_date(tk)
    if earnings_warning:
        warnings.append(earnings_warning)
    if earnings_succeeded:
        data["earnings_date"] = earnings_date
        data["days_to_earnings"] = days_to_earnings
        data["_earnings_fetched_at"] = now_iso
        earnings_status = "FRESH_NETWORK"
        earnings_age = 0.0
    elif cached is not None:
        data["earnings_date"] = cached.get("earnings_date")
        data["days_to_earnings"] = cached.get("days_to_earnings")
        earnings_status = "STALE_FALLBACK"
    else:
        earnings_status = "NETWORK_MISSING"

    data["fundamental_warning"] = "; ".join([w for w in warnings if w])
    if info_succeeded or earnings_succeeded:
        _save_cache(ticker, data)
    data = _set_cache_trace(
        data,
        fundamentals_status=fundamentals_status,
        fundamentals_age=fundamentals_age,
        earnings_status=earnings_status,
        earnings_age=earnings_age,
    )
    data = apply_metadata_fallback(data, config, fallback_providers)
    return data


def enrich_metadata(
    df: pd.DataFrame,
    config: dict,
    stats: dict | None = None,
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    """
    Fill missing sector/industry/company/earnings/fundamental columns.
    Limit can be configured to avoid making the scanner too slow.
    """
    if df.empty:
        return df

    metadata_cfg = config.get("fundamentals", {}).get("metadata_enrichment", {})
    enabled = metadata_cfg.get("enabled", True)
    if not enabled:
        return df

    max_tickers = metadata_cfg.get("max_tickers", 0)
    max_network_queries = int(metadata_cfg.get("max_network_queries_per_run", 0) or 0)
    out = df.copy()
    tickers = out["ticker"].dropna().astype(str).str.upper().unique().tolist()
    if max_tickers is not None and int(max_tickers or 0) > 0:
        tickers = tickers[: int(max_tickers)]

    rows = []
    fallback_providers = build_metadata_providers(config)
    telemetry = stats if stats is not None else {}
    telemetry.update(
        {
            "requested_tickers": len(tickers),
            "fundamentals_cache_hits": 0,
            "fundamentals_network_queries": 0,
            "fundamentals_stale_fallbacks": 0,
            "earnings_cache_hits": 0,
            "earnings_network_queries": 0,
            "earnings_stale_fallbacks": 0,
            "network_query_limit": max_network_queries,
            "network_queries_skipped_by_limit": 0,
            "processed_tickers": 0,
            "errors": [],
        }
    )
    for i, ticker in enumerate(tickers, start=1):
        try:
            record_config = config
            used_network_queries = int(telemetry["fundamentals_network_queries"]) + int(
                telemetry["earnings_network_queries"]
            )
            if max_network_queries > 0 and used_network_queries >= max_network_queries:
                record_config = {
                    **config,
                    "fundamentals": {
                        **config.get("fundamentals", {}),
                        "metadata_enrichment": {
                            **metadata_cfg,
                            "network_enabled": False,
                        },
                    },
                }
                telemetry["network_queries_skipped_by_limit"] += 1
            record = fetch_ticker_metadata(ticker, record_config, fallback_providers)
            rows.append(record)
            fundamental_status = str(record.get("fundamentals_cache_status") or "")
            earnings_status = str(record.get("earnings_cache_status") or "")
            telemetry["fundamentals_cache_hits"] += int(fundamental_status == "HIT")
            telemetry["fundamentals_network_queries"] += int(fundamental_status == "FRESH_NETWORK")
            telemetry["fundamentals_stale_fallbacks"] += int(fundamental_status == "STALE_FALLBACK")
            telemetry["earnings_cache_hits"] += int(earnings_status == "HIT")
            telemetry["earnings_network_queries"] += int(earnings_status in {"FRESH_NETWORK", "REFRESHED"})
            telemetry["earnings_stale_fallbacks"] += int(earnings_status == "STALE_FALLBACK")
        except Exception as exc:
            logger.warning(f"Metadata falló para {ticker}: {exc}")
            telemetry["errors"].append(f"{ticker}:{type(exc).__name__}:{exc}")
            rows.append(
                apply_metadata_fallback(
                    {"ticker": ticker, "fundamental_warning": str(exc), "metadata_source": "error"},
                    config,
                    fallback_providers,
                )
            )
        finally:
            telemetry["processed_tickers"] = i
            if progress_callback is not None and (i == len(tickers) or i % 25 == 0):
                try:
                    progress_callback(dict(telemetry))
                except Exception:
                    pass

    meta = pd.DataFrame(rows)
    if meta.empty:
        return out

    # Merge with suffix, then coalesce original columns with enriched columns.
    merged = out.merge(meta, on="ticker", how="left", suffixes=("", "_enriched"))
    for col in [
        "company",
        "exchange",
        "quote_type",
        "sector",
        "industry",
        "market_cap",
        "price",
        "spread_pct",
        "earnings_date",
        "next_earnings_date",
        "quote_source",
        "metadata_source",
        "sector_source",
        "industry_source",
        "market_cap_source",
        "earnings_source",
        "metadata_fallback_used",
        "metadata_fallback_sources",
        "metadata_fallback_notes",
        "metadata_confidence",
        "fundamentals_cache_status",
        "fundamentals_cache_age_minutes",
        "earnings_cache_status",
        "earnings_cache_age_minutes",
    ]:
        enriched_col = f"{col}_enriched"
        if enriched_col in merged.columns:
            if col not in merged.columns:
                merged[col] = merged[enriched_col]
            else:
                merged[col] = merged[col].where(merged[col].notna() & (merged[col].astype(str) != ""), merged[enriched_col])
            merged = merged.drop(columns=[enriched_col])

    return merged
