from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.data_telemetry import SourceMetrics, TelemetryState


def main() -> int:
    metrics = SourceMetrics()
    metrics.record(latency_ms=20, success=True, requested=4, covered=3, cache_hits=1)
    metrics.record(latency_ms=10, success=False, requested=1, error="timeout")
    summary = metrics.summary()
    assert summary["calls"] == 2
    assert summary["successes"] == 1
    assert summary["failures"] == 1
    assert summary["latency_ms_avg"] == 15.0
    assert summary["coverage_pct"] == 60.0
    assert summary["cache_hit_pct"] == 33.33
    assert summary["last_error"] == "timeout"

    state = TelemetryState()
    state.sources["prices"] = metrics
    snapshot = state.snapshot()
    assert snapshot["telemetry_schema_version"] == "1.1"
    assert snapshot["health"]["overall_status"] in {"HEALTHY", "DEGRADED", "CRITICAL", "NO_DATA"}
    assert "prices" in snapshot["sources"]
    print("OK: structured data-source telemetry validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
