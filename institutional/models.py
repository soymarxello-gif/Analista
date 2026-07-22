from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def require_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


class AssetType(StrEnum):
    COMMON_STOCK = "COMMON_STOCK"
    ETF = "ETF"


class DataStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


class DecisionState(StrEnum):
    SETUP_DISCOVERED = "SETUP_DISCOVERED"
    READY_FOR_NEXT_SESSION = "READY_FOR_NEXT_SESSION"
    LIVE_TRIGGER_PENDING = "LIVE_TRIGGER_PENDING"
    TRIGGER_CONFIRMED = "TRIGGER_CONFIRMED"
    DATA_BLOCKED = "DATA_BLOCKED"
    HARD_VETO = "HARD_VETO"


@dataclass(frozen=True)
class SourceStamp:
    source: str
    event_time: datetime
    available_at: datetime
    ingested_at: datetime
    status: DataStatus = DataStatus.COMPLETE
    feed: str | None = None
    license_tier: str | None = None

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("source is required")
        require_utc(self.event_time, "event_time")
        require_utc(self.available_at, "available_at")
        require_utc(self.ingested_at, "ingested_at")
        if self.available_at < self.event_time:
            raise ValueError("available_at cannot precede event_time")


@dataclass(frozen=True)
class SecurityRecord:
    symbol: str
    asset_type: AssetType
    exchange: str
    currency: str
    active: bool
    valid_from: datetime
    valid_to: datetime | None
    available_at: datetime
    market_cap_usd: float | None = None
    sector: str | None = None
    industry: str | None = None
    name: str | None = None
    source: str = "UNKNOWN"

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        require_utc(self.valid_from, "valid_from")
        require_utc(self.available_at, "available_at")
        if self.valid_to is not None:
            require_utc(self.valid_to, "valid_to")
            if self.valid_to <= self.valid_from:
                raise ValueError("valid_to must be after valid_from")


@dataclass(frozen=True)
class PriceBar:
    symbol: str
    session: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    available_at: datetime
    source: str
    feed: str
    adjusted: bool

    def __post_init__(self) -> None:
        require_utc(self.session, "session")
        require_utc(self.available_at, "available_at")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("OHLC values must be positive")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high is inconsistent")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low is inconsistent")
        if self.volume < 0:
            raise ValueError("volume cannot be negative")


@dataclass(frozen=True)
class FeatureValue:
    name: str
    value: float | str | bool | None
    status: DataStatus
    source: str
    event_time: datetime
    available_at: datetime
    reason: str | None = None

    def __post_init__(self) -> None:
        require_utc(self.event_time, "event_time")
        require_utc(self.available_at, "available_at")
        if self.status in {DataStatus.UNAVAILABLE, DataStatus.ERROR} and self.value is not None:
            raise ValueError("unavailable/error feature values must remain null")


@dataclass(frozen=True)
class SignalEvent:
    signal_id: str
    symbol: str
    decision_time: datetime
    available_at: datetime
    setup_type: str
    state: DecisionState
    setup_quality: float
    data_confidence: float
    regime_risk: float | None
    execution_readiness: float
    trigger_price: float
    stop_price: float
    target_price: float
    maximum_entry: float
    expiration_sessions: int
    model_version: str
    configuration_hash: str
    universe_snapshot_hash: str
    feature_hash: str
    maximum_holding_sessions: int = 20
    reasons: tuple[str, ...] = ()
    hard_vetoes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_utc(self.decision_time, "decision_time")
        require_utc(self.available_at, "available_at")
        if self.available_at < self.decision_time:
            raise ValueError("available_at cannot precede decision_time")
        for name in ("setup_quality", "data_confidence", "execution_readiness"):
            if not 0 <= getattr(self, name) <= 100:
                raise ValueError(f"{name} must be between 0 and 100")
        if self.regime_risk is not None and not 0 <= self.regime_risk <= 100:
            raise ValueError("regime_risk must be null or between 0 and 100")
        if not self.stop_price < self.trigger_price <= self.maximum_entry < self.target_price:
            raise ValueError("invalid trade geometry")
        if self.expiration_sessions < 1:
            raise ValueError("expiration_sessions must be positive")
        if self.maximum_holding_sessions < 20:
            raise ValueError("maximum_holding_sessions must cover the 20-session outcome")


@dataclass(frozen=True)
class Outcome:
    signal_id: str
    evaluated_at: datetime
    status: str
    triggered: bool
    entry_fill: float | None
    exit_fill: float | None
    return_r: float | None
    return_5d_pct: float | None
    return_10d_pct: float | None
    return_20d_pct: float | None
    mfe_pct: float | None
    mae_pct: float | None
    holding_sessions: int
    cost_model_version: str
    ambiguous: bool = False

    def __post_init__(self) -> None:
        require_utc(self.evaluated_at, "evaluated_at")
        if self.holding_sessions < 0:
            raise ValueError("holding_sessions cannot be negative")
