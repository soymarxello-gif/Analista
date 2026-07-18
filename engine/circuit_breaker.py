from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


class CircuitOpenError(RuntimeError):
    pass


@dataclass(frozen=True)
class CircuitBreakerPolicy:
    failure_threshold: int = 3
    recovery_timeout_seconds: float = 60.0

    @classmethod
    def from_config(cls, config: dict) -> "CircuitBreakerPolicy":
        raw = config.get("data_sources", {}).get("circuit_breaker", {})
        return cls(
            failure_threshold=max(1, int(raw.get("failure_threshold", 3))),
            recovery_timeout_seconds=max(0.0, float(raw.get("recovery_timeout_seconds", 60.0))),
        )


@dataclass
class CircuitState:
    consecutive_failures: int = 0
    opened_at: float | None = None

    def is_open(self, policy: CircuitBreakerPolicy, now: float | None = None) -> bool:
        if self.opened_at is None:
            return False
        current = monotonic() if now is None else now
        if current - self.opened_at >= policy.recovery_timeout_seconds:
            self.opened_at = None
            self.consecutive_failures = 0
            return False
        return True

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.opened_at = None

    def record_failure(self, policy: CircuitBreakerPolicy, now: float | None = None) -> bool:
        self.consecutive_failures += 1
        if self.consecutive_failures >= policy.failure_threshold:
            self.opened_at = monotonic() if now is None else now
            return True
        return False
