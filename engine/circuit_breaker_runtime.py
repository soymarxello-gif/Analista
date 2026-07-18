from __future__ import annotations

import pandas as pd

from engine.circuit_breaker import CircuitBreakerPolicy, CircuitOpenError, CircuitState
from engine.data_telemetry import TelemetryState


def install_circuit_breakers(scanner_module, config: dict, telemetry: TelemetryState):
    policy = CircuitBreakerPolicy.from_config(config)
    states = {}
    bindings = (
        ("run_screeners", "screeners"),
        ("enrich_metadata", "fundamentals_yahoo"),
        ("download_daily_prices", "price_history_yahoo"),
        ("fetch_options_metrics", "options_yahoo"),
    )

    for attribute, source_name in bindings:
        original = getattr(scanner_module, attribute)
        state = states.setdefault(source_name, CircuitState())
        metrics = telemetry.source(source_name)

        def wrapped(*args, _original=original, _state=state, _source=source_name, _metrics=metrics, **kwargs):
            if _state.is_open(policy):
                _metrics.blocked_calls += 1
                return _degraded_result(_source, args)
            try:
                result = _original(*args, **kwargs)
            except Exception:
                if _state.record_failure(policy):
                    _metrics.circuit_opens += 1
                raise
            _state.record_success()
            return result

        setattr(scanner_module, attribute, wrapped)

    return policy, states


def _degraded_result(source: str, args: tuple):
    if source == "screeners":
        raise CircuitOpenError("circuit breaker abierto para screeners")
    if source == "fundamentals_yahoo":
        frame = args[0].copy() if args and isinstance(args[0], pd.DataFrame) else pd.DataFrame()
        frame["metadata_source"] = "circuit_open"
        frame["fundamental_warning"] = "fundamentals_yahoo circuit breaker abierto"
        return frame
    if source == "price_history_yahoo":
        return {}
    if source == "options_yahoo":
        return {
            "options_data_available": False,
            "options_source": "circuit_open",
            "options_warning": "options_yahoo circuit breaker abierto",
        }
    raise CircuitOpenError(f"circuit breaker abierto para {source}")
