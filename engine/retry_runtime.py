from __future__ import annotations

from engine.data_telemetry import TelemetryState
from engine.retry_policy import RetryPolicy, call_with_retry


def install_retries(scanner_module, config: dict, telemetry: TelemetryState) -> RetryPolicy:
    """Wrap remote scanner clients with transient-error retries."""
    policy = RetryPolicy.from_config(config)
    bindings = (
        ("run_screeners", "screeners"),
        ("enrich_metadata", "fundamentals_yahoo"),
        ("download_daily_prices", "price_history_yahoo"),
        ("fetch_options_metrics", "options_yahoo"),
    )

    for attribute, source_name in bindings:
        original = getattr(scanner_module, attribute)
        metrics = telemetry.source(source_name)

        def wrapped(*args, _original=original, _metrics=metrics, **kwargs):
            return call_with_retry(
                _original,
                *args,
                policy=policy,
                metrics=_metrics,
                **kwargs,
            )

        setattr(scanner_module, attribute, wrapped)

    return policy
