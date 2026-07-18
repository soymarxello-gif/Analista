from __future__ import annotations

import sys
from pathlib import Path
import types
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.circuit_breaker_runtime import install_circuit_breakers
from engine.data_telemetry import TelemetryState


def main() -> int:
    config = {"data_sources": {"circuit_breaker": {"failure_threshold": 2, "recovery_timeout_seconds": 999}}}
    calls = {"options": 0}

    def fail_options(*_args, **_kwargs):
        calls["options"] += 1
        raise TimeoutError("temporary")

    scanner = types.SimpleNamespace(
        run_screeners=lambda config: None,
        enrich_metadata=lambda df, config: df,
        download_daily_prices=lambda tickers, *a, **k: {},
        fetch_options_metrics=fail_options,
    )
    telemetry = TelemetryState()
    install_circuit_breakers(scanner, config, telemetry)
    for _ in range(2):
        try:
            scanner.fetch_options_metrics("ABC", 10, config)
        except TimeoutError:
            pass
    degraded = scanner.fetch_options_metrics("ABC", 10, config)
    assert calls["options"] == 2
    assert degraded["options_source"] == "circuit_open"
    metrics = telemetry.source("options_yahoo")
    assert metrics.circuit_opens == 1 and metrics.blocked_calls == 1

    def fail_fundamentals(df, config):
        raise ConnectionError("down")

    fresh = types.SimpleNamespace(
        run_screeners=lambda config: None,
        enrich_metadata=fail_fundamentals,
        download_daily_prices=lambda tickers, *a, **k: {},
        fetch_options_metrics=lambda *a, **k: {},
    )
    telemetry2 = TelemetryState()
    install_circuit_breakers(fresh, config, telemetry2)
    frame = pd.DataFrame([{"ticker": "ABC"}])
    for _ in range(2):
        try:
            fresh.enrich_metadata(frame, config)
        except ConnectionError:
            pass
    degraded_frame = fresh.enrich_metadata(frame, config)
    assert degraded_frame.loc[0, "metadata_source"] == "circuit_open"
    print("OK: circuit breaker opens after threshold and degrades sources explicitly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
