from __future__ import annotations

import csv
import copy
import io
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable

from engine.data_sources.provider_contract import PROVIDER_CONFIDENCE_VALUES

GOOGLE_SHEETS_MANUAL = "GOOGLE_SHEETS_MANUAL"
GOOGLE_SHEETS_SOURCE = "GOOGLE_SHEETS_MANUAL_CSV"
REQUIRED_COLUMNS = {"ticker", "source", "updated_at", "confidence"}
OPTIONAL_COLUMNS = {
    "price",
    "bid",
    "ask",
    "spread_pct",
    "sector",
    "industry",
    "market_cap",
    "earnings_date",
    "next_earnings_date",
    "put_call_ratio",
    "options_volume",
    "options_open_interest",
    "iv",
    "delta",
    "gamma",
    "notes",
}

RequestFn = Callable[[str, int], tuple[int, str]]
_RECORD_CACHE: dict[tuple[str, int, int, int], dict[str, Any]] = {}


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "null"} else text


def _safe_float(value: Any) -> float | None:
    try:
        text = _safe_text(value)
        return float(text.replace(",", "")) if text else None
    except Exception:
        return None


def _parse_timestamp(value: Any) -> datetime | None:
    text = _safe_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def urllib_request_text(url: str, timeout_seconds: int) -> tuple[int, str]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Analista-google-sheets-manual/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return int(response.status), response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace")


def clear_google_sheets_cache() -> None:
    _RECORD_CACHE.clear()


def _csv_rows_and_header(text: str) -> tuple[list[str], list[list[str]], int, bool]:
    rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
    nonempty = [
        (index, row)
        for index, row in enumerate(rows)
        if any(_safe_text(value) for value in row)
    ]
    if not nonempty:
        return [], [], 0, False

    header_index = nonempty[0][0]
    header_detected = False
    for index, row in nonempty:
        normalized = {_safe_text(value).lower() for value in row}
        if REQUIRED_COLUMNS.issubset(normalized):
            header_index = index
            header_detected = True
            break
        if "ticker" in normalized:
            header_index = index
            break

    columns = [_safe_text(value) for value in rows[header_index]]
    data_rows = rows[header_index + 1 :]
    return columns, data_rows, header_index, header_detected


def parse_google_sheets_csv(
    text: str,
    *,
    max_stale_minutes: int = 1440,
    now: datetime | None = None,
) -> dict[str, Any]:
    column_list, data_rows, header_index, header_detected = _csv_rows_and_header(text)
    raw_rows: list[dict[str, Any]] = []
    for values in data_rows:
        if not any(_safe_text(value) for value in values):
            continue
        padded = values + [""] * max(len(column_list) - len(values), 0)
        raw_rows.append(dict(zip(column_list, padded[: len(column_list)])))

    columns = set(column_list)
    missing_columns = sorted(REQUIRED_COLUMNS - columns)
    optional_columns_present = sorted(OPTIONAL_COLUMNS & columns)
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    records: dict[str, dict[str, Any]] = {}
    normalized_rows: list[dict[str, Any]] = []
    stale_rows = 0
    invalid_timestamp_rows = 0
    invalid_ticker_rows = 0
    duplicate_tickers: list[str] = []

    for raw in raw_rows:
        ticker = _safe_text(raw.get("ticker")).upper()
        updated_at = _parse_timestamp(raw.get("updated_at"))
        age_minutes = None
        if updated_at is None:
            invalid_timestamp_rows += 1
        else:
            age_minutes = max((now - updated_at).total_seconds() / 60.0, 0.0)
        stale = age_minutes is not None and age_minutes > float(max_stale_minutes)
        if stale:
            stale_rows += 1
        if not ticker:
            invalid_ticker_rows += 1

        confidence = _safe_text(raw.get("confidence")).upper() or "UNKNOWN"
        if confidence not in PROVIDER_CONFIDENCE_VALUES:
            confidence = "UNKNOWN"

        available_fields = [
            column for column in optional_columns_present if _safe_text(raw.get(column))
        ]
        usable = bool(ticker and not missing_columns and updated_at is not None and not stale)
        normalized = {
            "ticker": ticker,
            "source": _safe_text(raw.get("source")) or GOOGLE_SHEETS_SOURCE,
            "updated_at": updated_at.isoformat() if updated_at else _safe_text(raw.get("updated_at")),
            "age_minutes": round(age_minutes, 2) if age_minutes is not None else None,
            "confidence": confidence,
            "data_freshness": "DELAYED_20_MIN",
            "available_fields": sorted(available_fields),
            "stale": stale,
            "usable": usable,
            "notes": _safe_text(raw.get("notes")),
        }
        normalized_rows.append(normalized)
        if not usable:
            continue

        if ticker in records:
            duplicate_tickers.append(ticker)
            prior_age = records[ticker].get("age_minutes")
            if prior_age is not None and age_minutes is not None and prior_age <= age_minutes:
                continue

        record = dict(normalized)
        for field in OPTIONAL_COLUMNS:
            value: Any = raw.get(field)
            if field in {
                "price",
                "bid",
                "ask",
                "spread_pct",
                "market_cap",
                "put_call_ratio",
                "options_volume",
                "options_open_interest",
                "iv",
                "delta",
                "gamma",
            }:
                value = _safe_float(value)
            else:
                value = _safe_text(value)
            if value is not None and value != "":
                record[field] = value
        records[ticker] = record

    issues: list[str] = []
    if missing_columns:
        issues.append("schema_missing_columns")
    if stale_rows:
        issues.append("stale_rows")
    if invalid_timestamp_rows:
        issues.append("invalid_updated_at")
    if invalid_ticker_rows:
        issues.append("invalid_ticker")
    if duplicate_tickers:
        issues.append("duplicate_tickers")
    if not raw_rows:
        issues.append("empty_csv")

    return {
        "status": "WARN" if issues else "PASS",
        "rows": len(raw_rows),
        "valid_rows": len(records),
        "header_row": header_index + 1 if column_list else None,
        "ignored_preamble_rows": header_index if column_list else 0,
        "header_detected": header_detected,
        "detected_schema": column_list,
        "stale_rows": stale_rows,
        "invalid_timestamp_rows": invalid_timestamp_rows,
        "invalid_ticker_rows": invalid_ticker_rows,
        "duplicate_tickers": sorted(set(duplicate_tickers)),
        "columns": sorted(columns),
        "missing_columns": missing_columns,
        "optional_columns_present": optional_columns_present,
        "sample_rows": normalized_rows[:10],
        "records": records,
        "issues": issues,
    }


