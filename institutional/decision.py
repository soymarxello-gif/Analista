from __future__ import annotations

from dataclasses import dataclass

from .models import DataStatus, DecisionState


@dataclass(frozen=True)
class DecisionInput:
    setup_valid: bool
    setup_quality: float
    hard_vetoes: tuple[str, ...] = ()
    required_data_statuses: tuple[DataStatus, ...] = ()
    market_session_open: bool = False
    quote_fresh: bool = False
    trigger_confirmed: bool = False
    risk_plan_valid: bool = True
    regime_risk: float | None = None


@dataclass(frozen=True)
class DecisionResult:
    state: DecisionState
    setup_quality: float
    data_confidence: float
    regime_risk: float | None
    execution_readiness: float
    reasons: tuple[str, ...]


class DecisionEngine:
    VERSION = "decision-lifecycle-1"

    def decide(self, value: DecisionInput) -> DecisionResult:
        if not 0 <= value.setup_quality <= 100:
            raise ValueError("setup_quality must be between 0 and 100")
        if value.regime_risk is not None and not 0 <= value.regime_risk <= 100:
            raise ValueError("regime_risk must be null or between 0 and 100")
        statuses = value.required_data_statuses
        if not statuses:
            data_confidence = 0.0
        else:
            weights = {
                DataStatus.COMPLETE: 1.0,
                DataStatus.PARTIAL: 0.5,
                DataStatus.STALE: 0.0,
                DataStatus.UNAVAILABLE: 0.0,
                DataStatus.ERROR: 0.0,
            }
            data_confidence = 100.0 * sum(weights[status] for status in statuses) / len(statuses)
        readiness = 0.0
        readiness += 35.0 if value.risk_plan_valid else 0.0
        readiness += 25.0 if value.market_session_open else 0.0
        readiness += 25.0 if value.quote_fresh else 0.0
        readiness += 15.0 if value.trigger_confirmed else 0.0
        reasons: list[str] = []
        if value.hard_vetoes:
            state = DecisionState.HARD_VETO
            reasons.extend(value.hard_vetoes)
        elif not value.setup_valid:
            state = DecisionState.DATA_BLOCKED if data_confidence == 0 else DecisionState.SETUP_DISCOVERED
            reasons.append("setup_not_validated")
        elif any(status in {DataStatus.ERROR, DataStatus.UNAVAILABLE, DataStatus.STALE} for status in statuses):
            state = DecisionState.DATA_BLOCKED
            reasons.append("required_data_not_execution_grade")
        elif value.trigger_confirmed and value.market_session_open and value.quote_fresh and value.risk_plan_valid:
            state = DecisionState.TRIGGER_CONFIRMED
        elif value.market_session_open:
            state = DecisionState.LIVE_TRIGGER_PENDING
            reasons.append("trigger_pending")
        elif value.risk_plan_valid:
            state = DecisionState.READY_FOR_NEXT_SESSION
            reasons.append("market_closed_setup_preserved")
        else:
            state = DecisionState.SETUP_DISCOVERED
            reasons.append("risk_plan_pending")
        return DecisionResult(
            state=state,
            setup_quality=value.setup_quality,
            data_confidence=data_confidence,
            regime_risk=value.regime_risk,
            execution_readiness=readiness,
            reasons=tuple(reasons),
        )
