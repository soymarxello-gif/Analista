from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from engine.data_telemetry import SourceMetrics

T = TypeVar("T")

TRANSIENT_MESSAGE_TOKENS = (
    "timeout",
    "timed out",
    "temporarily unavailable",
    "temporary failure",
    "connection reset",
    "connection aborted",
    "connection refused",
    "remote end closed",
    "rate limit",
    "too many requests",
    "http 429",
    "status 429",
    "http 500",
    "http 502",
    "http 503",
    "http 504",
    "status 500",
    "status 502",
    "status 503",
    "status 504",
)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 4.0
    jitter_ratio: float = 0.15

    @classmethod
    def from_config(cls, config: dict) -> "RetryPolicy":
        retry_cfg = config.get("data_sources", {}).get("retry", {})
        return cls(
            max_attempts=max(1, int(retry_cfg.get("max_attempts", 3))),
            base_delay_seconds=max(0.0, float(retry_cfg.get("base_delay_seconds", 0.5))),
            max_delay_seconds=max(0.0, float(retry_cfg.get("max_delay_seconds", 4.0))),
            jitter_ratio=max(0.0, float(retry_cfg.get("jitter_ratio", 0.15))),
        )


def is_transient_error(exc: Exception) -> bool:
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    if isinstance(exc, OSError) and getattr(exc, "errno", None) in {32, 54, 60, 61, 104, 110, 111}:
        return True
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(token in text for token in TRANSIENT_MESSAGE_TOKENS)


def retry_delay_seconds(policy: RetryPolicy, retry_index: int, random_fn=random.random) -> float:
    base = min(
        policy.max_delay_seconds,
        policy.base_delay_seconds * (2 ** max(0, retry_index - 1)),
    )
    if base <= 0 or policy.jitter_ratio <= 0:
        return base
    jitter = base * policy.jitter_ratio * ((2 * random_fn()) - 1)
    return max(0.0, min(policy.max_delay_seconds, base + jitter))


def call_with_retry(
    func: Callable[..., T],
    *args,
    policy: RetryPolicy,
    metrics: SourceMetrics,
    sleep_fn=time.sleep,
    random_fn=random.random,
    **kwargs,
) -> T:
    """Retry only transient failures and count each additional attempt."""
    attempt = 1
    while True:
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            if attempt >= policy.max_attempts or not is_transient_error(exc):
                raise
            metrics.retries += 1
            delay = retry_delay_seconds(policy, attempt, random_fn=random_fn)
            sleep_fn(delay)
            attempt += 1
