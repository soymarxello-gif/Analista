from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from math import isfinite

import pandas as pd

from .models import PriceBar


@dataclass(frozen=True)
class DiscoveryFeatures:
    symbol: str
    as_of: datetime
    close: float
    rsi6: float
    rsi14: float
    ema20: float
    ema50: float
    ema200: float
    relative_volume20: float
    weekly_trend: str
    market_rs20_pct: float | None
    sector_rs20_pct: float | None
    eligible: bool
    reasons: tuple[str, ...]
    feature_hash: str


def ema(values: list[float], period: int) -> float:
    if len(values) < period:
        raise ValueError(f"at least {period} values required")
    value = sum(values[:period]) / period
    alpha = 2.0 / (period + 1)
    for current in values[period:]:
        value = alpha * current + (1 - alpha) * value
    return value


def rsi_wilder(values: list[float], period: int) -> float:
    if len(values) <= period:
        raise ValueError(f"more than {period} values required")
    changes = [current - previous for previous, current in zip(values, values[1:])]
    average_gain = sum(max(change, 0.0) for change in changes[:period]) / period
    average_loss = sum(max(-change, 0.0) for change in changes[:period]) / period
    for change in changes[period:]:
        average_gain = ((period - 1) * average_gain + max(change, 0.0)) / period
        average_loss = ((period - 1) * average_loss + max(-change, 0.0)) / period
    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100.0 - 100.0 / (1.0 + relative_strength)


def calendar_weekly_closes(bars: list[PriceBar]) -> list[float]:
    if not bars:
        return []
    frame = pd.DataFrame(
        {"close": [bar.close for bar in bars]},
        index=pd.DatetimeIndex([bar.session for bar in bars]),
    )
    return frame["close"].resample("W-FRI").last().dropna().astype(float).tolist()


def relative_return(asset: list[float], benchmark: list[float], sessions: int) -> float | None:
    if len(asset) <= sessions or len(benchmark) <= sessions:
        return None
    asset_return = asset[-1] / asset[-sessions - 1] - 1.0
    benchmark_return = benchmark[-1] / benchmark[-sessions - 1] - 1.0
    return (asset_return - benchmark_return) * 100.0


class DiscoveryEngine:
    VERSION = "technical-discovery-1"

    def evaluate(
        self,
        symbol: str,
        bars: list[PriceBar],
        as_of: datetime,
        *,
        market_bars: list[PriceBar] | None = None,
        sector_bars: list[PriceBar] | None = None,
    ) -> DiscoveryFeatures:
        if len(bars) < 220:
            raise ValueError("at least 220 point-in-time bars are required")
        closes = [bar.close for bar in bars]
        volumes = [bar.volume for bar in bars]
        rsi6 = rsi_wilder(closes, 6)
        rsi14 = rsi_wilder(closes, 14)
        weekly = calendar_weekly_closes(bars)
        weekly_trend = "UNKNOWN"
        if len(weekly) >= 30:
            weekly10 = ema(weekly, 10)
            weekly30 = ema(weekly, 30)
            weekly_trend = (
                "UP" if weekly[-1] > weekly10 > weekly30 else "DOWN" if weekly[-1] < weekly10 < weekly30 else "SIDEWAYS"
            )
        recent_volume = volumes[-20:]
        average_volume = sum(recent_volume[:-1]) / max(1, len(recent_volume) - 1)
        relative_volume = recent_volume[-1] / average_volume if average_volume > 0 else 0.0
        reasons: list[str] = []
        if not 25.0 <= rsi14 <= 65.0:
            reasons.append("rsi14_outside_25_65")
        if rsi6 <= rsi14:
            reasons.append("rsi6_not_above_rsi14")
        if weekly_trend == "DOWN":
            reasons.append("weekly_downtrend_context")
        market_rs = relative_return(closes, [bar.close for bar in market_bars or []], 20)
        sector_rs = relative_return(closes, [bar.close for bar in sector_bars or []], 20)
        numeric = [rsi6, rsi14, relative_volume, closes[-1]]
        if not all(isfinite(value) for value in numeric):
            raise ValueError("non-finite discovery feature")
        canonical = "|".join(
            [
                self.VERSION,
                symbol.upper(),
                as_of.isoformat(),
                f"{closes[-1]:.8f}",
                f"{rsi6:.8f}",
                f"{rsi14:.8f}",
                f"{relative_volume:.8f}",
                weekly_trend,
                "NONE" if market_rs is None else f"{market_rs:.8f}",
                "NONE" if sector_rs is None else f"{sector_rs:.8f}",
            ]
        )
        return DiscoveryFeatures(
            symbol=symbol.upper(),
            as_of=as_of,
            close=closes[-1],
            rsi6=rsi6,
            rsi14=rsi14,
            ema20=ema(closes, 20),
            ema50=ema(closes, 50),
            ema200=ema(closes, 200),
            relative_volume20=relative_volume,
            weekly_trend=weekly_trend,
            market_rs20_pct=market_rs,
            sector_rs20_pct=sector_rs,
            eligible=not any(reason in reasons for reason in ("rsi14_outside_25_65", "rsi6_not_above_rsi14")),
            reasons=tuple(reasons),
            feature_hash=sha256(canonical.encode()).hexdigest(),
        )
