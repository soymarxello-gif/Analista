from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import floor

from .models import Outcome, PriceBar, SignalEvent
from .store import InstitutionalStore


@dataclass(frozen=True)
class CostModel:
    entry_slippage_bps: float = 5.0
    exit_slippage_bps: float = 5.0
    commission_per_share: float = 0.0
    version: str = "liquidity-cost-1"

    def __post_init__(self) -> None:
        if min(self.entry_slippage_bps, self.exit_slippage_bps, self.commission_per_share) < 0:
            raise ValueError("cost values cannot be negative")


class OutcomeEvaluator:
    """Evaluates immutable signals independently of the current universe."""

    VERSION = "fixed-horizon-outcomes-1"

    def __init__(self, store: InstitutionalStore, costs: CostModel = CostModel()) -> None:
        self.store = store
        self.costs = costs

    def evaluate(self, signal: SignalEvent, evaluated_at: datetime | None = None) -> Outcome:
        evaluated_at = evaluated_at or datetime.now(timezone.utc)
        bars = self.store.bars_after(
            signal.symbol,
            signal.decision_time,
            limit=signal.expiration_sessions + signal.maximum_holding_sessions + 1,
        )
        entry_index, entry_fill = self._entry(signal, bars)
        if entry_fill is None:
            status = "EXPIRED_NOT_TRIGGERED" if len(bars) >= signal.expiration_sessions else "PENDING"
            return Outcome(
                signal_id=signal.signal_id,
                evaluated_at=evaluated_at,
                status=status,
                triggered=False,
                entry_fill=None,
                exit_fill=None,
                return_r=None,
                return_5d_pct=None,
                return_10d_pct=None,
                return_20d_pct=None,
                mfe_pct=None,
                mae_pct=None,
                holding_sessions=min(len(bars), signal.expiration_sessions),
                cost_model_version=self.costs.version,
            )
        active = bars[entry_index : entry_index + signal.maximum_holding_sessions + 1]
        exit_fill: float | None = None
        status = "OPEN"
        ambiguous = False
        observed: list[PriceBar] = []
        for index, bar in enumerate(active):
            observed.append(bar)
            stop = bar.low <= signal.stop_price
            target = bar.high >= signal.target_price
            if index == 0 and bar.open < signal.trigger_price and stop:
                status = "CLOSED_AMBIGUOUS"
                ambiguous = True
                break
            if bar.open <= signal.stop_price:
                exit_fill = self._sell(bar.open)
                status = "CLOSED_STOP"
                break
            if bar.open >= signal.target_price:
                exit_fill = self._sell(bar.open)
                status = "CLOSED_TARGET"
                break
            if stop and target:
                status = "CLOSED_AMBIGUOUS"
                ambiguous = True
                break
            if stop:
                exit_fill = self._sell(signal.stop_price)
                status = "CLOSED_STOP"
                break
            if target:
                exit_fill = self._sell(signal.target_price)
                status = "CLOSED_TARGET"
                break
        if status == "OPEN" and len(active) > signal.maximum_holding_sessions:
            exit_fill = self._sell(active[signal.maximum_holding_sessions].close)
            status = "CLOSED_EXPIRED"
        risk = entry_fill - signal.stop_price
        return_r = (exit_fill - entry_fill) / risk if exit_fill is not None and risk > 0 else None
        mfe = max(((bar.high / entry_fill) - 1) * 100 for bar in observed) if observed else None
        mae = min(((bar.low / entry_fill) - 1) * 100 for bar in observed) if observed else None

        def markout(sessions: int) -> float | None:
            # Session one is the first complete session after the entry session.
            bar = active[sessions] if len(active) > sessions else None
            return ((bar.close / entry_fill) - 1) * 100 if bar else None

        return Outcome(
            signal_id=signal.signal_id,
            evaluated_at=evaluated_at,
            status=status,
            triggered=True,
            entry_fill=round(entry_fill, 4),
            exit_fill=round(exit_fill, 4) if exit_fill is not None else None,
            return_r=round(return_r, 4) if return_r is not None else None,
            return_5d_pct=self._round(markout(5)),
            return_10d_pct=self._round(markout(10)),
            return_20d_pct=self._round(markout(20)),
            mfe_pct=self._round(mfe),
            mae_pct=self._round(mae),
            holding_sessions=len(observed),
            cost_model_version=self.costs.version,
            ambiguous=ambiguous,
        )

    def evaluate_all(self) -> list[Outcome]:
        outcomes = [self.evaluate(signal) for signal in self.store.signals()]
        for outcome in outcomes:
            self.store.put_outcome(outcome)
        return outcomes

    def _entry(self, signal: SignalEvent, bars: list[PriceBar]) -> tuple[int, float | None]:
        for index, bar in enumerate(bars[: signal.expiration_sessions]):
            if bar.open > signal.maximum_entry or bar.high < signal.trigger_price:
                continue
            fill = max(bar.open, signal.trigger_price) * (1 + self.costs.entry_slippage_bps / 10_000)
            if fill <= signal.maximum_entry:
                return index, fill
        return 0, None

    def _sell(self, price: float) -> float:
        return price * (1 - self.costs.exit_slippage_bps / 10_000)

    @staticmethod
    def shares(position_value: float, entry_fill: float) -> int:
        return max(0, floor(position_value / entry_fill))

    @staticmethod
    def _round(value: float | None) -> float | None:
        return round(value, 4) if value is not None else None
