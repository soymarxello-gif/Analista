from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from .source_priority import (
    FINVIZ,
    GOOGLE_SHEETS_MANUAL,
    MARKETWATCH,
    MISSING,
    TRADINGVIEW_MANUAL,
    UNKNOWN,
    YAHOO_FINANCE,
    normalize_source,
)

METADATA_FIELDS = ("sector", "industry", "market_cap", "earnings_date", "next_earnings_date")

FIELD_SOURCE_COLUMNS = {
    "sector": "sector_source",
    "industry": "industry_source",
    "market_cap": "market_cap_source",
    "earnings_date": "earnings_source",
    "next_earnings_date": "earnings_source",
}

ESSENTIAL_FIELDS = ("sector", "industry", "market_cap")
SECONDARY_SOURCE_ORDER = (FINVIZ, MARKETWATCH, TRADINGVIEW_MANUAL, GOOGLE_SHEETS_MANUAL)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True

    try:
        if isinstance(value, float) and math.isnan(value):
            return True
        if pd.isna(value):
            return True
    except Exception:
        pass

    text = str(value).strip().lower()
    return text in {"", "none", "nan", "null", "na", "n/a", "unknown", "missing"}


def _safe_number(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _valid_value(field: str, value: Any) -> bool:
    if _is_missing(value):
        return False
    if field == "market_cap":
        numeric = _safe_number(value)
        return numeric is not None and numeric > 0
    return True


def _clean_value(field: str, value: Any) -> Any:
    if field == "market_cap":
        return _safe_number(value)
    return value


def _append_note(notes: list[str], note: str) -> None:
    if note and note not in notes:
        notes.append(note)


@dataclass(frozen=True)
class MetadataProvider:
    source: str
    fetcher: Callable[[str, dict], dict[str, Any] | None]

    def fetch(self, ticker: str, config: dict | None = None) -> dict[str, Any]:
        try:
            payload = self.fetcher(ticker, config or {}) or {}
        except Exception as exc:
            return {"metadata_fallback_error": str(exc)}
        return dict(payload)


class StaticMetadataProvider(MetadataProvider):
    def __init__(self, source: str, records: dict[str, dict[str, Any]]):
        normalized = {str(k).upper(): dict(v) for k, v in records.items()}

        def fetcher(ticker: str, _config: dict) -> dict[str, Any] | None:
            return normalized.get(str(ticker).upper())

        super().__init__(normalize_source(source), fetcher)


class ManualMetadataProvider(MetadataProvider):
    def __init__(self, source: str, path: str | Path):
        self.path = Path(path)
        records = _load_manual_records(self.path)
        super().__init__(normalize_source(source), StaticMetadataProvider(source, records).fetcher)


def _load_manual_records(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}

    if path.suffix.lower() == ".json":
        raw = pd.read_json(path)
    else:
        raw = pd.read_csv(path)

    if raw.empty or "ticker" not in raw.columns:
        return {}

    records: dict[str, dict[str, Any]] = {}
    for _, row in raw.iterrows():
        ticker = str(row.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        records[ticker] = row.dropna().to_dict()
    return records


def build_metadata_providers(config: dict | None = None) -> list[MetadataProvider]:
    """
    Build secondary providers from auditable local files.

    This deliberately avoids brittle web scraping. Configure paths under:
    data_sources.metadata_fallback.manual_sources.{finviz,marketwatch,tradingview_manual}
    """
    config = config or {}
    fb_cfg = config.get("data_sources", {}).get("metadata_fallback", {})
    if fb_cfg.get("enabled", True) is False:
        return []

    manual_sources = fb_cfg.get("manual_sources", {}) or {}
    source_paths = [
        (FINVIZ, manual_sources.get("finviz")),
        (MARKETWATCH, manual_sources.get("marketwatch")),
        (TRADINGVIEW_MANUAL, manual_sources.get("tradingview_manual") or manual_sources.get("tradingview")),
    ]

    providers: list[MetadataProvider] = []
    for source, path in source_paths:
        if path:
            providers.append(ManualMetadataProvider(source, path))

    sheets_cfg = config.get("data_sources", {}).get("providers", {}).get("google_sheets_manual", {}) or {}
    if sheets_cfg.get("enabled", False):
        from .google_sheets_manual import load_google_sheets_records

        result = load_google_sheets_records(
            str(sheets_cfg.get("published_csv_url") or ""),
            timeout_seconds=int(sheets_cfg.get("timeout_seconds", 20) or 20),
            max_stale_minutes=int(sheets_cfg.get("max_stale_minutes", 1440) or 1440),
        )
        records = result.get("records", {}) if isinstance(result, dict) else {}
        if records:
            providers.append(StaticMetadataProvider(GOOGLE_SHEETS_MANUAL, records))
    return providers


def _provider_sort_key(provider: MetadataProvider) -> int:
    try:
        return SECONDARY_SOURCE_ORDER.index(normalize_source(provider.source))
    except ValueError:
        return len(SECONDARY_SOURCE_ORDER)


def _metadata_confidence(row: dict[str, Any], fallback_used: bool) -> str:
    valid_count = sum(1 for field in ESSENTIAL_FIELDS if _valid_value(field, row.get(field)))
    if valid_count == len(ESSENTIAL_FIELDS):
        return "MEDIUM" if fallback_used else "HIGH"
    if valid_count == 0:
        return UNKNOWN
    return "LOW"


def apply_metadata_fallback(
    metadata: dict[str, Any],
    config: dict | None = None,
    providers: list[MetadataProvider] | None = None,
) -> dict[str, Any]:
    """
    Fill only missing/invalid metadata fields using secondary providers.

    Valid Yahoo values are preserved. Each covered field receives a source column,
    and failures degrade to MISSING/UNKNOWN without raising scanner errors.
    """
    config = config or {}
    row = dict(metadata)
    ticker = str(row.get("ticker") or "").upper().strip()

    primary_source = normalize_source(row.get("metadata_source"), YAHOO_FINANCE)
    if primary_source in {"CACHE", UNKNOWN, MISSING}:
        primary_source = YAHOO_FINANCE

    notes: list[str] = []
    used_sources: list[str] = []
    fallback_used = False

    for field, source_col in FIELD_SOURCE_COLUMNS.items():
        if field not in row and field == "next_earnings_date":
            continue
        if _valid_value(field, row.get(field)):
            row[source_col] = normalize_source(row.get(source_col), primary_source)

    if _valid_value("market_cap", row.get("market_cap")):
        row["market_cap"] = _clean_value("market_cap", row.get("market_cap"))

    if "quote_source" not in row:
        if any(_valid_value(field, row.get(field)) for field in ("bid", "ask", "regular_market_volume", "average_volume")):
            row["quote_source"] = primary_source
        else:
            row["quote_source"] = MISSING

    provider_list = sorted(providers if providers is not None else build_metadata_providers(config), key=_provider_sort_key)
    provider_payloads: list[tuple[str, dict[str, Any]]] = []
    if ticker:
        for provider in provider_list:
            source = normalize_source(provider.source)
            payload = provider.fetch(ticker, config)
            error = payload.get("metadata_fallback_error")
            if error:
                _append_note(notes, f"{source}:ERROR:{error}")
            elif not any(_valid_value(field, payload.get(field)) for field in METADATA_FIELDS):
                _append_note(notes, f"{source}:MISSING")
            provider_payloads.append((source, payload))

    for field in METADATA_FIELDS:
        if field not in row and field == "next_earnings_date":
            continue
        if _valid_value(field, row.get(field)):
            continue

        source_col = FIELD_SOURCE_COLUMNS[field]
        filled = False
        for source, payload in provider_payloads:
            value = payload.get(field)
            if not _valid_value(field, value):
                continue

            row[field] = _clean_value(field, value)
            row[source_col] = source
            if source not in used_sources:
                used_sources.append(source)
            fallback_used = True
            filled = True
            break

        if not filled:
            row[source_col] = MISSING
            if field != "next_earnings_date":
                _append_note(notes, f"{field}:MISSING_ALL_SOURCES")

    if _valid_value("earnings_date", row.get("earnings_date")) and not _valid_value(
        "next_earnings_date", row.get("next_earnings_date")
    ):
        row["next_earnings_date"] = row.get("earnings_date")

    if fallback_used:
        row["metadata_source"] = row.get("metadata_source") or used_sources[0]
    elif any(_valid_value(field, row.get(field)) for field in METADATA_FIELDS):
        row["metadata_source"] = row.get("metadata_source") or primary_source
    else:
        row["metadata_source"] = MISSING

    row["metadata_fallback_used"] = bool(row.get("metadata_fallback_used")) or fallback_used
    row["metadata_fallback_sources"] = ",".join(used_sources)
    row["metadata_fallback_notes"] = "; ".join(notes) if notes else ""
    row["metadata_confidence"] = _metadata_confidence(row, row["metadata_fallback_used"])

    return row
