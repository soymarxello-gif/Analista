from __future__ import annotations

import csv
import json
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Callable

import pandas as pd

FRED_CSV_URL = (
    "https://fred.stlouisfed.org/graph/fredgraph.csv"
    "?id={series_id}&cosd={start_date}&coed={end_date}"
)

SERIES_CONFIG: dict[str, dict[str, Any]] = {
    "M2SL": {"name": "M2 money stock", "frequency": "monthly", "max_age_days": 70},
    "RRPONTSYD": {"name": "Overnight reverse repos", "frequency": "daily", "max_age_days": 10},
    "DFF": {"name": "Effective federal funds rate", "frequency": "daily", "max_age_days": 10},
    "DGS10": {"name": "10Y Treasury", "frequency": "daily", "max_age_days": 10},
    "DGS30": {"name": "30Y Treasury", "frequency": "daily", "max_age_days": 10},
    "T10Y2Y": {"name": "10Y-2Y Treasury spread", "frequency": "daily", "max_age_days": 10},
    "T10Y3M": {"name": "10Y-3M Treasury spread", "frequency": "daily", "max_age_days": 10},
    "VIXCLS": {"name": "VIX close", "frequency": "daily", "max_age_days": 10},
    "BAMLH0A0HYM2": {"name": "US high yield spread", "frequency": "daily", "max_age_days": 10},
    "DTWEXBGS": {"name": "Trade weighted dollar index", "frequency": "daily", "max_age_days": 10},
    "DCOILWTICO": {"name": "WTI crude oil", "frequency": "daily", "max_age_days": 10},
    "CPIAUCSL": {"name": "CPI", "frequency": "monthly", "max_age_days": 70},
    "PAYEMS": {"name": "Nonfarm payrolls", "frequency": "monthly", "max_age_days": 70},
    "UNRATE": {"name": "Unemployment rate", "frequency": "monthly", "max_age_days": 70},
    "M2V": {"name": "Velocity of M2", "frequency": "quarterly", "max_age_days": 130},
}

DataReaderFn = Callable[[str, str, date, date], pd.DataFrame]