def load_google_sheets_records(
    csv_url: str,
    *,
    timeout_seconds: int = 20,
    max_stale_minutes: int = 1440,
    request_fn: RequestFn = urllib_request_text,
    use_cache: bool = True,
) -> dict[str, Any]:
    csv_url = _safe_text(csv_url)
    if not csv_url:
        return {
            "status": "WARN",
            "records": {},
            "issues": ["missing_google_sheets_csv_url"],
            "http_status": None,
        }
    cache_key = (csv_url, int(timeout_seconds), int(max_stale_minutes), id(request_fn))
    if use_cache and cache_key in _RECORD_CACHE:
        cached = copy.deepcopy(_RECORD_CACHE[cache_key])
        cached["cache_hit"] = True
        return cached
    try:
        http_status, text = request_fn(csv_url, timeout_seconds)
    except Exception as exc:
        return {
            "status": "WARN",
            "records": {},
            "issues": [f"google_sheets_request_exception:{type(exc).__name__}"],
            "http_status": None,
        }
    if not 200 <= int(http_status) < 300:
        return {
            "status": "WARN",
            "records": {},
            "issues": ["google_sheets_csv_unavailable"],
            "http_status": int(http_status),
        }
    parsed = parse_google_sheets_csv(text, max_stale_minutes=max_stale_minutes)
    parsed["http_status"] = int(http_status)
    parsed["cache_hit"] = False
    if use_cache:
        _RECORD_CACHE[cache_key] = copy.deepcopy(parsed)
    return parsed


def record_to_analysis_quote(record: dict[str, Any]) -> dict[str, Any] | None:
    price = _safe_float(record.get("price"))
    bid = _safe_float(record.get("bid"))
    ask = _safe_float(record.get("ask"))
    if price is None and bid is not None and ask is not None and ask >= bid:
        price = (bid + ask) / 2
    if price is None and bid is None and ask is None:
        return None

    spread_pct = _safe_float(record.get("spread_pct"))
    if spread_pct is None and bid is not None and ask is not None and ask >= bid:
        denominator = price if price and price > 0 else (bid + ask) / 2
        spread_pct = (ask - bid) / denominator if denominator else None

    return {
        "ticker": _safe_text(record.get("ticker")).upper(),
        "status": "PASS" if price is not None else "WARN",
        "analysis_price": price,
        "analysis_bid": bid,
        "analysis_ask": ask,
        "analysis_spread_pct": spread_pct,
        "analysis_quote_source": GOOGLE_SHEETS_SOURCE,
        "analysis_quote_timestamp": _safe_text(record.get("updated_at")),
        "analysis_quote_freshness": "DELAYED_20_MIN",
        "analysis_quote_confidence": _safe_text(record.get("confidence")).upper() or "LOW",
    }
