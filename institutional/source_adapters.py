from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any

from .models import AssetType, SecurityRecord


@dataclass(frozen=True)
class CompanyFactValue:
    value: float
    period_end: date
    filed_at: datetime
    accession: str
    form: str


def parse_nasdaq_symbol_directory(
    payload: str,
    *,
    available_at: datetime,
    exchange: str,
    source: str,
) -> list[SecurityRecord]:
    """Parse Nasdaq Trader pipe-delimited symbol files, excluding test issues."""
    lines = [line for line in payload.splitlines() if line.strip()]
    if len(lines) < 2:
        return []
    headers = [header.strip() for header in lines[0].split("|")]
    output: list[SecurityRecord] = []
    for line in lines[1:]:
        if line.startswith("File Creation Time"):
            continue
        values = line.split("|")
        if len(values) != len(headers):
            continue
        row = dict(zip(headers, values))
        symbol = (row.get("Symbol") or row.get("NASDAQ Symbol") or row.get("ACT Symbol") or "").strip().upper()
        if not symbol or row.get("Test Issue", "N").strip().upper() == "Y":
            continue
        is_etf = row.get("ETF", "N").strip().upper() == "Y"
        security_name = (row.get("Security Name") or "").strip()
        normalized_name = security_name.upper()
        excluded_non_common = (
            " WARRANT",
            " RIGHTS",
            " RIGHT ",
            " UNITS",
            " UNIT ",
            " PREFERRED",
            " PREFERENCE",
            " DEPOSITARY SHARES",
            " NOTES DUE",
            " CLOSED-END",
        )
        if not is_etf and any(marker in f" {normalized_name} " for marker in excluded_non_common):
            continue
        exchange_value = exchange
        if exchange.upper() == "AUTO":
            exchange_value = {
                "A": "AMEX",
                "N": "NYSE",
                "P": "ARCA",
                "Q": "NASDAQ",
                "Z": "BATS",
                "V": "IEX",
            }.get(row.get("Exchange", "").strip().upper(), "UNKNOWN")
        output.append(
            SecurityRecord(
                symbol=symbol.replace(".", "-"),
                asset_type=AssetType.ETF if is_etf else AssetType.COMMON_STOCK,
                exchange=exchange_value,
                currency="USD",
                active=True,
                valid_from=datetime.combine(available_at.date(), time.min, tzinfo=timezone.utc),
                valid_to=None,
                available_at=available_at,
                market_cap_usd=None,
                name=security_name or None,
                source=source,
            )
        )
    return output


def sec_company_fact_as_of(
    payload: dict[str, Any],
    taxonomy: str,
    concept: str,
    unit: str,
    as_of: datetime,
) -> CompanyFactValue | None:
    """Select the newest SEC fact that had actually been filed by ``as_of``."""
    values = (
        payload.get("facts", {})
        .get(taxonomy, {})
        .get(concept, {})
        .get("units", {})
        .get(unit, [])
    )
    eligible: list[CompanyFactValue] = []
    for item in values:
        try:
            filed = datetime.fromisoformat(item["filed"]).replace(tzinfo=timezone.utc)
            period_end = date.fromisoformat(item["end"])
            value = float(item["val"])
        except (KeyError, TypeError, ValueError):
            continue
        if filed <= as_of and datetime.combine(period_end, time.max, tzinfo=timezone.utc) <= as_of:
            eligible.append(
                CompanyFactValue(
                    value=value,
                    period_end=period_end,
                    filed_at=filed,
                    accession=str(item.get("accn", "")),
                    form=str(item.get("form", "")),
                )
            )
    return max(eligible, key=lambda value: (value.filed_at, value.period_end), default=None)


def validate_market_feed(feed: str, *, use_case: str) -> str:
    normalized_feed = feed.strip().upper()
    normalized_use = use_case.strip().upper()
    if normalized_use in {"ADV", "RELATIVE_VOLUME", "TRIGGER_CONFIRMATION"} and normalized_feed == "IEX":
        return "DEGRADED_RESEARCH_ONLY"
    if normalized_use == "OPTIONS_EXECUTION" and normalized_feed != "OPRA":
        return "DEGRADED_RESEARCH_ONLY"
    if normalized_feed in {"SIP", "OPRA"}:
        return "EXECUTION_GRADE"
    return "RESEARCH_ONLY"
