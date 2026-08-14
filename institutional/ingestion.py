from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import AssetType, PriceBar, SecurityRecord
from .source_adapters import parse_nasdaq_symbol_directory
from .store import InstitutionalStore


class IngestionError(RuntimeError):
    pass


@dataclass(frozen=True)
class IngestionResult:
    status: str
    securities_received: int
    securities_stored: int
    symbols_requested: int
    bars_stored: int
    feed: str
    errors: tuple[str, ...]


@dataclass(frozen=True)
class ContextIngestionResult:
    fred_series: int
    sec_companies: int
    option_underlyings: int
    errors: tuple[str, ...]


class HttpJsonClient:
    def request(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        attempts: int = 3,
    ) -> Any:
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                request = Request(url, headers={"User-Agent": "Analista/1.80 institutional-ingestor", **(headers or {})})
                with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed/provider URLs only
                    body = response.read().decode("utf-8")
                    content_type = response.headers.get("Content-Type", "")
                    return json.loads(body) if "json" in content_type or body.lstrip().startswith(("{", "[")) else body
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                last = exc
                if attempt + 1 < attempts:
                    time.sleep(0.5 * 2**attempt)
        raise IngestionError(f"provider request failed: {last}")


class InstitutionalIngestor:
    """Executable ingestion for Nasdaq Trader + Alpaca; never invents missing coverage."""

    NASDAQ_LISTED = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
    OTHER_LISTED = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
    ALPACA_ASSETS = "https://paper-api.alpaca.markets/v2/assets"
    ALPACA_BARS = "https://data.alpaca.markets/v2/stocks/bars"
    ALPACA_OPTION_CHAIN = "https://data.alpaca.markets/v1beta1/options/snapshots"
    NASDAQ_SCREENER = "https://api.nasdaq.com/api/screener/stocks"
    FRED_OBSERVATIONS = "https://api.stlouisfed.org/fred/series/observations"
    SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
    SEC_COMPANYFACTS = "https://data.sec.gov/api/xbrl/companyfacts"
    FRED_SERIES = ("DGS10", "DGS30", "VIXCLS", "DTWEXBGS", "DCOILWTICO", "M2SL", "RRPONTSYD")

    def __init__(self, store: InstitutionalStore, client: HttpJsonClient | None = None) -> None:
        self.store = store
        self.client = client or HttpJsonClient()

    def ingest_live(
        self,
        *,
        as_of: datetime | None = None,
        history_sessions: int = 320,
        batch_size: int = 150,
        symbols: list[str] | None = None,
    ) -> IngestionResult:
        as_of = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
        key = os.getenv("APCA_API_KEY_ID", "").strip()
        secret = os.getenv("APCA_API_SECRET_KEY", "").strip()
        feed = os.getenv("APCA_DATA_FEED", "sip").strip().lower()
        if not key or not secret:
            raise IngestionError("APCA_API_KEY_ID and APCA_API_SECRET_KEY are required for live ingestion")
        headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        errors: list[str] = []

        directory_records: list[SecurityRecord] = []
        for url, exchange in ((self.NASDAQ_LISTED, "NASDAQ"), (self.OTHER_LISTED, "AUTO")):
            try:
                payload = self.client.request(url)
                directory_records.extend(
                    parse_nasdaq_symbol_directory(
                        str(payload), available_at=as_of, exchange=exchange, source="NASDAQ_TRADER"
                    )
                )
            except IngestionError as exc:
                errors.append(f"NASDAQ_TRADER:{exchange}:{exc}")

        assets = self.client.request(f"{self.ALPACA_ASSETS}?{urlencode({'status': 'active', 'asset_class': 'us_equity'})}", headers=headers)
        if not isinstance(assets, list):
            raise IngestionError("Alpaca assets response is not a list")
        by_symbol = {record.symbol: record for record in directory_records}
        normalized: list[SecurityRecord] = []
        for item in assets:
            symbol = str(item.get("symbol", "")).upper().replace(".", "-")
            if not symbol or not item.get("tradable", False):
                continue
            directory = by_symbol.get(symbol)
            exchange = str(item.get("exchange") or (directory.exchange if directory else "")).upper()
            exchange = {"NASDAQ": "NASDAQ", "NYSE": "NYSE", "AMEX": "AMEX", "ARCA": "ARCA"}.get(exchange, exchange)
            asset_type = directory.asset_type if directory else AssetType.COMMON_STOCK
            normalized.append(
                SecurityRecord(
                    symbol=symbol,
                    asset_type=asset_type,
                    exchange=exchange,
                    currency="USD",
                    active=True,
                    valid_from=as_of.replace(hour=0, minute=0, second=0, microsecond=0),
                    valid_to=None,
                    available_at=as_of,
                    market_cap_usd=None,
                    name=str(item.get("name") or (directory.name if directory else "")) or None,
                    source="ALPACA_ASSETS+NASDAQ_TRADER",
                )
            )
        try:
            market_caps = self._nasdaq_market_caps()
        except IngestionError as exc:
            errors.append(f"NASDAQ_SCREENER_RESEARCH_METADATA:{exc}")
            market_caps = {}
        market_caps.update(self._load_market_caps(os.getenv("ANALISTA_MARKET_CAP_FILE")))
        normalized = [
            SecurityRecord(
                **{
                    **record.__dict__,
                    "market_cap_usd": market_caps.get(record.symbol),
                    "source": (
                        "ALPACA_ASSETS+NASDAQ_TRADER+NASDAQ_SCREENER_RESEARCH_METADATA"
                        if record.symbol in market_caps
                        else record.source
                    ),
                }
            )
            for record in normalized
        ]
        if symbols:
            requested = {symbol.upper() for symbol in symbols}
            normalized = [record for record in normalized if record.symbol in requested]
        self.store.put_security_records(normalized)

        requested_symbols = [
            record.symbol
            for record in normalized
            if record.asset_type == AssetType.ETF
            or record.market_cap_usd is None
            or record.market_cap_usd >= 1_500_000_000
        ]
        bars_stored = 0
        for offset in range(0, len(requested_symbols), batch_size):
            batch = requested_symbols[offset : offset + batch_size]
            try:
                latest = self.store.latest_bar_sessions(batch)
                starts = [latest[symbol] + timedelta(seconds=1) for symbol in batch if symbol in latest]
                start_at = min(starts) if len(starts) == len(batch) else as_of - timedelta(days=max(500, history_sessions * 2))
                start = start_at.date().isoformat()
                bars = self._alpaca_bars(batch, start, as_of, feed, headers)
                self.store.put_price_bars(bars)
                bars_stored += len(bars)
            except IngestionError as exc:
                errors.append(f"ALPACA_BARS:{batch[0]}..:{exc}")
        self.store.record_source_health(
            "ALPACA_BARS",
            as_of,
            "COMPLETE" if not errors and bars_stored else "PARTIAL" if bars_stored else "ERROR",
            100.0 * sum(bool(self.store.bars_as_of(symbol, as_of)) for symbol in requested_symbols) / max(1, len(requested_symbols)),
            0.0,
            f"feed={feed.upper()}; bars={bars_stored}; errors={len(errors)}",
        )
        return IngestionResult(
            status="COMPLETE" if not errors else "PARTIAL" if bars_stored else "ERROR",
            securities_received=len(directory_records),
            securities_stored=len(normalized),
            symbols_requested=len(requested_symbols),
            bars_stored=bars_stored,
            feed=feed.upper(),
            errors=tuple(errors),
        )

    def import_bundle(self, path: str | Path) -> IngestionResult:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        securities = [self._security(item) for item in payload.get("securities", [])]
        bars = [self._bar(item) for item in payload.get("bars", [])]
        self.store.put_security_records(securities)
        self.store.put_price_bars(bars)
        return IngestionResult("COMPLETE", len(securities), len(securities), len({bar.symbol for bar in bars}), len(bars), "BUNDLE", ())

    def ingest_context(self, symbols: list[str], *, as_of: datetime | None = None, maximum_symbols: int = 30) -> ContextIngestionResult:
        as_of = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
        selected = list(dict.fromkeys(symbol.upper() for symbol in symbols))[:maximum_symbols]
        errors: list[str] = []
        fred_count = self._ingest_fred(as_of, errors)
        sec_count = self._ingest_sec(selected, as_of, errors)
        option_count = self._ingest_options(selected, as_of, errors)
        return ContextIngestionResult(fred_count, sec_count, option_count, tuple(errors))

    def _ingest_fred(self, as_of: datetime, errors: list[str]) -> int:
        api_key = os.getenv("FRED_API_KEY", "").strip()
        if not api_key:
            self.store.record_source_health("FRED_ALFRED", as_of, "UNAVAILABLE", 0.0, None, "FRED_API_KEY missing")
            return 0
        stored = 0
        for series in self.FRED_SERIES:
            params = urlencode(
                {
                    "series_id": series,
                    "api_key": api_key,
                    "file_type": "json",
                    "realtime_start": as_of.date().isoformat(),
                    "realtime_end": as_of.date().isoformat(),
                    "observation_start": (as_of - timedelta(days=800)).date().isoformat(),
                    "observation_end": as_of.date().isoformat(),
                    "sort_order": "desc",
                    "limit": 1,
                }
            )
            try:
                payload = self.client.request(f"{self.FRED_OBSERVATIONS}?{params}")
                observation = next(
                    item for item in payload.get("observations", []) if item.get("value") not in {None, "."}
                )
                event_time = datetime.fromisoformat(observation["date"]).replace(tzinfo=timezone.utc)
                self.store.put_context_observation(
                    "FRED_ALFRED",
                    series,
                    event_time,
                    as_of,
                    "COMPLETE",
                    {
                        "value": float(observation["value"]),
                        "realtime_start": observation.get("realtime_start"),
                        "realtime_end": observation.get("realtime_end"),
                        "vintage_boundary": as_of.date().isoformat(),
                    },
                )
                stored += 1
            except (IngestionError, KeyError, StopIteration, TypeError, ValueError) as exc:
                errors.append(f"FRED_ALFRED:{series}:{exc}")
        self.store.record_source_health(
            "FRED_ALFRED",
            as_of,
            "COMPLETE" if stored == len(self.FRED_SERIES) else "PARTIAL" if stored else "ERROR",
            100.0 * stored / len(self.FRED_SERIES),
            0.0,
            f"vintage={as_of.date().isoformat()}; series={stored}/{len(self.FRED_SERIES)}",
        )
        return stored

    def _ingest_sec(self, symbols: list[str], as_of: datetime, errors: list[str]) -> int:
        contact = os.getenv("SEC_CONTACT_EMAIL", "").strip()
        if not contact:
            self.store.record_source_health("SEC_COMPANYFACTS", as_of, "UNAVAILABLE", 0.0, None, "SEC_CONTACT_EMAIL missing")
            return 0
        headers = {"User-Agent": f"Analista research {contact}"}
        try:
            tickers = self.client.request(self.SEC_TICKERS, headers=headers)
        except IngestionError as exc:
            errors.append(f"SEC_TICKERS:{exc}")
            return 0
        cik_by_symbol = {
            str(item.get("ticker", "")).upper().replace(".", "-"): int(item["cik_str"])
            for item in tickers.values()
            if item.get("ticker") and item.get("cik_str")
        }
        stored = 0
        concepts = (
            ("Revenues", "USD"),
            ("RevenueFromContractWithCustomerExcludingAssessedTax", "USD"),
            ("NetIncomeLoss", "USD"),
            ("Assets", "USD"),
            ("Liabilities", "USD"),
            ("EntityCommonStockSharesOutstanding", "shares"),
        )
        from .source_adapters import sec_company_fact_as_of

        for symbol in symbols:
            cik = cik_by_symbol.get(symbol)
            if cik is None:
                continue
            try:
                payload = self.client.request(f"{self.SEC_COMPANYFACTS}/CIK{cik:010d}.json", headers=headers)
                facts: dict[str, object] = {}
                filed_dates = []
                for concept, unit in concepts:
                    fact = sec_company_fact_as_of(payload, "us-gaap", concept, unit, as_of)
                    if fact is not None:
                        facts[concept] = fact.value
                        filed_dates.append(fact.filed_at)
                if not facts:
                    continue
                self.store.put_context_observation(
                    "SEC_COMPANYFACTS",
                    symbol,
                    max(filed_dates),
                    as_of,
                    "PARTIAL",
                    {"cik": cik, "facts": facts, "filed_at_max": max(filed_dates).isoformat()},
                )
                stored += 1
            except (IngestionError, KeyError, TypeError, ValueError) as exc:
                errors.append(f"SEC_COMPANYFACTS:{symbol}:{exc}")
        self.store.record_source_health(
            "SEC_COMPANYFACTS",
            as_of,
            "PARTIAL" if stored else "ERROR",
            100.0 * stored / max(1, len(symbols)),
            0.0,
            f"companies={stored}/{len(symbols)}; normalized_vendor_not_used",
        )
        return stored

    def _ingest_options(self, symbols: list[str], as_of: datetime, errors: list[str]) -> int:
        key = os.getenv("APCA_API_KEY_ID", "").strip()
        secret = os.getenv("APCA_API_SECRET_KEY", "").strip()
        feed = os.getenv("APCA_OPTIONS_FEED", "opra").strip().lower()
        if not key or not secret:
            self.store.record_source_health("ALPACA_OPTIONS", as_of, "UNAVAILABLE", 0.0, None, "Alpaca credentials missing")
            return 0
        headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        stored = 0
        for symbol in symbols:
            params = urlencode(
                {
                    "feed": feed,
                    "limit": 1000,
                    "expiration_date_gte": as_of.date().isoformat(),
                    "expiration_date_lte": (as_of + timedelta(days=45)).date().isoformat(),
                }
            )
            try:
                payload = self.client.request(f"{self.ALPACA_OPTION_CHAIN}/{symbol}?{params}", headers=headers)
                snapshots = payload.get("snapshots", {})
                if not isinstance(snapshots, dict):
                    raise IngestionError("option snapshots response has invalid shape")
                quotes = [item.get("latestQuote", {}) for item in snapshots.values()]
                valid_spreads = [
                    (float(item["ap"]) - float(item["bp"])) / ((float(item["ap"]) + float(item["bp"])) / 2)
                    for item in quotes
                    if float(item.get("ap") or 0) > float(item.get("bp") or 0) > 0
                ]
                self.store.put_context_observation(
                    "ALPACA_OPTIONS",
                    symbol,
                    as_of,
                    as_of,
                    "COMPLETE" if feed == "opra" else "PARTIAL",
                    {
                        "feed": feed.upper(),
                        "execution_grade": feed == "opra",
                        "contracts": len(snapshots),
                        "median_spread_pct": sorted(valid_spreads)[len(valid_spreads) // 2] * 100 if valid_spreads else None,
                        "open_interest_available": False,
                        "dealer_gamma_claimed": False,
                    },
                )
                stored += 1
            except (IngestionError, KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
                errors.append(f"ALPACA_OPTIONS:{symbol}:{exc}")
        self.store.record_source_health(
            "ALPACA_OPTIONS",
            as_of,
            "COMPLETE" if stored == len(symbols) and feed == "opra" else "PARTIAL" if stored else "ERROR",
            100.0 * stored / max(1, len(symbols)),
            0.0,
            f"feed={feed.upper()}; underlyings={stored}/{len(symbols)}; OI_not_available",
        )
        return stored

    def _alpaca_bars(
        self,
        symbols: list[str],
        start: str,
        as_of: datetime,
        feed: str,
        headers: dict[str, str],
    ) -> list[PriceBar]:
        output: list[PriceBar] = []
        page_token: str | None = None
        while True:
            params = {
                "symbols": ",".join(symbols),
                "timeframe": "1Day",
                "start": start,
                "end": as_of.isoformat(),
                "limit": 10000,
                "adjustment": "all",
                "feed": feed,
                "sort": "asc",
            }
            if page_token:
                params["page_token"] = page_token
            payload = self.client.request(f"{self.ALPACA_BARS}?{urlencode(params)}", headers=headers, timeout=60)
            if not isinstance(payload, dict) or not isinstance(payload.get("bars"), dict):
                raise IngestionError("Alpaca bars response has invalid shape")
            # ``as_of`` is the capture boundary supplied by the caller. Using it here
            # makes the just-completed atomic batch visible to the scan at that same
            # boundary while still preventing historical runs from seeing the backfill.
            ingested_at = as_of
            for symbol, rows in payload["bars"].items():
                for item in rows:
                    session = datetime.fromisoformat(str(item["t"]).replace("Z", "+00:00"))
                    output.append(
                        PriceBar(
                            symbol=symbol,
                            session=session,
                            open=float(item["o"]),
                            high=float(item["h"]),
                            low=float(item["l"]),
                            close=float(item["c"]),
                            volume=int(item["v"]),
                            available_at=ingested_at,
                            source="ALPACA",
                            feed=feed.upper(),
                            adjusted=True,
                        )
                    )
            page_token = payload.get("next_page_token")
            if not page_token:
                return output

    @staticmethod
    def _load_market_caps(path: str | None) -> dict[str, float]:
        if not path:
            return {}
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return {str(symbol).upper(): float(value) for symbol, value in payload.items() if value is not None}

    def _nasdaq_market_caps(self) -> dict[str, float]:
        params = urlencode({"tableonly": "true", "limit": 10000, "offset": 0, "download": "true"})
        payload = self.client.request(f"{self.NASDAQ_SCREENER}?{params}")
        try:
            rows = payload["data"]["table"]["rows"]
        except (KeyError, TypeError) as exc:
            raise IngestionError("Nasdaq screener response has invalid shape") from exc
        result: dict[str, float] = {}
        for row in rows or []:
            symbol = str(row.get("symbol", "")).upper().replace(".", "-")
            raw = str(row.get("marketCap") or "").replace("$", "").replace(",", "").strip()
            try:
                value = float(raw)
            except ValueError:
                continue
            if symbol and value > 0:
                result[symbol] = value
        return result

    @staticmethod
    def _security(item: dict[str, Any]) -> SecurityRecord:
        return SecurityRecord(
            **{
                **item,
                "asset_type": AssetType(item["asset_type"]),
                "valid_from": datetime.fromisoformat(item["valid_from"]),
                "valid_to": datetime.fromisoformat(item["valid_to"]) if item.get("valid_to") else None,
                "available_at": datetime.fromisoformat(item["available_at"]),
            }
        )

    @staticmethod
    def _bar(item: dict[str, Any]) -> PriceBar:
        return PriceBar(
            **{
                **item,
                "session": datetime.fromisoformat(item["session"]),
                "available_at": datetime.fromisoformat(item["available_at"]),
            }
        )