def _to_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def _to_float(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text or text == ".":
        return None
    try:
        return float(text)
    except Exception:
        return None


def parse_fred_csv_observations(text: str, series_id: str) -> list[dict[str, Any]]:
    if not text:
        return []
    rows = csv.DictReader(StringIO(text))
    observations: list[dict[str, Any]] = []
    for row in rows:
        obs_date = _to_date(row.get("DATE") or row.get("date"))
        value = _to_float(row.get(series_id))
        if obs_date is None or value is None:
            continue
        observations.append({"date": obs_date.isoformat(), "value": value})
    observations.sort(key=lambda item: item["date"])
    return observations


def dataframe_observations(frame: pd.DataFrame, series_id: str) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    if series_id in frame.columns:
        series = frame[series_id]
    else:
        series = frame.iloc[:, 0]
    observations: list[dict[str, Any]] = []
    for idx, value in series.items():
        obs_date = _to_date(idx)
        number = _to_float(value)
        if obs_date is None or number is None:
            continue
        observations.append({"date": obs_date.isoformat(), "value": number})
    observations.sort(key=lambda item: item["date"])
    return observations


def summarize_observations(
    observations: list[dict[str, Any]],
    *,
    series_id: str,
    as_of: date | None = None,
) -> dict[str, Any]:
    today = as_of or datetime.now(timezone.utc).date()
    config = SERIES_CONFIG.get(series_id, {"name": series_id, "frequency": "unknown", "max_age_days": 30})
    if not observations:
        return {
            "series_id": series_id,
            "series_name": config["name"],
            "status": "WARN",
            "issue": "fred_empty_or_invalid_series",
            "latest_value": None,
            "latest_date": "",
            "age_days": None,
            "change_4w": None,
            "stale": True,
        }

    latest = observations[-1]
    latest_date = _to_date(latest.get("date"))
    latest_value = _to_float(latest.get("value"))
    previous = None
    if latest_date is not None:
        cutoff = latest_date - timedelta(days=28)
        older = [obs for obs in observations if (_to_date(obs.get("date")) or latest_date) <= cutoff]
        previous = older[-1] if older else observations[0]
    previous_value = _to_float(previous.get("value")) if previous else None
    change_4w = None
    if latest_value is not None and previous_value not in (None, 0):
        change_4w = (latest_value / previous_value - 1.0) * 100.0
    age_days = (today - latest_date).days if latest_date else None
    max_age_days = int(config.get("max_age_days", 30))
    stale = age_days is None or age_days > max_age_days
    return {
        "series_id": series_id,
        "series_name": config["name"],
        "frequency": config.get("frequency", "unknown"),
        "status": "WARN" if stale else "PASS",
        "issue": "fred_series_stale" if stale else "",
        "latest_value": latest_value,
        "latest_date": latest_date.isoformat() if latest_date else "",
        "age_days": age_days,
        "max_age_days": max_age_days,
        "change_4w": change_4w,
        "observations": observations[-8:],
        "stale": stale,
    }


def _load_cache(cache_path: Path | None) -> dict[str, Any]:
    if not cache_path or not cache_path.exists():
        return {}
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save_cache(cache_path: Path | None, payload: dict[str, Any]) -> None:
    if not cache_path:
        return
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _direct_csv_fetch(series_id: str, request_fn: Callable[[str, int], tuple[int, str]], as_of: date, timeout_seconds: int) -> dict[str, Any]:
    url = FRED_CSV_URL.format(
        series_id=series_id,
        start_date=(as_of - timedelta(days=550)).isoformat(),
        end_date=as_of.isoformat(),
    )
    status, text = request_fn(url, timeout_seconds)
    if not 200 <= int(status) < 300:
        raise RuntimeError(f"fred_http_{status}")
    result = summarize_observations(parse_fred_csv_observations(text, series_id), series_id=series_id, as_of=as_of)
    result.update({"provider": "FRED_CSV_DIRECT", "source": url, "cache_status": "NOT_USED", "fallback_used": True, "errors": []})
    return result


def fetch_fred_bundle(
    series_ids: list[str] | None = None,
    *,
    as_of: date | None = None,
    request_fn: Callable[[str, int], tuple[int, str]] | None = None,
    datareader_fn: DataReaderFn | None = None,
    cache_path: Path | None = None,
    timeout_seconds: int = 20,
    retries: int = 3,
    backoff_factor: float = 0.6,
) -> dict[str, Any]:
    today = as_of or datetime.now(timezone.utc).date()
    ids = series_ids or list(SERIES_CONFIG)
    cache = _load_cache(cache_path)
    cached_series = cache.get("series", {}) if isinstance(cache.get("series"), dict) else {}
    series: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    if datareader_fn is None:
        try:
            from pandas_datareader import data as pdr_data

            datareader_fn = pdr_data.DataReader
        except Exception as exc:
            errors.append(f"pandas_datareader_unavailable:{type(exc).__name__}")

    for series_id in ids:
        item_errors: list[str] = []
        result: dict[str, Any] | None = None
        start = today - timedelta(days=550)
        if datareader_fn is not None:
            try:
                frame = datareader_fn(series_id, "fred", start, today)
                result = summarize_observations(dataframe_observations(frame, series_id), series_id=series_id, as_of=today)
                result.update({"provider": "PANDAS_DATAREADER_FRED", "source": "FRED", "cache_status": "REFRESHED", "fallback_used": False, "errors": []})
            except Exception as exc:
                item_errors.append(f"pandas_datareader:{type(exc).__name__}:{str(exc)[:160]}")
        if result is None and request_fn is not None:
            try:
                result = _direct_csv_fetch(series_id, request_fn, today, timeout_seconds)
            except Exception as exc:
                item_errors.append(f"csv_direct:{type(exc).__name__}:{str(exc)[:160]}")
        if result is None:
            cached = cached_series.get(series_id, {})
            if isinstance(cached, dict) and cached:
                result = dict(cached)
                result.update({"status": "WARN", "provider": result.get("provider", "CACHE"), "cache_status": "STALE_FALLBACK", "fallback_used": True})
            else:
                cfg = SERIES_CONFIG.get(series_id, {"name": series_id})
                result = {
                    "series_id": series_id,
                    "series_name": cfg.get("name", series_id),
                    "status": "WARN",
                    "issue": "fred_unavailable_no_cache",
                    "latest_value": None,
                    "latest_date": "",
                    "age_days": None,
                    "change_4w": None,
                    "provider": "UNAVAILABLE",
                    "source": "FRED",
                    "cache_status": "MISS",
                    "fallback_used": True,
                }
        result["errors"] = list(result.get("errors", [])) + item_errors
        series[series_id] = result

    cache_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "series": {key: value for key, value in series.items() if value.get("latest_value") is not None},
    }
    _save_cache(cache_path, cache_payload)
    bundle_status = "PASS" if all(value.get("status") == "PASS" for value in series.values()) else "WARN"
    provider_counts: dict[str, int] = {}
    for item in series.values():
        provider = str(item.get("provider", "UNKNOWN"))
        provider_counts[provider] = provider_counts.get(provider, 0) + 1
    return {
        "status": bundle_status,
        "provider": "FRED",
        "source": "FRED",
        "series": series,
        "provider_counts": provider_counts,
        "cache_updated": bool(cache_path),
        "errors": errors,
        "cache_path": str(cache_path) if cache_path else "",
        "retries": retries,
        "backoff_factor": backoff_factor,
    }
