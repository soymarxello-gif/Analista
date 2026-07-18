from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any
import json


@dataclass
class SourceMetrics:
    calls: int = 0
    successes: int = 0
    failures: int = 0
    retries: int = 0
    circuit_opens: int = 0
    blocked_calls: int = 0
    latency_ms_total: float = 0.0
    latency_ms_max: float = 0.0
    requested_items: int = 0
    covered_items: int = 0
    cache_hits: int = 0
    last_error: str | None = None

    def record(
        self,
        *,
        latency_ms: float,
        success: bool,
        requested: int = 0,
        covered: int = 0,
        cache_hits: int = 0,
        error: str | None = None,
    ) -> None:
        self.calls += 1
        self.successes += int(success)
        self.failures += int(not success)
        self.latency_ms_total += latency_ms
        self.latency_ms_max = max(self.latency_ms_max, latency_ms)
        self.requested_items += requested
        self.covered_items += covered
        self.cache_hits += cache_hits
        if error:
            self.last_error = error[:500]

    def summary(self) -> dict[str, Any]:
        data = asdict(self)
        data["latency_ms_total"] = round(self.latency_ms_total, 2)
        data["latency_ms_max"] = round(self.latency_ms_max, 2)
        data["latency_ms_avg"] = (
            round(self.latency_ms_total / self.calls, 2) if self.calls else 0.0
        )
        data["coverage_pct"] = (
            round(100 * self.covered_items / self.requested_items, 2)
            if self.requested_items
            else None
        )
        data["cache_hit_pct"] = (
            round(100 * self.cache_hits / self.covered_items, 2)
            if self.covered_items
            else None
        )
        return data


@dataclass
class TelemetryState:
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    sources: dict[str, SourceMetrics] = field(default_factory=dict)

    def source(self, name: str) -> SourceMetrics:
        return self.sources.setdefault(name, SourceMetrics())

    def snapshot(self) -> dict[str, Any]:
        return {
            "telemetry_schema_version": "1.0",
            "started_at": self.started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "sources": {
                name: metrics.summary()
                for name, metrics in sorted(self.sources.items())
            },
        }


def save_telemetry(
    state: TelemetryState,
    config: dict,
    path: str | None = None,
) -> Path:
    configured = config.get("telemetry", {}).get(
        "output_file", "logs/data_telemetry_latest.json"
    )
    target = Path(path or configured)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(state.snapshot(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(target)
    return target


def timed_call(
    metrics: SourceMetrics,
    func,
    *args,
    requested: int = 0,
    coverage_fn=None,
    cache_hits_fn=None,
    **kwargs,
):
    started = perf_counter()
    try:
        result = func(*args, **kwargs)
        covered = coverage_fn(result) if coverage_fn else requested
        cache_hits = cache_hits_fn(result) if cache_hits_fn else 0
        metrics.record(
            latency_ms=(perf_counter() - started) * 1000,
            success=True,
            requested=requested,
            covered=covered,
            cache_hits=cache_hits,
        )
        return result
    except Exception as exc:
        metrics.record(
            latency_ms=(perf_counter() - started) * 1000,
            success=False,
            requested=requested,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise
