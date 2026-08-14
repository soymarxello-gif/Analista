from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from math import isfinite
from uuid import NAMESPACE_URL, uuid5

from .decision import DecisionEngine, DecisionInput
from .features import DiscoveryEngine, DiscoveryFeatures, ema
from .models import DataStatus, PriceBar, SignalEvent
from .outcomes import OutcomeEvaluator
from .source_adapters import validate_market_feed
from .store import InstitutionalStore
from .universe import UniverseBuilder, UniverseSnapshot
from .walkforward import ResearchObservation, RollingWalkForward


@dataclass(frozen=True)
class RunResult:
    run_id: str
    started_at: datetime
    finished_at: datetime
    status: str
    universe_count: int
    discovery_count: int
    signal_count: int
    outcome_count: int
    promotion_eligible: bool
    promotion_reasons: tuple[str, ...]
    funnel: dict[str, int]
    signals: tuple[SignalEvent, ...]
    errors: tuple[dict[str, str], ...]
    configuration_hash: str
    universe_hash: str

    def to_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "signals": [serialize_signal(signal) for signal in self.signals],
        }


def serialize_signal(signal: SignalEvent) -> dict[str, object]:
    return {
        **asdict(signal),
        "decision_time": signal.decision_time.isoformat(),
        "available_at": signal.available_at.isoformat(),
        "state": signal.state.value,
        "reasons": list(signal.reasons),
        "hard_vetoes": list(signal.hard_vetoes),
    }


class InstitutionalRuntime:
    """The only production scan path: point-in-time store -> discovery -> decision -> signal."""

    VERSION = "institutional-runtime-2-technical-selection"

    def __init__(
        self,
        store: InstitutionalStore,
        *,
        configuration: dict[str, object] | None = None,
        universe_builder: UniverseBuilder | None = None,
    ) -> None:
        self.store = store
        self.configuration = configuration or {}
        self.universe_builder = universe_builder or UniverseBuilder(store)
        self.discovery = DiscoveryEngine()
        self.decision = DecisionEngine()

    def run(self, as_of: datetime | None = None) -> RunResult:
        started = datetime.now(timezone.utc)
        as_of = (as_of or started).astimezone(timezone.utc)
        snapshot = self.universe_builder.build(as_of)
        configuration_hash = self._hash(self.configuration)
        universe_hash = self._universe_hash(snapshot)
        run_id = f"{as_of:%Y%m%dT%H%M%SZ}-{universe_hash[:10]}"
        market_bars = self.store.bars_as_of("SPY", as_of)
        funnel = dict(snapshot.funnel)
        funnel.update({"discovery_evaluated": 0, "canonical_filter_passed": 0, "signals_persisted": 0})
        signals: list[SignalEvent] = []
        errors: list[dict[str, str]] = []

        for member in snapshot.members:
            symbol = member.security.symbol
            try:
                bars = self.store.bars_as_of(symbol, as_of)
                sector_bars = self._sector_bars(member.security.sector, as_of)
                features = self.discovery.evaluate(
                    symbol, bars, as_of, market_bars=market_bars, sector_bars=sector_bars
                )
                funnel["discovery_evaluated"] += 1
                if not features.eligible:
                    for reason in features.reasons:
                        funnel[f"discovery_{reason}"] = funnel.get(f"discovery_{reason}", 0) + 1
                    continue
                funnel["canonical_filter_passed"] += 1
                signal = self._signal(
                    member.security.sector,
                    member.warnings,
                    bars,
                    features,
                    as_of,
                    configuration_hash,
                    universe_hash,
                )
                self.store.put_signal(signal)
                signals.append(signal)
                funnel["signals_persisted"] += 1
            except (ValueError, ArithmeticError) as exc:
                errors.append({"symbol": symbol, "error": str(exc)})
                funnel["discovery_error"] = funnel.get("discovery_error", 0) + 1

        status = "COMPLETED" if snapshot.members else "DATA_BLOCKED_EMPTY_UNIVERSE"
        if errors and signals:
            status = "COMPLETED_WITH_ERRORS"
        finished = datetime.now(timezone.utc)
        outcomes = OutcomeEvaluator(self.store).evaluate_all()
        outcome_by_id = {outcome.signal_id: outcome for outcome in outcomes}
        observations = []
        for signal in self.store.signals():
            outcome = outcome_by_id.get(signal.signal_id)
            observations.append(
                ResearchObservation(
                    observation_id=signal.signal_id,
                    decision_time=signal.decision_time,
                    setup_type=signal.setup_type,
                    regime=str(signal.metadata.get("regime_status") or "UNKNOWN"),
                    sector=str(signal.metadata.get("sector") or "UNKNOWN"),
                    return_r=outcome.return_r if outcome else None,
                    activated=bool(outcome and outcome.triggered),
                    p0_valid=not signal.hard_vetoes,
                )
            )
        walk_forward = RollingWalkForward().evaluate(observations)
        payload = {
            "runtime_version": self.VERSION,
            "as_of": as_of.isoformat(),
            "funnel": funnel,
            "errors": errors,
            "store_counts": self.store.table_counts(),
            "outcomes_evaluated": len(outcomes),
            "walk_forward_eligible": walk_forward.eligible_for_promotion,
            "walk_forward_reasons": list(walk_forward.reasons),
            "walk_forward_oos_closed": walk_forward.metrics.closed,
        }
        self.store.record_shadow_run(
            run_id, started, configuration_hash, universe_hash, len(signals), status, payload
        )
        return RunResult(
            run_id=run_id,
            started_at=started,
            finished_at=finished,
            status=status,
            universe_count=len(snapshot.members),
            discovery_count=funnel["discovery_evaluated"],
            signal_count=len(signals),
            outcome_count=len(outcomes),
            promotion_eligible=walk_forward.eligible_for_promotion,
            promotion_reasons=walk_forward.reasons,
            funnel=funnel,
            signals=tuple(signals),
            errors=tuple(errors),
            configuration_hash=configuration_hash,
            universe_hash=universe_hash,
        )

    def _signal(
        self,
        sector: str | None,
        eligibility_warnings: tuple[str, ...],
        bars: list[PriceBar],
        features: DiscoveryFeatures,
        as_of: datetime,
        configuration_hash: str,
        universe_hash: str,
    ) -> SignalEvent:
        recent = bars[-21:]
        prior = recent[:-1]
        true_ranges = [
            max(bar.high - bar.low, abs(bar.high - previous.close), abs(bar.low - previous.close))
            for previous, bar in zip(bars[-15:-1], bars[-14:])
        ]
        atr = sum(true_ranges) / len(true_ranges)
        prior_resistance = max(bar.high for bar in prior)
        recent_low = min(bar.low for bar in bars[-10:])
        breakout = bars[-1].close >= prior_resistance * 0.995
        pullback = abs(bars[-1].close / features.ema20 - 1) <= 0.025 and bars[-1].close > features.ema50
        setup_type = "BREAKOUT" if breakout else "PULLBACK" if pullback else "MOMENTUM_RECLAIM"
        quality = self._setup_quality(features, breakout, pullback)
        trigger = max(bars[-1].high, prior_resistance) * 1.001
        stop = min(trigger - atr, recent_low)
        if stop <= 0 or stop >= trigger:
            stop = trigger - max(atr, trigger * 0.02)
        risk = trigger - stop
        maximum_entry = trigger + risk * 0.25
        target = trigger + risk * 2.0
        if not all(isfinite(value) and value > 0 for value in (trigger, stop, maximum_entry, target)):
            raise ValueError("invalid non-finite trade geometry")
        feed_grade = validate_market_feed(bars[-1].feed, use_case="RELATIVE_VOLUME")
        data_status = DataStatus.COMPLETE if feed_grade == "EXECUTION_GRADE" else DataStatus.UNAVAILABLE
        closes = [bar.close for bar in bars]
        macd_series = [ema(closes[:index], 12) - ema(closes[:index], 26) for index in range(26, len(closes) + 1)]
        macd_value = macd_series[-1]
        macd_signal = ema(macd_series, 9)
        window = bars[-14:]
        stochastic = 100.0 * (closes[-1] - min(bar.low for bar in window)) / max(
            1e-12, max(bar.high for bar in window) - min(bar.low for bar in window)
        )
        decision = self.decision.decide(
            DecisionInput(
                setup_valid=True,
                setup_quality=quality,
                required_data_statuses=(data_status,),
                market_session_open=False,
                quote_fresh=False,
                trigger_confirmed=False,
                risk_plan_valid=True,
                regime_risk=None,
            )
        )
        identity = "|".join((features.symbol, as_of.isoformat(), features.feature_hash, configuration_hash))
        return SignalEvent(
            signal_id=str(uuid5(NAMESPACE_URL, identity)),
            symbol=features.symbol,
            decision_time=as_of,
            available_at=as_of,
            setup_type=setup_type,
            state=decision.state,
            setup_quality=quality,
            data_confidence=decision.data_confidence,
            regime_risk=decision.regime_risk,
            execution_readiness=decision.execution_readiness,
            trigger_price=round(trigger, 4),
            stop_price=round(stop, 4),
            target_price=round(target, 4),
            maximum_entry=round(maximum_entry, 4),
            expiration_sessions=5,
            maximum_holding_sessions=20,
            model_version=f"{self.VERSION}+{self.discovery.VERSION}+{self.decision.VERSION}",
            configuration_hash=configuration_hash,
            universe_snapshot_hash=universe_hash,
            feature_hash=features.feature_hash,
            reasons=tuple(dict.fromkeys((*features.reasons, *decision.reasons))),
            metadata={
                "calibration_status": "UNCALIBRATED_RESEARCH_SCORE",
                "sector": sector,
                "close": features.close,
                "rsi6": features.rsi6,
                "rsi14": features.rsi14,
                "ema20": features.ema20,
                "ema50": features.ema50,
                "ema200": features.ema200,
                "relative_volume20": features.relative_volume20,
                "atr14": atr,
                "macd": macd_value,
                "macd_signal": macd_signal,
                "stochastic14": stochastic,
                "weekly_trend": features.weekly_trend,
                "market_rs20_pct": features.market_rs20_pct,
                "sector_rs20_pct": features.sector_rs20_pct,
                "feed": bars[-1].feed,
                "feed_grade": feed_grade,
                "regime_status": "UNAVAILABLE",
                "eligibility_warnings": list(eligibility_warnings),
            },
        )

    @staticmethod
    def _setup_quality(features: DiscoveryFeatures, breakout: bool, pullback: bool) -> float:
        score = 45.0
        maximum = 100.0
        score += 15.0 if features.weekly_trend == "UP" else 5.0 if features.weekly_trend == "SIDEWAYS" else 0.0
        score += 12.0 if breakout else 8.0 if pullback else 4.0
        score += min(12.0, max(0.0, (features.relative_volume20 - 0.8) * 15.0))
        score += 8.0 if features.close > features.ema20 > features.ema50 else 0.0
        if features.market_rs20_pct is None:
            maximum -= 8.0
        elif features.market_rs20_pct > 0:
            score += 8.0
        return round(min(100.0, score * 100.0 / maximum), 4)

    def _sector_bars(self, sector: str | None, as_of: datetime) -> list[PriceBar] | None:
        mapping = self.configuration.get("sector_benchmarks", {})
        if not isinstance(mapping, dict) or not sector:
            return None
        symbol = mapping.get(sector)
        return self.store.bars_as_of(str(symbol), as_of) if symbol else None

    @staticmethod
    def _hash(value: object) -> str:
        return sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _universe_hash(snapshot: UniverseSnapshot) -> str:
        canonical = "|".join(member.security.symbol for member in snapshot.members)
        return sha256(canonical.encode()).hexdigest()
