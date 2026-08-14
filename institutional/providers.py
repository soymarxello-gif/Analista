from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Capability(StrEnum):
    SECURITY_MASTER = "SECURITY_MASTER"
    HISTORICAL_PRICE = "HISTORICAL_PRICE"
    EXECUTION_QUOTE = "EXECUTION_QUOTE"
    FUNDAMENTALS = "FUNDAMENTALS"
    EARNINGS_CALENDAR = "EARNINGS_CALENDAR"
    OPTIONS = "OPTIONS"
    MACRO = "MACRO"
    POSITIONING = "POSITIONING"
    INSIDERS = "INSIDERS"


@dataclass(frozen=True)
class ProviderContract:
    capability: Capability
    provider: str
    feed: str | None
    implemented: bool
    execution_grade: bool
    point_in_time: bool
    notes: str


class ProviderPolicy:
    VERSION = "provider-contracts-2"
    CONTRACTS = (
        ProviderContract(Capability.SECURITY_MASTER, "NASDAQ_TRADER", None, True, True, False, "current directory; snapshots become point-in-time after ingestion"),
        ProviderContract(Capability.SECURITY_MASTER, "ALPACA", "ASSETS", True, True, False, "current tradability"),
        ProviderContract(Capability.HISTORICAL_PRICE, "ALPACA", "SIP", True, True, False, "current backfill; persist daily snapshots for point-in-time research"),
        ProviderContract(Capability.HISTORICAL_PRICE, "ALPACA", "IEX", True, False, False, "research degraded"),
        ProviderContract(Capability.EXECUTION_QUOTE, "ALPACA", "SIP", False, True, True, "target contract; live quote ingestion not wired"),
        ProviderContract(Capability.FUNDAMENTALS, "SEC", "COMPANYFACTS", True, True, True, "late candidate enrichment; filed facts only"),
        ProviderContract(Capability.EARNINGS_CALENDAR, "LICENSED_VENDOR", None, False, True, True, "configure vendor"),
        ProviderContract(Capability.OPTIONS, "ALPACA", "OPRA", True, True, True, "late snapshot enrichment; OI not exposed and no dealer GEX claim"),
        ProviderContract(Capability.MACRO, "FRED_ALFRED", None, True, True, True, "vintage boundary persisted"),
        ProviderContract(Capability.POSITIONING, "CFTC", "TFF", False, True, True, "target contract; backend ingestion not wired"),
        ProviderContract(Capability.POSITIONING, "FINRA", "SHORT_INTEREST", False, True, True, "target contract; backend ingestion not wired"),
        ProviderContract(Capability.INSIDERS, "SEC", "FORM4", False, True, True, "target contract; backend daily index not wired"),
    )

    @classmethod
    def contracts_for(cls, capability: Capability) -> tuple[ProviderContract, ...]:
        return tuple(contract for contract in cls.CONTRACTS if contract.capability == capability)

    @classmethod
    def execution_provider(cls, capability: Capability) -> ProviderContract | None:
        return next(
            (
                contract
                for contract in cls.contracts_for(capability)
                if contract.implemented and contract.execution_grade
            ),
            None,
        )

    @classmethod
    def validate(cls) -> None:
        if any(contract.provider == "TRADINGVIEW" for contract in cls.CONTRACTS):
            raise ValueError("TradingView cannot be configured as a data provider")
        duplicates = [
            (contract.capability, contract.provider, contract.feed)
            for contract in cls.CONTRACTS
        ]
        if len(duplicates) != len(set(duplicates)):
            raise ValueError("duplicate provider contract")
