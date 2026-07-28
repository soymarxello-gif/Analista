from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable

from engine.data_sources.provider_contract import ProviderResponse
from engine.data_sources.google_sheets_manual import (
    load_google_sheets_records,
    record_to_analysis_quote,
)

DEFAULT_ALPACA_DATA_BASE_URL = "https://data.alpaca.markets"
ALPACA_IEX_SOURCE = "ALPACA_IEX_READ_ONLY"

RequestFn = Callable[[str, dict[str, str], int], tuple[int, dict[str, Any]]]


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "null"} else text


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _env_first(names: list[str]) -> str:
    for name in names:
        value = _safe_text(os.environ.get(name))
        if value:
            return value
    return ""


def load_alpaca_credentials() -> dict[str, str]:
    return {
        "key": _env_first(["APCA_API_KEY_ID", "ALPACA_API_KEY_ID"]),
        "secret": _env_first(["APCA_API_SECRET_KEY", "ALPACA_API_SECRET_KEY"]),
    }


def alpaca_credentials_present() -> bool:
    credentials = load_alpaca_credentials()
    return bool(credentials["key"] and credentials["secret"])


def urllib_request_json(url: str, headers: dict[str, str], timeout_seconds: int) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read().decode("utf-8", errors="replace")
            return int(response.status), json.loads(payload or "{}")
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(payload or "{}")
        except Exception:
            data = {"message": payload[:500]}
        return int(exc.code), data


def _headers(credentials: dict[str, str]) -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": credentials.get("key", ""),
        "APCA-API-SECRET-KEY": credentials.get("secret", ""),
        "Accept": "application/json",
        "User-Agent": "Analista-analysis-quotes-readonly/1.0",
    }


