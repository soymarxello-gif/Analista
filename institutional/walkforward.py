from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import inf
from statistics import mean, median


@dataclass(frozen=True)
class ResearchObservation:
    observation_id: str
    decision_time: datetime
    setup_type: str
    regime: str
    sector: str
    return_r: float | None
    activated: bool = True
    p0_valid: bool = True


@dataclass(frozen=True)
class Fold:
    number: int
    train: tuple[ResearchObservation, ...]
    validation: tuple[ResearchObservation, ...]
    test: tuple[ResearchObservation, ...]


@dataclass(frozen=True)
class Metrics:
    closed: int
    expectancy_r: float | None
    median_r: float | None
    hit_rate_pct: float | None
    profit_factor: float | None
    maximum_drawdown_r: float | None
    expectancy_ci95: tuple[float, float] | None


@dataclass(frozen=True)
class WalkForwardReport:
    folds: tuple[Fold, ...]
    out_of_sample: tuple[ResearchObservation, ...]
    metrics: Metrics
    eligible_for_promotion: bool
    reasons: tuple[str, ...]
    by_setup: dict[str, Metrics]
    by_regime: dict[str, Metrics]


@dataclass(frozen=True)
class WalkForwardConfig:
    train_size: int = 120
    validation_size: int = 40
    test_size: int = 40
    step_size: int = 40
    embargo_sessions: int = 21
    expanding: bool = True
    minimum_oos_closed: int = 200
    minimum_dominant_cell: int = 40
    minimum_expectancy_r: float = 0.10
    bootstrap_samples: int = 2_000
    random_seed: int = 7


class RollingWalkForward:
    VERSION = "rolling-walk-forward-1"

    def __init__(self, config: WalkForwardConfig = WalkForwardConfig()) -> None:
        self.config = config
        if min(config.train_size, config.validation_size, config.test_size, config.step_size) <= 0:
            raise ValueError("window sizes must be positive")
        if config.embargo_sessions < 0:
            raise ValueError("embargo_sessions cannot be negative")

    def split(self, observations: list[ResearchObservation]) -> tuple[Fold, ...]:
        self._validate(observations)
        ordered = sorted(observations, key=lambda row: (row.decision_time, row.observation_id))
        folds: list[Fold] = []
        cursor = self.config.train_size
        number = 1
        while True:
            validation_start = cursor
            validation_end = validation_start + self.config.validation_size
            test_start = validation_end
            test_end = test_start + self.config.test_size
            if test_end > len(ordered):
                break
            raw_train = ordered[:cursor] if self.config.expanding else ordered[cursor - self.config.train_size : cursor]
            validation = ordered[validation_start:validation_end]
            test = ordered[test_start:test_end]
            validation_boundary = validation[0].decision_time - timedelta(days=self.config.embargo_sessions)
            test_boundary = test[0].decision_time - timedelta(days=self.config.embargo_sessions)
            train = [row for row in raw_train if row.decision_time < validation_boundary]
            validation = [row for row in validation if row.decision_time < test_boundary]
            folds.append(Fold(number, tuple(train), tuple(validation), tuple(test)))
            number += 1
            cursor += self.config.step_size
        return tuple(folds)

    def evaluate(self, observations: list[ResearchObservation]) -> WalkForwardReport:
        folds = self.split(observations)
        oos_by_id: dict[str, ResearchObservation] = {}
        for fold in folds:
            for row in fold.test:
                oos_by_id.setdefault(row.observation_id, row)
        out_of_sample = tuple(sorted(oos_by_id.values(), key=lambda row: (row.decision_time, row.observation_id)))
        metrics = self.metrics(out_of_sample)
        reasons: list[str] = []
        if not folds:
            reasons.append("no_complete_rolling_fold")
        if metrics.closed < self.config.minimum_oos_closed:
            reasons.append("insufficient_oos_closed")
        if any(not row.p0_valid for row in out_of_sample):
            reasons.append("p0_regression_present")
        if metrics.expectancy_r is None or metrics.expectancy_r < self.config.minimum_expectancy_r:
            reasons.append("expectancy_below_gate")
        if metrics.expectancy_ci95 is None or metrics.expectancy_ci95[0] <= 0:
            reasons.append("expectancy_confidence_interval_crosses_zero")
        by_setup = self._group_metrics(out_of_sample, lambda row: row.setup_type)
        by_regime = self._group_metrics(out_of_sample, lambda row: row.regime)
        for key, cell in by_setup.items():
            if cell.closed >= metrics.closed * 0.20 and cell.closed < self.config.minimum_dominant_cell:
                reasons.append(f"insufficient_dominant_setup:{key}")
        return WalkForwardReport(
            folds=folds,
            out_of_sample=out_of_sample,
            metrics=metrics,
            eligible_for_promotion=not reasons,
            reasons=tuple(dict.fromkeys(reasons)),
            by_setup=by_setup,
            by_regime=by_regime,
        )

    def metrics(self, observations: tuple[ResearchObservation, ...] | list[ResearchObservation]) -> Metrics:
        returns = [row.return_r for row in observations if row.activated and row.return_r is not None]
        if not returns:
            return Metrics(0, None, None, None, None, None, None)
        wins = [value for value in returns if value > 0]
        losses = [value for value in returns if value < 0]
        cumulative = 0.0
        peak = 0.0
        drawdown = 0.0
        for value in returns:
            cumulative += value
            peak = max(peak, cumulative)
            drawdown = max(drawdown, peak - cumulative)
        profit_factor = sum(wins) / abs(sum(losses)) if losses else inf
        return Metrics(
            closed=len(returns),
            expectancy_r=mean(returns),
            median_r=median(returns),
            hit_rate_pct=100 * len(wins) / len(returns),
            profit_factor=profit_factor,
            maximum_drawdown_r=drawdown,
            expectancy_ci95=self._bootstrap_ci(returns),
        )

    def _bootstrap_ci(self, values: list[float]) -> tuple[float, float]:
        rng = random.Random(self.config.random_seed)
        estimates = sorted(
            mean(rng.choices(values, k=len(values)))
            for _ in range(self.config.bootstrap_samples)
        )
        lower = estimates[int(0.025 * (len(estimates) - 1))]
        upper = estimates[int(0.975 * (len(estimates) - 1))]
        return lower, upper

    def _group_metrics(self, rows: tuple[ResearchObservation, ...], key) -> dict[str, Metrics]:
        groups: dict[str, list[ResearchObservation]] = {}
        for row in rows:
            groups.setdefault(str(key(row)).upper() or "UNKNOWN", []).append(row)
        return {name: self.metrics(values) for name, values in sorted(groups.items())}

    @staticmethod
    def _validate(observations: list[ResearchObservation]) -> None:
        identifiers = [row.observation_id for row in observations]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("observation_id must be unique")
        if any(row.decision_time.tzinfo is None or row.decision_time.utcoffset() is None for row in observations):
            raise ValueError("decision_time must be timezone-aware")
