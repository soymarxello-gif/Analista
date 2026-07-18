from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.source_health import assess_source_health, build_health_summary, format_health_log


def main() -> int:
    config = {"telemetry": {"health": {"degraded_latency_ms_avg": 1000}}}

    healthy = assess_source_health(
        {"calls": 10, "failures": 0, "retries": 0, "latency_ms_avg": 100, "requested_items": 10, "coverage_pct": 100, "circuit_opens": 0, "blocked_calls": 0},
        config,
    )
    assert healthy["health_status"] == "HEALTHY"

    degraded = assess_source_health(
        {"calls": 10, "failures": 1, "retries": 2, "latency_ms_avg": 1500, "requested_items": 10, "coverage_pct": 80, "circuit_opens": 0, "blocked_calls": 0},
        config,
    )
    assert degraded["health_status"] == "DEGRADED"
    assert "low_coverage" in degraded["health_reasons"]

    critical = assess_source_health(
        {"calls": 4, "failures": 2, "retries": 3, "latency_ms_avg": 12000, "requested_items": 4, "coverage_pct": 25, "circuit_opens": 1, "blocked_calls": 2},
        config,
    )
    assert critical["health_status"] == "CRITICAL"
    assert critical["health_score"] < degraded["health_score"]

    summary = build_health_summary(
        {
            "good": {"calls": 10, "failures": 0, "retries": 0, "latency_ms_avg": 100, "requested_items": 10, "coverage_pct": 100, "circuit_opens": 0, "blocked_calls": 0},
            "bad": {"calls": 4, "failures": 2, "retries": 3, "latency_ms_avg": 12000, "requested_items": 4, "coverage_pct": 25, "circuit_opens": 1, "blocked_calls": 2},
        },
        config,
    )
    assert summary["overall_status"] == "CRITICAL"
    assert summary["degraded_sources"] == ["bad"]
    assert len(format_health_log(summary)) == 3

    print("OK: source health combines failures, coverage, latency, retries and circuit state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
