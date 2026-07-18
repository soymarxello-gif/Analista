from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.data_telemetry import SourceMetrics
from engine.retry_policy import RetryPolicy, call_with_retry, is_transient_error


def main() -> int:
    policy = RetryPolicy(
        max_attempts=3,
        base_delay_seconds=0.1,
        max_delay_seconds=1,
        jitter_ratio=0,
    )
    metrics = SourceMetrics()
    delays: list[float] = []
    attempts = {"value": 0}

    def flaky():
        attempts["value"] += 1
        if attempts["value"] < 3:
            raise TimeoutError("temporary timeout")
        return "ok"

    assert call_with_retry(
        flaky,
        policy=policy,
        metrics=metrics,
        sleep_fn=delays.append,
    ) == "ok"
    assert attempts["value"] == 3
    assert metrics.retries == 2
    assert delays == [0.1, 0.2]

    permanent_attempts = {"value": 0}

    def permanent():
        permanent_attempts["value"] += 1
        raise ValueError("invalid ticker")

    try:
        call_with_retry(
            permanent,
            policy=policy,
            metrics=SourceMetrics(),
            sleep_fn=lambda _: None,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Permanent errors must be re-raised")

    assert permanent_attempts["value"] == 1
    assert is_transient_error(RuntimeError("HTTP 503 temporarily unavailable"))
    assert not is_transient_error(ValueError("invalid schema"))
    print("OK: transient retries use bounded exponential backoff and telemetry counters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