def _normalize_tickers(tickers: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for ticker in tickers:
        text = _safe_text(ticker).upper()
        if not text or text in seen:
            continue
        out.append(text)
        seen.add(text)
    return out


def _chunks(items: list[str], chunk_size: int) -> list[list[str]]:
    size = max(int(chunk_size or 0), 1)
    return [items[index : index + size] for index in range(0, len(items), size)]


def _extract_payload_map(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key, {}) if isinstance(data, dict) else {}
    return value if isinstance(value, dict) else {}


def _timestamp(*values: Any) -> str:
    for value in values:
        text = _safe_text(value)
        if text:
            return text
    return datetime.now(timezone.utc).isoformat()


def _spread_pct(bid: float | None, ask: float | None, price: float | None) -> float | None:
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        return None
    denominator = price if price and price > 0 else (bid + ask) / 2
    if not denominator:
        return None
    return round(float((ask - bid) / denominator), 6)


def _build_quote(ticker: str, quote: dict[str, Any], trade: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    bid = _safe_float(quote.get("bp") or quote.get("bid_price") or quote.get("bid"))
    ask = _safe_float(quote.get("ap") or quote.get("ask_price") or quote.get("ask"))
    trade_price = _safe_float(trade.get("p") or trade.get("price"))
    midpoint = (bid + ask) / 2 if bid is not None and ask is not None and ask >= bid else None
    price = trade_price if trade_price is not None else midpoint
    confidence = "MEDIUM" if price is not None else "LOW"
    status = "PASS" if price is not None else "WARN"

    provider = ProviderResponse(
        provider_name="alpaca_iex",
        status=status,
        source=ALPACA_IEX_SOURCE,
        timestamp=_timestamp(trade.get("t") or trade.get("timestamp"), quote.get("t") or quote.get("timestamp")),
        data_freshness="DELAYED_15_MIN",
        confidence=confidence,
        fields={
            "analysis_price": price,
            "analysis_bid": bid,
            "analysis_ask": ask,
            "analysis_spread_pct": _spread_pct(bid, ask, price),
        },
        errors=errors,
        notes=["read-only delayed analysis quote; execution fields are not changed"],
    ).to_dict()

    return {
        "ticker": ticker,
        "status": provider["status"],
        "analysis_price": price,
        "analysis_bid": bid,
        "analysis_ask": ask,
        "analysis_spread_pct": provider["fields"]["analysis_spread_pct"],
        "analysis_quote_source": provider["source"],
        "analysis_quote_timestamp": provider["timestamp"],
        "analysis_quote_freshness": provider["data_freshness"],
        "analysis_quote_confidence": provider["confidence"],
        "provider": provider,
    }


def fetch_alpaca_iex_analysis_quotes(
    tickers: list[str],
    *,
    data_base_url: str = DEFAULT_ALPACA_DATA_BASE_URL,
    timeout_seconds: int = 15,
    batch_size: int = 100,
    request_fn: RequestFn = urllib_request_json,
    credentials: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    tickers = _normalize_tickers(tickers)
    if not tickers:
        return {}

    credentials = credentials or load_alpaca_credentials()
    if not (credentials.get("key") and credentials.get("secret")):
        return {}

    base = data_base_url.rstrip("/")
    headers = _headers(credentials)

    out: dict[str, dict[str, Any]] = {}
    for group in _chunks(tickers, batch_size):
        symbols = urllib.parse.quote(",".join(group), safe=",")
        endpoints = {
            "quotes": f"{base}/v2/stocks/quotes/latest?symbols={symbols}&feed=iex",
            "trades": f"{base}/v2/stocks/trades/latest?symbols={symbols}&feed=iex",
        }

        payloads: dict[str, dict[str, Any]] = {}
        errors: list[str] = []
        for name, url in endpoints.items():
            try:
                http_status, data = request_fn(url, headers, timeout_seconds)
                if 200 <= int(http_status) < 300:
                    payloads[name] = data
                else:
                    errors.append(f"alpaca_{name}_http_{int(http_status)}")
                    payloads[name] = {}
            except Exception as exc:
                errors.append(f"alpaca_{name}_exception:{type(exc).__name__}")
                payloads[name] = {}

        quote_map = _extract_payload_map(payloads.get("quotes", {}), "quotes")
        trade_map = _extract_payload_map(payloads.get("trades", {}), "trades")

        for ticker in group:
            quote = quote_map.get(ticker) or quote_map.get(ticker.upper()) or {}
            trade = trade_map.get(ticker) or trade_map.get(ticker.upper()) or {}
            if not quote and not trade and errors:
                continue
            out[ticker] = _build_quote(ticker, quote, trade, errors)
    return out


def row_needs_analysis_quote_fallback(row: dict[str, Any]) -> bool:
    quote_status = _safe_text(row.get("quote_status")).upper()
    quote_quality = _safe_text(row.get("execution_quote_quality")).upper()
    if quote_status == "VALID" and quote_quality == "HIGH":
        return False
    return (
        quote_status in {"MISSING", "INVALID", "STALE_POSSIBLE", "WIDE_OR_INCOHERENT"}
        or quote_quality == "LOW"
        or row.get("analysis_price") is None
        or row.get("analysis_bid") is None
        or row.get("analysis_ask") is None
    )


def select_analysis_quote_fallback_tickers(rows: list[dict[str, Any]]) -> list[str]:
    tickers: list[str] = []
    seen: set[str] = set()
    for row in rows:
        ticker = _safe_text(row.get("ticker")).upper()
        if not ticker or ticker in seen or not row_needs_analysis_quote_fallback(row):
            continue
        tickers.append(ticker)
        seen.add(ticker)
    return tickers


def apply_analysis_quote_fallback(row: dict[str, Any], quote: dict[str, Any] | None) -> dict[str, Any]:
    if not quote or not row_needs_analysis_quote_fallback(row):
        return row

    updated = dict(row)
    for target, source in [
        ("analysis_price", "analysis_price"),
        ("analysis_bid", "analysis_bid"),
        ("analysis_ask", "analysis_ask"),
        ("analysis_spread_pct", "analysis_spread_pct"),
        ("analysis_quote_source", "analysis_quote_source"),
        ("analysis_quote_timestamp", "analysis_quote_timestamp"),
        ("analysis_quote_freshness", "analysis_quote_freshness"),
        ("analysis_quote_confidence", "analysis_quote_confidence"),
    ]:
        value = quote.get(source)
        if value is not None and _safe_text(value) != "":
            updated[target] = value

    existing_sources = _safe_text(updated.get("secondary_data_sources_used"))
    source = _safe_text(quote.get("analysis_quote_source"))
    if source and source not in existing_sources.split(","):
        updated["secondary_data_sources_used"] = (
            f"{existing_sources},{source}".strip(",") if existing_sources else source
        )

    note = "analysis quote filled from delayed read-only provider; execution fields unchanged"
    existing_notes = _safe_text(updated.get("secondary_data_notes"))
    updated["secondary_data_notes"] = f"{existing_notes}; {note}" if existing_notes else note
    return updated


def build_analysis_quote_fallbacks(
    tickers: list[str],
    config: dict,
    *,
    request_fn: RequestFn = urllib_request_json,
) -> dict[str, dict[str, Any]]:
    data_sources = config.get("data_sources", {}) or {}
    analysis_cfg = data_sources.get("analysis_quotes", {}) or {}
    providers_cfg = data_sources.get("providers", {}) or {}
    alpaca_cfg = providers_cfg.get("alpaca_iex", {}) or {}

    if not analysis_cfg.get("enabled", True):
        return {}
    max_tickers = int(analysis_cfg.get("max_tickers_per_run", 500) or 500)
    alpaca_batch_size = int(analysis_cfg.get("alpaca_batch_size", 100) or 100)
    all_tickers = _normalize_tickers(tickers)
    alpaca_tickers = all_tickers[:max_tickers]
    out: dict[str, dict[str, Any]] = {}

    if (
        alpaca_cfg.get("enabled", True)
        and analysis_cfg.get("use_alpaca_iex", True)
        and alpaca_credentials_present()
    ):
        out.update(
            fetch_alpaca_iex_analysis_quotes(
                alpaca_tickers,
                data_base_url=str(alpaca_cfg.get("data_base_url") or DEFAULT_ALPACA_DATA_BASE_URL),
                timeout_seconds=int(analysis_cfg.get("timeout_seconds", 15) or 15),
                batch_size=alpaca_batch_size,
                request_fn=request_fn,
            )
        )

    sheets_cfg = providers_cfg.get("google_sheets_manual", {}) or {}
    if sheets_cfg.get("enabled", False) and analysis_cfg.get("use_google_sheets_manual", True):
        sheets_result = load_google_sheets_records(
            str(sheets_cfg.get("published_csv_url") or ""),
            timeout_seconds=int(sheets_cfg.get("timeout_seconds", 20) or 20),
            max_stale_minutes=int(sheets_cfg.get("max_stale_minutes", 1440) or 1440),
        )
        records = sheets_result.get("records", {}) if isinstance(sheets_result, dict) else {}
        for ticker in all_tickers:
            if ticker in out:
                continue
            quote = record_to_analysis_quote(records.get(ticker, {}))
            if quote:
                out[ticker] = quote

    return out
