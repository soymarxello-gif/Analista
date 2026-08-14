from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import AssetType, SecurityRecord
from .store import InstitutionalStore


@dataclass(frozen=True)
class UniversePolicy:
    minimum_price_usd: float = 10.0
    minimum_stock_market_cap_usd: float = 1_500_000_000.0
    minimum_average_dollar_volume_20d: float = 20_000_000.0
    minimum_history_sessions: int = 220
    maximum_latest_bar_age_days: int = 10
    allowed_exchanges: frozenset[str] = frozenset({"NASDAQ", "NYSE", "AMEX", "ARCA", "NYSEARCA", "BATS"})
    allowed_asset_types: frozenset[AssetType] = frozenset({AssetType.COMMON_STOCK, AssetType.ETF})


@dataclass(frozen=True)
class UniverseMember:
    security: SecurityRecord
    latest_price: float
    average_dollar_volume_20d: float
    history_sessions: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class UniverseExclusion:
    symbol: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class UniverseSnapshot:
    as_of: datetime
    members: tuple[UniverseMember, ...]
    exclusions: tuple[UniverseExclusion, ...]

    @property
    def funnel(self) -> dict[str, int]:
        counts: dict[str, int] = {"eligible": len(self.members), "excluded": len(self.exclusions)}
        for exclusion in self.exclusions:
            for reason in exclusion.reasons:
                counts[reason] = counts.get(reason, 0) + 1
        return counts


class UniverseBuilder:
    """Builds the full eligible universe; it never applies an arbitrary top-N cap."""

    VERSION = "full-universe-point-in-time-1"

    def __init__(self, store: InstitutionalStore, policy: UniversePolicy = UniversePolicy()) -> None:
        self.store = store
        self.policy = policy

    def build(self, as_of: datetime) -> UniverseSnapshot:
        members: list[UniverseMember] = []
        exclusions: list[UniverseExclusion] = []
        for security in self.store.securities_as_of(as_of):
            reasons = self._security_reasons(security)
            warnings = self._security_warnings(security)
            bars = self.store.bars_as_of(security.symbol, as_of)
            if len(bars) < self.policy.minimum_history_sessions:
                reasons.append("insufficient_history")
            latest_price = bars[-1].close if bars else 0.0
            if bars and (as_of.date() - bars[-1].session.date()).days > self.policy.maximum_latest_bar_age_days:
                reasons.append("stale_price_history")
            if latest_price < self.policy.minimum_price_usd:
                reasons.append("price_below_minimum")
            recent = bars[-20:]
            adv = sum(bar.close * bar.volume for bar in recent) / len(recent) if recent else 0.0
            if adv < self.policy.minimum_average_dollar_volume_20d:
                reasons.append("dollar_volume_below_minimum")
            if reasons:
                exclusions.append(UniverseExclusion(security.symbol, tuple(dict.fromkeys(reasons))))
            else:
                members.append(UniverseMember(security, latest_price, adv, len(bars), tuple(warnings)))
        members.sort(key=lambda row: row.security.symbol)
        exclusions.sort(key=lambda row: row.symbol)
        return UniverseSnapshot(as_of, tuple(members), tuple(exclusions))

    def _security_reasons(self, security: SecurityRecord) -> list[str]:
        reasons: list[str] = []
        if not security.active:
            reasons.append("inactive_as_of")
        if security.currency != "USD":
            reasons.append("non_usd")
        if security.exchange not in self.policy.allowed_exchanges:
            reasons.append("exchange_not_allowed")
        if security.asset_type not in self.policy.allowed_asset_types:
            reasons.append("asset_type_not_allowed")
        if (
            security.asset_type == AssetType.COMMON_STOCK
            and security.market_cap_usd is not None
            and security.market_cap_usd < self.policy.minimum_stock_market_cap_usd
        ):
            reasons.append("stock_market_cap_below_minimum")
        return reasons

    @staticmethod
    def _security_warnings(security: SecurityRecord) -> list[str]:
        if security.asset_type == AssetType.COMMON_STOCK and security.market_cap_usd is None:
            return ["stock_market_cap_unavailable"]
        return []
